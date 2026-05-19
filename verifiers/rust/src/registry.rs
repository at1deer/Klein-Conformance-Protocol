use base64::engine::general_purpose::STANDARD;
use base64::Engine;
use ed25519_dalek::{Signature, Verifier, VerifyingKey};
use serde_json::Value;

use crate::canonical::canonical_json;
use crate::errors::{err, Result};
use crate::manifest::string_field;

pub struct RegistryIdentity {
    pub registry_id: String,
    pub backend_id: String,
    pub key_id: String,
    pub key_status: String,
    pub public_key: String,
    pub registry_signed: bool,
    pub registry_signature_status: String,
    pub registry_provenance_status: String,
    pub registry_authority_id: Option<String>,
    pub key_lifecycle_status: String,
}

pub fn resolve_manifest_identity(registry: &Value, manifest: &Value) -> Result<RegistryIdentity> {
    resolve_manifest_identity_with_policy(registry, manifest, None)
}

pub fn resolve_manifest_identity_with_policy(
    registry: &Value,
    manifest: &Value,
    policy: Option<&Value>,
) -> Result<RegistryIdentity> {
    if registry.get("registry_version").and_then(Value::as_str)
        != Some("klein.backend_identity_registry.v1")
    {
        return Err(err("BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID"));
    }
    let (registry_payload, registry_signed) = normalized_registry_payload(registry)?;
    let provenance = verify_registry_provenance(registry, registry_payload, policy)?;
    let payload = manifest
        .get("payload")
        .ok_or_else(|| err("RUN_MANIFEST_SCHEMA_INVALID"))?;
    let signature = manifest
        .get("signatures")
        .and_then(Value::as_array)
        .and_then(|values| values.first())
        .ok_or_else(|| err("RUN_MANIFEST_SIGNATURE_MISSING"))?;
    let backend_id = string_field(payload, "backend_id");
    let backend_version = string_field(payload, "backend_version");
    let profile_id = string_field(payload, "profile_id");
    let profile_version = string_field(payload, "profile_version");
    let key_id = string_field(signature, "key_id");
    let signature_public_key = string_field(signature, "public_key");
    let backends = registry_payload
        .get("backends")
        .and_then(Value::as_array)
        .ok_or_else(|| err("BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID"))?;
    let backend = backends
        .iter()
        .find(|backend| string_field(backend, "backend_id") == backend_id)
        .ok_or_else(|| err("BACKEND_IDENTITY_NOT_FOUND"))?;
    if listed_contains(backend, "backend_versions", &backend_version).is_some_and(|ok| !ok) {
        return Err(err("BACKEND_IDENTITY_SCOPE_MISMATCH"));
    }
    if !profile_allowed(backend, &profile_id, &profile_version) {
        return Err(err("BACKEND_IDENTITY_SCOPE_MISMATCH"));
    }
    let keys = backend
        .get("keys")
        .and_then(Value::as_array)
        .ok_or_else(|| err("BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID"))?;
    let key = keys
        .iter()
        .find(|key| string_field(key, "key_id") == key_id)
        .ok_or_else(|| err("BACKEND_IDENTITY_KEY_NOT_FOUND"))?;
    let public_key = string_field(key, "public_key");
    STANDARD
        .decode(&public_key)
        .map_err(|_| err("BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID"))?;
    if public_key != signature_public_key {
        return Err(err("BACKEND_IDENTITY_KEY_MISMATCH"));
    }
    let key_status = string_field(key, "status");
    let key_lifecycle_status = if key_status == "active" {
        "active".to_string()
    } else if key_status == "retired" {
        "indeterminate".to_string()
    } else {
        "revoked".to_string()
    };
    if key_status != "active" {
        return Err(err(if key_status == "revoked" {
            "BACKEND_IDENTITY_KEY_REVOKED"
        } else if key_status == "retired" {
            "BACKEND_IDENTITY_KEY_RETIRED"
        } else {
            "BACKEND_IDENTITY_UNTRUSTED"
        }));
    }
    Ok(RegistryIdentity {
        registry_id: string_field(registry_payload, "registry_id"),
        backend_id,
        key_id,
        key_status,
        public_key,
        registry_signed,
        registry_signature_status: provenance.0,
        registry_provenance_status: provenance.1,
        registry_authority_id: provenance.2,
        key_lifecycle_status,
    })
}

fn normalized_registry_payload(registry: &Value) -> Result<(&Value, bool)> {
    if let Some(payload) = registry.get("payload") {
        if !payload.is_object() {
            return Err(err("BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID"));
        }
        return Ok((payload, true));
    }
    Ok((registry, false))
}

fn verify_registry_provenance(
    registry: &Value,
    payload: &Value,
    policy: Option<&Value>,
) -> Result<(String, String, Option<String>)> {
    if registry.get("payload").is_none() {
        return Ok((
            "not_applicable".to_string(),
            "not_evaluated".to_string(),
            None,
        ));
    }
    let signatures = registry
        .get("signatures")
        .and_then(Value::as_array)
        .ok_or_else(|| err("BACKEND_REGISTRY_SIGNATURE_MISSING"))?;
    if signatures.is_empty() {
        return Err(err("BACKEND_REGISTRY_SIGNATURE_MISSING"));
    }
    for signature in signatures {
        if verify_registry_signature(payload, signature).is_ok() {
            let authority_id = string_field(signature, "authority_id");
            if authority_trusted(policy, &string_field(payload, "registry_id"), signature) {
                return Ok((
                    "valid".to_string(),
                    "trusted".to_string(),
                    Some(authority_id),
                ));
            }
            return Ok((
                "valid".to_string(),
                "not_evaluated".to_string(),
                Some(authority_id),
            ));
        }
    }
    Err(err("BACKEND_REGISTRY_SIGNATURE_INVALID"))
}

fn verify_registry_signature(payload: &Value, signature: &Value) -> Result<()> {
    let public_key = STANDARD.decode(required_signature_str(signature, "public_key")?)?;
    let signature_bytes = STANDARD.decode(required_signature_str(signature, "signature")?)?;
    let public_key: [u8; 32] = public_key
        .try_into()
        .map_err(|_| err("BACKEND_REGISTRY_SIGNATURE_INVALID"))?;
    let verifying_key = VerifyingKey::from_bytes(&public_key)?;
    let signature = Signature::from_slice(&signature_bytes)?;
    verifying_key
        .verify(canonical_json(payload)?.as_bytes(), &signature)
        .map_err(|_| err("BACKEND_REGISTRY_SIGNATURE_INVALID"))?;
    Ok(())
}

fn authority_trusted(policy: Option<&Value>, registry_id: &str, signature: &Value) -> bool {
    let Some(policy) = policy else {
        return false;
    };
    policy
        .get("trusted_registry_authorities")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .any(|authority| {
            string_field(authority, "status") == "trusted"
                && string_field(authority, "authority_id")
                    == string_field(signature, "authority_id")
                && string_field(authority, "public_key") == string_field(signature, "public_key")
                && authority
                    .get("registry_ids")
                    .and_then(Value::as_array)
                    .is_some_and(|ids| ids.iter().any(|id| id.as_str() == Some(registry_id)))
        })
}

fn required_signature_str<'a>(value: &'a Value, field: &str) -> Result<&'a str> {
    value
        .get(field)
        .and_then(Value::as_str)
        .ok_or_else(|| err("BACKEND_REGISTRY_SIGNATURE_INVALID"))
}

fn listed_contains(value: &Value, field: &str, needle: &str) -> Option<bool> {
    let values = value.get(field)?.as_array()?;
    if values.is_empty() {
        return None;
    }
    Some(values.iter().any(|value| value.as_str() == Some(needle)))
}

fn profile_allowed(backend: &Value, profile_id: &str, profile_version: &str) -> bool {
    let Some(profiles) = backend.get("profiles").and_then(Value::as_array) else {
        return true;
    };
    if profiles.is_empty() {
        return true;
    }
    profiles.iter().any(|profile| {
        string_field(profile, "profile_id") == profile_id
            && !listed_contains(profile, "profile_versions", profile_version).is_some_and(|ok| !ok)
    })
}
