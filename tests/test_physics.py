#!/usr/bin/env python3
"""
Physics Engine Test Suite

Tests the GeodesicSolver, FieldManager, and WaveSolver with real pathfinding.
"""

import sys

import numpy as np
from klein.sim.physics import (
    GeodesicSolver, FieldManager, WaveSolver,
    build_graph, compute_edge_cost, EPSILON, PHI_MAX,
    PathResult, FieldType
)
from klein.common.models import KleinProject, KleinNode, KleinEdge, KleinField


def test_basic_pathfinding():
    """Test basic A* pathfinding without fields."""
    print("Test 1: Basic pathfinding A -> E")
    
    # Create a simple test graph: 5 nodes in a line with one shortcut
    # A --1-- B --1-- C --1-- D --1-- E
    #          \____5____/
    #         (high impedance shortcut)
    
    project = KleinProject(
        meta={"version": "1.0", "target_substrate": "test"},
        nodes=[
            KleinNode(id="A", type="source", pos=[0, 0, 0]),
            KleinNode(id="B", type="relay", pos=[1, 0, 0]),
            KleinNode(id="C", type="relay", pos=[2, 0, 0]),
            KleinNode(id="D", type="relay", pos=[3, 0, 0]),
            KleinNode(id="E", type="sink", pos=[4, 0, 0]),
        ],
        edges=[
            KleinEdge(**{"from": "A", "to": "B", "type": "rail", "impedance": 1.0}),
            KleinEdge(**{"from": "B", "to": "C", "type": "rail", "impedance": 1.0}),
            KleinEdge(**{"from": "C", "to": "D", "type": "rail", "impedance": 1.0}),
            KleinEdge(**{"from": "D", "to": "E", "type": "rail", "impedance": 1.0}),
            KleinEdge(**{"from": "B", "to": "D", "type": "rail", "impedance": 5.0}),
        ]
    )
    
    graph, positions = build_graph(project)
    field_manager = FieldManager()
    solver = GeodesicSolver(graph, positions, field_manager)
    
    result = solver.solve("A", "E")
    
    print(f"  Success: {result.success}")
    print(f"  Path: {' -> '.join(result.path)}")
    print(f"  Total cost: {result.total_cost:.4f} Gm")
    print(f"  Nodes explored: {result.explored_count}")
    
    assert result.success, "Path should be found"
    assert result.path == ["A", "B", "C", "D", "E"], f"Expected main path, got {result.path}"
    print("  PASSED!")


def test_impedance_routing():
    """Test that solver correctly avoids high-impedance edges."""
    print("\nTest 2: Impedance-based routing")
    
    # Create graph with high-impedance shortcut
    project = KleinProject(
        meta={"version": "1.0", "target_substrate": "test"},
        nodes=[
            KleinNode(id="A", type="source", pos=[0, 0, 0]),
            KleinNode(id="B", type="relay", pos=[1, 0, 0]),
            KleinNode(id="C", type="relay", pos=[2, 0, 0]),
            KleinNode(id="D", type="relay", pos=[3, 0, 0]),
            KleinNode(id="E", type="sink", pos=[4, 0, 0]),
        ],
        edges=[
            KleinEdge(**{"from": "A", "to": "B", "type": "rail", "impedance": 1.0}),
            KleinEdge(**{"from": "B", "to": "C", "type": "rail", "impedance": 1.0}),
            KleinEdge(**{"from": "C", "to": "D", "type": "rail", "impedance": 1.0}),
            KleinEdge(**{"from": "D", "to": "E", "type": "rail", "impedance": 1.0}),
            KleinEdge(**{"from": "B", "to": "D", "type": "rail", "impedance": 5.0}),
        ]
    )
    
    graph, positions = build_graph(project)
    field_manager = FieldManager()
    solver = GeodesicSolver(graph, positions, field_manager)
    
    # Verify the shortcut is more expensive
    # B->D direct (distance=2, impedance=5): cost = 2 * (5 + 0.001) * 1 = 10.002
    # B->C->D (distance=2, impedance=1): cost = 2 * (1 + 0.001) * 1 = 2.002
    
    result = solver.solve("B", "D")
    print(f"  Path B -> D: {' -> '.join(result.path)}")
    print(f"  Cost: {result.total_cost:.4f} Gm")
    
    assert result.path == ["B", "C", "D"], "Should take the lower-impedance path"
    print("  PASSED!")


def test_attractor():
    """Test attractor (refractive-index well) field effect on routing."""
    print("\nTest 3: Attractor field effect")

    # Create graph with an attractor (refractive-index well)
    project = KleinProject(
        meta={"version": "1.0", "target_substrate": "test"},
        nodes=[
            KleinNode(id="A", type="source", pos=[0, 0, 0]),
            KleinNode(id="B", type="relay", pos=[1, 1, 0]),   # Upper path
            KleinNode(id="C", type="relay", pos=[1, -1, 0]),  # Lower path (attractor here)
            KleinNode(id="D", type="sink", pos=[2, 0, 0]),
        ],
        edges=[
            KleinEdge(**{"from": "A", "to": "B", "type": "rail", "impedance": 1.0}),
            KleinEdge(**{"from": "A", "to": "C", "type": "rail", "impedance": 1.0}),
            KleinEdge(**{"from": "B", "to": "D", "type": "rail", "impedance": 1.0}),
            KleinEdge(**{"from": "C", "to": "D", "type": "rail", "impedance": 1.0}),
        ],
        fields=[
            KleinField(type="attractor", center=[1, -1, 0], strength=0.8, radius=1.0)
        ]
    )

    graph, positions = build_graph(project)
    field_manager = FieldManager(project.fields)
    solver = GeodesicSolver(graph, positions, field_manager)

    # Check refractive-index modulator at C
    c_pos = np.array([1.0, -1.0, 0.0])
    effect = field_manager.compute_phi(c_pos)
    print(f"  Field Phi at C: {effect.phi:.4f}")
    print(f"  Contributors: {effect.contributors}")

    result = solver.solve("A", "D")
    print(f"  Path: {' -> '.join(result.path)}")
    print(f"  Cost: {result.total_cost:.4f} Gm")

    # The attractor should lower n_eff near C and pull the optical path through C.
    assert "C" in result.path, "Should route through attractor at C"
    print("  PASSED!")


def test_repulsor():
    """Test repulsor field effect on routing."""
    print("\nTest 4: Repulsor field effect")
    
    project = KleinProject(
        meta={"version": "1.0", "target_substrate": "test"},
        nodes=[
            KleinNode(id="A", type="source", pos=[0, 0, 0]),
            KleinNode(id="B", type="relay", pos=[1, 1, 0]),  # Upper path (repulsor here)
            KleinNode(id="C", type="relay", pos=[1, -1, 0]), # Lower path
            KleinNode(id="D", type="sink", pos=[2, 0, 0]),
        ],
        edges=[
            KleinEdge(**{"from": "A", "to": "B", "type": "rail", "impedance": 1.0}),
            KleinEdge(**{"from": "A", "to": "C", "type": "rail", "impedance": 1.0}),
            KleinEdge(**{"from": "B", "to": "D", "type": "rail", "impedance": 1.0}),
            KleinEdge(**{"from": "C", "to": "D", "type": "rail", "impedance": 1.0}),
        ],
        fields=[
            KleinField(type="repulsor", center=[1, 1, 0], strength=10.0, radius=1.0)
        ]
    )
    
    graph, positions = build_graph(project)
    field_manager = FieldManager(project.fields)
    solver = GeodesicSolver(graph, positions, field_manager)
    
    # Check field effect at B
    b_pos = np.array([1.0, 1.0, 0.0])
    effect = field_manager.compute_phi(b_pos)
    print(f"  Field Phi at B (repulsor): {effect.phi:.4f}")
    
    result = solver.solve("A", "D")
    print(f"  Path: {' -> '.join(result.path)}")
    print(f"  Cost: {result.total_cost:.4f} Gm")
    
    # Repulsor should make the B path more expensive
    assert "C" in result.path, "Should avoid repulsor at B"
    print("  PASSED!")


def test_wave_solver():
    """Test reversible random walk (Doyle-Snell conductance form) solver."""
    print("\nTest 5: Random walk on impedance graph (Doyle-Snell conductances)")
    
    project = KleinProject(
        meta={"version": "1.0", "target_substrate": "test"},
        nodes=[
            KleinNode(id="A", type="source", pos=[0, 0, 0]),
            KleinNode(id="B", type="relay", pos=[1, 0, 0]),
            KleinNode(id="C", type="relay", pos=[2, 1, 0]),  # Upper fork
            KleinNode(id="D", type="relay", pos=[2, -1, 0]), # Lower fork (cheaper)
            KleinNode(id="E", type="sink", pos=[3, 0, 0]),
        ],
        edges=[
            KleinEdge(**{"from": "A", "to": "B", "type": "rail", "impedance": 1.0}),
            KleinEdge(**{"from": "B", "to": "C", "type": "rail", "impedance": 2.0}),  # More expensive
            KleinEdge(**{"from": "B", "to": "D", "type": "rail", "impedance": 0.5}),  # Cheaper
            KleinEdge(**{"from": "C", "to": "E", "type": "rail", "impedance": 1.0}),
            KleinEdge(**{"from": "D", "to": "E", "type": "rail", "impedance": 1.0}),
        ]
    )
    
    graph, positions = build_graph(project)
    field_manager = FieldManager()
    wave_solver = WaveSolver(graph, positions, field_manager)
    
    # Check transition probabilities from B
    trans_probs = wave_solver.compute_transition_probabilities("B")
    print("  Transition probabilities from B:")
    for node, prob in sorted(trans_probs.items()):
        print(f"    B -> {node}: {prob*100:.1f}%")
    
    # D should have higher probability (lower impedance)
    assert trans_probs.get("D", 0) > trans_probs.get("C", 0), "D should be more probable"
    
    # Test sampling
    rng = np.random.default_rng(42)
    paths_to_d = 0
    n_samples = 100
    for _ in range(n_samples):
        path, reached = wave_solver.sample_path("A", "E", rng)
        if "D" in path:
            paths_to_d += 1
    
    print(f"  Sampled {n_samples} paths: {paths_to_d}% went through D")
    assert paths_to_d > 50, "Majority should go through cheaper D"
    print("  PASSED!")


def test_potential_map():
    """Test potential map (flood fill) computation."""
    print("\nTest 6: Potential map from source")
    
    project = KleinProject(
        meta={"version": "1.0", "target_substrate": "test"},
        nodes=[
            KleinNode(id="A", type="source", pos=[0, 0, 0]),
            KleinNode(id="B", type="relay", pos=[1, 0, 0]),
            KleinNode(id="C", type="relay", pos=[2, 0, 0]),
        ],
        edges=[
            KleinEdge(**{"from": "A", "to": "B", "type": "rail", "impedance": 1.0}),
            KleinEdge(**{"from": "B", "to": "C", "type": "rail", "impedance": 2.0}),
        ]
    )
    
    graph, positions = build_graph(project)
    field_manager = FieldManager()
    solver = GeodesicSolver(graph, positions, field_manager)
    
    potential_map = solver.compute_potential_map("A")
    print("  Costs from A:")
    for node, cost in sorted(potential_map.items()):
        print(f"    {node}: {cost:.4f} Gm")
    
    assert potential_map["A"] == 0.0, "Source should have zero cost"
    assert potential_map["B"] < potential_map["C"], "C should be more expensive than B"
    print("  PASSED!")


def test_no_path():
    """Test handling of unreachable nodes."""
    print("\nTest 7: Unreachable node handling")
    
    project = KleinProject(
        meta={"version": "1.0", "target_substrate": "test"},
        nodes=[
            KleinNode(id="A", type="source", pos=[0, 0, 0]),
            KleinNode(id="B", type="sink", pos=[1, 0, 0]),  # No edge to B
        ],
        edges=[]
    )
    
    graph, positions = build_graph(project)
    field_manager = FieldManager()
    solver = GeodesicSolver(graph, positions, field_manager)
    
    result = solver.solve("A", "B")
    print(f"  Success: {result.success}")
    print(f"  Path: {result.path}")
    
    assert not result.success, "Should fail for unreachable node"
    assert result.path == [], "Path should be empty"
    print("  PASSED!")


def test_phi_clamping():
    """Test that Phi is correctly clamped to PHI_MAX."""
    print("\nTest 8: Phi clamping to 0.95")

    # Create a very strong refractive-index attractor well
    field_manager = FieldManager([
        KleinField(type="attractor", center=[0, 0, 0], strength=10.0, radius=1.0)
    ])

    effect = field_manager.compute_phi(np.array([0.0, 0.0, 0.0]))
    print(f"  Phi at center of strong well: {effect.phi:.4f}")
    print(f"  PHI_MAX constant: {PHI_MAX}")

    assert effect.phi <= PHI_MAX, f"Phi should be clamped to {PHI_MAX}"
    assert effect.phi == PHI_MAX, "Strong attractor well should hit the cap"
    print("  PASSED!")


def main():
    print("=" * 50)
    print("Klein Physics Engine Test Suite")
    print("=" * 50)
    print()
    
    project, graph, positions = test_basic_pathfinding()
    test_impedance_routing(project, graph, positions)
    test_attractor()
    test_repulsor()
    test_wave_solver()
    test_potential_map()
    test_no_path()
    test_phi_clamping()
    
    print()
    print("=" * 50)
    print("All Physics Engine Tests PASSED!")
    print("=" * 50)
    return 0


if __name__ == "__main__":
    sys.exit(main())
