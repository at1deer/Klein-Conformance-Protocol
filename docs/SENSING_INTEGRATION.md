# Sensing and Vision Integration Guide (v3.0 Roadmap)

> Public-alpha note: this is target/future sensing roadmap material. Current alpha has
> simulator-backed Observation v1 snapshots, but it does not implement hardware sensor proof,
> sensor attestation, physical truth proof, trusted timestamps, or hardware attestation. For current
> claims, read `docs/CURRENT_ALPHA.md`.

This document describes the planned sensing and vision integration for Klein v3.0, including existing implementation hooks and future architecture.

---

## Executive Summary

Klein v3.0 will add **closed-loop feedback** via sensing channels, enabling:
- Real-time droplet tracking via camera
- Impedance-based presence detection
- Automatic error correction triggered by sensor mismatch
- Temperature and environmental monitoring

**Current status:** Schema and protocol hooks exist; no hardware sensing pipeline or sensor proof is
implemented in current alpha. Active implementation is planned for v3.0.

---

## Current State (v1.0)

Klein v1.0 includes schema and protocol hooks for sensing, but no active hardware implementation:

| Component | Location | Status |
|-----------|----------|--------|
| Sensing capability schema | `schemas/capabilities.schema.json` | Schema hook only |
| SensingProfile dataclass | `src/klein/substrate/api.py` | Planning hook only |
| ObservationSource enum | `src/klein/substrate/api.py` | Planning hook only |
| MEASUREMENT HAIL event | `schemas/hail_events.schema.json` | Schema only |
| read_observations() API | `src/klein/substrate/api.py` | Protocol hook only |

### Existing Code Hooks

#### 1. ObservationSource Enum

```python
# From src/klein/substrate/api.py
class ObservationSource(str, Enum):
    NONE = "none"           # No sensing
    CONTROLLER = "controller"  # Hardware telemetry only
    VISION = "vision"       # v3.0: Camera-based detection
    IMPEDANCE = "impedance" # v3.0: Capacitance sensing
```

#### 2. SensingProfile

```python
# From src/klein/substrate/api.py
@dataclass(frozen=True)
class SensingProfile:
    impedance: bool = False      # Has impedance sensing
    vision: bool = False         # Has camera
    electrode_feedback: bool = False  # Per-electrode voltage feedback
```

#### 3. Observation Dataclass

```python
# From src/klein/substrate/api.py
@dataclass(frozen=True)
class Observation:
    seq: int                    # Associated frame sequence
    time_ms: int               # Timestamp
    source: ObservationSource  # VISION, IMPEDANCE, etc.
    signals: Dict[str, Any]    # Sensor-specific data
```

---

## v3.0 Architecture

### Sensing Channel Types

From `schemas/capabilities.schema.json`:

```json
{
  "sensing": {
    "channels": [
      { "kind": "camera", "rate_hz": 30.0, "latency_ms": 50 },
      { "kind": "impedance", "rate_hz": 1000.0, "latency_ms": 5 },
      { "kind": "voltage", "rate_hz": 10000.0, "latency_ms": 1 },
      { "kind": "thermal", "rate_hz": 1.0, "latency_ms": 100 }
    ],
    "observables_supported": ["occupancy", "temperature", "impedance_map"],
    "observation_api": {
      "pull": true,
      "push": false,
      "timebase": "device_ticks"
    }
  }
}
```

| Channel Type | Purpose | Typical Rate | Use Case |
|--------------|---------|--------------|----------|
| `camera` | Droplet position/occupancy | 30 Hz | Visual tracking |
| `impedance` | Electrode capacitance | 1000 Hz | Presence detection |
| `voltage` | Actuation verification | 10000 Hz | Waveform monitoring |
| `thermal` | Temperature monitoring | 1 Hz | Environmental safety |

### Observation API Modes

| Mode | Description | Implementation |
|------|-------------|----------------|
| `pull` | Simulator polls `read_observations()` | Current design |
| `push` | Driver calls callback on new data | v3.0 addition |

---

## Implementation Roadmap

### Phase 1: Vision Integration (v3.0-alpha)

Basic droplet presence/absence detection per electrode.

#### VisionProcessor Interface

```python
from typing import Protocol
import numpy as np

class VisionProcessor(Protocol):
    """Interface for camera-based droplet detection."""
    
    def configure(self, topology: ElectrodeTopology) -> None:
        """Configure processor with electrode layout."""
        ...
    
    def process_frame(self, image: np.ndarray) -> dict[int, float]:
        """
        Process a camera frame.
        
        Returns:
            electrode_id -> occupancy confidence (0.0-1.0)
        """
        ...
    
    def get_mask(self) -> np.ndarray:
        """Return the electrode mask overlay."""
        ...
```

#### Example Implementation

```python
import cv2
import numpy as np

class OpenCVVisionProcessor:
    """Simple OpenCV-based droplet detector."""
    
    def __init__(self, electrode_mask_path: str):
        self.mask = cv2.imread(electrode_mask_path, cv2.IMREAD_GRAYSCALE)
        self.electrode_regions: dict[int, np.ndarray] = {}
        
    def configure(self, topology: ElectrodeTopology) -> None:
        # Map electrode IDs to pixel regions
        for electrode in topology.electrodes:
            if electrode.x is not None and electrode.y is not None:
                # Create region of interest for this electrode
                self.electrode_regions[electrode.eid] = self._create_roi(
                    electrode.x, electrode.y
                )
    
    def process_frame(self, image: np.ndarray) -> dict[int, float]:
        occupancy = {}
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Threshold for droplet detection (dark on light background)
        _, binary = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)
        
        for eid, roi in self.electrode_regions.items():
            # Calculate percentage of ROI that's "droplet"
            masked = cv2.bitwise_and(binary, binary, mask=roi)
            droplet_pixels = np.count_nonzero(masked)
            total_pixels = np.count_nonzero(roi)
            
            if total_pixels > 0:
                occupancy[eid] = droplet_pixels / total_pixels
            else:
                occupancy[eid] = 0.0
        
        return occupancy
```

### Phase 2: Droplet Tracking (v3.0-beta)

Persistent droplet identity across frames.

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class DropletState:
    """Tracked droplet state."""
    droplet_id: str           # Persistent identifier
    electrode_id: int         # Current location
    confidence: float         # Detection confidence
    velocity: tuple[float, float]  # Movement vector
    volume_estimate: float    # Estimated volume (nL)
    age_ticks: int           # Ticks since first detection


class DropletTracker:
    """Track droplets across frames with persistent IDs."""
    
    def __init__(self, max_distance: int = 2):
        self.droplets: dict[str, DropletState] = {}
        self.next_id = 0
        self.max_distance = max_distance  # Max electrode jump per frame
    
    def update(self, occupancy: dict[int, float], threshold: float = 0.7) -> list[DropletState]:
        """
        Update tracking with new occupancy data.
        
        Args:
            occupancy: electrode_id -> confidence
            threshold: Minimum confidence to consider occupied
            
        Returns:
            List of current droplet states
        """
        detected = {eid for eid, conf in occupancy.items() if conf >= threshold}
        
        # Match existing droplets to new positions
        matched: set[str] = set()
        for droplet_id, state in list(self.droplets.items()):
            # Find closest detected electrode
            candidates = [
                eid for eid in detected 
                if self._distance(state.electrode_id, eid) <= self.max_distance
            ]
            
            if candidates:
                # Update position to highest confidence match
                best = max(candidates, key=lambda e: occupancy[e])
                self.droplets[droplet_id] = DropletState(
                    droplet_id=droplet_id,
                    electrode_id=best,
                    confidence=occupancy[best],
                    velocity=self._compute_velocity(state.electrode_id, best),
                    volume_estimate=state.volume_estimate,
                    age_ticks=state.age_ticks + 1,
                )
                matched.add(droplet_id)
                detected.remove(best)
            else:
                # Droplet lost
                del self.droplets[droplet_id]
        
        # Create new droplets for unmatched detections
        for eid in detected:
            new_id = f"D{self.next_id}"
            self.next_id += 1
            self.droplets[new_id] = DropletState(
                droplet_id=new_id,
                electrode_id=eid,
                confidence=occupancy[eid],
                velocity=(0.0, 0.0),
                volume_estimate=1.0,  # Default 1nL
                age_ticks=0,
            )
        
        return list(self.droplets.values())
```

### Phase 3: ECRP Vision Triggers (v3.0-release)

Automatic error correction triggered by sensor mismatch.

```python
def check_occupancy_invariants(
    expected: set[int],
    observed: dict[int, float],
    threshold: float = 0.8,
) -> list[str]:
    """
    Compare expected vs observed occupancy.
    
    Args:
        expected: Electrodes where droplets should be
        observed: electrode_id -> observed confidence
        threshold: Confidence threshold for "present"
        
    Returns:
        List of violation descriptions triggering ECRP
    """
    violations = []
    
    # Check for missing droplets (expected but not observed)
    for eid in expected:
        if observed.get(eid, 0.0) < threshold:
            violations.append(f"MISSING_DROPLET_{eid}")
    
    # Check for unexpected droplets (observed but not expected)
    for eid, conf in observed.items():
        if eid not in expected and conf >= threshold:
            violations.append(f"UNEXPECTED_DROPLET_{eid}")
    
    return violations


class VisionTriggeredECRP:
    """ECRP with vision-based fault detection."""
    
    def __init__(self, vision: VisionProcessor, tracker: DropletTracker):
        self.vision = vision
        self.tracker = tracker
    
    def check_after_frame(
        self,
        expected_positions: set[int],
        camera_image: np.ndarray,
    ) -> tuple[bool, list[str]]:
        """
        Check if frame execution succeeded based on vision.
        
        Returns:
            (success, violations)
        """
        occupancy = self.vision.process_frame(camera_image)
        violations = check_occupancy_invariants(expected_positions, occupancy)
        
        return len(violations) == 0, violations
```

---

## Impedance Integration

### Use Cases

1. **Droplet detection** — Capacitance increases when droplet present
2. **Electrode health** — High impedance indicates fouling/damage
3. **Real-time feedback** — Sub-millisecond response for fast corrections

### Impedance Sensing Interface

```python
class ImpedanceSensor(Protocol):
    """Interface for impedance-based sensing."""
    
    def read_electrode(self, electrode_id: int) -> float:
        """Read impedance of single electrode in picofarads."""
        ...
    
    def read_all(self) -> dict[int, float]:
        """Read all electrode impedances."""
        ...
    
    def get_baseline(self) -> dict[int, float]:
        """Get baseline (no droplet) impedance values."""
        ...


def detect_presence_impedance(
    current: dict[int, float],
    baseline: dict[int, float],
    threshold_ratio: float = 1.5,
) -> dict[int, bool]:
    """
    Detect droplet presence via impedance change.
    
    Droplet increases capacitance (lowers impedance).
    
    Args:
        current: Current impedance readings
        baseline: Baseline (empty) readings
        threshold_ratio: Ratio above which droplet is considered present
        
    Returns:
        electrode_id -> is_occupied
    """
    presence = {}
    for eid, value in current.items():
        if eid in baseline:
            ratio = baseline[eid] / value  # Higher ratio = lower impedance = droplet
            presence[eid] = ratio >= threshold_ratio
    return presence
```

---

## HAIL Event Integration

### MEASUREMENT Events

Sensor readings are logged as MEASUREMENT events:

```python
def build_vision_measurement(
    t: int,
    run_id: str,
    occupancy: dict[int, float],
    frame_id: str,
) -> dict:
    """Build a vision MEASUREMENT event."""
    return {
        "kind": "MEASUREMENT",
        "t": t,
        "timebase": "DEVICE_TICKS",
        "run_id": run_id,
        "detector_id": "camera_0",
        "measurement_id": f"occupancy_{frame_id}",
        "value": {
            "type": "F64",
            "data": sum(occupancy.values()) / max(len(occupancy), 1),  # Avg confidence
        },
        "detail": {
            "occupied_electrodes": [eid for eid, c in occupancy.items() if c > 0.7],
            "electrode_confidences": occupancy,
        },
    }
```

### Vision-Triggered REPLAN_DECISION

```python
def build_vision_replan(
    t: int,
    run_id: str,
    checkpoint_id: str,
    violations: list[str],
    simgb_hash: str,
    rimgb_hash: str,
    seed: int,
) -> dict:
    """Build a vision-triggered REPLAN_DECISION event."""
    return {
        "kind": "REPLAN_DECISION",
        "t": t,
        "timebase": "DEVICE_TICKS",
        "run_id": run_id,
        "checkpoint_id": checkpoint_id,
        "reason": f"vision_violation: {violations[0]}",
        "solver_version": "klein-sim/1.0.0",
        "solver_mode": "GEODESIC",
        "seed": seed,
        "inputs_ref": {
            "simgb_hash": simgb_hash,
            "rimgb_hash": rimgb_hash,
            "observables_snapshot": {
                "trigger": "vision",
                "violations": violations,
            },
        },
    }
```

---

## Capabilities Schema Extensions

### Sensing Section

```json
{
  "sensing": {
    "observables_supported": [
      "occupancy",
      "droplet_tracking",
      "impedance_map",
      "temperature"
    ],
    "channels": [
      {
        "kind": "camera",
        "rate_hz": 30.0,
        "latency_ms": 50,
        "resolution": [1920, 1080],
        "fov_electrodes": 128
      },
      {
        "kind": "impedance",
        "rate_hz": 1000.0,
        "latency_ms": 5,
        "electrode_coverage": "all"
      }
    ],
    "observation_api": {
      "pull": true,
      "push": true,
      "timebase": "device_ticks",
      "buffer_depth": 100
    }
  }
}
```

### Extended SensingProfile

```python
@dataclass(frozen=True)
class SensingProfile:
    """Extended sensing profile for v3.0."""
    # Basic flags
    impedance: bool = False
    vision: bool = False
    electrode_feedback: bool = False
    
    # v3.0 extensions
    impedance_electrodes: tuple[int, ...] = ()  # Which electrodes have sensing
    impedance_threshold_pf: float = 10.0        # Capacitance threshold
    vision_camera_id: str | None = None         # Camera identifier
    vision_resolution: tuple[int, int] = (0, 0) # Camera resolution
    thermal_zones: int = 0                      # Number of thermal zones
```

---

## Test Vectors (Future)

| ID | Purpose | Category |
|----|---------|----------|
| 121 | MEASUREMENT event with camera occupancy | Positive |
| 122 | MEASUREMENT event with impedance reading | Positive |
| 123 | ECRP triggered by vision mismatch | Positive |
| 124 | Occupancy confidence within ENVELOPE tolerance | Positive |
| 125 | Vision-based REPLAN_DECISION | Positive |
| 126 | Camera latency exceeds max_schedule_horizon_ms | Negative |
| 127 | Impedance reading outside valid range | Negative |

---

## Migration Path

### From v1.0 (No Sensing)

1. Add `sensing` block to capabilities JSON
2. Implement `read_observations()` to return sensor data
3. Emit `MEASUREMENT` events in HAIL output
4. Update ECRP triggers to check sensor feedback

### From v2.0 (Hamiltonian)

1. Sensing data informs tensor field updates
2. Real-time impedance modifies edge weights
3. Coverage solver uses occupancy feedback for path planning

---

## Implementation Timeline

| Phase | Target | Features |
|-------|--------|----------|
| v3.0-alpha | Q2 2026 | Vision processor interface, basic occupancy |
| v3.0-beta | Q3 2026 | Droplet tracking, impedance integration |
| v3.0-release | Q4 2026 | Vision-triggered ECRP, full HAIL integration |

---

## References

- `schemas/capabilities.schema.json` — Sensing capability schema
- `schemas/hail_events.schema.json` — MEASUREMENT event schema
- `src/klein/substrate/api.py` — SubstrateDriver protocol
- `specs/klein_protocol_master.md` — HAIL event requirements
- [Hardware Integration Guide](HARDWARE_INTEGRATION.md) — Driver implementation
