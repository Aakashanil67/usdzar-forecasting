"""
run_all.py - Reproduce the analysis.

    python src/run_all.py             # rebuild everything from the committed raw files
    python src/run_all.py --refresh   # first download a new dated raw snapshot

The default needs no network access and takes about five minutes. A refresh
writes to data/raw/snapshots/<date>/ and leaves the committed raw files alone;
copy a snapshot over data/raw/ by hand if you decide to adopt it.

Stops at the first step that exits nonzero, so a failed audit fails the run.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

PY_STEPS = [
    ("verify_provenance.py", "check EconData against the SARB Web API"),
    ("build_dataset.py", "build the weekly Friday dataset"),
    ("run_backtest.py", "walk-forward out-of-sample backtest"),
    ("timing_sensitivity.py", "rerun with every non-spot predictor a week later"),
    ("statistical_tests.py", "DM tests, Holm adjustment, planning table"),
    ("diagnostics.py", "bias, direction, error correlation, weight ranges"),
    ("make_figures.py", "report figures"),
    ("make_presentation_figures.py", "presentation figures"),
    ("validate_results.py", "independent audit of the outputs"),
    ("render_docs.py", "fill the README and methodology from the outputs"),
    ("make_report.py", "build the technical report PDF"),
    ("build_notebook.py", "regenerate and execute the walkthrough notebook"),
]


def run(cmd, cwd=None):
    if subprocess.run(cmd, cwd=cwd).returncode:
        sys.exit(f"FAILED: {' '.join(map(str, cmd))}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--refresh", action="store_true",
                    help="download raw series into data/raw/snapshots/<today>/ first")
    args = ap.parse_args()

    steps = list(PY_STEPS)
    if args.refresh:
        steps.insert(0, ("fetch_data.py", "download a new dated raw snapshot"))
    n = len(steps) + 1                     # + the deck, built with Node

    for i, (script, what) in enumerate(steps, 1):
        print(f"\n[{i}/{n}] {script} - {what}")
        run([sys.executable, str(HERE / script)])

    print(f"\n[{n}/{n}] make_presentation.js - build reports/presentation.pptx")
    if not (HERE / "node_modules").exists():
        run([shutil.which("npm") or "npm", "ci"], cwd=HERE)
    run([shutil.which("node") or "node", "make_presentation.js"], cwd=HERE)

    print("\nDone. See figures/, reports/ and data/processed/.")
    print("Run the test suite with:  pytest -q")


if __name__ == "__main__":
    main()
