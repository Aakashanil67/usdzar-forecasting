"""
Checks on the saved judged-era forecast log: its shape, its agreement with the
raw target series, and the internal consistency of the combination and the
metrics. Leakage in the inputs and the fitting is tested in
test_dataset_timing.py, test_fitting.py and test_future_perturbation.py; the
audit script is tested in test_audit_exit.py.

Run:  pytest -q
"""
import json

import numpy as np
import pandas as pd
import pytest

from conftest import PROC, RAW

H_DAYS = 28
N_EXPECTED = 261
MODELS = ["AR1_log", "AR1_level", "RW", "CARRY", "RIDGE", "GBM", "COMBO"]


@pytest.fixture(scope="module")
def log():
    return pd.read_csv(PROC / "forecast_log.csv",
                       parse_dates=["origin", "target_date"])


@pytest.fixture(scope="module")
def weekly():
    return pd.read_csv(PROC / "weekly.csv",
                       parse_dates=["friday", "target_date"])


@pytest.fixture(scope="module")
def metrics():
    return json.load(open(PROC / "metrics.json"))


# --------------------------------------------------------------- structure
def test_every_origin_is_a_friday(log):
    assert set(log.origin.dt.dayofweek) == {4}


def test_horizon_is_exactly_28_days_everywhere(log):
    assert set((log.target_date - log.origin).dt.days) == {H_DAYS}


def test_expected_number_of_origins_in_judged_window(log):
    assert len(log) == N_EXPECTED
    assert str(log.origin.min().date()) == "2021-01-01"
    assert str(log.origin.max().date()) == "2025-12-26"


def test_no_missing_forecasts(log):
    assert log[MODELS + ["spot", "realized"]].notna().all().all()


# ------------------------------------------------------------- no leakage
def test_spot_equals_the_last_fixing_on_or_before_the_origin(log, spot):
    """Re-parses the raw export without pipeline code. If spot at an origin
    were a later fixing, this fails."""
    idx = spot["date"].values
    for _, r in log.iterrows():
        pos = np.searchsorted(idx, np.datetime64(r.origin), side="right") - 1
        assert pos >= 0
        assert spot["px"].iloc[pos] == pytest.approx(r.spot, abs=1e-9)
        assert spot["date"].iloc[pos] <= r.origin


def test_realized_equals_the_fixing_at_the_target_date(log, spot):
    idx = spot["date"].values
    for _, r in log.iterrows():
        pos = np.searchsorted(idx, np.datetime64(r.target_date),
                              side="right") - 1
        assert spot["px"].iloc[pos] == pytest.approx(r.realized, abs=1e-9)


def test_random_walk_forecast_is_exactly_the_origin_spot(log):
    """A definitional check: if RW ever differs from spot, the information set
    has been built wrongly somewhere upstream."""
    assert np.allclose(log["RW"], log["spot"], atol=0, rtol=0)


def test_weekly_spot_is_the_last_fixing_on_or_before_each_friday(weekly, spot):
    """Spot on the weekly grid must come from a fixing no later than the
    Friday it is attached to. Predictor timing is in test_dataset_timing.py."""
    idx = spot["date"].values
    sub = weekly.dropna(subset=["spot"]).tail(400)
    for _, r in sub.iterrows():
        pos = np.searchsorted(idx, np.datetime64(r.friday), side="right") - 1
        assert spot["date"].iloc[pos] <= r.friday
        assert spot["px"].iloc[pos] == pytest.approx(r.spot, abs=1e-9)


# ------------------------------------------------------------- consistency
def test_metrics_can_be_recomputed_from_the_log(log, metrics):
    for m in MODELS:
        e = log[m] - log["realized"]
        rmse = float(np.sqrt((e ** 2).mean()))
        mae = float(e.abs().mean())
        assert rmse == pytest.approx(metrics[m]["rmse"], abs=1e-9)
        assert mae == pytest.approx(metrics[m]["mae"], abs=1e-9)


def test_combination_is_a_convex_combination_of_its_members(log):
    """Weights must sum to one, be non-negative, and reproduce the forecast."""
    w = pd.read_csv(PROC / "combo_weights.csv", index_col=0, parse_dates=True)
    w = w.loc[w.index.isin(log["origin"])]
    j = log.set_index("origin").loc[w.index]
    assert np.allclose(w.sum(axis=1), 1.0, atol=1e-9)
    assert (w.values >= -1e-12).all()
    recon = (j["RW"] * w["RW"] + j["CARRY"] * w["CARRY"]
             + j["RIDGE"] * w["RIDGE"])
    assert np.allclose(recon, j["COMBO"], atol=1e-9)


def test_combination_forecast_lies_within_the_span_of_its_members(log):
    """A convex combination cannot be more extreme than its most extreme
    member. Catches a whole class of weighting bugs."""
    lo = log[["RW", "CARRY", "RIDGE"]].min(axis=1)
    hi = log[["RW", "CARRY", "RIDGE"]].max(axis=1)
    assert (log["COMBO"] >= lo - 1e-9).all()
    assert (log["COMBO"] <= hi + 1e-9).all()


def test_data_provenance_two_independent_sources_agree(spot):
    """EconData export against the SARB Web API pull."""
    api = pd.read_csv(RAW / "usdzar.csv", parse_dates=["date"]).rename(
        columns={"value": "api"})
    m = spot.merge(api, on="date")
    assert len(m) > 9000
    assert (m["px"] - m["api"]).abs().max() < 1e-9
