use std::fs;
use std::path::{Path, PathBuf};

use serde::Deserialize;
use serde_json::Value;

use crate::canonical::canonical_sha256_ref;
use crate::capabilities::verify_capability_declaration;
use crate::errors::{err, Result};
use crate::hail_chain::{hail_digest_ref, parse_jsonl, verify_hail_chain};
use crate::manifest::{validate_manifest_payload, verify_manifest_signature};
use crate::registry::{resolve_manifest_identity, resolve_manifest_identity_with_policy};
use crate::trust_policy::authorize;

#[derive(Debug)]
pub struct FixtureSummary {
    pub passed: usize,
    pub failed: usize,
    pub results: Vec<FixtureResult>,
}

#[derive(Debug)]
pub struct FixtureResult {
    pub fixture_id: String,
    pub status: String,
    pub message: String,
}

#[derive(Deserialize)]
struct FixtureIndex {
    fixtures: Vec<Fixture>,
}

#[derive(Deserialize)]
struct Fixture {
    fixture_id: String,
    #[serde(default)]
    fixture_type: Option<String>,
    input_paths: std::collections::BTreeMap<String, String>,
    #[serde(default)]
    expected_digests: std::collections::BTreeMap<String, String>,
    #[serde(default)]
    expected_status: Option<String>,
    #[serde(default)]
    expected_error_code: Option<String>,
    #[serde(default)]
    expected_failing_check: Option<String>,
    #[serde(default)]
    expected_backend_id: Option<String>,
    #[serde(default)]
    expected: Option<Expected>,
}

#[derive(Deserialize, Default)]
struct Expected {
    #[serde(default)]
    canonical_sha256: Option<String>,
    #[serde(default)]
    hail_digest: Option<String>,
    #[serde(default)]
    hail_chain_digest: Option<String>,
    #[serde(default)]
    overall_status: Option<String>,
    #[serde(default)]
    error_code: Option<String>,
}

pub fn verify_fixtures(index_path: &Path) -> Result<FixtureSummary> {
    let index: FixtureIndex = serde_json::from_str(&fs::read_to_string(index_path)?)?;
    let repo_root = repo_root_for(index_path)?;
    let mut results = Vec::new();
    let mut passed = 0;
    let mut failed = 0;
    for fixture in index.fixtures {
        match verify_fixture(&repo_root, &fixture) {
            Ok(()) => {
                passed += 1;
                results.push(FixtureResult {
                    fixture_id: fixture.fixture_id,
                    status: "pass".to_string(),
                    message: "ok".to_string(),
                });
            }
            Err(error) => {
                let expected_failure = fixture.expected_status.as_deref() == Some("fail")
                    || fixture
                        .expected
                        .as_ref()
                        .and_then(|expected| expected.overall_status.as_deref())
                        == Some("fail");
                let message = error.to_string();
                let expected_code = fixture.expected_error_code.clone().or_else(|| {
                    fixture
                        .expected
                        .as_ref()
                        .and_then(|expected| expected.error_code.clone())
                });
                if expected_failure
                    && expected_code
                        .as_deref()
                        .is_some_and(|code| message.contains(code))
                    && expected_check_matches(&fixture, &message)
                {
                    passed += 1;
                    results.push(FixtureResult {
                        fixture_id: fixture.fixture_id,
                        status: "pass".to_string(),
                        message: format!("expected failure observed: {message}"),
                    });
                } else {
                    failed += 1;
                    results.push(FixtureResult {
                        fixture_id: fixture.fixture_id,
                        status: "fail".to_string(),
                        message,
                    });
                }
            }
        }
    }
    Ok(FixtureSummary {
        passed,
        failed,
        results,
    })
}

fn repo_root_for(index_path: &Path) -> Result<PathBuf> {
    let mut cursor = fs::canonicalize(index_path)?
        .parent()
        .ok_or_else(|| err("fixture index has no parent"))?
        .to_path_buf();
    loop {
        if cursor.join("pyproject.toml").exists() && cursor.join("tests").exists() {
            return Ok(cursor);
        }
        if !cursor.pop() {
            return Ok(std::env::current_dir()?);
        }
    }
}

fn verify_fixture(repo_root: &Path, fixture: &Fixture) -> Result<()> {
    match fixture_type(fixture).as_str() {
        "canonical_json" => verify_canonical_json(repo_root, fixture),
        "hail_jsonl" => verify_hail_jsonl(repo_root, fixture),
        "hail_chain" => verify_hail_chain_fixture(repo_root, fixture),
        "run_manifest" | "trust_policy" | "signed_conformance" => {
            verify_manifest_and_policy(repo_root, fixture)
        }
        "backend_identity_registry" => verify_backend_identity_registry(repo_root, fixture),
        "backend_capabilities" => verify_backend_capabilities(repo_root, fixture),
        "dmf_capabilities" => verify_dmf_capabilities(repo_root, fixture),
        "dmf_payload" => verify_dmf_payload(repo_root, fixture),
        "artifact" => verify_artifact_fixture(repo_root, fixture),
        "runbook_trace" => verify_runbook_trace_fixture(repo_root, fixture),
        "ecrp" => verify_ecrp_fixture(repo_root, fixture),
        "observation" => verify_observation_fixture(repo_root, fixture),
        "hil" => verify_hil_fixture(repo_root, fixture),
        "recorded_run" => verify_recorded_run_fixture(repo_root, fixture),
        "raw_device_log" => verify_raw_device_log_fixture(repo_root, fixture),
        "dmf_backend_adapter" => verify_dmf_backend_adapter_fixture(repo_root, fixture),
        "opendrop_backend_adapter" => verify_opendrop_backend_adapter_fixture(repo_root, fixture),
        "opendrop_transport" => verify_opendrop_transport_fixture(repo_root, fixture),
        "conformance_levels_catalog" => verify_conformance_levels_catalog(repo_root, fixture),
        "timestamp_profile" => verify_timestamp_profile_fixture(repo_root, fixture),
        "timestamp_token" => verify_timestamp_token_fixture(repo_root, fixture),
        "attestation_profile" => verify_attestation_profile_fixture(repo_root, fixture),
        "attestation_statement" => verify_attestation_statement_fixture(repo_root, fixture),
        "run_bundle" => verify_bundle_fixture(repo_root, fixture),
        other => Err(err(format!("unsupported fixture type: {other}"))),
    }
}

fn verify_dmf_payload(repo_root: &Path, fixture: &Fixture) -> Result<()> {
    let payload: Value =
        serde_json::from_str(&fs::read_to_string(path(repo_root, fixture, "payload")?)?)?;
    validate_dmf_payload_value(&payload)
}

fn verify_artifact_fixture(repo_root: &Path, fixture: &Fixture) -> Result<()> {
    let input = fs::read_to_string(path(repo_root, fixture, "input")?)?;
    let value: Value = serde_json::from_str(&input)?;
    if let Some(expected_hash) = fixture.expected_digests.get("artifact_hash") {
        let actual = canonical_sha256_ref(&value)?;
        compare(&actual, expected_hash, "artifact canonical digest")?;
    }

    if fixture.expected_status.as_deref() == Some("fail") {
        let actual = classify_artifact_error(&value)
            .ok_or_else(|| err("artifact fixture unexpectedly valid"))?;
        let expected = fixture
            .expected_error_code
            .as_deref()
            .or(fixture
                .expected
                .as_ref()
                .and_then(|expected| expected.error_code.as_deref()))
            .ok_or_else(|| err("missing expected_error_code"))?;
        if actual != expected {
            return Err(err(format!(
                "expected artifact error {expected}, got {actual}"
            )));
        }
    }
    Ok(())
}

fn classify_artifact_error(value: &Value) -> Option<&'static str> {
    let obj = value.as_object()?;
    match obj.get("kind").and_then(Value::as_str) {
        Some("KLEIN_PROJECT") => {
            if obj.get("schema_version").and_then(Value::as_str) != Some("v1") {
                return Some("ARTIFACT_UNSUPPORTED_VERSION");
            }
            let profile = obj.get("profile").and_then(Value::as_object);
            if profile
                .and_then(|profile| profile.get("profile_id").and_then(Value::as_str))
                .is_none()
                || profile
                    .and_then(|profile| profile.get("profile_version").and_then(Value::as_str))
                    .is_none()
            {
                return Some("ARTIFACT_PROFILE_MISSING");
            }
            None
        }
        Some("KLEIN_CONTAINER") => {
            if obj.get("schema_version").and_then(Value::as_str) != Some("v1") {
                return Some("ARTIFACT_UNSUPPORTED_VERSION");
            }
            if !obj
                .get("payloads")
                .and_then(Value::as_array)
                .is_some_and(|items| !items.is_empty())
            {
                return Some("ARTIFACT_PAYLOAD_MISSING");
            }
            None
        }
        _ if obj.contains_key("klein_container_version") => {
            if obj.get("klein_container_version").and_then(Value::as_str) != Some("1.0") {
                return Some("ARTIFACT_UNSUPPORTED_VERSION");
            }
            if !obj.contains_key("payload") {
                return Some("ARTIFACT_PAYLOAD_MISSING");
            }
            None
        }
        _ => Some("ARTIFACT_UNSUPPORTED_KIND"),
    }
}

fn verify_runbook_trace_fixture(repo_root: &Path, fixture: &Fixture) -> Result<()> {
    let runbook: Value =
        serde_json::from_str(&fs::read_to_string(path(repo_root, fixture, "runbook")?)?)?;
    if let Some(expected_hash) = fixture.expected_digests.get("runbook_hash") {
        compare(
            &canonical_sha256_ref(&runbook)?,
            expected_hash,
            "runbook canonical digest",
        )?;
    }
    if let Some(trace_path) = fixture.input_paths.get("trace") {
        let trace: Value = serde_json::from_str(&fs::read_to_string(repo_root.join(trace_path))?)?;
        if let Some(expected_hash) = fixture.expected_digests.get("trace_hash") {
            compare(
                &canonical_sha256_ref(&trace)?,
                expected_hash,
                "trace canonical digest",
            )?;
        }
        let comparison = compare_trace_to_runbook_value(&trace, &runbook);
        if fixture.expected_status.as_deref() == Some("fail") {
            let expected = fixture
                .expected_error_code
                .as_deref()
                .ok_or_else(|| err("missing expected_error_code"))?;
            match comparison {
                Ok(()) => return Err(err("trace unexpectedly matched runbook")),
                Err(actual) if actual == expected => {}
                Err(actual) => {
                    return Err(err(format!(
                        "expected trace error {expected}, got {actual}"
                    )))
                }
            }
        } else {
            comparison.map_err(err)?;
        }
    }
    Ok(())
}

fn compare_trace_to_runbook_value(
    trace: &Value,
    runbook: &Value,
) -> std::result::Result<(), &'static str> {
    let runbook_steps = runbook
        .get("planned_steps")
        .and_then(Value::as_array)
        .ok_or("RUNBOOK_SCHEMA_INVALID")?;
    let trace_steps = trace
        .get("trace_steps")
        .and_then(Value::as_array)
        .ok_or("TRACE_SCHEMA_INVALID")?;
    let mut matched = 0;
    for trace_step in trace_steps {
        let runbook_step_id = trace_step
            .get("runbook_step_id")
            .and_then(Value::as_str)
            .ok_or("TRACE_SCHEMA_INVALID")?;
        let planned = runbook_steps
            .iter()
            .find(|step| step.get("step_id").and_then(Value::as_str) == Some(runbook_step_id))
            .ok_or("TRACE_STEP_MISSING")?;
        if planned.get("tick") != trace_step.get("tick")
            || planned.get("operation") != trace_step.get("operation")
        {
            return Err("TRACE_RUNBOOK_MISMATCH");
        }
        matched += 1;
    }
    if matched != runbook_steps.len() {
        return Err("TRACE_STEP_MISSING");
    }
    Ok(())
}

fn verify_ecrp_fixture(repo_root: &Path, fixture: &Fixture) -> Result<()> {
    let policy: Value =
        serde_json::from_str(&fs::read_to_string(path(repo_root, fixture, "policy")?)?)?;
    let policy_result = validate_ecrp_policy_value(&policy);
    if fixture.expected_status.as_deref() == Some("fail") && fixture.input_paths.len() == 1 {
        return ecrp_expected(policy_result, fixture);
    }
    policy_result.map_err(err)?;
    if let Some(hail_path) = fixture.input_paths.get("hail") {
        let events = parse_jsonl(&fs::read_to_string(repo_root.join(hail_path))?)?;
        return ecrp_expected(validate_ecrp_events_value(&events, &policy), fixture);
    }
    if let Some(trace_path) = fixture.input_paths.get("trace") {
        let runbook: Value =
            serde_json::from_str(&fs::read_to_string(path(repo_root, fixture, "runbook")?)?)?;
        let trace: Value = serde_json::from_str(&fs::read_to_string(repo_root.join(trace_path))?)?;
        if trace
            .get("metadata")
            .and_then(|metadata| metadata.get("ecrp_recovery_status"))
            .and_then(Value::as_str)
            == Some("success")
        {
            return ecrp_expected(validate_ecrp_success_trace_value(&trace, &policy), fixture);
        }
        let result = compare_trace_to_runbook_value(&trace, &runbook)
            .map_err(|code| {
                if code == "TRACE_STEP_MISSING" {
                    "ECRP_TRACE_EVIDENCE_MISSING"
                } else {
                    code
                }
            })
            .and_then(|_| {
                let has_failed_step = trace
                    .get("trace_steps")
                    .and_then(Value::as_array)
                    .into_iter()
                    .flatten()
                    .any(|step| step.get("status").and_then(Value::as_str) == Some("FAILED"));
                if !has_failed_step
                    && fixture.expected_error_code.as_deref() == Some("ECRP_TRACE_EVIDENCE_MISSING")
                {
                    Err("ECRP_TRACE_EVIDENCE_MISSING")
                } else {
                    Ok(())
                }
            });
        return ecrp_expected(result, fixture);
    }
    Ok(())
}

fn ecrp_expected(result: std::result::Result<(), &'static str>, fixture: &Fixture) -> Result<()> {
    if fixture.expected_status.as_deref() == Some("fail") {
        let expected = fixture
            .expected_error_code
            .as_deref()
            .ok_or_else(|| err("missing expected_error_code"))?;
        match result {
            Ok(()) => Err(err("ECRP fixture unexpectedly valid")),
            Err(actual) if actual == expected => Ok(()),
            Err(actual) => Err(err(format!("expected ECRP error {expected}, got {actual}"))),
        }
    } else {
        result.map_err(err)
    }
}

fn validate_ecrp_policy_value(policy: &Value) -> std::result::Result<(), &'static str> {
    if policy.get("ecrp_policy_version").and_then(Value::as_str) != Some("klein.ecrp_policy.v1") {
        return Err("ECRP_POLICY_SCHEMA_INVALID");
    }
    let max_attempts = policy
        .get("max_attempts")
        .and_then(Value::as_i64)
        .ok_or("ECRP_POLICY_SCHEMA_INVALID")?;
    if max_attempts < 0 {
        return Err("ECRP_POLICY_SCHEMA_INVALID");
    }
    let strategies = policy
        .get("allowed_strategies")
        .and_then(Value::as_array)
        .ok_or("ECRP_POLICY_SCHEMA_INVALID")?;
    for strategy in strategies {
        match strategy.as_str() {
            Some(
                "NUDGE_PULSE" | "NO_CHANGE" | "RETRY_SAME_STEP" | "REPLAN_AROUND_FAULT" | "ABORT",
            ) => {}
            _ => return Err("ECRP_STRATEGY_UNKNOWN"),
        }
    }
    let success_strategies = policy
        .get("allowed_success_strategies")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    for strategy in &success_strategies {
        match strategy.as_str() {
            Some(
                "NUDGE_PULSE" | "NO_CHANGE" | "RETRY_SAME_STEP" | "REPLAN_AROUND_FAULT" | "ABORT",
            ) => {}
            _ => return Err("ECRP_STRATEGY_UNKNOWN"),
        }
    }
    if policy
        .get("allow_success_after_replan")
        .and_then(Value::as_bool)
        == Some(true)
        && policy.get("allow_replan").and_then(Value::as_bool) != Some(true)
    {
        return Err("ECRP_POLICY_INVALID");
    }
    if policy.get("mode").and_then(Value::as_str) == Some("HARD")
        && policy.get("allow_replan").and_then(Value::as_bool) == Some(true)
    {
        return Err("ECRP_REPLAN_NOT_ALLOWED");
    }
    if policy
        .get("allow_success_after_retry")
        .and_then(Value::as_bool)
        == Some(true)
        && success_strategies.is_empty()
    {
        return Err("ECRP_POLICY_INVALID");
    }
    Ok(())
}

fn validate_ecrp_events_value(
    events: &[Value],
    policy: &Value,
) -> std::result::Result<(), &'static str> {
    let max_attempts = policy
        .get("max_attempts")
        .and_then(Value::as_i64)
        .unwrap_or(0);
    let allowed: std::collections::BTreeSet<&str> = policy
        .get("allowed_strategies")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(Value::as_str)
        .collect();
    let allowed_success: std::collections::BTreeSet<&str> = policy
        .get("allowed_success_strategies")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(Value::as_str)
        .collect();
    let attempts: Vec<&Value> = events
        .iter()
        .filter(|event| event.get("kind").and_then(Value::as_str) == Some("ECRP_ATTEMPT"))
        .collect();
    if attempts.len() as i64 > max_attempts {
        return Err("ECRP_ATTEMPTS_EXCEEDED");
    }
    for (idx, attempt) in attempts.iter().enumerate() {
        if attempt.get("attempt_index").and_then(Value::as_i64) != Some((idx + 1) as i64) {
            return Err("ECRP_ATTEMPT_SEQUENCE_INVALID");
        }
        let strategy = attempt
            .get("strategy")
            .and_then(Value::as_str)
            .ok_or("ECRP_ATTEMPT_SEQUENCE_INVALID")?;
        if !allowed.contains(strategy) {
            return Err("ECRP_STRATEGY_NOT_ALLOWED");
        }
        if attempt.get("outcome").and_then(Value::as_str) == Some("SUCCESS") {
            let retry_allowed = policy
                .get("allow_success_after_retry")
                .and_then(Value::as_bool)
                == Some(true);
            let replan_allowed = policy
                .get("allow_success_after_replan")
                .and_then(Value::as_bool)
                == Some(true);
            if !retry_allowed && !replan_allowed {
                return Err("ECRP_RECOVERY_SUCCESS_NOT_ALLOWED");
            }
            if !allowed_success.contains(strategy) {
                return Err("ECRP_RECOVERY_STRATEGY_NOT_ALLOWED");
            }
        }
    }
    let has_success = attempts
        .iter()
        .any(|attempt| attempt.get("outcome").and_then(Value::as_str) == Some("SUCCESS"));
    let terminal = events.iter().any(|event| {
        event.get("kind").and_then(Value::as_str) == Some("DEVICE_EVENT")
            && event.get("level").and_then(Value::as_str) == Some("ERROR")
            && event.get("code").and_then(Value::as_str) != Some("ECRP_BOUNDS_EXCEEDED")
    });
    if !attempts.is_empty()
        && policy
            .get("terminal_failure_required")
            .and_then(Value::as_bool)
            == Some(true)
        && !terminal
        && !has_success
    {
        return Err("ECRP_TERMINAL_FAILURE_MISSING");
    }
    Ok(())
}

fn validate_ecrp_success_trace_value(
    trace: &Value,
    policy: &Value,
) -> std::result::Result<(), &'static str> {
    if policy
        .get("allow_success_after_retry")
        .and_then(Value::as_bool)
        != Some(true)
    {
        return Err("ECRP_RECOVERY_SUCCESS_NOT_ALLOWED");
    }
    let allowed_success: std::collections::BTreeSet<&str> = policy
        .get("allowed_success_strategies")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(Value::as_str)
        .collect();
    let steps = trace
        .get("trace_steps")
        .and_then(Value::as_array)
        .ok_or("TRACE_SCHEMA_INVALID")?;
    let failed = steps
        .iter()
        .any(|step| step.get("status").and_then(Value::as_str) == Some("FAILED"));
    if !failed {
        return Err("ECRP_RECOVERY_EVIDENCE_MISSING");
    }
    let success_step = steps.iter().find(|step| {
        step.get("details")
            .and_then(|details| details.get("recovery_status"))
            .and_then(Value::as_str)
            == Some("success")
    });
    let Some(success_step) = success_step else {
        return Err("ECRP_RECOVERY_EVIDENCE_MISSING");
    };
    let strategy = success_step
        .get("details")
        .and_then(|details| details.get("recovery_strategy"))
        .and_then(Value::as_str)
        .ok_or("ECRP_RECOVERY_EVIDENCE_MISSING")?;
    if !allowed_success.contains(strategy) {
        return Err("ECRP_RECOVERY_STRATEGY_NOT_ALLOWED");
    }
    if success_step
        .get("runbook_step_id")
        .and_then(Value::as_str)
        .is_none()
    {
        return Err("ECRP_RETRY_STEP_MISSING");
    }
    Ok(())
}

fn verify_observation_fixture(repo_root: &Path, fixture: &Fixture) -> Result<()> {
    if let Some(policy_path) = fixture.input_paths.get("policy") {
        let policy: Value =
            serde_json::from_str(&fs::read_to_string(repo_root.join(policy_path))?)?;
        let policy_result = validate_observation_policy_value(&policy);
        if fixture.expected_status.as_deref() == Some("fail") && fixture.input_paths.len() == 1 {
            return observation_expected(policy_result, fixture);
        }
        policy_result.map_err(err)?;
    }
    if let Some(observation_path) = fixture.input_paths.get("observation") {
        let observation: Value =
            serde_json::from_str(&fs::read_to_string(repo_root.join(observation_path))?)?;
        if let Some(expected_hash) = fixture.expected_digests.get("observation_hash") {
            compare(
                &canonical_sha256_ref(&observation)?,
                expected_hash,
                "observation canonical digest",
            )?;
        }
        let snapshot_result = validate_observation_snapshot_value(&observation);
        if fixture.expected_status.as_deref() == Some("fail") && fixture.input_paths.len() == 1 {
            return observation_expected(snapshot_result, fixture);
        }
        snapshot_result.map_err(err)?;
        if let Some(trace_path) = fixture.input_paths.get("trace") {
            let trace: Value =
                serde_json::from_str(&fs::read_to_string(repo_root.join(trace_path))?)?;
            return observation_expected(
                compare_observation_to_trace_value(&observation, &trace),
                fixture,
            );
        }
    }
    Ok(())
}

fn observation_expected(
    result: std::result::Result<(), &'static str>,
    fixture: &Fixture,
) -> Result<()> {
    if fixture.expected_status.as_deref() == Some("fail") {
        let expected = fixture
            .expected_error_code
            .as_deref()
            .ok_or_else(|| err("missing expected_error_code"))?;
        match result {
            Ok(()) => Err(err("observation fixture unexpectedly valid")),
            Err(actual) if actual == expected => Ok(()),
            Err(actual) => Err(err(format!(
                "expected observation error {expected}, got {actual}"
            ))),
        }
    } else {
        result.map_err(err)
    }
}

fn verify_hil_fixture(repo_root: &Path, fixture: &Fixture) -> Result<()> {
    if let Some(contract_path) = fixture.input_paths.get("contract") {
        let contract: Value =
            serde_json::from_str(&fs::read_to_string(repo_root.join(contract_path))?)?;
        return hil_expected(validate_hil_contract_value(&contract), fixture);
    }
    if let Some(status_path) = fixture.input_paths.get("status") {
        let status: Value =
            serde_json::from_str(&fs::read_to_string(repo_root.join(status_path))?)?;
        return hil_expected(validate_hil_status_value(&status), fixture);
    }
    Err(err("hil fixture missing contract or status input"))
}

fn hil_expected(result: std::result::Result<(), &'static str>, fixture: &Fixture) -> Result<()> {
    if fixture.expected_status.as_deref() == Some("fail") {
        let expected = fixture
            .expected_error_code
            .as_deref()
            .ok_or_else(|| err("missing expected_error_code"))?;
        match result {
            Ok(()) => Err(err("hil fixture unexpectedly valid")),
            Err(actual) if actual == expected => Ok(()),
            Err(actual) => Err(err(format!("expected hil error {expected}, got {actual}"))),
        }
    } else {
        result.map_err(err)
    }
}

fn validate_hil_contract_value(contract: &Value) -> std::result::Result<(), &'static str> {
    if contract.get("hil_contract_version").and_then(Value::as_str)
        != Some("klein.hil_backend_contract.v1")
    {
        return Err("HIL_CONTRACT_SCHEMA_INVALID");
    }
    let supports = contract
        .get("supports")
        .and_then(Value::as_object)
        .ok_or("HIL_CONTRACT_SCHEMA_INVALID")?;
    for operation in [
        "connect",
        "disconnect",
        "get_capabilities",
        "get_topology",
        "get_health",
        "apply_frame",
        "read_observation",
        "emergency_stop",
        "reset",
    ] {
        if supports.get(operation).and_then(Value::as_bool) != Some(true) {
            if operation == "emergency_stop" {
                return Err("HIL_ESTOP_REQUIRED");
            }
            return Err("HIL_OPERATION_UNSUPPORTED");
        }
    }
    let safety = contract
        .get("safety")
        .and_then(Value::as_object)
        .ok_or("HIL_CONTRACT_SCHEMA_INVALID")?;
    if safety
        .get("requires_emergency_stop")
        .and_then(Value::as_bool)
        != Some(true)
    {
        return Err("HIL_ESTOP_REQUIRED");
    }
    let attestation = contract
        .get("attestation")
        .and_then(Value::as_object)
        .ok_or("HIL_CONTRACT_SCHEMA_INVALID")?;
    if attestation.get("supported").and_then(Value::as_bool) == Some(true) {
        return Err("HIL_ATTESTATION_UNSUPPORTED");
    }
    if contract
        .get("observation_sources")
        .and_then(Value::as_array)
        .is_some_and(|sources| {
            sources
                .iter()
                .any(|source| source.as_str() == Some("hardware_sensor"))
        })
    {
        return Err("HIL_HARDWARE_CLAIM_UNSUPPORTED");
    }
    Ok(())
}

fn validate_hil_status_value(status: &Value) -> std::result::Result<(), &'static str> {
    if status.get("hil_status_version").and_then(Value::as_str)
        != Some("klein.hil_backend_status.v1")
    {
        return Err("HIL_STATUS_SCHEMA_INVALID");
    }
    let health = status
        .get("health")
        .and_then(Value::as_str)
        .ok_or("HIL_STATUS_INVALID")?;
    if !["OK", "DEGRADED", "FAULTED", "UNKNOWN"].contains(&health) {
        return Err("HIL_STATUS_INVALID");
    }
    if health == "FAULTED" && status.get("last_error_code").is_none_or(Value::is_null) {
        return Err("HIL_FAULT_MISSING_ERROR");
    }
    Ok(())
}

fn verify_recorded_run_fixture(repo_root: &Path, fixture: &Fixture) -> Result<()> {
    let recorded_run_path = fixture
        .input_paths
        .get("recorded_run")
        .ok_or_else(|| err("recorded_run fixture missing recorded_run input"))?;
    let recorded_run: Value =
        serde_json::from_str(&fs::read_to_string(repo_root.join(recorded_run_path))?)?;
    recorded_run_expected(validate_recorded_run_value(&recorded_run), fixture)
}

fn verify_raw_device_log_fixture(repo_root: &Path, fixture: &Fixture) -> Result<()> {
    let raw_log_path = fixture
        .input_paths
        .get("raw_log")
        .ok_or_else(|| err("raw_device_log fixture missing raw_log input"))?;
    let text = fs::read_to_string(repo_root.join(raw_log_path))?;
    let mut events = Vec::new();
    for line in text.lines().filter(|line| !line.trim().is_empty()) {
        events.push(serde_json::from_str::<Value>(line)?);
    }
    recorded_run_expected(validate_raw_device_log_values(&events), fixture)
}

fn recorded_run_expected(
    result: std::result::Result<(), &'static str>,
    fixture: &Fixture,
) -> Result<()> {
    if fixture.expected_status.as_deref() == Some("fail") {
        let expected = fixture
            .expected_error_code
            .as_deref()
            .ok_or_else(|| err("missing expected_error_code"))?;
        match result {
            Ok(()) => Err(err("recorded run fixture unexpectedly valid")),
            Err(actual) if actual == expected => Ok(()),
            Err(actual) => Err(err(format!(
                "expected recorded run error {expected}, got {actual}"
            ))),
        }
    } else {
        result.map_err(err)
    }
}

fn validate_recorded_run_value(recorded_run: &Value) -> std::result::Result<(), &'static str> {
    if recorded_run
        .get("recorded_run_version")
        .and_then(Value::as_str)
        != Some("klein.recorded_device_run.v1")
    {
        return Err("RECORDED_RUN_SCHEMA_INVALID");
    }
    let source_type = recorded_run
        .get("source_type")
        .and_then(Value::as_str)
        .ok_or("RECORDED_RUN_SCHEMA_INVALID")?;
    if source_type == "hardware"
        || recorded_run
            .get("hardware_claimed")
            .and_then(Value::as_bool)
            == Some(true)
    {
        return Err("RECORDED_RUN_HARDWARE_CLAIM_UNSUPPORTED");
    }
    if !recorded_run.get("attestation").is_none_or(Value::is_null) {
        return Err("RECORDED_RUN_ATTESTATION_UNSUPPORTED");
    }
    if !recorded_run
        .get("trusted_timestamp")
        .is_none_or(Value::is_null)
    {
        return Err("RECORDED_RUN_TIMESTAMP_UNSUPPORTED");
    }
    recorded_run
        .get("artifact_hash")
        .and_then(Value::as_str)
        .filter(|value| is_sha256_ref(value))
        .ok_or("RECORDED_RUN_SCHEMA_INVALID")?;
    let raw_logs = recorded_run
        .get("raw_device_logs")
        .and_then(Value::as_array)
        .ok_or("RECORDED_RUN_SCHEMA_INVALID")?;
    for raw_log in raw_logs {
        let source = raw_log
            .get("source_type")
            .and_then(Value::as_str)
            .ok_or("RECORDED_RUN_SCHEMA_INVALID")?;
        if source == "hardware" {
            return Err("RECORDED_RUN_HARDWARE_CLAIM_UNSUPPORTED");
        }
        raw_log
            .get("sha256")
            .and_then(Value::as_str)
            .filter(|value| is_sha256_ref(value))
            .ok_or("RECORDED_RUN_SCHEMA_INVALID")?;
    }
    Ok(())
}

fn validate_raw_device_log_values(events: &[Value]) -> std::result::Result<(), &'static str> {
    for (index, event) in events.iter().enumerate() {
        if event.get("raw_log_version").and_then(Value::as_str) != Some("klein.raw_device_log.v1") {
            return Err("RAW_DEVICE_LOG_SCHEMA_INVALID");
        }
        if event.get("event_index").and_then(Value::as_u64) != Some((index + 1) as u64) {
            return Err("RAW_DEVICE_LOG_ORDER_INVALID");
        }
        if event.get("source_type").and_then(Value::as_str) == Some("hardware") {
            return Err("RECORDED_RUN_HARDWARE_CLAIM_UNSUPPORTED");
        }
        match event.get("status").and_then(Value::as_str) {
            Some("OK") => {}
            Some("ERROR") => {
                if event.get("error_code").and_then(Value::as_str).is_none() {
                    return Err("RAW_DEVICE_LOG_ERROR_CODE_MISSING");
                }
            }
            _ => return Err("RAW_DEVICE_LOG_SCHEMA_INVALID"),
        }
    }
    Ok(())
}

fn is_sha256_ref(value: &str) -> bool {
    value.len() == 71
        && value.starts_with("sha256:")
        && value[7..]
            .chars()
            .all(|ch| ch.is_ascii_hexdigit() && !ch.is_ascii_uppercase())
}

fn verify_dmf_backend_adapter_fixture(repo_root: &Path, fixture: &Fixture) -> Result<()> {
    if let Some(config_path) = fixture.input_paths.get("config") {
        let config: Value =
            serde_json::from_str(&fs::read_to_string(repo_root.join(config_path))?)?;
        return dmf_adapter_expected(validate_dmf_adapter_config_value(&config), fixture);
    }
    if let Some(status_path) = fixture.input_paths.get("status") {
        let status: Value =
            serde_json::from_str(&fs::read_to_string(repo_root.join(status_path))?)?;
        return dmf_adapter_expected(validate_dmf_adapter_status_value(&status), fixture);
    }
    Err(err(
        "dmf_backend_adapter fixture missing config or status input",
    ))
}

fn dmf_adapter_expected(
    result: std::result::Result<(), &'static str>,
    fixture: &Fixture,
) -> Result<()> {
    if fixture.expected_status.as_deref() == Some("fail") {
        let expected = fixture
            .expected_error_code
            .as_deref()
            .ok_or_else(|| err("missing expected_error_code"))?;
        match result {
            Ok(()) => Err(err("dmf adapter fixture unexpectedly valid")),
            Err(actual) if actual == expected => Ok(()),
            Err(actual) => Err(err(format!(
                "expected dmf adapter error {expected}, got {actual}"
            ))),
        }
    } else {
        result.map_err(err)
    }
}

fn validate_dmf_adapter_config_value(config: &Value) -> std::result::Result<(), &'static str> {
    if config.get("adapter_config_version").and_then(Value::as_str)
        != Some("klein.dmf_backend_adapter_config.v1")
    {
        return Err("DMF_ADAPTER_SCHEMA_INVALID");
    }
    let profile = config
        .get("profile")
        .and_then(Value::as_object)
        .ok_or("DMF_ADAPTER_SCHEMA_INVALID")?;
    if profile.get("profile_id").and_then(Value::as_str) != Some("dmf")
        || profile.get("profile_version").and_then(Value::as_str) != Some("v1")
    {
        return Err("DMF_ADAPTER_PROFILE_UNSUPPORTED");
    }
    if !matches!(
        config.get("mode").and_then(Value::as_str),
        Some("dry_run" | "mock")
    ) {
        return Err("DMF_ADAPTER_HARDWARE_IO_UNSUPPORTED");
    }
    if config.get("hardware_io_enabled").and_then(Value::as_bool) == Some(true) {
        return Err("DMF_ADAPTER_HARDWARE_IO_UNSUPPORTED");
    }
    let safety = config
        .get("safety")
        .and_then(Value::as_object)
        .ok_or("DMF_ADAPTER_SCHEMA_INVALID")?;
    if safety.get("require_estop").and_then(Value::as_bool) != Some(true) {
        return Err("DMF_ADAPTER_ESTOP_REQUIRED");
    }
    if safety.get("allow_hardware_io").and_then(Value::as_bool) == Some(true) {
        return Err("DMF_ADAPTER_HARDWARE_IO_UNSUPPORTED");
    }
    Ok(())
}

fn validate_dmf_adapter_status_value(status: &Value) -> std::result::Result<(), &'static str> {
    if status.get("adapter_status_version").and_then(Value::as_str)
        != Some("klein.dmf_backend_adapter_status.v1")
    {
        return Err("DMF_ADAPTER_STATUS_INVALID");
    }
    if status.get("hardware_io_enabled").and_then(Value::as_bool) == Some(true) {
        return Err("DMF_ADAPTER_HARDWARE_IO_UNSUPPORTED");
    }
    let health = status
        .get("health")
        .and_then(Value::as_str)
        .ok_or("DMF_ADAPTER_STATUS_INVALID")?;
    if !["OK", "DEGRADED", "FAULTED", "UNKNOWN"].contains(&health) {
        return Err("DMF_ADAPTER_STATUS_INVALID");
    }
    if health == "FAULTED" && status.get("last_error_code").is_none_or(Value::is_null) {
        return Err("DMF_ADAPTER_STATUS_INVALID");
    }
    Ok(())
}

fn verify_opendrop_backend_adapter_fixture(repo_root: &Path, fixture: &Fixture) -> Result<()> {
    if let Some(config_path) = fixture.input_paths.get("config") {
        let config: Value =
            serde_json::from_str(&fs::read_to_string(repo_root.join(config_path))?)?;
        return dmf_adapter_expected(validate_opendrop_adapter_config_value(&config), fixture);
    }
    if let Some(status_path) = fixture.input_paths.get("status") {
        let status: Value =
            serde_json::from_str(&fs::read_to_string(repo_root.join(status_path))?)?;
        return dmf_adapter_expected(validate_opendrop_adapter_status_value(&status), fixture);
    }
    if let Some(intent_path) = fixture.input_paths.get("intent") {
        let intent: Value =
            serde_json::from_str(&fs::read_to_string(repo_root.join(intent_path))?)?;
        return dmf_adapter_expected(validate_opendrop_command_intent_value(&intent), fixture);
    }
    Err(err(
        "opendrop_backend_adapter fixture missing config, status, or intent input",
    ))
}

fn validate_opendrop_adapter_config_value(config: &Value) -> std::result::Result<(), &'static str> {
    if config.get("adapter_config_version").and_then(Value::as_str)
        != Some("klein.opendrop_adapter_config.v1")
    {
        return Err("OPENDROP_ADAPTER_SCHEMA_INVALID");
    }
    if config.get("adapter_kind").and_then(Value::as_str) != Some("opendrop_ewod") {
        return Err("OPENDROP_ADAPTER_SCHEMA_INVALID");
    }
    let profile = config
        .get("profile")
        .and_then(Value::as_object)
        .ok_or("OPENDROP_ADAPTER_SCHEMA_INVALID")?;
    if profile.get("profile_id").and_then(Value::as_str) != Some("dmf")
        || profile.get("profile_version").and_then(Value::as_str) != Some("v1")
    {
        return Err("DMF_ADAPTER_PROFILE_UNSUPPORTED");
    }
    if !matches!(
        config.get("mode").and_then(Value::as_str),
        Some("dry_run" | "mock")
    ) {
        return Err("OPENDROP_HARDWARE_IO_UNSUPPORTED");
    }
    if config.get("hardware_io_enabled").and_then(Value::as_bool) == Some(true) {
        return Err("OPENDROP_HARDWARE_IO_UNSUPPORTED");
    }
    let transport = config
        .get("transport")
        .and_then(Value::as_object)
        .ok_or("OPENDROP_ADAPTER_SCHEMA_INVALID")?;
    if transport.get("transport_kind").and_then(Value::as_str) != Some("none")
        || !transport.get("endpoint").is_none_or(Value::is_null)
    {
        return Err("OPENDROP_TRANSPORT_UNSUPPORTED");
    }
    let safety = config
        .get("safety")
        .and_then(Value::as_object)
        .ok_or("OPENDROP_ADAPTER_SCHEMA_INVALID")?;
    if safety.get("require_estop").and_then(Value::as_bool) != Some(true) {
        return Err("DMF_ADAPTER_ESTOP_REQUIRED");
    }
    if safety.get("allow_hardware_io").and_then(Value::as_bool) == Some(true) {
        return Err("OPENDROP_HARDWARE_IO_UNSUPPORTED");
    }
    let layout = config
        .get("electrode_layout")
        .and_then(Value::as_object)
        .ok_or("OPENDROP_MAPPING_INVALID")?;
    let channel_count = layout
        .get("channel_count")
        .and_then(Value::as_u64)
        .ok_or("OPENDROP_MAPPING_INVALID")?;
    if channel_count == 0 {
        return Err("OPENDROP_MAPPING_INVALID");
    }
    if layout.get("mapping").and_then(Value::as_str) == Some("explicit") {
        validate_opendrop_explicit_mapping(layout, channel_count)?;
    }
    Ok(())
}

fn validate_opendrop_explicit_mapping(
    layout: &serde_json::Map<String, Value>,
    channel_count: u64,
) -> std::result::Result<(), &'static str> {
    let entries = layout
        .get("explicit_mapping")
        .and_then(Value::as_array)
        .ok_or("OPENDROP_MAPPING_INVALID")?;
    let mut channels = std::collections::BTreeSet::new();
    let mut electrodes = std::collections::BTreeSet::new();
    let mut coords = std::collections::BTreeSet::new();
    for entry in entries {
        let channel_id = entry
            .get("channel_id")
            .and_then(Value::as_u64)
            .ok_or("OPENDROP_MAPPING_INVALID")?;
        let electrode_id = entry
            .get("electrode_id")
            .and_then(Value::as_str)
            .ok_or("OPENDROP_MAPPING_INVALID")?;
        let x = entry
            .get("x")
            .and_then(Value::as_u64)
            .ok_or("OPENDROP_MAPPING_INVALID")?;
        let y = entry
            .get("y")
            .and_then(Value::as_u64)
            .ok_or("OPENDROP_MAPPING_INVALID")?;
        if channel_id == 0 || channel_id > channel_count {
            return Err("OPENDROP_CHANNEL_OOB");
        }
        if !channels.insert(channel_id)
            || !electrodes.insert(electrode_id.to_string())
            || !coords.insert((x, y))
        {
            return Err("OPENDROP_MAPPING_DUPLICATE");
        }
    }
    Ok(())
}

fn validate_opendrop_adapter_status_value(status: &Value) -> std::result::Result<(), &'static str> {
    if status.get("adapter_status_version").and_then(Value::as_str)
        != Some("klein.opendrop_adapter_status.v1")
    {
        return Err("OPENDROP_ADAPTER_SCHEMA_INVALID");
    }
    if status.get("hardware_io_enabled").and_then(Value::as_bool) == Some(true) {
        return Err("OPENDROP_HARDWARE_IO_UNSUPPORTED");
    }
    let health = status
        .get("health")
        .and_then(Value::as_str)
        .ok_or("OPENDROP_ADAPTER_SCHEMA_INVALID")?;
    if !["OK", "DEGRADED", "FAULTED", "UNKNOWN"].contains(&health) {
        return Err("OPENDROP_ADAPTER_SCHEMA_INVALID");
    }
    if health == "FAULTED" && status.get("last_error_code").is_none_or(Value::is_null) {
        return Err("OPENDROP_ADAPTER_SCHEMA_INVALID");
    }
    Ok(())
}

fn validate_opendrop_command_intent_value(intent: &Value) -> std::result::Result<(), &'static str> {
    if intent.get("command_intent_version").and_then(Value::as_str)
        != Some("klein.opendrop_command_intent.v1")
    {
        return Err("OPENDROP_COMMAND_INTENT_INVALID");
    }
    if !matches!(
        intent.get("operation").and_then(Value::as_str),
        Some("SET_ELECTRODES" | "APPLY_FRAME" | "CLEAR_ELECTRODES" | "ESTOP" | "RESET")
    ) {
        return Err("OPENDROP_COMMAND_INTENT_INVALID");
    }
    let electrodes = intent
        .get("electrodes")
        .and_then(Value::as_array)
        .ok_or("OPENDROP_COMMAND_INTENT_INVALID")?;
    for electrode in electrodes {
        let channel_id = electrode
            .get("channel_id")
            .and_then(Value::as_u64)
            .ok_or("OPENDROP_CHANNEL_OOB")?;
        if channel_id == 0 || channel_id > 128 {
            return Err("OPENDROP_CHANNEL_OOB");
        }
        if !matches!(
            electrode.get("state").and_then(Value::as_str),
            Some("ON" | "OFF")
        ) {
            return Err("OPENDROP_COMMAND_INTENT_INVALID");
        }
    }
    Ok(())
}

fn verify_opendrop_transport_fixture(repo_root: &Path, fixture: &Fixture) -> Result<()> {
    if let Some(transport_path) = fixture.input_paths.get("transport") {
        let transport: Value =
            serde_json::from_str(&fs::read_to_string(repo_root.join(transport_path))?)?;
        return dmf_adapter_expected(
            validate_opendrop_transport_config_value(&transport),
            fixture,
        );
    }
    if let Some(command_path) = fixture.input_paths.get("command") {
        let command: Value =
            serde_json::from_str(&fs::read_to_string(repo_root.join(command_path))?)?;
        return dmf_adapter_expected(validate_opendrop_serial_command_value(&command), fixture);
    }
    if let Some(stream_path) = fixture.input_paths.get("command_stream") {
        for line in fs::read_to_string(repo_root.join(stream_path))?.lines() {
            if line.trim().is_empty() {
                continue;
            }
            let command: Value = serde_json::from_str(line)?;
            validate_opendrop_serial_command_value(&command).map_err(err)?;
        }
        return Ok(());
    }
    Err(err(
        "opendrop_transport fixture missing transport, command, or command_stream input",
    ))
}

fn validate_opendrop_transport_config_value(
    config: &Value,
) -> std::result::Result<(), &'static str> {
    if config
        .get("transport_config_version")
        .and_then(Value::as_str)
        != Some("klein.opendrop_transport_config.v1")
    {
        return Err("OPENDROP_TRANSPORT_SCHEMA_INVALID");
    }
    let transport_kind = config
        .get("transport_kind")
        .and_then(Value::as_str)
        .ok_or("OPENDROP_TRANSPORT_SCHEMA_INVALID")?;
    if !["none", "serial_experimental"].contains(&transport_kind) {
        return Err("OPENDROP_TRANSPORT_UNSUPPORTED");
    }
    if config.get("hardware_io_enabled").and_then(Value::as_bool) == Some(true) {
        return Err("OPENDROP_HARDWARE_IO_UNSUPPORTED");
    }
    if transport_kind == "serial_experimental"
        && config
            .get("requires_explicit_enable")
            .and_then(Value::as_bool)
            != Some(true)
    {
        return Err("OPENDROP_TRANSPORT_CONFIG_INVALID");
    }
    if !config.get("endpoint").is_none_or(Value::is_null)
        || !config.get("baud_rate").is_none_or(Value::is_null)
    {
        return Err("OPENDROP_ENDPOINT_UNSUPPORTED_CURRENT_ALPHA");
    }
    if config.get("protocol_family").and_then(Value::as_str) != Some("opendrop_arduino_style") {
        return Err("OPENDROP_TRANSPORT_CONFIG_INVALID");
    }
    if !matches!(
        config.get("command_encoding").and_then(Value::as_str),
        Some("jsonl" | "text_lines")
    ) {
        return Err("OPENDROP_TRANSPORT_CONFIG_INVALID");
    }
    if config
        .get("untested_hardware_warning")
        .and_then(Value::as_bool)
        != Some(true)
    {
        return Err("OPENDROP_TRANSPORT_CONFIG_INVALID");
    }
    if !config
        .get("limitations")
        .and_then(Value::as_array)
        .is_some_and(|items| !items.is_empty())
    {
        return Err("OPENDROP_TRANSPORT_CONFIG_INVALID");
    }
    Ok(())
}

fn validate_opendrop_serial_command_value(
    command: &Value,
) -> std::result::Result<(), &'static str> {
    if command
        .get("serial_command_version")
        .and_then(Value::as_str)
        != Some("klein.opendrop_serial_command.v1")
    {
        return Err("OPENDROP_SERIAL_COMMAND_INVALID");
    }
    if !matches!(
        command.get("command_kind").and_then(Value::as_str),
        Some("SET_ELECTRODES" | "APPLY_FRAME" | "CLEAR_ELECTRODES" | "ESTOP" | "RESET")
    ) {
        return Err("OPENDROP_SERIAL_COMMAND_INVALID");
    }
    if command.get("hardware_io_allowed").and_then(Value::as_bool) != Some(false) {
        return Err("OPENDROP_HARDWARE_IO_UNSUPPORTED");
    }
    if !matches!(
        command.get("encoding").and_then(Value::as_str),
        Some("json" | "text")
    ) {
        return Err("OPENDROP_SERIAL_COMMAND_INVALID");
    }
    if command.get("payload").and_then(Value::as_object).is_none() {
        return Err("OPENDROP_SERIAL_COMMAND_INVALID");
    }
    if command
        .get("raw_line")
        .and_then(Value::as_str)
        .is_none_or(str::is_empty)
    {
        return Err("OPENDROP_SERIAL_COMMAND_INVALID");
    }
    if command.get("tick").and_then(Value::as_u64).is_none() {
        return Err("OPENDROP_SERIAL_COMMAND_INVALID");
    }
    Ok(())
}

fn verify_timestamp_profile_fixture(repo_root: &Path, fixture: &Fixture) -> Result<()> {
    let profile: Value =
        serde_json::from_str(&fs::read_to_string(path(repo_root, fixture, "profile")?)?)?;
    validate_timestamp_profile_value(&profile).map_err(err)
}

fn verify_timestamp_token_fixture(repo_root: &Path, fixture: &Fixture) -> Result<()> {
    let token: Value =
        serde_json::from_str(&fs::read_to_string(path(repo_root, fixture, "token")?)?)?;
    validate_timestamp_token_value(&token).map_err(err)?;
    if let Some(expected_hash) = fixture.expected_digests.get("target_hash") {
        let actual = token
            .get("target")
            .and_then(|target| target.get("target_hash"))
            .and_then(Value::as_str)
            .ok_or_else(|| err("TIMESTAMP_TOKEN_SCHEMA_INVALID"))?;
        if actual != expected_hash {
            return Err(err("TIMESTAMP_TARGET_HASH_MISMATCH"));
        }
    }
    Ok(())
}

fn validate_timestamp_profile_value(profile: &Value) -> std::result::Result<(), &'static str> {
    if profile
        .get("timestamp_profile_version")
        .and_then(Value::as_str)
        != Some("klein.timestamp_profile.v1")
    {
        return Err("TIMESTAMP_PROFILE_SCHEMA_INVALID");
    }
    if profile.get("profile_kind").and_then(Value::as_str) != Some("mock_local") {
        return Err("TIMESTAMP_PROFILE_INVALID");
    }
    if profile.get("trusted_time_claimed").and_then(Value::as_bool) != Some(false) {
        return Err("TIMESTAMP_TRUSTED_TIME_UNSUPPORTED");
    }
    if profile
        .get("requires_external_time_authority")
        .and_then(Value::as_bool)
        != Some(false)
    {
        return Err("TIMESTAMP_TSA_UNSUPPORTED");
    }
    let allowed = profile
        .get("allowed_token_kinds")
        .and_then(Value::as_array)
        .ok_or("TIMESTAMP_PROFILE_SCHEMA_INVALID")?;
    if allowed.len() != 1 || allowed.first().and_then(Value::as_str) != Some("mock_local") {
        return Err("TIMESTAMP_PROFILE_INVALID");
    }
    if !profile
        .get("trust_roots")
        .and_then(Value::as_array)
        .is_some_and(Vec::is_empty)
    {
        return Err("TIMESTAMP_PROFILE_INVALID");
    }
    Ok(())
}

fn validate_timestamp_token_value(token: &Value) -> std::result::Result<(), &'static str> {
    if token.get("timestamp_token_version").and_then(Value::as_str)
        != Some("klein.timestamp_token.v1")
    {
        return Err("TIMESTAMP_TOKEN_SCHEMA_INVALID");
    }
    if token.get("token_kind").and_then(Value::as_str) != Some("mock_local") {
        return Err("TIMESTAMP_TOKEN_INVALID");
    }
    if token.get("trusted_time_claimed").and_then(Value::as_bool) != Some(false) {
        return Err("TIMESTAMP_TRUSTED_TIME_UNSUPPORTED");
    }
    if !token.get("signature").is_none_or(Value::is_null) {
        return Err("TIMESTAMP_SIGNATURE_UNSUPPORTED");
    }
    let target = token
        .get("target")
        .and_then(Value::as_object)
        .ok_or("TIMESTAMP_TOKEN_SCHEMA_INVALID")?;
    let target_type = target
        .get("target_type")
        .and_then(Value::as_str)
        .ok_or("TIMESTAMP_TOKEN_SCHEMA_INVALID")?;
    if !["run_bundle", "run_manifest", "hail_chain", "recorded_run"].contains(&target_type) {
        return Err("TIMESTAMP_TOKEN_INVALID");
    }
    let target_hash = target
        .get("target_hash")
        .and_then(Value::as_str)
        .ok_or("TIMESTAMP_TOKEN_SCHEMA_INVALID")?;
    if !is_sha256_ref(target_hash) {
        return Err("TIMESTAMP_TOKEN_SCHEMA_INVALID");
    }
    let source = token
        .get("time_source")
        .and_then(Value::as_object)
        .ok_or("TIMESTAMP_TOKEN_SCHEMA_INVALID")?;
    if source.get("source_type").and_then(Value::as_str) == Some("tsa") {
        return Err("TIMESTAMP_TSA_UNSUPPORTED");
    }
    if let Some(claimed_time) = token.get("claimed_time").and_then(Value::as_str) {
        if !claimed_time.ends_with('Z') || !claimed_time.contains('T') {
            return Err("TIMESTAMP_TIME_INVALID");
        }
    } else if !token.get("claimed_time").is_none_or(Value::is_null) {
        return Err("TIMESTAMP_TIME_INVALID");
    }
    Ok(())
}

fn verify_attestation_profile_fixture(repo_root: &Path, fixture: &Fixture) -> Result<()> {
    let profile: Value =
        serde_json::from_str(&fs::read_to_string(path(repo_root, fixture, "profile")?)?)?;
    validate_attestation_profile_value(&profile).map_err(err)
}

fn verify_attestation_statement_fixture(repo_root: &Path, fixture: &Fixture) -> Result<()> {
    let statement: Value =
        serde_json::from_str(&fs::read_to_string(path(repo_root, fixture, "statement")?)?)?;
    validate_attestation_statement_value(&statement).map_err(err)?;
    if let Some(expected_hash) = fixture.expected_digests.get("subject_hash") {
        let actual = statement
            .get("subject")
            .and_then(|subject| subject.get("subject_hash"))
            .and_then(Value::as_str)
            .ok_or_else(|| err("ATTESTATION_STATEMENT_SCHEMA_INVALID"))?;
        if actual != expected_hash {
            return Err(err("ATTESTATION_SUBJECT_HASH_MISMATCH"));
        }
    }
    if let Some(expected_backend_id) = fixture.expected_backend_id.as_deref() {
        let actual = statement
            .get("backend")
            .and_then(|backend| backend.get("backend_id"))
            .and_then(Value::as_str)
            .ok_or_else(|| err("ATTESTATION_STATEMENT_SCHEMA_INVALID"))?;
        if actual != expected_backend_id {
            return Err(err("ATTESTATION_BACKEND_MISMATCH"));
        }
    }
    Ok(())
}

fn validate_attestation_profile_value(profile: &Value) -> std::result::Result<(), &'static str> {
    if profile
        .get("attestation_profile_version")
        .and_then(Value::as_str)
        != Some("klein.attestation_profile.v1")
    {
        return Err("ATTESTATION_PROFILE_SCHEMA_INVALID");
    }
    if profile.get("profile_kind").and_then(Value::as_str) != Some("mock_none") {
        return Err("ATTESTATION_PROFILE_INVALID");
    }
    if profile
        .get("hardware_attestation_claimed")
        .and_then(Value::as_bool)
        != Some(false)
    {
        return Err("ATTESTATION_HARDWARE_UNSUPPORTED");
    }
    if profile
        .get("requires_hardware_root")
        .and_then(Value::as_bool)
        != Some(false)
    {
        return Err("ATTESTATION_HARDWARE_ROOT_UNSUPPORTED");
    }
    let allowed = profile
        .get("allowed_statement_kinds")
        .and_then(Value::as_array)
        .ok_or("ATTESTATION_PROFILE_SCHEMA_INVALID")?;
    if allowed.is_empty()
        || allowed
            .iter()
            .any(|kind| !matches!(kind.as_str(), Some("none" | "mock")))
    {
        return Err("ATTESTATION_PROFILE_INVALID");
    }
    if !profile
        .get("trust_roots")
        .and_then(Value::as_array)
        .is_some_and(Vec::is_empty)
    {
        return Err("ATTESTATION_PROFILE_INVALID");
    }
    Ok(())
}

fn validate_attestation_statement_value(
    statement: &Value,
) -> std::result::Result<(), &'static str> {
    if statement
        .get("attestation_statement_version")
        .and_then(Value::as_str)
        != Some("klein.attestation_statement.v1")
    {
        return Err("ATTESTATION_STATEMENT_SCHEMA_INVALID");
    }
    if !matches!(
        statement.get("statement_kind").and_then(Value::as_str),
        Some("none" | "mock")
    ) {
        return Err("ATTESTATION_STATEMENT_INVALID");
    }
    if statement
        .get("hardware_attestation_claimed")
        .and_then(Value::as_bool)
        != Some(false)
    {
        return Err("ATTESTATION_HARDWARE_UNSUPPORTED");
    }
    if !statement.get("hardware_root").is_none_or(Value::is_null) {
        return Err("ATTESTATION_HARDWARE_ROOT_UNSUPPORTED");
    }
    if !statement.get("quote").is_none_or(Value::is_null) {
        return Err("ATTESTATION_QUOTE_UNSUPPORTED");
    }
    if !statement.get("signature").is_none_or(Value::is_null) {
        return Err("ATTESTATION_SIGNATURE_UNSUPPORTED");
    }
    if !statement
        .get("measurements")
        .and_then(Value::as_array)
        .is_some_and(Vec::is_empty)
    {
        return Err("ATTESTATION_STATEMENT_INVALID");
    }
    let subject = statement
        .get("subject")
        .and_then(Value::as_object)
        .ok_or("ATTESTATION_STATEMENT_SCHEMA_INVALID")?;
    let subject_type = subject
        .get("subject_type")
        .and_then(Value::as_str)
        .ok_or("ATTESTATION_STATEMENT_SCHEMA_INVALID")?;
    if !["backend", "run_bundle", "recorded_run", "device"].contains(&subject_type) {
        return Err("ATTESTATION_STATEMENT_INVALID");
    }
    if let Some(subject_hash) = subject.get("subject_hash").and_then(Value::as_str) {
        if !is_sha256_ref(subject_hash) {
            return Err("ATTESTATION_STATEMENT_SCHEMA_INVALID");
        }
    } else if !subject.get("subject_hash").is_none_or(Value::is_null) {
        return Err("ATTESTATION_STATEMENT_SCHEMA_INVALID");
    }
    statement
        .get("backend")
        .and_then(Value::as_object)
        .ok_or("ATTESTATION_STATEMENT_SCHEMA_INVALID")?;
    Ok(())
}

fn validate_observation_policy_value(policy: &Value) -> std::result::Result<(), &'static str> {
    if policy
        .get("observation_policy_version")
        .and_then(Value::as_str)
        != Some("klein.observation_policy.v1")
    {
        return Err("OBSERVATION_POLICY_SCHEMA_INVALID");
    }
    let sources = policy
        .get("allowed_sources")
        .and_then(Value::as_array)
        .ok_or("OBSERVATION_POLICY_SCHEMA_INVALID")?;
    if sources
        .iter()
        .any(|source| source.as_str() != Some("simulator"))
    {
        return Err("OBSERVATION_SOURCE_UNSUPPORTED");
    }
    if policy.get("requires_attestation").and_then(Value::as_bool) == Some(true) {
        return Err("OBSERVATION_ATTESTATION_UNSUPPORTED");
    }
    Ok(())
}

fn validate_observation_snapshot_value(
    observation: &Value,
) -> std::result::Result<(), &'static str> {
    if observation
        .get("observation_version")
        .and_then(Value::as_str)
        != Some("klein.observation_snapshot.v1")
    {
        return Err("OBSERVATION_SCHEMA_INVALID");
    }
    let confidence = observation
        .get("confidence")
        .and_then(Value::as_f64)
        .ok_or("OBSERVATION_CONFIDENCE_INVALID")?;
    if !(0.0..=1.0).contains(&confidence) {
        return Err("OBSERVATION_CONFIDENCE_INVALID");
    }
    let source = observation
        .get("source")
        .and_then(Value::as_object)
        .ok_or("OBSERVATION_SCHEMA_INVALID")?;
    if source.get("source_type").and_then(Value::as_str) != Some("simulator") {
        return Err("OBSERVATION_SOURCE_UNSUPPORTED");
    }
    if !source.get("attestation").is_none_or(Value::is_null) {
        return Err("OBSERVATION_ATTESTATION_UNSUPPORTED");
    }
    observation
        .get("state")
        .and_then(|state| state.get("dmf"))
        .and_then(|dmf| dmf.get("active_channels"))
        .and_then(Value::as_array)
        .ok_or("OBSERVATION_DMF_STATE_INVALID")?;
    Ok(())
}

fn compare_observation_to_trace_value(
    observation: &Value,
    trace: &Value,
) -> std::result::Result<(), &'static str> {
    let trace_step_id = observation
        .get("trace_step_id")
        .and_then(Value::as_str)
        .ok_or("OBSERVATION_TRACE_MISMATCH")?;
    let trace_steps = trace
        .get("trace_steps")
        .and_then(Value::as_array)
        .ok_or("TRACE_SCHEMA_INVALID")?;
    if trace_steps
        .iter()
        .any(|step| step.get("step_id").and_then(Value::as_str) == Some(trace_step_id))
    {
        Ok(())
    } else {
        Err("OBSERVATION_TRACE_MISMATCH")
    }
}

fn validate_dmf_payload_value(payload: &Value) -> Result<()> {
    match payload.get("kind").and_then(Value::as_str) {
        Some("CHANNEL_LIST") => {
            validate_dmf_channel_list(payload.get("data").unwrap_or(&Value::Null))
        }
        Some("FRAME_SEQUENCE") => {
            validate_dmf_frame_sequence(payload.get("data").unwrap_or(&Value::Null))
        }
        Some("BITMAP_SEQUENCE") => {
            validate_dmf_bitmap_sequence(payload.get("data").unwrap_or(&Value::Null))
        }
        _ => Err(err("DDI_UNSUPPORTED_PAYLOAD")),
    }
}

fn validate_dmf_channel_list(data: &Value) -> Result<()> {
    let entries = data.as_array().ok_or_else(|| err("PAYLOAD_MALFORMED"))?;
    let mut seen = std::collections::BTreeMap::new();
    for entry in entries {
        let tick = entry
            .get("t")
            .and_then(Value::as_i64)
            .ok_or_else(|| err("PAYLOAD_MALFORMED"))?;
        let channel = entry
            .get("channel_id")
            .and_then(Value::as_i64)
            .ok_or_else(|| err("PAYLOAD_MALFORMED"))?;
        if !(0..128).contains(&channel) {
            return Err(err("PAYLOAD_CHANNEL_OOB"));
        }
        let state = entry
            .get("state")
            .and_then(Value::as_str)
            .ok_or_else(|| err("PAYLOAD_MALFORMED"))?;
        if !matches!(state, "ON" | "OFF") {
            return Err(err("PAYLOAD_INVALID_STATE"));
        }
        if !entry.get("voltage_v").is_some_and(Value::is_number) {
            return Err(err("PAYLOAD_MALFORMED"));
        }
        let key = (tick, channel);
        if seen.get(&key).is_some_and(|previous| *previous != state) {
            return Err(err("PAYLOAD_CONFLICTING_STATE"));
        }
        seen.insert(key, state);
    }
    Ok(())
}

fn validate_dmf_frame_sequence(data: &Value) -> Result<()> {
    let frames = data.as_array().ok_or_else(|| err("PAYLOAD_MALFORMED"))?;
    for frame in frames {
        match frame.get("format").and_then(Value::as_str) {
            Some("sparse") => validate_sparse_pixels(frame.get("data").unwrap_or(&Value::Null)),
            Some("rle") => Err(err("PAYLOAD_UNSUPPORTED_FRAME_FORMAT")),
            Some("bitmap") | Some("delta_tiles") => Ok(()),
            _ => Err(err("PAYLOAD_MALFORMED")),
        }?;
    }
    Ok(())
}

fn validate_sparse_pixels(data: &Value) -> Result<()> {
    let pixels = data.as_array().ok_or_else(|| err("PAYLOAD_MALFORMED"))?;
    for pixel in pixels {
        if let Some(electrode) = pixel.as_i64() {
            if !(0..128).contains(&electrode) {
                return Err(err("PAYLOAD_OOB_PIXEL"));
            }
        }
    }
    Ok(())
}

fn validate_dmf_bitmap_sequence(data: &Value) -> Result<()> {
    let bitmaps = data.as_array().ok_or_else(|| err("PAYLOAD_MALFORMED"))?;
    for bitmap in bitmaps {
        if !bitmap.is_string() {
            return Err(err("PAYLOAD_MALFORMED"));
        }
    }
    Ok(())
}

fn verify_dmf_capabilities(repo_root: &Path, fixture: &Fixture) -> Result<()> {
    let capabilities: Value = serde_json::from_str(&fs::read_to_string(path(
        repo_root,
        fixture,
        "capabilities",
    )?)?)?;
    validate_dmf_capabilities_value(&capabilities)
}

fn validate_dmf_capabilities_value(capabilities: &Value) -> Result<()> {
    let addressing = capabilities
        .get("addressing")
        .ok_or_else(|| err("DMF_CAPABILITIES_INVALID"))?;
    for field in ["max_channels", "grid_width", "grid_height"] {
        if addressing.get(field).and_then(Value::as_i64).unwrap_or(0) <= 0 {
            return Err(err("DMF_CAPABILITIES_INVALID"));
        }
    }
    let electrical = capabilities
        .get("electrical")
        .ok_or_else(|| err("DMF_CAPABILITIES_INVALID"))?;
    if electrical
        .get("voltage_min_v")
        .and_then(Value::as_f64)
        .unwrap_or(f64::NAN)
        > electrical
            .get("voltage_max_v")
            .and_then(Value::as_f64)
            .unwrap_or(f64::NAN)
    {
        return Err(err("DMF_CAPABILITIES_INVALID"));
    }
    if electrical
        .get("frequency_min_hz")
        .and_then(Value::as_f64)
        .unwrap_or(f64::NAN)
        > electrical
            .get("frequency_max_hz")
            .and_then(Value::as_f64)
            .unwrap_or(f64::NAN)
    {
        return Err(err("DMF_CAPABILITIES_INVALID"));
    }
    let payloads = capabilities
        .get("payloads")
        .ok_or_else(|| err("DMF_CAPABILITIES_INVALID"))?;
    let supported = payloads
        .get("supported_frame_formats")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(Value::as_str)
        .collect::<std::collections::BTreeSet<_>>();
    let unsupported = payloads
        .get("unsupported_frame_formats")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(Value::as_str)
        .collect::<std::collections::BTreeSet<_>>();
    if supported.contains("rle") || supported.iter().any(|format| unsupported.contains(format)) {
        return Err(err("DMF_CAPABILITIES_INVALID"));
    }
    Ok(())
}

fn verify_conformance_levels_catalog(repo_root: &Path, fixture: &Fixture) -> Result<()> {
    let catalog: Value =
        serde_json::from_str(&fs::read_to_string(path(repo_root, fixture, "catalog")?)?)?;
    if catalog.get("catalog_version").and_then(Value::as_str) != Some("klein.conformance_levels.v1")
    {
        return Err(err("CONFORMANCE_LEVEL_CATALOG_INVALID"));
    }
    let levels = catalog
        .get("levels")
        .and_then(Value::as_array)
        .ok_or_else(|| err("CONFORMANCE_LEVEL_CATALOG_INVALID"))?;
    let mut ids = std::collections::BTreeSet::new();
    for level in levels {
        let Some(level_id) = level.get("level_id").and_then(Value::as_str) else {
            return Err(err("CONFORMANCE_LEVEL_CATALOG_INVALID"));
        };
        if !ids.insert(level_id.to_string()) {
            return Err(err("CONFORMANCE_LEVEL_CATALOG_INVALID"));
        }
    }
    for level in levels {
        for dependency in level
            .get("requires")
            .and_then(Value::as_array)
            .into_iter()
            .flatten()
            .filter_map(Value::as_str)
        {
            if !ids.contains(dependency) {
                return Err(err("CONFORMANCE_LEVEL_UNKNOWN"));
            }
        }
    }
    Ok(())
}

fn verify_backend_capabilities(repo_root: &Path, fixture: &Fixture) -> Result<()> {
    let declaration: Value = serde_json::from_str(&fs::read_to_string(path(
        repo_root,
        fixture,
        "declaration",
    )?)?)?;
    let registry = match path(repo_root, fixture, "registry") {
        Ok(path) => Some(serde_json::from_str::<Value>(&fs::read_to_string(path)?)?),
        Err(_) => None,
    };
    let policy = match path(repo_root, fixture, "trust_policy") {
        Ok(path) => Some(serde_json::from_str::<Value>(&fs::read_to_string(path)?)?),
        Err(_) => None,
    };
    let manifest = match path(repo_root, fixture, "manifest") {
        Ok(path) => Some(serde_json::from_str::<Value>(&fs::read_to_string(path)?)?),
        Err(_) => None,
    };
    verify_capability_declaration(
        &declaration,
        registry.as_ref(),
        policy.as_ref(),
        manifest.as_ref(),
    )?;
    Ok(())
}

fn verify_backend_identity_registry(repo_root: &Path, fixture: &Fixture) -> Result<()> {
    let registry: Value =
        serde_json::from_str(&fs::read_to_string(path(repo_root, fixture, "registry")?)?)?;
    let manifest: Value =
        serde_json::from_str(&fs::read_to_string(path(repo_root, fixture, "manifest")?)?)?;
    let policy = match path(repo_root, fixture, "trust_policy") {
        Ok(path) => Some(serde_json::from_str::<Value>(&fs::read_to_string(path)?)?),
        Err(_) => None,
    };
    if let Some(policy) = policy.as_ref() {
        resolve_manifest_identity_with_policy(&registry, &manifest, Some(policy))?;
    } else {
        resolve_manifest_identity(&registry, &manifest)?;
    }
    Ok(())
}

fn verify_canonical_json(repo_root: &Path, fixture: &Fixture) -> Result<()> {
    let input: Value =
        serde_json::from_str(&fs::read_to_string(path(repo_root, fixture, "input")?)?)?;
    let expected = expected_digest(repo_root, fixture, "canonical_sha256", "expected_sha256")?;
    let actual = canonical_sha256_ref(&input)?;
    compare(&actual, &expected, "canonical JSON digest")
}

fn verify_hail_jsonl(repo_root: &Path, fixture: &Fixture) -> Result<()> {
    let events = parse_jsonl(&fs::read_to_string(path(repo_root, fixture, "input")?)?)?;
    let expected = expected_digest(repo_root, fixture, "canonical_sha256", "expected_sha256")?;
    let actual = hail_digest_ref(&events)?;
    compare(&actual, &expected, "HAIL JSONL digest")
}

fn verify_hail_chain_fixture(repo_root: &Path, fixture: &Fixture) -> Result<()> {
    let events = parse_jsonl(&fs::read_to_string(path(repo_root, fixture, "hail")?)?)?;
    let actual = verify_hail_chain(&events)?;
    let expected = expected_value(fixture, "hail_chain_digest")
        .or_else(|| fixture.expected_digests.get("hail_chain_digest").cloned())
        .ok_or_else(|| err("missing expected hail_chain_digest"))?;
    compare(&actual, &expected, "HAIL chain digest")
}

fn verify_manifest_and_policy(repo_root: &Path, fixture: &Fixture) -> Result<()> {
    let events = parse_jsonl(&fs::read_to_string(path(repo_root, fixture, "hail")?)?)?;
    let chain_digest = verify_hail_chain(&events)?;
    let hail_digest = hail_digest_ref(&events)?;
    let manifest: Value =
        serde_json::from_str(&fs::read_to_string(path(repo_root, fixture, "manifest")?)?)?;
    let policy: Value = serde_json::from_str(&fs::read_to_string(path(
        repo_root,
        fixture,
        "trust_policy",
    )?)?)?;
    validate_manifest_payload(&manifest, &hail_digest, &chain_digest)?;
    verify_manifest_signature(&manifest)?;
    authorize(&policy, &manifest)?;
    Ok(())
}

fn verify_bundle_fixture(repo_root: &Path, fixture: &Fixture) -> Result<()> {
    let bundle_path = path(repo_root, fixture, "bundle")?;
    let result = crate::bundle::verify_bundle_result(&bundle_path);
    if fixture.expected_status.as_deref() == Some("fail") {
        let error = result
            .errors
            .first()
            .ok_or_else(|| err("expected bundle verification failure but verification passed"))?;
        if fixture
            .expected_error_code
            .as_deref()
            .is_some_and(|code| code != error.error_code)
        {
            return Err(err(format!(
                "expected {}, actual {}",
                fixture.expected_error_code.as_deref().unwrap_or(""),
                error.error_code
            )));
        }
        if fixture
            .expected_failing_check
            .as_deref()
            .is_some_and(|check| check != error.check)
        {
            return Err(err(format!(
                "expected failing check {}, actual {}",
                fixture.expected_failing_check.as_deref().unwrap_or(""),
                error.check
            )));
        }
        return Err(err(format!("{} {}", error.error_code, error.check)));
    }
    if !result.ok() {
        let message = result
            .errors
            .first()
            .map(|error| error.error_code.clone())
            .unwrap_or_else(|| "bundle verification failed".to_string());
        return Err(err(message));
    }
    Ok(())
}

fn fixture_type(fixture: &Fixture) -> String {
    if let Some(kind) = &fixture.fixture_type {
        return kind.clone();
    }
    if fixture.fixture_id.contains("canonical-json") {
        "canonical_json".to_string()
    } else if fixture.fixture_id.contains("hail-jsonl") {
        "hail_jsonl".to_string()
    } else if fixture.fixture_id.contains("hail-chain") {
        "hail_chain".to_string()
    } else if fixture.fixture_id.contains("manifest") {
        "run_manifest".to_string()
    } else {
        "run_bundle".to_string()
    }
}

fn path(repo_root: &Path, fixture: &Fixture, key: &str) -> Result<PathBuf> {
    fixture
        .input_paths
        .get(key)
        .map(|path| repo_root.join(path))
        .ok_or_else(|| err(format!("missing input path: {key}")))
}

fn expected_digest(
    repo_root: &Path,
    fixture: &Fixture,
    expected_key: &str,
    path_key: &str,
) -> Result<String> {
    if let Some(value) = expected_value(fixture, expected_key) {
        return Ok(value);
    }
    let expected_path = path(repo_root, fixture, path_key)?;
    Ok(fs::read_to_string(expected_path)?.trim().to_string())
}

fn expected_value(fixture: &Fixture, key: &str) -> Option<String> {
    let expected = fixture.expected.as_ref()?;
    match key {
        "canonical_sha256" => expected.canonical_sha256.clone(),
        "hail_digest" => expected.hail_digest.clone(),
        "hail_chain_digest" => expected.hail_chain_digest.clone(),
        _ => None,
    }
}

fn compare(actual: &str, expected: &str, label: &str) -> Result<()> {
    if actual == expected {
        Ok(())
    } else {
        Err(err(format!(
            "{label} mismatch: expected {expected}, actual {actual}"
        )))
    }
}

fn expected_check_matches(fixture: &Fixture, message: &str) -> bool {
    fixture
        .expected_failing_check
        .as_deref()
        .map(|check| message.contains(check))
        .unwrap_or(true)
}
