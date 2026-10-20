#!/usr/bin/env python3
"""Command-line entry point for frozen source metadata audits."""

from __future__ import annotations

import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from film_values.retrieval_controls import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
