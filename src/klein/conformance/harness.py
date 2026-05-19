#!/usr/bin/env python3
"""Compatibility exports for the Klein conformance harness."""

from __future__ import annotations

from klein.conformance.backends import *  # noqa: F403
from klein.conformance.cli import (  # noqa: F401
    main,
    parse_args,
    print_failure_details,
    print_result,
)
from klein.conformance.comparison import *  # noqa: F403
from klein.conformance.errors import *  # noqa: F403
from klein.conformance.models import *  # noqa: F403
from klein.conformance.runner import run_vector  # noqa: F401
from klein.conformance.suite import *  # noqa: F403

if __name__ == "__main__":
    raise SystemExit(main())
