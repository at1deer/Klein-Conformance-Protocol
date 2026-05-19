from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from klein.crypto.capabilities import (
    BackendCapabilityError,
    load_backend_capability_declaration,
    validate_backend_capability_declaration,
    verify_backend_capability_declaration,
)
from klein.crypto.registry import load_backend_identity_registry
from klein.crypto.trust import load_trust_policy
from klein.tools.backend_capabilities import main as capabilities_main

CAP = Path("tests/fixtures/capabilities/full_simulator_dmf_capabilities_signed.json")
TAMPERED = Path("tests/fixtures/capabilities/full_simulator_dmf_capabilities_tampered.json")
UNTRUSTED = Path("tests/fixtures/capabilities/full_simulator_dmf_capabilities_untrusted.json")
WRONG_PROFILE = Path("tests/fixtures/capabilities/full_simulator_dmf_capabilities_wrong_profile.json")
BAD_DMF = Path("tests/fixtures/capabilities/full_simulator_dmf_capabilities_bad_dmf_ranges.json")
REGISTRY = Path("tests/fixtures/crypto/backend_registry_signed_test.json")
POLICY = Path("tests/fixtures/crypto/trust_policy_registry_authority_test.json")
SUBSTRATE = "sha256:8258d5b8a612dc21efc011543aee1513864840467caa7a8e3b2255be11b2087e"


def _verify(path: Path = CAP, **kwargs):
    return verify_backend_capability_declaration(
        load_backend_capability_declaration(path),
        registry=load_backend_identity_registry(REGISTRY),
        trust_policy=load_trust_policy(POLICY),
        backend_id="full_simulator",
        backend_version="1.0.0a0",
        profile_id="dmf",
        profile_version="v1",
        mode="HARD",
        substrate_fingerprint=SUBSTRATE,
        require_trust=True,
        **kwargs,
    )


def test_valid_signed_capability_declaration_verifies() -> None:
    result = _verify()

    assert result.ok
    assert result.signature_status == "valid"
    assert result.identity_status == "resolved"
    assert result.trust_status == "trusted"
    assert result.capability_scope_status == "pass"


def test_tampered_payload_invalidates_signature() -> None:
    result = _verify(TAMPERED)

    assert not result.ok
    assert result.error_code == "BACKEND_CAPABILITY_SIGNATURE_INVALID"


def test_wrong_backend_key_fails() -> None:
    result = _verify(UNTRUSTED)

    assert not result.ok
    assert result.error_code == "BACKEND_IDENTITY_KEY_NOT_FOUND"


def test_registry_key_mismatch_fails() -> None:
    registry = load_backend_identity_registry(REGISTRY).data
    registry = deepcopy(registry)
    registry["backends"][0]["keys"][0]["public_key"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    result = verify_backend_capability_declaration(
        load_backend_capability_declaration(CAP),
        registry=registry,
        trust_policy=load_trust_policy(POLICY),
        require_trust=True,
    )

    assert not result.ok
    assert result.error_code == "BACKEND_IDENTITY_KEY_MISMATCH"


def test_untrusted_signing_key_fails_without_policy() -> None:
    result = verify_backend_capability_declaration(
        load_backend_capability_declaration(CAP),
        registry=load_backend_identity_registry(REGISTRY),
        trust_policy={"trusted_keys": []},
        require_trust=True,
    )

    assert not result.ok
    assert result.error_code == "BACKEND_CAPABILITY_UNTRUSTED"


def test_unsupported_profile_fails() -> None:
    result = verify_backend_capability_declaration(
        load_backend_capability_declaration(WRONG_PROFILE),
        backend_id="full_simulator",
        profile_id="dmf",
        profile_version="v1",
        mode="HARD",
    )

    assert not result.ok
    assert result.error_code == "BACKEND_CAPABILITY_PROFILE_UNSUPPORTED"


def test_unsupported_mode_fails() -> None:
    result = verify_backend_capability_declaration(
        load_backend_capability_declaration(CAP),
        backend_id="full_simulator",
        profile_id="dmf",
        profile_version="v1",
        mode="UNSUPPORTED",
    )

    assert not result.ok
    assert result.error_code == "BACKEND_CAPABILITY_MODE_UNSUPPORTED"


def test_substrate_fingerprint_mismatch_fails() -> None:
    result = verify_backend_capability_declaration(
        load_backend_capability_declaration(CAP),
        backend_id="full_simulator",
        profile_id="dmf",
        profile_version="v1",
        mode="HARD",
        substrate_fingerprint="sha256:" + "0" * 64,
    )

    assert not result.ok
    assert result.error_code == "BACKEND_CAPABILITY_SUBSTRATE_MISMATCH"


def test_invalid_dmf_ranges_fail() -> None:
    try:
        load_backend_capability_declaration(BAD_DMF)
    except BackendCapabilityError as exc:
        assert exc.error_code == "DMF_CAPABILITIES_INVALID"
    else:
        raise AssertionError("bad DMF capability fixture should fail")


def test_rle_cannot_be_supported_and_unsupported() -> None:
    declaration = load_backend_capability_declaration(CAP)
    declaration["payload"]["profile_capabilities"]["dmf"]["payloads"]["supported_frame_formats"].append("rle")

    try:
        validate_backend_capability_declaration(declaration)
    except BackendCapabilityError as exc:
        assert exc.error_code == "DMF_CAPABILITIES_INVALID"
    else:
        raise AssertionError("conflicting frame format should fail")


def test_hil_capability_claim_requires_contract_hash() -> None:
    declaration = load_backend_capability_declaration(CAP)
    declaration["payload"]["hil"] = {
        "hil_readiness": True,
        "hil_contract_hash": None,
        "hil_levels_supported": ["KCP-Core-HIL-Readiness-v1"],
        "hardware_execution_supported": False,
        "hardware_attestation_supported": False,
    }

    try:
        validate_backend_capability_declaration(declaration)
    except BackendCapabilityError as exc:
        assert exc.error_code == "HIL_CONTRACT_INVALID"
    else:
        raise AssertionError("HIL readiness claim without contract hash should fail")


def test_hil_capability_rejects_hardware_claims() -> None:
    declaration = load_backend_capability_declaration(CAP)
    declaration["payload"]["hil"] = {
        "hil_readiness": True,
        "hil_contract_hash": "sha256:" + "0" * 64,
        "hil_levels_supported": ["KCP-Core-HIL-Readiness-v1"],
        "hardware_execution_supported": True,
        "hardware_attestation_supported": False,
    }

    try:
        validate_backend_capability_declaration(declaration)
    except BackendCapabilityError as exc:
        assert exc.error_code == "HIL_HARDWARE_CLAIM_UNSUPPORTED"
    else:
        raise AssertionError("hardware execution claim should fail")


def test_backend_capabilities_cli(capsys) -> None:
    assert capabilities_main([
        "verify",
        "--declaration",
        str(CAP),
        "--backend-registry",
        str(REGISTRY),
        "--trust-policy",
        str(POLICY),
        "--backend-id",
        "full_simulator",
        "--profile-id",
        "dmf",
        "--profile-version",
        "v1",
        "--mode",
        "HARD",
    ]) == 0

    assert "signature_status=valid" in capsys.readouterr().out
