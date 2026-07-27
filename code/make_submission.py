"""
make_submission.py — Assembles submission/ : exactly what gets emailed, plus a
manifest. Always rebuilt from the current artifacts, so it can never drift out
of sync with the live results.

Run last:  python code/make_submission.py
"""
import datetime as dt
import hashlib
import json
import shutil
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SUB = BASE / "submission"
MET = json.load(open(BASE / "data" / "processed" / "metrics.json"))

TEAM = "Spurious Decision"
MEMBERS = "Aakash Anil and Stefan von der Heyden"

# (source, destination name)
ITEMS = [
    ("report/Project_Report.pdf", "01_Project_Report.pdf"),
    ("presentation/Deck.pptx", "02_Presentation.pptx"),
    ("data/processed/forecast_log.csv", "03_forecast_log.csv"),
    ("data/processed/metrics.json", "04_metrics.json"),
    ("data/processed/validation_metrics.json", "05_validation_metrics.json"),
]
CODE_FILES = ["fetch_data.py", "econdata_verify.py", "build_dataset.py",
              "models_backtest.py", "make_figures.py", "make_report.py",
              "make_guide.py", "make_slide_figures.py", "verify_charts.py",
              "final_check.py",
              "run_all.py", "README.md"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def main() -> None:
    if SUB.exists():
        shutil.rmtree(SUB)
    (SUB / "code").mkdir(parents=True)
    (SUB / "figures").mkdir()

    rows = []
    for src, dst in ITEMS:
        s = BASE / src
        shutil.copy2(s, SUB / dst)
        rows.append((dst, f"{s.stat().st_size / 1024:.0f} KB", sha(s)))
    for f in CODE_FILES:
        shutil.copy2(BASE / "code" / f, SUB / "code" / f)
    for f in sorted((BASE / "figures").glob("*.png")):
        shutil.copy2(f, SUB / "figures" / f.name)
    for f in sorted((BASE / "figures" / "slides").glob("*.png")):
        shutil.copy2(f, SUB / "figures" / f.name)

    b = MET["AR1_log"]["rmse"]
    lines = [
        f"SES x CODERA ANALYTICS HACKATHON - SUBMISSION",
        f"Team: {TEAM}",
        f"Members: {MEMBERS}, Stellenbosch University",
        f"Prepared: {dt.datetime.now():%Y-%m-%d %H:%M}",
        "",
        "HEADLINE RESULT",
        f"  Our model (forecast combination) RMSE : {MET['COMBO']['rmse']:.4f}",
        f"  AR(1) benchmark RMSE                  : {b:.4f}",
        f"  Improvement                           : "
        f"{100 * (1 - MET['COMBO']['rmse'] / b):+.2f}%",
        f"  Out-of-sample forecasts               : {MET['COMBO']['n']} "
        f"(every Friday, 2021-01-01 to 2025-12-26)",
        f"  Target series                         : SARB EXCX135 via EconData "
        f"(MARKET_RATES 1.0.0, EXCX135.B.A)",
        "",
        "CONTENTS",
        "  01_Project_Report.pdf          The formal report: model, data, "
        "methodology, results, charts.",
        "  02_Presentation.pptx           Judge-facing deck (speaker notes "
        "included).",
        "  03_forecast_log.csv            Every one of the "
        f"{MET['COMBO']['n']} forecasts with its origin date, target date, each",
        "                                 model's forecast and the realised "
        "value. Our proof of out-of-sample.",
        "  04_metrics.json                All accuracy metrics, Diebold-Mariano "
        "tests, per-year breakdown.",
        "  05_validation_metrics.json     The 2015-2020 validation grid that "
        "selected our frozen configuration.",
        "  code/                          Complete pipeline. Reproduce with: "
        "python code/run_all.py",
        "  figures/                       All charts at full resolution.",
        "",
        "REPRODUCING OUR RESULTS",
        "  pip install pandas numpy scikit-learn matplotlib requests reportlab "
        "pillow",
        "  python code/run_all.py         (about 4 minutes; no API keys "
        "required)",
        "",
        "FILE INTEGRITY (SHA-256, first 12 characters)",
    ]
    for name, size, h in rows:
        lines.append(f"  {name:<34} {size:>9}   {h}")
    (SUB / "00_README.txt").write_text("\n".join(lines) + "\n",
                                       encoding="utf-8")

    n = sum(1 for _ in SUB.rglob("*") if _.is_file())
    size = sum(f.stat().st_size for f in SUB.rglob("*") if f.is_file())
    print(f"submission/ built: {n} files, {size / 1024 / 1024:.1f} MB")
    print("email this folder (zipped) to 28399323@sun.ac.za with the "
          "completed submission form")


if __name__ == "__main__":
    main()
