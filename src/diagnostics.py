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

Output: data/processed/diagnostics.json

Run:  python src/diagnostics.py
"""
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

PROC = Path(__file__).resolve().parents[1] / "data" / "processed"

MODELS = ["AR1_log", "AR1_level", "AR1_log_roll", "AR1_log_vc", "RW",
          "RW_drift", "CARRY", "RIDGE", "GBM", "EQUAL3", "RW_CARRY",
          "RW_RIDGE", "COMBO"]
BASE_MODELS = ["AR1_log", "RW", "CARRY", "RIDGE", "GBM"]
COMPONENTS = ["RW", "CARRY", "RIDGE"]


def weight_stats(w: pd.DataFrame) -> dict:
    return {m: dict(min=float(w[m].min()), max=float(w[m].max()),
                    mean=float(w[m].mean())) for m in w.columns}


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
