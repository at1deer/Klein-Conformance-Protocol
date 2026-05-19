"""
Klein Simulator Package

Provides:
- Physics engine (GeodesicSolver, FieldManager, WaveSolver)
- Virtual substrate simulation (VirtualSubstrate)
- Execution engine (ExecutionEngine, PayloadParser)
- CLI runner (python -m klein.sim.runner)
"""

from klein.sim.physics import (
    GeodesicSolver,
    FieldManager,
    WaveSolver,
    PathResult,
    build_graph,
    compute_edge_cost,
    solve_geodesic,
    compute_action,
)

from klein.sim.virtual_substrate import (
    VirtualSubstrate,
    Droplet,
    DropletState,
    KleinErrorCode,
    ValidationError,
)

from klein.sim.execution_engine import (
    ExecutionEngine,
    ExecutionConfig,
    ExecutionResult,
    PayloadParser,
    PayloadKind,
    HAILEmitter,
)

__all__ = [
    # Physics
    "GeodesicSolver",
    "FieldManager", 
    "WaveSolver",
    "PathResult",
    "build_graph",
    "compute_edge_cost",
    "solve_geodesic",
    "compute_action",
    # Virtual Substrate
    "VirtualSubstrate",
    "Droplet",
    "DropletState",
    "KleinErrorCode",
    "ValidationError",
    # Execution Engine
    "ExecutionEngine",
    "ExecutionConfig",
    "ExecutionResult",
    "PayloadParser",
    "PayloadKind",
    "HAILEmitter",
]
