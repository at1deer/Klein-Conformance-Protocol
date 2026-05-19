use base64::engine::general_purpose::STANDARD;
use base64::Engine;
use ed25519_dalek::{Signature, Verifier, VerifyingKey};
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};

use crate::canonical::{canonical_json, canonical_sha256_ref};
use crate::errors::{err, Result};
use crate::manifest::string_field;
use crate::registry::resolve_manifest_identity_with_policy;
use crate::trust_policy::authorize_with_registry_key;

pub struct CapabilityVerification {
    pub declaration_hash: String,
    pub signature_status: String,
    pub trust_status: String,
    pub scope_status: String,
}

pub fn verify_capability_declaration(
    declaration: &Value,
    registry: Option<&Value>,
    policy: Option<&Value>,
    manifest: Option<&Value>,
) -> Result<CapabilityVerification> {
    let payload = declaration
        .get("payload")
        .ok_or_else(|| err("BACKEND_CAPABILITY_SCHEMA_INVALID"))?;
    validate_payload(payload)?;
    validate_declared_levels(payload)?;
    verify_signature(declaration)?;
    let mut trust_status = "not_evaluated".to_string();
    if let (Some(registry), Some(policy)) = (registry, policy) {
        let pseudo_manifest = capability_manifest(declaration)?;
        let identity =
            resolve_manifest_identity_with_policy(registry, &pseudo_manifest, Some(policy))?;
        authorize_with_registry_key(policy, &pseudo_manifest, Some(&identity.public_key))?;
        trust_status = "trusted".to_string();
    }
    let mut scope_status = "not_evaluated".to_string();
    if let Some(manifest) = manifest {
        verify_scope(payload, manifest)?;
        scope_status = "pass".to_string();
    }
    Ok(CapabilityVerification {
        declaration_hash: canonical_sha256_ref(payload)?,
        signature_status: "valid".to_string(),
        trust_status,
        scope_status,
    })
}

fn validate_declared_levels(payload: &Value) -> Result<()> {
    let declared = strings(payload, "supported_conformance_levels");
    if declared.is_empty() {
        return Err(err("CONFORMANCE_LEVEL_CLAIM_INVALID"));
    }
    let declared_set: BTreeSet<String> = declared.iter().cloned().collect();
    if declared_set.len() != declared.len() {
        return Err(err("CONFORMANCE_LEVEL_CLAIM_INVALID"));
    }
    let levels = conformance_levels();
    for level_id in &declared {
        let Some(level) = levels.get(level_id.as_str()) else {
            return Err(err("CONFORMANCE_LEVEL_UNKNOWN"));
        };
        if level.status == "future" {
            return Err(err("CONFORMANCE_LEVEL_FUTURE_UNSUPPORTED"));
        }
        if level.status == "target" {
            return Err(err("CONFORMANCE_LEVEL_TARGET_UNSUPPORTED"));
        }
    }
    for level_id in &declared {
        let level = levels.get(level_id.as_str()).unwrap();
        for dependency in level.requires {
            if !declared_set.contains(*dependency) {
                return Err(err("CONFORMANCE_LEVEL_DEPENDENCY_MISSING"));
            }
        }
    }
    Ok(())
}

fn validate_payload(payload: &Value) -> Result<()> {
    for field in ["backend_id", "backend_version", "declaration_id"] {
        if string_field(payload, field).is_empty() {
            return Err(err("BACKEND_CAPABILITY_SCHEMA_INVALID"));
        }
    }
    let profiles = payload
        .get("supported_profiles")
        .and_then(Value::as_array)
        .ok_or_else(|| err("BACKEND_CAPABILITY_SCHEMA_INVALID"))?;
    if profiles.is_empty() {
        return Err(err("BACKEND_CAPABILITY_SCHEMA_INVALID"));
    }
    if let Some(dmf) = payload
        .get("profile_capabilities")
        .and_then(|v| v.get("dmf"))
    {
        validate_dmf(dmf)?;
    }
    Ok(())
}

fn validate_dmf(dmf: &Value) -> Result<()> {
    let addressing = dmf.get("addressing").unwrap_or(&Value::Null);
    if int_field(addressing, "max_channels") <= 0
        || int_field(addressing, "grid_width") <= 0
        || int_field(addressing, "grid_height") <= 0
    {
        return Err(err("DMF_CAPABILITIES_INVALID"));
    }
    let electrical = dmf.get("electrical").unwrap_or(&Value::Null);
    if number_field(electrical, "voltage_min_v") > number_field(electrical, "voltage_max_v")
        || number_field(electrical, "frequency_min_hz")
            > number_field(electrical, "frequency_max_hz")
    {
        return Err(err("DMF_CAPABILITIES_INVALID"));
    }
    let payloads = dmf.get("payloads").unwrap_or(&Value::Null);
    let supported = strings(payloads, "supported_frame_formats");
    let unsupported = strings(payloads, "unsupported_frame_formats");
    if supported.iter().any(|item| unsupported.contains(item)) {
        return Err(err("DMF_CAPABILITIES_INVALID"));
    }
    Ok(())
}

fn verify_signature(declaration: &Value) -> Result<()> {
    let payload = declaration
        .get("payload")
        .ok_or_else(|| err("BACKEND_CAPABILITY_SCHEMA_INVALID"))?;
    let signature = declaration
        .get("signatures")
        .and_then(Value::as_array)
        .and_then(|signatures| signatures.first())
        .ok_or_else(|| err("BACKEND_CAPABILITY_SIGNATURE_INVALID"))?;
    let public_key = STANDARD
        .decode(required_str(signature, "public_key")?)
        .map_err(|_| err("BACKEND_CAPABILITY_SIGNATURE_INVALID"))?;
    let signature_bytes = STANDARD
        .decode(required_str(signature, "signature")?)
        .map_err(|_| err("BACKEND_CAPABILITY_SIGNATURE_INVALID"))?;
    let public_key: [u8; 32] = public_key
        .try_into()
        .map_err(|_| err("BACKEND_CAPABILITY_SIGNATURE_INVALID"))?;
    let verifying_key = VerifyingKey::from_bytes(&public_key)?;
    let signature = Signature::from_slice(&signature_bytes)?;
    verifying_key
        .verify(canonical_json(payload)?.as_bytes(), &signature)
        .map_err(|_| err("BACKEND_CAPABILITY_SIGNATURE_INVALID"))?;
    Ok(())
}

fn verify_scope(payload: &Value, manifest: &Value) -> Result<()> {
    let run = manifest
        .get("payload")
        .ok_or_else(|| err("RUN_MANIFEST_SCHEMA_INVALID"))?;
    if string_field(payload, "backend_id") != string_field(run, "backend_id")
        || string_field(payload, "backend_version") != string_field(run, "backend_version")
    {
        return Err(err("BACKEND_CAPABILITY_SCOPE_MISMATCH"));
    }
    let profile_id = string_field(run, "profile_id");
    let profile_version = string_field(run, "profile_version");
    let profile_ok = payload
        .get("supported_profiles")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .any(|profile| {
            string_field(profile, "profile_id") == profile_id
                && strings(profile, "profile_versions").contains(&profile_version)
        });
    if !profile_ok {
        return Err(err("BACKEND_CAPABILITY_PROFILE_UNSUPPORTED"));
    }
    if !strings(payload, "supported_execution_modes").contains(&string_field(run, "mode")) {
        return Err(err("BACKEND_CAPABILITY_MODE_UNSUPPORTED"));
    }
    let fingerprint = string_field(run, "substrate_fingerprint");
    if !fingerprint.is_empty()
        && !payload
            .get("substrates")
            .and_then(Value::as_array)
            .into_iter()
            .flatten()
            .any(|substrate| string_field(substrate, "substrate_fingerprint") == fingerprint)
    {
        return Err(err("BACKEND_CAPABILITY_SUBSTRATE_MISMATCH"));
    }
    Ok(())
}

fn capability_manifest(declaration: &Value) -> Result<Value> {
    let payload = declaration
        .get("payload")
        .ok_or_else(|| err("BACKEND_CAPABILITY_SCHEMA_INVALID"))?;
    let signature = declaration
        .get("signatures")
        .and_then(Value::as_array)
        .and_then(|signatures| signatures.first())
        .ok_or_else(|| err("BACKEND_CAPABILITY_SIGNATURE_INVALID"))?;
    let profile = payload
        .get("supported_profiles")
        .and_then(Value::as_array)
        .and_then(|profiles| profiles.first())
        .ok_or_else(|| err("BACKEND_CAPABILITY_PROFILE_UNSUPPORTED"))?;
    Ok(serde_json::json!({
        "manifest_version": "klein.run_manifest.v1",
        "payload": {
            "backend_id": string_field(payload, "backend_id"),
            "backend_version": string_field(payload, "backend_version"),
            "profile_id": string_field(profile, "profile_id"),
            "profile_version": profile.get("profile_versions").and_then(Value::as_array).and_then(|v| v.first()).and_then(Value::as_str).unwrap_or("")
        },
        "signatures": [signature.clone()]
    }))
}

fn required_str<'a>(value: &'a Value, field: &str) -> Result<&'a str> {
    value
        .get(field)
        .and_then(Value::as_str)
        .ok_or_else(|| err("BACKEND_CAPABILITY_SIGNATURE_INVALID"))
}

fn int_field(value: &Value, field: &str) -> i64 {
    value.get(field).and_then(Value::as_i64).unwrap_or(-1)
}

fn number_field(value: &Value, field: &str) -> f64 {
    value.get(field).and_then(Value::as_f64).unwrap_or(f64::NAN)
}

fn strings(value: &Value, field: &str) -> Vec<String> {
    value
        .get(field)
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(Value::as_str)
        .map(str::to_string)
        .collect()
}

struct LevelDef {
    status: &'static str,
    requires: &'static [&'static str],
}

fn conformance_levels() -> BTreeMap<&'static str, LevelDef> {
    BTreeMap::from([
        (
            "KCP-Core-HAIL-v1",
            LevelDef {
                status: "implemented",
                requires: &[],
            },
        ),
        (
            "KCP-Core-Canonical-v1",
            LevelDef {
                status: "implemented",
                requires: &[],
            },
        ),
        (
            "KCP-Core-Lifecycle-v1",
            LevelDef {
                status: "implemented",
                requires: &["KCP-Core-HAIL-v1"],
            },
        ),
        (
            "KCP-Core-Chain-v1",
            LevelDef {
                status: "implemented",
                requires: &[
                    "KCP-Core-HAIL-v1",
                    "KCP-Core-Canonical-v1",
                    "KCP-Core-Lifecycle-v1",
                ],
            },
        ),
        (
            "KCP-Core-RunManifest-v1",
            LevelDef {
                status: "implemented",
                requires: &[
                    "KCP-Core-HAIL-v1",
                    "KCP-Core-Canonical-v1",
                    "KCP-Core-Chain-v1",
                ],
            },
        ),
        (
            "KCP-Core-TrustPolicy-v1",
            LevelDef {
                status: "implemented",
                requires: &["KCP-Core-RunManifest-v1"],
            },
        ),
        (
            "KCP-Core-BackendRegistry-v1",
            LevelDef {
                status: "implemented",
                requires: &["KCP-Core-TrustPolicy-v1"],
            },
        ),
        (
            "KCP-Core-SignedRegistry-v1",
            LevelDef {
                status: "implemented",
                requires: &["KCP-Core-BackendRegistry-v1"],
            },
        ),
        (
            "KCP-Core-BackendCapabilities-v1",
            LevelDef {
                status: "implemented",
                requires: &["KCP-Core-SignedRegistry-v1"],
            },
        ),
        (
            "KCP-Core-Signed-Conformance-v1",
            LevelDef {
                status: "implemented",
                requires: &[
                    "KCP-Core-HAIL-v1",
                    "KCP-Core-Canonical-v1",
                    "KCP-Core-Lifecycle-v1",
                    "KCP-Core-Chain-v1",
                    "KCP-Core-RunManifest-v1",
                    "KCP-Core-TrustPolicy-v1",
                    "KCP-Core-BackendRegistry-v1",
                ],
            },
        ),
        (
            "KCP-Core-RunBundle-v1",
            LevelDef {
                status: "implemented",
                requires: &["KCP-Core-Signed-Conformance-v1"],
            },
        ),
        (
            "KCP-Core-Bundled-Verification-v1",
            LevelDef {
                status: "implemented",
                requires: &["KCP-Core-RunBundle-v1"],
            },
        ),
        (
            "KCP-Core-IndependentVerifier-v1",
            LevelDef {
                status: "implemented",
                requires: &["KCP-Core-RunBundle-v1"],
            },
        ),
        (
            "KCP-Core-RustVerifier-Fixture-v1",
            LevelDef {
                status: "partial",
                requires: &["KCP-Core-IndependentVerifier-v1"],
            },
        ),
        (
            "KCP-Profile-DMF-Payload-v1",
            LevelDef {
                status: "implemented",
                requires: &["KCP-Core-HAIL-v1", "KCP-Core-Canonical-v1"],
            },
        ),
        (
            "KCP-Profile-DMF-Simulator-v1",
            LevelDef {
                status: "implemented",
                requires: &[
                    "KCP-Profile-DMF-Payload-v1",
                    "KCP-Core-BackendCapabilities-v1",
                ],
            },
        ),
        (
            "KCP-Profile-DMF-Recovery-Sim-v1",
            LevelDef {
                status: "target",
                requires: &["KCP-Profile-DMF-Simulator-v1"],
            },
        ),
        (
            "KCP-Profile-DMF-Observation-v1",
            LevelDef {
                status: "target",
                requires: &["KCP-Profile-DMF-Simulator-v1"],
            },
        ),
        (
            "KCP-Profile-DMF-HIL-L0",
            LevelDef {
                status: "target",
                requires: &["KCP-Profile-DMF-Observation-v1"],
            },
        ),
        (
            "KCP-Profile-DMF-HIL-L1",
            LevelDef {
                status: "future",
                requires: &["KCP-Profile-DMF-HIL-L0"],
            },
        ),
        (
            "KCP-Core-TrustedTimestamp-v1",
            LevelDef {
                status: "target",
                requires: &["KCP-Core-Signed-Conformance-v1"],
            },
        ),
        (
            "KCP-Core-AttestationProfile-v1",
            LevelDef {
                status: "future",
                requires: &["KCP-Core-TrustedTimestamp-v1"],
            },
        ),
        (
            "KCP-Core-HardwareBackedEvidence-v1",
            LevelDef {
                status: "future",
                requires: &["KCP-Core-AttestationProfile-v1"],
            },
        ),
    ])
}
