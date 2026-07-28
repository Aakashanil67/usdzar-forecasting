"""
make_figures.py — All charts and tables for the report and deck.
Every figure is saved to figures/ at 200 dpi with labelled axes and titles.

  rmse_by_model.png      : RMSE per model, value printed on every bar (rubric)
  cumulative_error_difference.png    : cumulative squared-error difference AR(1) - COMBO
                            (rising line = COMBO winning), plus vs RW
  forecasts_vs_actual.png      : realized USDZAR at target dates vs COMBO and AR(1)
  input_series.png   : every input series used by the model (rubric)
  combination_weights.png        : combination weights through time
  rmse_by_year.png    : per-year RMSE bars, model vs AR(1) vs RW
  table_summary_stats.csv/png : observation counts + descriptive stats
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
PROC, FIG = BASE / "data" / "processed", BASE / "figures"
FIG.mkdir(exist_ok=True)
plt.rcParams.update({"figure.dpi": 200, "font.size": 9,
                     "axes.grid": True, "grid.alpha": 0.3})

COLORS = {"AR1_log": "#c0392b", "RW": "#7f8c8d", "CARRY": "#e67e22",
          "RIDGE": "#8e44ad", "GBM": "#2c3e50", "COMBO": "#1a7a4a"}
NICE = {"AR1_log": "AR(1) baseline", "RW": "Random walk", "CARRY": "Carry",
        "RIDGE": "Ridge", "GBM": "Grad. boosting", "COMBO": "Combination"}


def main() -> None:
    ev = pd.read_csv(PROC / "forecast_log.csv", parse_dates=["origin",
                                                             "target_date"])
    ev = ev.set_index("origin")
    met = json.load(open(PROC / "metrics.json"))
    models = ["AR1_log", "RW", "CARRY", "RIDGE", "GBM", "COMBO"]

    # ---- fig 1: RMSE bars with numbers --------------------------------
    fig, ax = plt.subplots(figsize=(7.2, 4))
    rmses = [met[m]["rmse"] for m in models]
    bars = ax.bar([NICE[m] for m in models], rmses,
                  color=[COLORS[m] for m in models])
    for b, v in zip(bars, rmses):
        ax.annotate(f"{v:.4f}", (b.get_x() + b.get_width() / 2, v),
                    ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.set_ylabel("RMSE (rand per USD)")
    ax.set_title("Out-of-sample RMSE, 1-month-ahead USDZAR forecasts every Friday\n"
                 f"2021-01-01 to 2025-12-31  (n = {met['COMBO']['n']} forecasts)")
    ax.set_ylim(0, max(rmses) * 1.15)
    plt.xticks(rotation=12)
    fig.tight_layout(); fig.savefig(FIG / "rmse_by_model.png"); plt.close(fig)

    # ---- fig 1b: % improvement vs AR(1) -------------------------------
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    base = met["AR1_log"]["rmse"]
    others = ["RW", "CARRY", "RIDGE", "GBM", "COMBO"]
    imp = [100 * (1 - met[m]["rmse"] / base) for m in others]
    bars = ax.barh([NICE[m] for m in others], imp,
                   color=[COLORS[m] for m in others])
    for b, v in zip(bars, imp):
        ax.annotate(f"{v:+.2f}%", (v, b.get_y() + b.get_height() / 2),
                    va="center", ha="left" if v >= 0 else "right",
                    fontsize=9, fontweight="bold")
    ax.axvline(0, color="black", lw=0.8)
    ax.set_xlabel("RMSE improvement vs AR(1) baseline (%)  —  positive = better")
    ax.set_title("Relative accuracy vs the AR(1) baseline (judged window)")
    ax.set_xlim(min(imp) * 1.35, max(imp) * 1.8)
    fig.tight_layout(); fig.savefig(FIG / "relative_improvement.png")
    plt.close(fig)

    # ---- fig 2: cumulative squared-error difference -------------------
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    d_ar1 = ((ev["AR1_log"] - ev["realized"]) ** 2
             - (ev["COMBO"] - ev["realized"]) ** 2).cumsum()
    d_rw = ((ev["RW"] - ev["realized"]) ** 2
            - (ev["COMBO"] - ev["realized"]) ** 2).cumsum()
    ax.plot(d_ar1, color=COLORS["COMBO"], label="vs AR(1) baseline")
    ax.plot(d_rw, color=COLORS["RW"], ls="--", label="vs random walk")
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title("Cumulative squared-error difference (positive = combination ahead)")
    ax.set_ylabel("cum. SE difference"); ax.legend()
    fig.tight_layout(); fig.savefig(FIG / "cumulative_error_difference.png"); plt.close(fig)

    # ---- fig 3: forecasts vs realized ---------------------------------
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    ax.plot(ev["target_date"], ev["realized"], color="black", lw=1.2,
            label="Realized USDZAR (EXCX135)")
    ax.plot(ev["target_date"], ev["COMBO"], color=COLORS["COMBO"], lw=1,
            alpha=0.85, label="Combination forecast")
    ax.plot(ev["target_date"], ev["AR1_log"], color=COLORS["AR1_log"], lw=0.9,
            alpha=0.7, label="AR(1) forecast")
    ax.set_title("1-month-ahead forecasts vs realized values at each target date")
    ax.set_ylabel("Rand per USD"); ax.legend()
    fig.tight_layout(); fig.savefig(FIG / "forecasts_vs_actual.png"); plt.close(fig)

    # ---- fig 4: input series panel ------------------------------------
    w = pd.read_csv(PROC / "weekly.csv", parse_dates=["friday"]).set_index("friday")
    panels = [("spot", "USDZAR spot (EXCX135)"), ("carry_diff", "JIBAR 3M − US 3M T-bill (decimal)"),
              ("gold", "Gold, USD/oz"), ("platinum", "Platinum, USD/oz"),
              ("brent", "Brent, USD/bbl"), ("usd_broad", "Broad USD index"),
              ("vix", "VIX"), ("ma_gap", "log gap to 200-day MA")]
    fig, axes = plt.subplots(4, 2, figsize=(8.6, 8.4), sharex=True)
    for ax, (col, title) in zip(axes.ravel(), panels):
        ax.plot(w.index, w[col], lw=0.7, color="#1f5fa8")
        ax.set_title(title, fontsize=8.5)
    fig.suptitle("Series used in the model (weekly, as-of each Friday)", y=0.995)
    fig.tight_layout(); fig.savefig(FIG / "input_series.png"); plt.close(fig)

    # ---- fig 5: combination weights -----------------------------------
    wl = pd.read_csv(PROC / "combo_weights.csv", index_col=0, parse_dates=True)
    wl = wl[wl.index >= "2021-01-01"]
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    ax.stackplot(wl.index, wl["RW"], wl["CARRY"], wl["RIDGE"],
                 labels=["Random walk", "Carry", "Ridge"],
                 colors=[COLORS["RW"], COLORS["CARRY"], COLORS["RIDGE"]],
                 alpha=0.85)
    ax.set_ylim(0, 1); ax.legend(loc="lower left", ncol=3)
    ax.set_title("Combination weights over time (inverse discounted-MSE, resolved errors only)")
    fig.tight_layout(); fig.savefig(FIG / "combination_weights.png"); plt.close(fig)

    # ---- fig 6: per-year RMSE -----------------------------------------
    yearly = met["_yearly"]
    yrs = sorted(yearly)
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    width = 0.27
    for k, mname in enumerate(["AR1_log", "RW", "COMBO"]):
        vals = [yearly[y][mname] for y in yrs]
        ax.bar(np.arange(len(yrs)) + (k - 1) * width, vals, width,
               color=COLORS[mname], label=NICE[mname])
        for xpos, v in zip(np.arange(len(yrs)) + (k - 1) * width, vals):
            ax.annotate(f"{v:.3f}", (xpos, v), ha="center", va="bottom",
                        fontsize=6.5)
    ax.set_xticks(range(len(yrs))); ax.set_xticklabels(yrs)
    ax.set_ylabel("RMSE"); ax.legend()
    ax.set_title("RMSE by calendar year of forecast origin")
    fig.tight_layout(); fig.savefig(FIG / "rmse_by_year.png"); plt.close(fig)

    # ---- summary statistics table -------------------------------------
    est = w[w.index < "2021-01-01"]; fc = w[w.index >= "2021-01-01"]
    tbl = pd.DataFrame({
        "obs_estimation_era(<2021)": est[["spot", "carry_diff", "gold",
                                          "platinum", "brent", "usd_broad",
                                          "vix"]].count(),
        "obs_forecast_era(2021-25)": fc.loc[:"2025-12-31",
                                            ["spot", "carry_diff", "gold",
                                             "platinum", "brent", "usd_broad",
                                             "vix"]].count(),
        "mean": w[["spot", "carry_diff", "gold", "platinum", "brent",
                   "usd_broad", "vix"]].mean().round(3),
        "std": w[["spot", "carry_diff", "gold", "platinum", "brent",
                  "usd_broad", "vix"]].std().round(3),
        "min": w[["spot", "carry_diff", "gold", "platinum", "brent",
                  "usd_broad", "vix"]].min().round(3),
        "max": w[["spot", "carry_diff", "gold", "platinum", "brent",
                  "usd_broad", "vix"]].max().round(3)})
    tbl.to_csv(PROC / "table_summary_stats.csv")
    fig, ax = plt.subplots(figsize=(8.6, 2.6)); ax.axis("off")
    t = ax.table(cellText=tbl.values, rowLabels=tbl.index,
                 colLabels=tbl.columns, loc="center", cellLoc="center")
    t.auto_set_font_size(False); t.set_fontsize(7); t.scale(1, 1.25)
    ax.set_title("Summary statistics — weekly (Friday) series", fontsize=10)
    fig.tight_layout(); fig.savefig(FIG / "summary_statistics.png")
    plt.close(fig)
    print("figures written:", sorted(p.name for p in FIG.iterdir()))


if __name__ == "__main__":
    main()
