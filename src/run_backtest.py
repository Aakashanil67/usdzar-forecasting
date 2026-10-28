"""
run_backtest.py - Walk-forward out-of-sample backtest for USDZAR, judged
window 2021-01-01 .. 2025-12-31.

Selection protocol
------------------
Every design choice with a free parameter (ridge feature set, intercept,
combination weighting scheme) is selected once on a pre-2021 validation era
and then frozen. The validation era runs from 2015-01-02 to 2020-11-27, the
last origin whose 28-day target is fixed before 2021-01-01; validation_era()
asserts this on the target dates. Nothing is tuned on 2021-2025. The 2013-2014
period only warms up combination weights. A row counts as training data at
origin t only once its target date is <= t (resolved()), and predictors enter
when they were published, not when they were observed (build_dataset.py).

Models
------
  AR1_log : the mandated benchmark (BASELINE). OLS AR(1) with intercept
      on the weekly log USDZAR level, expanding window from 1999, iterated
      4 steps and exponentiated. Variants, none of which replaces it:
      AR1_level (the same model on the level), AR1_log_roll (the last
      AR1_ROLL_WEEKS weeks only) and AR1_log_vc (exp(f + v/2), v the 4-step
      forecast variance implied by the residual variance of the fit at t).
  RW    : no-change forecast S_hat = S_t.
  RW_drift : S_t * exp(4 * mean weekly log change), expanding window from 1999.
  CARRY : forward-rate tilt  S_hat = S_t * (1 + (i_ZA - i_US) * 28/365).
  RIDGE : ridge regression of the 4-week log return on financial predictors,
      as a StandardScaler + Ridge pipeline so the scaling is refitted inside
      every CV fold. The penalty is re-selected quarterly by 5-fold purged CV
      on the resolved training rows (purged_folds()).
  GBM   : HistGradientBoosting on the same rows, its configuration picked from
      GBM_GRID by the same purged CV, once a year.
  COMBO : weighted average of {RW, CARRY, RIDGE}; weights at t from
      inverse discounted MSE of resolved past forecasts only:
          w_i propto (sum_k delta^age_k e_{i,k}^2)^(-theta)
      (delta, theta, ridge variant frozen on the validation era).
  Ablations of COMBO: EQUAL3 (RW, CARRY, RIDGE at 1/3 each), and RW_CARRY and
      RW_RIDGE (the same adaptive weighting with one member dropped).

Outputs: data/processed/{forecast_log.csv, combo_weights.csv, metrics.json,
validation_metrics.json}
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from statistical_tests import dm_test

BASE = Path(__file__).resolve().parents[1]
PROC = BASE / "data" / "processed"

FEATS_FULL = ["carry_diff", "d_carry_4w", "ret4_gold", "ret4_plat",
              "ret4_brent", "ret4_usd", "vix_z", "d_vix_4w", "ret4_spot",
              "ret12_spot", "ma_gap"]
FEATS_CMP = ["carry_diff", "ret4_gold", "ret4_plat", "ret4_usd", "vix_z"]

H = 4                                   # horizon: 4 weeks = 28 days
WARMUP_START = "2013-01-04"             # weight warm-up only
VAL_START, VAL_END = "2015-01-02", "2020-11-27"   # model-selection era
EVAL_START, EVAL_END = "2021-01-01", "2025-12-31" # judged era (frozen models)
BASELINE = "AR1_log"
ALPHAS = np.logspace(-2, 4, 7)
ALPHA_REFRESH = 13                      # re-select ridge penalty quarterly
CV_FOLDS = 5
GBM_REFIT_EVERY = 4
AR1_ROLL_WEEKS = 260                    # five years, fixed before any scoring
# 12 configurations x 5 folds is 60 fits per search. Quarterly, like the ridge
# penalty, that would be about 3,000 fits per run; yearly it is 780.
GBM_RETUNE_EVERY = 52
GBM_GRID = [dict(max_depth=d, learning_rate=lr, max_iter=it,
                 l2_regularization=l2, min_samples_leaf=leaf)
            for d in (2, 3)
            for lr, it in ((0.1, 50), (0.03, 150))
            for l2, leaf in ((0.0, 20), (1.0, 40), (10.0, 80))]


def resolved(df: pd.DataFrame, as_of) -> pd.DataFrame:
    """Rows whose target had been fixed by `as_of`, chosen by target date.
    A missing target date would be silently dropped here, so refuse it."""
    assert df["target_date"].notna().all(), "row without a target date"
    return df[df["target_date"] <= pd.Timestamp(as_of)]


def validation_era(log: pd.DataFrame) -> pd.DataFrame:
    v = log[(log.index >= VAL_START) & (log.index <= VAL_END)]
    last = v["target_date"].max()
    assert last < pd.Timestamp(EVAL_START), (
        f"validation target {last.date()} falls inside the judged era")
    return v


def judged_era(log: pd.DataFrame) -> pd.DataFrame:
    return log[(log.index >= EVAL_START) & (log.index <= EVAL_END)]


def purged_folds(origins: np.ndarray, targets: np.ndarray) -> list:
    """Time-ordered expanding folds. A training row is dropped when its target
    date is on or after the first origin of the fold it is scored against, so
    no training label is fixed inside that fold."""
    return [(tr[targets[tr] < origins[te[0]]], te)
            for tr, te in TimeSeriesSplit(CV_FOLDS).split(origins)]


def cv_mse(make_model, X: np.ndarray, y: np.ndarray, folds: list) -> float:
    return float(np.mean([
        np.mean((y[te] - make_model().fit(X[tr], y[tr]).predict(X[te])) ** 2)
        for tr, te in folds]))


def ridge_model(alpha: float, fit_intercept: bool):
    return make_pipeline(StandardScaler(),
                         Ridge(alpha=alpha, fit_intercept=fit_intercept))


def gbm_model(k: int) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(**GBM_GRID[k], random_state=42)


def ar1_fit(y: np.ndarray) -> tuple[float, float, float]:
    """OLS AR(1) with intercept: c, phi and the residual variance (n - 2 df)."""
    X = np.column_stack([np.ones(len(y) - 1), y[:-1]])
    (c, phi), rss = np.linalg.lstsq(X, y[1:], rcond=None)[:2]
    return c, phi, float(rss[0]) / (len(y) - 3)


def ar1_forecast(y: np.ndarray, steps: int) -> float:
    """OLS AR(1) with intercept, iterated `steps` ahead."""
    c, phi, _ = ar1_fit(y)
    f = y[-1]
    for _ in range(steps):
        f = c + phi * f
    return f


def ar1_log_corrected(level: np.ndarray, steps: int) -> float:
    """exp of the log AR(1) forecast is a median, not a mean. With Gaussian
    shocks the mean is exp(f + v/2), v = s2 * sum_j phi^(2j) for j < steps,
    s2 the residual variance of the same fit, so only data up to t."""
    y = np.log(level)
    _, phi, s2 = ar1_fit(y)
    v = s2 * sum(phi ** (2 * j) for j in range(steps))
    return float(np.exp(ar1_forecast(y, steps) + v / 2))


def drift_forecast(level: np.ndarray, steps: int) -> float:
    """Random walk with drift: the mean weekly log change up to t, carried
    `steps` weeks forward."""
    return float(level[-1] * np.exp(steps * np.diff(np.log(level)).mean()))


def run_members(w: pd.DataFrame, origins=None
                ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Member forecasts for every origin >= WARMUP_START (or for the given row
    labels of `w`), plus the purged-CV score of every GBM configuration at
    each yearly retune."""
    if origins is None:
        origins = w[(w.friday >= WARMUP_START) & (w.friday <= EVAL_END)].index
    alphas, rows, gbm_trials = {}, [], {}
    gbm_cfg, gbm_fit, gbm_age, since_tune = None, None, 0, GBM_RETUNE_EVERY

    for n_done, i in enumerate(origins):
        t, s_t = w.at[i, "friday"], w.at[i, "spot"]
        if not np.isfinite(s_t):
            continue
        hist = w.loc[:i, "spot"].dropna().values
        row = dict(origin=t, spot=s_t, target_date=w.at[i, "target_date"],
                   realized=w.at[i, "realized"],
                   AR1_log=float(np.exp(ar1_forecast(np.log(hist), H))),
                   AR1_level=float(ar1_forecast(hist, H)),
                   AR1_log_roll=float(np.exp(ar1_forecast(
                       np.log(hist[-AR1_ROLL_WEEKS:]), H))),
                   AR1_log_vc=ar1_log_corrected(hist, H),
                   RW=float(s_t), RW_drift=drift_forecast(hist, H))
        cd = w.at[i, "carry_diff"]
        row["CARRY"] = float(s_t * (1 + cd * 28 / 365)) if np.isfinite(cd) else row["RW"]

        tr = resolved(w, t).dropna(subset=FEATS_FULL + ["y"])
        ytr = tr["y"].values
        folds = purged_folds(tr["friday"].values, tr["target_date"].values)
        for tag, feats, fit_int in [("RIDGE_f1", FEATS_FULL, True),
                                    ("RIDGE_f0", FEATS_FULL, False),
                                    ("RIDGE_c1", FEATS_CMP, True),
                                    ("RIDGE_c0", FEATS_CMP, False)]:
            row[tag] = row["RW"]
            x_t = w.loc[i, feats].values.astype(float)
            if len(tr) > 120 and np.isfinite(x_t).all():
                Xtr = tr[feats].values.astype(float)
                if tag not in alphas or n_done % ALPHA_REFRESH == 0:
                    alphas[tag] = min(ALPHAS, key=lambda a: cv_mse(
                        lambda: ridge_model(a, fit_int), Xtr, ytr, folds))
                m = ridge_model(alphas[tag], fit_int).fit(Xtr, ytr)
                row[tag] = float(s_t * np.exp(m.predict(x_t[None])[0]))

        row["GBM"], row["gbm_cfg"] = row["RW"], -1
        x_t = w.loc[i, FEATS_FULL].values.astype(float)
        if len(tr) > 120 and np.isfinite(x_t).all():
            Xtr = tr[FEATS_FULL].values.astype(float)
            if since_tune >= GBM_RETUNE_EVERY:
                scores = [cv_mse(lambda: gbm_model(k), Xtr, ytr, folds)
                          for k in range(len(GBM_GRID))]
                gbm_trials[t] = scores
                gbm_cfg, since_tune = int(np.argmin(scores)), 0
                gbm_age = GBM_REFIT_EVERY          # refit now with the new config
            if gbm_age >= GBM_REFIT_EVERY:
                gbm_fit, gbm_age = gbm_model(gbm_cfg).fit(Xtr, ytr), 0
            gbm_age += 1
            since_tune += 1
            row["GBM"] = float(s_t * np.exp(gbm_fit.predict(x_t[None])[0]))
            row["gbm_cfg"] = gbm_cfg
        rows.append(row)
    trials = pd.DataFrame.from_dict(gbm_trials, orient="index",
                                    columns=[f"cfg{k}" for k in range(len(GBM_GRID))])
    trials.index.name = "origin"
    return pd.DataFrame(rows).set_index("origin"), trials


def combo_series(log: pd.DataFrame, members: list, delta: float,
                 theta: float) -> tuple[pd.Series, pd.DataFrame]:
    """Inverse discounted-MSE weighted combination of the `members` columns."""
    err2 = (log[members].sub(log["realized"], axis=0) ** 2)
    dates = log.index
    out, wlog = [], []
    for t in dates:
        past = err2.loc[resolved(log, t).index].dropna().tail(156)
        # Cross-check the target dates against the origins: the newest error
        # used at t must come from an origin at least 28 days earlier.
        assert past.empty or past.index[-1] <= t - pd.Timedelta(days=28), (
            f"combination weights at {t.date()} use an unresolved error")
        if len(past) < 26:
            wgt = np.ones(len(members)) / len(members)
        else:
            age = np.arange(len(past))[::-1]               # 0 = most recent
            disc = (delta ** age)[:, None]
            dmse = (past.values * disc).sum(0) / disc.sum()
            inv = dmse ** (-theta)
            wgt = inv / inv.sum()
        out.append(float(log.loc[t, members].values @ wgt))
        wlog.append(wgt)
    return (pd.Series(out, index=dates),
            pd.DataFrame(wlog, index=dates, columns=members))


def add_combinations(log: pd.DataFrame, ridge_tag: str, delta: float,
                     theta: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    """COMBO and its three ablations as new columns, plus COMBO's weights."""
    combo, wlog = combo_series(log, ["RW", "CARRY", ridge_tag], delta, theta)
    return log.assign(
        COMBO=combo,
        EQUAL3=log[["RW", "CARRY", ridge_tag]].mean(axis=1),
        RW_CARRY=combo_series(log, ["RW", "CARRY"], delta, theta)[0],
        RW_RIDGE=combo_series(log, ["RW", ridge_tag], delta, theta)[0]), wlog


def forecast_at(origin, w: pd.DataFrame, ridge_tag: str, delta: float,
                theta: float, lookback: int = 31) -> pd.Series:
    """Every model's forecast issued on `origin`, from the last `lookback`
    weekly rows of `w` up to and including it. It goes through run_members and
    combo_series, so it is the same fitting code as the full backtest, but the
    ridge penalty, the GBM configuration and the combination weights start from
    this shorter history. It does not reproduce forecast_log.csv; it exists to
    ask what a single forecast depends on. Thirty-one rows leave 27 resolved
    errors, enough for the combination to leave equal weights."""
    rows = w.index[w["friday"] <= pd.Timestamp(origin)][-lookback:]
    assert w.at[rows[-1], "friday"] == pd.Timestamp(origin), (
        f"{origin} is not a Friday on the weekly grid")
    log, _ = run_members(w, rows)
    log = add_combinations(log, ridge_tag, delta, theta)[0]
    return log.iloc[-1].drop(["target_date", "realized"])


def score(ev: pd.DataFrame, cols) -> dict:
    ev = ev.dropna(subset=["realized"])
    res = {}
    for c in cols:
        e = ev[c] - ev["realized"]
        res[c] = dict(rmse=float(np.sqrt((e ** 2).mean())),
                      mae=float(e.abs().mean()), n=int(len(e)),
                      dir_acc=float(np.mean(
                          np.sign(ev[c] / ev["spot"] - 1)
                          == np.sign(ev["realized"] / ev["spot"] - 1))),
                      up_share=float((ev[c] > ev["spot"]).mean()))
    return res


def members_cached(w: pd.DataFrame, name: str = "members_cache"
                   ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Member forecasts are the slow stage. Cache them, keyed on the inputs and
    the settings that determine them, so a rerun is fast but any real change to
    the data, the code or the configuration invalidates the cache automatically."""
    code = b"".join(f.read_bytes() for f in sorted(Path(__file__).parent.glob("*.py")))
    key = hashlib.sha256(
        pd.util.hash_pandas_object(w).values.tobytes() + code
        + repr([FEATS_FULL, FEATS_CMP, H, WARMUP_START, VAL_START, VAL_END,
                EVAL_START, EVAL_END, list(ALPHAS), ALPHA_REFRESH, CV_FOLDS,
                GBM_REFIT_EVERY, GBM_RETUNE_EVERY,
                [sorted(p.items()) for p in GBM_GRID],
                sklearn.__version__]).encode()
    ).hexdigest()
    cache, meta = PROC / f"{name}.csv", PROC / f"{name}.key"
    trials_file = PROC / f"{name}_gbm_cv.csv"
    if (cache.exists() and trials_file.exists() and meta.exists()
            and meta.read_text().strip() == key):
        print("member forecasts: loaded from cache")
        return (pd.read_csv(cache, parse_dates=["origin", "target_date"]
                            ).set_index("origin"),
                pd.read_csv(trials_file, parse_dates=["origin"]).set_index("origin"))
    print("member forecasts: computing (this is the slow stage)")
    log, trials = run_members(w)
    log.to_csv(cache)
    trials.to_csv(trials_file)
    meta.write_text(key)
    return log, trials


def select_config(log: pd.DataFrame) -> list:
    """Score every (ridge variant, delta, theta) on the validation era,
    best first."""
    grid = []
    for tag in ["RIDGE_f1", "RIDGE_f0", "RIDGE_c1", "RIDGE_c0"]:
        for delta in [1.0, 0.99, 0.97]:
            for theta in [1.0, 2.0]:
                combo, _ = combo_series(log, ["RW", "CARRY", tag], delta, theta)
                r = score(validation_era(log.assign(COMBO=combo)),
                          ["COMBO"])["COMBO"]["rmse"]
                grid.append(((tag, delta, theta), r))
    return sorted(grid, key=lambda g: g[1])


def gbm_summary(log: pd.DataFrame, trials: pd.DataFrame) -> dict:
    """The GBM grid, every retune's purged-CV scores, and which configuration
    produced each judged-era forecast."""
    in_force = judged_era(log)["gbm_cfg"].value_counts().sort_index()
    return dict(
        grid=GBM_GRID, retune_every=GBM_RETUNE_EVERY, cv_folds=CV_FOLDS,
        trials=[dict(origin=str(t.date()), cv_mse=list(r.values),
                     chosen=int(np.argmin(r.values)))
                for t, r in trials.iterrows()],
        judged_origins_by_config={int(k): int(v) for k, v in in_force.items()})


MODELS = ["AR1_log", "AR1_level", "AR1_log_roll", "AR1_log_vc", "RW",
          "RW_drift", "CARRY", "RIDGE", "GBM", "COMBO", "EQUAL3", "RW_CARRY",
          "RW_RIDGE"]


def main() -> None:
    w = pd.read_csv(PROC / "weekly.csv",
                    parse_dates=["friday", "target_date"]).reset_index(drop=True)
    log, gbm_trials = members_cached(w)

    # ---------- model selection, validation era only ----------
    val_scores = {}
    grid = select_config(log)
    (ridge_tag, delta, theta), val_rmse = grid[0]
    val_scores["chosen_config"] = dict(ridge=ridge_tag, delta=delta,
                                       theta=theta, val_rmse=val_rmse)
    log, wlog = add_combinations(log, ridge_tag, delta, theta)
    val = validation_era(log)
    val_scores["validation_window"] = dict(
        first_origin=str(val.index.min().date()),
        last_origin=str(val.index.max().date()),
        last_target=str(val["target_date"].max().date()))
    val_scores["validation_era"] = score(
        val, [ridge_tag if m == "RIDGE" else m for m in MODELS])
    val_scores["grid"] = [dict(ridge=c[0], delta=c[1], theta=c[2], rmse=r)
                          for c, r in grid]
    val_scores["gbm"] = gbm_summary(log, gbm_trials)
    with open(PROC / "validation_metrics.json", "w") as fh:
        json.dump(val_scores, fh, indent=2)

    # ---------- frozen model, judged era ----------
    log = log.rename(columns={ridge_tag: "RIDGE"})
    wlog.columns = ["RW", "CARRY", "RIDGE"]
    wlog.to_csv(PROC / "combo_weights.csv")

    ev = judged_era(log).dropna(subset=["realized"])
    ev[["spot", "target_date", "realized"] + MODELS].to_csv(
        PROC / "forecast_log.csv")

    res = score(ev, MODELS)
    res["_baseline_used"] = BASELINE
    for mname in ["RW", "CARRY", "RIDGE", "GBM", "COMBO"]:
        stat, p, _ = dm_test((ev[mname] - ev["realized"]).values,
                             (ev[BASELINE] - ev["realized"]).values)
        res[mname]["dm_vs_ar1"] = [round(float(stat), 3), round(float(p), 4)]
    stat, p, _ = dm_test((ev["COMBO"] - ev["realized"]).values,
                         (ev["RW"] - ev["realized"]).values)
    res["COMBO"]["dm_vs_rw"] = [round(float(stat), 3), round(float(p), 4)]

    res["_yearly"] = {y: {mname: float(np.sqrt(((
        (s := ev[ev.index.year == y])[mname] - s["realized"]) ** 2).mean()))
        for mname in MODELS} for y in range(2021, 2026)}
    ev2 = ev[ev["target_date"] <= EVAL_END]
    res["_targets_within_window"] = {mname: float(np.sqrt(
        ((ev2[mname] - ev2["realized"]) ** 2).mean())) for mname in MODELS}

    with open(PROC / "metrics.json", "w") as fh:
        json.dump(res, fh, indent=2, default=str)
    print("chosen:", val_scores["chosen_config"])
    print(json.dumps({k: dict(rmse=v["rmse"]) for k, v in res.items()
                      if isinstance(v, dict) and "rmse" in v}, indent=2))


if __name__ == "__main__":
    main()
