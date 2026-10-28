"""
statistical_tests.py - Formal comparison of forecast accuracy on the judged era.

Two comparisons were fixed before the judged era was scored: COMBO against the
mandated AR1_log, and COMBO against the random walk. Their p-values are reported
as they come. Every other model, variant and ablation is compared with the same
two benchmarks as exploratory work, and those p-values are Holm-adjusted as one
family, so a single lucky ablation cannot pass for a finding.

Overlapping 4-week forecasts make the loss differential serially correlated.
The DM variance is Newey-West (Bartlett) at lag h-1 = 3 by default; the two
prespecified comparisons are also run at lags 4 and 8 and at the Andrews (1991)
AR(1) plug-in lag, to show how much the answer depends on that choice.

The planning table replaces an earlier power calculation that was run at the
observed effect size. It asks, for RMSE reductions of 1, 2 and 5 per cent
chosen in advance, how many weekly origins a future holdout would need.

Outputs: data/processed/statistical_tests.json, figures/rolling_rmse_ratio.png

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

MODELS = ["AR1_log", "AR1_level", "AR1_log_roll", "AR1_log_vc", "RW",
          "RW_drift", "CARRY", "RIDGE", "GBM", "EQUAL3", "RW_CARRY",
          "RW_RIDGE", "COMBO"]
BENCHMARKS = ["RW", "AR1_log"]
PRESPECIFIED = [("COMBO", "AR1_log"), ("COMBO", "RW")]
H = 4                       # forecast horizon in weeks
LAG = H - 1                 # Newey-West lag for overlapping forecasts
SENSITIVITY_LAGS = [3, 4, 8]
Z95, Z80 = 1.959964, 0.841621
PLANNED_RMSE_CUTS_PCT = [1, 2, 5]

NAVY, GREEN = "#0E2A3B", "#1A7A4A"


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


def andrews_lag(d):
    """Andrews (1991) Bartlett bandwidth from an AR(1) fitted to d, truncated
    to an integer lag."""
    u = d - d.mean()
    rho = (u[1:] @ u[:-1]) / (u[:-1] @ u[:-1])
    alpha = 4 * rho ** 2 / ((1 - rho) ** 2 * (1 + rho) ** 2)
    return int(1.1447 * (alpha * len(d)) ** (1 / 3))


def dm_test(e1, e2, lag=LAG):
    """Diebold-Mariano on squared-error loss. Negative favours model 1."""
    d = e1 ** 2 - e2 ** 2
    var = newey_west_var(d, lag)
    stat = d.mean() / np.sqrt(var)
    return float(stat), float(2 * (1 - normal_cdf(abs(stat)))), d


def holm(pvalues):
    """Holm step-down adjusted p-values, in the order given."""
    p = np.asarray(pvalues, float)
    order = np.argsort(p)
    adj = np.maximum.accumulate((len(p) - np.arange(len(p))) * p[order])
    out = np.empty_like(p)
    out[order] = np.minimum(adj, 1.0)
    return out.tolist()


def dm_at(e_model, e_bench, lag):
    """DM statistic, p-value and 95% CI of the mean loss differential."""
    stat, p, d = dm_test(e_model, e_bench, lag)
    half = Z95 * sqrt(newey_west_var(d, lag))
    return dict(lag=int(lag), dm=stat, p=p,
                ci95=[float(d.mean() - half), float(d.mean() + half)])


def compare(e_model, e_bench, lags):
    """dm_at for each lag, plus the RMSE difference with the lag-3 CI carried
    onto the RMSE scale (benchmark MSE held fixed)."""
    mse_b = float((e_bench ** 2).mean())
    d = e_model ** 2 - e_bench ** 2
    by_lag = {str(lag): dm_at(e_model, e_bench, lag) for lag in lags}
    lo, hi = dm_at(e_model, e_bench, LAG)["ci95"]
    return dict(mean_loss_differential=float(d.mean()),
                rmse_difference=float(sqrt(mse_b + d.mean()) - sqrt(mse_b)),
                rmse_difference_ci95=[float(sqrt(mse_b + lo) - sqrt(mse_b)),
                                      float(sqrt(mse_b + hi) - sqrt(mse_b))],
                by_lag=by_lag)


def planning_table(e_model, e_bench):
    """Origins needed to detect a prespecified RMSE cut against this benchmark,
    two-sided 5% test, 80% power, normal approximation. The long-run sd of the
    loss differential and the benchmark MSE are held at their 2021-2025 values."""
    d = e_model ** 2 - e_bench ** 2
    n = len(d)
    sd = sqrt(newey_west_var(d, LAG) * n)
    mse_b = float((e_bench ** 2).mean())
    rows = []
    for cut in PLANNED_RMSE_CUTS_PCT:
        delta = mse_b * (1 - (1 - cut / 100) ** 2)
        need = ((Z95 + Z80) * sd / delta) ** 2
        rows.append(dict(rmse_reduction_pct=cut, mse_reduction=delta,
                         origins_needed=int(np.ceil(need)),
                         years_of_weekly_origins=round(need / 52, 1),
                         power_at_current_n=normal_cdf(delta * sqrt(n) / sd - Z95)))
    return dict(assumed_sd_loss_differential=sd, assumed_benchmark_mse=mse_b,
                current_n=n, rows=rows)


def main():
    log = pd.read_csv(PROC / "forecast_log.csv",
                      parse_dates=["origin", "target_date"]).set_index("origin")
    err = {m: (log[m] - log["realized"]).values for m in MODELS}
    out = {"note": (
        "model vs benchmark, squared-error loss. mean_loss_differential is "
        "MSE(model) - MSE(benchmark), so negative favours the model. DM uses a "
        "Newey-West variance; p-values are two-sided normal. Holm adjustment "
        "uses the lag-3 p-values of the exploratory family only."),
        "primary_lag": LAG}

    # ------------------------------------------------ comparisons
    comps = []
    for b in BENCHMARKS:
        for m in MODELS:
            if m == b:
                continue
            pre = (m, b) in PRESPECIFIED
            c = dict(model=m, benchmark=b,
                     role="prespecified" if pre else "exploratory",
                     **compare(err[m], err[b],
                               SENSITIVITY_LAGS if pre else [LAG]))
            if pre:
                auto = andrews_lag(err[m] ** 2 - err[b] ** 2)
                c["by_lag"]["auto"] = dm_at(err[m], err[b], auto)
            comps.append(c)

    # RW vs AR1_log and AR1_log vs RW are one hypothesis: count it once.
    family = sorted({frozenset((c["model"], c["benchmark"])) for c in comps
                     if c["role"] == "exploratory"}, key=sorted)
    p_of = {frozenset((c["model"], c["benchmark"])): c["by_lag"][str(LAG)]["p"]
            for c in comps}
    adj = dict(zip(family, holm([p_of[k] for k in family])))
    for c in comps:
        if c["role"] == "exploratory":
            c["p_holm"] = adj[frozenset((c["model"], c["benchmark"]))]
    out["exploratory_family_size"] = len(family)
    out["comparisons"] = comps

    print(f"{'model':<13}{'bench':<9}{'role':<14}{'dRMSE':>9}{'DM':>8}"
          f"{'p':>8}{'p_holm':>8}")
    for c in comps:
        r = c["by_lag"][str(LAG)]
        ph = f"{c['p_holm']:8.3f}" if "p_holm" in c else " " * 8
        print(f"{c['model']:<13}{c['benchmark']:<9}{c['role']:<14}"
              f"{c['rmse_difference']:+9.5f}{r['dm']:+8.2f}{r['p']:8.3f}{ph}")
    for c in comps:
        if c["role"] == "prespecified":
            print(f"\n{c['model']} vs {c['benchmark']}, HAC lag sensitivity")
            for k, r in c["by_lag"].items():
                print(f"  lag {r['lag']:>2} ({k:>4}): DM {r['dm']:+.3f}  "
                      f"p {r['p']:.3f}  CI [{r['ci95'][0]:+.5f}, {r['ci95'][1]:+.5f}]")

    # ------------------------------------------------ planning table
    out["planning"] = {
        "assumptions": [
            "two-sided 5% DM test on squared-error loss, 80% power, normal approximation",
            "the long-run sd of the loss differential stays at its 2021-2025 "
            "value for COMBO against that benchmark (Newey-West, lag 3)",
            "the benchmark's MSE stays at its 2021-2025 value",
            "effect sizes are fixed in advance, not taken from the observed result"],
        "vs": {b: planning_table(err["COMBO"], err[b]) for b in BENCHMARKS}}
    print("\nPlanning table: origins needed for 80% power")
    for b, tab in out["planning"]["vs"].items():
        print("  vs " + b + ": " + ", ".join(
            f"{r['rmse_reduction_pct']}% -> {r['origins_needed']}"
            for r in tab["rows"]))

    # ------------------------------------------------ rolling accuracy
    win = 52
    roll = {m: np.sqrt(pd.Series(err[m] ** 2, index=log.index).rolling(win).mean())
            for m in ["COMBO", "AR1_log"]}
    # Drop the first win-1 entries: they are NaN while the window fills, and
    # counting them as "not ahead" understates the share.
    ratio = (roll["COMBO"] / roll["AR1_log"]).dropna()
    out["rolling"] = {
        "window_weeks": win,
        "n_complete_windows": int(len(ratio)),
        "share_of_windows_ahead_of_benchmark": round(float((ratio < 1).mean()), 3),
        "best_window_ratio": round(float(ratio.min()), 4),
        "worst_window_ratio": round(float(ratio.max()), 4)}

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

    with open(PROC / "statistical_tests.json", "w") as fh:
        json.dump(out, fh, indent=2)
    print("\nwritten: data/processed/statistical_tests.json")


if __name__ == "__main__":
    main()
