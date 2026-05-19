# Klein Physics and Math Engine

**Version v1.0 - 2026-01-07**

This document defines the Physics Engine of the Geodesic Protocol.

This is a **Discrete Geodesic Optimization** modified by volumetric fields. We treat code execution as physical action following the **Principle of Least Action**.

---

## 1. The Core Equation: Discrete Action

In the Geodesic Protocol, "Code" is the path that minimizes the **Action (S)**.
Unlike standard physics (which integrates over continuous time), our graph is a **Discrete Lattice**. We use a Discrete Action Summation.

### 1.1 The Formula

For a path P consisting of a sequence of Edges e1, e2, ... en:

    S(P) = SUM_i [ L_i * (Z_i + epsilon) * (1 - Phi_local) ] + H(n_end)

**Where:**

| Symbol | Name | Description | Default |
|--------|------|-------------|---------|
| L_i | Edge Length | Euclidean distance between nodes | - |
| Z_i | Scalar Impedance | Material resistance (0.0 = superconductor, 1.0 = standard rail) | 1.0 |
| epsilon | Base Action Constant | Ensures non-zero cost even for superconductors | 0.001 |
| Phi_local | Field Potential | Gravity/Repulsion modifier at edge midpoint | 0.0 |
| H(n) | Heuristic | Estimated cost to reach the Sink | - |

### 1.2 Safety Rules

1. **Epsilon-Safety**: Even zero-impedance paths have non-zero traversal cost, preventing infinite loops.
2. **Phi-Clamping**: Phi is clamped to a maximum of **0.95** to prevent negative edge weights (which would invalidate A*).

### 1.3 Admissible Heuristic

    H(n) = EuclideanDist(n, goal) * Z_min_global

We scale by the lowest impedance in the graph to ensure the heuristic never overestimates (A* admissibility).

### 1.4 The Solver Rule

    P_optimal = argmin_P S(P)

The Solver selects the path where **Action (S)** is lowest. The unit of cost is the **Geodesic Meter (Gm)** - the effective distance after impedance and field effects.

### 1.5 Implementation Reference

```python
# From src/klein/sim/physics.py

EPSILON = 0.001   # Base action constant
PHI_MAX = 0.95    # Maximum field potential (prevents negative weights)

def compute_edge_cost(edge_data, field_manager, epsilon=EPSILON):
    L = edge_data.length           # Euclidean distance
    Z = edge_data.impedance        # Scalar impedance
    
    # Get Phi at edge midpoint (clamped to PHI_MAX)
    field_effect = field_manager.compute_phi(edge_data.midpoint)
    phi = field_effect.phi
    
    # Formula: Cost = L * (Z + epsilon) * (1 - Phi_local)
    cost = L * (Z + epsilon) * (1.0 - phi)
    return max(cost, epsilon)  # Ensure positive
```

---

## 2. Field Math (Volumetric Modifiers)

Fields are the mechanism by which the user "programs" the path without touching the nodes. They modify the value of Phi in the equation above.

### 2.1 Gravity Well (Attractor)

A Gaussian function that lowers the cost of traversing nodes near its center.

    Phi_grav(p) = S_strength * exp( -dist_sq / R_sq )

| Parameter | Description |
|-----------|-------------|
| p | Query position |
| C | Well center |
| R | Well radius (falloff) |
| S | Strength (0.0-1.0) |

**Effect:** If a path goes through the well, the term (1 - Phi) becomes small (e.g., 0.2). This makes the path "cheap" in terms of Action, effectively pulling the carrier into the well.

### 2.2 Repulsor (Barrier)

An inverse-square function that raises the cost of traversing near its center.

    Phi_rep(p) = -S_strength / dist_sq

**Effect:** As distance approaches 0, the term (1 - Phi) becomes large (Phi is negative). The Solver will go to extreme lengths to avoid this region.

### 2.3 Implementation Reference

```python
# From src/klein/sim/physics.py - FieldManager.compute_phi()

if field_type == "gravity":
    # Gaussian: Phi = S * exp(-dist_sq / R_sq)
    phi_contribution = strength * math.exp(-dist_sq / (radius ** 2))
    
elif field_type == "repulsor":
    # Inverse-square: Phi = -S / dist_sq
    phi_contribution = -strength / max(dist_sq, 1e-6)

# Final clamping
clamped_phi = min(total_phi, PHI_MAX)  # 0.95 max
```

---

## 3. The Backfill Algorithm (The Solver)

This is the step-by-step logic the engine executes when "Collapse" is triggered.

### Phase 1: The Potential Map (A* Flood Fill)

1. **Initialize:** Set cost of Source Node to 0. All others to infinity.
2. **Open Set:** Create a priority queue (min-heap by f-score).
3. **Expand:** Pop lowest f-score node. For each neighbor:
   - Query FieldManager for local Phi (apply clamping)
   - Compute tentative_cost = g[current] + edge_cost
   - If better than recorded, update and add to open set

### Phase 2: The Geodesic Trace (Backtracking)

1. **Start:** Begin at the Sink Node.
2. **Loop:** Follow the came_from chain back to Source.
3. **Trace:** Record the path as a sequence of node IDs.

### Phase 3: Logic Validation (Parity Check)

> Note: Not implemented in v1.0. Future versions will support gate insertion.

1. **Input State:** User defines Source as TRUE.
2. **Output Constraint:** User defines Sink as FALSE (Requires Inversion).
3. **Path Trace:** Simulate a "Test Particle" down the path.
4. **If Mismatch:** Insert Shape_Tetra (NOT Gate) at lowest-energy segment.

### 3.1 Implementation Reference

```python
# From src/klein/sim/physics.py - GeodesicSolver.solve()

def solve(self, source, sink):
    open_set = [(0.0, 0, source)]  # (f_score, counter, node_id)
    g_score = {source: 0.0}
    came_from = {}
    
    while open_set:
        _, _, current = heapq.heappop(open_set)
        
        if current == sink:
            path = self._reconstruct_path(came_from, sink)
            return PathResult(success=True, path=path, ...)
        
        for neighbor in self._graph.successors(current):
            edge_cost = compute_edge_cost(edge_data, self._field_manager)
            tentative_g = g_score[current] + edge_cost
            
            if tentative_g < g_score.get(neighbor, inf):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                h = compute_heuristic(neighbor_pos, goal_pos, z_min)
                heapq.heappush(open_set, (tentative_g + h, counter, neighbor))
```

---

## 4. Wave Mechanics (Unsafe Mode)

When debugging, we switch from A* (single optimal path) to a **Markov Chain** (stochastic reachability analysis).

### 4.1 The Probability Matrix

At a fork node with exits A and B, probability splits inversely proportional to action cost:

    P(A) = (1/S(A)) / (1/S(A) + 1/S(B))

**Example:**
- Path A through a Gravity Well: Cost = 2 Gm
- Path B through empty space: Cost = 10 Gm
- P(A) = (1/2) / (1/2 + 1/10) = 0.5 / 0.6 = **83%**

### 4.2 Implementation Reference

```python
# From src/klein/sim/physics.py - WaveSolver.compute_transition_probabilities()

def compute_transition_probabilities(self, node):
    inverse_costs = {}
    for neighbor in successors:
        cost = compute_edge_cost(edge_data, self._field_manager)
        inverse_costs[neighbor] = 1.0 / max(cost, EPSILON)
    
    total = sum(inverse_costs.values())
    return {n: inv / total for n, inv in inverse_costs.items()}
```

---

## 5. Hardware Translation Formulas

How do these abstract numbers map to physical reality?

### 5.1 Tier 1: EWOD (Digital Microfluidics)

For electrostatic systems like OpenDrop, we map the abstract fields to the **Lippmann-Young equation**.

#### Field Potential (Phi) to Voltage (V)

In the simulator, a "Gravity Well" is a region of low potential energy. On the hardware, activating an electrode reduces the surface tension of the droplet, creating a physical low-energy state.

    V_applied = V_max * sqrt(Phi_local)

| Phi_local | V_applied (at V_max=300V) | Notes |
|-----------|---------------------------|-------|
| 0.80 | 268V (89%) | Strong pull |
| 0.50 | 212V (71%) | Moderate pull |
| 0.95 | 292V (97%) | Maximum (clamped) |

**Translation:** If the Solver places a Gravity Well of strength Phi = 0.8 at a node to pull a droplet, the Driver must actuate that electrode at sqrt(0.8) = 89% of V_max.

**Clamping:** Since Phi is clamped to 0.95 (Section 1), we never exceed the dielectric breakdown voltage (V_max).

#### Action (S) to Duration (t)

The "Cost" of a path represents the difficulty of traversal. On an EWOD chip, "Difficulty" implies "Viscosity" or "Drag." A higher cost edge requires more time for the droplet to successfully complete the transport.

    Duration_ms = S_edge * k_viscosity

| Parameter | Description | Typical Value |
|-----------|-------------|---------------|
| S_edge | Action cost of the move (Gm) | - |
| k_viscosity | Hardware constant | 10 ms/Gm |

**Effect:** If the droplet moves across a "Dirty" electrode (Z = 2.0), the Action S doubles. The Compiler translates this into a duration_ms of 20ms instead of 10ms to prevent "Droplet Tearing" faults.

### 5.2 Tier 2: FPGA (Time Delay)

On a chip, "Distance" is "Time."

    Delay_ns = S_action * k_clock

The Compiler inserts buffer gates (NOPs) to ensure the signal arrives exactly when the logic dictates, maintaining synchronization without a global clock.

### 5.3 Tier 3: 3D Print (Slope)

In a gravity-fed marble logic system:

    theta_tilt = arccos( 1 / (1 + Phi_grav) )

| Phi_grav | theta_tilt | Effect |
|----------|------------|--------|
| 0.0 | 0 deg | Flat (slow) |
| 0.5 | 48 deg | Medium slope |
| 0.95 | 61 deg | Steep (fast) |

- **High Gravity** = Steep Slope (Fast)
- **Repulsor** = Uphill Slope (Slow/Impossible)

---

## 6. Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1.0 | 2026-01-07 | Initial release: Scalar impedance, A* solver, Gaussian/Inverse-square fields |
| v2.0 | TBD | Planned: Metric tensors (g_ij), Hamiltonian coverage mode |
