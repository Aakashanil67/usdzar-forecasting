"""
statistical_tests.py - Formal comparison of forecast accuracy.

Three things a single Diebold-Mariano p-value does not answer.

1. Which models differ from which, not only each model against the benchmark.
   Overlapping 4-week forecasts make errors serially correlated, so every test in
   the pairwise matrix uses a Newey-West variance at lag h-1.

2. What significance would have taken. Given the observed variance of the loss
   differential we compute how many origins would be needed to detect an effect of
   this size at 5% with 80% power, and what effect size would have been detectable
   with the 261 origins we had.

3. When the edge was earned. A single full-sample RMSE hides that, so we also
   compute a 52-week rolling RMSE ratio against the benchmark.

Outputs: data/processed/statistical_tests.json and two figures.

Run:  python src/statistical_tests.py
"""
import json
from math import erf, sqrt
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
PROC, FIG = BASE / "data" / "processed", BASE / "figures"

MODELS = ["AR1_log", "RW", "CARRY", "RIDGE", "GBM", "COMBO"]
NICE = {"AR1_log": "AR(1)", "RW": "Random walk", "CARRY": "Carry",
        "RIDGE": "Ridge", "GBM": "Boosting", "COMBO": "Combination"}
H = 4                       # forecast horizon in weeks
LAG = H - 1                 # Newey-West lag for overlapping forecasts
FOCAL, BENCH = "COMBO", "AR1_log"

NAVY, GREEN, MUTED = "#0E2A3B", "#1A7A4A", "#777777"


def normal_cdf(x):
    return 0.5 * (1 + erf(x / sqrt(2)))


def newey_west_var(d, lag=LAG):
    """Long-run variance of the mean of d, Bartlett kernel."""
    n = len(d)
    u = d - d.mean()
    s = u @ u / n
    for k in range(1, lag + 1):
        s += 2 * (1 - k / (lag + 1)) * (u[k:] @ u[:-k]) / n
    return s / n                       # variance OF THE MEAN


def dm_test(e1, e2, lag=LAG):
    """Diebold-Mariano on squared-error loss. Negative favours model 1."""
    d = e1 ** 2 - e2 ** 2
    var = newey_west_var(d, lag)
    stat = d.mean() / np.sqrt(var)
    return float(stat), float(2 * (1 - normal_cdf(abs(stat)))), d


def main():
    log = pd.read_csv(PROC / "forecast_log.csv",
                      parse_dates=["origin", "target_date"]).set_index("origin")
    err = {m: (log[m] - log["realized"]).values for m in MODELS}
    out = {}

    # ------------------------------------------------ 1. pairwise DM matrix
    mat, pmat = {}, {}
    for a in MODELS:
        mat[a], pmat[a] = {}, {}
        for b in MODELS:
            if a == b:
                mat[a][b], pmat[a][b] = 0.0, 1.0
                continue
            s, p, _ = dm_test(err[a], err[b])
            mat[a][b], pmat[a][b] = round(s, 3), round(p, 4)
    out["dm_statistic_matrix"] = mat
    out["dm_pvalue_matrix"] = pmat
    out["dm_note"] = ("Row model against column model, squared-error loss, "
                      "Newey-West variance at lag 3. Negative statistic means "
                      "the ROW model is more accurate. Two-sided p-values.")

    print("Pairwise Diebold-Mariano (row vs column). Negative favours the row.")
    print(f"{'':<14}" + "".join(f"{NICE[c]:>13}" for c in MODELS))
    for a in MODELS:
        print(f"{NICE[a]:<14}" + "".join(
            ("      .      " if a == b else f"{mat[a][b]:>8.2f}"
             f"{'*' if pmat[a][b] < 0.05 else ' '}    ") for b in MODELS))
    print("  * significant at 5%\n")

    # ------------------------------------------------ 2. power calculation
    s_dm, p_dm, d = dm_test(err[FOCAL], err[BENCH])
    n = len(d)
    sd_d = float(np.sqrt(newey_west_var(d, LAG) * n))   # per-observation sd
    z95, z80 = 1.959964, 0.841621

    n_needed = ((z95 + z80) * sd_d / abs(d.mean())) ** 2
    detectable_d = (z95 + z80) * sd_d / np.sqrt(n)
    # translate a detectable loss-differential into an RMSE gap
    mse_b = float((err[BENCH] ** 2).mean())
    detectable_rmse_pct = 100 * (1 - np.sqrt(mse_b - detectable_d) / np.sqrt(mse_b))
    observed_rmse_pct = 100 * (1 - np.sqrt((err[FOCAL] ** 2).mean() / mse_b))

    out["power_analysis"] = {
        "n_origins": int(n),
        "mean_loss_differential": float(d.mean()),
        "newey_west_sd_per_obs": sd_d,
        "dm_statistic": round(s_dm, 3),
        "dm_pvalue": round(p_dm, 4),
        "observed_rmse_improvement_pct": round(observed_rmse_pct, 3),
        "origins_needed_for_80pct_power": int(round(n_needed)),
        "years_of_weekly_origins_needed": round(n_needed / 52, 1),
        "minimum_detectable_rmse_improvement_pct": round(detectable_rmse_pct, 2),
        "interpretation": (
            f"With {n} overlapping origins, the smallest RMSE improvement "
            f"detectable at 5% with 80% power is about "
            f"{detectable_rmse_pct:.2f}%. We observed "
            f"{observed_rmse_pct:.2f}%, which is roughly "
            f"{detectable_rmse_pct / observed_rmse_pct:.0f}x too small to "
            f"clear that bar. Detecting an effect of the size we found would "
            f"need on the order of {n_needed / 52:.0f} years of weekly "
            f"forecasts. A non-significant result here is the expected "
            f"outcome, not evidence the model does nothing.")}

    print("Power analysis for the combination against the AR(1) benchmark")
    for k in ["n_origins", "observed_rmse_improvement_pct",
              "minimum_detectable_rmse_improvement_pct",
              "origins_needed_for_80pct_power",
              "years_of_weekly_origins_needed"]:
        print(f"  {k:<42} {out['power_analysis'][k]}")
    print()

    # ------------------------------------------------ 3. rolling accuracy
    win = 52
    roll = {}
    for m in MODELS:
        se = pd.Series(err[m] ** 2, index=log.index)
        roll[m] = np.sqrt(se.rolling(win).mean())
    # Drop the first win-1 entries: they are NaN while the window fills, and
    # counting them as "not ahead" understates the share.
    ratio = (roll[FOCAL] / roll[BENCH]).dropna()
    out["rolling"] = {
        "window_weeks": win,
        "n_complete_windows": int(len(ratio)),
        "share_of_windows_ahead_of_benchmark": round(float((ratio < 1).mean()), 3),
        "best_window_ratio": round(float(ratio.min()), 4),
        "worst_window_ratio": round(float(ratio.max()), 4)}
    print(f"Rolling {win}-week RMSE ratio (combination / benchmark)")
    print(f"  ahead of the benchmark in "
          f"{100 * out['rolling']['share_of_windows_ahead_of_benchmark']:.0f}% "
          f"of windows")
    print(f"  best {ratio.min():.4f}, worst {ratio.max():.4f}\n")

    # ---- figure: rolling ratio
    fig, ax = plt.subplots(figsize=(9.2, 4.4))
    v = ratio
    ax.fill_between(v.index, 1, v.values, where=(v.values < 1),
                    color=GREEN, alpha=0.30, interpolate=True,
                    label="combination ahead")
    ax.fill_between(v.index, 1, v.values, where=(v.values >= 1),
                    color="#B03A2E", alpha=0.22, interpolate=True,
                    label="benchmark ahead")
    ax.plot(v.index, v.values, color=NAVY, lw=1.9)
    ax.axhline(1, color="#444444", lw=1.2)
    ax.set_ylabel(f"{win}-week rolling RMSE ratio\n(combination / AR(1))",
                  fontsize=11)
    ax.set_title("Below 1.00 means the combination was the more accurate of the "
                 "two", fontsize=12.5, color=NAVY, pad=12)
    ax.legend(frameon=False, fontsize=10, loc="upper left", ncol=2)
    ax.grid(alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(FIG / "rolling_rmse_ratio.png", dpi=200, facecolor="white")
    plt.close(fig)

    # ---- figure: DM heatmap
    arr = np.array([[mat[a][b] for b in MODELS] for a in MODELS], float)
    fig, ax = plt.subplots(figsize=(7.6, 6.2))
    lim = np.abs(arr).max()
    im = ax.imshow(arr, cmap="RdYlGn_r", vmin=-lim, vmax=lim)
    ax.set_xticks(range(len(MODELS)))
    ax.set_xticklabels([NICE[m] for m in MODELS], rotation=35, ha="right")
    ax.set_yticks(range(len(MODELS)))
    ax.set_yticklabels([NICE[m] for m in MODELS])
    for i, a in enumerate(MODELS):
        for j, b in enumerate(MODELS):
            if i == j:
                ax.text(j, i, "-", ha="center", va="center", color="#555555")
            else:
                star = "*" if pmat[a][b] < 0.05 else ""
                ax.text(j, i, f"{mat[a][b]:.2f}{star}", ha="center",
                        va="center", fontsize=9.5,
                        color="white" if abs(arr[i, j]) > lim * 0.55 else "#1F2937")
    ax.set_title("Pairwise Diebold-Mariano statistics\n"
                 "negative favours the row model, * significant at 5%",
                 fontsize=12, color=NAVY, pad=14)
    fig.colorbar(im, ax=ax, shrink=0.78, label="DM statistic")
    fig.tight_layout()
    fig.savefig(FIG / "dm_test_matrix.png", dpi=200, facecolor="white")
    plt.close(fig)

    with open(PROC / "statistical_tests.json", "w") as fh:
        json.dump(out, fh, indent=2)
    print("written: data/processed/statistical_tests.json")
    print("figures: rolling_rmse_ratio.png, dm_test_matrix.png")


if __name__ == "__main__":
    main()
