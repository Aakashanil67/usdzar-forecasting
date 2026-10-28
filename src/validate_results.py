"""
validate_results.py - Independent audit of the pipeline's outputs.

This script deliberately does NOT import anything from the pipeline. It rebuilds
the quantities from the raw files, forecast_log.csv and combo_weights.csv using
its own code, and compares them with metrics.json, statistical_tests.json,
diagnostics.json and the tables derived from them. Expected values are always
recomputed here, never typed in; checks of numbers quoted in the documents
belong to the document generators.

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
MODELS = ["AR1_log", "AR1_level", "AR1_log_roll", "AR1_log_vc", "RW",
          "RW_drift", "CARRY", "RIDGE", "GBM", "COMBO", "EQUAL3", "RW_CARRY",
          "RW_RIDGE"]
mine = {}
for mdl in MODELS:
    e = log[mdl] - log["realized"]
    move, call = log["realized"] - log["spot"], log[mdl] - log["spot"]
    mine[mdl] = dict(rmse=float(np.sqrt((e ** 2).mean())),
                     mae=float(e.abs().mean()),
                     dir_acc=float((np.sign(call) == np.sign(move)).mean()),
                     up_share=float((call > 0).mean()))
    check(f"{mdl} RMSE matches metrics.json",
          close(mine[mdl]["rmse"], MET[mdl]["rmse"], 1e-9),
          f"{mine[mdl]['rmse']:.6f} vs {MET[mdl]['rmse']:.6f}")
for mdl in MODELS:
    check(f"{mdl} MAE, direction and up share match metrics.json",
          all(close(mine[mdl][k], MET[mdl][k], 1e-9)
              for k in ["mae", "dir_acc", "up_share"]),
          f"dir {mine[mdl]['dir_acc']:.3f}, up {mine[mdl]['up_share']:.3f}")

# ---------------------------------------------------------------------------
# 3. Relative accuracy, recomputed and compared with metrics.json
# ---------------------------------------------------------------------------
print("\n3. DIEBOLD-MARIANO AND RELATIVE RMSE")
base_name = MET["_baseline_used"]
base = mine[base_name]["rmse"]


def nw_var_of_mean(d, lag):
    """Bartlett long-run variance of d, divided by n."""
    n, u = len(d), d - d.mean()
    v = u @ u / n
    for k in range(1, lag + 1):
        v += 2 * (1 - k / (lag + 1)) * (u[k:] @ u[:-k]) / n
    return v / n


def dm(e1, e2, lag=3):
    """Squared-loss DM statistic and two-sided normal p."""
    d = np.asarray(e1) ** 2 - np.asarray(e2) ** 2
    z = d.mean() / np.sqrt(nw_var_of_mean(d, lag))
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
eq = (log["RW"] + log["CARRY"] + log["RIDGE"]) / 3
check("EQUAL3 is the plain mean of RW, CARRY and RIDGE",
      np.abs(eq - log["EQUAL3"]).max() < 1e-9, "")
for abl, other in [("RW_CARRY", "CARRY"), ("RW_RIDGE", "RIDGE")]:
    lo = np.minimum(log["RW"], log[other]) - 1e-9
    hi = np.maximum(log["RW"], log[other]) + 1e-9
    check(f"{abl} lies between RW and {other} at every origin",
          ((log[abl] >= lo) & (log[abl] <= hi)).all(), "")

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


def ar1_mean_corrected(level):
    """exp(4-step log AR(1) forecast + half its forecast variance), with the
    variance from the fit's own residuals."""
    y = np.log(level)
    X = np.column_stack([np.ones(len(y) - 1), y[:-1]])
    c, phi = np.linalg.lstsq(X, y[1:], rcond=None)[0]
    s2 = ((y[1:] - c - phi * y[:-1]) ** 2).sum() / (len(y) - 3)
    return np.exp(ar1_four_steps(y) + s2 * (1 + phi**2 + phi**4 + phi**6) / 2)


own = {k: [] for k in ["AR1_log", "AR1_level", "CARRY", "AR1_log_roll",
                       "AR1_log_vc", "RW_drift"]}
for t, s_t in zip(log["origin"], log["spot"]):
    hist = px[px.friday <= t]["spot"].values
    own["AR1_log"].append(np.exp(ar1_four_steps(np.log(hist))))
    own["AR1_level"].append(ar1_four_steps(hist))
    cd = cd_by_date.loc[t]
    own["CARRY"].append(s_t * (1 + cd * 28 / 365) if np.isfinite(cd) else s_t)
    own["AR1_log_roll"].append(np.exp(ar1_four_steps(np.log(hist[-260:]))))
    own["AR1_log_vc"].append(ar1_mean_corrected(hist))
    weekly_change = (np.log(hist[-1]) - np.log(hist[0])) / (len(hist) - 1)
    own["RW_drift"].append(hist[-1] * np.exp(4 * weekly_change))
for name, mine_f in own.items():
    diff = np.abs(np.array(mine_f) - log[name].values).max()
    check(f"{name} forecast rebuilt at every origin", diff < 1e-8,
          f"max diff {diff:.2e}")

# ---------------------------------------------------------------------------
# 9. Figure 4 series panel and Table 3.1 come from real downloaded files
# ---------------------------------------------------------------------------
print("\n9. FIGURE 4 (input series) AND TABLE 3.1 (summary statistics)")
issued = pd.to_datetime(wk["issued_at"], utc=True)
series_meta = json.load(open(RAW / "series_metadata.json"))["series"]
for name in ["spot", "jibar3m", "ustbill3m", "gold", "platinum", "brent",
             "usd_broad", "vix"]:
    used = wk[[name, f"{name}_obs_date", f"{name}_available_at"]].notna().all(axis=1)
    late = (pd.to_datetime(wk.loc[used, f"{name}_available_at"], utc=True)
            > issued[used]).sum()
    check(f"'{name}' was public by every issuance time", late == 0,
          f"{used.sum()} Fridays, {late} late")

    # The value must be what the source file showed for that observation on
    # the day before the Friday. A revision dated on the Friday itself came out
    # at a US release time, after the 17:00 Johannesburg issuance.
    code = series_meta["usdzar" if name == "spot" else name]["code"]
    vint = RAW / "vintages" / f"{code}.csv"
    if vint.exists():
        src = pd.read_csv(vint, parse_dates=["obs_date", "realtime_start"])
        first = src["realtime_start"].min()
        by_obs = {d: g for d, g in src.groupby("obs_date")}
    else:
        src = pd.read_csv(RAW / ("usdzar.csv" if name == "spot" else f"{name}.csv"),
                          parse_dates=["date"])
        by_date = src.set_index("date")["value"]
    bad = None
    for f_date, d, plotted in wk.loc[used, ["friday", f"{name}_obs_date",
                                            name]].values:
        f_date, d = pd.Timestamp(f_date), pd.Timestamp(d)
        if vint.exists():
            g = by_obs[d]
            known = g[g["realtime_start"] < f_date]
            if known.empty:
                known = g[g["realtime_start"] == first]
            expect = known["value"].iloc[-1]
        else:
            expect = by_date.loc[d]
        if d > f_date or abs(expect - plotted) > 1e-9:
            bad = f_date
            break
    check(f"fig4 panel '{name}' matches the source file", bad is None,
          f"{'ALFRED vintages' if vint.exists() else 'raw file'}"
          if bad is None else f"mismatch at {bad.date()}")

stats = pd.read_csv(PROC / "table_summary_stats.csv", index_col=0)
sp_mean = wk["spot"].mean()
check("Table 3.1 spot mean recomputes",
      close(round(sp_mean, 3), stats.loc["spot", "mean"], 1e-3),
      f"{sp_mean:.3f}")
check("Table 3.1 forecast-era observation count equals the log length",
      int(stats.loc["spot", "obs_forecast_era(2021-25)"]) == len(log),
      str(int(stats.loc["spot", "obs_forecast_era(2021-25)"])))

# ---------------------------------------------------------------------------
# 10. Comparisons, Holm adjustment and the planning table
# ---------------------------------------------------------------------------
print("\n10. COMPARISONS AGAINST RW AND AR(1)")
TESTS = json.load(open(PROC / "statistical_tests.json"))


def andrews(d):
    u = d - d.mean()
    r = (u[1:] @ u[:-1]) / (u[:-1] @ u[:-1])
    return int(1.1447 * (4 * r * r / ((1 - r) ** 2 * (1 + r) ** 2) * len(d)) ** (1 / 3))


comps = TESTS["comparisons"]
pre = {(c["model"], c["benchmark"]) for c in comps if c["role"] == "prespecified"}
check("exactly COMBO vs AR1_log and COMBO vs RW are prespecified",
      pre == {("COMBO", "AR1_log"), ("COMBO", "RW")}, str(sorted(pre)))
check("every model is compared with both benchmarks",
      {(c["model"], c["benchmark"]) for c in comps}
      == {(m, b) for m in MODELS for b in ["RW", "AR1_log"] if m != b},
      f"{len(comps)} comparisons")
worst = 0.0
for c in comps:
    e1, e2 = err[c["model"]], err[c["benchmark"]]
    d = e1 ** 2 - e2 ** 2
    for key, r in c["by_lag"].items():
        lag = andrews(d) if key == "auto" else int(key)
        z, pv = dm(e1, e2, lag)
        half = 1.959964 * np.sqrt(nw_var_of_mean(d, lag))
        worst = max(worst, abs(lag - r["lag"]), abs(z - r["dm"]), abs(pv - r["p"]),
                    abs(d.mean() - half - r["ci95"][0]),
                    abs(d.mean() + half - r["ci95"][1]))
    mse_b = (e2 ** 2).mean()
    lo, hi = c["by_lag"]["3"]["ci95"]
    worst = max(worst, abs(d.mean() - c["mean_loss_differential"]),
                abs(np.sqrt((e1 ** 2).mean()) - np.sqrt(mse_b) - c["rmse_difference"]),
                abs(np.sqrt(mse_b + lo) - np.sqrt(mse_b) - c["rmse_difference_ci95"][0]),
                abs(np.sqrt(mse_b + hi) - np.sqrt(mse_b) - c["rmse_difference_ci95"][1]))
check("DM statistic, p, CI and lag of every comparison reproduce",
      worst < 1e-9, f"worst difference {worst:.1e}")
for c in comps:
    if c["role"] == "prespecified":
        r = c["by_lag"]["3"]
        check(f"{c['model']} vs {c['benchmark']} run at lags 3, 4, 8 and auto",
              set(c["by_lag"]) == {"3", "4", "8", "auto"},
              f"DM {r['dm']:+.3f}, p {r['p']:.3f}, auto lag {c['by_lag']['auto']['lag']}")

# Holm, written out as the step-down procedure over unordered pairs, so that
# RW vs AR1_log and AR1_log vs RW count once.
fam = {frozenset((c["model"], c["benchmark"])): c["by_lag"]["3"]["p"]
       for c in comps if c["role"] == "exploratory"}
running, holm_p = 0.0, {}
for i, k in enumerate(sorted(fam, key=fam.get)):
    running = max(running, min(1.0, (len(fam) - i) * fam[k]))
    holm_p[k] = running
check("exploratory family size", TESTS["exploratory_family_size"] == len(fam),
      f"{len(fam)} hypotheses")
check("every exploratory p_holm reproduces",
      all(close(holm_p[frozenset((c["model"], c["benchmark"]))], c["p_holm"], 1e-12)
          for c in comps if c["role"] == "exploratory"),
      f"smallest {min(holm_p.values()):.3f}")
check("prespecified comparisons carry no Holm adjustment",
      all("p_holm" not in c for c in comps if c["role"] == "prespecified"), "")

for b, tab in TESTS["planning"]["vs"].items():
    d = err["COMBO"] ** 2 - err[b] ** 2
    sd = np.sqrt(nw_var_of_mean(d, 3) * len(d))
    mse_b = (err[b] ** 2).mean()
    ok = close(sd, tab["assumed_sd_loss_differential"], 1e-9)
    for r in tab["rows"]:
        delta = mse_b * (1 - (1 - r["rmse_reduction_pct"] / 100) ** 2)
        ok &= int(np.ceil(((1.959964 + 0.841621) * sd / delta) ** 2)) == r["origins_needed"]
    check(f"planning table vs {b} reproduces",
          ok and [r["rmse_reduction_pct"] for r in tab["rows"]] == [1, 2, 5],
          ", ".join(f"{r['rmse_reduction_pct']}%: {r['origins_needed']}"
                    for r in tab["rows"]))

# ---------------------------------------------------------------------------
# 11. Diagnostics
# ---------------------------------------------------------------------------
print("\n11. DIAGNOSTICS")
DIA = json.load(open(PROC / "diagnostics.json"))
worst = 0.0
for mdl in MODELS:
    e = err[mdl]
    a, gap = DIA["accuracy"][mdl], 100 * (log[mdl] / log["spot"] - 1)
    worst = max(worst, abs(mine[mdl]["rmse"] - a["rmse"]), abs(mine[mdl]["mae"] - a["mae"]),
                abs(e.mean() ** 2 - a["bias_sq"]), abs(e.var() - a["error_variance"]),
                abs(a["bias_sq"] + a["error_variance"] - a["rmse"] ** 2),
                abs(mine[mdl]["dir_acc"] - a["dir_acc"]),
                abs(mine[mdl]["up_share"] - a["up_share"]),
                abs(gap.mean() - DIA["deviation_from_spot"][mdl]["mean_pct"]),
                abs(gap.abs().mean() - DIA["deviation_from_spot"][mdl]["mean_abs_pct"]))
check("accuracy, bias^2 + variance and deviation from spot reproduce",
      worst < 1e-9, f"worst difference {worst:.1e}")
names = list(DIA["error_correlation"])
worst = max(abs(np.corrcoef(err[a], err[b])[0, 1] - DIA["error_correlation"][a][b])
            for a in names for b in names)
top = max([("RW", "CARRY"), ("RW", "RIDGE"), ("CARRY", "RIDGE")],
          key=lambda pair: np.corrcoef(err[pair[0]], err[pair[1]])[0, 1])
check("error correlations and the largest component pair reproduce",
      worst < 1e-9 and DIA["max_component_error_correlation"]["pair"] == list(top),
      f"{top[0]}/{top[1]} {DIA['max_component_error_correlation']['value']:.4f}")
worst = 0.0
groups = [("overall", w)] + [(str(y), w[w.index.year == y])
                             for y in sorted(set(w.index.year))]
for label, g in groups:
    got = DIA["weights"]["overall" if label == "overall" else "by_year"]
    got = got if label == "overall" else got[label]
    for mbr in ["RW", "CARRY", "RIDGE"]:
        worst = max(worst, abs(g[mbr].min() - got[mbr]["min"]),
                    abs(g[mbr].max() - got[mbr]["max"]),
                    abs(g[mbr].mean() - got[mbr]["mean"]))
check("weight min, max and mean, overall and by year, reproduce",
      worst < 1e-12, f"{len(groups) - 1} years")

# ---------------------------------------------------------------------------
# 12. The numbers the documents quote about the AR(1)'s implied mean, the
#     cumulative error difference and the worked example
# ---------------------------------------------------------------------------
print("\n12. AR(1) IMPLIED MEAN, CUMULATIVE ERROR, WORKED EXAMPLE")
mech = DIA["ar1_implied_mean"]
phis, mus = [], []
for t in log["origin"]:
    y = np.log(px[px.friday <= t]["spot"].values)
    c_t, phi_t = np.linalg.lstsq(np.column_stack([np.ones(len(y) - 1), y[:-1]]),
                                 y[1:], rcond=None)[0]
    phis.append(phi_t)
    mus.append(np.exp(c_t / (1 - phi_t)))
phis, mus = np.array(phis), np.array(mus)
gaps = log["spot"].values - mus
check("AR(1) persistence range and implied-mean range reproduce",
      close(phis.min(), mech["phi_min"], 1e-12) and close(phis.max(), mech["phi_max"], 1e-12)
      and close(mus.min(), mech["mu_min"], 1e-9) and close(mus.max(), mech["mu_max"], 1e-9),
      f"phi {phis.min():.4f} to {phis.max():.4f}, mu R{mus.min():.2f} to R{mus.max():.2f}")
check("implied mean below spot: count, mean gap and smallest gap reproduce",
      mech["n_below_spot"] == int((mus < log["spot"].values).sum())
      and close(gaps.mean(), mech["mean_gap"], 1e-9)
      and close(gaps.min(), mech["min_gap"], 1e-9),
      f"{mech['n_below_spot']} of {len(log)}, mean gap R{gaps.mean():.2f}")
check("first and highest spot at an origin reproduce",
      close(log["spot"].iloc[0], mech["spot_first"], 1e-12)
      and close(log["spot"].max(), mech["spot_peak"], 1e-12),
      f"R{mech['spot_first']:.2f} to R{mech['spot_peak']:.2f}")

cum = np.cumsum(err["AR1_log"] ** 2 - err["COMBO"] ** 2)
cum_s = pd.Series(cum, index=log["origin"])
cs = DIA["cumulative_se"]
check("cumulative squared-error difference: final, peak, peak date, year ends",
      close(cum[-1], cs["final"], 1e-9) and close(cum.max(), cs["peak"], 1e-9)
      and str(cum_s.idxmax().date()) == cs["peak_origin"]
      and all(close(g.iloc[-1], cs["end_of_year"][str(y)], 1e-9)
              for y, g in cum_s.groupby(cum_s.index.year)),
      f"peak {cs['peak']:.3f} on {cs['peak_origin']}, final {cs['final']:.3f}")

ex = DIA["worked_example"]
row = log[log["origin"] == pd.Timestamp(ex["origin"])].iloc[0]
wr = w.loc[pd.Timestamp(ex["origin"])]
y = np.log(px[px.friday <= pd.Timestamp(ex["origin"])]["spot"].values)
c_x, phi_x = np.linalg.lstsq(np.column_stack([np.ones(len(y) - 1), y[:-1]]),
                             y[1:], rcond=None)[0]
check("worked example: forecasts, errors, weights and AR(1) fit reproduce",
      all(close(row[m], ex["forecast"][m], 1e-9)
          and close(row[m] - row["realized"], ex["error"][m], 1e-9)
          for m in ex["forecast"])
      and all(close(wr[m], ex["weights"][m], 1e-12) for m in ex["weights"])
      and close(c_x, ex["ar1"]["c"], 1e-12) and close(phi_x, ex["ar1"]["phi"], 1e-12)
      and ex["ar1"]["n_obs"] == len(y)
      and close(sum(wr[m] * row[m] for m in ex["weights"]), row["COMBO"], 1e-9),
      f"{ex['origin']}, weights sum to COMBO {row['COMBO']:.4f}")

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
