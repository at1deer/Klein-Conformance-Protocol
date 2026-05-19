use serde_json::Value;
use sha2::{Digest, Sha256};

use crate::canonical::{canonical_json, sha256_hex};
use crate::errors::{err, Result};

const DOMAIN: &[u8] = b"KLEIN-HAIL-CHAIN-v1\0";

pub fn parse_jsonl(text: &str) -> Result<Vec<Value>> {
    text.lines()
        .filter(|line| !line.trim().is_empty())
        .map(|line| serde_json::from_str(line).map_err(Into::into))
        .collect()
}

pub fn canonical_hail_jsonl(events: &[Value]) -> Result<Vec<u8>> {
    let mut ordered: Vec<&Value> = events.iter().collect();
    ordered.sort_by(|left, right| event_sort_key(left).cmp(&event_sort_key(right)));
    let mut lines = Vec::with_capacity(ordered.len());
    for event in ordered {
        lines.push(canonical_json(event)?);
    }
    Ok(lines.join("\n").into_bytes())
}

pub fn hail_digest_ref(events: &[Value]) -> Result<String> {
    Ok(format!(
        "sha256:{}",
        sha256_hex(&canonical_hail_jsonl(events)?)
    ))
}

pub fn verify_hail_chain(events: &[Value]) -> Result<String> {
    let run_end = events
        .iter()
        .find(|event| string_field(event, "kind") == "RUN_END")
        .ok_or_else(|| err("HAIL_RUN_END_MISSING"))?;
    let expected = string_field(run_end, "preclose_hail_chain_digest");
    if expected.is_empty() {
        return Err(err("HAIL_CHAIN_MISSING"));
    }
    let actual = compute_hail_chain(events)?;
    if actual != expected {
        return Err(err("HAIL_CHAIN_MISMATCH"));
    }
    if !is_canonical_order(events) {
        return Err(err("HAIL_CHAIN_INVALID"));
    }
    Ok(actual)
}

pub fn compute_hail_chain(events: &[Value]) -> Result<String> {
    let mut chain_events: Vec<&Value> = events
        .iter()
        .filter(|event| string_field(event, "kind") != "RUN_END")
        .collect();
    chain_events.sort_by(|left, right| event_sort_key(left).cmp(&event_sort_key(right)));

    let mut previous = Sha256::digest([DOMAIN, b"GENESIS"].concat()).to_vec();
    for event in chain_events {
        let event_bytes = canonical_json(event)?.into_bytes();
        let mut payload = Vec::new();
        payload.extend_from_slice(DOMAIN);
        payload.extend_from_slice(&previous);
        payload.push(0);
        payload.extend_from_slice(&event_bytes);
        previous = Sha256::digest(payload).to_vec();
    }
    Ok(format!("sha256:{}", hex::encode(previous)))
}

fn is_canonical_order(events: &[Value]) -> bool {
    let keys: Vec<EventKey> = events.iter().map(event_sort_key).collect();
    let mut sorted = keys.clone();
    sorted.sort();
    keys == sorted
}

#[derive(Clone, Eq, PartialEq, Ord, PartialOrd)]
struct EventKey {
    t: i64,
    rank: i32,
    kind: String,
    tie: String,
}

fn event_sort_key(event: &Value) -> EventKey {
    let kind = string_field(event, "kind");
    let rank = match kind.as_str() {
        "RUN_START" => 0,
        "DEVICE_EVENT" => 10,
        "RUNTIME_STATE_SNAPSHOT" => 20,
        "MEASUREMENT" => 30,
        "ECRP_ATTEMPT" => 40,
        "REPLAN_DECISION" => 50,
        "RUN_END" => 90,
        _ => 80,
    };
    let tie = match kind.as_str() {
        "RUN_START" | "RUN_END" => string_field(event, "run_id"),
        "DEVICE_EVENT" => string_field(event, "code"),
        "RUNTIME_STATE_SNAPSHOT" => string_field(event, "rimgb_hash"),
        "MEASUREMENT" => string_field(event, "measurement_id"),
        "REPLAN_DECISION" => string_field(event, "checkpoint_id"),
        "ECRP_ATTEMPT" => int_field(event, "attempt_index").to_string(),
        _ => String::new(),
    };
    EventKey {
        t: int_field(event, "t"),
        rank,
        kind,
        tie,
    }
}

pub fn string_field(value: &Value, field: &str) -> String {
    value
        .get(field)
        .and_then(Value::as_str)
        .unwrap_or_default()
        .to_string()
}

fn int_field(value: &Value, field: &str) -> i64 {
    value.get(field).and_then(Value::as_i64).unwrap_or_default()
}
