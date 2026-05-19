#!/usr/bin/env python3
"""Compatibility wrapper for the packaged container packing tool."""

from klein.tools.pack_kleinc import main


if __name__ == "__main__":
    raise SystemExit(main())
