"""Execute notebooks headlessly and report failures clearly.

Used locally via `make notebook-check` and in CI. By default notebooks are
executed in memory so validation does not rewrite tracked files; pass
``--write`` to persist the refreshed outputs. The first failing cell is
reported with its source and error so failures are easy to interpret.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

DEFAULT_NOTEBOOKS = [
    "notebooks/00_business_problem_and_poc_design.ipynb",
    "notebooks/01_synthetic_healthcare_data_generation.ipynb",
    "notebooks/06_staffing_optimization_and_decision_layer.ipynb",
]

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "processed" / "clinic_daily_usage.csv"

#: Notebooks that read the processed data instead of generating their own.
NEEDS_DATA = {"02", "03", "04", "05", "06", "07", "08", "09", "10", "11"}


def parse_args() -> argparse.Namespace:
    """Parse notebook check options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "notebooks",
        nargs="*",
        default=DEFAULT_NOTEBOOKS,
        help="Notebook paths to execute (default: the lightweight smoke set).",
    )
    parser.add_argument(
        "--timeout", type=int, default=900, help="Per-cell timeout in seconds."
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write executed notebooks back to disk instead of validating in memory only.",
    )
    return parser.parse_args()


def run_notebook(path: Path, timeout: int, write: bool) -> bool:
    """Execute one notebook; return True on success and print errors clearly."""
    import nbformat
    from nbclient import NotebookClient
    from nbclient.exceptions import CellExecutionError

    notebook = nbformat.read(path, as_version=4)
    client = NotebookClient(
        notebook,
        timeout=timeout,
        kernel_name="python3",
        resources={"metadata": {"path": str(path.parent)}},
    )
    try:
        client.execute()
    except CellExecutionError as exc:
        print(f"\nFAILED: {path}")
        print(f"  {exc.ename}: {exc.evalue}")
        source = (exc.traceback or "").strip().splitlines()
        for line in source[-5:]:
            print(f"  {line}")
        return False
    if write:
        nbformat.write(notebook, path)
    print(f"ok: {path}")
    return True


def main() -> int:
    """Execute the requested notebooks and return a process exit code."""
    args = parse_args()
    failures = 0
    for raw_path in args.notebooks:
        path = Path(raw_path)
        if not path.exists():
            print(f"FAILED: {path} does not exist.")
            failures += 1
            continue
        prefix = path.name.split("_", 1)[0]
        if prefix in NEEDS_DATA and not DATA_FILE.exists():
            print(
                f"FAILED: {path.name} needs the processed data. "
                "Run `poetry run python scripts/generate_data.py` first."
            )
            failures += 1
            continue
        if not run_notebook(path, args.timeout, args.write):
            failures += 1
    if failures:
        print(f"\n{failures} notebook(s) failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
