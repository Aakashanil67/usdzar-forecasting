"""
make_figures.py - All charts and tables for the report and deck.
Every figure is saved to figures/ at 200 dpi with labelled axes and titles.

  rmse_by_model.png      : RMSE per model, value printed on every bar (rubric)
  rmse_difference_ci.png : RMSE difference from RW and from AR(1), 95% CIs
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
        "RIDGE": "Ridge", "GBM": "Grad. boosting", "COMBO": "Combination",
        "AR1_level": "AR(1) on the level", "AR1_log_roll": "AR(1), 5-year window",
        "AR1_log_vc": "AR(1), mean-corrected", "RW_drift": "Random walk + drift",
        "EQUAL3": "Equal-weight RW+carry+ridge", "RW_CARRY": "Adaptive RW+carry",
        "RW_RIDGE": "Adaptive RW+ridge"}
FOCAL, MUTED_DOT = "#1a7a4a", "#a0a8b0"
DOT_ROWS = ["COMBO", "EQUAL3", "RW_CARRY", "RW_RIDGE", "CARRY", "RIDGE", "GBM",
            "RW_drift", "RW", "AR1_log", "AR1_log_vc", "AR1_log_roll", "AR1_level"]


def rmse_difference_dots(tests: dict) -> None:
    """RMSE(model) - RMSE(benchmark) with the 95% CI from the lag-3 HAC
    interval of the mean loss differential. Filled green marks the two
    prespecified comparisons; the rest are exploratory."""
    by = {(c["model"], c["benchmark"]): c for c in tests["comparisons"]}
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 4.6), sharey=True, sharex=True)
    y = np.arange(len(DOT_ROWS))[::-1]
    for ax, bench, title in zip(axes, ["RW", "AR1_log"],
                                ["vs random walk", "vs AR(1) baseline"]):
        for yy, m in zip(y, DOT_ROWS):
            c = by.get((m, bench))
            if c is None:
                ax.annotate("benchmark", (0, yy), ha="center", va="center",
                            fontsize=7.5, color="#555555", style="italic",
                            bbox=dict(fc="white", ec="none", pad=1))
                continue
            pre = c["role"] == "prespecified"
            col = FOCAL if pre else MUTED_DOT
            lo, hi = c["rmse_difference_ci95"]
            ax.plot([lo, hi], [yy, yy], color=col, lw=2.2 if pre else 1.6,
                    solid_capstyle="round", zorder=2)
            ax.plot(c["rmse_difference"], yy, "o", ms=7 if pre else 6,
                    mfc=col if pre else "white", mec=col, mew=1.6, zorder=3)
            if not pre and c["p_holm"] < 0.05:
                ax.annotate("*", (hi, yy), xytext=(4, -3), textcoords="offset points",
                            fontsize=11, color="#333333")
        ax.axvline(0, color="black", lw=0.8, zorder=1)
        ax.set_title(title)
        ax.grid(axis="y", alpha=0)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels([NICE[m] for m in DOT_ROWS])
    for t, m in zip(axes[0].get_yticklabels(), DOT_ROWS):
        t.set_fontweight("bold" if m == "COMBO" else "normal")
    fig.supxlabel("RMSE(model) - RMSE(benchmark), rand per USD; "
                  "left of zero = model more accurate", fontsize=8.5)
    handles = [plt.Line2D([], [], color=FOCAL, marker="o", lw=2.2, ms=7,
                          label="prespecified, p unadjusted"),
               plt.Line2D([], [], color=MUTED_DOT, marker="o", mfc="white",
                          mew=1.6, lw=1.6, ms=6,
                          label="exploratory, * Holm-adjusted p < 0.05")]
    fig.legend(handles=handles, loc="upper center", ncol=2, frameon=False,
               bbox_to_anchor=(0.5, 0.955), fontsize=8)
    fig.suptitle("RMSE difference from each benchmark with 95% CI (Newey-West, lag 3), "
                 f"judged window, n = {tests['planning']['vs']['RW']['current_n']}")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(FIG / "rmse_difference_ci.png")
    plt.close(fig)


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

    # ---- fig 1b: RMSE difference from each benchmark, with CI ---------
    rmse_difference_dots(json.load(open(PROC / "statistical_tests.json")))

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
    fig.suptitle("Series used in the model, as known at each Friday 17:00 issuance", y=0.995)
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
    ax.set_title("Summary statistics - weekly (Friday) series", fontsize=10)
    fig.tight_layout(); fig.savefig(FIG / "summary_statistics.png")
    plt.close(fig)
    print("figures written:", sorted(p.name for p in FIG.iterdir()))


if __name__ == "__main__":
    main()
