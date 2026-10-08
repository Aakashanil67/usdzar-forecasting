"""
Leakage inside model fitting: which training rows count as resolved, how the
cross-validation folds are cut, where the scaler is fitted, where the
validation era stops, and which past errors may set the combination weights.
"""
import numpy as np
import pandas as pd
import pytest
from sklearn.model_selection import TimeSeriesSplit

import run_backtest as rb

FRIDAYS = pd.date_range("2016-01-01", periods=90, freq="W-FRI")


@pytest.fixture(scope="module")
def training_rows(built):
    """Complete training rows as of mid-2018, as run_members builds them."""
    rows = rb.resolved(built, "2018-06-01").dropna(subset=rb.FEATS_FULL + ["y"])
    assert len(rows) > 300
    return rows


# ---------------------------------------------------------------- resolved
def test_a_row_resolves_on_its_target_date_not_one_day_earlier():
    df = pd.DataFrame({"target_date": pd.to_datetime(["2020-01-02", "2020-01-03",
                                                       "2020-01-04"])})
    assert list(rb.resolved(df, "2020-01-03").index) == [0, 1]


def test_resolved_refuses_rows_without_a_target_date():
    df = pd.DataFrame({"target_date": pd.to_datetime(["2020-01-02", None])})
    with pytest.raises(AssertionError):
        rb.resolved(df, "2020-06-01")


def test_resolved_training_rows_all_have_their_label_fixed(training_rows):
    assert (training_rows["target_date"] <= pd.Timestamp("2018-06-01")).all()


# ---------------------------------------------------------- purged folds
def test_no_training_label_is_fixed_inside_the_fold_it_is_scored_on(training_rows):
    origins = training_rows["friday"].values
    targets = training_rows["target_date"].values
    folds = rb.purged_folds(origins, targets)
    assert len(folds) == rb.CV_FOLDS
    for tr, te in folds:
        assert len(tr) > 0 and len(te) > 0
        assert targets[tr].max() < origins[te[0]]
        assert origins[tr].max() < origins[te[0]]


def test_plain_time_series_split_would_leak_on_this_data(training_rows):
    """The purge has to be doing work: without it, training labels from the
    last few weeks of each training block are fixed inside the scored fold."""
    origins = training_rows["friday"].values
    targets = training_rows["target_date"].values
    for tr, te in TimeSeriesSplit(rb.CV_FOLDS).split(origins):
        assert targets[tr].max() >= origins[te[0]]


def test_purge_removes_only_the_overlapping_rows(training_rows):
    origins = training_rows["friday"].values
    targets = training_rows["target_date"].values
    for (kept, te), (full, _) in zip(rb.purged_folds(origins, targets),
                                     TimeSeriesSplit(rb.CV_FOLDS).split(origins)):
        dropped = np.setdiff1d(full, kept)
        assert 0 < len(dropped) <= rb.H
        assert (targets[dropped] >= origins[te[0]]).all()


# ------------------------------------------------------------------ scaler
def test_scaler_is_fitted_on_each_folds_training_rows_only(training_rows):
    X = training_rows[rb.FEATS_FULL].to_numpy(float)
    y = training_rows["y"].to_numpy()
    folds = rb.purged_folds(training_rows["friday"].values,
                            training_rows["target_date"].values)
    fitted = []

    def make():
        m = rb.ridge_model(1.0, True)
        fitted.append(m)
        return m

    rb.cv_mse(make, X, y, folds)
    assert len(fitted) == len(folds)
    for m, (tr, te) in zip(fitted, folds):
        scaler = m.named_steps["standardscaler"]
        assert np.allclose(scaler.mean_, X[tr].mean(axis=0), atol=1e-12)
        assert np.allclose(scaler.scale_, X[tr].std(axis=0), atol=1e-12)
        assert not np.allclose(scaler.mean_, X.mean(axis=0), atol=1e-12)


# ------------------------------------------------------ validation boundary
def test_validation_era_ends_before_the_first_judged_target(built):
    log = built.set_index("friday")[["target_date"]]
    v = rb.validation_era(log)
    assert v["target_date"].max() < pd.Timestamp(rb.EVAL_START)
    assert v.index.max() == pd.Timestamp(rb.VAL_END)


def test_validation_boundary_assertion_fires_when_the_era_runs_too_late(
        built, monkeypatch):
    """The last origin of 2020-12-25 has a target on 2021-01-22."""
    monkeypatch.setattr(rb, "VAL_END", "2020-12-25")
    with pytest.raises(AssertionError, match="judged era"):
        rb.validation_era(built.set_index("friday")[["target_date"]])


# ---------------------------------------------------------- combination
def synthetic_log(n=80, seed=7):
    rng = np.random.default_rng(seed)
    spot = 15 + np.cumsum(rng.normal(0, 0.1, n))
    realized = np.r_[spot[4:], spot[-1] + rng.normal(0, 0.1, 4)]
    log = pd.DataFrame({
        "RW": spot,
        "CARRY": spot * 1.002,
        "R": spot + rng.normal(0, 0.15, n),
        "realized": realized,
        "target_date": FRIDAYS[:n] + pd.Timedelta(days=28)}, index=FRIDAYS[:n])
    return log


def weights_at(log, t):
    return rb.combo_series(log, "R", 0.97, 2.0)[1].loc[t].values


def test_errors_not_yet_resolved_cannot_move_the_weights():
    log = synthetic_log()
    t = FRIDAYS[60]
    clean = weights_at(log, t)
    pending = log.index[(log["target_date"] > t) & (log.index < t)]
    assert len(pending) == 3
    garbled = log.copy()
    garbled.loc[pending, "realized"] *= 3.0
    assert np.array_equal(weights_at(garbled, t), clean)


def test_an_error_resolved_exactly_on_the_origin_does_set_the_weights():
    log = synthetic_log()
    t = FRIDAYS[60]
    just_resolved = t - pd.Timedelta(days=28)
    assert log.loc[just_resolved, "target_date"] == t
    garbled = log.copy()
    garbled.loc[just_resolved, "realized"] *= 3.0
    assert not np.allclose(weights_at(garbled, t), weights_at(log, t))


def test_weights_stay_equal_until_26_errors_have_resolved():
    log = synthetic_log()
    w = rb.combo_series(log, "R", 0.97, 2.0)[1]
    n_resolved = [(log["target_date"] <= t).sum() for t in log.index]
    early = [n < 26 for n in n_resolved]
    assert early.count(True) > 20 and early.count(False) > 20
    assert np.allclose(w[early], 1 / 3)
    assert not np.allclose(w[[not e for e in early]].iloc[-1], 1 / 3)
