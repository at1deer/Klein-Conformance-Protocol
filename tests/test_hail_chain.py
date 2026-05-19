from __future__ import annotations

import json
from pathlib import Path

import pytest

from klein.conformance.backends import FullSimulatorBackend
from klein.conformance.suite import discover_vectors
from klein.hail.canonical import canonicalize_hail_jsonl, event_sort_key
from klein.hail.chain import compute_hail_chain, verify_hail_chain
from klein.hail.validation import parse_jsonl_events
from klein.tools.hail_canon import main as hail_canon_main


def _lifecycle_events() -> list[dict]:
    vector = discover_vectors(
        vector_ids=["010"],
        suite_dir=Path("tests/vectors/v1"),
    )[0]
    execution = FullSimulatorBackend().execute(vector)
    return sorted(execution.events, key=event_sort_key)


def _write_jsonl(path: Path, events: list[dict]) -> None:
    path.write_bytes(canonicalize_hail_jsonl(events))


def test_hail_chain_matches_run_end_for_lifecycle_stream() -> None:
    events = _lifecycle_events()

    verification = verify_hail_chain(events)
    run_end = next(event for event in events if event["kind"] == "RUN_END")

    assert verification.ok
    assert verification.matches_run_end is True
    assert verification.canonical_order_ok is True
    assert verification.result is not None
    assert verification.result.terminal_chain_digest_ref == run_end[
        "preclose_hail_chain_digest"
    ]
    assert verification.result.event_count_chained == run_end["event_count_preclose"]


def test_hail_chain_digest_changes_when_event_is_tampered() -> None:
    events = _lifecycle_events()
    tampered = [dict(event) for event in events]
    device_event = next(event for event in tampered if event.get("kind") == "DEVICE_EVENT")
    device_event["message"] = "tampered"

    verification = verify_hail_chain(tampered)

    assert not verification.ok
    assert verification.error_code == "HAIL_CHAIN_MISMATCH"


def test_hail_chain_digest_changes_when_event_is_removed() -> None:
    events = _lifecycle_events()
    removed = [event for event in events if event.get("code") != "NO_PAYLOAD"]

    verification = verify_hail_chain(removed)

    assert not verification.ok
    assert verification.error_code == "HAIL_CHAIN_MISMATCH"


def test_hail_chain_detects_noncanonical_reordering() -> None:
    events = _lifecycle_events()
    reordered = list(events)
    reordered[1], reordered[2] = reordered[2], reordered[1]

    verification = verify_hail_chain(reordered)

    assert not verification.ok
    assert verification.matches_run_end is True
    assert verification.canonical_order_ok is False
    assert verification.error_code == "HAIL_CHAIN_INVALID"


def test_hail_chain_missing_run_end_reports_error() -> None:
    events = [event for event in _lifecycle_events() if event.get("kind") != "RUN_END"]

    verification = verify_hail_chain(events)

    assert not verification.ok
    assert verification.error_code == "HAIL_RUN_END_MISSING"


def test_hail_chain_cli_verify_and_digest(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    events = _lifecycle_events()
    stream = tmp_path / "lifecycle.jsonl"
    _write_jsonl(stream, events)

    assert hail_canon_main([str(stream), "--verify-chain"]) == 0
    assert hail_canon_main([str(stream), "--chain-digest"]) == 0
    digest = capsys.readouterr().out.strip()

    assert digest == compute_hail_chain(events).terminal_chain_digest_ref


def test_hail_chain_cli_rejects_altered_run_end_digest(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    events = _lifecycle_events()
    altered = [dict(event) for event in events]
    run_end = next(event for event in altered if event["kind"] == "RUN_END")
    run_end["preclose_hail_chain_digest"] = "sha256:" + ("0" * 64)
    stream = tmp_path / "altered.jsonl"
    _write_jsonl(stream, altered)

    assert hail_canon_main([str(stream), "--verify-chain"]) == 1
    assert "HAIL_CHAIN_MISMATCH" in capsys.readouterr().err


def test_hail_chain_cli_rejects_tampered_event(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    events = _lifecycle_events()
    altered = [dict(event) for event in events]
    device_event = next(event for event in altered if event.get("kind") == "DEVICE_EVENT")
    device_event["message"] = "tampered"
    stream = tmp_path / "tampered.jsonl"
    _write_jsonl(stream, altered)

    assert hail_canon_main([str(stream), "--verify-chain"]) == 1
    assert "HAIL_CHAIN_MISMATCH" in capsys.readouterr().err


def test_chain_fixture_round_trips_when_present() -> None:
    fixture = Path("tests/fixtures/hail_chain/lifecycle_stream.jsonl")
    expected = json.loads(Path("tests/fixtures/hail_chain/expected.json").read_text())

    validation, events = parse_jsonl_events(fixture.read_text(encoding="utf-8"))
    verification = verify_hail_chain(events)

    assert validation.ok
    assert verification.ok
    assert verification.result is not None
    assert verification.result.terminal_chain_digest_ref == expected[
        "preclose_hail_chain_digest"
    ]
