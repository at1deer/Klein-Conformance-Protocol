"""Tamper-evident HAIL v1 event hash-chain helpers."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from klein.hail.canonical import canonicalize_hail_event, event_sort_key
from klein.hail.validation import validate_events

HAIL_CHAIN_DOMAIN = b"KLEIN-HAIL-CHAIN-v1\0"
HAIL_CHAIN_ALGORITHM = "klein.hail.chain.v1"


@dataclass(frozen=True)
class HailChainResult:
    """Computed HAIL chain terminal digest."""

    event_count_chained: int
    terminal_chain_digest: str
    terminal_chain_digest_ref: str
    chain_algorithm: str
    excluded_run_end: bool


@dataclass(frozen=True)
class HailChainVerification:
    """Verification result for a lifecycle-bound HAIL stream."""

    ok: bool
    result: HailChainResult | None
    run_end_expected_digest: str | None
    matches_run_end: bool | None
    canonical_order_ok: bool
    error_code: str | None = None
    reason: str | None = None


def _sha256(payload: bytes) -> bytes:
    return hashlib.sha256(payload).digest()


def _preclose_events(
    events: Sequence[dict[str, Any]],
    *,
    exclude_run_end: bool,
) -> list[dict[str, Any]]:
    if not exclude_run_end:
        return list(events)
    return [event for event in events if event.get("kind") != "RUN_END"]


def is_canonical_event_order(events: Sequence[dict[str, Any]]) -> bool:
    """Return True when events are already in Klein HAIL canonical event order."""
    return list(events) == sorted(events, key=event_sort_key)


def compute_hail_chain(
    events: Sequence[dict[str, Any]],
    *,
    exclude_run_end: bool = True,
) -> HailChainResult:
    """
    Compute the Klein HAIL chain v1 terminal digest.

    The chain is computed over strict HAIL v1 events in Klein canonical event order.
    RUN_END is excluded by default so RUN_END can carry a non-circular terminal
    chain digest over the pre-close stream.
    """
    chain_events = _preclose_events(events, exclude_run_end=exclude_run_end)
    validation = validate_events(chain_events)
    if not validation.ok:
        raise ValueError(
            f"HAIL validation failed before chain computation: "
            f"{validation.error_code} stage={validation.validation_stage}"
        )

    previous = _sha256(HAIL_CHAIN_DOMAIN + b"GENESIS")
    for event in sorted(chain_events, key=event_sort_key):
        event_bytes = canonicalize_hail_event(event)
        previous = _sha256(HAIL_CHAIN_DOMAIN + previous + b"\0" + event_bytes)

    digest_hex = previous.hex()
    return HailChainResult(
        event_count_chained=len(chain_events),
        terminal_chain_digest=digest_hex,
        terminal_chain_digest_ref=f"sha256:{digest_hex}",
        chain_algorithm=HAIL_CHAIN_ALGORITHM,
        excluded_run_end=exclude_run_end,
    )


def verify_hail_chain(events: Sequence[dict[str, Any]]) -> HailChainVerification:
    """
    Verify RUN_END.preclose_hail_chain_digest against the pre-close HAIL chain.

    Digest computation sorts events into Klein canonical event order. The
    verification result also reports whether the input stream was already in
    canonical event order so tools can reject reordered JSONL evidence.
    """
    validation = validate_events(list(events))
    if not validation.ok:
        return HailChainVerification(
            ok=False,
            result=None,
            run_end_expected_digest=None,
            matches_run_end=None,
            canonical_order_ok=False,
            error_code="HAIL_CHAIN_INVALID",
            reason=validation.message,
        )

    canonical_order_ok = is_canonical_event_order(events)
    run_end_events = [event for event in events if event.get("kind") == "RUN_END"]
    if not run_end_events:
        result = compute_hail_chain(events, exclude_run_end=True)
        return HailChainVerification(
            ok=False,
            result=result,
            run_end_expected_digest=None,
            matches_run_end=None,
            canonical_order_ok=canonical_order_ok,
            error_code="HAIL_RUN_END_MISSING",
            reason="RUN_END event missing",
        )
    if len(run_end_events) > 1:
        result = compute_hail_chain(events, exclude_run_end=True)
        return HailChainVerification(
            ok=False,
            result=result,
            run_end_expected_digest=None,
            matches_run_end=None,
            canonical_order_ok=canonical_order_ok,
            error_code="HAIL_CHAIN_INVALID",
            reason="multiple RUN_END events are not valid for chain verification",
        )

    run_end = run_end_events[0]
    expected = run_end.get("preclose_hail_chain_digest")
    if not isinstance(expected, str) or not expected:
        result = compute_hail_chain(events, exclude_run_end=True)
        return HailChainVerification(
            ok=False,
            result=result,
            run_end_expected_digest=None,
            matches_run_end=None,
            canonical_order_ok=canonical_order_ok,
            error_code="HAIL_CHAIN_MISSING",
            reason="RUN_END.preclose_hail_chain_digest missing",
        )

    algorithm = run_end.get("preclose_hail_chain_algorithm")
    if algorithm != HAIL_CHAIN_ALGORITHM:
        result = compute_hail_chain(events, exclude_run_end=True)
        return HailChainVerification(
            ok=False,
            result=result,
            run_end_expected_digest=expected,
            matches_run_end=False,
            canonical_order_ok=canonical_order_ok,
            error_code="HAIL_CHAIN_INVALID",
            reason="RUN_END.preclose_hail_chain_algorithm is not klein.hail.chain.v1",
        )

    result = compute_hail_chain(events, exclude_run_end=True)
    matches = result.terminal_chain_digest_ref == expected
    ok = matches and canonical_order_ok
    reason = None
    error_code = None
    if not matches:
        reason = "RUN_END.preclose_hail_chain_digest does not match computed chain digest"
        error_code = "HAIL_CHAIN_MISMATCH"
    elif not canonical_order_ok:
        reason = "HAIL JSONL stream is not in canonical event order"
        error_code = "HAIL_CHAIN_INVALID"

    return HailChainVerification(
        ok=ok,
        result=result,
        run_end_expected_digest=expected,
        matches_run_end=matches,
        canonical_order_ok=canonical_order_ok,
        error_code=error_code,
        reason=reason,
    )


def chain_digest_hail_jsonl(events: Sequence[dict[str, Any]]) -> str:
    """Return sha256:<hex> terminal HAIL chain digest for a stream."""
    return compute_hail_chain(events, exclude_run_end=True).terminal_chain_digest_ref
