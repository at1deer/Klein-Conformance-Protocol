"""HAIL validation, canonicalization, and chain helpers."""

from .canonical import (
    canonicalize_events,
    canonicalize_hail_event,
    canonicalize_hail_jsonl,
    canonicalize_json_value,
    compute_digest,
    digest_hail_jsonl,
    dump_canonical,
    event_sort_key,
    hash_hail_jsonl,
)
from .chain import (
    HAIL_CHAIN_ALGORITHM,
    HAIL_CHAIN_DOMAIN,
    HailChainResult,
    HailChainVerification,
    chain_digest_hail_jsonl,
    compute_hail_chain,
    is_canonical_event_order,
    verify_hail_chain,
)
from .validation import (
    HAILValidationResult,
    normalize_legacy_event,
    normalize_legacy_events,
    parse_jsonl_events,
    validate_event,
    validate_events,
    validate_jsonl,
)

__all__ = [
    "HAIL_CHAIN_ALGORITHM",
    "HAIL_CHAIN_DOMAIN",
    "HAILValidationResult",
    "HailChainResult",
    "HailChainVerification",
    "canonicalize_events",
    "canonicalize_hail_event",
    "canonicalize_hail_jsonl",
    "canonicalize_json_value",
    "chain_digest_hail_jsonl",
    "compute_digest",
    "compute_hail_chain",
    "digest_hail_jsonl",
    "dump_canonical",
    "event_sort_key",
    "hash_hail_jsonl",
    "is_canonical_event_order",
    "normalize_legacy_event",
    "normalize_legacy_events",
    "parse_jsonl_events",
    "validate_event",
    "validate_events",
    "validate_jsonl",
    "verify_hail_chain",
]
