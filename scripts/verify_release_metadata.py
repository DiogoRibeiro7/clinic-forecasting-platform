"""Validate release metadata without publishing or tagging."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from clinic_forecast.release_metadata import verify_release_metadata


def main() -> int:
    """Validate the current repository release contract."""
    root = Path(__file__).resolve().parents[1]
    summary = verify_release_metadata(root)
    print(json.dumps(asdict(summary), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
