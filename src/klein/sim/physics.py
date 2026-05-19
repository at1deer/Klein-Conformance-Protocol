"""
Klein Physics & Math Engine v1.0

Discrete optical pathfinding plus reversible random walk on the same weighted
graph, intended for the Klein Protocol's *planning* side. None of this is a
claim about substrate execution; see CLAIMS_LEDGER.md for the evidence side.

Two analogies are honored by the math here and used as the design vocabulary:

1.  GeodesicSolver. Fermat's Principle of Least Optical Path on a discrete
    graph. The deterministic solver minimizes the sum of edge optical-path
    lengths

        L_edge = L_i · (Z_i + ε) · (1 − Φ_local)

    where ``n_eff(midpoint) = (Z + ε)(1 − Φ)`` plays the role of a
    spatially-varying refractive index. ``Z`` is local resistance to traversal,
    ``Φ`` is a refractive-index modulator field, attractors lower n_eff, and
    repulsor barriers raise it. Light minimizes ∫ n ds; this solver minimizes
    its discrete graph analogue with A*.

2.  WaveSolver. Natural reversible random walk on the same weighted graph,
    Doyle-Snell conductance form for a resistor network. Treat each edge as a
    resistor with conductance ``c_ij = 1 / edge_cost``. The transition law is

        P(i → j) = c_ij / Σ_k c_ik

    This is the standard reversible Markov chain on the impedance graph
    (Doyle & Snell, *Random Walks and Electric Networks*). It is **not**
    quantum-mechanical wave mechanics; nothing here uses complex amplitudes
    or interference.

Core Equation (Discrete Fermat / Optical Path):
    S(P) = Σ_i [ L_i · (Z_i + ε) · (1 − Φ_local) ] + H(n_end)

Where:
    - L_i: Euclidean edge length
    - Z_i: Scalar impedance (0.0 = superconductor, 1.0 = standard)
    - ε: Base path-cost constant (~0.001); prevents zero-cost paths
    - Φ_local: Refractive-index modulator at the edge midpoint, clamped to
      (−∞, 0.95]
    - n_eff(midpoint) = (Z + ε)(1 − Φ) is the discrete effective refractive
      index
    - H(n): Admissible A* heuristic = EuclideanDist(n, goal) × Z_min_global

The unit of cost is the **Geodesic Meter (Gm)**, the effective optical-path
length on a graph after impedance and refractive-index modulation. This is the
*planning* prior. KCP evidence (runbook → trace → HAIL → manifest) verifies
what was actually done; the planning prior here does not.

Why this vocabulary changed (v1.0.0a1 reframe): earlier drafts called S(P) a
"Discrete Action" minimized by a "Principle of Least Action" and called the
attractor field a "gravity well". Those names borrowed prestige from
Lagrangian mechanics and quantum wave mechanics that the math does not
support: real action is stationary (not minimized), real potentials are
additive (not multiplicative), and quantum wave mechanics requires complex
amplitudes (not real-valued inverse-cost weights). The new names (Fermat;
Doyle-Snell conductance) correspond exactly to what this code does and
connect to standard literature.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Sequence

import networkx as nx
import numpy as np
from numpy.typing import NDArray

from klein.common.models import KleinProject, KleinNode, KleinEdge, KleinField


# =============================================================================
# Constants
# =============================================================================

EPSILON: float = 0.001  # Base path-cost constant (prevents zero-cost paths)
PHI_MAX: float = 0.95   # Refractive-index modulator clamp (prevents negative edge weights)
DEFAULT_IMPEDANCE: float = 1.0  # Default impedance for edges without explicit value


# =============================================================================
# Field Types
# =============================================================================

class FieldType(str, Enum):
    """Supported refractive-index modulator field types.

    Each field type lowers or raises the local effective refractive index
    n_eff(p) = (Z + ε)(1 − Φ(p)) at points near its centre, which in turn
    raises or lowers the discrete Fermat optical-path length of any edge that
    passes through that region.
    """

    ATTRACTOR = "attractor"  # Refractive-index well (Gaussian; lowers n_eff)
    REPULSOR = "repulsor"    # Refractive-index barrier (inverse-square; raises n_eff)


@dataclass
class FieldEffect:
    """Computed field effect at a point."""
    phi: float              # Total field potential
    contributors: list[str] # Field types that contributed


# =============================================================================
# Field Manager
# =============================================================================

class FieldManager:
    """
    Manages volumetric refractive-index modulator fields that bias path costs.

    Fields are the mechanism by which the caller "programs" the path without
    touching nodes directly: they modify the Φ value in the discrete Fermat
    edge-cost expression L · (Z + ε) · (1 − Φ_local). Attractors lower n_eff
    near a centre and pull the optical path toward themselves; repulsor
    barriers raise n_eff and push the optical path away.
    """
    
    def __init__(self, fields: Sequence[KleinField] | None = None):
        self._fields: list[KleinField] = list(fields) if fields else []
    
    def add_field(self, field: KleinField) -> None:
        """Add a field to the manager."""
        self._fields.append(field)
    
    def clear(self) -> None:
        """Remove all fields."""
        self._fields.clear()
    
    def compute_phi(self, position: NDArray[np.floating]) -> FieldEffect:
        """
        Compute the total refractive-index modulator Φ at a given position.

        Args:
            position: 3D position vector [x, y, z]

        Returns:
            FieldEffect with clamped phi value and list of contributors
        """
        total_phi = 0.0
        contributors: list[str] = []

        for f in self._fields:
            center = np.array(f.center, dtype=np.float64)
            dist_sq = float(np.sum((position - center) ** 2))
            dist = math.sqrt(dist_sq) if dist_sq > 0 else 1e-10

            field_type = f.type.lower()

            if field_type == FieldType.ATTRACTOR.value:
                # Attractor (refractive-index well): Gaussian
                # Φ_attr(p) = S_strength · exp(-||p − C||² / R²)
                # Lowers n_eff = (Z + ε)(1 − Φ) near the centre, shortening
                # the discrete Fermat optical-path length of nearby edges.
                radius = f.radius if f.radius and f.radius > 0 else 1.0
                phi_contribution = f.strength * math.exp(-dist_sq / (radius ** 2))
                total_phi += phi_contribution
                if abs(phi_contribution) > 1e-6:
                    contributors.append(FieldType.ATTRACTOR.value)

            elif field_type == FieldType.REPULSOR.value:
                # Repulsor (refractive-index barrier): inverse-square
                # Φ_rep(p) = −1 · S_strength / ||p − C||²
                # As distance → 0, n_eff → large, so the optical-path
                # length diverges and the solver routes around the region.
                phi_contribution = -f.strength / max(dist_sq, 1e-6)
                total_phi += phi_contribution
                if abs(phi_contribution) > 1e-6:
                    contributors.append(FieldType.REPULSOR.value)

        # Clamp Φ to maximum of PHI_MAX (0.95) to keep (1 − Φ) ≥ 0.05 and
        # therefore n_eff strictly positive, which A* admissibility requires.
        clamped_phi = min(total_phi, PHI_MAX)

        return FieldEffect(phi=clamped_phi, contributors=contributors)


# =============================================================================
# Graph Builder
# =============================================================================

@dataclass
class EdgeData:
    """Computed edge data for the physics graph."""
    length: float           # Euclidean distance L
    impedance: float        # Scalar impedance Z
    midpoint: NDArray[np.floating]  # For field calculations
    from_id: str
    to_id: str


def build_graph(project: KleinProject) -> tuple[nx.DiGraph, dict[str, NDArray[np.floating]]]:
    """
    Build a NetworkX directed graph from a Klein project.
    
    Args:
        project: The Klein project definition
        
    Returns:
        Tuple of (graph, node_positions)
    """
    G = nx.DiGraph()
    positions: dict[str, NDArray[np.floating]] = {}
    
    # Add nodes with positions
    for node in project.nodes:
        pos = np.array(node.pos, dtype=np.float64)
        positions[node.id] = pos
        G.add_node(node.id, pos=pos, type=node.type, state=node.state)
    
    # Add edges with computed data
    for edge in project.edges:
        from_id = edge.from_  # Note: aliased field
        to_id = edge.to
        
        if from_id not in positions or to_id not in positions:
            continue  # Skip invalid edges
        
        from_pos = positions[from_id]
        to_pos = positions[to_id]
        
        # Compute edge properties
        diff = to_pos - from_pos
        length = float(np.linalg.norm(diff))
        midpoint = (from_pos + to_pos) / 2.0
        impedance = edge.impedance if edge.impedance is not None else DEFAULT_IMPEDANCE
        
        edge_data = EdgeData(
            length=length,
            impedance=impedance,
            midpoint=midpoint,
            from_id=from_id,
            to_id=to_id,
        )
        
        G.add_edge(from_id, to_id, data=edge_data)
    
    return G, positions


# =============================================================================
# Cost Functions
# =============================================================================

def compute_edge_cost(
    edge_data: EdgeData,
    field_manager: FieldManager,
    epsilon: float = EPSILON,
) -> float:
    """
    Compute the discrete Fermat optical-path cost of traversing an edge.

    Formula: Cost = L · (Z + ε) · (1 − Φ_local), which is the same as
    L · n_eff(midpoint) where n_eff = (Z + ε)(1 − Φ).

    Args:
        edge_data: The edge properties
        field_manager: Manager for refractive-index modulator fields
        epsilon: Base path-cost constant

    Returns:
        The optical-path cost in Geodesic Meters (Gm).
    """
    L = edge_data.length
    Z = edge_data.impedance

    # Get the local refractive-index modulator at the edge midpoint
    field_effect = field_manager.compute_phi(edge_data.midpoint)
    phi = field_effect.phi

    # Compute cost: L · (Z + ε) · (1 − Φ)
    # Φ is already clamped to PHI_MAX so (1 − Φ) ≥ 0.05 and n_eff > 0.
    cost = L * (Z + epsilon) * (1.0 - phi)

    return max(cost, epsilon)  # Ensure strictly positive cost


def compute_heuristic(
    position: NDArray[np.floating],
    goal: NDArray[np.floating],
    z_min_global: float,
) -> float:
    """
    Compute admissible A* heuristic.
    
    Formula: H(n) = EuclideanDist(n, goal) × Z_min_global
    
    This heuristic never overestimates because it uses the minimum possible
    impedance, making it admissible for A*.
    
    Args:
        position: Current node position
        goal: Goal node position
        z_min_global: Minimum impedance in the graph
        
    Returns:
        Admissible heuristic estimate
    """
    dist = float(np.linalg.norm(goal - position))
    return dist * max(z_min_global, EPSILON)


# =============================================================================
# Path Result
# =============================================================================

@dataclass
class PathResult:
    """Result of a pathfinding operation."""
    success: bool
    path: list[str]                          # Sequence of node IDs
    total_cost: float                        # Total optical-path cost (Gm)
    explored_count: int                      # Number of nodes explored
    edge_costs: dict[tuple[str, str], float] = field(default_factory=dict)
    
    @property
    def path_length(self) -> int:
        """Number of nodes in path."""
        return len(self.path)
    
    @property
    def edge_count(self) -> int:
        """Number of edges in path."""
        return max(0, len(self.path) - 1)


@dataclass
class WaveResult:
    """Result of reversible random-walk reachability analysis."""
    probabilities: dict[str, float]  # Node ID → probability of reaching
    expected_cost: float             # Expected optical-path cost
    paths: list[tuple[list[str], float]]  # (path, probability) pairs


# =============================================================================
# Geodesic Solver (A*)
# =============================================================================

class GeodesicSolver:
    """
    A* pathfinding solver that minimizes the discrete Fermat optical-path
    length on a graph whose edges have refractive index n_eff = (Z + ε)(1 − Φ).

    This is the deterministic side of the Klein Physics Engine: Fermat's
    Principle of Least Optical Path applied to a graph. Volumetric attractor
    and repulsor fields modify n_eff locally so the optimal path is "bent"
    just as a light ray would be in a medium with a spatially-varying index.
    """
    
    def __init__(
        self,
        graph: nx.DiGraph,
        positions: dict[str, NDArray[np.floating]],
        field_manager: FieldManager | None = None,
    ):
        self._graph = graph
        self._positions = positions
        self._field_manager = field_manager or FieldManager()
        self._z_min_global = self._compute_z_min()
    
    def _compute_z_min(self) -> float:
        """Compute minimum impedance across all edges."""
        z_min = float('inf')
        for _, _, data in self._graph.edges(data=True):
            edge_data: EdgeData = data['data']
            z_min = min(z_min, edge_data.impedance)
        return z_min if z_min != float('inf') else EPSILON
    
    def solve(self, source: str, sink: str) -> PathResult:
        """
        Find the optimal geodesic path from source to sink.
        
        This implements the three-phase algorithm:
        1. Phase 1 (Potential Map): A* flood fill with field-modified costs
        2. Phase 2 (Geodesic Trace): Backtrack to extract path
        3. Phase 3 (Logic Validation): Not implemented (requires gate types)
        
        Args:
            source: Source node ID
            sink: Sink (goal) node ID
            
        Returns:
            PathResult with optimal path and cost
        """
        if source not in self._graph or sink not in self._graph:
            return PathResult(
                success=False,
                path=[],
                total_cost=float('inf'),
                explored_count=0,
            )
        
        goal_pos = self._positions[sink]
        
        # Priority queue: (f_score, counter, node_id)
        # Counter breaks ties deterministically
        counter = 0
        open_set: list[tuple[float, int, str]] = []
        heapq.heappush(open_set, (0.0, counter, source))
        
        # Cost tracking
        g_score: dict[str, float] = {source: 0.0}
        came_from: dict[str, str] = {}
        edge_costs: dict[tuple[str, str], float] = {}
        
        # Closed set
        closed_set: set[str] = set()
        explored_count = 0
        
        while open_set:
            _, _, current = heapq.heappop(open_set)
            
            if current in closed_set:
                continue
            
            closed_set.add(current)
            explored_count += 1
            
            # Goal reached!
            if current == sink:
                path = self._reconstruct_path(came_from, sink)
                return PathResult(
                    success=True,
                    path=path,
                    total_cost=g_score[sink],
                    explored_count=explored_count,
                    edge_costs=edge_costs,
                )
            
            # Explore neighbors
            for neighbor in self._graph.successors(current):
                if neighbor in closed_set:
                    continue
                
                # Get edge data and compute cost
                edge_data: EdgeData = self._graph[current][neighbor]['data']
                edge_cost = compute_edge_cost(edge_data, self._field_manager)
                
                tentative_g = g_score[current] + edge_cost
                
                if tentative_g < g_score.get(neighbor, float('inf')):
                    # Better path found
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    edge_costs[(current, neighbor)] = edge_cost
                    
                    # Compute heuristic
                    neighbor_pos = self._positions[neighbor]
                    h = compute_heuristic(neighbor_pos, goal_pos, self._z_min_global)
                    f = tentative_g + h
                    
                    counter += 1
                    heapq.heappush(open_set, (f, counter, neighbor))
        
        # No path found
        return PathResult(
            success=False,
            path=[],
            total_cost=float('inf'),
            explored_count=explored_count,
        )
    
    def _reconstruct_path(self, came_from: dict[str, str], current: str) -> list[str]:
        """Backtrack to reconstruct the path from source to sink."""
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path
    
    def compute_potential_map(self, source: str) -> dict[str, float]:
        """
        Compute the potential (cost) map from source to all reachable nodes.
        
        This is Phase 1 of the algorithm without a specific goal.
        Useful for visualization ("blue liquid flooding").
        
        Args:
            source: Source node ID
            
        Returns:
            Dict mapping node ID → minimum cost to reach from source
        """
        if source not in self._graph:
            return {}
        
        costs: dict[str, float] = {source: 0.0}
        counter = 0
        open_set: list[tuple[float, int, str]] = [(0.0, counter, source)]
        closed_set: set[str] = set()
        
        while open_set:
            cost, _, current = heapq.heappop(open_set)
            
            if current in closed_set:
                continue
            closed_set.add(current)
            
            for neighbor in self._graph.successors(current):
                if neighbor in closed_set:
                    continue
                
                edge_data: EdgeData = self._graph[current][neighbor]['data']
                edge_cost = compute_edge_cost(edge_data, self._field_manager)
                tentative = cost + edge_cost
                
                if tentative < costs.get(neighbor, float('inf')):
                    costs[neighbor] = tentative
                    counter += 1
                    heapq.heappush(open_set, (tentative, counter, neighbor))
        
        return costs


# =============================================================================
# Random Walk on Impedance Graph (Doyle-Snell conductance form)
# =============================================================================

class WaveSolver:
    """
    Natural reversible random walk on the same weighted graph used by
    ``GeodesicSolver``.

    Treat each directed edge ``(i → j)`` as a resistor with conductance
    ``c_ij = 1 / edge_cost(i → j)``. The transition probability out of node
    ``i`` is then the Doyle-Snell conductance form for a random walk on a
    resistor network:

        P(i → j) = c_ij / Σ_k c_ik
                 = (1 / cost(i → j)) / Σ_k (1 / cost(i → k))

    This is a textbook reversible Markov chain on the impedance graph
    (Doyle & Snell, *Random Walks and Electric Networks*). It is **not**
    quantum-mechanical wave mechanics; there are no complex amplitudes and
    no interference. The name "WaveSolver" is retained for API stability;
    it could equivalently be called ``ResistorNetworkSolver`` or
    ``RandomWalkSolver``.

    Use this instead of the deterministic GeodesicSolver when you want
    stochastic reachability or to model fork-then-merge behaviour where
    "more conductive" branches simply attract more walkers.

    TODO(reframe/fermat-conductance): expose an optional temperature-like
    knob ``beta`` so transition probabilities become
    ``P(i → j) ∝ (1 / cost(i → j))^beta`` with ``beta = 1`` reproducing the
    current Doyle-Snell behaviour exactly. Any real ``beta > 0`` is still a
    valid conductance on a transformed edge weight, so this stays inside
    the resistor-network interpretation. (Flagged for review; do not ship
    until requested.)
    """
    
    def __init__(
        self,
        graph: nx.DiGraph,
        positions: dict[str, NDArray[np.floating]],
        field_manager: FieldManager | None = None,
    ):
        self._graph = graph
        self._positions = positions
        self._field_manager = field_manager or FieldManager()
    
    def compute_transition_probabilities(self, node: str) -> dict[str, float]:
        """
        Compute transition probabilities from a node to its successors.

        Each outgoing edge ``(node → j)`` is treated as a resistor with
        conductance ``c_j = 1 / edge_cost(node → j)``. The Doyle-Snell
        transition law for a reversible random walk on a resistor network
        then gives

            P(node → j) = c_j / Σ_k c_k

        i.e. the conductance of the chosen edge divided by the total
        conductance leaving ``node``. More conductive edges (cheaper
        optical-path cost) attract proportionally more probability mass.

        Args:
            node: Current node ID

        Returns:
            Dict mapping successor node ID → transition probability.
        """
        if node not in self._graph:
            return {}

        successors = list(self._graph.successors(node))
        if not successors:
            return {}

        # Edge conductances: c_j = 1 / cost(node → j)
        conductances: dict[str, float] = {}
        for neighbor in successors:
            edge_data: EdgeData = self._graph[node][neighbor]['data']
            cost = compute_edge_cost(edge_data, self._field_manager)
            conductances[neighbor] = 1.0 / max(cost, EPSILON)

        # Total node conductance Σ_k c_k
        total_conductance = sum(conductances.values())
        if total_conductance <= 0:
            # Degenerate case: fall back to uniform.
            uniform_p = 1.0 / len(successors)
            return {n: uniform_p for n in successors}

        # P(node → j) = c_j / Σ_k c_k
        return {n: c / total_conductance for n, c in conductances.items()}
    
    def compute_reachability(
        self,
        source: str,
        max_depth: int = 100,
        min_probability: float = 1e-6,
    ) -> dict[str, float]:
        """
        Compute probability of reaching each node from source.
        
        Uses breadth-first probability propagation with pruning.
        
        Args:
            source: Source node ID
            max_depth: Maximum propagation depth
            min_probability: Prune paths below this probability
            
        Returns:
            Dict mapping node ID → probability of reaching
        """
        if source not in self._graph:
            return {}
        
        # Probability at each node (can accumulate from multiple paths)
        reach_prob: dict[str, float] = {source: 1.0}
        
        # Frontier: (node, accumulated_probability, depth)
        frontier: list[tuple[str, float, int]] = [(source, 1.0, 0)]
        
        while frontier:
            current, prob, depth = frontier.pop(0)
            
            if depth >= max_depth:
                continue
            
            trans_probs = self.compute_transition_probabilities(current)
            
            for neighbor, trans_p in trans_probs.items():
                new_prob = prob * trans_p
                
                if new_prob < min_probability:
                    continue
                
                # Accumulate probability (multiple paths can reach same node)
                reach_prob[neighbor] = reach_prob.get(neighbor, 0.0) + new_prob
                frontier.append((neighbor, new_prob, depth + 1))
        
        return reach_prob
    
    def sample_path(
        self,
        source: str,
        sink: str,
        rng: np.random.Generator | None = None,
        max_steps: int = 1000,
    ) -> tuple[list[str], bool]:
        """
        Sample a single stochastic path from source to sink.
        
        Args:
            source: Source node ID
            sink: Sink node ID
            rng: Random number generator (uses default if None)
            max_steps: Maximum path length
            
        Returns:
            Tuple of (path, reached_sink)
        """
        if rng is None:
            rng = np.random.default_rng()
        
        path = [source]
        current = source
        
        for _ in range(max_steps):
            if current == sink:
                return path, True
            
            trans_probs = self.compute_transition_probabilities(current)
            if not trans_probs:
                break  # Dead end
            
            # Sample next node according to probabilities
            neighbors = list(trans_probs.keys())
            probs = [trans_probs[n] for n in neighbors]
            
            idx = rng.choice(len(neighbors), p=probs)
            current = neighbors[idx]
            path.append(current)
        
        return path, current == sink


# =============================================================================
# High-Level API
# =============================================================================

def solve_geodesic(
    project: KleinProject,
    source: str,
    sink: str,
) -> PathResult:
    """
    Find the optimal geodesic path in a Klein project.
    
    This is the main entry point for the physics engine.
    
    Args:
        project: The Klein project definition
        source: Source node ID
        sink: Sink (goal) node ID
        
    Returns:
        PathResult with optimal path and cost
    """
    graph, positions = build_graph(project)
    field_manager = FieldManager(project.fields)
    solver = GeodesicSolver(graph, positions, field_manager)
    return solver.solve(source, sink)


def compute_path_cost(
    project: KleinProject,
    path: list[str],
) -> float:
    """
    Compute the total discrete Fermat optical-path cost of a given path.

    Args:
        project: The Klein project definition
        path: Sequence of node IDs

    Returns:
        Total optical-path cost in Geodesic Meters (Gm); ``inf`` if the
        path references an edge that does not exist in the project graph.
    """
    if len(path) < 2:
        return 0.0

    graph, _ = build_graph(project)
    field_manager = FieldManager(project.fields)

    total_cost = 0.0
    for i in range(len(path) - 1):
        from_id, to_id = path[i], path[i + 1]
        if not graph.has_edge(from_id, to_id):
            return float('inf')  # Invalid path

        edge_data: EdgeData = graph[from_id][to_id]['data']
        total_cost += compute_edge_cost(edge_data, field_manager)

    return total_cost


def analyze_wave(
    project: KleinProject,
    source: str,
    max_depth: int = 100,
) -> dict[str, float]:
    """
    Compute stochastic reachability from a source node.
    
    Args:
        project: The Klein project definition
        source: Source node ID
        max_depth: Maximum propagation depth
        
    Returns:
        Dict mapping node ID → probability of reaching
    """
    graph, positions = build_graph(project)
    field_manager = FieldManager(project.fields)
    solver = WaveSolver(graph, positions, field_manager)
    return solver.compute_reachability(source, max_depth)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Constants
    "EPSILON",
    "PHI_MAX",
    "DEFAULT_IMPEDANCE",
    # Field types
    "FieldType",
    "FieldEffect",
    "FieldManager",
    # Graph building
    "EdgeData",
    "build_graph",
    # Cost functions
    "compute_edge_cost",
    "compute_heuristic",
    # Results
    "PathResult",
    "WaveResult",
    # Solvers
    "GeodesicSolver",
    "WaveSolver",
    # High-level API
    "solve_geodesic",
    "compute_path_cost",
    "analyze_wave",
]
