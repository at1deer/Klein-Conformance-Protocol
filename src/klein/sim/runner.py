"""
Klein Simulator CLI (klein-sim)

Reference simulator that validates .klein packages and produces HAIL-compliant
JSONL event streams (Hardware Audit & Integrity Log).

Usage:
    python -m klein.sim.runner <project.klein> --source <node> --sink <node> [options]

Logic:
    Load .klein → Build Graph → Run A* → Output JSONL

Requirements:
    - Must emit RUNTIME_STATE_SNAPSHOT on startup
    - Output follows klein.canon.jsonl.v1 canonicalization
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

from klein.common.models import (
    KleinProject,
    StateImageBundle,
    Timebase,
)
from klein.common.hashing import canonical_json_sha256_ref
from klein.sim.physics import (
    build_graph,
    FieldManager,
    GeodesicSolver,
)
from klein.hail.canonical import dump_canonical


# =============================================================================
# Constants
# =============================================================================

SOLVER_VERSION = "klein-sim/1.0.0"
DEFAULT_TIMEBASE: Timebase = "DEVICE_TICKS"


# =============================================================================
# Canonical JSONL Serialization (klein.canon.jsonl.v1)
# =============================================================================

def emit_event(event: dict[str, Any], output: TextIO = sys.stdout) -> None:
    """Emit a single HAIL event as canonical JSONL."""
    line = dump_canonical(event)
    output.write(line + "\n")
    output.flush()


# =============================================================================
# Hash Utilities
# =============================================================================

def compute_hash(data: Any) -> str:
    """Compute evidence-bound SHA-256 ref over JCS canonical JSON bytes."""
    return canonical_json_sha256_ref(data)


def compute_rimgb_hash(
    project: KleinProject,
    simgb: StateImageBundle | None,
    timestamp_ms: int,
) -> str:
    """
    Compute Runtime Image Bundle (RImgB) hash.
    
    RImgB captures time-varying environment state at runtime.
    Formerly known as RSB (Runtime State Bundle).
    """
    rimgb_data = {
        "project_nodes": len(project.nodes),
        "project_edges": len(project.edges),
        "fields_count": len(project.fields) if project.fields else 0,
        "simgb_device_id": simgb.device_id if simgb else None,
        "timestamp_ms": timestamp_ms,
    }
    return compute_hash(rimgb_data)


# =============================================================================
# ECRP (Error Correction & Recovery Protocol) Support
# =============================================================================

@dataclass
class ECRPConfig:
    """
    Configuration for Error Correction & Recovery Protocol.
    
    ECRP attempts MUST be deterministic and bounded by max_attempts
    in HARD/ENVELOPE modes (per spec Section 4).
    """
    enabled: bool = False
    max_attempts: int = 3
    strategies: list[str] = field(default_factory=lambda: [
        "NUDGE_PULSE",      # Brief high-voltage pulse to unstick
        "VOLTAGE_BOOST",    # Increase voltage temporarily
        "FREQUENCY_SWEEP",  # Sweep AC frequency
    ])


@dataclass
class ECRPState:
    """Tracks ECRP attempts during a run."""
    total_attempts: int = 0
    current_strategy_idx: int = 0
    last_attempt_tick: int = 0
    outcomes: list[str] = field(default_factory=list)


def build_ecrp_attempt(
    t: int,
    run_id: str,
    attempt_index: int,
    strategy: str,
    outcome: str,
    deltas: dict[str, Any],
    parameters: dict[str, Any],
    timebase: Timebase = DEFAULT_TIMEBASE,
) -> dict[str, Any]:
    """
    Build an ECRP_ATTEMPT event per conformance spec.
    
    ECRP_ATTEMPT (formerly LCP_ATTEMPT) records correction attempt evidence
    with attempt_index, parameters, and outcome.
    """
    return {
        "kind": "ECRP_ATTEMPT",
        "t": t,
        "timebase": timebase,
        "run_id": run_id,
        "attempt_index": attempt_index,
        "strategy": strategy,
        "outcome": outcome,
        "deltas": deltas,
        "parameters": parameters,
    }


def attempt_ecrp_recovery(
    config: ECRPConfig,
    state: ECRPState,
    t: int,
    run_id: str,
    fault_description: str,
    output: TextIO = sys.stdout,
) -> tuple[bool, str | None]:
    """
    Attempt ECRP recovery within max_attempts bound.
    
    Per spec Section 4:
    - Each attempt MUST emit ECRP_ATTEMPT with attempt_index and outcome
    - If recovery fails in HARD/ENVELOPE: STOP + NONCONFORMANT
    
    Args:
        config: ECRP configuration
        state: Current ECRP state
        t: Current tick
        run_id: Run identifier
        fault_description: Description of the fault being corrected
        output: Output stream for events
        
    Returns:
        (success, error_code) - If success=False, error_code explains why
    """
    if not config.enabled:
        return False, None
    
    # Check if we've exceeded max_attempts
    if state.total_attempts >= config.max_attempts:
        # Emit bounded ECRP failure evidence.
        error_event = {
            "kind": "DEVICE_EVENT",
            "t": t,
            "timebase": "DEVICE_TICKS",
            "run_id": run_id,
            "level": "ERROR",
            "code": "ECRP_BOUNDS_EXCEEDED",
            "message": f"ECRP exceeded max_attempts={config.max_attempts}; aborting strict run",
        }
        emit_event(error_event, output)
        return False, "ECRP_BOUNDS_EXCEEDED"
    
    # Attempt recovery with current strategy
    state.total_attempts += 1
    strategy = config.strategies[state.current_strategy_idx % len(config.strategies)]
    
    # Build parameters based on strategy
    parameters: dict[str, Any] = {"strategy": strategy}
    if strategy == "NUDGE_PULSE":
        parameters["pulse_ms"] = 50 + (state.total_attempts * 25)
        parameters["voltage_v"] = 120
    elif strategy == "VOLTAGE_BOOST":
        parameters["boost_percent"] = 10 + (state.total_attempts * 5)
    elif strategy == "FREQUENCY_SWEEP":
        parameters["sweep_range_hz"] = [100, 1000]
    
    # Determine outcome (simulated - real implementation checks sensor feedback)
    # For simulation, first attempt usually fails, later attempts may succeed
    if state.total_attempts < config.max_attempts:
        outcome = "NO_CHANGE"
        deltas = {"occupancy_shift_cells": 0}
    else:
        # Last attempt - simulate partial recovery for test compatibility
        outcome = "PARTIAL"
        deltas = {"occupancy_shift_cells": 1}
    
    # Emit ECRP_ATTEMPT event (REQUIRED per spec)
    attempt_event = build_ecrp_attempt(
        t=t,
        run_id=run_id,
        attempt_index=state.total_attempts,
        strategy=strategy,
        outcome=outcome,
        deltas=deltas,
        parameters=parameters,
    )
    emit_event(attempt_event, output)
    
    # Track outcome
    state.outcomes.append(outcome)
    state.last_attempt_tick = t
    
    # Cycle to next strategy for next attempt
    state.current_strategy_idx += 1
    
    return outcome == "RECOVERED", None


# =============================================================================
# HAIL Event Builders (Hardware Audit & Integrity Log)
# =============================================================================

def build_runtime_state_snapshot(
    t: int,
    run_id: str,
    rimgb_hash: str,
    timebase: Timebase = DEFAULT_TIMEBASE,
    state_fields: dict[str, Any] | None = None,
    validity_start: int = 0,
    validity_end: int | None = None,
) -> dict[str, Any]:
    """Build a RUNTIME_STATE_SNAPSHOT event."""
    return {
        "kind": "RUNTIME_STATE_SNAPSHOT",
        "t": t,
        "timebase": timebase,
        "run_id": run_id,
        "rimgb_hash": rimgb_hash,
        "state_fields": state_fields or {},
        "validity_window": {
            "start_t": validity_start,
            "end_t": validity_end if validity_end is not None else t,
        },
    }


def build_device_event(
    t: int,
    run_id: str,
    code: str,
    timebase: Timebase = DEFAULT_TIMEBASE,
    detail: dict[str, Any] | None = None,
    level: str = "INFO",
    message: str | None = None,
) -> dict[str, Any]:
    """Build a DEVICE_EVENT."""
    event = {
        "kind": "DEVICE_EVENT",
        "t": t,
        "timebase": timebase,
        "run_id": run_id,
        "code": code,
        "level": level,
        "message": message or code,
    }
    if detail:
        event["detail"] = detail
    return event


def build_measurement(
    t: int,
    run_id: str,
    detector_id: str,
    measurement_id: str,
    value_type: str,
    value_data: Any,
    timebase: Timebase = DEFAULT_TIMEBASE,
    op_id: str | None = None,
) -> dict[str, Any]:
    """Build a MEASUREMENT event."""
    event = {
        "kind": "MEASUREMENT",
        "t": t,
        "timebase": timebase,
        "run_id": run_id,
        "detector_id": detector_id,
        "measurement_id": measurement_id,
        "value": {
            "type": value_type,
            "data": value_data,
        },
    }
    if op_id:
        event["op_id"] = op_id
    return event


def build_replan_decision(
    t: int,
    run_id: str,
    checkpoint_id: str,
    reason: str,
    seed: int,
    simgb_hash: str,
    rimgb_hash: str,
    timebase: Timebase = DEFAULT_TIMEBASE,
    solver_mode: str = "GEODESIC",
    observables_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a REPLAN_DECISION event."""
    return {
        "kind": "REPLAN_DECISION",
        "t": t,
        "timebase": timebase,
        "run_id": run_id,
        "checkpoint_id": checkpoint_id,
        "reason": reason,
        "solver_version": SOLVER_VERSION,
        "solver_mode": solver_mode,
        "seed": seed,
        "inputs_ref": {
            "simgb_hash": simgb_hash,
            "rimgb_hash": rimgb_hash,
            "observables_snapshot": observables_snapshot or {},
        },
    }


# =============================================================================
# Simulation Runner
# =============================================================================

class SimulationRunner:
    """
    Klein Reference Simulator.
    
    Executes .klein projects and produces HAIL-compliant event streams.
    """
    
    def __init__(
        self,
        project: KleinProject,
        simgb: StateImageBundle | None = None,
        seed: int | None = None,
        output: TextIO = sys.stdout,
        ecrp_config: ECRPConfig | None = None,
        run_id: str | None = None,
        start_time_ms: int | None = None,
    ):
        self.project = project
        self.simgb = simgb
        self.seed = seed if seed is not None else int(time.time() * 1000) % (2**31)
        self.output = output
        
        self.run_id = run_id or str(uuid.uuid4())
        self.tick = 0
        self.start_time_ms = start_time_ms if start_time_ms is not None else int(time.time() * 1000)
        
        # Compute hashes
        self.simgb_hash = compute_hash(simgb.model_dump()) if simgb else "null"
        self.rimgb_hash = compute_rimgb_hash(project, simgb, self.start_time_ms)
        
        # Build graph
        self.graph, self.positions = build_graph(project)
        self.field_manager = FieldManager(project.fields)
        self.solver = GeodesicSolver(self.graph, self.positions, self.field_manager)
        
        # Trace tracking
        self.trace_ops: list[dict[str, Any]] = []
        self.trace_start_tick = 0
        
        # ECRP (Error Correction & Recovery Protocol) support
        self.ecrp_config = ecrp_config or ECRPConfig()
        self.ecrp_state = ECRPState()
    
    def emit(self, event: dict[str, Any]) -> None:
        """Emit a HAIL event."""
        emit_event(event, self.output)
    
    def emit_startup(self) -> None:
        """Emit RUNTIME_STATE_SNAPSHOT on startup (required)."""
        state_fields = {
            "solver_version": SOLVER_VERSION,
            "project_version": self.project.meta.version,
            "target_substrate": self.project.meta.target_substrate,
            "node_count": len(self.project.nodes),
            "edge_count": len(self.project.edges),
            "field_count": len(self.project.fields) if self.project.fields else 0,
            "seed": self.seed,
        }
        
        event = build_runtime_state_snapshot(
            t=self.tick,
            run_id=self.run_id,
            rimgb_hash=self.rimgb_hash,
            state_fields=state_fields,
            validity_start=0,
        )
        self.emit(event)
        
        # Also emit INIT device event
        init_event = build_device_event(
            t=self.tick,
            run_id=self.run_id,
            code="INIT",
            message="Run initialized",
            detail={
                "simgb_hash": self.simgb_hash,
                "rimgb_hash": self.rimgb_hash,
            },
        )
        self.emit(init_event)
    
    def attempt_ecrp(self, fault_description: str) -> tuple[bool, str | None]:
        """
        Attempt ECRP recovery for a fault.
        
        Wrapper around attempt_ecrp_recovery that uses instance state.
        
        Args:
            fault_description: Description of the fault
            
        Returns:
            (success, error_code) - error_code is set if max_attempts exceeded
        """
        return attempt_ecrp_recovery(
            config=self.ecrp_config,
            state=self.ecrp_state,
            t=self.tick,
            run_id=self.run_id,
            fault_description=fault_description,
            output=self.output,
        )
    
    def run_geodesic(self, source: str, sink: str) -> bool:
        """
        Execute geodesic pathfinding from source to sink.
        
        If pathfinding fails and ECRP is enabled, attempts recovery
        within max_attempts bound.
        
        Args:
            source: Source node ID
            sink: Sink node ID
            
        Returns:
            True if path found, False otherwise
        """
        self.tick += 1
        
        # Emit REPLAN_DECISION at start of solve
        checkpoint_id = f"solve_{self.tick}"
        replan_event = build_replan_decision(
            t=self.tick,
            run_id=self.run_id,
            checkpoint_id=checkpoint_id,
            reason="geodesic_solve",
            seed=self.seed,
            simgb_hash=self.simgb_hash,
            rimgb_hash=self.rimgb_hash,
            solver_mode="GEODESIC",
        )
        self.emit(replan_event)
        
        # Run the solver
        result = self.solver.solve(source, sink)
        
        self.tick += 1
        
        if result.success:
            # Emit path measurement
            path_event = build_measurement(
                t=self.tick,
                run_id=self.run_id,
                detector_id="geodesic_solver",
                measurement_id=f"path_{checkpoint_id}",
                value_type="F64",
                value_data=result.total_cost,
                op_id=checkpoint_id,
            )
            self.emit(path_event)
            
            # Emit success device event with path details
            success_event = build_device_event(
                t=self.tick,
                run_id=self.run_id,
                code="PATH_FOUND",
                message="Path found",
                detail={
                    "path": result.path,
                    "cost_gm": result.total_cost,
                    "edge_count": result.edge_count,
                    "explored_count": result.explored_count,
                },
            )
            self.emit(success_event)
            
            # Record trace operation for path
            self._record_path_trace(checkpoint_id, result.path)
            
        else:
            # Emit failure device event
            fail_event = build_device_event(
                t=self.tick,
                run_id=self.run_id,
                code="PATH_NOT_FOUND",
                level="ERROR",
                message="Path not found",
                detail={
                    "source": source,
                    "sink": sink,
                    "explored_count": result.explored_count,
                },
            )
            self.emit(fail_event)
            
            # Attempt ECRP recovery if enabled
            if self.ecrp_config.enabled:
                self.tick += 1
                recovered, error_code = self.attempt_ecrp(
                    f"PATH_NOT_FOUND: {source} -> {sink}"
                )
                if error_code:
                    # ECRP bounds exceeded - emit and fail
                    return False
                # Note: In a full implementation, we would re-solve after
                # successful recovery. For now, we just record the attempt.
        
        return result.success
    
    def run_ticks(self, num_ticks: int) -> None:
        """
        Advance simulation by a number of ticks.
        
        Emits periodic state snapshots.
        """
        for _ in range(num_ticks):
            self.tick += 1
            
            # Emit periodic state snapshot every 10 ticks
            if self.tick % 10 == 0:
                snapshot = build_runtime_state_snapshot(
                    t=self.tick,
                    run_id=self.run_id,
                    rimgb_hash=self.rimgb_hash,
                    validity_start=self.tick - 10,
                    validity_end=self.tick,
                )
                self.emit(snapshot)
    
    def _record_path_trace(self, op_id: str, path: list[str]) -> None:
        """
        Record trace operation for a solved path.
        
        Maps logical path to physical actuation references.
        """
        actuation_refs = []
        tick_offset = 0
        ticks_per_edge = 10  # Simulated tick duration per edge
        
        for i, node_id in enumerate(path):
            # Map node to hypothetical channel ID
            channel_id = hash(node_id) % 128
            
            actuation_refs.append({
                "channel_id": channel_id,
                "tick_range": {
                    "start": self.tick + tick_offset,
                    "end": self.tick + tick_offset + ticks_per_edge,
                },
                "kind": "ACTUATION",
            })
            tick_offset += ticks_per_edge
        
        self.trace_ops.append({
            "op_id": op_id,
            "actuation_refs": actuation_refs,
        })
    
    def export_trace(self) -> dict[str, Any]:
        """
        Export execution trace per trace.schema.json.
        
        Returns:
            Trace artifact suitable for serialization.
        """
        return {
            "trace_version": "1.0",
            "tick_range": {
                "start": self.trace_start_tick,
                "end": self.tick,
            },
            "plans": [
                {
                    "plan_id": f"plan_{self.run_id[:8]}",
                    "ops": self.trace_ops,
                }
            ],
        }
    
    def finalize(self) -> None:
        """Emit final state and shutdown events."""
        self.tick += 1
        
        # Final state snapshot
        final_snapshot = build_runtime_state_snapshot(
            t=self.tick,
            run_id=self.run_id,
            rimgb_hash=self.rimgb_hash,
            state_fields={"status": "completed"},
            validity_start=0,
            validity_end=self.tick,
        )
        self.emit(final_snapshot)
        
        # Shutdown event
        shutdown_event = build_device_event(
            t=self.tick,
            run_id=self.run_id,
            code="SHUTDOWN",
            message="Run completed",
            detail={"final_tick": self.tick},
        )
        self.emit(shutdown_event)


# =============================================================================
# File Loaders
# =============================================================================

def load_project(path: Path) -> KleinProject:
    """Load a .klein project file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return KleinProject.model_validate(data)


def load_simgb(path: Path) -> StateImageBundle:
    """Load a State Image Bundle (SImgB) file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return StateImageBundle.model_validate(data)


# =============================================================================
# CLI
# =============================================================================

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="klein-sim",
        description="Klein Reference Simulator - Geodesic pathfinding for programmable matter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m klein.sim.runner project.klein --source A --sink Z
  python -m klein.sim.runner project.klein --source A --sink Z --simgb device.json
  python -m klein.sim.runner project.klein --source A --sink Z --ticks 50 --seed 42
        """,
    )
    
    parser.add_argument(
        "project",
        type=Path,
        help="Path to .klein project file",
    )
    
    parser.add_argument(
        "--source", "-s",
        type=str,
        required=True,
        help="Source node ID",
    )
    
    parser.add_argument(
        "--sink", "-t",
        type=str,
        required=True,
        help="Sink (target) node ID",
    )
    
    parser.add_argument(
        "--simgb",
        type=Path,
        default=None,
        help="Path to State Image Bundle (SImgB) JSON file",
    )
    
    parser.add_argument(
        "--ticks",
        type=int,
        default=0,
        help="Additional ticks to simulate after pathfinding (default: 0)",
    )
    
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for deterministic execution",
    )
    
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="Output file for JSONL (default: stdout)",
    )
    
    parser.add_argument(
        "--trace",
        type=Path,
        default=None,
        help="Output file for execution trace (JSON)",
    )
    
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress stderr status messages",
    )
    
    parser.add_argument(
        "--ecrp",
        action="store_true",
        help="Enable ECRP (Error Correction & Recovery Protocol)",
    )
    
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=3,
        help="Maximum ECRP attempts before ECRP_BOUNDS_EXCEEDED (default: 3)",
    )
    
    parser.add_argument(
        "--version", "-V",
        action="version",
        version=f"%(prog)s {SOLVER_VERSION}",
    )
    
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    args = parse_args(argv)
    
    # Status output helper
    def status(msg: str) -> None:
        if not args.quiet:
            print(msg, file=sys.stderr)
    
    # Load project
    status(f"Loading project: {args.project}")
    try:
        project = load_project(args.project)
    except FileNotFoundError:
        print(f"Error: Project file not found: {args.project}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error loading project: {e}", file=sys.stderr)
        return 1
    
    # Load SImgB if provided
    simgb = None
    if args.simgb:
        status(f"Loading SImgB: {args.simgb}")
        try:
            simgb = load_simgb(args.simgb)
        except FileNotFoundError:
            print(f"Error: SImgB file not found: {args.simgb}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error loading SImgB: {e}", file=sys.stderr)
            return 1
    
    # Validate source/sink exist
    node_ids = {n.id for n in project.nodes}
    if args.source not in node_ids:
        print(f"Error: Source node '{args.source}' not found in project", file=sys.stderr)
        print(f"Available nodes: {sorted(node_ids)}", file=sys.stderr)
        return 1
    if args.sink not in node_ids:
        print(f"Error: Sink node '{args.sink}' not found in project", file=sys.stderr)
        print(f"Available nodes: {sorted(node_ids)}", file=sys.stderr)
        return 1
    
    # Setup output
    output: TextIO
    output_path = args.output
    if output_path:
        output = open(output_path, "w", encoding="utf-8")
    else:
        output = sys.stdout
    
    try:
        # Create ECRP config if enabled
        ecrp_config = None
        if args.ecrp:
            ecrp_config = ECRPConfig(
                enabled=True,
                max_attempts=args.max_attempts,
            )
            status(f"ECRP enabled (max_attempts={args.max_attempts})")
        
        # Create and run simulator
        status(f"Initializing simulator (seed={args.seed})")
        runner = SimulationRunner(
            project=project,
            simgb=simgb,
            seed=args.seed,
            output=output,
            ecrp_config=ecrp_config,
        )
        
        # Emit startup (RUNTIME_STATE_SNAPSHOT required)
        runner.emit_startup()
        
        # Run geodesic solve
        status(f"Solving: {args.source} → {args.sink}")
        success = runner.run_geodesic(args.source, args.sink)
        
        if success:
            status("Path found!")
        else:
            status("No path found.")
        
        # Run additional ticks if requested
        if args.ticks > 0:
            status(f"Running {args.ticks} additional ticks...")
            runner.run_ticks(args.ticks)
        
        # Finalize
        runner.finalize()
        status("Simulation complete.")
        
        # Write trace if requested
        if args.trace:
            trace_data = runner.export_trace()
            with open(args.trace, "w", encoding="utf-8") as f:
                json.dump(trace_data, f, indent=2)
            status(f"Trace written to: {args.trace}")
        
        return 0 if success else 2
        
    finally:
        if output_path and output != sys.stdout:
            output.close()


if __name__ == "__main__":
    sys.exit(main())
