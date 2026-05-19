#!/usr/bin/env python3
"""
Execution Engine Test Suite

Tests the VirtualSubstrate, PayloadParser, and ExecutionEngine.
"""

import io
import json
from dataclasses import replace
from pathlib import Path

import pytest

from klein.common.errors import ErrorCode
from klein.profiles.dmf import DMFProfileContext, context_from_substrate
from klein.sim.virtual_substrate import (
    Droplet,
    DropletState,
    KleinErrorCode,
    ValidationError,
    VirtualSubstrate,
)
from klein.sim.execution_engine import (
    ExecutionEngine,
    ExecutionConfig,
    ExecutionResult,
    HAILEmitter,
    PayloadParser,
    PayloadKind,
    ChannelEntry,
    FrameSequence,
)
from klein.substrate.api import Frame, VoltageRange, WaveformMode, WaveformProfile


# =============================================================================
# VirtualSubstrate Tests
# =============================================================================

class TestVirtualSubstrateBasics:
    """Basic VirtualSubstrate functionality."""
    
    def test_connect_and_capabilities(self):
        """Test connection and capability reporting."""
        substrate = VirtualSubstrate(max_channels=64)
        substrate.connect("virtual://test")
        
        caps = substrate.get_capabilities()
        assert caps.device_vendor == "klein-sim"
        assert caps.device_model == "VirtualSubstrate"
        assert caps.max_channels == 64
        assert caps.sensing.impedance is True
    
    def test_grid_topology(self):
        """Test grid topology generation."""
        substrate = VirtualSubstrate(max_channels=32, grid_width=8, grid_height=4)
        substrate.connect("virtual://test")
        
        topo = substrate.get_topology()
        assert len(topo.electrodes) == 32
        assert topo.cartridge_id == "VIRTUAL-GRID"
        
        # Check adjacency for corner electrode (0)
        assert 0 in topo.adjacency
        neighbors = topo.adjacency[0]
        assert 1 in neighbors  # right
        assert 8 in neighbors  # down
        assert -1 not in neighbors  # no left
    
    def test_apply_frame_success(self):
        """Test successful frame application."""
        substrate = VirtualSubstrate()
        substrate.connect("virtual://test")
        
        frame = Frame(seq=1, active_electrodes=(10, 11), duration_ms=20)
        ack = substrate.apply_frame(frame)
        
        assert ack.ok is True
        assert ack.seq == 1


class TestDropletSimulation:
    """Droplet physics simulation tests."""
    
    def test_spawn_droplet(self):
        """Test spawning a droplet."""
        substrate = VirtualSubstrate()
        substrate.connect("virtual://test")
        
        substrate.spawn_droplet("drop1", electrode_id=10)
        positions = substrate.get_droplet_positions()
        
        assert "drop1" in positions
        assert positions["drop1"] == 10
    
    def test_droplet_movement(self):
        """Test droplet moves when adjacent electrode activated."""
        substrate = VirtualSubstrate(grid_width=4, grid_height=4, max_channels=16)
        substrate.connect("virtual://test")
        
        # Spawn at electrode 5 (1,1 in 4x4 grid)
        substrate.spawn_droplet("drop1", electrode_id=5)
        
        # Activate adjacent electrode 6 (right)
        frame = Frame(seq=1, active_electrodes=(6,), duration_ms=20)
        ack = substrate.apply_frame(frame)
        
        assert ack.ok is True
        positions = substrate.get_droplet_positions()
        assert positions["drop1"] == 6  # Moved to activated electrode
    
    def test_stuck_droplet_probability(self):
        """Test stuck probability affects movement."""
        # 100% stuck probability
        substrate = VirtualSubstrate(stuck_probability=1.0)
        substrate.connect("virtual://test")
        
        substrate.spawn_droplet("drop1", electrode_id=5)
        
        # Try to move
        frame = Frame(seq=1, active_electrodes=(6,), duration_ms=20)
        ack = substrate.apply_frame(frame)
        
        # Should be stuck
        positions = substrate.get_droplet_positions()
        assert positions["drop1"] == 5  # Didn't move
        assert "stuck_droplets" in ack.detail
    
    def test_impedance_sensing(self):
        """Test simulated impedance readings."""
        substrate = VirtualSubstrate()
        substrate.connect("virtual://test")
        
        # Empty electrode - high impedance
        readings = substrate.read_impedance_map()
        assert readings[10] > 1_000_000  # ~10 MΩ
        
        # Add droplet
        substrate.spawn_droplet("drop1", electrode_id=10)
        readings = substrate.read_impedance_map()
        assert readings[10] < 100_000  # ~50 kΩ


class TestContainerValidation:
    """Container/SImgB validation tests."""
    
    def test_geometry_hash_mismatch(self):
        """Test geometry hash validation."""
        substrate = VirtualSubstrate()
        substrate.connect("virtual://test")
        
        # Configure expected hash
        substrate.configure_validation(geometry_hash="expected_hash_123")
        
        # Validate with wrong hash
        simgb = {"geometry_hash": "wrong_hash_456"}
        errors = substrate.validate_simgb(simgb)
        
        assert len(errors) == 1
        assert errors[0].code == KleinErrorCode.SIMGB_GEOMETRY_MISMATCH
    
    def test_calibration_hash_mismatch(self):
        """Test calibration hash validation."""
        substrate = VirtualSubstrate()
        substrate.connect("virtual://test")
        
        substrate.configure_validation(calibration_hash="cal_hash_abc")
        
        simgb = {"calibration": {"hash": "cal_hash_xyz"}}
        errors = substrate.validate_simgb(simgb)
        
        assert len(errors) == 1
        assert errors[0].code == KleinErrorCode.SIMGB_CALIBRATION_MISMATCH
    
    def test_dead_channel_validation(self):
        """Test dead channel detection."""
        substrate = VirtualSubstrate()
        substrate.connect("virtual://test")
        
        substrate.configure_validation(dead_channels=[17, 42])
        
        # Apply frame with dead channel
        frame = Frame(seq=1, active_electrodes=(17,), duration_ms=20)
        ack = substrate.apply_frame(frame)
        
        assert ack.ok is False
        assert ack.faults[0].detail.get("klein_error_code") == "CHANNEL_DEAD"


# =============================================================================
# PayloadParser Tests
# =============================================================================

class TestPayloadParser:
    """Payload parsing tests."""
    
    def test_parse_channel_list(self):
        """Test CHANNEL_LIST payload parsing."""
        parser = PayloadParser()
        
        payload = {
            "kind": "CHANNEL_LIST",
            "encoding": "JSON",
            "data": [
                {"t": 0, "channel_id": 10, "state": "ON", "voltage_v": 200.0},
                {"t": 0, "channel_id": 11, "state": "ON", "voltage_v": 200.0},
                {"t": 10, "channel_id": 12, "state": "ON", "voltage_v": 200.0},
            ],
        }
        
        sequence = parser.parse_container_payload(payload)
        
        assert sequence.source_kind == PayloadKind.CHANNEL_LIST
        assert len(sequence.frames) == 2  # Two ticks: 0 and 10
        
        # First frame at t=0 has two channels
        assert len(sequence.frames[0].active_electrodes) == 2
        assert 10 in sequence.frames[0].active_electrodes
        assert 11 in sequence.frames[0].active_electrodes
        
        # Second frame at t=10 has one channel
        assert len(sequence.frames[1].active_electrodes) == 1
        assert 12 in sequence.frames[1].active_electrodes
    
    def test_parse_frame_sequence_sparse(self):
        """Test FRAME_SEQUENCE with sparse format."""
        parser = PayloadParser()
        
        payload = {
            "kind": "FRAME_SEQUENCE",
            "encoding": "JSON",
            "data": [
                {"t": 0, "format": "sparse", "data": [5, 6, 7]},
                {"t": 10, "format": "sparse", "data": [8, 9]},
            ],
        }
        
        sequence = parser.parse_container_payload(payload)
        
        assert sequence.source_kind == PayloadKind.FRAME_SEQUENCE
        assert len(sequence.frames) == 2
        assert sequence.frames[0].active_electrodes == (5, 6, 7)
        assert sequence.frames[1].active_electrodes == (8, 9)
    
    def test_parse_empty_payload(self):
        """Test empty payload handling."""
        parser = PayloadParser()
        
        payload = {"kind": "CHANNEL_LIST", "data": []}
        sequence = parser.parse_container_payload(payload)
        
        assert len(sequence.frames) == 0

    def test_validate_channel_list_rejects_invalid_state(self):
        parser = PayloadParser()
        errors = parser.validate_container_payload({
            "kind": "CHANNEL_LIST",
            "data": [{"t": 0, "channel_id": 5, "state": "PULSE", "voltage_v": 200.0}],
        })

        assert errors[0].code == KleinErrorCode.PAYLOAD_INVALID_STATE

    def test_validate_channel_list_rejects_conflict(self):
        parser = PayloadParser()
        errors = parser.validate_container_payload({
            "kind": "CHANNEL_LIST",
            "data": [
                {"t": 0, "channel_id": 5, "state": "ON", "voltage_v": 200.0},
                {"t": 0, "channel_id": 5, "state": "OFF", "voltage_v": 200.0},
            ],
        })

        assert errors[0].code == KleinErrorCode.PAYLOAD_CONFLICTING_STATE

    def test_validate_frame_sequence_rejects_sparse_oob(self):
        parser = PayloadParser(max_channels=8)
        errors = parser.validate_container_payload({
            "kind": "FRAME_SEQUENCE",
            "data": [{"t": 0, "format": "sparse", "data": [8]}],
        })

        assert errors[0].code == KleinErrorCode.PAYLOAD_OOB_PIXEL

    def test_validate_bitmap_rejects_invalid_base64(self):
        parser = PayloadParser()
        errors = parser.validate_container_payload({
            "kind": "BITMAP_SEQUENCE",
            "data": ["not base64 !"],
        })

        assert errors[0].code == KleinErrorCode.PAYLOAD_BASE64_INVALID

    def test_profile_context_uses_substrate_max_channels(self):
        substrate = VirtualSubstrate(max_channels=8, grid_width=4, grid_height=2)
        substrate.connect("virtual://test")
        parser = PayloadParser(context_from_substrate(substrate))

        errors = parser.validate_container_payload({
            "kind": "CHANNEL_LIST",
            "data": [{"t": 0, "channel_id": 9, "state": "ON", "voltage_v": 50.0}],
        })

        assert errors[0].code == ErrorCode.PAYLOAD_CHANNEL_OOB

    def test_profile_context_uses_declared_voltage_range(self):
        substrate = VirtualSubstrate(max_channels=16)
        substrate.connect("virtual://test")
        caps = substrate.get_capabilities()
        limited_caps = replace(caps, voltage_range=VoltageRange(v_min=0.0, v_max=100.0))
        limited = VirtualSubstrate(max_channels=16, capabilities=limited_caps)
        limited.connect("virtual://limited")
        parser = PayloadParser(context_from_substrate(limited))

        errors = parser.validate_container_payload({
            "kind": "CHANNEL_LIST",
            "data": [{"t": 0, "channel_id": 4, "state": "ON", "voltage_v": 200.0}],
        })

        assert errors[0].code == ErrorCode.PAYLOAD_VOLTAGE_OOB

    def test_sparse_coordinates_use_declared_grid_width(self):
        parser = PayloadParser(DMFProfileContext(max_channels=16, grid_width=4, grid_height=4))

        sequence = parser.parse_container_payload({
            "kind": "FRAME_SEQUENCE",
            "data": [{"t": 0, "format": "sparse", "data": [{"x": 1, "y": 1}]}],
        })

        assert sequence.frames[0].active_electrodes == (5,)

    def test_same_payload_can_fail_under_smaller_capabilities(self):
        payload = {
            "kind": "CHANNEL_LIST",
            "data": [{"t": 0, "channel_id": 9, "state": "ON", "voltage_v": 50.0}],
        }

        assert PayloadParser(DMFProfileContext(max_channels=16)).validate_container_payload(payload) == []
        errors = PayloadParser(DMFProfileContext(max_channels=8)).validate_container_payload(payload)
        assert errors[0].code == ErrorCode.PAYLOAD_CHANNEL_OOB

    def test_delta_tiles_apply_add_remove_statefully(self):
        parser = PayloadParser()

        sequence = parser.parse_container_payload({
            "kind": "FRAME_SEQUENCE",
            "data": [
                {"t": 0, "format": "delta_tiles", "data": {"add": [1, 2], "remove": []}},
                {"t": 1, "format": "delta_tiles", "data": {"add": [], "remove": [1]}},
            ],
        })

        assert sequence.frames[0].active_electrodes == (1, 2)
        assert sequence.frames[1].active_electrodes == (2,)

    def test_rle_frame_format_is_explicitly_unsupported_in_v1(self):
        parser = PayloadParser()

        errors = parser.validate_container_payload({
            "kind": "FRAME_SEQUENCE",
            "data": [{"t": 0, "format": "rle", "data": [1, 2]}],
        })

        assert errors[0].code == ErrorCode.PAYLOAD_UNSUPPORTED_FRAME_FORMAT


# =============================================================================
# HAILEmitter Tests
# =============================================================================

class TestHAILEmitter:
    """HAIL event emission tests."""
    
    def test_emit_device_event(self):
        """Test DEVICE_EVENT emission."""
        output = io.StringIO()
        emitter = HAILEmitter(output=output, run_id="test_run")
        
        emitter.emit_device_event(t=0, code="START", detail={"foo": "bar"})
        
        output.seek(0)
        event = json.loads(output.readline())
        
        assert event["kind"] == "DEVICE_EVENT"
        assert event["t"] == 0
        assert event["run_id"] == "test_run"
        assert event["code"] == "START"
        assert event["detail"]["foo"] == "bar"
    
    def test_emit_measurement(self):
        """Test MEASUREMENT emission."""
        output = io.StringIO()
        emitter = HAILEmitter(output=output, run_id="test_run")
        
        emitter.emit_measurement(
            t=10,
            detector_id="impedance",
            measurement_id="m1",
            value_type="F64",
            value_data=42.5,
        )
        
        output.seek(0)
        event = json.loads(output.readline())
        
        assert event["kind"] == "MEASUREMENT"
        assert event["detector_id"] == "impedance"
        assert event["value"]["type"] == "F64"
        assert event["value"]["data"] == 42.5
    
    def test_emit_ecrp_attempt(self):
        """Test ECRP_ATTEMPT emission."""
        output = io.StringIO()
        emitter = HAILEmitter(output=output, run_id="test_run")
        
        emitter.emit_ecrp_attempt(
            t=5,
            attempt_index=1,
            strategy="NUDGE_PULSE",
            outcome="NO_CHANGE",
            deltas={"shift": 0},
            parameters={"pulse_ms": 50},
        )
        
        output.seek(0)
        event = json.loads(output.readline())
        
        assert event["kind"] == "ECRP_ATTEMPT"
        assert event["attempt_index"] == 1
        assert event["outcome"] == "NO_CHANGE"


# =============================================================================
# ExecutionEngine Tests
# =============================================================================

class TestExecutionEngine:
    """Execution engine integration tests."""
    
    def test_execute_simple_payload(self):
        """Test executing a simple payload."""
        output = io.StringIO()
        substrate = VirtualSubstrate()
        substrate.connect("virtual://test")
        
        emitter = HAILEmitter(output=output, run_id="exec_test")
        config = ExecutionConfig(emit_frame_events=True, emit_observations=False)
        engine = ExecutionEngine(substrate=substrate, emitter=emitter, config=config)
        
        # Create mock container-like object
        class MockContainer:
            class MockManifest:
                def model_dump(self):
                    return {"version": "1.0"}
            manifest = MockManifest()
            payload = {
                "kind": "CHANNEL_LIST",
                "data": [
                    {"t": 0, "channel_id": 5, "state": "ON", "voltage_v": 200.0},
                ],
            }
        
        result = engine.execute_container(MockContainer())
        
        assert result.success is True
        assert result.frames_executed == 1
        
        # Check events were emitted
        output.seek(0)
        events = [json.loads(line) for line in output]
        
        kinds = [e["kind"] for e in events]
        assert "RUNTIME_STATE_SNAPSHOT" in kinds
        assert "DEVICE_EVENT" in kinds
    
    def test_execute_with_validation_error(self):
        """Test execution with validation error injection."""
        output = io.StringIO()
        substrate = VirtualSubstrate()
        substrate.connect("virtual://test")
        
        # Inject error
        substrate.inject_error(ValidationError(
            code=KleinErrorCode.SCHEMA_VIOLATION,
            message="Test validation error",
        ))
        
        emitter = HAILEmitter(output=output, run_id="error_test")
        engine = ExecutionEngine(substrate=substrate, emitter=emitter)
        
        class MockContainer:
            class MockManifest:
                def model_dump(self):
                    return {}
            manifest = MockManifest()
            payload = {"kind": "CHANNEL_LIST", "data": [{"t": 0, "channel_id": 0, "state": "ON", "voltage_v": 200}]}
        
        result = engine.execute_container(MockContainer())
        
        # First frame should fail due to injected error
        assert result.frames_executed == 0 or len(result.errors) > 0

    def test_ecrp_max_attempts_one_emits_one_attempt(self):
        output = io.StringIO()
        substrate = VirtualSubstrate()
        substrate.connect("virtual://test")
        substrate.configure_validation(dead_channels=[5])
        emitter = HAILEmitter(output=output, run_id="ecrp_test")
        engine = ExecutionEngine(
            substrate=substrate,
            emitter=emitter,
            config=ExecutionConfig(ecrp_enabled=True, ecrp_max_attempts=1, emit_observations=False),
        )

        class MockContainer:
            class MockManifest:
                def model_dump(self):
                    return {"version": "1.0"}
            manifest = MockManifest()
            payload = {"kind": "CHANNEL_LIST", "data": [{"t": 0, "channel_id": 5, "state": "ON", "voltage_v": 200}]}

        result = engine.execute_container(MockContainer())
        events = [json.loads(line) for line in output.getvalue().splitlines()]
        attempts = [event for event in events if event["kind"] == "ECRP_ATTEMPT"]

        assert result.success is False
        assert len(attempts) == 1
        assert attempts[0]["attempt_index"] == 1
        assert attempts[0]["strategy"] == "NUDGE_PULSE"
        assert attempts[0]["outcome"] == "PARTIAL"

    def test_ecrp_max_attempts_two_emits_at_most_two_attempts(self):
        output = io.StringIO()
        substrate = VirtualSubstrate()
        substrate.connect("virtual://test")
        substrate.configure_validation(dead_channels=[5])
        emitter = HAILEmitter(output=output, run_id="ecrp_test")
        engine = ExecutionEngine(
            substrate=substrate,
            emitter=emitter,
            config=ExecutionConfig(ecrp_enabled=True, ecrp_max_attempts=2, emit_observations=False),
        )

        class MockContainer:
            class MockManifest:
                def model_dump(self):
                    return {"version": "1.0"}
            manifest = MockManifest()
            payload = {"kind": "CHANNEL_LIST", "data": [{"t": 0, "channel_id": 5, "state": "ON", "voltage_v": 200}]}

        result = engine.execute_container(MockContainer())
        attempts = [
            json.loads(line)
            for line in output.getvalue().splitlines()
            if json.loads(line)["kind"] == "ECRP_ATTEMPT"
        ]

        assert result.success is False
        assert 1 <= len(attempts) <= 2
        assert attempts[0]["strategy"] == "NUDGE_PULSE"
        assert attempts[0]["outcome"] == "NO_CHANGE"


# =============================================================================
# Integration Test with Real Container
# =============================================================================

class TestIntegrationWithContainer:
    """Integration tests using real .kleinc containers."""
    
    def test_load_and_execute_001(self):
        """Test loading and executing vector 001."""
        container_path = Path(__file__).parent / "vectors" / "kap" / "001_minimal_muxed.klnc"
        if not container_path.exists():
            pytest.skip("Test vector not found")
        
        with open(container_path) as f:
            data = json.load(f)
        
        from klein.common.models import Container
        container = Container.model_validate(data)
        
        output = io.StringIO()
        substrate = VirtualSubstrate()
        substrate.connect("virtual://test")
        
        emitter = HAILEmitter(output=output, run_id="int_test")
        config = ExecutionConfig(emit_frame_events=True, emit_observations=True)
        engine = ExecutionEngine(substrate=substrate, emitter=emitter, config=config)
        
        result = engine.execute_container(container)
        
        assert result.success is True
        assert result.frames_executed >= 1
        
        # Verify HAIL output
        output.seek(0)
        events = [json.loads(line) for line in output]
        assert len(events) >= 3  # At least startup, frame, shutdown


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
