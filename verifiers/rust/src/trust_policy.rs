use serde_json::Value;

use crate::errors::{err, Result};
use crate::manifest::string_field;

pub fn authorize(policy: &Value, manifest: &Value) -> Result<Vec<String>> {
    authorize_with_registry_key(policy, manifest, None)
}

pub fn authorize_with_registry_key(
    policy: &Value,
    manifest: &Value,
    registry_public_key: Option<&str>,
) -> Result<Vec<String>> {
    let payload = manifest
        .get("payload")
        .ok_or_else(|| err("RUN_MANIFEST_SCHEMA_INVALID"))?;
    let signature = manifest
        .get("signatures")
        .and_then(Value::as_array)
        .and_then(|signatures| signatures.first())
        .ok_or_else(|| err("RUN_MANIFEST_SIGNATURE_MISSING"))?;
    let key_id = string_field(signature, "key_id");
    let public_key = string_field(signature, "public_key");

    for revoked in policy
        .get("revoked_keys")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
    {
        if string_field(revoked, "key_id") == key_id
            && string_field(revoked, "public_key") == public_key
        {
            return Err(err("TRUST_POLICY_KEY_REVOKED"));
        }
    }

    let trusted_keys = policy
        .get("trusted_keys")
        .and_then(Value::as_array)
        .ok_or_else(|| err("TRUST_POLICY_SCHEMA_INVALID"))?;
    let trusted = trusted_keys
        .iter()
        .find(|entry| policy_key_matches(entry, &key_id, &public_key, registry_public_key))
        .ok_or_else(|| err("TRUST_POLICY_KEY_NOT_FOUND"))?;
    if string_field(trusted, "status") != "trusted" {
        return Err(err("BACKEND_IDENTITY_UNTRUSTED"));
    }
    let scope = trusted
        .get("trust_scope")
        .ok_or_else(|| err("TRUST_POLICY_SCHEMA_INVALID"))?;
    let checks = [
        ("backend_ids", string_field(payload, "backend_id")),
        ("profile_ids", string_field(payload, "profile_id")),
        ("profile_versions", string_field(payload, "profile_version")),
        (
            "manifest_versions",
            string_field(manifest, "manifest_version"),
        ),
    ];
    for (scope_field, value) in checks {
        if !contains_string(scope, scope_field, &value) {
            return Err(err("TRUST_POLICY_SCOPE_MISMATCH"));
        }
    }
    Ok(vec![key_id])
}

fn policy_key_matches(
    entry: &Value,
    key_id: &str,
    public_key: &str,
    registry_public_key: Option<&str>,
) -> bool {
    if string_field(entry, "key_id") != key_id {
        return false;
    }
    if let Some(policy_public_key) = entry.get("public_key").and_then(Value::as_str) {
        return policy_public_key == public_key
            && registry_public_key.is_none_or(|key| key == policy_public_key);
    }
    entry.get("source").and_then(Value::as_str) == Some("registry")
        && registry_public_key.is_some_and(|key| key == public_key)
}

fn contains_string(value: &Value, field: &str, needle: &str) -> bool {
    value
        .get(field)
        .and_then(Value::as_array)
        .map(|items| items.iter().any(|item| item.as_str() == Some(needle)))
        .unwrap_or(false)
}

#[cfg(test)]
mod tests {
    use serde_json::Value;

    use super::authorize;

    fn manifest() -> Value {
        serde_json::from_str(include_str!(
            "../../../tests/fixtures/signed_conformance/manifest_signed.json"
        ))
        .unwrap()
    }

    fn policy() -> Value {
        serde_json::from_str(include_str!(
            "../../../tests/fixtures/signed_conformance/trust_policy.json"
        ))
        .unwrap()
    }

    #[test]
    fn trusted_key_correct_scope_is_authorized() {
        assert_eq!(
            authorize(&policy(), &manifest()).unwrap(),
            vec!["klein-test-backend-001"]
        );
    }

    #[test]
    fn trusted_key_wrong_backend_is_untrusted() {
        let mut policy = policy();
        policy["trusted_keys"][0]["trust_scope"]["backend_ids"] = serde_json::json!(["other"]);

        assert_error(&policy, &manifest(), "TRUST_POLICY_SCOPE_MISMATCH");
    }

    #[test]
    fn trusted_key_wrong_profile_is_untrusted() {
        let mut policy = policy();
        policy["trusted_keys"][0]["trust_scope"]["profile_ids"] = serde_json::json!(["other"]);

        assert_error(&policy, &manifest(), "TRUST_POLICY_SCOPE_MISMATCH");
    }

    #[test]
    fn revoked_key_is_untrusted() {
        let mut policy = policy();
        let revoked = policy["trusted_keys"][0].clone();
        policy["revoked_keys"] = serde_json::json!([revoked]);

        assert_error(&policy, &manifest(), "TRUST_POLICY_KEY_REVOKED");
    }

    #[test]
    fn unknown_key_is_untrusted() {
        let mut policy = policy();
        policy["trusted_keys"][0]["key_id"] = serde_json::json!("other-key");

        assert_error(&policy, &manifest(), "TRUST_POLICY_KEY_NOT_FOUND");
    }

    #[test]
    fn missing_policy_is_not_supported_for_bundle_verification() {
        assert_error(&Value::Null, &manifest(), "TRUST_POLICY_SCHEMA_INVALID");
    }

    fn assert_error(policy: &Value, manifest: &Value, code: &str) {
        let error = authorize(policy, manifest).unwrap_err().to_string();
        assert_eq!(error, code);
    }
}
