"""
Pytest configuration for Klein Conformance Tests.

Registers custom options and markers for conformance testing.
"""

from __future__ import annotations

import pytest

def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom pytest options for conformance testing."""
    group = parser.getgroup("conformance", "Klein Conformance Options")
    group.addoption(
        "--full-conformance",
        action="store_true",
        default=False,
        help="Run full conformance suite instead of smoke tests",
    )
    group.addoption(
        "--conformance-backend",
        action="store",
        default="full_simulator",
        choices=["mock", "subprocess", "simulator", "full_simulator"],
        help="Backend to use for conformance tests (default: full_simulator)",
    )
    group.addoption(
        "--conformance-verbose",
        action="store_true",
        default=False,
        help="Show detailed conformance output",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers (also defined in pyproject.toml)."""
    # Markers are also defined in pyproject.toml, but we add them here
    # for IDE support and explicit documentation
    for marker in [
        "conformance: mark test as part of conformance suite",
        "smoke: mark test as smoke test (runs by default)",
        "positive: mark test as positive conformance case",
        "negative: mark test as negative conformance case",
    ]:
        config.addinivalue_line("markers", marker)
