"""
diagnostics.py - What the judged-era forecasts look like, beyond one RMSE.

  accuracy             RMSE, MAE, MSE = bias^2 + error variance, directional
                       accuracy next to the share of up calls (a model that
                       always calls "up" scores the base rate of up moves)
  deviation_from_spot  how far each forecast sits from the spot rate at issue
  error_correlation    correlation of forecast errors between the base models;
                       members whose errors move together leave a combination
                       little to work with
  weights              min, max and mean of COMBO's weights, overall and by year
  ar1_implied_mean     the AR(1) refitted at every origin: persistence, the
                       level exp(c / (1 - phi)) it is pulled toward, and how
                       that level compares with the spot rate
  cumulative_se        running sum of squared-error differences, AR(1) minus
                       COMBO, by year and at its peak
  worked_example       every model's forecast, error and COMBO weight at one
                       origin, with that day's AR(1) fit

Output: data/processed/diagnostics.json

Run:  python src/diagnostics.py
"""
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

PROC = Path(__file__).resolve().parents[1] / "data" / "processed"
WORKED_ORIGIN = "2022-06-03"

MODELS = ["AR1_log", "AR1_level", "AR1_log_roll", "AR1_log_vc", "RW",
          "RW_drift", "CARRY", "RIDGE", "GBM", "EQUAL3", "RW_CARRY",
          "RW_RIDGE", "COMBO"]
BASE_MODELS = ["AR1_log", "RW", "CARRY", "RIDGE", "GBM"]
COMPONENTS = ["RW", "CARRY", "RIDGE"]


def weight_stats(w: pd.DataFrame) -> dict:
    return {m: dict(min=float(w[m].min()), max=float(w[m].max()),
                    mean=float(w[m].mean())) for m in w.columns}


def ar1_fit(spot: np.ndarray) -> tuple[float, float]:
    """OLS AR(1) with intercept on the log level: c and phi."""
    y = np.log(spot)
    X = np.column_stack([np.ones(len(y) - 1), y[:-1]])
    c, phi = np.linalg.lstsq(X, y[1:], rcond=None)[0]
    return float(c), float(phi)


def ar1_implied_mean(log: pd.DataFrame, weekly: pd.DataFrame) -> dict:
    """Refit the AR(1) on spot up to each origin and compare exp(c/(1-phi))
    with that origin's spot. Same expanding window as run_backtest."""
    fits = []
    for t in log.index:
        c, phi = ar1_fit(weekly.loc[weekly["friday"] <= t, "spot"].dropna().values)
        fits.append((c, phi, float(np.exp(c / (1 - phi)))))
    phi = np.array([f[1] for f in fits])
    mu = np.array([f[2] for f in fits])
    gap = log["spot"].values - mu
    return dict(n_origins=len(log), phi_min=float(phi.min()), phi_max=float(phi.max()),
                mu_min=float(mu.min()), mu_max=float(mu.max()),
                n_below_spot=int((mu < log["spot"].values).sum()),
                mean_gap=float(gap.mean()), min_gap=float(gap.min()),
                spot_first=float(log["spot"].iloc[0]),
                spot_peak=float(log["spot"].max()))


def cumulative_se(log: pd.DataFrame) -> dict:
    cum = ((log["AR1_log"] - log["realized"]) ** 2
           - (log["COMBO"] - log["realized"]) ** 2).cumsum()
    return dict(final=float(cum.iloc[-1]), peak=float(cum.max()),
                peak_origin=str(cum.idxmax().date()),
                end_of_year={str(y): float(g.iloc[-1])
                             for y, g in cum.groupby(cum.index.year)})


def worked_example(log: pd.DataFrame, weekly: pd.DataFrame, weights: pd.DataFrame
                   ) -> dict:
    t = pd.Timestamp(WORKED_ORIGIN)
    r = log.loc[t]
    names = ["RW", "CARRY", "AR1_log", "RIDGE", "GBM", "COMBO"]
    spot_hist = weekly.loc[weekly["friday"] <= t, "spot"].dropna().values
    c, phi = ar1_fit(spot_hist)
    return dict(origin=WORKED_ORIGIN, target_date=str(r["target_date"].date()),
                spot=float(r["spot"]), realized=float(r["realized"]),
                carry_diff=float(weekly.loc[weekly["friday"] == t, "carry_diff"].iloc[0]),
                forecast={m: float(r[m]) for m in names},
                error={m: float(r[m] - r["realized"]) for m in names},
                weights={m: float(weights.loc[t, m]) for m in ["RW", "CARRY", "RIDGE"]},
                ar1=dict(c=c, phi=phi, mu=float(np.exp(c / (1 - phi))),
                         n_obs=len(spot_hist),
                         half_life_weeks=float(np.log(0.5) / np.log(phi))))


def main() -> None:
    log = pd.read_csv(PROC / "forecast_log.csv",
                      parse_dates=["origin", "target_date"]).set_index("origin")
    up_moves = log["realized"] > log["spot"]
    out = {"n": len(log), "realized_up_share": float(up_moves.mean())}

    acc, dev = {}, {}
    for m in MODELS:
        e = log[m] - log["realized"]
        bias, var = float(e.mean()), float(e.var(ddof=0))
        calls_up = log[m] > log["spot"]
        acc[m] = dict(rmse=float(np.sqrt((e ** 2).mean())), mae=float(e.abs().mean()),
                      bias=bias, bias_sq=bias ** 2, error_variance=var,
                      bias_sq_share_of_mse=bias ** 2 / (bias ** 2 + var),
                      dir_acc=float((np.sign(log[m] - log["spot"])
                                     == np.sign(log["realized"] - log["spot"])).mean()),
                      up_share=float(calls_up.mean()))
        gap = 100 * (log[m] / log["spot"] - 1)
        dev[m] = dict(mean_pct=float(gap.mean()), mean_abs_pct=float(gap.abs().mean()),
                      sd_pct=float(gap.std(ddof=0)), up_share=float(calls_up.mean()))
    out["accuracy"], out["deviation_from_spot"] = acc, dev

    corr = log[BASE_MODELS].sub(log["realized"], axis=0).corr()
    out["error_correlation"] = {a: {b: float(corr.loc[a, b]) for b in BASE_MODELS}
                                for a in BASE_MODELS}
    a, b = max(itertools.combinations(COMPONENTS, 2), key=lambda p: corr.loc[p])
    out["max_component_error_correlation"] = dict(pair=[a, b],
                                                  value=float(corr.loc[a, b]))

    w = pd.read_csv(PROC / "combo_weights.csv", index_col=0, parse_dates=True)
    w = w.loc[log.index]
    out["weights"] = dict(overall=weight_stats(w), by_year={
        str(y): weight_stats(g) for y, g in w.groupby(w.index.year)})

    weekly = pd.read_csv(PROC / "weekly.csv", parse_dates=["friday"])
    out["ar1_implied_mean"] = ar1_implied_mean(log, weekly)
    out["cumulative_se"] = cumulative_se(log)
    out["worked_example"] = worked_example(log, weekly, w)

    with open(PROC / "diagnostics.json", "w") as fh:
        json.dump(out, fh, indent=2)

    print(f"{'model':<13}{'RMSE':>8}{'MAE':>8}{'bias^2%':>8}{'dir':>7}{'up':>7}")
    for m in MODELS:
        r = acc[m]
        print(f"{m:<13}{r['rmse']:8.4f}{r['mae']:8.4f}"
              f"{100 * r['bias_sq_share_of_mse']:8.1f}{r['dir_acc']:7.3f}{r['up_share']:7.3f}")
    print(f"realized up share {out['realized_up_share']:.3f}; max component error "
          f"correlation {a}/{b} {corr.loc[a, b]:.4f}")
    for m, s in out["weights"]["overall"].items():
        print(f"weight {m:<6} min {s['min']:.3f} max {s['max']:.3f} mean {s['mean']:.3f}")


if __name__ == "__main__":
    main()
