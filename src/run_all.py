"""
run_all.py - Reproduce the entire analysis from raw data.

    python src/run_all.py

Runs in about five minutes. Deterministic: every published number reproduces
to twelve decimal places. No API keys and no paid data are required.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

STEPS = [
    ("fetch_data.py", "download every raw series"),
    ("verify_provenance.py", "check EconData against the SARB Web API"),
    ("build_dataset.py", "build the weekly Friday dataset"),
    ("run_backtest.py", "walk-forward out-of-sample backtest"),
    ("statistical_tests.py", "DM matrix, power analysis, rolling accuracy"),
    ("make_figures.py", "report figures"),
    ("make_presentation_figures.py", "presentation figures"),
    ("validate_results.py", "audit every plotted number against raw data"),
    ("make_report.py", "build the technical report PDF"),
    ("build_notebook.py", "regenerate the walkthrough notebook"),
]

for i, (script, what) in enumerate(STEPS, 1):
    print(f"\n[{i}/{len(STEPS)}] {script} - {what}")
    if subprocess.run([sys.executable, str(HERE / script)]).returncode:
        sys.exit(f"FAILED at {script}")

print("\nDone. See figures/, reports/ and data/processed/.")
print("Run the test suite with:  pytest -q")
