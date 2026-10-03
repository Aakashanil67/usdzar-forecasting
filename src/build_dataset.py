"""
build_dataset.py - Construct the weekly (Friday) forecasting dataset.

Protocol:
  * Issuance: a forecast is issued every Friday at 17:00 Africa/Johannesburg
    (data/raw/series_metadata.json). That is after the SARB 10:30 rand rate and
    JIBAR, and before any US close of the same day.
  * Information set: an observation enters only if it had been published by
    the issuance time. Each series has a release rule taken from its
    publisher's schedule, recorded with its source in series_metadata.json.
    Market fixings a trader could watch (the SARB rate, the London gold fix,
    NYMEX platinum) are stamped at observation time; published rates and
    indices at publication time. So a Friday forecast sees Wednesday's T-bill
    rate, Thursday's VIX and platinum, the previous Friday's dollar index, and
    Brent up to Monday.
  * Revisions: for DTB3, VIXCLS, DTWEXBGS and DCOILBRENTEU the value used is
    the one ALFRED shows on the issuance date (data/raw/vintages/). A revision
    counts from the later of its ALFRED date and the release rule. Before a
    series' first ALFRED vintage the values from that first vintage are used,
    on the release rule's timing. This is an approximation.
  * Spot at t          : last EXCX135D fixing on or before t (10:30 same day).
  * Target ("1 month") : EXCX135D fixing at t + 28 days (as-of backward for
    holidays). 4 weeks = the Friday-to-Friday definition of one month.
  * y = log(S_{t+28}) - log(S_t)  (4-week-ahead log return, the model target)

Features at t, all from values available at the issuance time t:
  carry_diff  : (JIBAR 3M - US 3M T-bill)/100, annualised decimal
  d_carry_4w  : change in carry_diff since the observation that was latest four
                weeks earlier, both legs as known at t
  ret4_gold / ret4_plat / ret4_brent / ret4_usd : 4-week log returns, both
                legs as known at t, so a revision between them cannot show up
                as a return
  ret4_spot, ret12_spot : own momentum (4w, 12w log returns)
  vix_z       : VIX z-score vs its trailing 156-week window
  d_vix_4w    : 4-week log change in VIX
  ma_gap      : log(spot) - log(200-trading-day moving average of daily spot)

For every input the weekly file also carries <name>_obs_date (the observation
used) and <name>_available_at (when that value became public), next to
issued_at, so the timing can be audited row by row.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

BASE = Path(__file__).resolve().parents[1]
RAW, PROC = BASE / "data" / "raw", BASE / "data" / "processed"
PROC.mkdir(parents=True, exist_ok=True)

META = json.loads((RAW / "series_metadata.json").read_text(encoding="utf-8"))
ISSUE_TZ = META["issuance"]["timezone"]
ISSUE_TIME = pd.Timedelta(META["issuance"]["time"] + ":00")
US_HOLIDAYS = USFederalHolidayCalendar().holidays("1950", "2030").values.astype(
    "datetime64[D]")
PREDICTORS = ["jibar3m", "ustbill3m", "gold", "platinum", "brent",
              "usd_broad", "vix"]
TOL = pd.Timedelta(days=14)            # an observation older than this is missing


def release_day(obs: pd.Series, rule: str) -> pd.Series:
    """Calendar day on which the publisher releases each observation."""
    if rule == "same_day":
        return obs
    days = obs.values.astype("datetime64[D]")
    if rule == "next_us_business_day":
        nxt = np.busday_offset(days, 1, roll="forward", holidays=US_HOLIDAYS)
        return pd.Series(nxt.astype("datetime64[ns]"), index=obs.index)
    if rule == "monday_after_week":
        monday = days + (7 - obs.dt.dayofweek.values).astype("timedelta64[D]")
        nxt = np.busday_offset(monday, 0, roll="forward", holidays=US_HOLIDAYS)
        return pd.Series(nxt.astype("datetime64[ns]"), index=obs.index)
    if rule == "wednesday_after_two_days":
        d = obs + pd.Timedelta(days=2)
        return d + pd.to_timedelta((2 - d.dt.dayofweek) % 7, unit="D")
    raise ValueError(f"unknown release rule {rule!r}")


def stamp(day: pd.Series, hhmm: str, tz: str) -> pd.Series:
    return ((day + pd.Timedelta(hhmm + ":00")).dt.tz_localize(tz)
            .dt.tz_convert("UTC").dt.as_unit("ns"))


def realtime_table(name: str, raw: pd.DataFrame,
                   extra_lag: pd.Timedelta) -> pd.DataFrame:
    """Every value a series has had, with the moment it became public:
    columns obs_date, value, available_at (UTC)."""
    spec = META["series"][name]
    vint = RAW / "vintages" / f"{spec['code']}.csv"
    if vint.exists():
        df = pd.read_csv(vint, parse_dates=["obs_date", "realtime_start"])
    else:
        df = raw.rename(columns={"date": "obs_date"})[["obs_date", "value"]]
    released = stamp(release_day(df["obs_date"], spec["release_rule"]),
                     spec["release_time"], spec["timezone"])
    if vint.exists():
        seen = stamp(df["realtime_start"], spec["release_time"], spec["timezone"])
        # rows from the first vintage cover all earlier history, which ALFRED
        # never saw being published, so only the release rule dates them
        first = df["realtime_start"] == df["realtime_start"].min()
        released = released.where(first, np.maximum(released, seen))
    return (df.assign(available_at=released + extra_lag)
              [["obs_date", "value", "available_at"]]
              .sort_values("available_at", kind="stable").reset_index(drop=True))


def asof_weekly(rt: pd.DataFrame, issued: pd.Series, lookback=pd.Timedelta(0)):
    """For each issuance time T: the newest observation that was public at
    T - lookback, valued as it was known at T. Returns obs_date, value and the
    time that value became public."""
    avail = rt["available_at"].dt.as_unit("ns").values.astype("int64")
    obs = rt["obs_date"].dt.as_unit("ns").values
    newest = np.maximum.accumulate(obs)
    val = rt["value"].values
    hist = {pd.Timestamp(d): (avail[i], val[i])
            for d, i in rt.groupby("obs_date", sort=False).indices.items()}
    T = issued.dt.as_unit("ns").values.astype("int64")
    T_look = (issued - lookback).dt.as_unit("ns").values.astype("int64")
    out_d, out_v, out_a = [], [], []
    days = (issued - lookback).dt.tz_convert(ISSUE_TZ).dt.tz_localize(None).dt.normalize()
    for t, tl, day in zip(T, T_look, days):
        k = np.searchsorted(avail, tl, side="right")
        if k == 0 or day - pd.Timestamp(newest[k - 1]) > TOL:
            out_d.append(pd.NaT); out_v.append(np.nan); out_a.append(np.nan)
            continue
        d = pd.Timestamp(newest[k - 1])
        a, v = hist[d]
        j = np.searchsorted(a, t, side="right") - 1
        out_d.append(d); out_v.append(v[j]); out_a.append(a[j])
    return (pd.Series(pd.to_datetime(out_d)), np.array(out_v, dtype=float),
            pd.Series(pd.to_datetime(out_a, utc=True)))


def load_target() -> pd.DataFrame:
    """USDZAR (EXCX135). Primary source: the official EconData export
    (data/raw/econdata_excx135_clean.csv, produced by verify_provenance.py).
    Fallback: the SARB Web API pull, which verify_provenance.py has confirmed is
    numerically identical over all 9 141 overlapping observations."""
    f = RAW / "econdata_excx135_clean.csv"
    if f.exists():
        df = pd.read_csv(f, parse_dates=["date"])
        print(f"target series: EconData EXCX135 export ({len(df)} obs)")
    else:
        print("target series: SARB Web API EXCX135D (EconData export not present)")
        df = pd.read_csv(RAW / "usdzar.csv", parse_dates=["date"])
    return df.sort_values("date").reset_index(drop=True)


def build(extra_lag_days: int = 0) -> pd.DataFrame:
    """The weekly dataset. extra_lag_days delays every non-spot predictor's
    availability, for the timing sensitivity run."""
    spot_d = load_target()
    extra = pd.Timedelta(days=extra_lag_days)

    # Friday grid: features need history; targets run into Jan 2026
    fridays = pd.Series(pd.date_range("1999-01-08", "2026-02-27", freq="W-FRI"),
                        name="date")
    issued = (fridays + ISSUE_TIME).dt.tz_localize(ISSUE_TZ).dt.tz_convert("UTC")
    local = lambda s: s.dt.tz_convert(ISSUE_TZ).astype(str)

    w = pd.DataFrame({"friday": fridays})
    rt_spot = realtime_table("usdzar", spot_d, pd.Timedelta(0))
    obs, w["spot"], at = asof_weekly(rt_spot, issued)
    w["issued_at"] = local(issued)
    w["spot_obs_date"], w["spot_available_at"] = obs, local(at)

    # ---- target: spot 28 days ahead (as-of backward at the target date) ----
    tgt_dates = fridays + pd.Timedelta(days=28)
    m = pd.merge_asof(pd.DataFrame({"date": tgt_dates}), spot_d, on="date",
                      direction="backward", tolerance=pd.Timedelta(days=14))
    w["target_date"] = tgt_dates.values
    w["realized"] = m["value"].values
    w["y"] = np.log(w["realized"]) - np.log(w["spot"])

    # ---- predictors, each with its value four weeks back as known now ----
    then = {}
    for name in PREDICTORS:
        raw = pd.read_csv(RAW / f"{name}.csv", parse_dates=["date"])
        rt = realtime_table(name, raw, extra)
        obs, w[name], at = asof_weekly(rt, issued)
        w[f"{name}_obs_date"], w[f"{name}_available_at"] = obs, local(at)
        then[name] = asof_weekly(rt, issued, pd.Timedelta(weeks=4))[1]

    w["carry_diff"] = (w["jibar3m"] - w["ustbill3m"]) / 100.0
    w["d_carry_4w"] = w["carry_diff"] - (then["jibar3m"] - then["ustbill3m"]) / 100.0
    for src, out in [("gold", "ret4_gold"), ("platinum", "ret4_plat"),
                     ("brent", "ret4_brent"), ("usd_broad", "ret4_usd")]:
        w[out] = np.log(w[src]) - np.log(then[src])
    w["ret4_spot"] = np.log(w["spot"]) - np.log(w["spot"].shift(4))
    w["ret12_spot"] = np.log(w["spot"]) - np.log(w["spot"].shift(12))
    roll = w["vix"].rolling(156, min_periods=104)
    w["vix_z"] = (w["vix"] - roll.mean()) / roll.std()
    w["d_vix_4w"] = np.log(w["vix"]) - np.log(then["vix"])

    # 200-trading-day MA of the DAILY spot, known at the same time as spot
    ma = spot_d.assign(value=spot_d["value"].rolling(200).mean()).dropna()
    w["ma_gap"] = np.log(w["spot"]) - np.log(
        asof_weekly(realtime_table("usdzar", ma, pd.Timedelta(0)), issued)[1])
    return w


def main() -> None:
    w = build()
    w.to_csv(PROC / "weekly.csv", index=False)

    feats = ["spot", "carry_diff", "ret4_gold", "ret4_plat", "ret4_brent",
             "ret4_usd", "vix_z", "ma_gap", "ret4_spot"]
    print(w.tail(3)[["friday", "spot", "target_date", "realized"]])
    print(f"rows: {len(w)}  complete-feature rows: "
          f"{w.dropna(subset=feats + ['y']).shape[0]}")
    judged = w[(w.friday >= "2021-01-01") & (w.friday <= "2025-12-31")]
    print("median age of the newest usable observation at issuance, 2021-2025:")
    for name in PREDICTORS:
        age = (judged["friday"] - judged[f"{name}_obs_date"]).dt.days
        print(f"  {name:10s} {age.median():.0f} days (max {age.max():.0f})")


if __name__ == "__main__":
    main()
