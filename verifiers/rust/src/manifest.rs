use base64::engine::general_purpose::STANDARD;
use base64::Engine;
use ed25519_dalek::{Signature, Verifier, VerifyingKey};
use serde_json::Value;

use crate::canonical::canonical_json;
use crate::errors::{err, Result};

pub fn verify_manifest_signature(manifest: &Value) -> Result<Vec<String>> {
    let payload = manifest
        .get("payload")
        .ok_or_else(|| err("RUN_MANIFEST_SCHEMA_INVALID"))?;
    let signatures = manifest
        .get("signatures")
        .and_then(Value::as_array)
        .ok_or_else(|| err("RUN_MANIFEST_SCHEMA_INVALID"))?;
    if signatures.is_empty() {
        return Err(err("RUN_MANIFEST_SIGNATURE_MISSING"));
    }
    let preimage = canonical_json(payload)?.into_bytes();
    for signature in signatures {
        let public_key = STANDARD.decode(required_str(signature, "public_key")?)?;
        let signature_bytes = STANDARD.decode(required_str(signature, "signature")?)?;
        let public_key: [u8; 32] = public_key
            .try_into()
            .map_err(|_| err("RUN_MANIFEST_SIGNATURE_INVALID"))?;
        let verifying_key = VerifyingKey::from_bytes(&public_key)?;
        let signature = Signature::from_slice(&signature_bytes)?;
        verifying_key
            .verify(&preimage, &signature)
            .map_err(|_| err("RUN_MANIFEST_SIGNATURE_INVALID"))?;
    }
    Ok(signatures
        .iter()
        .filter_map(|signature| {
            signature
                .get("key_id")
                .and_then(Value::as_str)
                .map(str::to_string)
        })
        .collect())
}

pub fn payload(manifest: &Value) -> Result<&Value> {
    manifest
        .get("payload")
        .ok_or_else(|| err("RUN_MANIFEST_SCHEMA_INVALID"))
}

pub fn validate_manifest_payload(
    manifest: &Value,
    hail_digest: &str,
    hail_chain_digest: &str,
) -> Result<()> {
    let payload = payload(manifest)?;
    if string_field(payload, "hail_digest") != hail_digest {
        return Err(err("RUN_MANIFEST_PAYLOAD_MISMATCH"));
    }
    if string_field(payload, "hail_chain_digest") != hail_chain_digest {
        return Err(err("RUN_MANIFEST_PAYLOAD_MISMATCH"));
    }
    Ok(())
}

pub fn string_field(value: &Value, field: &str) -> String {
    value
        .get(field)
        .and_then(Value::as_str)
        .unwrap_or_default()
        .to_string()
}

fn required_str<'a>(value: &'a Value, field: &str) -> Result<&'a str> {
    value
        .get(field)
        .and_then(Value::as_str)
        .ok_or_else(|| err("RUN_MANIFEST_SIGNATURE_INVALID"))
}
