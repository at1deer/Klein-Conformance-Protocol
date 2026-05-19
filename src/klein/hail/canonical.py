"""RFC 8785/JCS canonical JSONL helpers for HAIL v1."""

from __future__ import annotations

from typing import Any

from klein.common.hashing import HashResult, canonical_json_bytes, sha256_bytes

EVENT_KIND_RANK = {
    "RUN_START": 0,
    "DEVICE_EVENT": 10,
    "RUNTIME_STATE_SNAPSHOT": 20,
    "MEASUREMENT": 30,
    "ECRP_ATTEMPT": 40,
    "REPLAN_DECISION": 50,
    "RUN_END": 90,
}


def event_sort_key(event: dict[str, Any]) -> tuple[Any, ...]:
    """Return the deterministic HAIL v1 sort key for an event."""
    kind = event.get("kind", "")
    rank = EVENT_KIND_RANK.get(kind, 80)

    tie_breaker: Any = ""
    if kind == "RUN_START":
        tie_breaker = event.get("run_id", "")
    elif kind == "MEASUREMENT":
        tie_breaker = event.get("measurement_id", "")
    elif kind == "REPLAN_DECISION":
        tie_breaker = event.get("checkpoint_id", "")
    elif kind == "ECRP_ATTEMPT":
        tie_breaker = event.get("attempt_index", 0)
    elif kind == "DEVICE_EVENT":
        tie_breaker = event.get("code", "")
    elif kind == "RUNTIME_STATE_SNAPSHOT":
        # v1 uses rimgb_hash. rsb_hash is kept only as an explicit migration
        # bridge for legacy-normalized comparisons.
        tie_breaker = event.get("rimgb_hash", event.get("rsb_hash", ""))
    elif kind == "RUN_END":
        tie_breaker = event.get("run_id", "")

    return (event.get("t", 0), rank, kind, tie_breaker)


def canonicalize_json_value(value: Any) -> bytes:
    """Serialize an I-JSON value using RFC 8785/JCS canonical JSON."""
    return canonical_json_bytes(value)


def canonicalize_hail_event(event: dict[str, Any]) -> bytes:
    """Serialize one HAIL event as RFC 8785/JCS canonical JSON bytes."""
    return canonicalize_json_value(event)


def dump_canonical(event: dict[str, Any]) -> str:
    """Serialize one event with RFC 8785/JCS canonical JSON."""
    return canonicalize_hail_event(event).decode("utf-8")


def canonicalize_events(events: list[dict[str, Any]]) -> list[str]:
    """Return canonical JSONL lines sorted by the HAIL v1 event sort key."""
    return [dump_canonical(event) for event in sorted(events, key=event_sort_key)]


def canonical_payload(events: list[dict[str, Any]]) -> str:
    """Return the newline-joined canonical payload used for digests."""
    return "\n".join(canonicalize_events(events))


def canonicalize_hail_jsonl(events: list[dict[str, Any]]) -> bytes:
    """Return LF-delimited canonical HAIL JSONL bytes without a trailing LF."""
    return b"\n".join(canonicalize_hail_event(event) for event in sorted(events, key=event_sort_key))


def compute_digest(events: list[dict[str, Any]]) -> str:
    """Compute a SHA-256 digest over the canonical HAIL payload."""
    return digest_hail_jsonl(events)


def digest_hail_jsonl(events: list[dict[str, Any]]) -> str:
    """Compute a SHA-256 digest over exact canonical HAIL JSONL bytes."""
    return sha256_bytes(canonicalize_hail_jsonl(events))


def hash_hail_jsonl(events: list[dict[str, Any]]) -> HashResult:
    """Return the structured canonical HAIL JSONL hash result."""
    digest = digest_hail_jsonl(events)
    return HashResult(
        algorithm="sha256",
        digest_hex=digest,
        ref=f"sha256:{digest}",
        canonicalization="klein.canon.jsonl.v1",
    )


def normalize_run_metadata(
    events: list[dict[str, Any]],
    *,
    run_id: str = "<run_id>",
) -> list[dict[str, Any]]:
    """Return a copy of events with run-specific identifiers normalized."""
    normalized: list[dict[str, Any]] = []
    for event in events:
        copied = dict(event)
        if "run_id" in copied:
            copied["run_id"] = run_id
        normalized.append(copied)
    return normalized
