"""
Timing of the weekly dataset. Every number a forecast uses must have been
public at the Friday 17:00 Johannesburg issuance, and a value that was later
revised must enter as it stood on that day. These tests call build_dataset's
own functions on the committed raw files.
"""
import numpy as np
import pandas as pd
import pytest

import build_dataset as bd
from conftest import PROC

INPUTS = ["spot"] + bd.PREDICTORS


def utc(col: pd.Series) -> pd.Series:
    return pd.to_datetime(col, utc=True, format="ISO8601")


@pytest.mark.parametrize("name", INPUTS)
def test_value_is_public_before_the_issuance_that_uses_it(built, name):
    """Checked for every input, not only spot: a series stamped when it was
    observed instead of when it was published fails here."""
    avail = utc(built[f"{name}_available_at"])
    issued = utc(built["issued_at"])
    used = avail.notna()
    assert used.sum() > 800, f"{name} is missing for most of the sample"
    assert (avail[used] <= issued[used]).all()
    assert (built.loc[used, f"{name}_obs_date"] <= built.loc[used, "friday"]).all()


@pytest.mark.parametrize("name, days_before_friday", [
    ("ustbill3m", 2),    # H.15 posts the next business day: Wednesday at the latest
    ("vix", 1),          # Thursday's close
    ("usd_broad", 7),    # H.10 comes out Monday for the week before
    ("brent", 4),        # EIA's Wednesday release runs to the Monday before
])
def test_published_series_lag_their_observation_date(built, name, days_before_friday):
    """A Friday forecast must not see a same-day observation of a series that
    its publisher releases later. Bounds follow series_metadata.json."""
    sub = built[built["friday"] >= "2005-01-01"].dropna(subset=[f"{name}_obs_date"])
    lag = (sub["friday"] - sub[f"{name}_obs_date"]).dt.days
    assert lag.min() >= days_before_friday, (
        f"{name} used an observation {lag.min()} days old, "
        f"inside its {days_before_friday}-day publication lag")


def _revised_series():
    """One observation, released on Monday 2020-01-06 at 1.0 and revised to 2.0
    on 2020-01-14, as a realtime table."""
    avail = pd.to_datetime(["2020-01-06 22:00", "2020-01-14 22:00"], utc=True)
    return pd.DataFrame({"obs_date": pd.to_datetime(["2020-01-03"] * 2),
                         "value": [1.0, 2.0], "available_at": avail})


def issuance(*fridays: str) -> pd.Series:
    day = pd.Series(pd.to_datetime(list(fridays)))
    return (day + bd.ISSUE_TIME).dt.tz_localize(bd.ISSUE_TZ).dt.tz_convert("UTC")


def test_revision_published_after_issuance_is_not_used():
    obs, value, avail = bd.asof_weekly(_revised_series(), issuance("2020-01-10"))
    assert value[0] == 1.0
    assert avail[0] == pd.Timestamp("2020-01-06 22:00", tz="UTC")


def test_revision_is_used_once_it_has_been_published():
    obs, value, _ = bd.asof_weekly(_revised_series(), issuance("2020-01-17"))
    assert value[0] == 2.0
    assert obs[0] == pd.Timestamp("2020-01-03")


def test_observation_older_than_the_tolerance_is_missing_not_stale():
    obs, value, _ = bd.asof_weekly(_revised_series(), issuance("2020-02-14"))
    assert np.isnan(value[0]) and pd.isna(obs[0])


def test_four_week_lookback_returns_the_value_known_then_as_of_now():
    """The 'then' leg of a return is the observation that was newest four weeks
    earlier, valued as known at the later issuance."""
    rt = pd.DataFrame({
        "obs_date": pd.to_datetime(["2020-01-03", "2020-01-31"]),
        "value": [10.0, 20.0],
        "available_at": pd.to_datetime(["2020-01-03 10:00", "2020-01-31 10:00"],
                                       utc=True)})
    obs, value, _ = bd.asof_weekly(rt, issuance("2020-01-31"),
                                   lookback=pd.Timedelta(weeks=4))
    assert obs[0] == pd.Timestamp("2020-01-03") and value[0] == 10.0


def test_extra_lag_only_moves_predictors_further_back(built):
    late = bd.build(extra_lag_days=7)
    for name in bd.PREDICTORS:
        a, b = built[f"{name}_obs_date"], late[f"{name}_obs_date"]
        ok = a.notna() & b.notna()
        assert (b[ok] <= a[ok]).all() and (b[ok] < a[ok]).any(), name
        avail = utc(late[f"{name}_available_at"]).dropna()
        assert (avail <= utc(late.loc[avail.index, "issued_at"])).all(), name
    pd.testing.assert_series_equal(built["spot"], late["spot"])


def test_return_features_are_built_from_the_lagged_columns(built):
    """The unrevised series' four-week returns must equal log changes of their
    own weekly columns; the target must not appear in any feature."""
    for src, out in [("gold", "ret4_gold"), ("platinum", "ret4_plat")]:
        expect = np.log(built[src]) - np.log(built[src].shift(4))
        both = expect.notna() & built[out].notna()
        assert both.sum() > 1000
        assert np.allclose(built.loc[both, out], expect[both], atol=1e-12, rtol=0)
    carry = (built["jibar3m"] - built["ustbill3m"]) / 100.0
    ok = carry.notna()
    assert np.allclose(built.loc[ok, "carry_diff"], carry[ok], atol=1e-15, rtol=0)
    feats = ["carry_diff", "d_carry_4w", "ret4_gold", "ret4_plat", "ret4_brent",
             "ret4_usd", "vix_z", "d_vix_4w", "ret4_spot", "ret12_spot", "ma_gap"]
    for f in feats:
        both = built[[f, "y"]].dropna()
        assert not np.allclose(both[f], both["y"]), f"{f} is the target"


def test_saved_weekly_file_is_what_build_produces(built):
    """A stale or hand-edited weekly.csv would let the other tests pass on the
    wrong data."""
    saved = pd.read_csv(PROC / "weekly.csv", parse_dates=["friday", "target_date"])
    cols = ["spot", "carry_diff", "d_carry_4w", "ret4_gold", "ret4_plat",
            "ret4_brent", "ret4_usd", "vix_z", "d_vix_4w", "ret4_spot",
            "ret12_spot", "ma_gap", "y", "realized"]
    for c in cols:
        assert np.allclose(saved[c].to_numpy(float), built[c].to_numpy(float),
                           rtol=1e-12, atol=1e-12, equal_nan=True), c
