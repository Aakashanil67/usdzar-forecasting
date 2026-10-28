"""
The comparison code checked against outside references: Holm and the HAC
variance against statsmodels, and the AR(1) mean correction against simulation.
validate_results.py recomputes the same numbers with its own code, but a
formula it got wrong in the same way would pass there.
"""
import numpy as np
import pytest
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests

import run_backtest as rb
import statistical_tests as st


def test_holm_matches_statsmodels():
    p = np.random.default_rng(3).uniform(0, 0.2, 21)
    p[[4, 9]] = p[2]                                   # ties
    assert st.holm(p) == pytest.approx(multipletests(p, method="holm")[1], abs=1e-15)


@pytest.mark.parametrize("lag", [3, 8])
def test_newey_west_variance_matches_statsmodels_hac(lag):
    rng = np.random.default_rng(11)
    d = np.convolve(rng.normal(size=300), np.ones(4), "valid")   # MA(3), like h = 4
    fit = sm.OLS(d, np.ones(len(d))).fit(
        cov_type="HAC", cov_kwds=dict(maxlags=lag, use_correction=False))
    assert st.newey_west_var(d, lag) == pytest.approx(fit.bse[0] ** 2, rel=1e-12)


def test_mean_corrected_ar1_is_the_mean_of_simulated_outcomes():
    rng = np.random.default_rng(5)
    y = [np.log(15.0)]
    for _ in range(600):
        y.append(0.02 + 0.99 * y[-1] + rng.normal(0, 0.05))
    level = np.exp(y)
    c, phi, s2 = rb.ar1_fit(np.log(level))

    paths = np.full(1_000_000, np.log(level[-1]))
    for _ in range(4):
        paths = c + phi * paths + rng.normal(0, np.sqrt(s2), len(paths))
    simulated_mean = np.exp(paths).mean()

    assert rb.ar1_log_corrected(level, 4) == pytest.approx(simulated_mean, rel=5e-4)
    # the uncorrected median sits about v/2 = 0.5% below and must not pass
    assert np.exp(rb.ar1_forecast(np.log(level), 4)) != pytest.approx(
        simulated_mean, rel=2e-3)
