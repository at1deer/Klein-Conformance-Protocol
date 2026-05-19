"""
Virtual Substrate - Full simulation of a DMF substrate for conformance testing.

Extends MockSubstrate with:
- Droplet position tracking (occupancy model)
- Simulated impedance sensing
- Stuck droplet detection (for ECRP testing)
- Deterministic fault injection with error code mapping
- Container/SImgB validation

This enables the conformance harness to run test vectors without real hardware.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple

from klein.substrate.api import (
    Ack,
    AddressingMode,
    CapabilityProfile,
    Electrode,
    ElectrodeTopology,
    Fault,
    FaultCode,
    FaultRule,
    Frame,
    FrequencyRange,
    HealthReport,
    MockSubstrate,
    Observation,
    ObservationSource,
    RunOptions,
    RunReport,
    SensingProfile,
    SubstrateError,
    TimingProfile,
    VoltageRange,
    WaveformMode,
    WaveformProfile,
)


# =============================================================================
# Error Code Mapping (Klein Protocol → FaultCode)
# =============================================================================

class KleinErrorCode(str, Enum):
    """Klein Protocol error codes that can be simulated."""
    # Schema/Validation errors
    SCHEMA_VIOLATION = "SCHEMA_VIOLATION"
    PAYLOAD_MALFORMED = "PAYLOAD_MALFORMED"
    DDI_UNSUPPORTED_PAYLOAD = "DDI_UNSUPPORTED_PAYLOAD"
    PAYLOAD_CHANNEL_OOB = "PAYLOAD_CHANNEL_OOB"
    PAYLOAD_INVALID_STATE = "PAYLOAD_INVALID_STATE"
    PAYLOAD_VOLTAGE_OOB = "PAYLOAD_VOLTAGE_OOB"
    PAYLOAD_FREQUENCY_OOB = "PAYLOAD_FREQUENCY_OOB"
    PAYLOAD_CONFLICTING_STATE = "PAYLOAD_CONFLICTING_STATE"
    PAYLOAD_OOB_PIXEL = "PAYLOAD_OOB_PIXEL"
    PAYLOAD_NONMONOTONIC_TICKS = "PAYLOAD_NONMONOTONIC_TICKS"
    PAYLOAD_DUPLICATE_PIXEL = "PAYLOAD_DUPLICATE_PIXEL"
    PAYLOAD_BASE64_INVALID = "PAYLOAD_BASE64_INVALID"
    PAYLOAD_DELTA_CONFLICT = "PAYLOAD_DELTA_CONFLICT"
    PAYLOAD_DELTA_REMOVE_MISS = "PAYLOAD_DELTA_REMOVE_MISS"
    PAYLOAD_UNSUPPORTED_DIMS = "PAYLOAD_UNSUPPORTED_DIMS"
    PAYLOAD_UNSUPPORTED_FRAME_FORMAT = "PAYLOAD_UNSUPPORTED_FRAME_FORMAT"

    # SImgB/RImgB errors
    SIMGB_GEOMETRY_MISMATCH = "SIMGB_GEOMETRY_MISMATCH"
    SIMGB_CALIBRATION_MISMATCH = "SIMGB_CALIBRATION_MISMATCH"
    SIMGB_HASH_MISMATCH = "SIMGB_HASH_MISMATCH"
    RIMGB_SCHEMA_INVALID = "RIMGB_SCHEMA_INVALID"
    DSB_GEOMETRY_MISMATCH = "SIMGB_GEOMETRY_MISMATCH"  # Legacy alias
    CALIBRATION_HASH_MISMATCH = "SIMGB_CALIBRATION_MISMATCH"  # Legacy alias
    RSB_SCHEMA_INVALID = "RIMGB_SCHEMA_INVALID"  # Legacy alias
    
    # Execution errors
    CHANNEL_DEAD = "CHANNEL_DEAD"
    DROPLET_STUCK = "DROPLET_STUCK"
    DROPLET_LOST = "DROPLET_LOST"
    DROPLET_COLLISION = "DROPLET_COLLISION"
    
    # ECRP errors
    ECRP_BOUNDS_EXCEEDED = "ECRP_BOUNDS_EXCEEDED"
    ECRP_MISSING_EVIDENCE = "ECRP_MISSING_EVIDENCE"
    LCP_BOUNDS_EXCEEDED = "ECRP_BOUNDS_EXCEEDED"  # Legacy alias
    LCP_MISSING_EVIDENCE = "ECRP_MISSING_EVIDENCE"  # Legacy alias
    
    # Hardware errors
    OVERCURRENT = "OVERCURRENT"
    UNDERVOLTAGE = "UNDERVOLTAGE"
    WATCHDOG_TIMEOUT = "WATCHDOG_TIMEOUT"


@dataclass
class ValidationError:
    """Validation error from container/SImgB checking."""
    code: KleinErrorCode
    message: str
    detail: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Droplet Model
# =============================================================================

@dataclass
class Droplet:
    """Represents a droplet on the substrate."""
    id: str
    electrode_id: int
    volume_nl: float = 1000.0  # nanoliters
    stuck: bool = False
    stuck_since_seq: Optional[int] = None
    
    def move_to(self, electrode_id: int) -> None:
        """Move droplet to a new electrode."""
        self.electrode_id = electrode_id
        self.stuck = False
        self.stuck_since_seq = None


@dataclass 
class DropletState:
    """Tracks all droplets on the substrate."""
    droplets: Dict[str, Droplet] = field(default_factory=dict)
    electrode_occupancy: Dict[int, str] = field(default_factory=dict)  # electrode -> droplet_id
    
    def add_droplet(self, droplet: Droplet) -> None:
        """Add a droplet to the substrate."""
        self.droplets[droplet.id] = droplet
        self.electrode_occupancy[droplet.electrode_id] = droplet.id
    
    def move_droplet(self, droplet_id: str, to_electrode: int) -> bool:
        """
        Move a droplet to a new electrode.
        
        Returns:
            True if move succeeded, False if collision or stuck
        """
        if droplet_id not in self.droplets:
            return False
        
        droplet = self.droplets[droplet_id]
        
        # Check for stuck droplet
        if droplet.stuck:
            return False
        
        # Check for collision
        if to_electrode in self.electrode_occupancy:
            existing = self.electrode_occupancy[to_electrode]
            if existing != droplet_id:
                return False  # Collision
        
        # Move
        old_electrode = droplet.electrode_id
        if old_electrode in self.electrode_occupancy:
            del self.electrode_occupancy[old_electrode]
        
        droplet.move_to(to_electrode)
        self.electrode_occupancy[to_electrode] = droplet_id
        return True
    
    def get_droplet_at(self, electrode_id: int) -> Optional[Droplet]:
        """Get droplet at an electrode, if any."""
        droplet_id = self.electrode_occupancy.get(electrode_id)
        if droplet_id:
            return self.droplets.get(droplet_id)
        return None
    
    def mark_stuck(self, droplet_id: str, seq: int) -> None:
        """Mark a droplet as stuck."""
        if droplet_id in self.droplets:
            self.droplets[droplet_id].stuck = True
            self.droplets[droplet_id].stuck_since_seq = seq
    
    def clear(self) -> None:
        """Clear all droplets."""
        self.droplets.clear()
        self.electrode_occupancy.clear()


# =============================================================================
# Simulated Sensing
# =============================================================================

@dataclass
class ImpedanceReading:
    """Simulated impedance reading for an electrode."""
    electrode_id: int
    impedance_ohms: float
    occupied: bool
    timestamp_ms: int


class SensorSimulator:
    """Generates simulated sensor readings based on droplet state."""
    
    # Typical impedance values (simplified model)
    IMPEDANCE_EMPTY = 10_000_000.0  # 10 MΩ when empty
    IMPEDANCE_DROPLET = 50_000.0     # 50 kΩ when droplet present
    IMPEDANCE_NOISE_PERCENT = 5.0    # ±5% noise
    
    def __init__(self, seed: int = 42):
        self._rng = random.Random(seed)
    
    def read_impedance(
        self,
        electrode_id: int,
        droplet_state: DropletState,
        timestamp_ms: int,
    ) -> ImpedanceReading:
        """Generate simulated impedance reading."""
        droplet = droplet_state.get_droplet_at(electrode_id)
        occupied = droplet is not None
        
        base = self.IMPEDANCE_DROPLET if occupied else self.IMPEDANCE_EMPTY
        noise = self._rng.gauss(0, base * self.IMPEDANCE_NOISE_PERCENT / 100)
        impedance = max(0, base + noise)
        
        return ImpedanceReading(
            electrode_id=electrode_id,
            impedance_ohms=impedance,
            occupied=occupied,
            timestamp_ms=timestamp_ms,
        )
    
    def detect_occupancy(
        self,
        electrodes: List[int],
        droplet_state: DropletState,
        timestamp_ms: int,
    ) -> Dict[int, bool]:
        """Detect which electrodes have droplets."""
        return {
            eid: droplet_state.get_droplet_at(eid) is not None
            for eid in electrodes
        }


# =============================================================================
# Container Validation
# =============================================================================

class ContainerValidator:
    """Validates .kleinc containers and SImgB bundles."""
    
    def __init__(self, geometry_hash: Optional[str] = None, calibration_hash: Optional[str] = None):
        self._geometry_hash = geometry_hash
        self._calibration_hash = calibration_hash
        self._dead_channels: Set[int] = set()
    
    def set_dead_channels(self, channels: List[int]) -> None:
        """Set list of dead channels for validation."""
        self._dead_channels = set(channels)
    
    def validate_simgb(self, simgb: Dict[str, Any]) -> List[ValidationError]:
        """
        Validate a State Image Bundle against expected hardware config.
        
        Checks:
        - geometry_hash matches expected
        - calibration.hash matches expected (if calibration present)
        """
        errors: List[ValidationError] = []
        
        # Check geometry hash
        if self._geometry_hash is not None:
            actual_hash = simgb.get("geometry_hash", "")
            if actual_hash != self._geometry_hash:
                errors.append(ValidationError(
                    code=KleinErrorCode.SIMGB_GEOMETRY_MISMATCH,
                    message=f"Geometry hash mismatch: expected {self._geometry_hash}, got {actual_hash}",
                    detail={"expected": self._geometry_hash, "actual": actual_hash},
                ))
        
        # Check calibration hash
        if self._calibration_hash is not None:
            calibration = simgb.get("calibration", {})
            actual_cal_hash = calibration.get("hash", "")
            if actual_cal_hash and actual_cal_hash != self._calibration_hash:
                errors.append(ValidationError(
                    code=KleinErrorCode.SIMGB_CALIBRATION_MISMATCH,
                    message=f"Calibration hash mismatch: expected {self._calibration_hash}, got {actual_cal_hash}",
                    detail={"expected": self._calibration_hash, "actual": actual_cal_hash},
                ))
        
        return errors
    
    def validate_payload_electrode(self, electrode_id: int) -> Optional[ValidationError]:
        """Check if an electrode is dead."""
        if electrode_id in self._dead_channels:
            return ValidationError(
                code=KleinErrorCode.CHANNEL_DEAD,
                message=f"Electrode {electrode_id} is marked as dead in SImgB",
                detail={"electrode_id": electrode_id},
            )
        return None


# =============================================================================
# Virtual Substrate
# =============================================================================

class VirtualSubstrate(MockSubstrate):
    """
    Full-featured virtual substrate for simulation and conformance testing.
    
    Extends MockSubstrate with:
    - Droplet position tracking
    - Simulated impedance sensing
    - Stuck droplet detection
    - Container/SImgB validation
    - Error code emission for negative tests
    """
    
    def __init__(
        self,
        max_channels: int = 128,
        grid_width: int = 16,
        grid_height: int = 8,
        seed: int = 42,
        stuck_probability: float = 0.0,  # Probability of droplet getting stuck per move
        topology: Optional[ElectrodeTopology] = None,
        capabilities: Optional[CapabilityProfile] = None,
    ):
        # Build grid topology if not provided
        if topology is None:
            topology = self._build_grid_topology(max_channels, grid_width, grid_height)
        
        # Build capabilities with sensing enabled
        if capabilities is None:
            capabilities = CapabilityProfile(
                device_vendor="klein-sim",
                device_model="VirtualSubstrate",
                firmware="1.0.0",
                max_channels=max_channels,
                addressing=AddressingMode.DIRECT,
                supports_groups=True,
                waveforms=(WaveformMode.DC, WaveformMode.AC),
                voltage_range=VoltageRange(v_min=0.0, v_max=300.0),
                ac_frequency_range=FrequencyRange(hz_min=1.0, hz_max=50_000.0),
                timing=TimingProfile(min_frame_ms=5, typical_jitter_ms=1, max_schedule_horizon_ms=5000),
                sensing=SensingProfile(impedance=True, vision=False, electrode_feedback=True),
                safety_estop=True,
                safety_overcurrent_protection=True,
            )
        
        super().__init__(
            max_channels=max_channels,
            topology=topology,
            capabilities=capabilities,
        )
        
        self._seed = seed
        self._rng = random.Random(seed)
        self._stuck_probability = stuck_probability
        
        # Droplet state
        self._droplet_state = DropletState()
        
        # Sensing
        self._sensor = SensorSimulator(seed=seed)
        
        # Validation
        self._validator = ContainerValidator()
        
        # Error injection for negative tests
        self._pending_errors: List[ValidationError] = []
        
        # Grid dimensions for position mapping
        self._grid_width = grid_width
        self._grid_height = grid_height
    
    def _build_grid_topology(
        self,
        max_channels: int,
        width: int,
        height: int,
    ) -> ElectrodeTopology:
        """Build a grid topology with proper adjacency."""
        electrodes = []
        adjacency: Dict[int, Tuple[int, ...]] = {}
        
        for i in range(min(max_channels, width * height)):
            x = i % width
            y = i // width
            electrodes.append(Electrode(eid=i, label=f"E{i}", x=float(x), y=float(y)))
            
            # Build adjacency (4-connected grid)
            neighbors = []
            if x > 0:
                neighbors.append(i - 1)  # left
            if x < width - 1:
                neighbors.append(i + 1)  # right
            if y > 0:
                neighbors.append(i - width)  # up
            if y < height - 1:
                neighbors.append(i + width)  # down
            adjacency[i] = tuple(neighbors)
        
        return ElectrodeTopology(
            electrodes=tuple(electrodes),
            adjacency=adjacency,
            cartridge_id="VIRTUAL-GRID",
        )
    
    # -------------------------------------------------------------------------
    # Droplet Management
    # -------------------------------------------------------------------------
    
    def spawn_droplet(self, droplet_id: str, electrode_id: int, volume_nl: float = 1000.0) -> None:
        """Spawn a droplet at a specific electrode."""
        droplet = Droplet(id=droplet_id, electrode_id=electrode_id, volume_nl=volume_nl)
        self._droplet_state.add_droplet(droplet)
    
    def get_droplet_positions(self) -> Dict[str, int]:
        """Get current positions of all droplets."""
        return {
            droplet.id: droplet.electrode_id
            for droplet in self._droplet_state.droplets.values()
        }
    
    def get_occupancy_map(self) -> Dict[int, bool]:
        """Get electrode occupancy map."""
        return {
            eid: eid in self._droplet_state.electrode_occupancy
            for eid in range(self._cap.max_channels)
        }
    
    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------
    
    def configure_validation(
        self,
        geometry_hash: Optional[str] = None,
        calibration_hash: Optional[str] = None,
        dead_channels: Optional[List[int]] = None,
    ) -> None:
        """Configure validation parameters for SImgB checking."""
        self._validator = ContainerValidator(
            geometry_hash=geometry_hash,
            calibration_hash=calibration_hash,
        )
        if dead_channels:
            self._validator.set_dead_channels(dead_channels)
    
    def validate_simgb(self, simgb: Dict[str, Any]) -> List[ValidationError]:
        """Validate a SImgB bundle. Returns list of errors (empty if valid)."""
        return self._validator.validate_simgb(simgb)
    
    def inject_error(self, error: ValidationError) -> None:
        """Inject an error to be reported on next frame."""
        self._pending_errors.append(error)
    
    # -------------------------------------------------------------------------
    # Frame Application (Extended)
    # -------------------------------------------------------------------------
    
    def apply_frame(self, frame: Frame) -> Ack:
        """
        Apply a frame with droplet physics simulation.
        
        Extends MockSubstrate.apply_frame with:
        - Droplet movement based on activated electrodes
        - Stuck droplet detection
        - Impedance-based observations
        """
        # Check for pending validation errors
        if self._pending_errors:
            error = self._pending_errors.pop(0)
            fault = Fault(
                code=FaultCode.OVERRIDE,
                message=error.message,
                detail={"klein_error_code": error.code.value, **error.detail},
            )
            return Ack(seq=frame.seq, ok=False, faults=(fault,))
        
        # Check dead channels
        for eid in frame.active_electrodes:
            channel_error = self._validator.validate_payload_electrode(eid)
            if channel_error:
                fault = Fault(
                    code=FaultCode.CHANNEL_UNAVAILABLE,
                    message=channel_error.message,
                    detail={"klein_error_code": channel_error.code.value, **channel_error.detail},
                )
                return Ack(seq=frame.seq, ok=False, faults=(fault,))
        
        # Run base frame application (timing, bounds checks, fault injection)
        ack = super().apply_frame(frame)
        if not ack.ok:
            return ack
        
        # Simulate droplet physics
        stuck_droplets = self._simulate_droplet_movement(frame)
        
        # Generate impedance observations
        self._generate_impedance_observations(frame)
        
        # Report stuck droplets as partial success
        if stuck_droplets:
            return Ack(
                seq=frame.seq,
                ok=True,  # Frame applied, but with warning
                faults=(),
                detail={
                    "time_ms": self._time_ms,
                    "stuck_droplets": stuck_droplets,
                    "warning": "DROPLET_STUCK",
                },
            )
        
        return ack
    
    def _simulate_droplet_movement(self, frame: Frame) -> List[str]:
        """
        Simulate droplet movement based on activated electrodes.
        
        Simple model: droplets move toward activated adjacent electrodes.
        
        Returns:
            List of droplet IDs that are stuck
        """
        stuck_droplets: List[str] = []
        active_set = set(frame.active_electrodes)
        
        for droplet in list(self._droplet_state.droplets.values()):
            if droplet.stuck:
                stuck_droplets.append(droplet.id)
                continue
            
            current_electrode = droplet.electrode_id
            
            # Find activated adjacent electrode
            neighbors = self._topology.adjacency.get(current_electrode, ())
            target = None
            for neighbor in neighbors:
                if neighbor in active_set:
                    target = neighbor
                    break
            
            if target is not None:
                # Random stuck check
                if self._stuck_probability > 0 and self._rng.random() < self._stuck_probability:
                    self._droplet_state.mark_stuck(droplet.id, frame.seq)
                    stuck_droplets.append(droplet.id)
                else:
                    # Try to move
                    success = self._droplet_state.move_droplet(droplet.id, target)
                    if not success:
                        # Collision or stuck
                        self._droplet_state.mark_stuck(droplet.id, frame.seq)
                        stuck_droplets.append(droplet.id)
        
        return stuck_droplets
    
    def _generate_impedance_observations(self, frame: Frame) -> None:
        """Generate impedance observations for active electrodes."""
        for eid in frame.active_electrodes:
            reading = self._sensor.read_impedance(
                electrode_id=eid,
                droplet_state=self._droplet_state,
                timestamp_ms=self._time_ms,
            )
            
            obs = Observation(
                seq=frame.seq,
                time_ms=self._time_ms,
                source=ObservationSource.IMPEDANCE,
                signals={
                    "electrode_id": eid,
                    "impedance_ohms": reading.impedance_ohms,
                    "occupied": reading.occupied,
                },
            )
            self._observations.append(obs)
    
    # -------------------------------------------------------------------------
    # Sensing API
    # -------------------------------------------------------------------------
    
    def read_impedance_map(self) -> Dict[int, float]:
        """Read impedance values for all electrodes."""
        result = {}
        for eid in range(self._cap.max_channels):
            reading = self._sensor.read_impedance(
                electrode_id=eid,
                droplet_state=self._droplet_state,
                timestamp_ms=self._time_ms,
            )
            result[eid] = reading.impedance_ohms
        return result
    
    def detect_droplet_positions(self) -> List[int]:
        """Detect which electrodes have droplets (via simulated impedance)."""
        occupied = []
        for eid in range(self._cap.max_channels):
            reading = self._sensor.read_impedance(
                electrode_id=eid,
                droplet_state=self._droplet_state,
                timestamp_ms=self._time_ms,
            )
            if reading.occupied:
                occupied.append(eid)
        return occupied
    
    # -------------------------------------------------------------------------
    # Reset
    # -------------------------------------------------------------------------
    
    def reset(self) -> None:
        """Reset substrate state including droplets."""
        super().reset()
        self._droplet_state.clear()
        self._pending_errors.clear()
        self._rng = random.Random(self._seed)
