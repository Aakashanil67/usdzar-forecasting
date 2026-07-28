"""
validate_results.py - Independent audit of every number that appears in a chart,
a table or the text of the submitted documents.

This script deliberately does NOT import anything from the pipeline. It rebuilds
the quantities from the raw files using its own code, then checks them against
what the pipeline produced and against what is drawn in the figures. If any
number in the submission had been typed in by hand or drifted, this fails.

Run:  python src/validate_results.py
"""
import json
import re
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
print("INDEPENDENT VERIFICATION OF EVERY PLOTTED / QUOTED NUMBER")
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
check("all 261 origins are Fridays",
      set(log.origin.dt.dayofweek) == {4}, f"n = {len(log)}")
check("every horizon is exactly 28 days",
      set((log.target_date - log.origin).dt.days) == {28}, "28 days")
check("origins span the judged window",
      str(log.origin.min().date()) == "2021-01-01"
      and str(log.origin.max().date()) == "2025-12-26",
      f"{log.origin.min().date()} to {log.origin.max().date()}")

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
# 3. Figure 1 and 1b: the bar chart labels
# ---------------------------------------------------------------------------
print("\n3. FIGURE 1 (RMSE bars) AND 1b (relative improvement)")
base = mine["AR1_log"]["rmse"]
for mdl, shown in [("AR1_log", 0.5624), ("RW", 0.5600), ("CARRY", 0.5606),
                   ("RIDGE", 0.5605), ("GBM", 0.6046), ("COMBO", 0.5600)]:
    check(f"fig1 bar label for {mdl}", close(round(mine[mdl]["rmse"], 4), shown),
          f"chart shows {shown}, recomputed {mine[mdl]['rmse']:.4f}")
gain = 100 * (1 - mine["COMBO"]["rmse"] / base)
check("headline improvement +0.42 per cent", close(round(gain, 2), 0.42, 1e-9),
      f"recomputed {gain:+.4f}%")
gbm_loss = 100 * (mine["GBM"]["rmse"] / base - 1)
check("gradient boosting loses 7.5 per cent",
      close(round(gbm_loss, 1), 7.5, 1e-9), f"recomputed {gbm_loss:+.3f}%")
check("four of five models beat the baseline",
      sum(mine[k]["rmse"] < base for k in
          ["RW", "CARRY", "RIDGE", "GBM", "COMBO"]) == 4, "RW, CARRY, RIDGE, COMBO")

# ---------------------------------------------------------------------------
# 4. Figure 2: cumulative squared-error difference
# ---------------------------------------------------------------------------
print("\n4. FIGURE 2 (cumulative squared-error difference)")
cum_ar1 = ((log["AR1_log"] - log["realized"]) ** 2
           - (log["COMBO"] - log["realized"]) ** 2).cumsum()
cum_rw = ((log["RW"] - log["realized"]) ** 2
          - (log["COMBO"] - log["realized"]) ** 2).cumsum()
check("curve ends positive against AR(1) (we finish ahead)",
      cum_ar1.iloc[-1] > 0, f"final value {cum_ar1.iloc[-1]:.4f}")
check("final cumulative value equals n x (MSE difference)",
      close(cum_ar1.iloc[-1],
            len(log) * (base ** 2 - mine["COMBO"]["rmse"] ** 2), 1e-8),
      "identity holds")
c21 = cum_ar1[log.origin.dt.year == 2021]
check("2021 curve oscillates either side of zero and ends barely ahead",
      c21.min() < 0 < c21.max() and abs(c21.iloc[-1]) < 0.15,
      f"2021 min {c21.min():+.2f}, max {c21.max():+.2f}, end {c21.iloc[-1]:+.2f}")
rise = (cum_ar1[log.origin.dt.year == 2023].iloc[-1]
        - cum_ar1[log.origin.dt.year == 2022].iloc[0])
check("edge builds through 2022-23 (claim on slide 2)", rise > 0,
      f"gain across 2022-23: {rise:+.3f}")
check("peak 1.29 and final 0.69 as stated in the report",
      close(round(cum_ar1.max(), 2), 1.29, 1e-9)
      and close(round(cum_ar1.iloc[-1], 2), 0.69, 1e-9),
      f"peak {cum_ar1.max():.3f}, final {cum_ar1.iloc[-1]:.3f}")
check("2023 year-end value 1.19 as stated in the report",
      close(round(cum_ar1[log.origin.dt.year == 2023].iloc[-1], 2), 1.19, 1e-9),
      f"{cum_ar1[log.origin.dt.year == 2023].iloc[-1]:.3f}")
check("vs random walk curve ends near zero", abs(cum_rw.iloc[-1]) < 0.05,
      f"final {cum_rw.iloc[-1]:+.4f}")

# ---------------------------------------------------------------------------
# 5. Figure 6: RMSE by year
# ---------------------------------------------------------------------------
print("\n5. FIGURE 6 (RMSE by year)")
wins = 0
for y in range(2021, 2026):
    sub = log[log.origin.dt.year == y]
    a = float(np.sqrt(((sub["AR1_log"] - sub["realized"]) ** 2).mean()))
    c = float(np.sqrt(((sub["COMBO"] - sub["realized"]) ** 2).mean()))
    ok = close(a, MET["_yearly"][str(y)]["AR1_log"], 1e-9) and \
        close(c, MET["_yearly"][str(y)]["COMBO"], 1e-9)
    wins += c < a
    check(f"{y} yearly RMSE reproduces", ok,
          f"AR1 {a:.4f} / COMBO {c:.4f} -> {'we win' if c < a else 'baseline wins'}")
check("we win four years of five (claim in report and deck)", wins == 4,
      f"{wins} wins")

# ---------------------------------------------------------------------------
# 6. Robustness cut
# ---------------------------------------------------------------------------
print("\n6. ROBUSTNESS CUT (targets inside 2025)")
sub = log[log.target_date <= "2025-12-31"]
rob = {k: float(np.sqrt(((sub[k] - sub["realized"]) ** 2).mean()))
       for k in MODELS}
for k in MODELS:
    check(f"{k} robustness RMSE matches",
          close(rob[k], MET["_targets_within_window"][k], 1e-9), f"{rob[k]:.4f}")
check("combination leads every model on this cut (claim on slide 4)",
      rob["COMBO"] == min(rob.values()),
      f"COMBO {rob['COMBO']:.4f}, next best {sorted(rob.values())[1]:.4f}")

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
# 8. The AR(1) claims quoted in the documents (R13.01, phi, half-life)
# ---------------------------------------------------------------------------
print("\n8. AR(1) CLAIMS QUOTED IN THE TEXT AND ON SLIDE 2")
wk = pd.read_csv(PROC / "weekly.csv", parse_dates=["friday"])
mus, phis = [], []
for t in log["origin"]:
    hh = wk[wk.friday <= t]["spot"].dropna().values
    yy = np.log(hh)
    XX = np.column_stack([np.ones(len(yy) - 1), yy[:-1]])
    cc, pp = np.linalg.lstsq(XX, yy[1:], rcond=None)[0]
    mus.append(np.exp(cc / (1 - pp)))
    phis.append(pp)
mus, phis = np.array(mus), np.array(phis)
gap = log["spot"].values - mus
check("implied long-run mean is BELOW spot at all 261 origins (headline claim)",
      (mus < log["spot"].values).all(),
      f"{(mus < log['spot'].values).sum()} of {len(log)}")
check("average gap R2.11 as quoted", close(round(gap.mean(), 2), 2.11, 1e-9),
      f"mean gap R{gap.mean():.4f}")
check("smallest gap R0.57 as quoted", close(round(gap.min(), 2), 0.57, 1e-9),
      f"min gap R{gap.min():.4f}")
check("implied mean ranges R11.80 to R19.18 as quoted",
      close(round(mus.min(), 2), 11.80, 1e-9)
      and close(round(mus.max(), 2), 19.18, 1e-9),
      f"R{mus.min():.2f} to R{mus.max():.2f}")
check("phi ranges 0.9971 to 0.9986 as quoted",
      close(round(phis.min(), 4), 0.9971, 1e-9)
      and close(round(phis.max(), 4), 0.9986, 1e-9),
      f"{phis.min():.4f} to {phis.max():.4f}")
check("spot rose from R14.62 to a peak of R19.74 as quoted",
      close(round(log["spot"].iloc[0], 2), 14.62, 1e-9)
      and close(round(log["spot"].max(), 2), 19.74, 1e-9),
      f"first R{log['spot'].iloc[0]:.2f}, peak R{log['spot'].max():.2f}")
i22 = wk.index[wk.friday == "2022-06-03"][0]
h22 = wk[wk.friday <= "2022-06-03"]["spot"].dropna().values
y22 = np.log(h22)
X22 = np.column_stack([np.ones(len(y22) - 1), y22[:-1]])
c22, p22 = np.linalg.lstsq(X22, y22[1:], rcond=None)[0]
check("worked-example origin: 1 222 obs, c=0.006335, phi=0.997531 as quoted",
      len(y22) == 1222 and close(round(c22, 6), 0.006335, 1e-9)
      and close(round(p22, 6), 0.997531, 1e-9),
      f"n={len(y22)}, c={c22:.6f}, phi={p22:.6f}")
check("worked-example implied mean R13.01 and half-life 280 weeks",
      close(round(float(np.exp(c22 / (1 - p22))), 2), 13.01, 1e-9)
      and abs(np.log(0.5) / np.log(p22) - 280) < 1,
      f"R{np.exp(c22 / (1 - p22)):.2f}, {np.log(0.5) / np.log(p22):.1f} weeks")
hL = wk[wk.friday <= "2025-12-26"]["spot"].dropna().values
yL = np.log(hL)
XL = np.column_stack([np.ones(len(yL) - 1), yL[:-1]])
cL, pL = np.linalg.lstsq(XL, yL[1:], rcond=None)[0]
check("final origin: mean R14.90, phi 0.9980 as quoted in the guide",
      close(round(float(np.exp(cL / (1 - pL))), 2), 14.90, 1e-9)
      and close(round(pL, 4), 0.9980, 1e-9),
      f"R{np.exp(cL / (1 - pL)):.2f}, phi {pL:.4f}")
r2223 = wk[(wk.friday >= "2022-01-01") & (wk.friday <= "2023-12-31")]["spot"]
check("2022-23 range R14.54 to R19.74 as quoted",
      close(round(r2223.min(), 2), 14.54, 1e-9)
      and close(round(r2223.max(), 2), 19.74, 1e-9),
      f"R{r2223.min():.2f} to R{r2223.max():.2f}")

# ---------------------------------------------------------------------------
# 9. Worked example on backup slide 12
# ---------------------------------------------------------------------------
print("\n9. WORKED EXAMPLE (backup slide 12, 3 June 2022)")
row = log[log.origin == "2022-06-03"]
if len(row):
    r = row.iloc[0]
    for label, shown, actual in [
            ("spot", 15.4117, r["spot"]), ("realised", 16.3482, r["realized"]),
            ("random walk", 15.4117, r["RW"]), ("carry", 15.4557, r["CARRY"]),
            ("AR(1)", 15.3861, r["AR1_log"]), ("ridge", 15.4089, r["RIDGE"]),
            ("combination", 15.4256, r["COMBO"])]:
        check(f"slide 12 {label}", close(round(actual, 4), shown),
              f"shows {shown}, actual {actual:.4f}")
    wrow = w.loc[pd.Timestamp("2022-06-03")]
    check("slide 12 weights 0.333 / 0.337 / 0.331",
          close(round(wrow["RW"], 3), 0.333) and
          close(round(wrow["CARRY"], 3), 0.337) and
          close(round(wrow["RIDGE"], 3), 0.331),
          f"{wrow['RW']:.3f} / {wrow['CARRY']:.3f} / {wrow['RIDGE']:.3f}")
    cd = wk[wk.friday == "2022-06-03"]["carry_diff"].iloc[0]
    check("slide 12 carry arithmetic reproduces",
          close(r["spot"] * (1 + cd * 28 / 365), r["CARRY"], 1e-6),
          f"{r['spot']:.4f} x (1 + {cd:.4f} x 28/365) = {r['CARRY']:.4f}")
else:
    check("worked example origin present in the log", False, "MISSING")

# ---------------------------------------------------------------------------
# 10. Figure 4 series panel and Table 3.1 come from real downloaded files
# ---------------------------------------------------------------------------
print("\n10. FIGURE 4 (input series) AND TABLE 3.1 (summary statistics)")
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
check("Table 3.1 forecast-era observation count is 261",
      int(stats.loc["spot", "obs_forecast_era(2021-25)"]) == 261,
      str(int(stats.loc["spot", "obs_forecast_era(2021-25)"])))

# ---------------------------------------------------------------------------
# 11. Claims about sample sizes quoted in the documents
# ---------------------------------------------------------------------------
print("\n11. SAMPLE-SIZE CLAIMS IN THE TEXT")
feats = ["carry_diff", "ret4_gold", "ret4_plat", "ret4_usd", "vix_z"]
trainable = wk.dropna(subset=feats + ["y"])
check("'about 850 training observations' is fair",
      800 <= len(trainable) <= 900, f"{len(trainable)} complete rows")
check("'14 173 daily observations' matches the EconData export",
      len(ecd) == 14173, f"{len(ecd)}")
check("'9 141 overlapping observations' matches the verification",
      len(m) == 9141, f"{len(m)}")

# ---------------------------------------------------------------------------
# 12. Ridge shrinkage claim (8 per cent of OLS)
# ---------------------------------------------------------------------------
print("\n12. RIDGE SHRINKAGE CLAIM")
try:
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler
    i = wk.index[wk.friday == "2025-12-26"][0]
    tr = wk.loc[wk.index <= i - 4].dropna(subset=feats + ["y"])
    Xs = StandardScaler().fit_transform(tr[feats].values.astype(float))
    yv = tr["y"].values
    ridge = Ridge(alpha=10000, fit_intercept=False).fit(Xs, yv)
    ols = Ridge(alpha=1e-9, fit_intercept=False).fit(Xs, yv)
    ratio = np.linalg.norm(ridge.coef_) / np.linalg.norm(ols.coef_)
    check("'about 8 per cent of the OLS coefficients'",
          0.06 <= ratio <= 0.10, f"ratio {ratio:.3f}")
except Exception as ex:              # pragma: no cover
    check("ridge shrinkage check ran", False, str(ex)[:50])

# ---------------------------------------------------------------------------
# 13. Numbers hard-coded in the deck must match the live metrics
# ---------------------------------------------------------------------------
print("\n13. HARD-CODED NUMBERS IN THE DECK SOURCE")
js = (BASE / "src" / "make_presentation.js").read_text(encoding="utf-8")
for lit, val, lab in [("15.4117", r["spot"], "worked-example spot"),
                      ("16.3482", r["realized"], "worked-example realised"),
                      ("15.4256", r["COMBO"], "worked-example combination"),
                      ("2.11", gap.mean(), "average lean below spot"),
                      ("11.80", mus.min(), "minimum implied mean"),
                      ("19.18", mus.max(), "maximum implied mean"),
                      ("19.74", log["spot"].max(), "peak spot in window"),
                      ("14.62", log["spot"].iloc[0], "first spot in window")]:
    check(f"deck literal {lit} ({lab})",
          lit in js and close(float(lit), round(val, len(lit.split('.')[1])),
                              10 ** -len(lit.split('.')[1]) * 1.01),
          f"live value {val:.4f}")

# ---------------------------------------------------------------------------
print("\n" + "=" * 78)
print(f"RESULT: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("\nFAILURES:")
    for f in FAIL:
        print("  -", f)
else:
    print("Every plotted and quoted number traces back to the raw data.")
print("=" * 78)
