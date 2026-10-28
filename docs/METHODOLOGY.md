# Methodology and findings

This is the reference write-up: the task, the data, the models, how the out-of-sample protocol is enforced, the results, and how far they can be trusted. The short version is the [README](../README.md). A chart-led version is [`notebooks/walkthrough.ipynb`](../notebooks/walkthrough.ipynb).

Every number below is filled in from `data/processed/*.json` by `src/render_docs.py`, so this file cannot disagree with the pipeline's outputs. "We" is the competition entry (Aakash Anil and Stefan von der Heyden); "I" is the work done afterwards.

**Summary.** Over 261 Friday origins the combination scored an RMSE of 0.5599 against 0.5624 for the mandated AR(1), 0.44 per cent lower. The difference is not statistically established (Diebold-Mariano p = 0.449; 95% interval for the mean squared-error difference -0.0099 to +0.0044). Against the random walk (RMSE 0.5600) the combination is level (p = 0.967). An equal-weight average of the same three components scored 0.5599, so adaptive weighting adds nothing measurable. All 2021 to 2025 results are exploratory (section 13).

**Contents**

1. [The task](#1-the-task)
2. [Why this problem is hard](#2-why-this-problem-is-hard)
3. [Data](#3-data)
4. [The out-of-sample protocol](#4-the-out-of-sample-protocol)
5. [The models](#5-the-models)
6. [The forecast combination](#6-the-forecast-combination)
7. [Choosing the configuration](#7-choosing-the-configuration)
8. [Results](#8-results)
9. [What the AR(1) does differently](#9-what-the-ar1-does-differently)
10. [Statistical inference and planning](#10-statistical-inference-and-planning)
11. [Other cuts and timing sensitivity](#11-other-cuts-and-timing-sensitivity)
12. [Problems found in review](#12-problems-found-in-review)
13. [Limitations and exploratory status](#13-limitations-and-exploratory-status)
14. [Reproducing everything](#14-reproducing-everything)
15. [References](#15-references)

---

## 1. The task

Produce a one-month-ahead forecast of USDZAR every Friday from 1 January 2021 to 31 December 2025, out of sample, scored on RMSE against an AR(1) benchmark.

The target series is EXCX135, the South African Reserve Bank's rand-per-dollar rate, distributed through EconData. Every Friday `t` is a forecast origin and the target is the fixing on `t + 28 days`. That gives 261 forecasts, from 1 January 2021 to 26 December 2025. The last targets fall on 23 January 2026, after the end of the window, and 257 of the 261 targets fall inside 2025. All forecasts are in [`data/processed/forecast_log.csv`](../data/processed/forecast_log.csv) with the origin date, target date, spot at the origin, each model's forecast and the realised value.

I read "one month" as 28 days, which keeps origin and target on the same weekday. I did not rerun the exercise with calendar months.

The brief is in [`docs/original_task_brief.pdf`](original_task_brief.pdf).

---

## 2. Why this problem is hard

Meese and Rogoff (1983) gave standard structural exchange-rate models the actual future values of their own driving variables and still found that they lost to a no-change forecast out of sample. Rossi (2013) surveys the work since and finds that forecasting success depends on the sample, the predictor, the horizon and the benchmark chosen.

The usual explanation is that USDZAR is priced continuously by a deep market, so public information is in the price quickly and a month-ahead forecast is left with a small residual. That is an explanation I find plausible, not one this repository tests.

Two things follow for the design. First, differences between sensible forecasts will be small, and the evidence for any of them will be thin. Second, a large improvement would be a reason to look for leakage before looking for skill. Most of the engineering effort went into making leakage hard to introduce and into tests that fail if it appears.

Forecast combination has a long record in the literature, starting with Bates and Granger (1969). The M5 accuracy results paper (Makridakis, Spiliotis and Assimakopoulos, 2022, *International Journal of Forecasting*) reports that the top methods were machine-learning methods, mostly LightGBM, and that combinations helped. So the M5 evidence does not say that simple methods beat flexible ones. The gradient-boosting result in this repository covers one specification on one series and should not be read as a general claim about machine learning.

---

## 3. Data

### The target

EXCX135, from the official EconData export (`MARKET_RATES 1.0.0`, `EXCX135.B.A`). The free API tier returns only about six months of history, so the series back to 2 January 1970 came from the EconData web export. It holds 14,173 daily observations.

Because that export was manual, `verify_provenance.py` pulls the same series from the SARB Web API and compares the two:

| | |
|:---|---:|
| Overlapping observations | 9,141 |
| Largest absolute difference | 0.000000 |
| Mismatching observations | 0 |
| Observations inside the forecast window | 1,290 |

The result is written to `data/processed/provenance.json` on every run.

### The predictors

| Series | Source | Role |
|:---|:---|:---|
| JIBAR 3M minus US 3M T-bill | SARB Web API (`MMRD403A`), FRED `DTB3` | The carry signal |
| Gold, platinum | SARB (`GDPL201D`), NYMEX front-month future (`PL=F`) | South Africa exports both |
| Brent crude | FRED `DCOILBRENTEU` | South Africa imports oil |
| Broad US dollar index | FRED `DTWEXBGS` | Dollar strength against all currencies |
| VIX | FRED `VIXCLS` | Global risk appetite |

The feature sets also use the rand's own four- and twelve-week returns and its gap to the 200-day moving average. There is no CPI, current account or GDP series. Those are published late and revised, and the repository has no vintages for them.

### When each series is known

A forecast is issued at 17:00 Johannesburg time each Friday, after the SARB's 10:30 rand rate and the morning JIBAR fixing and before any US market closes that day. A value is used only if it was public by then. The release rules come from each publisher's schedule, and `data/raw/series_metadata.json` holds the rule, the source URL and the reasoning for every series.

| Series | Public at | Newest value a Friday forecast sees |
|:---|:---|:---|
| USDZAR `EXCX135D` | 10:30 Johannesburg, same day | Friday |
| JIBAR 3M | 11:00 Johannesburg, same day (10:00 from October 2012) | Friday |
| Gold, mean of the London a.m. and p.m. fixes | 15:30 London, 30 minutes after the p.m. auction starts | Friday in UK summer, Thursday in UK winter |
| Platinum `PL=F` | 17:00 New York, end of the CME day | Thursday |
| US 3M T-bill `DTB3` | H.15, 16:15 New York the next business day | Wednesday |
| VIX | Cboe close, 16:15 New York | Thursday |
| Broad dollar index `DTWEXBGS` | H.10, 16:15 New York the Monday after the week | Previous Friday |
| Brent `DCOILBRENTEU` | EIA weekly update on Wednesday | Monday |

Market fixings that a trader could watch as they happened (the SARB rate, the gold fix, platinum) are stamped at the time they were struck. Published rates and indices are stamped when they were published. Where the schedule leaves room I took the later reading. The gold rule is the one I am least sure of: the 30 minutes is my allowance for the auction, not a published time.

The dollar index, Brent, the T-bill rate and the VIX are revised. For those four the value used is the one ALFRED, the St. Louis Fed's vintage archive, showed at the time (`data/raw/vintages/`), and a four-week return takes both ends from the same vintage, so a revision cannot pass itself off as a price move. ALFRED's history starts later than the data. For the dollar index the first vintage is 4 February 2019, and before that date the earliest vintage stands in for what was known. That is an approximation, and for the dollar index it matters most, because the index was redefined and the earlier definitions are not in ALFRED. `series_metadata.json` records the first vintage and the revision counts for each series.

---

## 4. The out-of-sample protocol

**Information sets follow publication.** A predictor joins the weekly grid only once it was public by the Friday 17:00 issuance time, with the vintage then current where the series is revised. `weekly.csv` keeps, for every input, the observation date used and the moment that value became public, so the timing can be checked row by row.

**Resolved-only training.** A row of training data counts at origin `t` only once its target date is on or before `t`, whatever the row's own origin. The helper `resolved(df, as_of)` filters on target dates, not row counts, and refuses rows without one.

**Purged cross-validation.** Ridge penalties and the boosting configuration are chosen by five-fold time-ordered cross-validation. In each fold I drop the training rows whose target date is on or after the fold's first origin, because four-week targets overlap, so a plain time-series split trains on labels that are fixed inside the validation fold. The predictors are standardised inside each fold, so the scaler never sees the rows it is scored on.

**Embargoed combination weights.** Weights at origin `t` use only errors from forecasts whose targets had been fixed by `t`, which means origins at least 28 days earlier. The code asserts it.

**Selection before the judged window.** The configuration was chosen on validation origins from 2 January 2015 to 27 November 2020. The last of those has its target on 25 December 2020, before the judged window starts, and the code asserts that on target dates.

**Timing sensitivity.** The release rules involve judgement, so `timing_sensitivity.py` reruns the whole backtest, selection included, with every non-spot predictor a further week late (section 11).

### The checks

The tests in `tests/` are written so that each can fail. The ones doing most of the work:

- `test_every_forecast_at_the_origin_ignores_later_raw_data` scrambles every raw input dated after a sampled origin, rebuilds the dataset and the forecasts, and requires every model's forecast at that origin to be unchanged. `test_scrambling_the_future_changes_the_future_but_not_the_past` confirms the scramble does change the later data.
- `test_value_is_public_before_the_issuance_that_uses_it` and the neighbouring timing tests check availability for every predictor, not only spot.
- `test_no_training_label_is_fixed_inside_the_fold_it_is_scored_on` and `test_scaler_is_fitted_on_each_folds_training_rows_only` cover the purge and the per-fold scaling. `test_plain_time_series_split_would_leak_on_this_data` shows the unpurged split does leak here.
- `test_validation_boundary_assertion_fires_when_the_era_runs_too_late` and the combination tests cover the boundary and the embargo.
- `test_audit_exits_nonzero_when_a_reported_metric_is_wrong` runs the audit on a corrupted copy and requires a nonzero exit.
- `test_spot_equals_the_last_fixing_on_or_before_the_origin` re-parses the raw EconData file independently of the pipeline.

No test asserts that a model beats another. Whether it does is a result, and results come from the audit, `validate_results.py`, which recomputes the outputs from the raw files and the forecast log with its own code and exits nonzero on any mismatch.

---

## 5. The models

### AR(1), the mandated benchmark

OLS with intercept on the weekly log level, expanding window from 1999, iterated four steps forward:

$$y_t = c + \phi\, y_{t-1} + \varepsilon_t, \qquad y_t = \log S_t$$

$$\hat y_{t+4} = c\,(1 + \phi + \phi^2 + \phi^3) + \phi^4 y_t$$

`AR1_log` is the benchmark in every comparison and was fixed in advance. Three variants appear as exploratory comparisons and none replaces it:

- `AR1_level` is the same model on the level of the rate.
- `AR1_log_roll` uses only the last five years of weekly data.
- `AR1_log_vc` corrects the retransformation. The exponential of a forecast of the log is a forecast of the median of the rate under normal errors, not its mean. The mean is `exp(f + v/2)`, with `v` the four-step forecast variance implied by the fit's own residuals up to `t`. Its RMSE is 0.5617, against 0.5624 for the uncorrected version.

### Random walk, and random walk with drift

The random walk forecasts today's rate, with no parameters. `RW_drift` adds the mean weekly log change up to the origin, carried four weeks forward. Its RMSE is 0.5627, and it forecast a rise at 100 per cent of origins.

### Carry

$$\hat S_{t+28d} = S_t \left( 1 + \left(i^{ZA}_t - i^{US}_t\right)\frac{28}{365} \right)$$

This is the covered-interest-parity forward rate. Covered parity prices a forward contract that can be locked in today by borrowing and lending, and it is not the market's expectation of the future spot rate. If uncovered parity held, the forward would be an unbiased forecast, and the long literature on the forward premium puzzle finds that it generally does not. I use carry as one component and make no claim that it is a good forecast on its own.

The inputs are a mismatch. JIBAR is a bank-offered rate and the T-bill is a government rate on a discount basis, so the gap includes a credit and instrument difference as well as the rate difference. Both are three-month rates, while the horizon is 28 days, and the formula assumes the three-month gap describes the next 28 days.

### Ridge

The four-week log return regressed on a predictor set, with the scaler and the ridge fitted together inside every purged fold, a penalty chosen from a logarithmic grid and refreshed every 13 origins, and no intercept in the chosen variant. Under a heavy penalty every coefficient shrinks towards zero, the predicted return goes to zero and the forecast becomes the random walk. With an intercept it would shrink towards the historical average return instead.

The variant that went into the combination is the full predictor set, no intercept, picked on the validation era (section 7).

### Gradient boosting

`HistGradientBoostingRegressor` on the same rows. Every 52 weeks the configuration is chosen from 12 combinations of depth, learning rate, iterations, L2 penalty and minimum leaf size by the same purged 5-fold search, and the model is refitted every four weeks. There were 14 retunes in total, and the number of distinct configurations in force across the judged origins was 1.

It is a comparator. Its RMSE is 0.5745, 2.2 per cent above the AR(1) and 2.6 per cent above the random walk. Neither difference is statistically significant (p = 0.363 and 0.273). The conclusion covers this feature set, this grid and this sample only.

---

## 6. The forecast combination

The combination is an inverse discounted-MSE weighted average of the random walk, carry and ridge. At each origin, for each component `m`, take the discounted mean squared error over the last 156 resolved origins:

$$\text{DMSE}_m = \frac{\sum_{k} \delta^{k}\, e_{m,k}^2}{\sum_{k} \delta^{k}}, \qquad \delta = 0.97$$

where `k` runs backwards from the most recent resolved origin. Then weight inversely, with sharpness `θ`:

$$w_m = \frac{\left(1/\text{DMSE}_m\right)^{\theta}}{\sum_j \left(1/\text{DMSE}_j\right)^{\theta}}, \qquad \theta = 2$$

With fewer than 26 resolved errors the weights are equal. The weights are non-negative and sum to one, so the combination cannot leave the range of its members.

### What the weights did

They stayed close to equal. Across all 261 origins every weight lay between 0.306 and 0.353, and the averages were 0.334 (random walk), 0.333 (carry) and 0.333 (ridge).

| Year | Random walk, mean | Carry, mean | Ridge, mean | Smallest weight | Largest weight |
|:---|---:|---:|---:|---:|---:|
| 2021 | 0.338 | 0.330 | 0.332 | 0.320 | 0.346 |
| 2022 | 0.332 | 0.339 | 0.329 | 0.322 | 0.353 |
| 2023 | 0.330 | 0.342 | 0.328 | 0.323 | 0.352 |
| 2024 | 0.336 | 0.328 | 0.335 | 0.312 | 0.346 |
| 2025 | 0.337 | 0.324 | 0.340 | 0.306 | 0.348 |

The reason is in the errors. The component forecasts all sit within a fraction of a per cent of spot, so their errors are almost the same series. The largest pairwise correlation among the components' errors, between the random walk and carry, is 0.99998. When the errors are that similar, inverse-error weights barely move off one third each.

### Ablations

Three variants test what the adaptive scheme contributes. `EQUAL3` averages the three components at one third each. `RW_CARRY` and `RW_RIDGE` apply the same adaptive weighting with one component dropped.

`EQUAL3` scored 0.5599 against 0.5599 for the adaptive combination, a difference of 0.00002 (lower for equal weights). `RW_CARRY` scored 0.5599 and `RW_RIDGE` 0.5601. The largest gap between the combination and any of the three is 0.00017, against a 95% interval half-width of about 0.0026 rand for the combination against the random walk (section 10). I did not test the ablation differences formally, but they are far inside that width. Adaptive weighting is not a demonstrated improvement on equal weighting in this sample.

---

## 7. Choosing the configuration

Three things were chosen on the validation era: the ridge variant (feature set and intercept), the decay `δ` and the sharpness `θ`. Choosing them on the judged window would let the reported number partly measure how many configurations I tried.

The validation origins run from 2 January 2015 to 27 November 2020 (309 origins). The last target resolves on 25 December 2020. The chosen configuration is RIDGE_f0, δ = 0.97 and θ = 2, with a validation RMSE of 0.6592 for the combination, against 0.6679 for the AR(1) and 0.6593 for the random walk.

Those validation scores were used to pick the configuration, so they are not independent evidence about the combination. I report them for completeness.

The full grid of 24 configurations is in [`data/processed/validation_metrics.json`](../data/processed/validation_metrics.json), along with every boosting trial. The best five:

| Ridge variant | Decay | Sharpness | Validation RMSE |
|:---|---:|---:|---:|
| RIDGE_f0 (full set, no intercept) | 0.97 | 2 | 0.65920 |
| RIDGE_f0 (full set, no intercept) | 0.99 | 2 | 0.65928 |
| RIDGE_f0 (full set, no intercept) | 0.97 | 1 | 0.65928 |
| RIDGE_f0 (full set, no intercept) | 1.00 | 2 | 0.65932 |
| RIDGE_f0 (full set, no intercept) | 0.99 | 1 | 0.65932 |

The surface is flat. The fifth-best configuration is 0.00012 worse than the best, and the whole grid spans 0.00237. Choosing among these configurations changed almost nothing, which is also why the selection step cannot account for a gain in the judged window.

---

## 8. Results

All 261 origins, 1 January 2021 to 26 December 2025. RMSE and MAE are in rand per dollar. "RMSE below AR(1)" is the per cent by which a model's RMSE is below the benchmark's, so a positive number favours the model. The rank is by RMSE across the 13 models, 1 being lowest. "Calls a rise" is the share of origins at which the forecast was above spot.

| Model | RMSE | MAE | RMSE below AR(1) | Rank | Calls a rise |
|:---|---:|---:|---:|---:|---:|
| AR(1), log level (benchmark) | 0.5624 | 0.4478 |  | 9 | 0% |
| AR(1), level | 0.5629 | 0.4492 | -0.09% | 11 | 31% |
| AR(1), 5-year window | 0.5724 | 0.4502 | -1.79% | 12 | 9% |
| AR(1), mean-corrected | 0.5617 | 0.4492 | +0.11% | 8 | 59% |
| Random walk | 0.5600 | 0.4480 | +0.43% | 4 | 0% |
| Random walk with drift | 0.5627 | 0.4577 | -0.05% | 10 | 100% |
| Carry | 0.5606 | 0.4540 | +0.32% | 7 | 100% |
| Ridge | 0.5602 | 0.4479 | +0.38% | 6 | 72% |
| Gradient boosting | 0.5745 | 0.4723 | -2.16% | 13 | 65% |
| Combination | 0.5599 | 0.4495 | +0.44% | 3 | 100% |
| Equal-weight RW + carry + ridge | 0.5599 | 0.4495 | +0.44% | 2 | 100% |
| Adaptive RW + carry | 0.5599 | 0.4504 | +0.44% | 1 | 100% |
| Adaptive RW + ridge | 0.5601 | 0.4479 | +0.40% | 5 | 72% |

The combination ranks 3 of 13 and the random walk 4. The 7 models built from the random walk, carry and ridge (those three, the combination, the equal-weight average and the two adaptive pairs) are all within 0.00068 of each other. Of the 5 core models (random walk, carry, ridge, gradient boosting and the combination), 4 scored below the AR(1). Those margins are small, and whether any of them is more than noise is the subject of section 10.

### By year

| Year | AR(1) | Random walk | Combination | Equal weights | Lower of AR(1) and combination |
|:---|---:|---:|---:|---:|---:|
| 2021 | 0.5118 | 0.5102 | 0.5104 | 0.5104 | Combination |
| 2022 | 0.6985 | 0.6928 | 0.6902 | 0.6901 | Combination |
| 2023 | 0.6553 | 0.6493 | 0.6475 | 0.6475 | Combination |
| 2024 | 0.4456 | 0.4449 | 0.4453 | 0.4452 | Combination |
| 2025 | 0.4523 | 0.4574 | 0.4629 | 0.4630 | AR(1) |

The combination was ahead of the AR(1) in 4 of 5 years (2021, 2022, 2023 and 2024) and behind in 2025, when the AR(1) scored 0.4523 against 0.4629 and the random walk 0.4574. I have not tested why. Five annual RMSEs cannot say whether the year-to-year pattern is stable.

Cumulative squared-error difference, AR(1) minus combination: 0.08 at the end of 2021, 0.68 in 2022, 1.20 in 2023 and 1.22 in 2024, a peak of 1.32 on 28 March 2025, and 0.72 at the end of 2025. Positive means the combination is ahead.

### One forecast, worked

Friday 3 June 2022. Spot R15.4117, target 1 July 2022, realised R16.3482.

| Model | Forecast | Error |
|:---|---:|---:|
| Gradient boosting | 15.5674 | -0.7808 |
| Carry | 15.4563 | -0.8919 |
| Combination | 15.4275 | -0.9207 |
| Ridge | 15.4141 | -0.9341 |
| Random walk | 15.4117 | -0.9365 |
| AR(1), log level (benchmark) | 15.3861 | -0.9621 |

Every model forecast too low. The combination's weights that day were 0.333 (random walk), 0.337 (carry) and 0.331 (ridge), which give 15.4275. Carry's forecast is `15.4117 x (1 + 0.0377 x 28/365)`, with a gap of 0.0377 between the two three-month rates. The forecasts range from 15.386 to 15.567, a spread of 18 cents, against an actual move of 94 cents.

---

## 9. What the AR(1) does differently

An AR(1) with persistence `φ` below one is pulled towards a long-run level. For the log series the level it is pulled towards is

$$\mu = \exp\left(\frac{c}{1-\phi}\right)$$

which is the equilibrium of the log, so it is a median-type level and not the mean of the rate. It is fragile near a unit root. Across the 261 origins the estimated `φ` ran from 0.9971 to 0.9986, so `1 - φ` ran from 0.0014 to 0.0029. A small change in `c` or `φ` moves `μ` a long way, and it did: `μ` ranged from R11.80 to R19.18 as the estimation sample grew, while spot at the origins ran from R14.62 at the first to R19.74 at the highest. At the worked-example origin the fit had 1,222 observations, `φ` = 0.997531 and `μ` = R13.01, against a spot rate of R15.41, with a shock half-life of 280 weeks.

### What the data show

- `μ` was below spot at 261 of 261 origins, by R2.11 on average and by at least R0.57.
- The AR(1) forecast a rise at 0 per cent of origins. On average its forecast sat -0.112 per cent from spot.
- Its mean error (forecast minus outcome) was -0.0393, against -0.0207 for the random walk and -0.0055 for the combination.
- Squared bias is 0.49 per cent of the AR(1)'s mean squared error and 0.01 per cent of the combination's. The AR(1)'s mean squared error is 0.00275 higher than the combination's, and 55 per cent of that gap is the difference in squared bias. The remainder is variance.

These are observations. The AR(1) leans downward, and the difference in squared bias accounts for 55 per cent of its excess squared error against the combination. I have not shown that this is the full explanation, or that it would persist. The rand's own path over 1 January 2021 to 26 December 2025 is one sample, and a mean-reverting model will do better in a sample where the rand reverts. The AR(1) was ahead in 2025, and I have not tested why.

---

## 10. Statistical inference and planning

### The Diebold-Mariano test

Forecasts four weeks ahead overlap, so the loss differential between two models is serially correlated by construction. Every DM statistic here uses a Newey-West long-run variance with a Bartlett kernel, at lag 3 (`h - 1`) as the primary choice. The statistic is the mean of `loss(model) - loss(benchmark)`, with squared error as the loss, divided by its standard error. A negative value favours the model. P-values are two-sided and use the normal distribution. The intervals are 95% intervals for the mean loss differential.

Two comparisons were fixed before the judged window was scored: the combination against the AR(1) and the combination against the random walk. They are reported with unadjusted p-values and at several lags. Everything else is exploratory.

| Comparison | DM (lag 3) | p | 95% interval, mean squared-error difference | RMSE difference | p across the four lags |
|:---|---:|---:|:---|---:|:---|
| Combination vs AR(1) | -0.76 | 0.449 | -0.0099 to +0.0044 | -0.00245 | 0.449 to 0.456 |
| Combination vs random walk | -0.04 | 0.967 | -0.0030 to +0.0029 | -0.00006 | 0.966 to 0.967 |

The four lags are 3, 4, 8 and the Andrews (1991) automatic choice, which was 13 against the AR(1) and 11 against the random walk. The answer does not depend on the lag. Both intervals contain zero. On the RMSE scale, holding the benchmark's MSE fixed, the interval for the combination against the AR(1) is -0.0088 to +0.0039 rand.

### Exploratory comparisons

Each non-prespecified model is compared with both benchmarks. That is 21 distinct hypotheses (the random walk against the AR(1) counts once). The p-values are adjusted together by Holm's step-down method. 2 of the 21 have an unadjusted p-value below 0.05, and 0 survive the adjustment. The smallest adjusted p-value is 0.201.

| Model | DM vs AR(1) | p | Holm p | DM vs RW | p | Holm p |
|:---|---:|---:|---:|---:|---:|---:|
| AR(1), log level (benchmark) | - | - | - | +1.23 | 0.218 | 1.000 |
| AR(1), level | +0.33 | 0.741 | 1.000 | +2.39 | 0.017 | 0.338 |
| AR(1), 5-year window | +0.82 | 0.410 | 1.000 | +0.92 | 0.355 | 1.000 |
| AR(1), mean-corrected | -0.38 | 0.703 | 1.000 | +2.59 | 0.010 | 0.201 |
| Random walk | -1.23 | 0.218 | 1.000 | - | - | - |
| Random walk with drift | +0.04 | 0.968 | 1.000 | +0.48 | 0.628 | 1.000 |
| Carry | -0.31 | 0.760 | 1.000 | +0.14 | 0.885 | 1.000 |
| Ridge | -1.12 | 0.264 | 1.000 | +0.42 | 0.673 | 1.000 |
| Gradient boosting | +0.91 | 0.363 | 1.000 | +1.10 | 0.273 | 1.000 |
| Combination (prespecified) | -0.76 | 0.449 | n/a | -0.04 | 0.967 | n/a |
| Equal-weight RW + carry + ridge | -0.77 | 0.444 | 1.000 | -0.06 | 0.952 | 1.000 |
| Adaptive RW + carry | -0.63 | 0.525 | 1.000 | -0.05 | 0.962 | 1.000 |
| Adaptive RW + ridge | -1.19 | 0.233 | 1.000 | +0.39 | 0.697 | 1.000 |

"n/a" marks the two prespecified comparisons, which are not adjusted.

### What the results can and cannot say

The combination moves almost in step with the random walk. Its forecast differs from spot by 0.089 per cent on average. It forecast a rise at 100 per cent of origins, because carry's tilt is always upward, while the rand rose at 46.4 per cent of them. So its directional accuracy (46.4 per cent) is just the share of origins at which the rand rose, and the combination carries no directional information.

### Planning table

An earlier version of this repository ran a power calculation at the observed effect size, which says nothing about what a study could detect. This table fixes the effect sizes in advance instead: RMSE reductions of 1, 2 and 5 per cent, chosen as round numbers and not as a statement of what the literature has achieved. It gives the number of weekly origins at which a two-sided 5% Diebold-Mariano test would detect each one with 80 per cent power.

The assumptions, all of which can fail:

- two-sided 5% DM test on squared-error loss, 80% power, normal approximation
- the long-run sd of the loss differential stays at its 2021-2025 value for COMBO against that benchmark (Newey-West, lag 3)
- the benchmark's MSE stays at its 2021-2025 value
- effect sizes are fixed in advance, not taken from the observed result

Against the AR(1):

| RMSE cut | Origins needed | Years of weekly origins | Power with 261 origins |
|:---|---:|---:|---:|
| 1% | 680 | 13.1 | 41% |
| 2% | 172 | 3.3 | 93% |
| 5% | 29 | 0.5 | 100% |

Against the random walk:

| RMSE cut | Origins needed | Years of weekly origins | Power with 261 origins |
|:---|---:|---:|---:|
| 1% | 120 | 2.3 | 99% |
| 2% | 31 | 0.6 | 100% |
| 5% | 5 | 0.1 | 100% |

The two tables differ because the loss differential has a different standard deviation in each case (0.0586 against the AR(1), 0.0243 against the random walk). The requirements against the random walk are small only because the combination and the random walk are nearly the same forecast, which keeps that standard deviation small. A reduction of 1 to 5 per cent between two forecasts that differ from each other by 0.089 per cent of spot is implausible, so those rows show what the test could detect if such an effect existed, and are no forecast of what a holdout would find.

The planning table is about this combination against these two benchmarks and says nothing about any other forecaster's results.

### Rolling accuracy

Over 210 complete 52-week rolling windows the combination had a lower RMSE than the AR(1) in 67.6 per cent of them. The best window ratio (combination over AR(1)) was 0.9800 and the worst 1.0234. Adjacent windows share most of their origins, so this is one comparison viewed through a moving frame and not 210 independent results.

---

## 11. Other cuts and timing sensitivity

### Timing

Every non-spot predictor was pushed a further week late and the whole backtest, selection included, was rerun. Selection picked the same configuration.

| Model | Base timing | Predictors one week later | Change |
|:---|---:|---:|---:|
| AR(1), log level (benchmark) | 0.5624 | 0.5624 | +0.00000 |
| AR(1), level | 0.5629 | 0.5629 | +0.00000 |
| Random walk | 0.5600 | 0.5600 | +0.00000 |
| Carry | 0.5606 | 0.5605 | -0.00003 |
| Ridge | 0.5602 | 0.5599 | -0.00033 |
| Gradient boosting | 0.5745 | 0.5638 | -0.01075 |
| Combination | 0.5599 | 0.5598 | -0.00014 |

The AR(1) models and the random walk use spot only, so they do not move. Among the rest, the largest change outside gradient boosting is 0.00033. Gradient boosting's RMSE changes by 0.0107 (0.5745 to 0.5638), so a statement about its accuracy depends on the release-lag assumptions. The combination moves from 0.5599 to 0.5598.

### Other cuts

- Strict cut. Keeping only origins whose targets also fall inside 2025 (257 origins), the combination scores 0.5619, the AR(1) 0.5647 and the random walk 0.5622. This is a subset of the same data. It is not an independent confirmation.
- Validation era. The combination scores 0.6592 and the AR(1) 0.6679, but that era chose the configuration (section 7).
- Determinism. The pipeline reruns from the committed raw files with no randomness beyond fixed seeds, and CI fails if the regenerated files under `data/processed`, the README or this document differ from what is committed.

---

## 12. Problems found in review

An outside review of an earlier version found that the numbers reproduced but that the claims went further than the evidence. The main items, and what changed:

- The information set: The first version assumed every predictor was public the moment it was observed. Several are published a day or more late, and some are revised. Predictors now join on their publication time with the vintage then current (section 3).
- Validation reaching into the judged window: Four-week targets from the last validation origins fell in 2021. Validation now ends at the last origin whose target resolves before 2021, and the code asserts it.
- Leaky ridge selection: The penalty was chosen with an unpurged time split and scaling outside the folds. Both are fixed (section 4).
- Tests that could not fail: The old tests could not detect leakage, one test asserted the headline result, and the audit exited with success even when a check failed. The tests now scramble post-origin data and check each rule, none asserts a result, and the audit's exit code is tested.
- The AR(1) baseline picked after the fact: It had been chosen as the better of two variants on the judged window. `AR1_log` is now fixed in advance and the other variants are exploratory.
- The power calculation: It was run at the observed effect size and read as a statement about a competitor's result. It is replaced by the planning table.
- A reversed sign: The Diebold-Mariano table had the signs of the statistics reversed against its own legend. The table is now generated from the saved results with the sign defined in section 10.
- The M5 citation: The earlier text said the M5 competition favoured simple methods. The M5 accuracy results paper reports that machine-learning methods led and that combinations helped (section 2).
- Economics: Covered interest parity prices a forward and is not an expected spot rate. The AR(1)'s long-run level is `exp(c/(1-φ))` and is fragile near a unit root. The log forecast needs a retransformation correction to be a mean. The AR(1)'s downward lean was presented as the explanation for its loss and is now reported as an observation.
- Numbers typed into documents: Documents carried hand-typed results that drifted from the outputs. They are now generated from the JSON files.

A smaller error from before the review is worth keeping: the rolling-accuracy share was computed over a series whose first 51 entries were missing while the window filled, and the comparison treated those as losses. It now drops them.

---

## 13. Limitations and exploratory status

### Exploratory status

All 2021 to 2025 results are exploratory. The window was scored repeatedly while the code was built and then repaired, benchmarks and ablations were added after earlier results had been seen, and no new holdout was added. The two prespecified comparisons are labelled as such in the code and the outputs, but nothing registered them outside the repository.

### Other limitations

- Overlapping four-week forecasts and overlapping sample cuts are not independent. The strict cut, the by-year results and the rolling windows are views of the same 261 errors.
- Five years is a short window and the results are for one path of the rand. Other periods may differ.
- The gradient-boosting conclusion covers this feature set, this grid and these release lags (section 11).
- The release lags are partly judgement, and the dollar index before its first ALFRED vintage uses the earliest vintage as a stand-in.
- Carry uses three-month rates for a 28-day horizon, as set out in section 5.
- Directional accuracy is uninformative: the combination forecasts a rise at nearly every origin.
- Nothing here tests profitability. RMSE and trading return are different objectives.

### What I do not claim

A statistically established improvement over the AR(1). Any improvement over the random walk. That adaptive weighting helps. That the AR(1)'s downward lean is the full explanation for its score. That any of this persists out of sample.

### A prospective-holdout protocol

A clean test needs forecasts made after the design is frozen. The protocol:

1. Freeze the design. Record the git commit of the code, the chosen configuration in `validation_metrics.json` and the date of the raw-data snapshot, and publish them before the first new origin. Afterwards change nothing except bugs, and record each fix with its reason.
2. Prespecify the tests: the combination against the AR(1) and against the random walk, squared-error loss, Newey-West lag 3, two-sided 5%. Treat every other comparison as exploratory with a Holm adjustment.
3. Fix the sample size and stop date before the first origin, using the planning table (section 10). Against the AR(1), a 2 per cent RMSE cut needs about 172 origins (3.3 years of weekly forecasts) and a 1 per cent cut about 680 (13.1 years), under that table's assumptions.
4. Score each origin once, after its target is fixed, by appending to a log that is never rewritten.
5. Report the result whatever it is.

### What I would try next

- Option-implied volatility and risk reversals. Greenwood-Nimmo, Steenkamp and van Jaarsveld (SARB WP/22/14) report that information on the distribution of rand returns improves the SARB's forecasts, and this is the input I would add first.
- Density forecasts. For hedging decisions the distribution matters more than the point forecast, and volatility is more forecastable than the mean.
- Horizons of 1, 2, 8 and 12 weeks, to see whether the AR(1)'s lean costs more as the horizon grows.
- Bayesian model averaging over a wider set of components.

---

## 14. Reproducing everything

```bash
git clone <repo-url> && cd <repo>
pip install -r requirements-lock.txt
python src/run_all.py
pytest -q
```

`requirements-lock.txt` pins the versions the committed outputs were produced with. The raw files are committed, so the default run needs no network access and no API key. `--refresh` first downloads a new dated snapshot into `data/raw/snapshots/` and leaves the committed raw files alone. The slides need Node.js; `run_all.py` runs `npm ci` if `src/node_modules` is missing.

`run_all.py` stops at the first step that exits nonzero. Its steps, in order:

| Step | Script | What it does |
|:---|:---|:---|
| 0 | `fetch_data.py` | With `--refresh` only: download the raw series and ALFRED vintages into a dated snapshot |
| 1 | `verify_provenance.py` | Check EconData against the SARB Web API |
| 2 | `build_dataset.py` | Build the weekly dataset from what was public at each issuance |
| 3 | `run_backtest.py` | Walk-forward backtest, validation-era selection, all models |
| 4 | `timing_sensitivity.py` | Rerun the backtest with non-spot predictors a week later |
| 5 | `statistical_tests.py` | DM tests, Holm adjustment, planning table, rolling accuracy |
| 6 | `diagnostics.py` | Bias, direction, error correlation, weights, the AR(1) fit |
| 7 | `make_figures.py` | Report figures |
| 8 | `make_presentation_figures.py` | Slide figures |
| 9 | `validate_results.py` | Audit the outputs against the raw data |
| 10 | `render_docs.py` | Fill the README and this document from the JSON outputs |
| 11 | `make_report.py` | Build the technical report PDF |
| 12 | `build_notebook.py` | Regenerate and execute the notebook |
| 13 | `make_presentation.js` | Build the slide deck |

The slow stages cache their intermediate results, keyed on a hash of the data, the source files and the configuration, so a rerun with unchanged inputs is fast and a changed input recomputes. The cache is gitignored.

---

## 15. References

Andrews, D. W. K. (1991). "Heteroskedasticity and autocorrelation consistent covariance matrix estimation." *Econometrica* 59(3).

Bates, J. M. and Granger, C. W. J. (1969). "The combination of forecasts." *Operational Research Quarterly* 20(4).

Diebold, F. X. and Mariano, R. S. (1995). "Comparing predictive accuracy." *Journal of Business and Economic Statistics* 13(3).

Greenwood-Nimmo, M., Steenkamp, D. and van Jaarsveld, R. (2022). "Can information on the distribution of ZAR returns be used to improve SARB's ZAR forecasts?" *SARB Working Paper* WP/22/14.
[PDF](https://www.resbank.co.za/content/dam/sarb/publications/working-papers/2022/WP%202214.pdf)

Holm, S. (1979). "A simple sequentially rejective multiple test procedure." *Scandinavian Journal of Statistics* 6(2).

Makridakis, S., Spiliotis, E. and Assimakopoulos, V. (2022). "M5 accuracy competition: Results, findings, and conclusions." *International Journal of Forecasting*.

Meese, R. A. and Rogoff, K. (1983). "Empirical exchange rate models of the seventies: Do they fit out of sample?" *Journal of International Economics* 14.

Newey, W. K. and West, K. D. (1987). "A simple, positive semi-definite, heteroskedasticity and autocorrelation consistent covariance matrix." *Econometrica* 55(3).

Rossi, B. (2013). "Exchange rate predictability." *Journal of Economic Literature* 51(4).

Data citation: SARB. *MARKET_RATES*. Version 1.0.0. Pretoria: SARB [producer]. Johannesburg: EconData [distributor], 2026.
