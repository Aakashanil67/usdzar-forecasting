"""
Future perturbation. Scramble every raw input dated after a forecast origin,
rebuild the dataset with build_dataset.build(), refit with
run_backtest.forecast_at(), and require the forecast at that origin to come
out the same. A forecast that depends on anything later than its origin,
whether through the features, the target, the training window, a CV fold or the
combination weights, changes here.
"""
import shutil

import numpy as np
import pandas as pd
import pytest
from threadpoolctl import threadpool_limits

import build_dataset as bd
import run_backtest as rb
from conftest import RAW

# warm-up, validation and judged eras
ORIGINS = ["2013-06-07", "2016-03-04", "2019-09-06", "2022-05-06", "2025-06-06"]
MODELS = ["AR1_log", "AR1_level", "RW", "CARRY", "RIDGE_f1", "RIDGE_f0",
          "RIDGE_c1", "RIDGE_c0", "GBM", "COMBO"]
FEATURES = rb.FEATS_FULL + ["spot", "jibar3m", "ustbill3m", "gold", "platinum",
                            "brent", "usd_broad", "vix"]


def scramble_after(origin: str, dest) -> None:
    """Copy data/raw to `dest`, multiplying every value dated after `origin` by
    a random factor. In the ALFRED vintage files a row also counts as future
    when it was first published after the origin, except the first vintage,
    which stands in for all earlier history (build_dataset's documented
    approximation for the years before ALFRED started)."""
    shutil.copytree(RAW, dest)
    cut, rng = pd.Timestamp(origin), np.random.default_rng(2024)
    for f in sorted(dest.rglob("*.csv")):
        df = pd.read_csv(f)
        if "date" in df.columns:
            future = pd.to_datetime(df["date"]) > cut
        elif "obs_date" in df.columns:
            rts = pd.to_datetime(df["realtime_start"])
            future = (pd.to_datetime(df["obs_date"]) > cut) | (
                (rts > cut) & (rts != rts.min()))
        else:
            continue
        df.loc[future, "value"] *= rng.uniform(0.5, 2.0, future.sum())
        df.to_csv(f, index=False)


@pytest.fixture(scope="module")
def forecasts(built, chosen, tmp_path_factory):
    """origin -> (weekly frame, forecasts) on the real data and on the data
    with everything after the origin scrambled."""
    out = {}
    # Every fit and CV fold still runs; a third of the GBM grid keeps the
    # forty-odd retunes inside the suite's time budget.
    with threadpool_limits(1), pytest.MonkeyPatch.context() as grid:
        grid.setattr(rb, "GBM_GRID", rb.GBM_GRID[::3])
        for origin in ORIGINS:
            raw = tmp_path_factory.mktemp("raw") / "raw"
            scramble_after(origin, raw)
            patch = pytest.MonkeyPatch()
            patch.setattr(bd, "RAW", raw)
            try:
                scrambled = bd.build()
            finally:
                patch.undo()
            out[origin] = (
                (built, rb.forecast_at(origin, built, *chosen)),
                (scrambled, rb.forecast_at(origin, scrambled, *chosen)))
    return out


@pytest.mark.parametrize("origin", ORIGINS)
def test_scrambling_the_future_changes_the_future_but_not_the_past(forecasts, origin):
    """Guards the perturbation itself: the scramble has to reach the targets
    after the origin, and nothing known at the origin may move."""
    (real, _), (scr, _) = forecasts[origin]
    t = pd.Timestamp(origin)
    past, future = real["friday"] <= t, real["friday"] > t + pd.Timedelta(days=60)
    assert not np.allclose(real.loc[future, "realized"].dropna(),
                           scr.loc[future, "realized"].dropna())
    for col in FEATURES:
        assert np.allclose(real.loc[past, col].to_numpy(float),
                           scr.loc[past, col].to_numpy(float),
                           rtol=0, atol=1e-12, equal_nan=True), col


@pytest.mark.parametrize("origin", ORIGINS)
def test_every_forecast_at_the_origin_ignores_later_raw_data(forecasts, origin):
    (_, base), (_, pert) = forecasts[origin]
    for m in MODELS:
        assert float(pert[m]) == pytest.approx(float(base[m]), abs=1e-12, rel=0), (
            f"{m} forecast issued {origin} moved when later data changed")
    assert base["RW"] == base["spot"]


def test_forecasts_differ_across_models_and_origins(forecasts):
    """If forecast_at returned one number for everything the test above would
    pass trivially."""
    at = pd.DataFrame({o: forecasts[o][0][1][MODELS].astype(float) for o in ORIGINS})
    assert (at.nunique(axis=1) == len(ORIGINS)).all()
    assert (at.T.nunique(axis=1) > 5).all()
