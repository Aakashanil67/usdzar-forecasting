"""
run_backtest.py - Walk-forward out-of-sample backtest for USDZAR, judged
window 2021-01-01 .. 2025-12-31.

Honesty protocol
----------------
Every design choice with a free parameter (ridge feature set, intercept,
combination weighting scheme) is selected ONCE on a pre-2021 VALIDATION era
(origins 2015-01-02 .. 2020-12-25, whose targets all resolve before the judged
window) and then FROZEN. Nothing is tuned on 2021-2025. The 2013-2014 period
only warms up combination weights. Every forecast at origin t uses only data
dated <= t.

Models
------
  AR1_log / AR1_level : required baseline. OLS AR(1) with intercept on the
      weekly (log) USDZAR level, expanding window from 1999, iterated 4 steps.
      The official comparison uses whichever variant has the LOWER RMSE in the
      judged window (we compare against the stronger baseline).
  RW    : no-change forecast S_hat = S_t.
  CARRY : forward-rate tilt  S_hat = S_t * (1 + (i_ZA - i_US) * 28/365).
  RIDGE : ridge regression of the 4-week log return on financial predictors.
      Standardised on training window; penalty by 5-fold time-ordered CV inside
      the training window, re-selected quarterly; training rows restricted to
      origins whose target has RESOLVED by t (index <= t - 4 weeks).
  GBM   : small HistGradientBoosting comparator under identical discipline.
  COMBO : weighted average of {RW, CARRY, RIDGE}; weights at t from
      inverse discounted MSE of RESOLVED past forecasts only:
          w_i propto (sum_k delta^age_k e_{i,k}^2)^(-theta)
      (delta, theta, ridge variant frozen on the validation era).

Outputs: data/processed/{forecast_log.csv, combo_weights.csv, metrics.json,
validation_metrics.json}
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler

BASE = Path(__file__).resolve().parents[1]
PROC = BASE / "data" / "processed"

FEATS_FULL = ["carry_diff", "d_carry_4w", "ret4_gold", "ret4_plat",
              "ret4_brent", "ret4_usd", "vix_z", "d_vix_4w", "ret4_spot",
              "ret12_spot", "ma_gap"]
FEATS_CMP = ["carry_diff", "ret4_gold", "ret4_plat", "ret4_usd", "vix_z"]

H = 4                                   # horizon: 4 weeks = 28 days
WARMUP_START = "2013-01-04"             # weight warm-up only
VAL_START, VAL_END = "2015-01-02", "2020-12-25"   # model-selection era
EVAL_START, EVAL_END = "2021-01-01", "2025-12-31" # judged era (frozen models)
ALPHAS = np.logspace(-2, 4, 7)
ALPHA_REFRESH = 13                      # re-select ridge penalty quarterly
GBM_REFIT_EVERY = 4


def ar1_forecast(y: np.ndarray, steps: int) -> float:
    """OLS AR(1) with intercept, iterated `steps` ahead."""
    x, z = y[:-1], y[1:]
    X = np.column_stack([np.ones_like(x), x])
    c, phi = np.linalg.lstsq(X, z, rcond=None)[0]
    f = y[-1]
    for _ in range(steps):
        f = c + phi * f
    return f


def ridge_cv_alpha(X: np.ndarray, y: np.ndarray, fit_intercept: bool) -> float:
    best, best_mse = ALPHAS[0], np.inf
    for a in ALPHAS:
        mse = []
        for tr, te in TimeSeriesSplit(5).split(X):
            m = Ridge(alpha=a, fit_intercept=fit_intercept).fit(X[tr], y[tr])
            mse.append(np.mean((y[te] - m.predict(X[te])) ** 2))
        if np.mean(mse) < best_mse:
            best, best_mse = a, np.mean(mse)
    return best


def dm_test(e1: np.ndarray, e2: np.ndarray, lag: int = H - 1):
    """Diebold-Mariano, squared loss, Newey-West var (overlapping forecasts).
    Negative => model 1 more accurate."""
    d = e1 ** 2 - e2 ** 2
    n = len(d)
    u = d - d.mean()
    s = u @ u / n
    for k in range(1, lag + 1):
        s += 2 * (1 - k / (lag + 1)) * (u[k:] @ u[:-k]) / n
    stat = d.mean() / np.sqrt(s / n)
    from math import erf, sqrt
    return stat, 2 * (1 - 0.5 * (1 + erf(abs(stat) / sqrt(2))))


def run_members(w: pd.DataFrame) -> pd.DataFrame:
    """Generate all member forecasts for every origin >= WARMUP_START."""
    idx = w.index.values
    origins = w[(w.friday >= WARMUP_START) & (w.friday <= EVAL_END)].index
    alphas_cache, rows = {}, []
    gbm_model, gbm_age = None, 10 ** 9

    for n_done, i in enumerate(origins):
        t, s_t = w.at[i, "friday"], w.at[i, "spot"]
        if not np.isfinite(s_t):
            continue
        hist = w.loc[:i, "spot"].dropna().values
        row = dict(origin=t, spot=s_t, target_date=w.at[i, "target_date"],
                   realized=w.at[i, "realized"],
                   AR1_log=float(np.exp(ar1_forecast(np.log(hist), H))),
                   AR1_level=float(ar1_forecast(hist, H)), RW=float(s_t))
        cd = w.at[i, "carry_diff"]
        row["CARRY"] = float(s_t * (1 + cd * 28 / 365)) if np.isfinite(cd) else row["RW"]

        tr = w.loc[idx < i - H + 1].dropna(subset=FEATS_FULL + ["y"])
        tr = tr[tr.index <= i - H]                      # resolved targets only
        for tag, feats, fit_int in [("RIDGE_f1", FEATS_FULL, True),
                                    ("RIDGE_f0", FEATS_FULL, False),
                                    ("RIDGE_c1", FEATS_CMP, True),
                                    ("RIDGE_c0", FEATS_CMP, False)]:
            row[tag] = row["RW"]
            x_t = w.loc[i, feats].values.astype(float)
            if len(tr) > 120 and np.isfinite(x_t).all():
                Xtr, ytr = tr[feats].values.astype(float), tr["y"].values
                sc = StandardScaler().fit(Xtr)
                Xs = sc.transform(Xtr)
                if tag not in alphas_cache or n_done % ALPHA_REFRESH == 0:
                    alphas_cache[tag] = ridge_cv_alpha(Xs, ytr, fit_int)
                m = Ridge(alpha=alphas_cache[tag], fit_intercept=fit_int).fit(Xs, ytr)
                row[tag] = float(s_t * np.exp(m.predict(sc.transform(x_t[None]))[0]))

        row["GBM"] = row["RW"]
        x_t = w.loc[i, FEATS_FULL].values.astype(float)
        if len(tr) > 120 and np.isfinite(x_t).all():
            if gbm_age >= GBM_REFIT_EVERY:
                gbm_model = HistGradientBoostingRegressor(
                    max_depth=2, learning_rate=0.05, max_iter=150,
                    l2_regularization=1.0, random_state=42
                ).fit(tr[FEATS_FULL].values.astype(float), tr["y"].values)
                gbm_age = 0
            gbm_age += 1
            row["GBM"] = float(s_t * np.exp(gbm_model.predict(x_t[None])[0]))
        rows.append(row)
    return pd.DataFrame(rows).set_index("origin")


def combo_series(log: pd.DataFrame, ridge_tag: str, delta: float,
                 theta: float) -> tuple[pd.Series, pd.DataFrame]:
    """Inverse discounted-MSE weighted combination of RW, CARRY, chosen RIDGE."""
    members = ["RW", "CARRY", ridge_tag]
    err2 = (log[members].sub(log["realized"], axis=0) ** 2)
    dates = log.index
    out, wlog = [], []
    for t in dates:
        resolved = err2[dates <= t - pd.Timedelta(days=28)].dropna().tail(156)
        if len(resolved) < 26:
            wgt = np.ones(3) / 3
        else:
            age = np.arange(len(resolved))[::-1]           # 0 = most recent
            disc = (delta ** age)[:, None]
            dmse = (resolved.values * disc).sum(0) / disc.sum()
            inv = dmse ** (-theta)
            wgt = inv / inv.sum()
        out.append(float(log.loc[t, members].values @ wgt))
        wlog.append(wgt)
    return (pd.Series(out, index=dates, name="COMBO"),
            pd.DataFrame(wlog, index=dates, columns=members))


def score(log: pd.DataFrame, cols, start, end) -> dict:
    ev = log[(log.index >= start) & (log.index <= end)].dropna(subset=["realized"])
    res = {}
    for c in cols:
        e = ev[c] - ev["realized"]
        res[c] = dict(rmse=float(np.sqrt((e ** 2).mean())),
                      mae=float(e.abs().mean()), n=int(len(e)),
                      dir_acc=float(np.mean(
                          np.sign(ev[c] / ev["spot"] - 1)
                          == np.sign(ev["realized"] / ev["spot"] - 1))))
    return res


def members_cached(w: pd.DataFrame) -> pd.DataFrame:
    """Member forecasts are the slow stage. Cache them, keyed on the inputs and
    the settings that determine them, so a rerun is fast but any real change to
    the data or the configuration invalidates the cache automatically."""
    import hashlib
    key = hashlib.sha256(
        (PROC / "weekly.csv").read_bytes()
        + repr([FEATS_FULL, FEATS_CMP, H, WARMUP_START, EVAL_END,
                list(ALPHAS), ALPHA_REFRESH, GBM_REFIT_EVERY]).encode()
    ).hexdigest()
    cache, meta = PROC / "members_cache.csv", PROC / "members_cache.key"
    if cache.exists() and meta.exists() and meta.read_text().strip() == key:
        print("member forecasts: loaded from cache")
        return pd.read_csv(cache, parse_dates=["origin", "target_date"]
                           ).set_index("origin")
    print("member forecasts: computing (this is the slow stage)")
    log = run_members(w)
    log.to_csv(cache)
    meta.write_text(key)
    return log


def main() -> None:
    w = pd.read_csv(PROC / "weekly.csv",
                    parse_dates=["friday", "target_date"]).reset_index(drop=True)
    log = members_cached(w)

    # ---------- model selection on the VALIDATION era only ----------
    grid, val_scores = [], {}
    for tag in ["RIDGE_f1", "RIDGE_f0", "RIDGE_c1", "RIDGE_c0"]:
        for delta in [1.0, 0.99, 0.97]:
            for theta in [1.0, 2.0]:
                combo, _ = combo_series(log, tag, delta, theta)
                tmp = log.copy(); tmp["COMBO"] = combo
                r = score(tmp, ["COMBO"], VAL_START, VAL_END)["COMBO"]["rmse"]
                grid.append(((tag, delta, theta), r))
    grid.sort(key=lambda g: g[1])
    (ridge_tag, delta, theta), val_rmse = grid[0]
    val_scores["chosen_config"] = dict(ridge=ridge_tag, delta=delta,
                                       theta=theta, val_rmse=val_rmse)
    val_scores["validation_era"] = score(
        log.assign(COMBO=combo_series(log, ridge_tag, delta, theta)[0]),
        ["AR1_log", "AR1_level", "RW", "CARRY", ridge_tag, "GBM", "COMBO"],
        VAL_START, VAL_END)
    val_scores["grid_top5"] = [dict(cfg=list(c), rmse=r) for c, r in grid[:5]]
    with open(PROC / "validation_metrics.json", "w") as fh:
        json.dump(val_scores, fh, indent=2)

    # ---------- frozen model, judged era ----------
    combo, wlog = combo_series(log, ridge_tag, delta, theta)
    log["COMBO"] = combo
    log = log.rename(columns={ridge_tag: "RIDGE"})
    wlog.columns = ["RW", "CARRY", "RIDGE"]
    wlog.to_csv(PROC / "combo_weights.csv")

    models = ["AR1_log", "AR1_level", "RW", "CARRY", "RIDGE", "GBM", "COMBO"]
    ev = log[(log.index >= EVAL_START) & (log.index <= EVAL_END)].dropna(
        subset=["realized"])
    ev[["spot", "target_date", "realized"] + models].to_csv(
        PROC / "forecast_log.csv")

    res = score(log, models, EVAL_START, EVAL_END)
    base = min(["AR1_log", "AR1_level"], key=lambda v: res[v]["rmse"])
    res["_baseline_used"] = base
    for mname in ["RW", "CARRY", "RIDGE", "GBM", "COMBO"]:
        stat, p = dm_test((ev[mname] - ev["realized"]).values,
                          (ev[base] - ev["realized"]).values)
        res[mname]["dm_vs_ar1"] = [round(float(stat), 3), round(float(p), 4)]
    stat, p = dm_test((ev["COMBO"] - ev["realized"]).values,
                      (ev["RW"] - ev["realized"]).values)
    res["COMBO"]["dm_vs_rw"] = [round(float(stat), 3), round(float(p), 4)]

    res["_yearly"] = {y: {mname: float(np.sqrt(((
        (s := ev[ev.index.year == y])[mname] - s["realized"]) ** 2).mean()))
        for mname in models} for y in range(2021, 2026)}
    ev2 = ev[ev["target_date"] <= EVAL_END]
    res["_targets_within_window"] = {mname: float(np.sqrt(
        ((ev2[mname] - ev2["realized"]) ** 2).mean())) for mname in models}

    with open(PROC / "metrics.json", "w") as fh:
        json.dump(res, fh, indent=2, default=str)
    print("chosen:", val_scores["chosen_config"])
    print(json.dumps({k: dict(rmse=v["rmse"]) for k, v in res.items()
                      if isinstance(v, dict) and "rmse" in v}, indent=2))


if __name__ == "__main__":
    main()
