"""
build_dataset.py - Construct the weekly (Friday) forecasting dataset.

Protocol:
  * Origin grid: every Friday. For each Friday t the information set is all
    observations DATED ON OR BEFORE t (as-of merge, backward). All predictors are
    daily financial-market series: no publication lags, no revisions -> the
    as-of merge is sufficient to guarantee a true pseudo-real-time design.
  * Spot at t          : last EXCX135D fixing on or before t.
  * Target ("1 month") : EXCX135D fixing at t + 28 days (as-of backward for
    holidays). 4 weeks = the Friday-to-Friday definition of one month.
  * y = log(S_{t+28}) - log(S_t)  (4-week-ahead log return, the model target)

Features at t (all computed only from data <= t):
  carry_diff  : (JIBAR 3M - US 3M T-bill)/100, annualised decimal
  d_carry_4w  : 4-week change in carry_diff
  ret4_gold / ret4_plat / ret4_brent / ret4_usd : 4-week log returns
  ret4_spot, ret12_spot : own momentum (4w, 12w log returns)
  vix_z       : VIX z-score vs its trailing 156-week window
  d_vix_4w    : 4-week log change in VIX
  ma_gap      : log(spot) - log(200-trading-day moving average of daily spot)
"""
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
RAW, PROC = BASE / "data" / "raw", BASE / "data" / "processed"
PROC.mkdir(parents=True, exist_ok=True)


def load(name: str) -> pd.DataFrame:
    df = pd.read_csv(RAW / f"{name}.csv", parse_dates=["date"])
    return df.sort_values("date").rename(columns={"value": name})


def asof_weekly(daily: pd.DataFrame, fridays: pd.Series, col: str,
                tol_days: int = 14) -> pd.Series:
    """Last observation on or before each Friday (max staleness tol_days)."""
    m = pd.merge_asof(pd.DataFrame({"date": fridays}), daily,
                      on="date", direction="backward",
                      tolerance=pd.Timedelta(days=tol_days))
    return m[col].values


def load_target() -> pd.DataFrame:
    """USDZAR (EXCX135). Primary source: the official EconData export
    (data/raw/econdata_excx135_clean.csv, produced by verify_provenance.py).
    Fallback: the SARB Web API pull, which verify_provenance.py has confirmed is
    numerically identical over all 9 141 overlapping observations."""
    f = RAW / "econdata_excx135_clean.csv"
    if f.exists():
        df = pd.read_csv(f, parse_dates=["date"]).rename(
            columns={"value": "usdzar"})
        print(f"target series: EconData EXCX135 export ({len(df)} obs)")
        return df.sort_values("date")
    print("target series: SARB Web API EXCX135D (EconData export not present)")
    return load("usdzar")


def main() -> None:
    spot_d = load_target()

    # Friday grid: features need history; targets run into Jan 2026
    fridays = pd.Series(pd.date_range("1999-01-08", "2026-02-27", freq="W-FRI"),
                        name="date")

    w = pd.DataFrame({"friday": fridays})
    w["spot"] = asof_weekly(spot_d, fridays, "usdzar")

    # ---- target: spot 28 days ahead (as-of backward at the target date) ----
    tgt_dates = fridays + pd.Timedelta(days=28)
    m = pd.merge_asof(pd.DataFrame({"date": tgt_dates}), spot_d, on="date",
                      direction="backward", tolerance=pd.Timedelta(days=14))
    w["target_date"] = tgt_dates.values
    w["realized"] = m["usdzar"].values
    w["y"] = np.log(w["realized"]) - np.log(w["spot"])

    # ---- predictors ----
    for name in ["jibar3m", "ustbill3m", "gold", "platinum", "brent",
                 "usd_broad", "vix"]:
        w[name] = asof_weekly(load(name), fridays, name)

    w["carry_diff"] = (w["jibar3m"] - w["ustbill3m"]) / 100.0
    w["d_carry_4w"] = w["carry_diff"] - w["carry_diff"].shift(4)
    for src, out in [("gold", "ret4_gold"), ("platinum", "ret4_plat"),
                     ("brent", "ret4_brent"), ("usd_broad", "ret4_usd")]:
        w[out] = np.log(w[src]) - np.log(w[src].shift(4))
    w["ret4_spot"] = np.log(w["spot"]) - np.log(w["spot"].shift(4))
    w["ret12_spot"] = np.log(w["spot"]) - np.log(w["spot"].shift(12))
    roll = w["vix"].rolling(156, min_periods=104)
    w["vix_z"] = (w["vix"] - roll.mean()) / roll.std()
    w["d_vix_4w"] = np.log(w["vix"]) - np.log(w["vix"].shift(4))

    # 200-trading-day MA of the DAILY spot, evaluated as-of each Friday
    spot_ma = spot_d.copy()
    spot_ma["ma200"] = spot_ma["usdzar"].rolling(200).mean()
    w["ma_gap"] = np.log(w["spot"]) - np.log(
        asof_weekly(spot_ma[["date", "ma200"]], fridays, "ma200"))

    w.to_csv(PROC / "weekly.csv", index=False)

    feats = ["spot", "carry_diff", "ret4_gold", "ret4_plat", "ret4_brent",
             "ret4_usd", "vix_z", "ma_gap", "ret4_spot"]
    print(w.tail(3)[["friday", "spot", "target_date", "realized"]])
    print(f"rows: {len(w)}  complete-feature rows: "
          f"{w.dropna(subset=feats + ['y']).shape[0]}")


if __name__ == "__main__":
    main()
