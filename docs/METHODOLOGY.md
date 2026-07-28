# Methodology and findings

A complete walkthrough of the project: what the problem is, why it is hard, how
the data was assembled, how each model works, how the out-of-sample protocol was
enforced, what the results were, and what I would and would not claim from them.

The short version lives in the [README](../README.md). The interactive version
is [`notebooks/walkthrough.ipynb`](../notebooks/walkthrough.ipynb). This document
is the reference: it is the one to read if you want to check the reasoning rather
than the headline.

**Contents**

1. [The task](#1-the-task)
2. [Why this problem is hard](#2-why-this-problem-is-hard)
3. [Data](#3-data)
4. [The out-of-sample protocol](#4-the-out-of-sample-protocol)
5. [The models](#5-the-models)
6. [The forecast combination](#6-the-forecast-combination)
7. [Choosing the configuration without cheating](#7-choosing-the-configuration-without-cheating)
8. [Results](#8-results)
9. [Why the benchmark loses](#9-why-the-benchmark-loses)
10. [Statistical inference and power](#10-statistical-inference-and-power)
11. [Robustness](#11-robustness)
12. [What went wrong, and what I fixed](#12-what-went-wrong-and-what-i-fixed)
13. [Limitations and what I would do next](#13-limitations-and-what-i-would-do-next)
14. [Reproducing everything](#14-reproducing-everything)
15. [References](#15-references)

---

## 1. The task

Produce a **one-month-ahead forecast of USDZAR every Friday** from 1 January 2021
to 31 December 2025, out of sample, scored on RMSE against an AR(1) benchmark.

The target series is **EXCX135**, the South African Reserve Bank's rand-per-dollar
rate, distributed through EconData. Every Friday `t` is a forecast origin; the
target is the fixing on `t + 28 days`. That gives **261 forecasts**, all logged in
[`data/processed/forecast_log.csv`](../data/processed/forecast_log.csv) with the
origin date, target date, prevailing spot, each model's forecast and the realised
outcome. Every number in this document can be recomputed from that one file.

The brief is in [`docs/original_task_brief.pdf`](original_task_brief.pdf).

---

## 2. Why this problem is hard

Meese and Rogoff (1983) ran the definitive test: they took the standard
structural exchange-rate models, gave them the **actual future values** of their
own driving variables, and still found they lost to a naive no-change forecast
out of sample. Handing a model the future and watching it lose anyway is a
strong result, and Rossi's (2013) survey found that thirty years of subsequent
work had not overturned it in any robust way.

The mechanism is not mysterious. USDZAR is priced continuously by a deep, liquid
market. Anything publicly knowable about South African fundamentals is in the
price within minutes of becoming knowable. What remains to be forecast one month
out is a small residual driven by information that does not yet exist.

Two things follow, and they shaped every decision in this project:

**First, the honest bar is low.** Published improvements over naive benchmarks in
this literature run at roughly **1 to 5 percent in RMSE**, and they come from
shrinkage, combination and disciplined validation rather than from richer models.
The M4 and M5 forecasting competitions found the same thing across thousands of
unrelated series: simple combinations of simple methods win, and complexity is
usually a tax.

**Second, a large result is a red flag.** If a backtest on a liquid FX pair
reports a 20 percent RMSE improvement, the overwhelmingly likely explanation is
that future information leaked into the forecast, not that a genuine edge was
found. That is why most of the engineering effort here went into making leakage
structurally impossible and then writing tests that fail loudly if it ever
appears, rather than into model complexity.

---

## 3. Data

### The target

**EXCX135**, from the official EconData export (`MARKET_RATES 1.0.0`,
`EXCX135.B.A`). The free API tier returns only about six months of history, so
the full series back to 1970 was taken from the EconData web export.

Because that export was manual, it is verified programmatically. `verify_provenance.py`
pulls the same series independently from the SARB Web API and compares:

```
overlapping observations   9,141
maximum absolute difference  0.000000
```

This runs as part of the pipeline and again as a test
(`test_data_provenance_two_independent_sources_agree`). A hand-downloaded file is
a weak link in any analysis; this turns it into a checkable claim.

### The predictors

| Series | Source | Economic role |
|---|---|---|
| JIBAR 3M minus US 3M T-bill | SARB Web API, FRED `DTB3` | The carry signal. Covered interest parity says the forward rate embeds this gap. |
| Gold, platinum | SARB, NYMEX | South Africa is a major exporter of both. Higher prices, stronger rand. |
| Brent crude | FRED | South Africa imports oil. Higher prices, weaker rand. |
| Broad US dollar index | FRED `DTWEXBGS` | Much of what looks like rand movement is dollar movement against everything. |
| VIX | FRED `VIXCLS` | Global risk appetite. The rand is one of the most liquid EM currencies and so is used as a risk proxy. |

### The constraint that matters most

**Every predictor is a daily market price or rate.** No CPI, no current account,
no GDP, no unemployment.

That was deliberate and it cost something. Macro fundamentals have a genuine
claim on a rand model. But they are published with a lag of weeks to months, and
then revised for years afterwards. A backtest that uses today's published history
of CPI inside a simulated forecast made in March 2021 is using numbers that did
not exist in March 2021, and often did not exist in that form until 2023.

Market prices are known the instant they print and are never revised. Restricting
the information set to them makes look-ahead bias **impossible by construction**
rather than merely avoided by careful coding. I would rather defend a smaller
model that cannot cheat than a larger one that might.

---

## 4. The out-of-sample protocol

This is the part of the project I would most want a reviewer to check, because
it is where forecasting results usually go wrong. Five guarantees, each enforced
in code and then again in a test.

**1. Information sets are backward-looking by construction.** Every predictor
joins the weekly grid through a backward `merge_asof`, so a forecast made on
Friday `t` can only see observations dated on or before `t`. Never after.

**2. No publication lags.** Market data only, as argued in section 3.

**3. Resolved-only training.** The regressions train only on origins whose
28-day outcome had already happened by the time of the forecast:

```python
tr = tr[tr.index <= i - H]      # H = 4 weeks
```

Without this line the model at origin `i` would be fitted partly on the outcome
of forecasts that had not yet resolved. It is a one-line difference and it is the
single most common leak in walk-forward backtests.

**4. Embargoed combination weights.** The weights that blend the component models
come from their past errors. Those errors are only usable once the forecast has
resolved, so the weight applied at origin `i` uses errors from origins up to
`i − 28 days` only.

**5. Frozen configuration.** Covered in section 7. This is the subtle one.

### These are tests, not prose

`tests/test_no_lookahead.py` runs 14 checks, including:

- `test_spot_equals_the_last_fixing_on_or_before_the_origin` — re-parses the raw
  EconData CSV independently of the pipeline and confirms, for all 261 origins,
  that the spot used was the last fixing on or before that Friday. If any
  forecast ever used tomorrow's price, this fails.
- `test_random_walk_forecast_is_exactly_the_origin_spot` — a definitional check.
  If the random walk ever differs from spot, the information set was built wrongly
  upstream and everything downstream is suspect.
- `test_combination_is_a_convex_combination_of_its_members` — weights sum to one,
  are non-negative, and reproduce the combination forecast exactly.
- `test_combination_forecast_lies_within_the_span_of_its_members` — a convex
  combination cannot be more extreme than its most extreme member. Catches a
  whole class of weighting bugs.
- `test_metrics_can_be_recomputed_from_the_log` — the published RMSE and MAE for
  every model recompute from the forecast log to 1e-9.

```bash
pytest -q          # 14 passed
```

---

## 5. The models

### AR(1), the benchmark

OLS with intercept on the weekly log level, expanding window from 1999, iterated
four steps forward:

$$y_t = c + \phi\, y_{t-1} + \varepsilon_t, \qquad y_t = \log S_t$$

$$\hat y_{t+4} = c\,(1 + \phi + \phi^2 + \phi^3) + \phi^4 y_t$$

Both a log and a level variant were run, and results are reported against
whichever scores better, so the comparison is never against a deliberately
weakened benchmark. The log variant wins (RMSE 0.5624 against 0.5629).

### Random walk

$\hat S_{t+28d} = S_t$. No parameters, nothing to estimate. At this horizon it is
the strongest single benchmark, and the literature in section 2 is essentially
the story of models failing to beat it.

### Carry

The covered-interest-parity forward rate:

$$\hat S_{t+28d} = S_t \left( 1 + \left(i^{ZA}_t - i^{US}_t\right)\frac{28}{365} \right)$$

With the South African policy rate well above the US rate, this tilts the
forecast slightly upward (weaker rand). It is the theoretically correct
no-arbitrage prediction, so it is a useful component even though it is a poor
standalone predictor.

### Ridge

Predicts the **4-week log return**, not the level, using the compact predictor
set. Standardised within each training window, penalty chosen by time-ordered
cross-validation, and — importantly — **no intercept**.

That last choice deserves an explanation, because it is what makes the model safe.
Under a heavy penalty every coefficient shrinks toward zero, so the predicted
return goes to zero, so the forecast becomes $S_t \cdot e^0 = S_t$. **A ridge
that finds no signal collapses into the random walk.** With an intercept it would
instead collapse toward the average historical return, which is a slow drift in a
direction that has no reason to persist. The failure mode of the no-intercept
version is harmless; the failure mode of the other version is exactly the bias
that sinks the AR(1) (section 9).

### Gradient boosting

`HistGradientBoostingRegressor`, depth 2, under identical discipline: same
features, same resolved-only training, same walk-forward loop. It is included as
a **deliberate control**, not as a candidate.

The point is to measure what flexibility costs in a low signal-to-noise setting.
It lost by 7.5 percent, and that is the one difference in the entire results table
that reaches statistical significance. Reporting it is more informative than
quietly dropping it, and it is direct evidence for the design choices everywhere
else.

---

## 6. The forecast combination

The submitted model is an inverse discounted-MSE weighted average of
{random walk, carry, ridge}.

At each origin, for each component model $m$, compute a discounted mean squared
error over the last 156 resolved origins:

$$\text{DMSE}_m = \frac{\sum_{k} \delta^{k}\, e_{m,k}^2}{\sum_{k} \delta^{k}},
\qquad \delta = 0.97$$

where $k$ indexes backwards from the most recent **resolved** origin, so recent
performance counts more. Then weight inversely, with a sharpness parameter:

$$w_m = \frac{\left(1/\text{DMSE}_m\right)^{\theta}}{\sum_j \left(1/\text{DMSE}_j\right)^{\theta}},
\qquad \theta = 2$$

$\theta = 1$ gives plain inverse-error weighting; larger $\theta$ concentrates
weight on recent winners. The weights are non-negative and sum to one by
construction, which is not just tidiness: it bounds the combination inside the
range of its members, so a single component behaving badly cannot produce a wild
forecast. That property is asserted as a test.

**Why combine at all?** Forecast combination is one of the most reliably
replicated results in the whole forecasting literature (Bates and Granger 1969
onwards, and both the M4 and M5 competitions). Component models make partly
independent errors; averaging cancels some of that error variance without
requiring any component to be individually good. It is variance reduction, not
insight, and it is the closest thing to a free lunch this problem offers.

In practice the weights sat close to equal. At the worked example in section 8
they were 0.333 / 0.337 / 0.331. That is itself informative: the three components
have very similar recent accuracy, which is what you would expect when all three
are anchored near spot.

---

## 7. Choosing the configuration without cheating

There are choices to make: which ridge feature set, what decay $\delta$, what
sharpness $\theta$. Tuning them on the evaluation window and reporting the best
result would be a subtle but serious form of cheating. The reported number would
be partly a measure of how many configurations were tried, and it would not
repeat out of sample.

So the search ran on a **separate validation era: 2015 to 2020**, chosen so that
every target date resolves before 1 January 2021. Then the winning configuration
was **frozen** and applied to the judged window untouched.

The full grid is committed in
[`data/processed/validation_metrics.json`](../data/processed/validation_metrics.json).
The top five configurations were:

| Ridge variant | δ | θ | Validation RMSE |
|---|---|---|---|
| `RIDGE_c0` | 0.97 | 2.0 | 0.65693 |
| `RIDGE_c0` | 0.99 | 2.0 | 0.65700 |
| `RIDGE_c0` | 0.97 | 1.0 | 0.65701 |
| `RIDGE_f0` | 0.97 | 2.0 | 0.65702 |
| `RIDGE_c0` | 1.00 | 2.0 | 0.65703 |

Note how flat that surface is: the gap between best and fifth-best is 0.0001, or
0.015 percent. **The configuration barely matters.** This is worth stating plainly
because it cuts both ways. It means the result is not an artefact of a lucky
hyperparameter, which is reassuring. It also means there was never much to be won
by tuning, which is consistent with everything in section 2.

Committing the grid rather than only the winner is deliberate. It lets a reviewer
see how many configurations were tried, which is the information needed to judge
whether the headline number has been selection-mined.

---

## 8. Results

All 261 origins, 1 January 2021 to 26 December 2025.

| Model | RMSE | MAE | vs AR(1) | DM p-value vs AR(1) |
|---|---|---|---|---|
| AR(1) benchmark | 0.5624 | 0.4478 | — | — |
| Random walk | 0.5600 | 0.4480 | **+0.43%** | 0.218 |
| **Combination** | **0.5600** | 0.4496 | **+0.42%** | 0.469 |
| Ridge | 0.5605 | 0.4482 | +0.34% | 0.334 |
| Carry | 0.5606 | 0.4540 | +0.31% | 0.768 |
| Gradient boosting | 0.6046 | 0.4919 | **−7.51%** | 0.042 |

Four of five models beat the benchmark. Boosting, under identical rules, loses
badly.

### By year

| Year | AR(1) | Combination | Winner |
|---|---|---|---|
| 2021 | 0.5118 | 0.5102 | Combination |
| 2022 | 0.6985 | 0.6904 | Combination |
| 2023 | 0.6553 | 0.6476 | Combination |
| 2024 | 0.4456 | 0.4455 | Combination (barely) |
| 2025 | 0.4523 | 0.4630 | **AR(1)** |

2025 is the honest counterexample and it is reported rather than buried. When the
rand strengthened back toward the AR(1)'s implied mean, the benchmark's bias
became an advantage. Section 9 explains why that is exactly what should happen.

### One forecast, fully worked

Abstractions are easy to hide behind, so here is a single origin with every
number. Friday **3 June 2022**, spot R15.4117, target 1 July 2022, actual
**R16.3482**.

| Model | Forecast | Error |
|---|---|---|
| Gradient boosting | 15.4671 | −0.8811 |
| Carry | 15.4557 | −0.8925 |
| **Combination** | **15.4256** | **−0.9226** |
| Ridge | 15.4089 | −0.9393 |
| Random walk | 15.4117 | −0.9365 |
| AR(1) | 15.3861 | **−0.9621** |

Combination check: `0.333 × 15.4117 + 0.337 × 15.4557 + 0.331 × 15.4089 = 15.4256`.

Two things to take from this. **The AR(1) has the largest error of the six**,
because its implied long-run mean that day was R13.01 and that pull dragged the
forecast down at exactly the moment the rand was rising. And **every forecast sits
within eight cents of every other** (15.386 to 15.467) against an actual move of
94 cents. At a one-month horizon no defensible model strays far from the current
price. The competition is fought inside those few cents, which is why 0.42 percent
is a real result and why a claimed 20 percent should invite scepticism.

---

## 9. Why the benchmark loses

This is the core finding, and the reason the project is more than a leaderboard
entry.

An AR(1) has persistence $\phi$. Fitted on USDZAR it estimates between **0.9971
and 0.9986** across the 261 origins: very close to one, but below it. Any
$\phi < 1$ implies mean reversion toward

$$\mu = \frac{c}{1 - \phi}$$

and every forecast is pulled toward that $\mu$. So the question is: where did
$\mu$ sit relative to the market?

Refitting the AR(1) at all 261 origins and recomputing $\mu$ each time:

| | |
|---|---|
| $\mu$ below the prevailing spot rate | **261 of 261 origins** |
| Average gap | **R2.11** |
| Smallest gap | R0.57 |
| Range of $\mu$ | R11.80 to R19.18 |
| Actual spot over the window | R14.62, peaking at R19.74 |

**At every single origin the benchmark leaned below the market.** Meanwhile the
rand was in a multi-year depreciation. A mean-reverting model applied to a
trending series pulls every forecast the wrong way, and because RMSE squares
errors, the occasional large miss that produces dominates the score.

That is the entire result in one sentence. **The models here do not predict the
rand better in any deep sense. They decline to make one specific, repeated,
identifiable mistake.**

It also predicts precisely when the edge should vanish: whenever the rand moves
*toward* $\mu$ rather than away from it, the bias helps the benchmark. That is
2025, and it is why the honest framing is a structural explanation with a known
failure condition, not a claim of forecasting skill.

See [`figures/forecasts_vs_actual.png`](../figures/forecasts_vs_actual.png) and the
notebook's section 5 chart.

---

## 10. Statistical inference and power

### The Diebold-Mariano test

Forecast errors from overlapping 4-week windows are serially correlated by
construction: consecutive origins share most of their forecast period. Ignoring
that inflates test statistics. Every DM test here uses a **Newey-West long-run
variance with a Bartlett kernel at lag $h - 1 = 3$**.

Full pairwise matrix (negative statistic favours the row model, `*` = significant
at 5 percent):

| | AR(1) | RW | Carry | Ridge | Boosting | Combo |
|---|---|---|---|---|---|---|
| **AR(1)** | . | −1.23 | −0.30 | −0.97 | 2.03\* | −0.72 |
| **RW** | 1.23 | . | 0.16 | 1.90 | 2.10\* | 0.02 |
| **Carry** | 0.30 | −0.16 | . | −0.04 | 2.00\* | −0.23 |
| **Ridge** | 0.97 | −1.90 | 0.04 | . | 2.08\* | −0.34 |
| **Boosting** | −2.03\* | −2.10\* | −2.00\* | −2.08\* | . | −2.08\* |
| **Combo** | 0.72 | −0.02 | 0.23 | 0.34 | 2.08\* | . |

The only significant differences anywhere in the table involve boosting, which is
significantly **worse** than all five other models. Nothing else separates.

### Power: what "not significant" actually means here

Our p-value is 0.47. Leaving it there would be lazy, because a non-significant
result is only interpretable if you know what the test could have detected.

Given the observed Newey-West standard deviation of the loss differential:

| | |
|---|---|
| Origins available | 261 |
| Observed RMSE improvement | **0.42%** |
| Minimum improvement detectable at 5% with 80% power | **1.64%** |
| Origins needed to detect an effect this size | **3,906** |
| Equivalent span of weekly forecasts | **~75 years** |

The observed effect is roughly **four times too small** to clear the detection
threshold with the sample available. Detecting it would require about 75 years of
weekly forecasts, which is longer than the floating-rate era.

So a non-significant result here is the **expected outcome given the sample**, not
evidence the model does nothing. Equally, it is not evidence the model does
something. The correct reading is that this experiment cannot resolve an effect
of this size, and any competitor claiming significance on 261 origins with a
sub-1-percent improvement is reporting something that does not follow from their
data.

This calculation is arguably the single most useful thing in the project. It
converts "we failed to reject" into a quantified statement about what the
experiment was capable of.

### Rolling accuracy

A single full-sample RMSE hides *when* an edge was earned. Over 210 complete
52-week rolling windows:

| | |
|---|---|
| Windows where the combination is ahead | **62.4%** |
| Best window ratio | 0.9801 |
| Worst window ratio | 1.0239 |

Ahead most of the time, by never more than 2 percent, and behind by up to 2.4
percent in the worst stretch. Thin and regime-dependent, which is consistent with
the mechanism in section 9 rather than with a stable edge.

---

## 11. Robustness

| Check | Result |
|---|---|
| Strict cut: only origins whose targets also fall inside the window | Combination 0.5621 vs AR(1) 0.5647, still ahead |
| Validation era 2015-2020 (never used for evaluation) | Combination 0.6569 vs AR(1) 0.6659, ahead |
| Benchmark variant | Reported against the better of AR(1)-log and AR(1)-level |
| Determinism | `data/processed` deleted and rebuilt from raw: max RMSE difference **2.22e-16** |
| Chart audit | `validate_results.py` re-derives every plotted number from raw data, 96 checks |

The determinism check matters more than it looks. Rebuilding from raw and landing
on the same numbers to machine precision means there is no hidden state, no cached
intermediate quietly carrying stale results, and no unseeded randomness.

---

## 12. What went wrong, and what I fixed

Including this section is a deliberate choice. Every project has these; most
write-ups omit them, which makes the write-up less trustworthy rather than more.

**1. A statistic I had misattributed.** The R13.01 figure was originally presented
as *the* AR(1)'s long-run mean. It is not: it is the estimate at the 3 June 2022
origin specifically. The value at the final origin is R14.90 with $\phi = 0.9980$.
Caught by an audit script written to re-derive every plotted number from raw data.
The fix replaced one convenient number with a stronger honest claim: the implied
mean sat below spot at **all 261 origins**, by R2.11 on average. The corrected
version is more persuasive than the error was.

**2. A quoted range that was wrong.** The 2022-23 spot range had been described as
"R14.60 to R19". The actual weekly range is R14.54 to R19.74. Same audit.

**3. A chart caption that overclaimed.** The cumulative error chart was captioned
as showing the edge "holds". It does not: it peaks at 1.29 and then gives back to
0.69. Rewritten to state the peak and the give-back explicitly.

**4. A bug in my own statistics module.** The rolling-accuracy share was computed
as `(ratio < 1).mean()` over a series whose first 51 entries were NaN while the
window filled. NaN comparisons are False, so those warm-up periods were silently
counted as losses and the reported share came out at 50.2 percent instead of the
correct **62.4 percent**. Found by cross-checking the notebook's independently
written calculation against the committed JSON and noticing they disagreed. This
is a good argument for computing an important number twice, in two places, by two
routes.

The pattern across all four: **an audit that re-derives numbers independently
catches things that reading your own code does not.** That is why
`validate_results.py` exists and why it re-reads the raw files rather than the
processed ones.

---

## 13. Limitations and what I would do next

### What I do not claim

- **Statistical significance.** Section 10.
- **Directional predictability.** Directional accuracy sits near 50 percent for
  every model. Nothing here predicts which way the rand moves.
- **Profitability.** Never tested. RMSE and trading P&L are different objectives
  and optimising one does not optimise the other.
- **Persistence.** 2025 goes the other way, for a reason the mechanism predicts.

### What I would do next, in order of expected value

**1. Option-implied volatility and risk reversals.** Greenwood-Nimmo, Steenkamp
and van Jaarsveld (SARB WP/22/14, "Can information on the distribution of ZAR
returns be used to improve SARB's ZAR forecasts?") find that distributional
information from the rand options market improves the SARB's own forecasts. Risk
reversals in particular price the market's skew, which carries information no
spot-based predictor has. This is the most promising unexplored input and it fits
the existing "market prices only" constraint exactly. Worth noting that Steenkamp
is CEO of Codera Analytics, who co-hosted this competition and distribute the
target series, so this is the host's own research on the host's own problem.

**2. Density forecasts rather than point forecasts.** For anyone actually using an
FX forecast — a treasurer deciding whether to hedge, a risk manager sizing a
position — the decision-relevant object is the distribution, not the point.
Forecasting the mean of a near-random-walk series is close to hopeless;
forecasting its dispersion is not, because volatility genuinely clusters. This is
where the real value is, and it is a better-posed problem.

**3. Bayesian model averaging over a wider component set.** Inverse-error weights
are a crude approximation to a posterior. BMA handles model uncertainty properly
and extends naturally to a larger pool of components.

**4. Horizon sensitivity.** Repeat the whole exercise at 1, 2, 8 and 12 weeks. The
AR(1)'s mean-reversion bias should bite harder as the horizon lengthens, because
$\phi^h$ pulls further. That is a testable prediction of the mechanism in section
9, and confirming it would turn an observation into an explanation.

---

## 14. Reproducing everything

```bash
git clone <repo-url> && cd <repo>
pip install -r requirements.txt

python src/run_all.py     # full pipeline, about four minutes
pytest -q                 # 14 leakage and integrity tests
```

No API keys. No paid data. The raw files are committed, so the pipeline runs
offline from `build_dataset.py` onwards.

`run_all.py` executes nine stages in order:

| Stage | Script | What it does |
|---|---|---|
| 1 | `fetch_data.py` | Download every raw series |
| 2 | `verify_provenance.py` | Check EconData against the SARB Web API |
| 3 | `build_dataset.py` | Build the weekly Friday dataset with backward as-of merges |
| 4 | `run_backtest.py` | Walk-forward out-of-sample backtest, all six models |
| 5 | `statistical_tests.py` | DM matrix, power analysis, rolling accuracy |
| 6 | `make_figures.py` | Report figures |
| 7 | `make_presentation_figures.py` | Presentation figures |
| 8 | `validate_results.py` | Audit every plotted number against the raw data |
| 9 | `make_report.py` | Build the technical report PDF |

Stage 4 caches its intermediate results keyed on a SHA-256 hash of the input data
plus the configuration, so a rerun with unchanged inputs is fast and a rerun with
changed inputs recomputes automatically. The cache is gitignored.

---

## 15. References

Bates, J. M. and Granger, C. W. J. (1969). "The combination of forecasts."
*Operational Research Quarterly* 20(4).

Diebold, F. X. and Mariano, R. S. (1995). "Comparing predictive accuracy."
*Journal of Business and Economic Statistics* 13(3).

Makridakis, S., Spiliotis, E. and Assimakopoulos, V. (2020). "The M4 Competition:
100,000 time series and 61 forecasting methods." *International Journal of
Forecasting* 36(1).

Meese, R. A. and Rogoff, K. (1983). "Empirical exchange rate models of the
seventies: Do they fit out of sample?" *Journal of International Economics* 14.

Newey, W. K. and West, K. D. (1987). "A simple, positive semi-definite,
heteroskedasticity and autocorrelation consistent covariance matrix."
*Econometrica* 55(3).

Rossi, B. (2013). "Exchange rate predictability." *Journal of Economic Literature*
51(4).

Greenwood-Nimmo, M., Steenkamp, D. and van Jaarsveld, R. (2022). "Can information
on the distribution of ZAR returns be used to improve SARB's ZAR forecasts?"
*SARB Working Paper* WP/22/14.
[PDF](https://www.resbank.co.za/content/dam/sarb/publications/working-papers/2022/WP%202214.pdf)

Data citation: SARB. *MARKET_RATES*. Version 1.0.0. Pretoria: SARB [producer].
Johannesburg: EconData [distributor], 2026.
