"""
Klein Conformance Protocol - Pydantic v2 Models

Strict Pydantic models generated from the Klein JSON schemas.
These models enforce the Klein Conformance Protocol specification for:
- Backend capabilities negotiation
- State Image Bundles (SImgB)
- Project files (.klein)
- Package manifests
- Runbooks
- HAIL log events (Hardware Audit & Integrity Log)
- Trace artifacts
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# Base Configuration
# =============================================================================

class StrictModel(BaseModel):
    """Base model with strict validation enabled."""
    model_config = ConfigDict(strict=True, extra="forbid")


class StrictModelAllowExtra(BaseModel):
    """Base model with strict validation but allowing extra fields (forward compat)."""
    model_config = ConfigDict(strict=True, extra="allow")


# =============================================================================
# Capabilities Schema (capabilities.schema.json)
# =============================================================================

class CapabilitiesBackend(StrictModel):
    """Backend identification information."""
    name: str
    vendor: str
    firmware_id: str
    backend_version: str | None = None
    hardware_id: str | None = None
    commit: str | None = None


class CapabilitiesFingerprint(StrictModel):
    """Cryptographic hash of capabilities to prevent version mismatches."""
    algo: Literal["sha256"]
    value: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    inputs: list[str]


class CapabilitiesSupports(StrictModel):
    """Feature flags for gating conformance vectors."""
    envelope: bool
    diagnostic: bool
    checkpoint_replan: bool
    exact_jsonl_ordering: bool | None = None
    anisotropic_physics: bool | None = None  # RESERVED v2.0
    hamiltonian_solver: bool | None = None  # RESERVED v2.0


class SubstrateGrid(StrictModel):
    """Grid configuration for electrode topology."""
    rows: int | None = None
    cols: int | None = None
    pitch_um: int | None = None


class SubstrateElectrodes(StrictModel):
    """Electrode topology definition."""
    topology: Literal["grid", "irregular"]
    max_count: int
    coordinate_system: Literal["row_col", "xy_um", "vendor_defined"] | None = None
    grid: SubstrateGrid | None = None


class SubstrateAddressing(StrictModel):
    """Electrode addressing mode configuration."""
    mode: Literal["row_col", "linear_id", "direct"]
    maps: dict[str, Any] | None = None


class CapabilitiesSubstrate(StrictModel):
    """Physical topology definition for the Compiler."""
    kind: Literal["dmf", "continuous"]
    electrodes: SubstrateElectrodes
    addressing: SubstrateAddressing


class VoltageRange(StrictModel):
    """Voltage range specification."""
    min: float
    max: float
    step: float | None = None


class FrequencyRange(StrictModel):
    """Frequency range specification."""
    min: float | None = None
    max: float | None = None


class ActuationWaveforms(StrictModel):
    """Waveform configuration for actuation."""
    modes: list[Literal["AC", "DC"]] | None = None
    voltage_v: VoltageRange | None = None
    frequency_hz: FrequencyRange | None = None


class LatencySpec(StrictModel):
    """Latency specification."""
    p99: int | None = None
    max: int | None = None


class ActuationTiming(StrictModel):
    """Timing contract for actuation."""
    max_schedule_horizon_ms: int
    tick_resolution_ms: int | None = None
    min_frame_ms: int | None = None
    latency_ms: LatencySpec | None = None


class CapabilitiesActuation(StrictModel):
    """Electrical and timing contract."""
    waveforms: ActuationWaveforms
    timing: ActuationTiming


class SensingChannel(StrictModel):
    """Sensing channel specification."""
    kind: Literal["camera", "impedance", "voltage", "thermal"]
    rate_hz: float | None = None
    latency_ms: int | None = None


class ObservationAPI(StrictModel):
    """Observation API configuration."""
    pull: bool | None = None
    push: bool | None = None
    timebase: Literal["device_ticks", "host_time"] | None = None


class CapabilitiesSensing(StrictModel):
    """Available observables for the RImgB (Runtime Image Bundle)."""
    observables_supported: list[str] | None = None
    channels: list[SensingChannel] | None = None
    observation_api: ObservationAPI | None = None


class PrimitiveCapability(StrictModel):
    """Capability declaration for a primitive operation."""
    supported: bool
    guarantee: Literal["guaranteed", "best_effort", "advisory_only"]


class CapabilitiesFaults(StrictModel):
    """Fault detection capabilities."""
    model_config = ConfigDict(strict=True, extra="allow")
    
    detectable: list[str] | None = None
    inferable: list[str] | None = None
    codes_emitted: list[str] | None = None


class EnvelopeDimension(StrictModel):
    """Envelope dimension specification for tolerance bounds."""
    name: str
    max_error: float
    unit: str


class CompareExactJsonl(StrictModel):
    """Exact JSONL comparison configuration."""
    ordering: str | None = None


class CompareSet(StrictModel):
    """Set-based comparison configuration."""
    canonicalization_algo: str | None = None


class CompareEnvelope(StrictModel):
    """Envelope mode comparison configuration."""
    dimensions: list[EnvelopeDimension] | None = None


class CapabilitiesCompare(StrictModel):
    """Canonicalization rules for Conformance Verification."""
    exact_jsonl: CompareExactJsonl | None = None
    set: CompareSet | None = None
    envelope: CompareEnvelope | None = None


class Capabilities(StrictModel):
    """
    Klein Backend Capabilities Profile v0.1
    
    Normative schema for hardware driver negotiation, including v2.0 reserved 
    fields and safety contracts.
    """
    klein_capabilities_version: Literal["0.1"]
    backend: CapabilitiesBackend
    fingerprint: CapabilitiesFingerprint
    supports: CapabilitiesSupports
    substrate: CapabilitiesSubstrate
    actuation: CapabilitiesActuation
    compare: CapabilitiesCompare
    sensing: CapabilitiesSensing | None = None
    primitives: dict[str, PrimitiveCapability] | None = None
    faults: CapabilitiesFaults | None = None


# =============================================================================
# State Image Bundle Schema (simgb.schema.json) - formerly DSB
# =============================================================================

class SImgBCalibration(StrictModel):
    """Per-device calibration data."""
    model_config = ConfigDict(strict=True, extra="allow")
    
    hash: str
    map: dict[str, float]


class SImgBDefects(StrictModel):
    """Device defect information."""
    dead_channels: list[int]
    high_impedance_regions: list[int] | None = None


class StateImageBundle(StrictModel):
    """
    Klein State Image Bundle (SImgB)
    
    Static hardware definition used for compile-time routing and runtime verification.
    Formerly known as Device State Bundle (DSB).
    """
    device_id: str
    geometry_hash: str
    defects: SImgBDefects
    calibration: SImgBCalibration | None = None


# =============================================================================
# Klein Project File Schema (klein.schema.json)
# =============================================================================

class KleinMeta(StrictModel):
    """Project file metadata."""
    version: str
    target_substrate: str
    author: str | None = None
    resources: list[str] | None = None
    biosafety_level: Literal[1, 2, 3, 4] | None = Field(default=1)
    solver_mode: Literal["GEODESIC", "HAMILTONIAN"] | None = Field(default="GEODESIC")


PortDirection = Literal["North", "South", "East", "West", "Up", "Down"]


class KleinNode(StrictModel):
    """Graph node definition."""
    id: str
    type: str
    pos: Annotated[list[int], Field(min_length=3, max_length=3)]
    ports: dict[str, PortDirection] | None = None
    state: int | float | None = None


MetricTensor3x3 = Annotated[
    list[Annotated[list[float], Field(min_length=3, max_length=3)]],
    Field(min_length=3, max_length=3)
]


class KleinEdge(StrictModel):
    """Graph edge definition."""
    from_: str = Field(alias="from")
    to: str
    type: str
    from_port: str | None = None
    to_port: str | None = None
    impedance: float | None = None
    metric_tensor: MetricTensor3x3 | None = None  # RESERVED v2.0

    model_config = ConfigDict(strict=True, extra="forbid", populate_by_name=True)


class KleinField(StrictModel):
    """Scalar or tensor field definition."""
    type: str
    center: Annotated[list[float | int], Field(min_length=3, max_length=3)]
    strength: float
    radius: float | None = None
    tensor_components: list[float] | None = None  # RESERVED v2.0


class KleinProject(StrictModel):
    """
    Klein Project File (.klein)
    
    Defines the graph structure with nodes, edges, and optional fields for
    geodesic path computation.
    """
    meta: KleinMeta
    nodes: list[KleinNode]
    edges: list[KleinEdge]
    fields: list[KleinField] | None = None


# =============================================================================
# Manifest Schema (manifest.schema.json)
# =============================================================================

class ManifestProject(StrictModelAllowExtra):
    """Package project metadata (allows extra fields for forward compatibility)."""
    name: str
    version: str
    authors: list[str]
    license: str | None = Field(default="UNLICENSED")
    description: str | None = None


class ManifestRuntime(StrictModel):
    """Runtime execution configuration."""
    mode: Literal["HARD", "ENVELOPE", "DIAGNOSTIC"]
    target_substrate: str
    biosafety_level: Literal[1, 2, 3, 4] | None = Field(default=1)
    resources: list[str] | None = None


class Manifest(StrictModel):
    """
    Klein Package Manifest
    
    Top-level package configuration with project metadata and runtime settings.
    """
    project: ManifestProject
    runtime: ManifestRuntime


# =============================================================================
# Runbook Schema (runbook.schema.json)
# =============================================================================

class RunbookSegment(StrictModel):
    """A single segment in the runbook orchestration sequence."""
    id: str
    executable: str
    timeout_ms: int | None = None
    on_success: str | None = None
    on_failure: str | None = None
    required_capabilities: list[str] | None = None


class Runbook(StrictModel):
    """
    Klein Runbook
    
    Defines a high-level orchestration sequence for adaptive execution.
    """
    version: Literal["1.0"]
    segments: list[RunbookSegment]
    id: str | None = None
    timeout_global_ms: int | None = None


# =============================================================================
# HAIL Events Schema (hail_events.schema.json) - Hardware Audit & Integrity Log
# Formerly SCI Events
# =============================================================================

HAILEventKind = Literal[
    "RUN_START",
    "DEVICE_EVENT",
    "MEASUREMENT",
    "ECRP_ATTEMPT",      # Formerly LCP_ATTEMPT
    "REPLAN_DECISION",
    "RUNTIME_STATE_SNAPSHOT",
    "RUN_END",
]

Timebase = Literal["DEVICE_TICKS", "WALL_MS"]
ArtifactType = Literal["project", "container", "hail_jsonl", "invalid_artifact", "unknown"]
ArtifactCanonicalization = Literal["klein.canon.json.v1", "klein.canon.jsonl.v1", "raw-bytes"]
RunStatus = Literal["SUCCESS", "FAIL", "ERROR"]


class HAILEventBase(StrictModel):
    """Base class for all HAIL log events."""
    t: Annotated[int, Field(ge=0)]
    timebase: Timebase
    run_id: str


class RunStartEvent(HAILEventBase):
    """Run lifecycle start event binding execution evidence to declared inputs."""
    kind: Literal["RUN_START"]
    artifact_hash: str
    artifact_canonicalization: ArtifactCanonicalization
    artifact_type: ArtifactType
    profile_id: str
    profile_version: str
    backend_id: str
    backend_version: str
    mode: Literal["HARD", "ENVELOPE", "DIAGNOSTIC"]
    substrate_capabilities_hash: str | None = None
    substrate_topology_hash: str | None = None
    substrate_fingerprint: str | None = None
    substrate_fingerprint_canonicalization: str | None = None


class DeviceEvent(HAILEventBase):
    """Generic device event."""
    kind: Literal["DEVICE_EVENT"]
    code: str
    level: Literal["DEBUG", "INFO", "WARN", "ERROR"]
    message: str
    detail: dict[str, Any] | None = None


class MeasurementValue(StrictModel):
    """Measurement value container."""
    type: Literal["F64", "U32", "BOOL"]
    data: Any


class MeasurementEvent(HAILEventBase):
    """Measurement event from a detector."""
    kind: Literal["MEASUREMENT"]
    detector_id: str
    value: MeasurementValue
    op_id: str | None = None
    measurement_id: str | None = None


class ECRPAttemptEvent(HAILEventBase):
    """
    Error Correction & Recovery Protocol (ECRP) attempt event.
    Formerly known as LCP_ATTEMPT (Local Correction Protocol).
    """
    kind: Literal["ECRP_ATTEMPT"]
    attempt_index: Annotated[int, Field(ge=1)]
    strategy: str
    outcome: Literal["SUCCESS", "FAIL", "PARTIAL", "NO_CHANGE"]
    deltas: dict[str, Any]
    parameters: dict[str, Any] | None = None


class ReplanInputsRef(StrictModel):
    """References to state bundles used in replanning."""
    simgb_hash: str  # Formerly dsb_hash
    rimgb_hash: str  # Formerly rsb_hash
    observables_snapshot: dict[str, Any] | None = None


class ReplanDecisionEvent(HAILEventBase):
    """Replan decision event at a checkpoint."""
    kind: Literal["REPLAN_DECISION"]
    checkpoint_id: str
    reason: str
    solver_version: str
    seed: int
    inputs_ref: ReplanInputsRef
    solver_mode: Literal["GEODESIC", "HAMILTONIAN"] | None = Field(default="GEODESIC")


class ValidityWindow(StrictModel):
    """Time window for state validity."""
    start_t: Annotated[int, Field(ge=0)] | None = None
    end_t: Annotated[int, Field(ge=0)] | None = None


class RuntimeStateSnapshotEvent(HAILEventBase):
    """Runtime state snapshot event."""
    kind: Literal["RUNTIME_STATE_SNAPSHOT"]
    rimgb_hash: str  # Formerly rsb_hash
    validity_window: ValidityWindow
    state_fields: dict[str, Any] | None = None


class RunEndEvent(HAILEventBase):
    """Run lifecycle end event with pre-close HAIL stream digests."""
    kind: Literal["RUN_END"]
    status: RunStatus
    error_code: str | None = None
    preclose_hail_digest: str
    preclose_hail_canonicalization: Literal["klein.canon.jsonl.v1"]
    preclose_hail_chain_digest: str
    preclose_hail_chain_algorithm: Literal["klein.hail.chain.v1"]
    event_count_preclose: Annotated[int, Field(ge=0)]


# Discriminated union for HAIL events
HAILEvent = (
    RunStartEvent
    | DeviceEvent
    | MeasurementEvent
    | ECRPAttemptEvent
    | ReplanDecisionEvent
    | RuntimeStateSnapshotEvent
    | RunEndEvent
)


# =============================================================================
# Trace Schema (trace.schema.json)
# =============================================================================

class TickRange(StrictModel):
    """Tick range specification."""
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(ge=0)]


class ActuationRef(StrictModel):
    """Reference to a physical actuation."""
    channel_id: int
    tick_range: TickRange
    kind: Literal["ACTUATION", "SENSING"] | None = None


class TraceOp(StrictModel):
    """Logical operation within a plan."""
    op_id: str
    actuation_refs: Annotated[list[ActuationRef], Field(min_length=1)]


class TracePlan(StrictModel):
    """Logical plan containing operations."""
    plan_id: str
    ops: list[TraceOp]


class Trace(StrictModel):
    """
    Klein Trace Artifact
    
    Maps high-level logical plans/ops to low-level physical actuations.
    """
    trace_version: str
    tick_range: TickRange
    plans: list[TracePlan]


# =============================================================================
# Loose Manifest Format (Legacy Test Vectors)
# =============================================================================

class LooseManifestCalibration(StrictModelAllowExtra):
    """Calibration settings for loose manifests."""
    required: bool | None = None


class LooseManifestObservables(StrictModelAllowExtra):
    """Observable configuration for loose manifests."""
    declared: list[str]
    strictness: Literal["HARD", "ENVELOPE", "DIAGNOSTIC"] | None = None


class LooseManifestPayload(StrictModelAllowExtra):
    """Payload reference in loose manifests."""
    kind: str
    path: str
    digest: str | None = None


class LooseManifestRuntime(StrictModelAllowExtra):
    """Runtime configuration for loose manifests."""
    strict_mode: bool | None = None
    tick_ms: int | None = None
    ticks_per_meter: int | None = None


class LooseManifestSource(StrictModelAllowExtra):
    """Source provenance for loose manifests."""
    backend_profile: str
    klein_version: str | None = None  # Formerly kln_version
    source_digest: str | None = None
    decision_log_digest: str | None = None
    commit_profile: str | None = None


class LooseManifest(StrictModelAllowExtra):
    """
    Loose Manifest Format (Legacy)
    
    Used in test vector loose folders. Different structure from Container manifest.
    Allows extra fields for forward compatibility.
    """
    kap_version: str | None = None
    created_utc: str | None = None
    calibration: LooseManifestCalibration | None = None
    observables: LooseManifestObservables | None = None
    payloads: list[LooseManifestPayload] | None = None
    runtime: LooseManifestRuntime | None = None
    source: LooseManifestSource | None = None


# =============================================================================
# Container Schema (container.schema.json)
# =============================================================================

PayloadKind = Literal["CHANNEL_LIST", "FRAME_SEQUENCE", "BITMAP_SEQUENCE"]
PayloadEncoding = Literal["JSON", "BASE64_GZIP", "RLE"]


class ContainerPayload(StrictModel):
    """Payload containing actuation data (frames/instructions)."""
    kind: PayloadKind
    data: list[Any] | str
    encoding: PayloadEncoding | None = Field(default="JSON")


class Container(StrictModel):
    """
    Klein Compiled Container (.kleinc)
    
    A self-contained package bundling manifest, optional SImgB/runbook,
    and payload data for execution.
    """
    klein_container_version: Literal["1.0"]
    manifest: Manifest
    payload: ContainerPayload
    simgb: StateImageBundle | None = None  # Formerly dsb
    runbook: Runbook | None = None


# =============================================================================
# Type Aliases for Convenience
# =============================================================================

# New terminology
SImgB = StateImageBundle
RImgB = RuntimeStateSnapshotEvent  # Runtime Image Bundle is captured via events

# Legacy aliases (deprecated, for backwards compatibility)
DSB = StateImageBundle  # @deprecated: use SImgB
DeviceStateBundle = StateImageBundle  # @deprecated: use StateImageBundle
Kln = KleinProject  # @deprecated: use KleinProject
Klnc = Container  # @deprecated: use Container
SCIEvent = HAILEvent  # @deprecated: use HAILEvent
SCIEventKind = HAILEventKind  # @deprecated: use HAILEventKind
SCIEventBase = HAILEventBase  # @deprecated: use HAILEventBase
LCPAttemptEvent = ECRPAttemptEvent  # @deprecated: use ECRPAttemptEvent

__all__ = [
    # Base
    "StrictModel",
    "StrictModelAllowExtra",
    # Capabilities
    "Capabilities",
    "CapabilitiesBackend",
    "CapabilitiesFingerprint",
    "CapabilitiesSupports",
    "CapabilitiesSubstrate",
    "CapabilitiesActuation",
    "CapabilitiesSensing",
    "CapabilitiesCompare",
    "CapabilitiesFaults",
    "SubstrateElectrodes",
    "SubstrateAddressing",
    "SubstrateGrid",
    "ActuationWaveforms",
    "ActuationTiming",
    "VoltageRange",
    "FrequencyRange",
    "LatencySpec",
    "SensingChannel",
    "ObservationAPI",
    "PrimitiveCapability",
    "EnvelopeDimension",
    "CompareExactJsonl",
    "CompareSet",
    "CompareEnvelope",
    # State Image Bundle (SImgB) - formerly DSB
    "StateImageBundle",
    "SImgB",
    "SImgBCalibration",
    "SImgBDefects",
    # Legacy DSB aliases (deprecated)
    "DeviceStateBundle",
    "DSB",
    # Klein Project
    "KleinProject",
    "Kln",
    "KleinMeta",
    "KleinNode",
    "KleinEdge",
    "KleinField",
    "PortDirection",
    "MetricTensor3x3",
    # Manifest
    "Manifest",
    "ManifestProject",
    "ManifestRuntime",
    # Loose Manifest (Legacy)
    "LooseManifest",
    "LooseManifestCalibration",
    "LooseManifestObservables",
    "LooseManifestPayload",
    "LooseManifestRuntime",
    "LooseManifestSource",
    # Runbook
    "Runbook",
    "RunbookSegment",
    # HAIL Events (Hardware Audit & Integrity Log) - formerly SCI
    "HAILEvent",
    "HAILEventKind",
    "HAILEventBase",
    "Timebase",
    "RunStartEvent",
    "DeviceEvent",
    "MeasurementEvent",
    "MeasurementValue",
    "ECRPAttemptEvent",
    "ReplanDecisionEvent",
    "ReplanInputsRef",
    "RuntimeStateSnapshotEvent",
    "RunEndEvent",
    "ValidityWindow",
    # Legacy SCI aliases (deprecated)
    "SCIEvent",
    "SCIEventKind",
    "SCIEventBase",
    "LCPAttemptEvent",
    # Trace
    "Trace",
    "TracePlan",
    "TraceOp",
    "ActuationRef",
    "TickRange",
    # Container
    "Container",
    "Klnc",
    "ContainerPayload",
    "PayloadKind",
    "PayloadEncoding",
]
