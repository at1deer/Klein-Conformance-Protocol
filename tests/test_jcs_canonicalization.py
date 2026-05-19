from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest

from klein.hail.canonical import (
    canonical_payload,
    canonicalize_events,
    canonicalize_hail_jsonl,
    canonicalize_json_value,
    compute_digest,
    dump_canonical,
)
from klein.tools.hail_canon import main as hail_canon_main

FIXTURES = Path("tests/fixtures/canonicalization")


def test_jcs_object_key_ordering_uses_utf16_code_units() -> None:
    supplementary = "\U00010000"
    bmp_high = "\uffff"

    canonical = canonicalize_json_value({bmp_high: 1, supplementary: 2}).decode("utf-8")

    assert canonical == '{"' + supplementary + '":2,"' + bmp_high + '":1}'


def test_jcs_nested_objects_and_arrays() -> None:
    value = {"z": [{"b": 2, "a": 1}], "a": {"d": True, "c": None}}

    assert canonicalize_json_value(value) == b'{"a":{"c":null,"d":true},"z":[{"a":1,"b":2}]}'


def test_jcs_string_escaping_and_unicode() -> None:
    value = "line\nquote\"slash\\" + chr(0x00B5)

    assert canonicalize_json_value(value).decode("utf-8") == '"line\\nquote\\"slash\\\\µ"'


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1, "1"),
        (-12, "-12"),
        (1.0, "1"),
        (-0.0, "0"),
        (1.5, "1.5"),
        (0.000001, "0.000001"),
        (0.00001, "0.00001"),
        (0.0000001, "1e-7"),
        (5e-324, "5e-324"),
        (-5e-324, "-5e-324"),
        (9.999999999999997e-7, "9.999999999999997e-7"),
        (1e20, "100000000000000000000"),
        (1e21, "1e+21"),
        (1.7976931348623157e308, "1.7976931348623157e+308"),
        (-1.7976931348623157e308, "-1.7976931348623157e+308"),
        (333333333.33333329, "333333333.3333333"),
    ],
)
def test_jcs_number_serialization(value: int | float, expected: str) -> None:
    assert canonicalize_json_value(value).decode("ascii") == expected


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_jcs_rejects_non_finite_numbers(value: float) -> None:
    with pytest.raises(ValueError):
        canonicalize_json_value(value)


def test_jcs_rejects_lone_surrogates() -> None:
    with pytest.raises(ValueError):
        canonicalize_json_value("\ud800")


def test_jcs_jsonl_uses_lf_without_trailing_whitespace() -> None:
    events = [
        {"kind": "MEASUREMENT", "t": 2, "measurement_id": "B"},
        {"kind": "DEVICE_EVENT", "t": 1, "code": "INIT"},
    ]

    payload = canonicalize_hail_jsonl(events)

    assert payload == b'{"code":"INIT","kind":"DEVICE_EVENT","t":1}\n{"kind":"MEASUREMENT","measurement_id":"B","t":2}'
    assert not payload.endswith(b"\n")
    assert canonical_payload(events) == payload.decode("utf-8")


def test_hail_event_ordering_uses_rimgb_hash_tie_breaker() -> None:
    events = [
        {"kind": "RUNTIME_STATE_SNAPSHOT", "t": 0, "rimgb_hash": "sha256:z"},
        {"kind": "RUNTIME_STATE_SNAPSHOT", "t": 0, "rimgb_hash": "sha256:a"},
    ]

    assert canonicalize_events(events) == [
        '{"kind":"RUNTIME_STATE_SNAPSHOT","rimgb_hash":"sha256:a","t":0}',
        '{"kind":"RUNTIME_STATE_SNAPSHOT","rimgb_hash":"sha256:z","t":0}',
    ]


def test_hail_digest_is_over_exact_canonical_bytes() -> None:
    events = [{"kind": "DEVICE_EVENT", "t": 1, "code": "INIT"}]

    assert compute_digest(events) == hashlib.sha256(canonicalize_hail_jsonl(events)).hexdigest()


def test_klein_hail_canon_cli_checks_fixture(capsys: pytest.CaptureFixture[str]) -> None:
    input_path = FIXTURES / "hail_events_unsorted.jsonl"
    expected_path = FIXTURES / "hail_events_expected_canonical.jsonl"

    exit_code = hail_canon_main([str(input_path), "--check", str(expected_path), "--digest"])

    assert exit_code == 0
    assert capsys.readouterr().out.startswith("sha256:")


def test_klein_hail_canon_cli_rejects_bad_digest(capsys: pytest.CaptureFixture[str]) -> None:
    input_path = FIXTURES / "hail_events_unsorted.jsonl"

    exit_code = hail_canon_main([str(input_path), "--check-digest", "0" * 64])

    assert exit_code == 1
    assert "digest mismatch" in capsys.readouterr().err


def test_klein_hail_canon_cli_accepts_prefixed_digest(capsys: pytest.CaptureFixture[str]) -> None:
    input_path = FIXTURES / "hail_events_unsorted.jsonl"

    exit_code = hail_canon_main(
        [
            str(input_path),
            "--check-digest",
            "sha256:e85eedb37e0e13857cad58d9708f1374f9fcf415bb30fa6fa99a4c4d086d3a87",
        ]
    )

    assert exit_code == 0
    assert capsys.readouterr().err == ""


def test_klein_hail_canon_cli_rejects_invalid_hail(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    invalid = tmp_path / "invalid.jsonl"
    invalid.write_text(
        '{"kind":"DEVICE_EVENT","t":0,"timebase":"DEVICE_TICKS","run_id":"R1","code":"INIT","level":"INFO"}\n',
        encoding="utf-8",
    )

    exit_code = hail_canon_main([str(invalid), "--digest"])

    assert exit_code == 1
    assert "HAIL validation failed" in capsys.readouterr().err


def test_klein_hail_canon_cli_rejects_duplicate_names(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    invalid = tmp_path / "duplicate.jsonl"
    invalid.write_text(
        '{"kind":"DEVICE_EVENT","kind":"DEVICE_EVENT","t":0,'
        '"timebase":"DEVICE_TICKS","run_id":"R1","code":"INIT","level":"INFO","message":"ok"}\n',
        encoding="utf-8",
    )

    exit_code = hail_canon_main([str(invalid), "--digest"])

    assert exit_code == 1
    assert "duplicate JSON object name" in capsys.readouterr().err


def test_klein_hail_canon_cli_rejects_nan(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    invalid = tmp_path / "nan.jsonl"
    invalid.write_text(
        '{"kind":"MEASUREMENT","t":0,"timebase":"DEVICE_TICKS","run_id":"R1",'
        '"detector_id":"sensor","measurement_id":"m1","value":{"type":"F64","data":NaN}}\n',
        encoding="utf-8",
    )

    exit_code = hail_canon_main([str(invalid), "--digest"])

    assert exit_code == 1
    assert "non-finite JSON number" in capsys.readouterr().err


def test_klein_hail_canon_cli_rejects_crlf_expected(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = FIXTURES / "hail_events_unsorted.jsonl"
    expected = tmp_path / "expected.jsonl"
    expected.write_bytes((FIXTURES / "hail_events_expected_canonical.jsonl").read_bytes() + b"\r\n")

    exit_code = hail_canon_main([str(input_path), "--check", str(expected)])

    assert exit_code == 1
    assert "must use LF line endings" in capsys.readouterr().err


def test_klein_hail_canon_cli_writes_exact_output_bytes(tmp_path: Path) -> None:
    input_path = FIXTURES / "hail_events_unsorted.jsonl"
    output_path = tmp_path / "canonical.jsonl"
    expected = _expected_bytes(FIXTURES / "hail_events_expected_canonical.jsonl")

    exit_code = hail_canon_main([str(input_path), "--output", str(output_path)])

    assert exit_code == 0
    assert output_path.read_bytes() == expected


def test_dump_canonical_uses_jcs_number_form() -> None:
    assert dump_canonical({"n": 1e-6, "m": 1e20}) == '{"m":100000000000000000000,"n":0.000001}'


def _expected_bytes(path: Path) -> bytes:
    payload = path.read_bytes()
    return payload[:-1] if payload.endswith(b"\n") else payload


def test_cross_language_json_fixtures_match_expected_bytes_and_digests() -> None:
    base = FIXTURES / "cross_language"
    for name in ["object_ordering", "number_formatting", "string_unicode"]:
        input_value = json.loads((base / f"{name}_input.json").read_text(encoding="utf-8"))
        canonical = canonicalize_json_value(input_value)
        expected = _expected_bytes(base / f"{name}_expected.json")
        expected_digest = (base / f"{name}_expected.sha256").read_text(encoding="utf-8").strip()

        assert canonical == expected
        assert "sha256:" + hashlib.sha256(canonical).hexdigest() == expected_digest


def test_cross_language_hail_fixture_matches_expected_bytes_and_digest() -> None:
    from klein.hail.validation import parse_jsonl_events

    base = FIXTURES / "cross_language"
    validation, events = parse_jsonl_events(
        (base / "hail_ordering_input.jsonl").read_text(encoding="utf-8")
    )
    assert validation.ok
    canonical = canonicalize_hail_jsonl(events)
    expected = _expected_bytes(base / "hail_ordering_expected.jsonl")
    expected_digest = (base / "hail_ordering_expected.sha256").read_text(encoding="utf-8").strip()

    assert canonical == expected
    assert "sha256:" + hashlib.sha256(canonical).hexdigest() == expected_digest
