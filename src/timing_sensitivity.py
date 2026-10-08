"""
timing_sensitivity.py - How much do the results depend on the release lags?

Reruns the whole backtest, validation-era selection included, with every
non-spot predictor delayed by a further 7 days beyond its documented release
rule, and compares judged-era RMSE with the base timing. Spot, and the
features built from spot alone, keep their timing: the SARB rate is public at
10:30 on the day.

If the extra week moved the results a lot, the conclusions would hinge on
release-lag assumptions that are partly judgement (see series_metadata.json).

Output: data/processed/timing_sensitivity.json
"""
import json
from pathlib import Path

import pandas as pd

import build_dataset
from run_backtest import (combo_series, judged_era, members_cached, score,
                          select_config)

PROC = Path(__file__).resolve().parents[1] / "data" / "processed"
MODELS = ["AR1_log", "AR1_level", "RW", "CARRY", "RIDGE", "GBM", "COMBO"]


def judged_rmse(log: pd.DataFrame) -> dict:
    (ridge_tag, delta, theta), _ = select_config(log)[0]
    log = log.assign(COMBO=combo_series(log, ridge_tag, delta, theta)[0])
    log = log.rename(columns={ridge_tag: "RIDGE"})
    res = score(judged_era(log), MODELS)
    return dict(chosen=dict(ridge=ridge_tag, delta=delta, theta=theta),
                rmse={m: res[m]["rmse"] for m in MODELS})


def main() -> None:
    base = pd.read_csv(PROC / "weekly.csv", parse_dates=["friday", "target_date"])
    late = build_dataset.build(extra_lag_days=7)
    out = {"issuance": "Friday 17:00 Africa/Johannesburg",
           "base": judged_rmse(members_cached(base)[0]),
           "extra_week": judged_rmse(members_cached(late, "members_cache_lag7")[0])}
    out["extra_week_minus_base"] = {
        m: out["extra_week"]["rmse"][m] - out["base"]["rmse"][m] for m in MODELS}
    with open(PROC / "timing_sensitivity.json", "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"{'model':10s} {'base':>9s} {'+1 week':>9s} {'change':>9s}")
    for m in MODELS:
        print(f"{m:10s} {out['base']['rmse'][m]:9.5f} "
              f"{out['extra_week']['rmse'][m]:9.5f} "
              f"{out['extra_week_minus_base'][m]:+9.5f}")


if __name__ == "__main__":
    main()
