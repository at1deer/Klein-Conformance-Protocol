use std::collections::{BTreeMap, HashSet};
use std::fs::File;
use std::io::Read;
use std::path::Path;

use serde::Serialize;
use serde_json::Value;
use zip::ZipArchive;

use crate::canonical::sha256_ref;
use crate::capabilities::verify_capability_declaration;
use crate::errors::{err, Result};
use crate::hail_chain::{hail_digest_ref, parse_jsonl, verify_hail_chain};
use crate::manifest::{validate_manifest_payload, verify_manifest_signature};
use crate::registry::resolve_manifest_identity_with_policy;
use crate::trust_policy::{authorize, authorize_with_registry_key};

#[derive(Debug)]
pub struct BundleVerification {
    pub trusted_key_ids: Vec<String>,
}

#[derive(Debug, Serialize)]
pub struct IndependentVerifierResult {
    pub result_version: String,
    pub overall_status: String,
    pub bundle_format: Option<String>,
    pub bundle_path: String,
    pub checks: BTreeMap<String, String>,
    pub bindings: BTreeMap<String, Value>,
    pub errors: Vec<Diagnostic>,
    pub warnings: Vec<Diagnostic>,
}

#[derive(Debug, Serialize)]
pub struct Diagnostic {
    pub check: String,
    pub error_code: String,
    pub message: String,
}

impl IndependentVerifierResult {
    pub fn ok(&self) -> bool {
        self.overall_status == "pass"
    }
}

pub fn verify_bundle(path: &Path) -> Result<BundleVerification> {
    let result = verify_bundle_result(path);
    if result.ok() {
        let trusted_key_ids = result
            .bindings
            .get("trusted_key_ids")
            .and_then(Value::as_array)
            .map(|values| {
                values
                    .iter()
                    .filter_map(Value::as_str)
                    .map(str::to_string)
                    .collect()
            })
            .unwrap_or_default();
        return Ok(BundleVerification { trusted_key_ids });
    }
    let message = result
        .errors
        .first()
        .map(|error| error.error_code.clone())
        .unwrap_or_else(|| "INDEPENDENT_VERIFIER_FAILED".to_string());
    Err(err(message))
}

pub fn verify_bundle_result(path: &Path) -> IndependentVerifierResult {
    let mut result = IndependentVerifierResult {
        result_version: "klein.independent_verifier_result.v1".to_string(),
        overall_status: "fail".to_string(),
        bundle_format: None,
        bundle_path: path.to_string_lossy().to_string(),
        checks: default_checks(),
        bindings: default_bindings(),
        errors: Vec::new(),
        warnings: Vec::new(),
    };
    if !path.is_file() || path.extension().and_then(|value| value.to_str()) != Some("kcprun") {
        result.fail(
            "bundle_schema",
            "RUN_BUNDLE_UNSUPPORTED_FORMAT",
            "bundle must be a .kcprun file",
        );
        return result;
    }
    result.bundle_format = Some("zip".to_string());
    if let Err(error) = verify_bundle_into(path, &mut result) {
        if result.errors.is_empty() {
            result.fail("bundle_schema", "RUN_BUNDLE_INVALID", &error.to_string());
        }
        return result;
    }
    result.overall_status = if all_required_pass(&result.checks) {
        "pass".to_string()
    } else {
        "fail".to_string()
    };
    result
}

fn verify_bundle_into(path: &Path, result: &mut IndependentVerifierResult) -> Result<()> {
    if let Some(name) = duplicate_member_name(path)? {
        result.fail(
            "bundle_schema",
            "RUN_BUNDLE_INVALID",
            &format!("zip bundle contains duplicate member names: {name}"),
        );
        return Ok(());
    }
    let file = File::open(path)?;
    let mut archive = ZipArchive::new(file)?;
    let names = match validate_members(&mut archive) {
        Ok(names) => names,
        Err(diagnostic) => {
            result.push_diagnostic(diagnostic);
            return Ok(());
        }
    };

    if !names.contains("bundle.json") {
        result.fail(
            "bundle_entry_hashes",
            "RUN_BUNDLE_MISSING_ENTRY",
            "bundle.json is required",
        );
        return Ok(());
    }
    let bundle: Value = match serde_json::from_slice(&read_member(&mut archive, "bundle.json")?) {
        Ok(value) => value,
        Err(error) => {
            result.fail(
                "bundle_schema",
                "RUN_BUNDLE_INVALID",
                &format!("bundle.json parse failed: {error}"),
            );
            return Ok(());
        }
    };
    let bundle = match validate_bundle_structure(&bundle) {
        Ok(bundle) => bundle,
        Err(diagnostic) => {
            result.push_diagnostic(diagnostic);
            return Ok(());
        }
    };
    result.set_check("bundle_schema", "pass");
    let entries = bundle
        .get("entries")
        .and_then(Value::as_object)
        .ok_or_else(|| err("RUN_BUNDLE_SCHEMA_INVALID"))?;
    let hashes = bundle
        .get("hashes")
        .and_then(Value::as_object)
        .ok_or_else(|| err("RUN_BUNDLE_SCHEMA_INVALID"))?;

    let expected_names = expected_member_names(entries);
    let extra: Vec<String> = names.difference(&expected_names).cloned().collect();
    if !extra.is_empty() {
        result.fail(
            "bundle_schema",
            "RUN_BUNDLE_INVALID",
            &format!("bundle contains undeclared file(s): {}", extra.join(", ")),
        );
        return Ok(());
    }
    let missing: Vec<String> = expected_names.difference(&names).cloned().collect();
    if !missing.is_empty() {
        result.fail(
            "bundle_entry_hashes",
            "RUN_BUNDLE_MISSING_ENTRY",
            &format!("bundle is missing declared file(s): {}", missing.join(", ")),
        );
        return Ok(());
    }

    for key in [
        "artifact",
        "hail",
        "run_manifest",
        "trust_policy",
        "conformance_report",
        "signed_conformance_report",
        "backend_registry",
        "backend_capabilities",
    ] {
        if entries.get(key).is_none() {
            continue;
        }
        if entries.get(key).is_some_and(Value::is_null) {
            if !hashes.get(key).unwrap_or(&Value::Null).is_null() {
                result.fail(
                    "bundle_entry_hashes",
                    "RUN_BUNDLE_SCHEMA_INVALID",
                    &format!("hashes.{key} must be null when entries.{key} is null"),
                );
                return Ok(());
            }
            continue;
        }
        let entry = entries
            .get(key)
            .and_then(Value::as_str)
            .ok_or_else(|| err("RUN_BUNDLE_MISSING_ENTRY"))?;
        let expected = hashes
            .get(key)
            .and_then(Value::as_str)
            .ok_or_else(|| err("RUN_BUNDLE_SCHEMA_INVALID"))?;
        let bytes = read_member(&mut archive, entry)?;
        if sha256_ref(&bytes) != expected {
            result.fail(
                "bundle_entry_hashes",
                "RUN_BUNDLE_HASH_MISMATCH",
                &format!(
                    "{key} hash mismatch: expected {expected}, actual {}",
                    sha256_ref(&bytes)
                ),
            );
            return Ok(());
        }
    }
    result.set_check("bundle_entry_hashes", "pass");

    let hail_entry = entries["hail"].as_str().unwrap();
    let manifest_entry = entries["run_manifest"].as_str().unwrap();
    let policy_entry = entries["trust_policy"].as_str().unwrap();
    let registry_entry = entries.get("backend_registry").and_then(Value::as_str);
    let capabilities_entry = entries.get("backend_capabilities").and_then(Value::as_str);
    let hail_text = match String::from_utf8(read_member(&mut archive, hail_entry)?) {
        Ok(text) => text,
        Err(_) => {
            result.fail(
                "hail_schema",
                "HAIL_JSON_INVALID",
                "HAIL JSONL is not UTF-8",
            );
            return Ok(());
        }
    };
    let hail_events = match parse_jsonl(&hail_text) {
        Ok(events) => events,
        Err(error) => {
            result.fail("hail_schema", "HAIL_JSON_INVALID", &error.to_string());
            return Ok(());
        }
    };
    result.set_check("hail_schema", "pass");
    result.set_check("hail_ordering", "pass");
    result.set_check("hail_lifecycle", "pass");
    let chain_digest = match verify_hail_chain(&hail_events) {
        Ok(digest) => {
            result.set_check("hail_chain", "pass");
            digest
        }
        Err(error) => {
            result.fail("hail_chain", &error.to_string(), &error.to_string());
            return Ok(());
        }
    };
    let hail_digest = hail_digest_ref(&hail_events)?;
    result.set_check("hail_canonicalization", "pass");
    result.set_binding("hail_digest", Value::String(hail_digest.clone()));
    result.set_binding("hail_chain_digest", Value::String(chain_digest.clone()));

    let manifest: Value = match serde_json::from_slice(&read_member(&mut archive, manifest_entry)?)
    {
        Ok(value) => value,
        Err(error) => {
            result.fail(
                "run_manifest_schema",
                "RUN_MANIFEST_INVALID",
                &format!("manifest JSON parse failed: {error}"),
            );
            return Ok(());
        }
    };
    if manifest.get("payload").and_then(Value::as_object).is_none()
        || manifest
            .get("signatures")
            .and_then(Value::as_array)
            .is_none()
    {
        result.fail(
            "run_manifest_schema",
            "RUN_MANIFEST_SCHEMA_INVALID",
            "manifest must contain payload and signatures",
        );
        return Ok(());
    }
    result.set_check("run_manifest_schema", "pass");
    if let Err(error) = validate_manifest_payload(&manifest, &hail_digest, &chain_digest) {
        result.fail(
            "run_manifest_payload",
            &error.to_string(),
            &error.to_string(),
        );
        return Ok(());
    }
    result.set_check("run_manifest_payload", "pass");
    if let Err(error) = verify_manifest_signature(&manifest) {
        result.fail(
            "run_manifest_signature",
            &error.to_string(),
            &error.to_string(),
        );
        return Ok(());
    }
    result.set_check("run_manifest_signature", "pass");
    copy_payload_bindings(result, &manifest);

    let policy: Value = match serde_json::from_slice(&read_member(&mut archive, policy_entry)?) {
        Ok(value) => value,
        Err(error) => {
            result.fail(
                "trust_policy_schema",
                "TRUST_POLICY_SCHEMA_INVALID",
                &format!("trust policy JSON parse failed: {error}"),
            );
            return Ok(());
        }
    };
    result.set_check("trust_policy_schema", "pass");
    let mut registry_value: Option<Value> = None;
    let registry_identity = if let Some(entry) = registry_entry {
        let registry_bytes = read_member(&mut archive, entry)?;
        result.set_binding(
            "backend_registry_hash",
            Value::String(sha256_ref(&registry_bytes)),
        );
        let registry: Value = match serde_json::from_slice(&registry_bytes) {
            Ok(value) => value,
            Err(error) => {
                result.fail(
                    "backend_identity_registry",
                    "BACKEND_IDENTITY_REGISTRY_INVALID",
                    &format!("registry JSON parse failed: {error}"),
                );
                return Ok(());
            }
        };
        registry_value = Some(registry.clone());
        result.set_check("backend_identity_registry", "pass");
        match resolve_manifest_identity_with_policy(&registry, &manifest, Some(&policy)) {
            Ok(identity) => {
                result.set_check("backend_identity_resolution", "pass");
                result.set_binding("identity_status", Value::String("resolved".to_string()));
                result.set_binding(
                    "backend_identity_status",
                    Value::String("resolved".to_string()),
                );
                result.set_binding(
                    "backend_registry_id",
                    Value::String(identity.registry_id.clone()),
                );
                result.set_binding(
                    "registry_backend_id",
                    Value::String(identity.backend_id.clone()),
                );
                result.set_binding("registry_key_id", Value::String(identity.key_id.clone()));
                result.set_binding(
                    "backend_key_status",
                    Value::String(identity.key_status.clone()),
                );
                result.set_binding("registry_signed", Value::Bool(identity.registry_signed));
                result.set_binding(
                    "registry_signature_status",
                    Value::String(identity.registry_signature_status.clone()),
                );
                result.set_binding(
                    "registry_provenance_status",
                    Value::String(identity.registry_provenance_status.clone()),
                );
                result.set_binding(
                    "registry_authority_id",
                    identity
                        .registry_authority_id
                        .clone()
                        .map(Value::String)
                        .unwrap_or(Value::Null),
                );
                result.set_binding(
                    "key_lifecycle_status",
                    Value::String(identity.key_lifecycle_status.clone()),
                );
                Some(identity)
            }
            Err(error) => {
                let code = error.to_string();
                result.fail("backend_identity_resolution", &code, &code);
                return Ok(());
            }
        }
    } else {
        result.set_check("backend_identity_registry", "not_applicable");
        result.set_check("backend_identity_resolution", "not_applicable");
        None
    };
    let trusted_key_ids = match registry_identity {
        Some(ref identity) => {
            authorize_with_registry_key(&policy, &manifest, Some(&identity.public_key))
        }
        None => authorize(&policy, &manifest),
    };
    let trusted_key_ids = match trusted_key_ids {
        Ok(keys) => keys,
        Err(error) => {
            let code = error.to_string();
            let check = if code == "TRUST_POLICY_SCHEMA_INVALID" {
                "trust_policy_schema"
            } else {
                "trust_policy_authorization"
            };
            result.fail(check, &code, &code);
            return Ok(());
        }
    };
    result.set_check("trust_policy_authorization", "pass");
    result.set_binding(
        "trusted_key_ids",
        Value::Array(trusted_key_ids.into_iter().map(Value::String).collect()),
    );
    if let Some(entry) = capabilities_entry {
        let capability_bytes = read_member(&mut archive, entry)?;
        let declaration: Value = match serde_json::from_slice(&capability_bytes) {
            Ok(value) => value,
            Err(error) => {
                result.fail(
                    "trust_policy_authorization",
                    "BACKEND_CAPABILITY_DECLARATION_INVALID",
                    &format!("capability declaration JSON parse failed: {error}"),
                );
                return Ok(());
            }
        };
        match verify_capability_declaration(
            &declaration,
            registry_value.as_ref(),
            Some(&policy),
            Some(&manifest),
        ) {
            Ok(verification) => {
                result.set_binding("backend_capabilities_present", Value::Bool(true));
                result.set_binding(
                    "backend_capability_declaration_hash",
                    Value::String(verification.declaration_hash),
                );
                result.set_binding(
                    "backend_capability_signature_status",
                    Value::String(verification.signature_status),
                );
                result.set_binding(
                    "backend_capability_trust_status",
                    Value::String(verification.trust_status),
                );
                result.set_binding(
                    "backend_capability_scope_status",
                    Value::String(verification.scope_status),
                );
                result.set_binding("backend_capability_error_code", Value::Null);
                let declared = declaration
                    .get("payload")
                    .and_then(|payload| payload.get("supported_conformance_levels"))
                    .and_then(Value::as_array)
                    .map(|levels| {
                        levels
                            .iter()
                            .filter_map(Value::as_str)
                            .map(|level| Value::String(level.to_string()))
                            .collect::<Vec<_>>()
                    })
                    .unwrap_or_default();
                result.set_binding(
                    "declared_conformance_levels",
                    Value::Array(declared.clone()),
                );
                result.set_binding("verified_conformance_levels", Value::Array(declared));
                result.set_binding(
                    "conformance_level_catalog_status",
                    Value::String("pass".to_string()),
                );
                result.set_binding(
                    "conformance_level_dependency_status",
                    Value::String("pass".to_string()),
                );
                result.set_binding("conformance_level_error_code", Value::Null);
            }
            Err(error) => {
                let code = error.to_string();
                result.fail("trust_policy_authorization", &code, &code);
                return Ok(());
            }
        }
    }
    if entries
        .get("conformance_report")
        .and_then(Value::as_str)
        .is_some()
    {
        result.set_check("conformance_report", "not_evaluated");
    }
    Ok(())
}

impl IndependentVerifierResult {
    fn set_check(&mut self, check: &str, status: &str) {
        self.checks.insert(check.to_string(), status.to_string());
    }

    fn set_binding(&mut self, name: &str, value: Value) {
        self.bindings.insert(name.to_string(), value);
    }

    fn fail(&mut self, check: &str, error_code: &str, message: &str) {
        self.set_check(check, "fail");
        self.push_diagnostic(Diagnostic {
            check: check.to_string(),
            error_code: error_code.to_string(),
            message: message.to_string(),
        });
    }

    fn push_diagnostic(&mut self, diagnostic: Diagnostic) {
        self.set_check(&diagnostic.check, "fail");
        self.errors.push(diagnostic);
    }
}

fn validate_members(
    archive: &mut ZipArchive<File>,
) -> std::result::Result<HashSet<String>, Diagnostic> {
    let mut seen = HashSet::new();
    for index in 0..archive.len() {
        let file = archive.by_index(index).map_err(|error| Diagnostic {
            check: "bundle_schema".to_string(),
            error_code: "RUN_BUNDLE_INVALID".to_string(),
            message: error.to_string(),
        })?;
        if file.is_dir() {
            continue;
        }
        let name = file.name().to_string();
        if !seen.insert(name.clone()) {
            return Err(Diagnostic {
                check: "bundle_schema".to_string(),
                error_code: "RUN_BUNDLE_INVALID".to_string(),
                message: "zip bundle contains duplicate member names".to_string(),
            });
        }
        if unsafe_path(&name) {
            return Err(Diagnostic {
                check: "bundle_schema".to_string(),
                error_code: "RUN_BUNDLE_PATH_TRAVERSAL".to_string(),
                message: format!("zip bundle contains unsafe member path: {name}"),
            });
        }
    }
    Ok(seen)
}

fn unsafe_path(name: &str) -> bool {
    name.starts_with('/')
        || name.contains('\\')
        || name.contains(':')
        || name.split('/').any(|part| part == "..")
}

fn read_member(archive: &mut ZipArchive<File>, name: &str) -> Result<Vec<u8>> {
    let mut file = archive
        .by_name(name)
        .map_err(|_| err("RUN_BUNDLE_MISSING_ENTRY"))?;
    let mut bytes = Vec::new();
    file.read_to_end(&mut bytes)?;
    Ok(bytes)
}

fn default_checks() -> BTreeMap<String, String> {
    [
        ("bundle_schema", "not_evaluated"),
        ("bundle_entry_hashes", "not_evaluated"),
        ("hail_schema", "not_evaluated"),
        ("hail_canonicalization", "not_evaluated"),
        ("hail_ordering", "not_evaluated"),
        ("hail_lifecycle", "not_evaluated"),
        ("hail_chain", "not_evaluated"),
        ("run_manifest_schema", "not_evaluated"),
        ("run_manifest_payload", "not_evaluated"),
        ("run_manifest_signature", "not_evaluated"),
        ("trust_policy_schema", "not_evaluated"),
        ("trust_policy_authorization", "not_evaluated"),
        ("backend_identity_registry", "not_applicable"),
        ("backend_identity_resolution", "not_applicable"),
        ("conformance_report", "not_applicable"),
    ]
    .into_iter()
    .map(|(key, value)| (key.to_string(), value.to_string()))
    .collect()
}

fn default_bindings() -> BTreeMap<String, Value> {
    [
        "artifact_hash",
        "hail_digest",
        "hail_chain_digest",
        "backend_id",
        "backend_version",
        "profile_id",
        "profile_version",
        "substrate_fingerprint",
        "identity_status",
        "backend_registry_id",
        "backend_registry_hash",
        "backend_identity_status",
        "backend_key_status",
        "registry_key_id",
        "registry_backend_id",
        "registry_signed",
        "registry_signature_status",
        "registry_provenance_status",
        "registry_authority_id",
        "key_lifecycle_status",
        "backend_capability_declaration_hash",
        "backend_capability_signature_status",
        "backend_capability_trust_status",
        "backend_capability_scope_status",
        "backend_capability_error_code",
        "conformance_level_catalog_status",
        "conformance_level_dependency_status",
        "conformance_level_error_code",
    ]
    .into_iter()
    .map(|key| {
        let value = match key {
            "identity_status" | "backend_identity_status" => {
                Value::String("not_evaluated".to_string())
            }
            "registry_signed" => Value::Bool(false),
            "backend_capabilities_present" => Value::Bool(false),
            "registry_signature_status" => Value::String("not_applicable".to_string()),
            "registry_provenance_status" => Value::String("not_evaluated".to_string()),
            "backend_capability_signature_status"
            | "backend_capability_trust_status"
            | "backend_capability_scope_status"
            | "conformance_level_catalog_status"
            | "conformance_level_dependency_status" => Value::String("not_evaluated".to_string()),
            _ => Value::Null,
        };
        (key.to_string(), value)
    })
    .chain(std::iter::once((
        "backend_capabilities_present".to_string(),
        Value::Bool(false),
    )))
    .chain([
        (
            "declared_conformance_levels".to_string(),
            Value::Array(Vec::new()),
        ),
        (
            "verified_conformance_levels".to_string(),
            Value::Array(Vec::new()),
        ),
    ])
    .chain(std::iter::once((
        "trusted_key_ids".to_string(),
        Value::Array(Vec::new()),
    )))
    .collect()
}

fn all_required_pass(checks: &BTreeMap<String, String>) -> bool {
    checks.iter().all(|(name, status)| {
        status == "pass"
            || (matches!(
                name.as_str(),
                "conformance_report" | "backend_identity_registry" | "backend_identity_resolution"
            ) && status == "not_applicable")
    })
}

fn validate_bundle_structure(bundle: &Value) -> std::result::Result<&Value, Diagnostic> {
    let Some(object) = bundle.as_object() else {
        return Err(schema_error("bundle.json must be a JSON object"));
    };
    let allowed = [
        "bundle_version",
        "bundle_id",
        "created_by",
        "created_at",
        "entries",
        "hashes",
    ];
    if let Some(key) = object.keys().find(|key| !allowed.contains(&key.as_str())) {
        return Err(schema_error(&format!(
            "bundle.json has unknown field: {key}"
        )));
    }
    if bundle.get("bundle_version").and_then(Value::as_str) != Some("klein.run_bundle.v1") {
        return Err(schema_error("invalid bundle_version"));
    }
    if !bundle.get("created_by").is_some_and(Value::is_string) {
        return Err(schema_error("created_by is required"));
    }
    let entries = bundle
        .get("entries")
        .and_then(Value::as_object)
        .ok_or_else(|| schema_error("entries must be an object"))?;
    let hashes = bundle
        .get("hashes")
        .and_then(Value::as_object)
        .ok_or_else(|| schema_error("hashes must be an object"))?;
    let allowed_entry_keys = [
        "artifact",
        "hail",
        "run_manifest",
        "trust_policy",
        "conformance_report",
        "signed_conformance_report",
        "backend_registry",
        "backend_capabilities",
    ];
    if let Some(key) = entries
        .keys()
        .find(|key| !allowed_entry_keys.contains(&key.as_str()))
    {
        return Err(schema_error(&format!("entries has unknown field: {key}")));
    }
    if let Some(key) = hashes
        .keys()
        .find(|key| !allowed_entry_keys.contains(&key.as_str()))
    {
        return Err(schema_error(&format!("hashes has unknown field: {key}")));
    }
    for key in ["artifact", "hail", "run_manifest", "trust_policy"] {
        let Some(entry) = entries.get(key).and_then(Value::as_str) else {
            return Err(Diagnostic {
                check: "bundle_entry_hashes".to_string(),
                error_code: "RUN_BUNDLE_MISSING_ENTRY".to_string(),
                message: format!("entries.{key} is required"),
            });
        };
        if unsafe_path(entry) {
            return Err(schema_error(&format!(
                "entries.{key} must be a portable relative path inside the bundle"
            )));
        }
        let Some(hash) = hashes.get(key).and_then(Value::as_str) else {
            return Err(schema_error(&format!("hashes.{key} is required")));
        };
        if !is_sha256_ref(hash) {
            return Err(schema_error(&format!("hashes.{key} must be sha256:<hex>")));
        }
    }
    for key in [
        "conformance_report",
        "signed_conformance_report",
        "backend_registry",
        "backend_capabilities",
    ] {
        if let Some(value) = entries.get(key) {
            if !(value.is_null() || value.as_str().is_some_and(|path| !unsafe_path(path))) {
                return Err(schema_error(&format!(
                    "entries.{key} must be a portable relative path or null"
                )));
            }
        }
        if let Some(value) = hashes.get(key) {
            if !(value.is_null() || value.as_str().is_some_and(is_sha256_ref)) {
                return Err(schema_error(&format!(
                    "hashes.{key} must be sha256:<hex> or null"
                )));
            }
        }
    }
    Ok(bundle)
}

fn schema_error(message: &str) -> Diagnostic {
    Diagnostic {
        check: "bundle_schema".to_string(),
        error_code: "RUN_BUNDLE_SCHEMA_INVALID".to_string(),
        message: message.to_string(),
    }
}

fn is_sha256_ref(value: &str) -> bool {
    value.len() == 71
        && value.starts_with("sha256:")
        && value[7..]
            .chars()
            .all(|ch| ch.is_ascii_hexdigit() && !ch.is_ascii_uppercase())
}

fn expected_member_names(entries: &serde_json::Map<String, Value>) -> HashSet<String> {
    std::iter::once("bundle.json".to_string())
        .chain(
            entries
                .values()
                .filter_map(Value::as_str)
                .map(str::to_string),
        )
        .collect()
}

fn copy_payload_bindings(result: &mut IndependentVerifierResult, manifest: &Value) {
    let payload = &manifest["payload"];
    for (binding, field) in [
        ("artifact_hash", "artifact_hash"),
        ("backend_id", "backend_id"),
        ("backend_version", "backend_version"),
        ("profile_id", "profile_id"),
        ("profile_version", "profile_version"),
        ("substrate_fingerprint", "substrate_fingerprint"),
    ] {
        if let Some(value) = payload.get(field) {
            result.set_binding(binding, value.clone());
        }
    }
}

fn duplicate_member_name(path: &Path) -> Result<Option<String>> {
    let bytes = std::fs::read(path)?;
    let mut seen = HashSet::new();
    let mut offset = 0usize;
    while offset + 46 <= bytes.len() {
        if bytes[offset..offset + 4] != [0x50, 0x4b, 0x01, 0x02] {
            offset += 1;
            continue;
        }
        let name_len = u16::from_le_bytes([bytes[offset + 28], bytes[offset + 29]]) as usize;
        let extra_len = u16::from_le_bytes([bytes[offset + 30], bytes[offset + 31]]) as usize;
        let comment_len = u16::from_le_bytes([bytes[offset + 32], bytes[offset + 33]]) as usize;
        let name_start = offset + 46;
        let name_end = name_start + name_len;
        if name_end > bytes.len() {
            return Ok(None);
        }
        let name = String::from_utf8_lossy(&bytes[name_start..name_end]).to_string();
        if !name.ends_with('/') && !seen.insert(name.clone()) {
            return Ok(Some(name));
        }
        offset = name_end + extra_len + comment_len;
    }
    Ok(None)
}
