"""run_all.py — one-command full reproduction: data -> models -> figures -> report."""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for step in ["fetch_data.py", "econdata_verify.py", "build_dataset.py",
             "models_backtest.py",
             "make_figures.py", "make_slide_figures.py", "verify_charts.py",
             "make_report.py", "make_guide.py"]:
    print(f"\n=== {step} ===")
    r = subprocess.run([sys.executable, str(HERE / step)])
    if r.returncode:
        sys.exit(f"step failed: {step}")
print("\nAll done. See figures/, data/processed/ and report/.")
print("Next: python code/make_submission.py, then python code/final_check.py")
