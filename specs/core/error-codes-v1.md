# Error Codes v1

Klein Core v1 reports protocol failures with explicit codes. Negative conformance vectors pass
only when the observed code matches the expected code.

## Vector And Golden Errors

- `VECTOR_INDEX_INVALID`: malformed `tests/vectors/v1/index.json`
- `VECTOR_METADATA_INVALID`: malformed `vector.json`
- `VECTOR_INPUT_MISSING`: declared v1 input artifact is absent
- `VECTOR_GOLDEN_MISSING`: positive v1 vector has no golden HAIL stream
- `VECTOR_EVIDENCE_ASSERTION_FAILED`: a negative vector's required evidence assertion was not observed
- `HAIL_GOLDEN_SCHEMA_INVALID`: golden HAIL JSONL is malformed or not strict HAIL v1

## Artifact Errors

- `ARTIFACT_JSON_INVALID`: project/container artifact is not valid JSON
- `ARTIFACT_INVALID`: artifact root or content cannot be processed as a Klein artifact
- `ARTIFACT_SCHEMA_INVALID`: artifact JSON does not match the expected core model
- `ARTIFACT_KIND_MISSING`: canonical artifact is missing its kind discriminator
- `ARTIFACT_UNSUPPORTED_KIND`: artifact kind is unknown or not supported by v1 alpha
- `ARTIFACT_UNSUPPORTED_VERSION`: artifact schema/container version is unknown or unsupported
- `ARTIFACT_PROFILE_MISSING`: canonical artifact is missing required profile metadata
- `ARTIFACT_PROFILE_MISMATCH`: artifact profile metadata is unsupported for the embedded payload
- `ARTIFACT_PAYLOAD_MISSING`: project/container payload is required but absent
- `ARTIFACT_PAYLOAD_INVALID`: project/container payload structure is invalid before profile validation
- `ARTIFACT_HASH_MISMATCH`: a declared artifact hash does not match the canonical artifact hash
- `RUNBOOK_INVALID`: Runbook v1 artifact cannot be processed
- `RUNBOOK_SCHEMA_INVALID`: Runbook v1 JSON shape or ordering is invalid
- `RUNBOOK_ARTIFACT_MISMATCH`: Runbook source artifact binding is unsupported or inconsistent
- `RUNBOOK_PROFILE_MISMATCH`: Runbook profile metadata is missing or inconsistent
- `TRACE_INVALID`: Execution Trace v1 artifact cannot be processed
- `TRACE_SCHEMA_INVALID`: Execution Trace v1 JSON shape or ordering is invalid
- `TRACE_RUNBOOK_MISMATCH`: trace step tick or operation differs from the referenced runbook step
- `TRACE_STEP_MISSING`: trace references a missing runbook step or omits a planned step
- `TRACE_STEP_ORDER_INVALID`: runbook or trace steps are not in canonical order
- `TRACE_STATUS_INVALID`: trace step status/issued/applied/error fields are inconsistent
- `ECRP_POLICY_INVALID`: ECRP policy is internally inconsistent
- `ECRP_POLICY_SCHEMA_INVALID`: ECRP policy JSON shape is not ECRP Policy v1
- `ECRP_STRATEGY_UNKNOWN`: ECRP policy or attempt names an unknown strategy
- `ECRP_STRATEGY_NOT_ALLOWED`: ECRP attempt strategy is not allowed by policy
- `ECRP_ATTEMPTS_EXCEEDED`: ECRP attempt count exceeds policy `max_attempts`
- `ECRP_ATTEMPT_SEQUENCE_INVALID`: ECRP attempt numbers are missing or non-contiguous
- `ECRP_TERMINAL_FAILURE_MISSING`: required terminal failure evidence is absent
- `ECRP_REPLAN_NOT_ALLOWED`: policy or trace uses replan where mode/policy forbids it
- `ECRP_TRACE_EVIDENCE_MISSING`: trace lacks required recovery/failure evidence
- `ECRP_SUCCESS_NOT_SUPPORTED`: ECRP success is claimed where current policy does not support it
- `ECRP_RECOVERY_SUCCESS_NOT_ALLOWED`: recovery success is claimed but policy does not permit it
- `ECRP_RECOVERY_EVIDENCE_MISSING`: recovery success lacks required failed-step or retry evidence
- `ECRP_RECOVERY_TRACE_INVALID`: recovery trace shape is invalid for the claimed recovery
- `ECRP_RECOVERY_STRATEGY_NOT_ALLOWED`: recovery success uses a strategy not allowed for success
- `ECRP_RECOVERY_UNSUPPORTED`: requested recovery behavior is outside current alpha support
- `ECRP_RETRY_STEP_MISSING`: recovery retry is not tied to a runbook step
- `OBSERVATION_POLICY_INVALID`: observation policy is internally inconsistent
- `OBSERVATION_POLICY_SCHEMA_INVALID`: observation policy JSON shape is invalid
- `OBSERVATION_SNAPSHOT_INVALID`: observation snapshot is invalid
- `OBSERVATION_SCHEMA_INVALID`: observation snapshot JSON shape is invalid
- `OBSERVATION_SOURCE_UNSUPPORTED`: observation source is not supported in CURRENT_ALPHA
- `OBSERVATION_ATTESTATION_UNSUPPORTED`: observation carries attestation where unsupported
- `OBSERVATION_CONFIDENCE_INVALID`: observation confidence is outside `[0, 1]`
- `OBSERVATION_TRACE_MISMATCH`: observation does not align with the declared trace step
- `OBSERVATION_RUNBOOK_MISMATCH`: observation does not align with the declared runbook step
- `OBSERVATION_REQUIRED_MISSING`: required observation evidence is absent
- `OBSERVATION_DMF_STATE_INVALID`: DMF observation state is malformed or outside context
- `HIL_CONTRACT_INVALID`: HIL backend contract content is internally inconsistent
- `HIL_CONTRACT_SCHEMA_INVALID`: HIL backend contract JSON shape is invalid
- `HIL_OPERATION_UNSUPPORTED`: HIL readiness contract omits a required operation
- `HIL_ESTOP_REQUIRED`: HIL readiness contract lacks required emergency-stop semantics
- `HIL_ATTESTATION_UNSUPPORTED`: HIL readiness or capability declaration claims unsupported attestation
- `HIL_STATUS_INVALID`: HIL backend status content is internally inconsistent
- `HIL_STATUS_SCHEMA_INVALID`: HIL backend status JSON shape is invalid
- `HIL_FAULT_MISSING_ERROR`: FAULTED HIL status omits `last_error_code`
- `HIL_HARDWARE_CLAIM_UNSUPPORTED`: current alpha rejected a hardware execution, hardware sensor, HIL-L1, or hardware attestation claim
- `RECORDED_RUN_INVALID`: Recorded Device Run v1 archive index or package cannot be processed
- `RECORDED_RUN_SCHEMA_INVALID`: Recorded Device Run v1 JSON shape is invalid
- `RECORDED_RUN_HARDWARE_CLAIM_UNSUPPORTED`: current alpha rejected a recorded-run hardware source or hardware claim
- `RECORDED_RUN_ATTESTATION_UNSUPPORTED`: current alpha rejected recorded-run attestation metadata
- `RECORDED_RUN_TIMESTAMP_UNSUPPORTED`: current alpha rejected recorded-run trusted timestamp metadata
- `RECORDED_RUN_BUNDLE_MISSING`: recorded run references a missing `.kcprun` bundle
- `RECORDED_RUN_BUNDLE_INVALID`: referenced `.kcprun` bundle hash or optional verification failed
- `RAW_DEVICE_LOG_INVALID`: Raw Device Log v1 cannot be parsed or processed
- `RAW_DEVICE_LOG_SCHEMA_INVALID`: Raw Device Log v1 event shape is invalid
- `RAW_DEVICE_LOG_ORDER_INVALID`: raw log `event_index` values are not strictly monotonic
- `RAW_DEVICE_LOG_ERROR_CODE_MISSING`: raw log `ERROR` event omits `error_code`
- `RAW_DEVICE_LOG_HASH_MISMATCH`: packaged raw log bytes do not match the declared hash
- `DMF_ADAPTER_CONFIG_INVALID`: DMF backend adapter config is internally inconsistent
- `DMF_ADAPTER_SCHEMA_INVALID`: DMF backend adapter config shape is invalid
- `DMF_ADAPTER_HARDWARE_IO_UNSUPPORTED`: current alpha rejected hardware IO or hardware mode
- `DMF_ADAPTER_PROFILE_UNSUPPORTED`: DMF backend adapter config does not target `dmf/v1`
- `DMF_ADAPTER_ESTOP_REQUIRED`: DMF backend adapter config lacks required emergency-stop semantics
- `DMF_ADAPTER_STATUS_INVALID`: DMF backend adapter status is invalid
- `DMF_ADAPTER_DRY_RUN_FAILED`: dry-run adapter execution failed
- `DMF_ADAPTER_ESTOP_ACTIVE`: dry-run adapter execution was blocked by emergency stop
- `DMF_ADAPTER_RECORDING_FAILED`: adapter-generated recorded-run package creation failed
- `OPENDROP_ADAPTER_CONFIG_INVALID`: OpenDrop/EWOD adapter config is internally inconsistent
- `OPENDROP_ADAPTER_SCHEMA_INVALID`: OpenDrop/EWOD adapter config/status shape is invalid
- `OPENDROP_TRANSPORT_CONFIG_INVALID`: OpenDrop transport planning config is internally inconsistent
- `OPENDROP_TRANSPORT_SCHEMA_INVALID`: OpenDrop transport planning config shape is invalid
- `OPENDROP_HARDWARE_IO_UNSUPPORTED`: current alpha rejected OpenDrop hardware IO or hardware mode
- `OPENDROP_TRANSPORT_UNSUPPORTED`: current alpha rejected OpenDrop USB/serial/network transport
- `OPENDROP_ENDPOINT_UNSUPPORTED_CURRENT_ALPHA`: current alpha rejected an OpenDrop endpoint or baud-rate hardware transport setting
- `OPENDROP_MAPPING_INVALID`: OpenDrop/EWOD electrode mapping is invalid
- `OPENDROP_MAPPING_DUPLICATE`: OpenDrop/EWOD mapping repeats a channel, electrode, or coordinate
- `OPENDROP_CHANNEL_OOB`: OpenDrop/EWOD command or mapping references an out-of-range channel
- `OPENDROP_COMMAND_INTENT_INVALID`: OpenDrop/EWOD command intent shape is invalid
- `OPENDROP_SERIAL_COMMAND_INVALID`: OpenDrop serial-command planning artifact is invalid
- `OPENDROP_SERIALIZATION_FAILED`: OpenDrop command-intent serialization failed
- `OPENDROP_DRY_RUN_FAILED`: OpenDrop/EWOD dry-run adapter execution failed
- `OPENDROP_RECORDING_FAILED`: OpenDrop/EWOD adapter-generated recorded-run package creation failed
- `TIMESTAMP_PROFILE_INVALID`: timestamp profile content is internally inconsistent
- `TIMESTAMP_PROFILE_SCHEMA_INVALID`: timestamp profile JSON shape is invalid
- `TIMESTAMP_TOKEN_INVALID`: timestamp token content is internally inconsistent
- `TIMESTAMP_TOKEN_SCHEMA_INVALID`: timestamp token JSON shape is invalid
- `TIMESTAMP_TRUSTED_TIME_UNSUPPORTED`: current alpha rejected a trusted-time claim
- `TIMESTAMP_TSA_UNSUPPORTED`: current alpha rejected a TSA/external time authority token or profile
- `TIMESTAMP_TARGET_HASH_MISMATCH`: timestamp token does not bind to the expected target hash
- `TIMESTAMP_TIME_INVALID`: timestamp token `claimed_time` is not parseable UTC/Z time
- `TIMESTAMP_SIGNATURE_UNSUPPORTED`: current-alpha mock/local timestamp token carried a signature
- `ATTESTATION_PROFILE_INVALID`: attestation profile content is internally inconsistent
- `ATTESTATION_PROFILE_SCHEMA_INVALID`: attestation profile JSON shape is invalid
- `ATTESTATION_STATEMENT_INVALID`: attestation statement content is internally inconsistent
- `ATTESTATION_STATEMENT_SCHEMA_INVALID`: attestation statement JSON shape is invalid
- `ATTESTATION_HARDWARE_UNSUPPORTED`: current alpha rejected a hardware attestation claim
- `ATTESTATION_HARDWARE_ROOT_UNSUPPORTED`: current alpha rejected hardware root metadata
- `ATTESTATION_QUOTE_UNSUPPORTED`: current alpha rejected attestation quote material
- `ATTESTATION_SIGNATURE_UNSUPPORTED`: current-alpha none/mock attestation statement carried a signature
- `ATTESTATION_SUBJECT_HASH_MISMATCH`: attestation statement does not bind to the expected subject hash
- `ATTESTATION_BACKEND_MISMATCH`: attestation statement does not bind to the expected backend id

## HAIL Errors

- `HAIL_JSON_INVALID`: HAIL JSONL input line is not valid JSON
- `HAIL_SCHEMA_INVALID`: HAIL event is not strict HAIL v1
- `HAIL_CHAIN_MISSING`: lifecycle stream has `RUN_END` without required chain fields
- `HAIL_CHAIN_MISMATCH`: computed HAIL chain digest does not match `RUN_END`
- `HAIL_CHAIN_INVALID`: HAIL chain verification failed for structural/order reasons
- `HAIL_RUN_END_MISSING`: chain verification expected a lifecycle close event but no `RUN_END` was present
- `HAIL_LIFECYCLE_INCOMPLETE`: execution evidence is missing required lifecycle binding

## Run Manifest And Trust Policy Errors

- `RUN_MANIFEST_INVALID`: manifest or source HAIL cannot be processed as Run Manifest v1 evidence
- `RUN_MANIFEST_SCHEMA_INVALID`: manifest JSON shape is not Run Manifest v1
- `RUN_MANIFEST_SIGNATURE_MISSING`: manifest has no signatures
- `RUN_MANIFEST_SIGNATURE_INVALID`: Ed25519 signature verification failed
- `RUN_MANIFEST_PAYLOAD_MISMATCH`: manifest payload does not match supplied lifecycle HAIL
- `RUN_MANIFEST_LIFECYCLE_MISSING`: source HAIL lacks the required lifecycle events
- `RUN_MANIFEST_CHAIN_INVALID`: source HAIL chain verification failed before manifest verification
- `BACKEND_IDENTITY_REGISTRY_INVALID`: backend identity registry JSON cannot be parsed or processed
- `BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID`: backend identity registry JSON shape is not Backend Identity Registry v1
- `BACKEND_IDENTITY_NOT_FOUND`: manifest backend is absent from the registry
- `BACKEND_IDENTITY_KEY_NOT_FOUND`: manifest signature key is absent from the registered backend
- `BACKEND_IDENTITY_KEY_MISMATCH`: manifest, policy, and registry public keys disagree
- `BACKEND_IDENTITY_KEY_REVOKED`: registry declares the signing key revoked
- `BACKEND_IDENTITY_KEY_RETIRED`: registry key is retired and cannot be accepted for this manifest
- `BACKEND_IDENTITY_KEY_EXPIRED`: manifest was created after the registry key validity window
- `BACKEND_IDENTITY_KEY_NOT_YET_VALID`: manifest was created before the registry key validity window
- `BACKEND_IDENTITY_KEY_ROTATION_INVALID`: registry key rotation metadata points to an invalid successor
- `BACKEND_IDENTITY_SCOPE_MISMATCH`: registry does not declare the manifest backend version or profile scope
- `BACKEND_IDENTITY_UNTRUSTED`: signature is valid but not authorized by the active trust policy
- `BACKEND_REGISTRY_SIGNATURE_INVALID`: signed registry signature verification failed
- `BACKEND_REGISTRY_SIGNATURE_MISSING`: signed registry has no usable signatures
- `BACKEND_REGISTRY_AUTHORITY_UNTRUSTED`: local Trust Policy does not trust the registry signing authority for this registry id
- `BACKEND_REGISTRY_PROVENANCE_REQUIRED`: strict verification required trusted signed registry provenance but it was absent or untrusted
- `BACKEND_REGISTRY_PAYLOAD_MISMATCH`: registry envelope payload and verified registry identity fields are inconsistent
- `BACKEND_CAPABILITY_DECLARATION_INVALID`: backend capability declaration JSON cannot be parsed or processed
- `BACKEND_CAPABILITY_SCHEMA_INVALID`: backend capability declaration shape is invalid
- `BACKEND_CAPABILITY_SIGNATURE_INVALID`: backend capability declaration signature verification failed
- `BACKEND_CAPABILITY_UNTRUSTED`: capability declaration signer is not locally trusted
- `BACKEND_CAPABILITY_SCOPE_MISMATCH`: capability declaration backend/version scope does not match the run
- `BACKEND_CAPABILITY_SUBSTRATE_MISMATCH`: run substrate fingerprint is not declared by the capability declaration
- `BACKEND_CAPABILITY_PROFILE_UNSUPPORTED`: run profile/version is not supported by the declaration
- `BACKEND_CAPABILITY_MODE_UNSUPPORTED`: run execution mode is not supported by the declaration
- `BACKEND_CAPABILITY_DMF_INVALID`: DMF profile capability content is internally invalid
- `BACKEND_CAPABILITY_REQUIRED`: strict verification required a backend capability declaration but none was supplied
- `DMF_CAPABILITIES_INVALID`: DMF/EWOD capability declaration content is internally invalid
- `DMF_PROFILE_UNSUPPORTED`: requested DMF profile capability set is unsupported
- `DMF_SUBSTRATE_MISMATCH`: declared DMF capabilities and substrate binding are incompatible
- `CONFORMANCE_LEVEL_CATALOG_INVALID`: conformance-level catalog shape, uniqueness, or evidence metadata is invalid
- `CONFORMANCE_LEVEL_UNKNOWN`: a declared or required conformance level id is not present in the catalog
- `CONFORMANCE_LEVEL_DEPENDENCY_MISSING`: a declared conformance level is missing a required dependency level
- `CONFORMANCE_LEVEL_CYCLE`: conformance-level dependency graph contains a cycle
- `CONFORMANCE_LEVEL_FUTURE_UNSUPPORTED`: a future-only conformance level was claimed as supported
- `CONFORMANCE_LEVEL_TARGET_UNSUPPORTED`: a target conformance level was claimed without explicitly enabling target claims
- `CONFORMANCE_LEVEL_CLAIM_INVALID`: conformance-level claim shape or policy is invalid
- `TRUST_POLICY_INVALID`: trust policy JSON cannot be parsed or processed
- `TRUST_POLICY_SCHEMA_INVALID`: trust policy JSON shape is not Trust Policy v1
- `TRUST_POLICY_KEY_NOT_FOUND`: valid signing key is absent from the trust policy
- `TRUST_POLICY_SCOPE_MISMATCH`: valid signing key is not authorized for the claimed backend/profile scope
- `TRUST_POLICY_KEY_REVOKED`: signing key appears in the policy revocation list

## Run Bundle Errors

- `RUN_BUNDLE_INVALID`: bundle JSON, directory, or archive cannot be processed as Run Bundle v1
- `RUN_BUNDLE_SCHEMA_INVALID`: `bundle.json` shape is not Run Bundle v1
- `RUN_BUNDLE_MISSING_ENTRY`: a required or declared bundle entry is absent
- `RUN_BUNDLE_HASH_MISMATCH`: a bundle entry raw SHA-256 hash does not match `bundle.json`
- `RUN_BUNDLE_PATH_TRAVERSAL`: zip member names include absolute or parent-traversal paths
- `RUN_BUNDLE_SIGNED_CONFORMANCE_FAILED`: bundle integrity passed but signed-conformance failed
- `RUN_BUNDLE_UNSUPPORTED_FORMAT`: bundle path is neither a directory nor canonical `.kcprun` archive

## Independent Verifier Errors

- `INDEPENDENT_VERIFIER_FAILED`: independent verifier could not complete the required contract
- `VERIFIER_BUNDLE_INVALID`: verifier-level bundle processing failed; prefer precise `RUN_BUNDLE_*` codes when available
- `VERIFIER_HAIL_INVALID`: verifier-level HAIL processing failed; prefer precise `HAIL_*` codes when available
- `VERIFIER_MANIFEST_INVALID`: verifier-level manifest processing failed; prefer precise `RUN_MANIFEST_*` codes when available
- `VERIFIER_TRUST_POLICY_INVALID`: verifier-level trust policy processing failed; prefer precise `TRUST_POLICY_*` codes when available
- `VERIFIER_BINDING_MISMATCH`: verifier-level evidence binding mismatch; prefer precise lower-level mismatch codes when available

## Payload Validation Errors

- `DDI_UNSUPPORTED_PAYLOAD`: unsupported payload kind
- `PAYLOAD_UNSUPPORTED_FRAME_FORMAT`: unsupported DMF v1 frame format or payload encoding
- `PAYLOAD_MALFORMED`: required payload field/type is invalid
- `PAYLOAD_CHANNEL_OOB`: channel id is outside substrate bounds
- `PAYLOAD_INVALID_STATE`: channel state is not `ON` or `OFF`
- `PAYLOAD_VOLTAGE_OOB`: voltage is outside declared substrate capability
- `PAYLOAD_FREQUENCY_OOB`: frequency is outside declared substrate capability
- `PAYLOAD_CONFLICTING_STATE`: same tick/channel declares conflicting states
- `PAYLOAD_OOB_PIXEL`: sparse/coordinate pixel maps outside substrate bounds
- `PAYLOAD_DUPLICATE_PIXEL`: sparse frame repeats an electrode
- `PAYLOAD_BASE64_INVALID`: bitmap payload is not valid base64

DMF/EWOD v1 alpha keeps established repository names for channel and base64 failures:
`PAYLOAD_CHANNEL_OOB` and `PAYLOAD_BASE64_INVALID`.
- `PAYLOAD_DELTA_CONFLICT`: delta frame adds and removes the same electrode
- `PAYLOAD_DELTA_REMOVE_MISS`: delta frame removes an electrode that is not active
- `PAYLOAD_UNSUPPORTED_DIMS`: bitmap expands beyond supported dimensions

## Execution Errors

- `CHANNEL_DEAD`: frame attempted to actuate a declared dead channel
- `ECRP_BOUNDS_EXCEEDED`: bounded ECRP attempts were exhausted before an attempt could run
- `ECRP_MISSING_EVIDENCE`: ECRP was invoked without required attempt evidence
- `SIMGB_GEOMETRY_MISMATCH`: SImgB geometry does not match declared substrate geometry
- `SIMGB_CALIBRATION_MISMATCH`: SImgB calibration does not match declared substrate calibration
- `SIMGB_HASH_MISMATCH`: SImgB hash does not match the declared artifact reference
- `RIMGB_SCHEMA_INVALID`: RImgB runtime-state evidence is not valid

Legacy aliases remain only for explicit legacy handling:

- `LCP_BOUNDS_EXCEEDED` -> `ECRP_BOUNDS_EXCEEDED`
- `LCP_MISSING_EVIDENCE` -> `ECRP_MISSING_EVIDENCE`
- `DSB_GEOMETRY_MISMATCH` -> `SIMGB_GEOMETRY_MISMATCH`
- `CALIBRATION_HASH_MISMATCH` -> `SIMGB_CALIBRATION_MISMATCH`
- `RSB_SCHEMA_INVALID` -> `RIMGB_SCHEMA_INVALID`

Strict v1 HAIL should emit `ECRP`, `SImgB`, and `RImgB` terminology.
