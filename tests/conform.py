#!/usr/bin/env python3
"""Compatibility wrapper for the packaged conformance harness."""

from klein.conformance.harness import main


if __name__ == "__main__":
    raise SystemExit(main())
