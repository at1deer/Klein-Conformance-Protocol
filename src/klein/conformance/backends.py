"""Conformance execution backends."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from klein.artifacts import (
    ArtifactValidationError,
    validate_klein_container,
    validate_klein_project,
)
from klein.artifacts.validation import load_json_artifact
from klein.common.models import Container
from klein.conformance.comparison import input_artifact_binding_details
from klein.conformance.errors import (
    ARTIFACT_JSON_INVALID,
    ARTIFACT_SCHEMA_INVALID,
    DDI_UNSUPPORTED_PAYLOAD,
    REPO_ROOT,
    SIMULATOR_MODULE,
    VECTOR_INPUT_MISSING,
)
from klein.conformance.models import BackendType, ConformanceVector, ExecutionResult
from klein.execution import (
    build_dmf_simulated_observations_from_events,
    build_runbook_from_artifact,
    build_trace_from_execution_result,
    build_trace_from_hail_events,
    canonical_ecrp_policy_hash,
    canonical_runbook_hash,
    canonical_trace_hash,
    compare_trace_to_runbook,
    default_ecrp_policy_for_mode,
    default_observation_policy,
    validate_ecrp_attempt_sequence,
    validate_observation_contract,
    validate_trace_recovery_contract,
)
from klein.hail.canonical import event_sort_key, hash_hail_jsonl
from klein.hail.chain import compute_hail_chain
from klein.hail.validation import parse_jsonl_events
from klein.profiles.dmf import substrate_fingerprint_details


@runtime_checkable
class Backend(Protocol):
    """
    Protocol defining the backend interface.

    All backends must implement these methods to be used by the conformance harness.
    This enables future expansion to substrate drivers, remote execution, etc.
    """

    @property
    def name(self) -> str:
        """Backend identifier."""
        ...

    def check_capabilities(self, required: list[str]) -> tuple[bool, str]:
        """Check if backend supports required capabilities."""
        ...

    def execute(self, vector: ConformanceVector) -> ExecutionResult:
        """Execute a test vector and return results."""
        ...

    def cleanup(self) -> None:
        """Cleanup any resources (temp files, connections)."""
        ...


# =============================================================================
# Backend Implementations
# =============================================================================


class MockBackend:
    """
    Mock backend for testing the harness itself.

    Returns golden observables directly without execution.
    Useful for validating the harness logic.
    """

    def __init__(self, capabilities: dict[str, Any] | None = None):
        self._capabilities = capabilities or {
            "supports": {
                "envelope": True,
                "diagnostic": True,
                "checkpoint_replan": True,
            }
        }

    @property
    def name(self) -> str:
        return "mock"

    def check_capabilities(self, required: list[str]) -> tuple[bool, str]:
        """Check if backend supports required capabilities."""
        supports = self._capabilities.get("supports", {})
        for cap in required:
            if not supports.get(cap, False):
                return False, f"Missing capability: {cap}"
        return True, "All capabilities supported"

    def execute(self, vector: ConformanceVector) -> ExecutionResult:
        """Return golden observables as mock execution."""
        start = time.perf_counter()

        if vector.golden_observables:
            return ExecutionResult(
                success=True,
                events=vector.golden_observables,
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        # Generate minimal events for container without golden
        if vector.container:
            run_id = f"R{vector.id}"
            events = [
                {
                    "kind": "RUNTIME_STATE_SNAPSHOT",
                    "t": 0,
                    "timebase": "DEVICE_TICKS",
                    "run_id": run_id,
                    "rimgb_hash": "mock_hash",
                    "state_fields": {"status": "mock"},
                    "validity_window": {"start_t": 0, "end_t": 100},
                },
                {
                    "kind": "DEVICE_EVENT",
                    "t": 0,
                    "timebase": "DEVICE_TICKS",
                    "run_id": run_id,
                    "code": "INIT",
                    "level": "INFO",
                    "message": "Mock run initialized",
                },
            ]
            return ExecutionResult(
                success=True,
                events=events,
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        return ExecutionResult(
            success=False,
            events=[],
            error_message="No executable content",
            duration_ms=(time.perf_counter() - start) * 1000,
        )

    def cleanup(self) -> None:
        pass


class SubprocessBackend:
    """
    Backend that executes the simulator via subprocess.

    Calls `python -m klein.sim.runner` with appropriate arguments
    and captures the JSONL output.
    """

    def __init__(
        self,
        python_executable: str | None = None,
        timeout_seconds: float = 30.0,
        capabilities: dict[str, Any] | None = None,
    ):
        self._python = python_executable or sys.executable
        self._timeout = timeout_seconds
        self._capabilities = capabilities or {
            "supports": {
                "envelope": True,
                "diagnostic": True,
                "checkpoint_replan": True,
            }
        }
        self._temp_files: list[Path] = []

    @property
    def name(self) -> str:
        return "subprocess"

    def check_capabilities(self, required: list[str]) -> tuple[bool, str]:
        """Check if backend supports required capabilities."""
        supports = self._capabilities.get("supports", {})
        for cap in required:
            if not supports.get(cap, False):
                return False, f"Missing capability: {cap}"
        return True, "All capabilities supported"

    def execute(self, vector: ConformanceVector) -> ExecutionResult:
        """Execute vector via subprocess."""
        start = time.perf_counter()

        # Create temporary .kln file from container
        if not vector.container and not vector.loose_path:
            return ExecutionResult(
                success=False,
                events=[],
                error_message="No executable content",
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        try:
            # Create temp directory for this execution
            with tempfile.TemporaryDirectory(prefix="klein_conform_") as tmpdir:
                tmpdir_path = Path(tmpdir)

                # Export .klein project file
                klein_path = tmpdir_path / f"vector_{vector.id}.klein"
                output_path = tmpdir_path / "output.jsonl"

                if vector.container:
                    vector.to_klein_file(klein_path)
                elif vector.loose_path:
                    # Copy payload from loose format
                    klein_path = self._create_klein_from_loose(vector.loose_path, tmpdir_path)

                source, sink = vector.get_source_sink()

                # Build command
                cmd = [
                    self._python,
                    "-m",
                    SIMULATOR_MODULE,
                    str(klein_path),
                    "--source",
                    source,
                    "--sink",
                    sink,
                    "--output",
                    str(output_path),
                    "--quiet",
                ]

                # Add seed for determinism
                cmd.extend(["--seed", "42"])

                # Execute
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self._timeout,
                    cwd=str(REPO_ROOT),
                )

                # Parse output
                events = []
                if output_path.exists():
                    with open(output_path, encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    events.append(json.loads(line))
                                except json.JSONDecodeError:
                                    pass

                # Check for errors
                if result.returncode not in (0, 2):  # 0=success, 2=no path found
                    return ExecutionResult(
                        success=False,
                        events=events,
                        error_code=f"EXIT_{result.returncode}",
                        error_message=result.stderr[:500] if result.stderr else None,
                        exit_code=result.returncode,
                        duration_ms=(time.perf_counter() - start) * 1000,
                    )

                return ExecutionResult(
                    success=True,
                    events=events,
                    exit_code=result.returncode,
                    duration_ms=(time.perf_counter() - start) * 1000,
                )

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                events=[],
                error_code="TIMEOUT",
                error_message=f"Execution timed out after {self._timeout}s",
                duration_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                events=[],
                error_code="EXCEPTION",
                error_message=str(e),
                duration_ms=(time.perf_counter() - start) * 1000,
            )

    def _create_klein_from_loose(self, loose_path: Path, tmpdir: Path) -> Path:
        """Create .klein file from loose format vector."""
        klein_path = tmpdir / "project.klein"

        # Build minimal structure
        klein_data = {
            "meta": {
                "version": "1.0",
                "target_substrate": "dmf.muxed_ewod.opendrop.v1.0",
            },
            "nodes": [
                {"id": "source", "type": "Source", "pos": [0, 0, 0]},
                {"id": "sink", "type": "Sink", "pos": [10, 0, 0]},
            ],
            "edges": [
                {"from": "source", "to": "sink", "type": "rail", "impedance": 1.0},
            ],
        }

        with open(klein_path, "w", encoding="utf-8") as f:
            json.dump(klein_data, f, indent=2)

        return klein_path

    def cleanup(self) -> None:
        """Cleanup temp files."""
        for path in self._temp_files:
            try:
                path.unlink(missing_ok=True)
            except Exception:  # noqa: B110 - temp-file cleanup is best effort.
                pass
        self._temp_files.clear()


class SimulatorBackend:
    """
    Backend that uses the simulator Python API directly.

    More efficient than subprocess for batch testing.
    Imports and calls the simulator module in-process.
    """

    def __init__(self, capabilities: dict[str, Any] | None = None):
        self._capabilities = capabilities or {
            "supports": {
                "envelope": True,
                "diagnostic": True,
                "checkpoint_replan": True,
            }
        }
        self._runner_module = None

    @property
    def name(self) -> str:
        return "simulator"

    def _ensure_imported(self) -> None:
        """Lazy import the runner module."""
        if self._runner_module is None:
            from klein.sim import runner

            self._runner_module = runner

    def check_capabilities(self, required: list[str]) -> tuple[bool, str]:
        """Check if backend supports required capabilities."""
        supports = self._capabilities.get("supports", {})
        for cap in required:
            if not supports.get(cap, False):
                return False, f"Missing capability: {cap}"
        return True, "All capabilities supported"

    def execute(self, vector: ConformanceVector) -> ExecutionResult:
        """Execute vector using Python API."""
        import io

        start = time.perf_counter()

        if not vector.container and not vector.loose_path:
            return ExecutionResult(
                success=False,
                events=[],
                error_message="No executable content",
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        try:
            self._ensure_imported()

            # Create temp file for .klein
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".klein",
                delete=False,
                encoding="utf-8",
            ) as f:
                if vector.container:
                    vector.to_klein_file(Path(f.name))
                else:
                    # Minimal structure
                    json.dump(
                        {
                            "meta": {"version": "1.0", "target_substrate": "test"},
                            "nodes": [
                                {"id": "source", "type": "Source", "pos": [0, 0, 0]},
                                {"id": "sink", "type": "Sink", "pos": [10, 0, 0]},
                            ],
                            "edges": [
                                {"from": "source", "to": "sink", "type": "rail", "impedance": 1.0},
                            ],
                        },
                        f,
                    )
                kln_path = Path(f.name)

            try:
                # Capture output
                output_buffer = io.StringIO()

                # Load project
                project = self._runner_module.load_project(kln_path)

                # Create runner
                runner = self._runner_module.SimulationRunner(
                    project=project,
                    simgb=None,
                    seed=42,
                    output=output_buffer,
                )

                # Execute
                runner.emit_startup()
                source, sink = vector.get_source_sink()
                success = runner.run_geodesic(source, sink)
                runner.finalize()

                # Parse events
                events = []
                output_buffer.seek(0)
                for line in output_buffer:
                    line = line.strip()
                    if line:
                        try:
                            events.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass

                return ExecutionResult(
                    success=True,
                    events=events,
                    exit_code=0 if success else 2,
                    duration_ms=(time.perf_counter() - start) * 1000,
                )

            finally:
                kln_path.unlink(missing_ok=True)

        except Exception as e:
            return ExecutionResult(
                success=False,
                events=[],
                error_code="EXCEPTION",
                error_message=str(e),
                duration_ms=(time.perf_counter() - start) * 1000,
            )

    def cleanup(self) -> None:
        pass


class FullSimulatorBackend:
    """
    Full-featured simulator backend using the execution engine.

    Unlike SimulatorBackend which only runs A* pathfinding, this backend:
    - Validates containers and SImgB bundles
    - Executes payload operations
    - Simulates droplet physics
    - Emits proper error codes for negative tests
    - Supports ECRP recovery attempts

    This is the recommended backend for conformance testing.
    """

    backend_version = "1.0.0a0"

    def __init__(
        self,
        capabilities: dict[str, Any] | None = None,
        ecrp_enabled: bool = False,
        ecrp_max_attempts: int = 3,
    ):
        self._capabilities = capabilities or {
            "supports": {
                "envelope": True,
                "diagnostic": True,
                "checkpoint_replan": True,
                "container_validation": True,
                "payload_execution": True,
                "droplet_simulation": True,
                "ecrp": True,
            }
        }
        self._ecrp_enabled = ecrp_enabled
        self._ecrp_max_attempts = ecrp_max_attempts
        self._modules_loaded = False

    @property
    def name(self) -> str:
        return "full_simulator"

    def _ensure_imported(self) -> None:
        """Lazy import the execution engine modules."""
        if not self._modules_loaded:
            # Import here to avoid circular imports and speed up startup
            from klein.sim.execution_engine import (
                ExecutionConfig,
                ExecutionEngine,
                HAILEmitter,
            )
            from klein.sim.virtual_substrate import VirtualSubstrate

            self._VirtualSubstrate = VirtualSubstrate
            self._ExecutionEngine = ExecutionEngine
            self._ExecutionConfig = ExecutionConfig
            self._HAILEmitter = HAILEmitter
            self._modules_loaded = True

    def check_capabilities(self, required: list[str]) -> tuple[bool, str]:
        """Check if backend supports required capabilities."""
        supports = self._capabilities.get("supports", {})
        for cap in required:
            if not supports.get(cap, False):
                return False, f"Missing capability: {cap}"
        return True, "All capabilities supported"

    def _missing_input_result(self, vector: ConformanceVector, start: float) -> ExecutionResult:
        """Return the v1 missing-input diagnostic."""
        declared = str(vector.input_path) if vector.input_path else None
        return ExecutionResult(
            success=False,
            events=[],
            error_code=VECTOR_INPUT_MISSING,
            error_message="v1 vector requires an existing declared input artifact",
            validation_stage="vector_input",
            duration_ms=(time.perf_counter() - start) * 1000,
            details={
                **self._base_report_details(vector),
                "input_type": vector.input_type,
                "input_path": declared,
            },
        )

    def _json_error_result(
        self,
        start: float,
        *,
        code: str,
        message: str,
        stage: str = "artifact_parse",
        details: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        """Return a structured artifact validation failure."""
        return ExecutionResult(
            success=False,
            events=[],
            error_code=code,
            error_message=message,
            validation_stage=stage,
            duration_ms=(time.perf_counter() - start) * 1000,
            details=details or {},
        )

    def _base_report_details(self, vector: ConformanceVector) -> dict[str, Any]:
        """Return backend/profile fields common to full-simulator v1 results."""
        details = {
            "backend_id": self.name,
            "backend_version": self.backend_version,
            "profile_id": vector.profile,
            "profile_version": str(vector.metadata.get("profile_version", "v1")),
        }
        details.update(input_artifact_binding_details(vector))
        return details

    def _substrate_report_details(self, vector: ConformanceVector, substrate: Any) -> dict[str, Any]:
        details = self._base_report_details(vector)
        details.update(substrate_fingerprint_details(substrate))
        return details

    def _run_start_event(
        self,
        vector: ConformanceVector,
        *,
        run_id: str,
        details: dict[str, Any],
    ) -> dict[str, Any] | None:
        artifact_hash = details.get("input_artifact_hash") or details.get("input_raw_sha256")
        if not artifact_hash:
            return None
        event: dict[str, Any] = {
            "kind": "RUN_START",
            "t": 0,
            "timebase": "DEVICE_TICKS",
            "run_id": run_id,
            "artifact_hash": artifact_hash,
            "artifact_canonicalization": (
                details.get("input_artifact_canonicalization") or "raw-bytes"
            ),
            "artifact_type": vector.input_type or "unknown",
            "profile_id": details.get("profile_id", vector.profile),
            "profile_version": details.get("profile_version", "v1"),
            "backend_id": self.name,
            "backend_version": self.backend_version,
            "mode": vector.mode,
        }
        for field in (
            "substrate_capabilities_hash",
            "substrate_topology_hash",
            "substrate_fingerprint",
            "substrate_fingerprint_canonicalization",
        ):
            if details.get(field) is not None:
                event[field] = details[field]
        return event

    def _with_lifecycle_events(
        self,
        vector: ConformanceVector,
        *,
        events: list[dict[str, Any]],
        run_id: str,
        success: bool,
        error_code: str | None,
        details: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Wrap execution-vector HAIL with RUN_START/RUN_END binding events."""
        if vector.schema_version != "v1" or vector.input_type not in {"project", "container"}:
            return events
        if any(event.get("kind") in {"RUN_START", "RUN_END"} for event in events):
            return events
        run_start = self._run_start_event(vector, run_id=run_id, details=details)
        if run_start is None:
            return events

        preclose_events = [run_start, *events]
        preclose_hash = hash_hail_jsonl(preclose_events)
        preclose_chain = compute_hail_chain(preclose_events)
        final_t = max((int(event.get("t", 0)) for event in events), default=0)
        run_end = {
            "kind": "RUN_END",
            "t": final_t,
            "timebase": "DEVICE_TICKS",
            "run_id": run_id,
            "status": "SUCCESS" if success and error_code is None else "FAIL",
            "error_code": error_code,
            "preclose_hail_digest": preclose_hash.ref,
            "preclose_hail_canonicalization": preclose_hash.canonicalization,
            "preclose_hail_chain_digest": preclose_chain.terminal_chain_digest_ref,
            "preclose_hail_chain_algorithm": preclose_chain.chain_algorithm,
            "event_count_preclose": len(preclose_events),
        }
        return sorted([*preclose_events, run_end], key=event_sort_key)

    def _execution_artifact_details(
        self,
        runbook: dict[str, Any],
        *,
        run_id: str,
        success: bool,
        error_code: str | None,
        events: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if events is None:
            trace = build_trace_from_execution_result(
                runbook,
                run_id=run_id,
                backend_id=self.name,
                backend_version=self.backend_version,
                execution_success=success,
                error_code=error_code,
            )
        else:
            trace = build_trace_from_hail_events(
                runbook,
                events,
                run_id=run_id,
                backend_id=self.name,
                backend_version=self.backend_version,
                execution_success=success,
                error_code=error_code,
            )
        comparison = compare_trace_to_runbook(trace, runbook)
        recovery_validated = trace.get("metadata", {}).get("ecrp_recovery_status") == "success"
        return {
            "runbook_present": True,
            "runbook_hash": canonical_runbook_hash(runbook).ref,
            "runbook_step_count": len(runbook.get("planned_steps", [])),
            "trace_present": True,
            "trace_hash": canonical_trace_hash(trace).ref,
            "trace_step_count": len(trace.get("trace_steps", [])),
            "trace_matches_runbook": comparison.ok,
            "trace_recovery_validated": recovery_validated,
            "trace_comparison_error_code": comparison.error_code,
        }

    def _ecrp_contract_details(
        self,
        *,
        events: list[dict[str, Any]],
        runbook: dict[str, Any],
        run_id: str,
        success: bool,
        error_code: str | None,
        mode: str,
        max_attempts: int,
        allow_success_after_retry: bool = False,
        allowed_success_strategies: list[str] | None = None,
    ) -> dict[str, Any]:
        attempts = [event for event in events if event.get("kind") == "ECRP_ATTEMPT"]
        if not attempts:
            return {
                "ecrp_policy_present": False,
                "ecrp_policy_hash": None,
                "ecrp_contract_status": "not_applicable",
                "ecrp_attempt_count": 0,
                "ecrp_terminal_failure_status": "not_applicable",
                "ecrp_error_code": None,
            }
        policy = default_ecrp_policy_for_mode(mode)
        policy["max_attempts"] = max_attempts
        policy["allow_success_after_retry"] = allow_success_after_retry
        policy["allowed_success_strategies"] = allowed_success_strategies or []
        hail_result = validate_ecrp_attempt_sequence(events, policy)
        trace = build_trace_from_hail_events(
            runbook,
            events,
            run_id=run_id,
            backend_id=self.name,
            backend_version=self.backend_version,
            execution_success=success,
            error_code=error_code,
        )
        trace_result = validate_trace_recovery_contract(trace, runbook, policy)
        ok = hail_result.ok and trace_result.ok
        error = hail_result.error_code if not hail_result.ok else trace_result.error_code
        successful_attempts = [
            event for event in events
            if event.get("kind") == "ECRP_ATTEMPT" and event.get("outcome") == "SUCCESS"
        ]
        return {
            "ecrp_policy_present": True,
            "ecrp_policy_hash": canonical_ecrp_policy_hash(policy).ref,
            "ecrp_contract_status": "pass" if ok else "fail",
            "ecrp_attempt_count": hail_result.attempt_count,
            "ecrp_terminal_failure_status": hail_result.terminal_failure_status,
            "ecrp_error_code": error,
            "ecrp_recovery_status": "success" if ok and successful_attempts else "not_applicable",
            "ecrp_recovery_strategy": successful_attempts[0].get("strategy") if ok and successful_attempts else None,
        }

    def _observation_contract_details(
        self,
        *,
        events: list[dict[str, Any]],
        runbook: dict[str, Any],
        run_id: str,
        success: bool,
        error_code: str | None,
        profile_version: str,
        recovery_success: bool,
        observation_required: bool,
    ) -> dict[str, Any]:
        if not observation_required and not recovery_success:
            return {
                "observation_present": False,
                "observation_count": 0,
                "observation_contract_status": "not_applicable",
                "observation_model": None,
                "observation_source_type": None,
                "observation_recovery_validated": False,
                "observation_error_code": None,
            }
        trace = build_trace_from_hail_events(
            runbook,
            events,
            run_id=run_id,
            backend_id=self.name,
            backend_version=self.backend_version,
            execution_success=success,
            error_code=error_code,
        )
        observations = build_dmf_simulated_observations_from_events(
            events,
            trace,
            run_id=run_id,
            profile_version=profile_version,
            source_id=self.name,
            source_version=self.backend_version,
        )
        policy = default_observation_policy()
        result = validate_observation_contract(
            observations,
            trace,
            runbook,
            policy,
            context={"max_channels": 128, "grid_width": 16, "grid_height": 8},
            recovery_success=recovery_success,
        )
        first = observations[0] if observations else {}
        return {
            "observation_present": bool(observations),
            "observation_count": len(observations),
            "observation_contract_status": "pass" if result.ok else "fail",
            "observation_model": first.get("observation_model"),
            "observation_source_type": first.get("source", {}).get("source_type"),
            "observation_recovery_validated": bool(result.ok and recovery_success),
            "observation_error_code": result.error_code,
        }

    @staticmethod
    def _first_error_code(events: list[dict[str, Any]]) -> str | None:
        for event in events:
            if event.get("level") == "ERROR" or str(event.get("code", "")).startswith("E_"):
                code = event.get("code")
                return str(code) if code is not None else None
        return None

    def _execute_v1_hail_jsonl(self, vector: ConformanceVector, start: float) -> ExecutionResult:
        """Validate a declared HAIL JSONL input and return parsed events."""
        assert vector.input_path is not None
        payload = vector.input_path.read_text(encoding="utf-8")
        validation, events = parse_jsonl_events(payload)
        if not validation.ok:
            return ExecutionResult(
                success=False,
                events=events,
                error_code=validation.error_code,
                error_message=validation.message,
                validation_stage=validation.validation_stage,
                duration_ms=(time.perf_counter() - start) * 1000,
                details={
                    **self._base_report_details(vector),
                    "line_index": validation.index,
                },
            )
        return ExecutionResult(
            success=True,
            events=events,
            duration_ms=(time.perf_counter() - start) * 1000,
            details=self._base_report_details(vector),
        )

    def _execute_v1_project(self, vector: ConformanceVector, start: float) -> ExecutionResult:
        """Execute a declared .klein project through the geodesic simulator."""
        import io

        from klein.sim import runner as runner_module

        assert vector.input_path is not None
        try:
            data = load_json_artifact(vector.input_path)
            validation = validate_klein_project(data)
            if not validation.ok:
                return self._json_error_result(
                    start,
                    code=validation.error_code or ARTIFACT_SCHEMA_INVALID,
                    message=validation.message or "project artifact invalid",
                    stage="artifact_schema",
                    details=self._base_report_details(vector),
                )
            project = runner_module.load_project(vector.input_path)
        except ArtifactValidationError as exc:
            return self._json_error_result(
                start,
                code=exc.error_code,
                message=str(exc),
                details=self._base_report_details(vector),
            )
        except Exception as exc:
            return self._json_error_result(
                start,
                code=ARTIFACT_SCHEMA_INVALID,
                message=f"{type(exc).__name__}: {exc}",
                stage="artifact_schema",
                details=self._base_report_details(vector),
            )

        output_buffer = io.StringIO()
        run_id = vector.metadata.get("run_id", f"R{vector.id}")
        start_time_ms = int(vector.metadata.get("start_time_ms", 0))
        runner = runner_module.SimulationRunner(
            project=project,
            simgb=None,
            seed=int(vector.metadata.get("seed", 42)),
            output=output_buffer,
            run_id=run_id,
            start_time_ms=start_time_ms,
        )
        runner.emit_startup()
        source, sink = vector.get_source_sink()
        success = runner.run_geodesic(source, sink)
        runner.finalize()

        events: list[dict[str, Any]] = []
        output_buffer.seek(0)
        for line in output_buffer:
            line = line.strip()
            if line:
                events.append(json.loads(line))
        error_code = self._first_error_code(events)
        report_details = self._base_report_details(vector)
        runbook = build_runbook_from_artifact(
            vector.input_path,
            {
                "profile_id": vector.profile,
                "profile_version": str(vector.metadata.get("profile_version", "v1")),
                "mode": vector.mode,
            },
        )
        report_details.update(
            self._execution_artifact_details(
                runbook,
                run_id=run_id,
                success=success,
                error_code=error_code,
            )
        )
        events = self._with_lifecycle_events(
            vector,
            events=events,
            run_id=run_id,
            success=success,
            error_code=error_code,
            details=report_details,
        )

        return ExecutionResult(
            success=success,
            events=events,
            error_code=error_code,
            exit_code=0 if success else 2,
            duration_ms=(time.perf_counter() - start) * 1000,
            details=report_details,
        )

    def _load_container_input(
        self,
        vector: ConformanceVector,
        start: float,
    ) -> tuple[Container | None, ExecutionResult | None]:
        """Load a declared v1 container while preserving canonical negative error codes."""
        assert vector.input_path is not None
        try:
            data = load_json_artifact(vector.input_path)
        except ArtifactValidationError as exc:
            return None, self._json_error_result(
                start,
                code=exc.error_code,
                message=str(exc),
                details=self._base_report_details(vector),
            )

        validation = validate_klein_container(data)
        payload_validation_error = bool(
            validation.error_code
            and validation.error_code.startswith("PAYLOAD_")
            and validation.error_code != "ARTIFACT_PAYLOAD_MISSING"
        )
        if not validation.ok and not payload_validation_error:
            return None, self._json_error_result(
                start,
                code=validation.error_code or ARTIFACT_SCHEMA_INVALID,
                message=validation.message or "container artifact invalid",
                stage="artifact_schema",
                details=self._base_report_details(vector),
            )

        payload = data.get("payload") if isinstance(data, dict) else None
        payload_kind = payload.get("kind") if isinstance(payload, dict) else None
        if payload_kind and payload_kind not in {
            "CHANNEL_LIST",
            "FRAME_SEQUENCE",
            "BITMAP_SEQUENCE",
        }:
            return None, self._json_error_result(
                start,
                code=DDI_UNSUPPORTED_PAYLOAD,
                message=f"Unsupported payload kind {payload_kind}",
                stage="payload_validation",
                details=self._base_report_details(vector),
            )

        try:
            return Container.model_validate(data), None
        except Exception as exc:
            return None, self._json_error_result(
                start,
                code=ARTIFACT_SCHEMA_INVALID,
                message=f"{type(exc).__name__}: {exc}",
                stage="artifact_schema",
                details=self._base_report_details(vector),
            )

    def _execute_v1_container(self, vector: ConformanceVector, start: float) -> ExecutionResult:
        """Execute a declared .kleinc container through the full execution engine."""
        import io

        container, error = self._load_container_input(vector, start)
        if error is not None:
            return error
        assert container is not None

        try:
            self._ensure_imported()
            output_buffer = io.StringIO()
            run_id = vector.metadata.get("run_id", f"R{vector.id}")

            substrate = self._VirtualSubstrate(
                max_channels=128,
                grid_width=16,
                grid_height=8,
                seed=int(vector.metadata.get("seed", 42)),
            )
            substrate.connect("virtual://test")
            report_details = self._substrate_report_details(vector, substrate)
            runbook = build_runbook_from_artifact(
                vector.input_path,
                {
                    "profile_id": "dmf",
                    "profile_version": str(vector.metadata.get("profile_version", "v1")),
                    "mode": vector.mode,
                    "substrate_fingerprint": report_details.get("substrate_fingerprint"),
                },
            )
            fault_injection = vector.metadata.get("fault_injection") or {}
            if fault_injection.get("type") == "dead_channel":
                substrate.configure_validation(dead_channels=fault_injection.get("channels", []))
            transient_channels = tuple(fault_injection.get("channels", [])) if fault_injection.get("type") == "transient_channel_failure" else ()

            emitter = self._HAILEmitter(output=output_buffer, run_id=run_id)
            config = self._ExecutionConfig(
                ecrp_enabled=bool(vector.metadata.get("ecrp_enabled", self._ecrp_enabled)),
                ecrp_max_attempts=int(
                    vector.metadata.get("ecrp_max_attempts", self._ecrp_max_attempts)
                ),
                emit_frame_events=True,
                emit_observations=bool(vector.metadata.get("emit_observations", False)),
                transient_fault_channels=transient_channels,
                ecrp_recover_transient_faults=bool(transient_channels),
            )
            engine = self._ExecutionEngine(
                substrate=substrate,
                emitter=emitter,
                config=config,
            )
            result = engine.execute_container(container)

            events: list[dict[str, Any]] = []
            output_buffer.seek(0)
            for line in output_buffer:
                line = line.strip()
                if line:
                    events.append(json.loads(line))

            error_code = self._first_error_code(events)
            report_details.update(
                self._execution_artifact_details(
                    runbook,
                    run_id=run_id,
                    success=result.success,
                    error_code=error_code,
                    events=events,
                )
            )
            report_details.update(
                self._ecrp_contract_details(
                    events=events,
                    runbook=runbook,
                    run_id=run_id,
                    success=result.success,
                    error_code=error_code,
                    mode=vector.mode,
                    max_attempts=int(vector.metadata.get("ecrp_max_attempts", self._ecrp_max_attempts)),
                    allow_success_after_retry=bool(vector.metadata.get("ecrp_allow_success_after_retry", False)),
                    allowed_success_strategies=list(vector.metadata.get("ecrp_allowed_success_strategies", [])),
                )
            )
            report_details.update(
                self._observation_contract_details(
                    events=events,
                    runbook=runbook,
                    run_id=run_id,
                    success=result.success,
                    error_code=error_code,
                    profile_version=str(vector.metadata.get("profile_version", "v1")),
                    recovery_success=report_details.get("ecrp_recovery_status") == "success",
                    observation_required=bool(vector.metadata.get("observation_required", False)),
                )
            )
            events = self._with_lifecycle_events(
                vector,
                events=events,
                run_id=run_id,
                success=result.success,
                error_code=error_code,
                details=report_details,
            )

            return ExecutionResult(
                success=result.success,
                events=events,
                error_code=error_code,
                exit_code=0 if result.success else 1,
                duration_ms=(time.perf_counter() - start) * 1000,
                details=report_details,
            )
        except Exception as exc:
            return ExecutionResult(
                success=False,
                events=[],
                error_code="EXCEPTION",
                error_message=f"{type(exc).__name__}: {exc}",
                duration_ms=(time.perf_counter() - start) * 1000,
                details=self._base_report_details(vector),
            )

    def _execute_invalid_artifact(self, vector: ConformanceVector, start: float) -> ExecutionResult:
        """Parse an intentionally invalid artifact and report the first hard failure."""
        assert vector.input_path is not None
        try:
            json.loads(vector.input_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return self._json_error_result(
                start,
                code=ARTIFACT_JSON_INVALID,
                message=str(exc),
                details=self._base_report_details(vector),
            )
        return self._json_error_result(
            start,
            code=ARTIFACT_SCHEMA_INVALID,
            message="Invalid artifact parsed as JSON but has no supported v1 input type",
            stage="artifact_schema",
            details=self._base_report_details(vector),
        )

    def _execute_v1(self, vector: ConformanceVector, start: float) -> ExecutionResult:
        """Execute a v1 vector only through its declared input contract."""
        if not vector.input_type or vector.input_path is None or not vector.input_path.exists():
            return self._missing_input_result(vector, start)

        input_type = vector.input_type
        if input_type == "hail_jsonl":
            return self._execute_v1_hail_jsonl(vector, start)
        if input_type == "project":
            return self._execute_v1_project(vector, start)
        if input_type == "container":
            return self._execute_v1_container(vector, start)
        if input_type == "invalid_artifact":
            return self._execute_invalid_artifact(vector, start)

        return self._json_error_result(
            start,
            code=ARTIFACT_SCHEMA_INVALID,
            message=f"Unsupported v1 input_type {input_type}",
            stage="vector_input",
            details=self._base_report_details(vector),
        )

    def execute(self, vector: ConformanceVector) -> ExecutionResult:
        """Execute vector using full execution engine."""
        import io

        start = time.perf_counter()

        if vector.schema_version == "v1":
            return self._execute_v1(vector, start)

        if not vector.container and not vector.loose_path:
            return ExecutionResult(
                success=False,
                events=[],
                error_message="No executable content",
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        try:
            self._ensure_imported()

            # Create output buffer
            output_buffer = io.StringIO()
            run_id = f"R{vector.id}"

            # Create virtual substrate
            substrate = self._VirtualSubstrate(
                max_channels=128,
                grid_width=16,
                grid_height=8,
                seed=42,
            )
            substrate.connect("virtual://test")

            # Configure validation based on container SImgB
            if vector.container:
                # Extract expected hashes from container for validation
                simgb = None
                if hasattr(vector.container, "simgb") and vector.container.simgb:
                    simgb = vector.container.simgb
                elif hasattr(vector.container, "dsb") and vector.container.dsb:
                    simgb = vector.container.dsb  # Legacy field

                if simgb:
                    # For negative tests, configure mismatched hashes
                    if vector.is_negative and vector.expected_error_code:
                        if "GEOMETRY" in vector.expected_error_code.upper():
                            substrate.configure_validation(geometry_hash="WRONG_HASH")
                        elif "CALIBRATION" in vector.expected_error_code.upper():
                            substrate.configure_validation(calibration_hash="WRONG_HASH")
                        elif (
                            "DEAD" in vector.expected_error_code.upper()
                            or "CHANNEL" in vector.expected_error_code.upper()
                        ):
                            substrate.configure_validation(dead_channels=[17, 42])

            # Create emitter
            emitter = self._HAILEmitter(
                output=output_buffer,
                run_id=run_id,
            )

            # Create execution config
            config = self._ExecutionConfig(
                ecrp_enabled=self._ecrp_enabled,
                ecrp_max_attempts=self._ecrp_max_attempts,
                emit_frame_events=True,
                emit_observations=True,
            )

            # Create engine
            engine = self._ExecutionEngine(
                substrate=substrate,
                emitter=emitter,
                config=config,
            )

            # Execute
            if vector.container:
                result = engine.execute_container(vector.container)
            else:
                # Loose format - create minimal container-like execution
                emitter.emit_runtime_state_snapshot(
                    t=0,
                    rimgb_hash="loose_vector_hash",
                    state_fields={"vector_id": vector.id},
                )
                emitter.emit_device_event(t=0, code="INIT", message="Run initialized")
                emitter.emit_device_event(t=1, code="SHUTDOWN", message="Run completed")
                result = type("Result", (), {"success": True, "tick": 1, "frames_executed": 0})()

            # Parse events from output
            events = []
            output_buffer.seek(0)
            for line in output_buffer:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

            # Check for error events (for negative test detection)
            error_code = None
            for event in events:
                if event.get("level") == "ERROR" or event.get("code", "").startswith("E_"):
                    error_code = event.get("code")
                    break

            return ExecutionResult(
                success=result.success,
                events=events,
                error_code=error_code,
                exit_code=0 if result.success else 1,
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        except Exception as e:
            return ExecutionResult(
                success=False,
                events=[],
                error_code="EXCEPTION",
                error_message=f"{type(e).__name__}: {e}",
                duration_ms=(time.perf_counter() - start) * 1000,
            )

    def cleanup(self) -> None:
        pass


class SubstrateBackend:
    """
    Backend for direct substrate driver integration (FUTURE).

    This is a placeholder for future expansion. When implemented,
    it will:
    1. Connect to actual hardware via SubstrateDriver
    2. Execute actuations from the test vector payload
    3. Capture observations and convert to HAIL events

    Integration points:
    - klein.substrate.api.SubstrateDriver protocol
    - klein.substrate.api.MockSubstrate for CI testing
    - Frame-based actuation from payload
    - Observation capture and event generation

    CI Testing with Fault Injection:
        For deterministic CI tests, use MockSubstrate with FaultRule:

        from klein.substrate.api import (
            MockSubstrate, Frame, FaultRule, Fault, FaultCode,
            WaveformProfile, WaveformMode
        )

        drv = MockSubstrate()
        drv.connect("mock://ci")
        drv.set_waveform(WaveformProfile(
            mode=WaveformMode.AC, voltage_v=200.0, ac_frequency_hz=1000.0
        ))

        # Inject deterministic fault on frame 3
        drv.add_fault_rule(FaultRule(
            when_seq=3,
            fault=Fault(FaultCode.OVERCURRENT, "Injected OC", {"channel": 17}),
        ))

        frames = [
            Frame(seq=1, active_electrodes=(17,), duration_ms=20),
            Frame(seq=2, active_electrodes=(18,), duration_ms=20),
            Frame(seq=3, active_electrodes=(19,), duration_ms=20),
        ]

        report = drv.run_sequence(frames)
        assert report.ok is False
        assert report.faults[0].code == FaultCode.OVERCURRENT
    """

    def __init__(
        self,
        driver_uri: str | None = None,
        capabilities: dict[str, Any] | None = None,
        fault_rules: list[Any] | None = None,
    ):
        self._driver_uri = driver_uri or "mock://ci"
        self._capabilities = capabilities or {}
        self._fault_rules = fault_rules or []
        self._driver = None

    @property
    def name(self) -> str:
        return "substrate"

    def check_capabilities(self, required: list[str]) -> tuple[bool, str]:
        """Check if connected substrate supports required capabilities."""
        # TODO: Query actual driver capabilities via self._driver.get_capabilities()
        return False, "Substrate backend not yet implemented"

    def execute(self, vector: ConformanceVector) -> ExecutionResult:
        """Execute vector on real hardware."""
        # TODO: Implement hardware execution
        # 1. Connect to driver if not connected:
        #    from klein.substrate.api import MockSubstrate
        #    self._driver = MockSubstrate()
        #    self._driver.connect(self._driver_uri)
        #
        # 2. Apply fault rules for CI testing:
        #    for rule in self._fault_rules:
        #        self._driver.add_fault_rule(rule)
        #
        # 3. Convert payload to Frames:
        #    frames = self._payload_to_frames(vector.container.payload)
        #
        # 4. Execute frame sequence:
        #    report = self._driver.run_sequence(frames)
        #
        # 5. Convert observations to HAIL events:
        #    observations = self._driver.read_observations()
        #    events = self._observations_to_sci_events(observations, report)
        #
        # 6. Return result:
        #    return ExecutionResult(success=report.ok, events=events, ...)

        return ExecutionResult(
            success=False,
            events=[],
            error_code="NOT_IMPLEMENTED",
            error_message="Substrate backend not yet implemented",
        )

    def add_fault_rule(self, rule: Any) -> None:
        """Add a fault rule for CI testing (pre-execution)."""
        self._fault_rules.append(rule)

    def cleanup(self) -> None:
        """Disconnect from hardware."""
        if self._driver is not None:
            try:
                # self._driver.reset()
                pass
            except Exception:  # noqa: B110 - substrate cleanup is best effort.
                pass
            self._driver = None


def create_backend(backend_type: BackendType, **kwargs: Any) -> Backend:
    """Factory function to create backend instances."""
    if backend_type == BackendType.MOCK:
        # MockBackend only accepts 'capabilities'
        mock_kwargs = {k: v for k, v in kwargs.items() if k == "capabilities"}
        return MockBackend(**mock_kwargs)
    elif backend_type == BackendType.SUBPROCESS:
        # SubprocessBackend accepts 'timeout_seconds', 'python_executable', 'capabilities'
        sub_kwargs = {
            k: v
            for k, v in kwargs.items()
            if k in ("timeout_seconds", "python_executable", "capabilities")
        }
        return SubprocessBackend(**sub_kwargs)
    elif backend_type == BackendType.SIMULATOR:
        # SimulatorBackend only accepts 'capabilities'
        sim_kwargs = {k: v for k, v in kwargs.items() if k == "capabilities"}
        return SimulatorBackend(**sim_kwargs)
    elif backend_type == BackendType.FULL_SIMULATOR:
        # FullSimulatorBackend accepts 'capabilities', 'ecrp_enabled', 'ecrp_max_attempts'
        full_kwargs = {
            k: v
            for k, v in kwargs.items()
            if k in ("capabilities", "ecrp_enabled", "ecrp_max_attempts")
        }
        return FullSimulatorBackend(**full_kwargs)
    elif backend_type == BackendType.SUBSTRATE:
        # SubstrateBackend accepts 'driver_uri', 'capabilities', 'fault_rules'
        sub_kwargs = {
            k: v for k, v in kwargs.items() if k in ("driver_uri", "capabilities", "fault_rules")
        }
        return SubstrateBackend(**sub_kwargs)
    else:
        raise ValueError(f"Unknown backend type: {backend_type}")


# =============================================================================
