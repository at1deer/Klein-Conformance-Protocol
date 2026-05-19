from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from klein.conformance.levels import (
    ConformanceLevelError,
    get_conformance_level,
    load_conformance_level_catalog,
    validate_conformance_level_catalog,
    verify_capability_declared_levels,
)
from klein.crypto.capabilities import BackendCapabilityError, load_backend_capability_declaration
from klein.tools.conformance_levels import main as levels_main

CATALOG = Path("specs/catalogs/conformance_levels.v1.json")
CAP = Path("tests/fixtures/capabilities/full_simulator_dmf_capabilities_signed.json")
UNKNOWN = Path("tests/fixtures/conformance_levels/capability_unknown_level.json")
FUTURE = Path("tests/fixtures/conformance_levels/capability_future_level_claim.json")
MISSING = Path("tests/fixtures/conformance_levels/capability_missing_dependency.json")


def test_catalog_validates_and_ids_are_unique() -> None:
    catalog = load_conformance_level_catalog(CATALOG)
    ids = [level["level_id"] for level in catalog["levels"]]

    assert len(ids) == len(set(ids))
    assert get_conformance_level("KCP-Core-Signed-Conformance-v1", catalog)["status"] == "implemented"


def test_requires_references_existing_levels_and_alpha_avoids_future_only() -> None:
    catalog = load_conformance_level_catalog(CATALOG)
    by_id = {level["level_id"]: level for level in catalog["levels"]}

    for level in catalog["levels"]:
        for dependency in level["requires"]:
            assert dependency in by_id
            assert not (level["layer"] == "CURRENT_ALPHA" and by_id[dependency]["status"] == "future")


def test_implemented_levels_have_evidence() -> None:
    catalog = load_conformance_level_catalog(CATALOG)

    for level in catalog["levels"]:
        if level["status"] == "implemented":
            evidence = level["evidence"]
            assert evidence["specs"] or evidence["tests"] or evidence["fixtures"]


def test_capability_declared_levels_exist_and_verify() -> None:
    declaration = load_backend_capability_declaration(CAP)
    result = verify_capability_declared_levels(declaration, load_conformance_level_catalog(CATALOG))

    assert result.ok
    assert "KCP-Core-Signed-Conformance-v1" in result.verified_levels


def test_unknown_level_fails() -> None:
    try:
        load_backend_capability_declaration(UNKNOWN)
    except BackendCapabilityError as exc:
        assert exc.error_code == "CONFORMANCE_LEVEL_UNKNOWN"
    else:
        raise AssertionError("unknown level should fail")


def test_future_hil_level_claim_fails() -> None:
    try:
        load_backend_capability_declaration(FUTURE)
    except BackendCapabilityError as exc:
        assert exc.error_code == "CONFORMANCE_LEVEL_FUTURE_UNSUPPORTED"
    else:
        raise AssertionError("future HIL level should fail")


def test_missing_required_dependency_fails() -> None:
    try:
        load_backend_capability_declaration(MISSING)
    except BackendCapabilityError as exc:
        assert exc.error_code == "CONFORMANCE_LEVEL_DEPENDENCY_MISSING"
    else:
        raise AssertionError("missing dependency should fail")


def test_dmf_simulator_requires_dmf_payload() -> None:
    declaration = json.loads(CAP.read_text())
    levels = declaration["payload"]["supported_conformance_levels"]
    declaration["payload"]["supported_conformance_levels"] = [
        level for level in levels if level != "KCP-Profile-DMF-Payload-v1"
    ]
    result = verify_capability_declared_levels(declaration, load_conformance_level_catalog(CATALOG))

    assert not result.ok
    assert result.error_code == "CONFORMANCE_LEVEL_DEPENDENCY_MISSING"


def test_partial_level_is_allowed() -> None:
    declaration = load_backend_capability_declaration(CAP)
    result = verify_capability_declared_levels(declaration, load_conformance_level_catalog(CATALOG))

    assert result.ok
    assert "KCP-Core-RustVerifier-Fixture-v1" in result.verified_levels


def test_cycle_fails_if_introduced() -> None:
    catalog = load_conformance_level_catalog(CATALOG)
    catalog = deepcopy(catalog)
    catalog["levels"][0]["requires"] = [catalog["levels"][1]["level_id"]]
    catalog["levels"][1]["requires"] = [catalog["levels"][0]["level_id"]]

    try:
        validate_conformance_level_catalog(catalog)
    except ConformanceLevelError as exc:
        assert exc.error_code == "CONFORMANCE_LEVEL_CYCLE"
    else:
        raise AssertionError("cycle should fail")


def test_conformance_levels_cli(capsys) -> None:
    assert levels_main(["validate-catalog"]) == 0
    assert "Conformance level catalog valid" in capsys.readouterr().out

    assert levels_main(["show", "KCP-Core-Signed-Conformance-v1"]) == 0
    assert "KCP-Core-Signed-Conformance-v1" in capsys.readouterr().out

    assert levels_main(["verify-capabilities", "--declaration", str(CAP)]) == 0
    assert "dependency_status=pass" in capsys.readouterr().out
