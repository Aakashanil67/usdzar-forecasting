# Methodology and findings

The full write-up: what the problem is, why it is hard, how the data was
assembled, how each model works, how the out-of-sample protocol was enforced, what
the results were, and what I would and would not claim from them.

The short version is in the [README](../README.md). The interactive version is
[`notebooks/walkthrough.ipynb`](../notebooks/walkthrough.ipynb). This document is
the reference, the one to read if you want to check the reasoning rather than the
headline.

As in the README, "we" refers to the competition entry and "I" to the work added
afterwards.

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

Produce a one-month-ahead forecast of USDZAR every Friday from 1 January 2021 to
31 December 2025, out of sample, scored on RMSE against an AR(1) benchmark.

The target series is EXCX135, the South African Reserve Bank's rand-per-dollar
rate, distributed through EconData. Every Friday `t` is a forecast origin and the
target is the fixing on `t + 28 days`, which gives 261 forecasts. All of them are
in [`data/processed/forecast_log.csv`](../data/processed/forecast_log.csv) with the
origin date, target date, prevailing spot, each model's forecast and the realised
outcome. Every number in this document can be recomputed from that one file.

The brief is in [`docs/original_task_brief.pdf`](original_task_brief.pdf).

---

## 2. Why this problem is hard

Meese and Rogoff (1983) ran the test that settled the field for a generation. They
took the standard structural exchange-rate models, handed them the actual future
values of their own driving variables, and still found they lost to a naive
no-change forecast out of sample. Giving a model the future and watching it lose
anyway is a strong result, and Rossi's (2013) survey found that thirty years of
work had not overturned it in any robust way.

The mechanism is not mysterious. USDZAR is priced continuously by a deep, liquid
market, so anything publicly knowable about South African fundamentals is in the
price within minutes of becoming knowable. What is left to forecast a month out is
a small residual driven by information that does not yet exist.

Two things follow, and they shaped every decision here.

The first is that the honest bar is low. Published improvements over naive
benchmarks in this literature run at roughly 1 to 5 per cent in RMSE, and they come
from shrinkage, combination and disciplined validation rather than from richer
models. The M4 and M5 forecasting competitions found the same across thousands of
unrelated series: simple combinations of simple methods win, and complexity is
usually a tax.

The second is that a large result should worry you. If a backtest on a liquid FX
pair reports a 20 per cent RMSE improvement, the likely explanation is that future
information leaked into the forecast, not that a real edge was found. That is why
most of the engineering effort here went into making leakage structurally
impossible, and then writing tests that fail loudly if it appears anyway, rather
than into model complexity.

---

## 3. Data

### The target

EXCX135, from the official EconData export (`MARKET_RATES 1.0.0`, `EXCX135.B.A`).
The free API tier returns only about six months of history, so the full series back
to 1970 came from the EconData web export.

Because that export was manual, it gets verified in code. `verify_provenance.py`
pulls the same series independently from the SARB Web API and compares:

```
overlapping observations     9 141
maximum absolute difference  0.000000
```

This runs as part of the pipeline and again as a test
(`test_data_provenance_two_independent_sources_agree`). A hand-downloaded file is a
weak link in any analysis. This turns it into a claim someone can check.

### The predictors

| Series | Source | Economic role |
|---|---|---|
| JIBAR 3M minus US 3M T-bill | SARB Web API, FRED `DTB3` | The carry signal. Covered interest parity says the forward rate embeds this gap. |
| Gold, platinum | SARB, NYMEX | South Africa exports both in quantity. Higher prices, stronger rand. |
| Brent crude | FRED `DCOILBRENTEU` (EIA) | South Africa imports oil. Higher prices, weaker rand. |
| Broad US dollar index | FRED `DTWEXBGS` | Much of what looks like rand movement is dollar movement against everything. |
| VIX | FRED `VIXCLS` | Global risk appetite. The rand is one of the most liquid EM currencies, so it gets traded as a risk proxy. |

### When each series is known

A forecast is issued at 17:00 Johannesburg time each Friday. That is after the
SARB's 10:30 rand rate and the morning JIBAR fix, and before any US market closes
that day. A value is used only if it was public by then. Each release rule below
comes from the publisher's own schedule; `data/raw/series_metadata.json` holds the
rule, the source URL and the reasoning for every series.

| Series | Public at | Newest value a Friday forecast sees |
|---|---|---|
| USDZAR `EXCX135D` | 10:30 Johannesburg, same day | Friday |
| JIBAR 3M | 11:00 Johannesburg, same day (10:00 since October 2012) | Friday |
| Gold, mean of the London a.m. and p.m. fixes | 15:30 London, 30 minutes after the p.m. auction starts | Friday in UK summer, Thursday in UK winter |
| Platinum `PL=F` | 17:00 New York, end of the CME day | Thursday |
| US 3M T-bill `DTB3` | H.15, 16:15 New York the next business day | Wednesday |
| VIX | Cboe close, 16:15 New York | Thursday |
| Broad dollar index `DTWEXBGS` | H.10, 16:15 New York the Monday after the week | Previous Friday |
| Brent `DCOILBRENTEU` | EIA weekly update on Wednesday | Monday |

Market fixings that a trader could watch as they happened (the SARB rate, the gold
fix, platinum) are stamped at the time they were struck. Published rates and
indices are stamped when they were published. Where the schedule leaves room, the
rule takes the later reading: the platinum close is taken at the end of the CME
day rather than at the 13:05 settlement, and Brent is treated as arriving only up
to the Monday before each Wednesday update, because that is what FRED actually
received. The gold rule is the one I am least sure of: the 30 minutes is my
allowance for the auction, not a published time.

Four of the series are revised. The broad dollar index is revised every time its
trade weights are, which touches every observation. Brent, the T-bill rate and
the VIX have had 23, 35 and 11 observations revised. For these the value used is
the one ALFRED, the St. Louis Fed's vintage archive, showed at the time
(`data/raw/vintages/`), and a four-week return takes both ends from that same
vintage, so a revision cannot pass itself off as a price move. ALFRED's history
starts in 2019 for the dollar index, 2011 for Brent, 2010 for the VIX and 2005 for
the T-bill. Before those dates the earliest vintage stands in for what was known.
That is an approximation. For the dollar index it matters most, because the index
was redefined in 2019 and the pre-2019 versions are not in ALFRED.

### The constraint that matters most

Every predictor is a daily market price or rate. No CPI, no current account, no
GDP, no unemployment.

That was deliberate and it cost us something. Macro fundamentals have a real claim
on a rand model. But they are published weeks to months late and then revised for
years afterwards. A backtest that uses today's published history of CPI inside a
simulated forecast made in March 2021 is using numbers that did not exist in March
2021, and in some cases did not exist in that form until 2023.

Market data narrows the problem but does not remove it. The dollar index, Brent,
the T-bill rate and the VIX all reach the public hours to days after the fact, and
some are revised later, so the timing still has to be modelled. The previous
section sets out how.

---

## 4. The out-of-sample protocol

This is the part I would most want a reviewer to check, because it is where
forecasting results usually go wrong. Five guarantees, each enforced in code and
then again in a test.

**Information sets follow publication, not observation.** A predictor joins the
weekly grid only once it was public by the Friday 17:00 issuance time, with the
vintage then current where the series is revised (section 3). `weekly.csv` keeps,
for every input, the observation date used and the moment that value became
public, so the timing can be checked row by row. The audit confirms that every
value was public by its issuance time and matches the source file as it then stood.

**Timing sensitivity.** The release rules involve some judgement, so
`timing_sensitivity.py` reruns the whole backtest, selection included, with every
non-spot predictor a further week late. RMSE for each model under both timings is
in `data/processed/timing_sensitivity.json`.

**Resolved-only training.** The regressions train only on origins whose 28-day
outcome had already happened by the time of the forecast:

```python
tr = tr[tr.index <= i - H]      # H = 4 weeks
```

Without that line the model at origin `i` would be fitted partly on the outcome of
forecasts that had not yet resolved. One line of difference, and the most common
leak in walk-forward backtests.

**Embargoed combination weights.** The weights blending the component models come
from their past errors, and those errors are only usable once the forecast has
resolved. So the weight applied at origin `i` uses errors from origins up to
`i − 28 days` only.

**Frozen configuration.** Section 7 covers this one, which is the subtle one.

### These are tests, not prose

`tests/test_no_lookahead.py` runs fourteen checks. The ones that matter most:

`test_spot_equals_the_last_fixing_on_or_before_the_origin` re-parses the raw
EconData CSV independently of the pipeline and confirms, for all 261 origins, that
the spot used was the last fixing on or before that Friday. If any forecast ever
used tomorrow's price, this fails.

`test_random_walk_forecast_is_exactly_the_origin_spot` is definitional. If the
random walk ever differs from spot, the information set was built wrongly upstream
and everything downstream is suspect.

`test_combination_is_a_convex_combination_of_its_members` checks that weights sum
to one, are non-negative, and reproduce the combination forecast exactly.
`test_combination_forecast_lies_within_the_span_of_its_members` checks that a
convex combination is never more extreme than its most extreme member, which
catches a whole class of weighting bugs.

`test_metrics_can_be_recomputed_from_the_log` recomputes the published RMSE and MAE
for every model from the forecast log, to 1e-9.

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

We ran both a log and a level variant and report against whichever scores better,
so the comparison is never against a deliberately weakened benchmark. The log
variant wins, 0.5624 against 0.5629.

### Random walk

$\hat S_{t+28d} = S_t$. No parameters and nothing to estimate. At this horizon it
is the strongest single benchmark, and the literature in section 2 is largely the
story of models failing to beat it.

### Carry

The covered-interest-parity forward rate:

$$\hat S_{t+28d} = S_t \left( 1 + \left(i^{ZA}_t - i^{US}_t\right)\frac{28}{365} \right)$$

With the South African policy rate well above the US rate this tilts the forecast
slightly upward, meaning a weaker rand. It is the theoretically correct
no-arbitrage prediction, which makes it a useful component even though it is a poor
standalone predictor.

### Ridge

Predicts the 4-week log return rather than the level, using the compact predictor
set. Standardised within each training window, penalty chosen by time-ordered
cross-validation, and no intercept.

That last choice is what makes the model safe, so it is worth spelling out. Under a
heavy penalty every coefficient shrinks toward zero, the predicted return goes to
zero, and the forecast becomes $S_t \cdot e^0 = S_t$. A ridge that finds no signal
collapses into the random walk. With an intercept it would instead collapse toward
the average historical return, a slow drift in a direction with no reason to
persist. The failure mode of the version we used is harmless. The failure mode of
the other one is the exact bias that sinks the AR(1) in section 9.

### Gradient boosting

`HistGradientBoostingRegressor`, depth 2, under identical discipline: same
features, same resolved-only training, same walk-forward loop. It is a deliberate
control, not a candidate.

The point was to measure what flexibility costs in a low signal-to-noise setting.
It lost by 7.5 per cent, and that is the one difference in the entire results table
that reaches statistical significance. Reporting it tells a reader more than
quietly dropping it would, and it is direct evidence for the design choices
everywhere else.

---

## 6. The forecast combination

Our submitted model is an inverse discounted-MSE weighted average of {random walk,
carry, ridge}.

At each origin, for each component model $m$, compute a discounted mean squared
error over the last 156 resolved origins:

$$\text{DMSE}_m = \frac{\sum_{k} \delta^{k}\, e_{m,k}^2}{\sum_{k} \delta^{k}},
\qquad \delta = 0.97$$

where $k$ indexes backwards from the most recent resolved origin, so recent
performance counts more. Then weight inversely, with a sharpness parameter:

$$w_m = \frac{\left(1/\text{DMSE}_m\right)^{\theta}}{\sum_j \left(1/\text{DMSE}_j\right)^{\theta}},
\qquad \theta = 2$$

$\theta = 1$ gives plain inverse-error weighting and larger $\theta$ concentrates
weight on recent winners. The weights are non-negative and sum to one by
construction, which does real work: it bounds the combination inside the range of
its members, so one component behaving badly cannot produce a wild forecast. That
property is asserted as a test.

Why combine at all? Forecast combination is one of the most reliably replicated
results in the forecasting literature, from Bates and Granger (1969) through to
both the M4 and M5 competitions. Component models make partly independent errors
and averaging cancels some of that error variance, without requiring any component
to be individually good. It is variance reduction rather than insight, and it is
the closest thing to a free lunch this problem offers.

In practice the weights sat close to equal. At the worked example in section 8 they
were 0.333, 0.337 and 0.331, which is itself informative: the three components have
very similar recent accuracy, as you would expect when all three are anchored near
spot.

---

## 7. Choosing the configuration without cheating

There are choices to make. Which ridge feature set, what decay $\delta$, what
sharpness $\theta$. Tuning them on the evaluation window and reporting the best
result would be a subtle but serious form of cheating, because the reported number
would partly measure how many configurations were tried, and it would not repeat
out of sample.

So the search ran on a separate validation era, 2015 to 2020, chosen so that every
target date resolves before 1 January 2021. The winning configuration was then
frozen and applied to the judged window untouched.

The full grid is committed in
[`data/processed/validation_metrics.json`](../data/processed/validation_metrics.json).
The top five were:

| Ridge variant | δ | θ | Validation RMSE |
|---|---|---|---|
| `RIDGE_c0` | 0.97 | 2.0 | 0.65693 |
| `RIDGE_c0` | 0.99 | 2.0 | 0.65700 |
| `RIDGE_c0` | 0.97 | 1.0 | 0.65701 |
| `RIDGE_f0` | 0.97 | 2.0 | 0.65702 |
| `RIDGE_c0` | 1.00 | 2.0 | 0.65703 |

Look at how flat that surface is. The gap between best and fifth-best is 0.0001, or
0.015 per cent. The configuration barely matters, and that cuts both ways: the
result is not an artefact of a lucky hyperparameter, but there was never much to be
won by tuning either. Which is consistent with everything in section 2.

Committing the grid rather than only the winner is deliberate. It lets a reviewer
see how many configurations were tried, which is the information you need to judge
whether a headline number has been mined.

---

## 8. Results

All 261 origins, 1 January 2021 to 26 December 2025.

| Model | RMSE | MAE | vs AR(1) | DM p-value vs AR(1) |
|---|---|---|---|---|
| AR(1) benchmark | 0.5624 | 0.4478 | — | — |
| Random walk | 0.5600 | 0.4480 | +0.43% | 0.218 |
| Combination | 0.5600 | 0.4496 | +0.42% | 0.469 |
| Ridge | 0.5605 | 0.4482 | +0.34% | 0.334 |
| Carry | 0.5606 | 0.4540 | +0.31% | 0.768 |
| Gradient boosting | 0.6046 | 0.4919 | −7.51% | 0.042 |

Four of five models beat the benchmark. Boosting, under identical rules, loses
badly.

### By year

| Year | AR(1) | Combination | Winner |
|---|---|---|---|
| 2021 | 0.5118 | 0.5102 | Combination |
| 2022 | 0.6985 | 0.6904 | Combination |
| 2023 | 0.6553 | 0.6476 | Combination |
| 2024 | 0.4456 | 0.4455 | Combination, barely |
| 2025 | 0.4523 | 0.4630 | AR(1) |

2025 is the honest counterexample, and it is reported rather than buried. When the
rand strengthened back toward the AR(1)'s implied mean, the benchmark's bias turned
into an advantage. Section 9 explains why that is exactly what should happen.

### One forecast, fully worked

Friday 3 June 2022. Spot R15.4117, target 1 July 2022, actual R16.3482.

| Model | Forecast | Error |
|---|---|---|
| Gradient boosting | 15.4671 | −0.8811 |
| Carry | 15.4557 | −0.8925 |
| Combination | 15.4256 | −0.9226 |
| Random walk | 15.4117 | −0.9365 |
| Ridge | 15.4089 | −0.9393 |
| AR(1) | 15.3861 | −0.9621 |

Combination check: `0.333 × 15.4117 + 0.337 × 15.4557 + 0.331 × 15.4089 = 15.4256`.

Two things to take from this. The AR(1) has the largest error of the six, because
its implied long-run mean that day was R13.01 and that pull dragged the forecast
down at exactly the moment the rand was rising.

And every forecast sits within eight cents of every other, 15.386 to 15.467,
against an actual move of 94 cents. At a one-month horizon no defensible model
strays far from the current price. The competition is fought inside those few
cents, which is why 0.42 per cent is a real result and why a claimed 20 per cent
should invite scepticism.

---

## 9. Why the benchmark loses

This is the core finding, and the reason the project is more than a leaderboard
entry.

An AR(1) has persistence $\phi$. Fitted on USDZAR it estimates between 0.9971 and
0.9986 across the 261 origins, very close to one but below it. Any $\phi < 1$
implies mean reversion toward

$$\mu = \frac{c}{1 - \phi}$$

and every forecast is pulled that way. So the question is where $\mu$ sat relative
to the market.

Refitting the AR(1) at all 261 origins and recomputing $\mu$ each time:

| | |
|---|---|
| $\mu$ below the prevailing spot rate | 261 of 261 origins |
| Average gap | R2.11 |
| Smallest gap | R0.57 |
| Range of $\mu$ | R11.80 to R19.18 |
| Actual spot over the window | R14.62, peaking at R19.74 |

At every single origin the benchmark leaned below the market, while the rand was in
a multi-year depreciation. A mean-reverting model applied to a trending series
pulls every forecast the wrong way, and because RMSE squares errors, the occasional
large miss that produces dominates the score.

That is the whole result in one sentence. Our models do not predict the rand better
in any deep sense. They decline to make one specific, repeated, identifiable
mistake.

It also predicts precisely when the advantage should vanish. Whenever the rand
moves toward $\mu$ rather than away from it, the bias helps the benchmark. That is
2025, and it is why the honest framing here is a structural explanation with a
known failure condition rather than a claim of forecasting skill.

See [`figures/forecasts_vs_actual.png`](../figures/forecasts_vs_actual.png) and
section 5 of the notebook.

---

## 10. Statistical inference and power

### The Diebold-Mariano test

Forecast errors from overlapping 4-week windows are serially correlated by
construction, since consecutive origins share most of their forecast period.
Ignoring that inflates test statistics. Every DM test here uses a Newey-West
long-run variance with a Bartlett kernel at lag $h - 1 = 3$.

Full pairwise matrix. A negative statistic favours the row model, and `*` marks
significance at 5 per cent.

| | AR(1) | RW | Carry | Ridge | Boosting | Combo |
|---|---|---|---|---|---|---|
| **AR(1)** | . | −1.23 | −0.30 | −0.97 | 2.03\* | −0.72 |
| **RW** | 1.23 | . | 0.16 | 1.90 | 2.10\* | 0.02 |
| **Carry** | 0.30 | −0.16 | . | −0.04 | 2.00\* | −0.23 |
| **Ridge** | 0.97 | −1.90 | 0.04 | . | 2.08\* | −0.34 |
| **Boosting** | −2.03\* | −2.10\* | −2.00\* | −2.08\* | . | −2.08\* |
| **Combo** | 0.72 | −0.02 | 0.23 | 0.34 | 2.08\* | . |

The only significant differences anywhere involve boosting, which is significantly
worse than all five other models. Nothing else separates.

### Power, or what "not significant" means here

Our p-value is 0.47. Leaving it there would be lazy, because a non-significant
result is only interpretable once you know what the test could have detected.

Given the observed Newey-West standard deviation of the loss differential:

| | |
|---|---|
| Origins available | 261 |
| Observed RMSE improvement | 0.42 per cent |
| Minimum improvement detectable at 5 per cent with 80 per cent power | 1.64 per cent |
| Origins needed to detect an effect this size | 3 906 |
| Equivalent span of weekly forecasts | about 75 years |

The observed effect is roughly four times too small to clear the detection
threshold with the sample available. Detecting it would take about 75 years of
weekly forecasts, longer than the floating-rate era.

So a non-significant result here is the expected outcome given the sample, not
evidence the model does nothing. Equally, it is not evidence the model does
something. The correct reading is that this experiment cannot resolve an effect of
this size, and that any competitor claiming significance on 261 origins with a
sub-1-per-cent improvement is reporting something that does not follow from their
data.

This calculation is the single most useful thing I added after the competition. It
converts "we failed to reject" into a quantified statement about what the
experiment was capable of.

### Rolling accuracy

A single full-sample RMSE hides when an edge was earned. Over 210 complete 52-week
rolling windows:

| | |
|---|---|
| Windows where the combination is ahead | 62.4 per cent |
| Best window ratio | 0.9801 |
| Worst window ratio | 1.0239 |

Ahead most of the time, by never more than 2 per cent, and behind by up to 2.4 per
cent in the worst stretch. Thin and regime-dependent, which fits the mechanism in
section 9 rather than a stable edge.

---

## 11. Robustness

| Check | Result |
|---|---|
| Strict cut: only origins whose targets also fall inside the window | Combination 0.5621 against AR(1) 0.5647, still ahead |
| Validation era 2015-2020, never used for evaluation | Combination 0.6569 against AR(1) 0.6659, ahead |
| Benchmark variant | Reported against the better of AR(1)-log and AR(1)-level |
| Determinism | `data/processed` deleted and rebuilt from raw, maximum RMSE difference 2.22e-16 |
| Chart audit | `validate_results.py` re-derives every plotted number from raw data, 96 checks |

The determinism check matters more than it looks. Rebuilding from raw and landing
on the same numbers to machine precision means there is no hidden state, no cached
intermediate quietly carrying stale results, and no unseeded randomness.

---

## 12. What went wrong, and what I fixed

Including this section is a deliberate choice. Every project has these. Most
write-ups omit them, which makes the write-up less trustworthy rather than more.

**A statistic I had misattributed.** The R13.01 figure was originally presented as
the AR(1)'s long-run mean. It is not. It is the estimate at the 3 June 2022 origin
specifically, and the value at the final origin is R14.90 with $\phi = 0.9980$. An
audit script written to re-derive every plotted number from raw data caught it. The
fix replaced one convenient number with a stronger honest claim: the implied mean
sat below spot at all 261 origins, by R2.11 on average. The corrected version
persuades better than the error did.

**A quoted range that was wrong.** The 2022-23 spot range had been described as
R14.60 to R19. The actual weekly range is R14.54 to R19.74. Same audit.

**A chart caption that overclaimed.** The cumulative error chart was captioned as
showing the edge "holds". It does not. It peaks at 1.29 and then gives back to
0.69. Rewritten to state the peak and the give-back explicitly.

**A bug in my own statistics module.** The rolling-accuracy share was computed as
`(ratio < 1).mean()` over a series whose first 51 entries were NaN while the window
filled. NaN comparisons evaluate to False, so those warm-up periods were silently
counted as losses and the reported share came out at 50.2 per cent instead of the
correct 62.4 per cent. I found it by cross-checking the notebook's independently
written calculation against the committed JSON and noticing they disagreed. Good
argument for computing an important number twice, in two places, by two routes.

The pattern across all four is the same. An audit that re-derives numbers
independently catches things that reading your own code does not, which is why
`validate_results.py` exists and why it re-reads the raw files rather than the
processed ones.

---

## 13. Limitations and what I would do next

### What I do not claim

Statistical significance, for the reasons in section 10.

Directional predictability. Directional accuracy sits near 50 per cent for every
model, so nothing here predicts which way the rand moves.

Profitability. Never tested, and RMSE and trading P&L are different objectives.
Optimising one does not optimise the other.

Persistence. 2025 goes the other way, for a reason the mechanism predicts.

### What I would do next, in order of expected value

**Option-implied volatility and risk reversals.** Greenwood-Nimmo, Steenkamp and
van Jaarsveld (SARB WP/22/14) find that distributional information from the rand
options market improves the SARB's own forecasts. Risk reversals in particular
price the market's skew, which carries information no spot-based predictor has.
This is the most promising unexplored input and it fits the existing market-prices-
only constraint exactly. Worth noting that Steenkamp is CEO of Codera Analytics,
who co-hosted this competition and distribute the target series, so this is the
host's own research on the host's own problem.

**Density forecasts rather than point forecasts.** For anyone actually using an FX
forecast, a treasurer deciding whether to hedge or a risk manager sizing a
position, the decision-relevant object is the distribution and not the point.
Forecasting the mean of a near-random-walk series is close to hopeless. Forecasting
its dispersion is not, because volatility genuinely clusters. That is where the
value is, and it is a better-posed problem.

**Bayesian model averaging over a wider component set.** Inverse-error weights are a
crude approximation to a posterior. BMA handles model uncertainty properly and
extends naturally to a larger pool of components.

**Horizon sensitivity.** Repeat the whole exercise at 1, 2, 8 and 12 weeks. The
AR(1)'s mean-reversion bias should bite harder as the horizon lengthens, because
$\phi^h$ pulls further. That is a testable prediction of the mechanism in section 9,
and confirming it would turn an observation into an explanation.

---

## 14. Reproducing everything

```bash
git clone <repo-url> && cd <repo>
pip install -r requirements.txt

python src/run_all.py     # full pipeline, about five minutes
pytest -q                 # fourteen leakage and integrity tests
```

No API keys and no paid data. The raw files are committed, so the pipeline runs
offline from `build_dataset.py` onwards.

`run_all.py` executes these stages in order. Stage 1 runs only with `--refresh`:

| Stage | Script | What it does |
|---|---|---|
| 1 | `fetch_data.py` | Download every raw series and the ALFRED vintages into a dated snapshot |
| 2 | `verify_provenance.py` | Check EconData against the SARB Web API |
| 3 | `build_dataset.py` | Build the weekly Friday dataset from what was public at each issuance |
| 4 | `run_backtest.py` | Walk-forward out-of-sample backtest, all six models |
| 5 | `timing_sensitivity.py` | Rerun the backtest with every non-spot predictor a week later |
| 6 | `statistical_tests.py` | DM matrix, power analysis, rolling accuracy |
| 7 | `make_figures.py` | Report figures |
| 8 | `make_presentation_figures.py` | Presentation figures |
| 9 | `validate_results.py` | Audit every plotted number against the raw data |
| 10 | `make_report.py` | Build the technical report PDF |
| 11 | `build_notebook.py` | Regenerate the walkthrough notebook |

Stages 4 and 5 cache their intermediate results keyed on a SHA-256 hash of the input data
plus the configuration, so a rerun with unchanged inputs is fast and a rerun with
changed inputs recomputes on its own. The cache is gitignored.

---

## 15. References

Bates, J. M. and Granger, C. W. J. (1969). "The combination of forecasts."
*Operational Research Quarterly* 20(4).

Diebold, F. X. and Mariano, R. S. (1995). "Comparing predictive accuracy."
*Journal of Business and Economic Statistics* 13(3).

Greenwood-Nimmo, M., Steenkamp, D. and van Jaarsveld, R. (2022). "Can information
on the distribution of ZAR returns be used to improve SARB's ZAR forecasts?"
*SARB Working Paper* WP/22/14.
[PDF](https://www.resbank.co.za/content/dam/sarb/publications/working-papers/2022/WP%202214.pdf)

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

Data citation: SARB. *MARKET_RATES*. Version 1.0.0. Pretoria: SARB [producer].
Johannesburg: EconData [distributor], 2026.
