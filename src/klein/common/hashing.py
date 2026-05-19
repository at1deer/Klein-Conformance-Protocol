"""Canonical hashing utilities for Klein evidence-bound data."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MAX_SAFE_INTEGER = 9_007_199_254_740_991
_EXPONENT_RE = re.compile(r"^([+-]?)(\d+)(?:\.(\d+))?[eE]([+-]?\d+)$")


class DuplicateJSONKeyError(ValueError):
    """Raised when a JSON object contains a duplicate member name."""


class NonFiniteJSONNumberError(ValueError):
    """Raised when JSON input uses NaN or Infinity extensions."""


@dataclass(frozen=True)
class HashResult:
    """Structured SHA-256 hash result with canonicalization metadata."""

    algorithm: str
    digest_hex: str
    ref: str
    canonicalization: str


def object_pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """JSON object hook rejecting duplicate member names."""
    seen: set[str] = set()
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise DuplicateJSONKeyError(f"duplicate JSON object name: {key}")
        seen.add(key)
        result[key] = value
    return result


def reject_non_finite_json_number(value: str) -> None:
    """JSON parse hook rejecting NaN and Infinity extensions."""
    raise NonFiniteJSONNumberError(f"non-finite JSON number is not valid Klein I-JSON: {value}")


def parse_ijson(payload: str) -> Any:
    """Parse JSON as Klein I-JSON with duplicate-name and non-finite rejection."""
    return json.loads(
        payload,
        object_pairs_hook=object_pairs_no_duplicates,
        parse_constant=reject_non_finite_json_number,
    )


def sha256_bytes(payload: bytes) -> str:
    """Return a bare SHA-256 hex digest."""
    return hashlib.sha256(payload).hexdigest()


def sha256_ref(payload: bytes) -> str:
    """Return a SHA-256 digest reference using the external Klein ref form."""
    return f"sha256:{sha256_bytes(payload)}"


def raw_file_sha256(path: Path) -> HashResult:
    """Hash file bytes without canonicalization."""
    digest = sha256_bytes(path.read_bytes())
    return HashResult(
        algorithm="sha256",
        digest_hex=digest,
        ref=f"sha256:{digest}",
        canonicalization="raw-bytes",
    )


def _utf16_sort_key(value: str) -> bytes:
    """Return the RFC 8785 object-property ordering key."""
    return value.encode("utf-16-be", "surrogatepass")


def _escape_string(value: str) -> str:
    """Serialize a JSON string using JCS-compatible escaping."""
    out: list[str] = ['"']
    for char in value:
        codepoint = ord(char)
        if 0xD800 <= codepoint <= 0xDFFF:
            raise ValueError("JCS canonical JSON rejects lone UTF-16 surrogate code points")
        if char == '"':
            out.append('\\"')
        elif char == "\\":
            out.append("\\\\")
        elif char == "\b":
            out.append("\\b")
        elif char == "\t":
            out.append("\\t")
        elif char == "\n":
            out.append("\\n")
        elif char == "\f":
            out.append("\\f")
        elif char == "\r":
            out.append("\\r")
        elif codepoint <= 0x1F:
            out.append(f"\\u{codepoint:04x}")
        else:
            out.append(char)
    out.append('"')
    return "".join(out)


def _expand_exponent(sign: str, integer: str, fraction: str, exponent: int) -> str:
    digits = integer + fraction
    decimal_position = len(integer) + exponent
    if decimal_position <= 0:
        expanded = "0." + ("0" * -decimal_position) + digits
    elif decimal_position >= len(digits):
        expanded = digits + ("0" * (decimal_position - len(digits)))
    else:
        expanded = digits[:decimal_position] + "." + digits[decimal_position:]

    if "." in expanded:
        expanded = expanded.rstrip("0").rstrip(".")
    if expanded == "-0" or expanded == "":
        expanded = "0"
    return sign + expanded if expanded != "0" else "0"


def _normalize_exponent(value: str) -> str:
    mantissa, exponent = value.lower().split("e", 1)
    if mantissa.endswith(".0"):
        mantissa = mantissa[:-2]
    exponent_int = int(exponent)
    sign = "+" if exponent_int >= 0 else "-"
    return f"{mantissa}e{sign}{abs(exponent_int)}"


def _format_float(value: float) -> str:
    """Serialize a finite IEEE-754 double using JCS/ECMAScript JSON number rules."""
    if not math.isfinite(value):
        raise ValueError("JCS canonical JSON rejects NaN and Infinity")
    if value == 0:
        return "0"

    absolute = abs(value)
    rendered = repr(value)

    if 1e-6 <= absolute < 1e21:
        match = _EXPONENT_RE.match(rendered)
        if match:
            sign, integer, fraction, exponent = match.groups()
            return _expand_exponent(sign, integer, fraction or "", int(exponent))
        if rendered.endswith(".0"):
            return rendered[:-2]
        return rendered

    if "e" in rendered.lower():
        return _normalize_exponent(rendered)
    return _normalize_exponent(f"{value:.15e}")


def _format_number(value: int | float) -> str:
    if isinstance(value, bool):
        raise TypeError("bool must be serialized as a JSON boolean, not a number")
    if isinstance(value, int):
        if abs(value) > MAX_SAFE_INTEGER:
            raise ValueError("JCS canonical JSON requires integers within the I-JSON safe range")
        return str(value)
    return _format_float(value)


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize an I-JSON value using RFC 8785/JCS canonical JSON."""
    if value is None:
        return b"null"
    if value is True:
        return b"true"
    if value is False:
        return b"false"
    if isinstance(value, str):
        return _escape_string(value).encode("utf-8")
    if isinstance(value, int | float) and not isinstance(value, bool):
        return _format_number(value).encode("ascii")
    if isinstance(value, list):
        return b"[" + b",".join(canonical_json_bytes(item) for item in value) + b"]"
    if isinstance(value, dict):
        items: list[bytes] = []
        keys = list(value)
        for key in keys:
            if not isinstance(key, str):
                raise TypeError("JCS canonical JSON object keys must be strings")
        for key in sorted(keys, key=_utf16_sort_key):
            items.append(canonical_json_bytes(key) + b":" + canonical_json_bytes(value[key]))
        return b"{" + b",".join(items) + b"}"
    raise TypeError(f"Unsupported JCS canonical JSON value: {type(value).__name__}")


def canonical_json_sha256(value: Any) -> str:
    """Hash a value after RFC 8785/JCS canonical JSON serialization."""
    return sha256_bytes(canonical_json_bytes(value))


def canonical_json_sha256_ref(value: Any) -> str:
    """Hash a value after RFC 8785/JCS serialization using sha256:<hex> ref form."""
    return f"sha256:{canonical_json_sha256(value)}"


def hash_json_value(value: Any) -> HashResult:
    """Return the canonical JSON hash result for an already-parsed JSON value."""
    digest = canonical_json_sha256(value)
    return HashResult(
        algorithm="sha256",
        digest_hex=digest,
        ref=f"sha256:{digest}",
        canonicalization="klein.canon.json.v1",
    )


def hash_json_artifact(path: Path) -> HashResult:
    """Parse a JSON artifact as I-JSON and hash its canonical JSON bytes."""
    return hash_json_value(parse_ijson(path.read_text(encoding="utf-8")))
