"""
validate_results.py - Independent audit of the pipeline's outputs.

This script deliberately does NOT import anything from the pipeline. It rebuilds
the quantities from the raw files, forecast_log.csv and combo_weights.csv using
its own code, and compares them with metrics.json, statistical_tests.json and
the tables derived from them. Expected values are always recomputed here, never
typed in; checks of numbers quoted in the documents belong to the document
generators.

Exits with status 1 if any check fails.

Run:  python src/validate_results.py
"""
import json
import sys
from math import erf, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
RAW, PROC, FIG = (BASE / "data" / "raw", BASE / "data" / "processed",
                  BASE / "figures")

PASS, FAIL = [], []


def check(label, ok, detail=""):
    (PASS if ok else FAIL).append(label)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label:<52} {detail}")


def close(a, b, tol=5e-5):
    return abs(a - b) < tol


print("=" * 78)
print("INDEPENDENT AUDIT OF THE PIPELINE OUTPUTS")
print("=" * 78)

# ---------------------------------------------------------------------------
# 0. The raw target series, straight from the EconData export
# ---------------------------------------------------------------------------
print("\n0. RAW DATA PROVENANCE")
rows, meta = [], {}
with open(RAW / "econdata_excx135.csv", encoding="utf-8-sig") as fh:
    for line in fh:
        parts = line.rstrip("\n").split(",")
        if len(parts) < 2:
            continue
        k, v = parts[0].strip(), parts[1].strip()
        if k[:4].isdigit() and "-" in k:
            if v:
                rows.append((k, float(v)))
        elif not rows:
            meta[k] = v
ecd = pd.DataFrame(rows, columns=["date", "px"])
ecd["date"] = pd.to_datetime(ecd["date"])
ecd = ecd.sort_values("date").reset_index(drop=True)
check("EconData export parses", len(ecd) > 14000, f"{len(ecd)} daily observations")
check("EconData series code is EXCX135D", meta.get("Source ID") == "EXCX135D",
      meta.get("Source ID", "?"))
check("EconData label is Rand per US Dollar",
      meta.get("Label") == "Rand per US Dollar", meta.get("Label", "?"))

sarb = pd.read_csv(RAW / "usdzar.csv", parse_dates=["date"])
m = ecd.merge(sarb.rename(columns={"value": "api"}), on="date")
d = (m["px"] - m["api"]).abs()
check("EconData == SARB Web API, every overlapping day", d.max() < 1e-9,
      f"{len(m)} obs, max diff {d.max():.10f}")

# ---------------------------------------------------------------------------
# 1. Rebuild the forecast log's spot and realised values from raw data
# ---------------------------------------------------------------------------
print("\n1. FORECAST LOG AGAINST RAW DATA (spot and realised values)")
log = pd.read_csv(PROC / "forecast_log.csv",
                  parse_dates=["origin", "target_date"])

def asof(dates):
    """Last raw observation dated on or before each date. Written from scratch."""
    out = []
    px = ecd.set_index("date")["px"]
    idx = px.index.values
    for dt in pd.to_datetime(dates):
        pos = np.searchsorted(idx, np.datetime64(dt), side="right") - 1
        out.append(px.iloc[pos] if pos >= 0 else np.nan)
    return np.array(out)

spot_chk = asof(log["origin"])
real_chk = asof(log["target_date"])
check("every 'spot' equals the raw fixing at its origin",
      np.abs(spot_chk - log["spot"].values).max() < 1e-9,
      f"max diff {np.abs(spot_chk - log['spot'].values).max():.10f}")
check("every 'realized' equals the raw fixing at its target",
      np.abs(real_chk - log["realized"].values).max() < 1e-9,
      f"max diff {np.abs(real_chk - log['realized'].values).max():.10f}")
check("every origin is a Friday",
      set(log.origin.dt.dayofweek) == {4}, f"n = {len(log)}")
check("every horizon is exactly 28 days",
      set((log.target_date - log.origin).dt.days) == {28}, "28 days")
fridays = pd.date_range("2021-01-01", "2025-12-31", freq="W-FRI")
check("origins are exactly the Fridays of the judged window",
      len(log) == len(fridays) and (log.origin.values == fridays.values).all(),
      f"{log.origin.min().date()} to {log.origin.max().date()}, n = {len(log)}")

# ---------------------------------------------------------------------------
# 2. Recompute every metric from the log, compare to metrics.json
# ---------------------------------------------------------------------------
print("\n2. METRICS RECOMPUTED FROM THE LOG")
MET = json.load(open(PROC / "metrics.json"))
MODELS = ["AR1_log", "AR1_level", "RW", "CARRY", "RIDGE", "GBM", "COMBO"]
mine = {}
for mdl in MODELS:
    e = log[mdl] - log["realized"]
    mine[mdl] = dict(rmse=float(np.sqrt((e ** 2).mean())),
                     mae=float(e.abs().mean()))
    check(f"{mdl} RMSE matches metrics.json",
          close(mine[mdl]["rmse"], MET[mdl]["rmse"], 1e-9),
          f"{mine[mdl]['rmse']:.6f} vs {MET[mdl]['rmse']:.6f}")
for mdl in MODELS:
    check(f"{mdl} MAE matches metrics.json",
          close(mine[mdl]["mae"], MET[mdl]["mae"], 1e-9), "")

# ---------------------------------------------------------------------------
# 3. Relative accuracy, recomputed and compared with metrics.json
# ---------------------------------------------------------------------------
print("\n3. DIEBOLD-MARIANO AND RELATIVE RMSE")
base_name = MET["_baseline_used"]
base = mine[base_name]["rmse"]


def dm(e1, e2, lag=3):
    """Squared-loss DM statistic and two-sided normal p, Bartlett variance."""
    d = np.asarray(e1) ** 2 - np.asarray(e2) ** 2
    n, u = len(d), d - d.mean()
    v = u @ u / n
    for k in range(1, lag + 1):
        v += 2 * (1 - k / (lag + 1)) * (u[k:] @ u[:-k]) / n
    z = d.mean() / np.sqrt(v / n)
    return z, 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))


err = {k: (log[k] - log["realized"]).values for k in MODELS}
for mdl in ["RW", "CARRY", "RIDGE", "GBM", "COMBO"]:
    z, pv = dm(err[mdl], err[base_name])
    check(f"{mdl} vs {base_name}: DM statistic and p match metrics.json",
          close(round(z, 3), MET[mdl]["dm_vs_ar1"][0], 1e-9)
          and close(round(pv, 4), MET[mdl]["dm_vs_ar1"][1], 1e-9),
          f"z = {z:+.3f}, p = {pv:.4f}")
z, pv = dm(err["COMBO"], err["RW"])
check("COMBO vs RW: DM statistic and p match metrics.json",
      close(round(z, 3), MET["COMBO"]["dm_vs_rw"][0], 1e-9)
      and close(round(pv, 4), MET["COMBO"]["dm_vs_rw"][1], 1e-9),
      f"z = {z:+.3f}, p = {pv:.4f}")

TESTS = json.load(open(PROC / "statistical_tests.json"))
worst = 0.0
for a in TESTS["dm_statistic_matrix"]:
    for b in TESTS["dm_statistic_matrix"][a]:
        if a != b:
            z, pv = dm(err[a], err[b])
            worst = max(worst, abs(round(z, 3) - TESTS["dm_statistic_matrix"][a][b]),
                        abs(round(pv, 4) - TESTS["dm_pvalue_matrix"][a][b]))
check("every cell of the DM matrix in statistical_tests.json reproduces",
      worst < 1e-9, f"worst cell difference {worst:.1e}")

PA = TESTS["power_analysis"]
d = err["COMBO"] ** 2 - err[base_name] ** 2
check("mean loss differential in statistical_tests.json",
      close(d.mean(), PA["mean_loss_differential"], 1e-9), f"{d.mean():+.6f}")
gain = 100 * (1 - np.sqrt((err["COMBO"] ** 2).mean() / (err[base_name] ** 2).mean()))
check("COMBO RMSE improvement over the baseline in statistical_tests.json",
      close(round(gain, 3), PA["observed_rmse_improvement_pct"], 1e-9),
      f"{gain:+.4f}%")

# ---------------------------------------------------------------------------
# 4. Cumulative squared-error difference
# ---------------------------------------------------------------------------
print("\n4. CUMULATIVE SQUARED-ERROR DIFFERENCE")
cum_ar1 = ((log[base_name] - log["realized"]) ** 2
           - (log["COMBO"] - log["realized"]) ** 2).cumsum()
cum_rw = ((log["RW"] - log["realized"]) ** 2
          - (log["COMBO"] - log["realized"]) ** 2).cumsum()
check("final value against the baseline equals n x (MSE difference)",
      close(cum_ar1.iloc[-1],
            len(log) * (base ** 2 - mine["COMBO"]["rmse"] ** 2), 1e-8),
      f"{cum_ar1.iloc[-1]:+.4f}")
check("final value against RW equals n x (MSE difference)",
      close(cum_rw.iloc[-1],
            len(log) * (mine["RW"]["rmse"] ** 2 - mine["COMBO"]["rmse"] ** 2), 1e-8),
      f"{cum_rw.iloc[-1]:+.4f}")

# ---------------------------------------------------------------------------
# 5. RMSE by year
# ---------------------------------------------------------------------------
print("\n5. RMSE BY YEAR")
for y in range(log.origin.dt.year.min(), log.origin.dt.year.max() + 1):
    sub = log[log.origin.dt.year == y]
    got = {k: float(np.sqrt(((sub[k] - sub["realized"]) ** 2).mean()))
           for k in MODELS}
    ok = all(close(got[k], MET["_yearly"][str(y)][k], 1e-9) for k in MODELS)
    check(f"{y} yearly RMSE reproduces for every model", ok,
          f"n = {len(sub)}, COMBO {got['COMBO']:.4f}")

# ---------------------------------------------------------------------------
# 6. Cut keeping only forecasts whose target falls inside the window
# ---------------------------------------------------------------------------
print("\n6. TARGETS INSIDE THE WINDOW")
sub = log[log.target_date <= "2025-12-31"]
rob = {k: float(np.sqrt(((sub[k] - sub["realized"]) ** 2).mean()))
       for k in MODELS}
for k in MODELS:
    check(f"{k} RMSE on this cut matches",
          close(rob[k], MET["_targets_within_window"][k], 1e-9), f"{rob[k]:.4f}")

# ---------------------------------------------------------------------------
# 7. Combination weights reconcile with the combination forecast
# ---------------------------------------------------------------------------
print("\n7. FIGURE 5 (combination weights)")
w = pd.read_csv(PROC / "combo_weights.csv", index_col=0, parse_dates=True)
w = w.loc[w.index.isin(log["origin"])]
j = log.set_index("origin").loc[w.index]
recon = (j["RW"] * w["RW"] + j["CARRY"] * w["CARRY"] + j["RIDGE"] * w["RIDGE"])
check("weights x member forecasts reproduce COMBO exactly",
      np.abs(recon - j["COMBO"]).max() < 1e-9,
      f"max diff {np.abs(recon - j['COMBO']).max():.2e}")
check("weights sum to 1 at every origin",
      np.abs(w.sum(axis=1) - 1).max() < 1e-9, "")
check("no negative weights", (w.values >= 0).all(), "")

# ---------------------------------------------------------------------------
# 8. Baseline and carry forecasts rebuilt from weekly.csv
# ---------------------------------------------------------------------------
print("\n8. AR(1) AND CARRY FORECASTS REBUILT FROM THE WEEKLY DATA")
wk = pd.read_csv(PROC / "weekly.csv", parse_dates=["friday"])
px = wk[["friday", "spot"]].dropna()
cd_by_date = wk.set_index("friday")["carry_diff"]


def ar1_four_steps(y):
    X = np.column_stack([np.ones(len(y) - 1), y[:-1]])
    c, phi = np.linalg.lstsq(X, y[1:], rcond=None)[0]
    f = y[-1]
    for _ in range(4):
        f = c + phi * f
    return f


own_log, own_lvl, own_carry = [], [], []
for t, s_t in zip(log["origin"], log["spot"]):
    hist = px[px.friday <= t]["spot"].values
    own_log.append(np.exp(ar1_four_steps(np.log(hist))))
    own_lvl.append(ar1_four_steps(hist))
    cd = cd_by_date.loc[t]
    own_carry.append(s_t * (1 + cd * 28 / 365) if np.isfinite(cd) else s_t)
for name, mine_f in [("AR1_log", own_log), ("AR1_level", own_lvl),
                     ("CARRY", own_carry)]:
    diff = np.abs(np.array(mine_f) - log[name].values).max()
    check(f"{name} forecast rebuilt at every origin", diff < 1e-8,
          f"max diff {diff:.2e}")

# ---------------------------------------------------------------------------
# 9. Figure 4 series panel and Table 3.1 come from real downloaded files
# ---------------------------------------------------------------------------
print("\n9. FIGURE 4 (input series) AND TABLE 3.1 (summary statistics)")
for name, col in [("jibar3m", "jibar3m"), ("ustbill3m", "ustbill3m"),
                  ("gold", "gold"), ("platinum", "platinum"),
                  ("brent", "brent"), ("usd_broad", "usd_broad"),
                  ("vix", "vix")]:
    src = pd.read_csv(RAW / f"{name}.csv", parse_dates=["date"]).sort_values("date")
    idx = src["date"].values
    ok, bad = True, None
    for f_date, plotted in wk[["friday", col]].dropna().tail(200).values:
        pos = np.searchsorted(idx, np.datetime64(pd.Timestamp(f_date)),
                              side="right") - 1
        if pos < 0 or abs(src["value"].iloc[pos] - plotted) > 1e-9:
            ok, bad = False, f_date
            break
    check(f"fig4 panel '{name}' matches the downloaded file", ok,
          f"{len(src)} raw rows" if ok else f"mismatch at {bad}")

stats = pd.read_csv(PROC / "table_summary_stats.csv", index_col=0)
sp_mean = wk["spot"].mean()
check("Table 3.1 spot mean recomputes",
      close(round(sp_mean, 3), stats.loc["spot", "mean"], 1e-3),
      f"{sp_mean:.3f}")
check("Table 3.1 forecast-era observation count equals the log length",
      int(stats.loc["spot", "obs_forecast_era(2021-25)"]) == len(log),
      str(int(stats.loc["spot", "obs_forecast_era(2021-25)"])))

# ---------------------------------------------------------------------------
print("\n" + "=" * 78)
print(f"RESULT: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("\nFAILURES:")
    for f in FAIL:
        print("  -", f)
else:
    print("Every audited number reproduces from the raw data and the forecast log.")
print("=" * 78)
sys.exit(1 if FAIL else 0)
