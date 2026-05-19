# Klein Physics and Math Engine

**Version v1.0 - 2026-01-07**
**Vocabulary reframe: v1.0.0a1 - 2026-05-19** (Fermat + Doyle-Snell; see §6)

This document defines the Physics Engine of the Klein Conformance Protocol's
*planning* side.

The engine is a **Discrete Geodesic Optimization on a weighted graph**,
modified by volumetric refractive-index modulator fields. We treat the
optimal plan as the discrete analogue of an optical ray under **Fermat's
Principle of Least Optical Path**.

This is the planning prior. The KCP evidence stack
(runbook → trace → HAIL → manifest) verifies what was actually executed on
substrate. Nothing in this document is a claim about physical truth, sensor
proof, hardware attestation, or HIL execution.

---

## 1. The Core Equation: Discrete Fermat / Optical Path

In the Geodesic Protocol, the planned "path" is the discrete curve that
minimizes the **optical-path length S(P)** along a weighted graph.

Each edge contributes its Euclidean length multiplied by an effective
refractive index `n_eff` that depends on the local impedance `Z` and the
refractive-index modulator `Φ`:

    n_eff(midpoint) = (Z + epsilon) * (1 - Phi_local)

Fermat's principle says light minimizes `∫ n ds`. Discretized to a graph,
that is exactly what this solver does.

### 1.1 The Formula

For a path P consisting of a sequence of edges e1, e2, ..., en:

    S(P) = SUM_i [ L_i * (Z_i + epsilon) * (1 - Phi_local) ] + H(n_end)
         = SUM_i [ L_i * n_eff(midpoint_i) ]              + H(n_end)

**Where:**

| Symbol | Name | Description | Default |
|--------|------|-------------|---------|
| L_i | Edge Length | Euclidean distance between nodes | - |
| Z_i | Scalar Impedance | Material resistance (0.0 = superconductor, 1.0 = standard rail) | 1.0 |
| epsilon | Base path-cost constant | Ensures non-zero edge cost even for superconductors | 0.001 |
| Phi_local | Refractive-index modulator | Field-induced modulation at the edge midpoint | 0.0 |
| n_eff | Effective refractive index | (Z + epsilon) * (1 - Phi_local) | - |
| H(n) | Heuristic | Admissible A* estimate of cost-to-go to the Sink | - |

### 1.2 Safety Rules

1. **Epsilon-Safety**: Even zero-impedance edges have non-zero traversal cost,
   so the optical-path length cannot collapse to zero and trap A* in cycles.
2. **Phi-Clamping**: Phi is clamped to a maximum of **0.95** so that
   `(1 - Phi) >= 0.05` and `n_eff > 0`. A* admissibility requires strictly
   positive edge weights.

### 1.3 Admissible Heuristic

    H(n) = EuclideanDist(n, goal) * Z_min_global

We scale by the lowest impedance in the graph to ensure the heuristic never
overestimates remaining cost. This is the optical-path equivalent of using
the lowest refractive index anywhere in the medium as an under-estimate.

### 1.4 The Solver Rule

    P_optimal = argmin_P S(P)

The Solver selects the path where the **discrete Fermat optical-path length
S(P)** is lowest. The unit of cost is the **Geodesic Meter (Gm)**, the
effective optical-path length on the graph after impedance and
refractive-index modulation.

### 1.5 Implementation Reference

```python
# From src/klein/sim/physics.py

EPSILON = 0.001   # Base path-cost constant
PHI_MAX = 0.95    # Refractive-index modulator clamp

def compute_edge_cost(edge_data, field_manager, epsilon=EPSILON):
    L = edge_data.length           # Euclidean distance
    Z = edge_data.impedance        # Scalar impedance

    # Local refractive-index modulator at the edge midpoint (clamped to PHI_MAX)
    field_effect = field_manager.compute_phi(edge_data.midpoint)
    phi = field_effect.phi

    # Formula: Cost = L * (Z + epsilon) * (1 - Phi_local) = L * n_eff
    cost = L * (Z + epsilon) * (1.0 - phi)
    return max(cost, epsilon)  # Ensure strictly positive
```

---

## 2. Field Math (Volumetric Refractive-Index Modulators)

Fields are the mechanism by which the caller "programs" the path without
touching the nodes. They modify Φ (and therefore `n_eff`) locally.

### 2.1 Attractor (refractive-index well)

A Gaussian function that **lowers** `n_eff` near its centre, shortening the
optical-path length of nearby edges and bending the optimal path toward
itself (just as a region of lower refractive index does for a real ray).

    Phi_attr(p) = S_strength * exp( -dist_sq / R_sq )

| Parameter | Description |
|-----------|-------------|
| p | Query position |
| C | Well centre |
| R | Well radius (falloff) |
| S | Strength (0.0-1.0) |

**Effect:** If a path goes through the well, `(1 - Phi)` becomes small (e.g.
0.2). This makes the edge "cheap" in terms of optical-path length, so the
solver routes through the well.

> **Naming history.** Earlier drafts (pre-v1.0.0a1) called this a "Gravity
> Well". That name was misleading because the Gaussian multiplicative-Φ
> model does not match any gravitational potential (real potentials are
> additive, not multiplicative; gravity does not lower a refractive index;
> Fermat is the correct analogue). The field is now called an **Attractor**
> and the schema string is **`"attractor"`**.

### 2.2 Repulsor (refractive-index barrier)

An inverse-square function that **raises** `n_eff` near its centre, so the
optical-path length of any edge through the region grows without bound and
the solver routes around it.

    Phi_rep(p) = -S_strength / dist_sq

**Effect:** As distance approaches 0, `(1 - Phi)` becomes large (Phi is
negative). The solver will go to extreme lengths to avoid this region. This
is the optical-path analogue of a region of very high refractive index.

### 2.3 Implementation Reference

```python
# From src/klein/sim/physics.py - FieldManager.compute_phi()

if field_type == "attractor":
    # Gaussian refractive-index well: Phi = S * exp(-dist_sq / R_sq)
    phi_contribution = strength * math.exp(-dist_sq / (radius ** 2))

elif field_type == "repulsor":
    # Inverse-square refractive-index barrier: Phi = -S / dist_sq
    phi_contribution = -strength / max(dist_sq, 1e-6)

# Final clamping: n_eff stays strictly positive (A* admissibility)
clamped_phi = min(total_phi, PHI_MAX)  # 0.95 max
```

---

## 3. The Solver Algorithm

This is the step-by-step logic the engine executes when a plan is requested.

### Phase 1: The Potential Map (A* Flood Fill)

1. **Initialize:** Set cost of Source Node to 0. All others to infinity.
2. **Open Set:** Create a priority queue (min-heap by f-score).
3. **Expand:** Pop lowest f-score node. For each neighbour:
   - Query FieldManager for local Phi (apply clamping)
   - Compute tentative_cost = g[current] + edge_cost (= L * n_eff)
   - If better than recorded, update and add to open set

### Phase 2: The Geodesic Trace (Backtracking)

1. **Start:** Begin at the Sink Node.
2. **Loop:** Follow the came_from chain back to Source.
3. **Trace:** Record the path as a sequence of node IDs.

### Phase 3: Logic Validation (Parity Check)

> Note: Not implemented in v1.0. Future versions will support gate insertion.

1. **Input State:** User defines Source as TRUE.
2. **Output Constraint:** User defines Sink as FALSE (Requires Inversion).
3. **Path Trace:** Simulate a test particle along the path.
4. **If Mismatch:** Insert Shape_Tetra (NOT Gate) at lowest-cost segment.

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

## 4. Random Walk on the Impedance Graph (Doyle-Snell Conductance Form)

When stochastic reachability is needed instead of a single optimal path, we
switch from A* (the deterministic Fermat solver) to a **reversible Markov
chain** on the same weighted graph.

Each directed edge `(i → j)` is treated as a **resistor** with conductance

    c_ij = 1 / edge_cost(i → j)

The transition probability out of node `i` is the standard **Doyle-Snell
conductance form** for a random walk on a resistor network:

    P(i → j) = c_ij / SUM_k c_ik

i.e. the conductance of the chosen edge divided by the total conductance
leaving the node.

This is a textbook reversible Markov chain on the impedance graph
(Doyle & Snell, *Random Walks and Electric Networks*).

> **What it is not.** This is **not** quantum-mechanical wave mechanics.
> There are no complex amplitudes and no interference. Earlier drafts used
> the phrase "wave mechanics (stochastic mode)"; that phrasing has been
> retired in v1.0.0a1. The class is still named `WaveSolver` only for API
> stability; semantically it is a Doyle-Snell random walk solver on a
> resistor network.

### 4.1 The Probability Matrix

At a fork node with exits A and B, probability splits in proportion to
edge conductance (i.e. in inverse proportion to edge optical-path cost):

    P(A) = c_A / (c_A + c_B)
         = (1/S(A)) / ((1/S(A)) + (1/S(B)))

**Example:**
- Path A through an attractor: cost = 2 Gm  → conductance 0.5
- Path B through empty space: cost = 10 Gm → conductance 0.1
- P(A) = 0.5 / (0.5 + 0.1) = **83.3%**

### 4.2 Future Extension (flagged for review)

The solver TODO in `src/klein/sim/physics.py` notes an optional temperature
knob of the form `P(i → j) ∝ (1 / cost)^beta`. With `beta = 1` (current
behaviour) this is exactly the Doyle-Snell form above. Any real `beta > 0`
is still a valid conductance on a transformed edge weight, so the
random-walk interpretation survives. Not implemented; tracked as a TODO.

### 4.3 Implementation Reference

```python
# From src/klein/sim/physics.py - WaveSolver.compute_transition_probabilities()

def compute_transition_probabilities(self, node):
    conductances = {}
    for neighbor in successors:
        cost = compute_edge_cost(edge_data, self._field_manager)
        conductances[neighbor] = 1.0 / max(cost, EPSILON)  # c_j = 1 / cost

    total = sum(conductances.values())                      # SUM_k c_k
    return {n: c / total for n, c in conductances.items()}  # c_j / SUM_k c_k
```

---

## 5. Hardware Translation Formulas

How do these abstract numbers map to physical reality? They don't, by
themselves: KCP makes no claim that the planning prior matches any specific
substrate. The mappings below are *suggested* translations for backends
that wish to adopt them; the protocol does not require any of them.

### 5.1 Tier 1: EWOD (Digital Microfluidics)

For electrostatic systems like OpenDrop, the abstract refractive-index
modulator can be mapped to the **Lippmann-Young equation**.

#### Refractive-index modulator (Phi) → Voltage (V)

In the simulator, an attractor is a region of *low* effective refractive
index. On the hardware, activating an electrode reduces the surface tension
of the droplet, creating a physical low-energy state, which suggests the
following backend-suggested mapping:

    V_applied = V_max * sqrt(Phi_local)

| Phi_local | V_applied (at V_max=300V) | Notes |
|-----------|---------------------------|-------|
| 0.80 | 268V (89%) | Strong pull |
| 0.50 | 212V (71%) | Moderate pull |
| 0.95 | 292V (97%) | Maximum (clamped) |

**Translation:** If the solver places an attractor of strength Phi = 0.8 at
a node to pull a droplet, the driver may actuate that electrode at
sqrt(0.8) = 89% of V_max.

**Clamping:** Since Phi is clamped to 0.95 (§1), the suggested mapping never
exceeds the dielectric breakdown voltage (V_max).

#### Optical-path cost (S) → Duration (t)

The optical-path cost of an edge can be mapped to actuation duration. A
"more refractive" edge (higher impedance, higher n_eff) requires more time
for the droplet to successfully traverse it:

    Duration_ms = S_edge * k_viscosity

| Parameter | Description | Typical Value |
|-----------|-------------|---------------|
| S_edge | Optical-path cost of the edge (Gm) | - |
| k_viscosity | Hardware constant | 10 ms/Gm |

**Effect:** If the droplet moves across a "dirty" electrode (Z = 2.0), the
optical-path cost S doubles. The compiler may translate this into a
duration_ms of 20 ms instead of 10 ms.

### 5.2 Tier 2: FPGA (Time Delay)

On a chip, "distance" can be "time":

    Delay_ns = S_edge * k_clock

A compiler may insert buffer gates (NOPs) so the signal arrives exactly
when the logic dictates.

### 5.3 Tier 3: 3D Print (Slope)

In a gravity-fed marble logic system, the geometric realization of the
refractive-index modulator becomes a tilt angle:

    theta_tilt = arccos( 1 / (1 + Phi_attr) )

| Phi_attr | theta_tilt | Effect |
|----------|------------|--------|
| 0.0 | 0 deg | Flat (slow) |
| 0.5 | 48 deg | Medium slope |
| 0.95 | 61 deg | Steep (fast) |

- **High Phi_attr** = steep slope (fast traversal)
- **Repulsor**     = uphill slope (slow / impossible)

---

## 6. Changelog

| Version | Date       | Changes |
|---------|------------|---------|
| v1.0     | 2026-01-07 | Initial release: scalar impedance, A* solver, Gaussian / inverse-square fields. |
| v1.0.0a1 | 2026-05-19 | **Vocabulary reframe** (no numerical changes). Renamed "Principle of Least Action" → "Fermat's Principle of Least Optical Path on a discrete graph". Renamed "Discrete Action" → "Discrete Fermat / Optical Path". Renamed `FieldType.GRAVITY = "gravity"` → `FieldType.ATTRACTOR = "attractor"` (breaking schema string change; no deprecation alias in alpha). Renamed `compute_action` → `compute_path_cost`. Renamed "wave mechanics (stochastic mode)" → "Natural reversible random walk on the impedance graph (Doyle-Snell conductance form)". `WaveSolver` class name kept for API stability. All Gaussian / inverse-square / `(1 − Φ)` / EPSILON / PHI_MAX values and the A* heuristic are unchanged. |
| v2.0     | TBD        | Planned: metric tensors (g_ij), Hamiltonian coverage mode. |
