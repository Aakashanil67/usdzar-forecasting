# Forecasting USDZAR one month ahead

**Can a simple forecast combination beat an AR(1) benchmark out of sample, and
can we explain exactly why?**

261 out-of-sample forecasts of the rand, one every Friday from 1 January 2021 to
31 December 2025, at a 28-day horizon. Built for the SES x Codera Analytics
Hackathon, July 2026, and extended afterwards with the statistical work a quant
reviewer would ask for.

| | |
|---|---|
| **Forecast combination** (submitted model) | RMSE **0.5600** |
| **AR(1) benchmark** | RMSE **0.5624** |
| **Improvement** | **0.42%**, with 4 of 5 models beating the benchmark |
| **Target series** | SARB **EXCX135**, verified identical to the SARB Web API across 9,141 observations (max difference 0.000000) |
| **Reproducibility** | `data/processed` deleted and rebuilt from raw: max RMSE difference **2.22e-16** |

---

## Start here

| If you have… | Open |
|---|---|
| **5 minutes** | The two sections below |
| **20 minutes** | [`notebooks/walkthrough.ipynb`](notebooks/walkthrough.ipynb) — the analysis end to end, with charts, runs in seconds |
| **An hour** | [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) — the full manual: protocol, models, results, mistakes, limitations |
| **Doubts about the numbers** | [`data/processed/forecast_log.csv`](data/processed/forecast_log.csv) — all 261 forecasts, every model, recompute the headline in one line |
| **Doubts about the discipline** | `pytest -q` — 14 tests that fail loudly if any forecast could not have been made at the time it claims |

---

## The result in one paragraph

At a one-month horizon the rand is close to a random walk. Since Meese and Rogoff
(1983), structural exchange-rate models have reliably lost to a no-change
forecast, and honest published gains sit around 1 to 5 percent in RMSE. So rather
than fight that, this project builds a **forecast combination**: a random-walk
anchor, a carry tilt from the JIBAR minus US T-bill gap, and a heavily shrunk
ridge on commodity, dollar and risk factors, weighted by their recent
out-of-sample accuracy.

It beats the AR(1) by 0.42 percent. More importantly, **it is possible to say
exactly why.**

## Why the benchmark loses

An AR(1) estimates persistence between 0.9971 and 0.9986 on this series: close to
one, but below it. Any persistence below one pulls every forecast toward an
implied long-run mean, `mu = c / (1 - phi)`.

Refitting the AR(1) at all 261 origins and recomputing that mean each time:

> **The implied mean sat below the prevailing spot rate at 261 of 261 origins**,
> by **R2.11** on average, never by less than R0.57, while the rand rose from
> R14.62 to a peak of R19.74.

A mean-reverting model applied to a trending series pulls every forecast the
wrong way. RMSE squares errors, so the occasional large miss that produces
dominates the score.

That is the whole result. These models do not predict the rand better in any deep
sense; they decline to make one specific, repeated, identifiable mistake. It also
predicts when the edge should vanish, and it does: **2025 goes to the benchmark**,
because that is the year the rand moved back toward the mean.

![Forecasts against actual](figures/forecasts_vs_actual.png)

---

## What makes this more than a leaderboard entry

**A power analysis instead of an excuse.** The improvement is not statistically
significant (Diebold-Mariano p = 0.47). Rather than leave that as a weakness, the
project asks what significance would have required:

| | |
|---|---|
| Origins available | 261 |
| Observed improvement | 0.42% |
| Minimum detectable at 5% with 80% power | **1.64%** |
| Origins needed to detect an effect this size | 3,906, about **75 years** of weekly forecasts |

A non-significant result here is the expected outcome given the sample, not
evidence the model does nothing. It also means any competitor claiming
significance on 261 origins with a sub-1-percent improvement is reporting
something that does not follow from their data.

**A control that was designed to fail, and did.** Gradient boosting ran under
identical rules and lost by 7.5 percent. It is the only difference in the entire
pairwise DM matrix that reaches significance. Keeping it in is more informative
than dropping it.

**Leakage prevention that is tested, not asserted.** Five structural guarantees,
each enforced by a test that re-derives the answer from the raw files rather than
trusting the pipeline. See [the protocol section](docs/METHODOLOGY.md#4-the-out-of-sample-protocol).

**A written record of what went wrong.** [Section 12](docs/METHODOLOGY.md#12-what-went-wrong-and-what-i-fixed)
of the methodology lists four errors found by auditing, including one bug in my
own statistics module that silently understated a headline figure. Every project
has these; most write-ups omit them.

---

## The out-of-sample protocol

The part worth checking if you are evaluating this.

1. **Information sets.** Every predictor enters through a backward `merge_asof`,
   so a forecast made on Friday `t` sees only observations dated on or before `t`.
2. **No publication lags.** Every predictor is a daily market price or rate.
   Never revised, no release delay, so look-ahead bias is impossible by
   construction rather than merely avoided. CPI and the current account were given
   up to buy that guarantee.
3. **Resolved-only training.** The regressions train only on origins whose 28-day
   outcome had already resolved: `tr = tr[tr.index <= i - H]`.
4. **Embargoed weights.** Combination weights use only errors from forecasts
   resolved 28 days before the current origin.
5. **Frozen configuration.** Feature set, intercept choice, decay and sharpness
   were chosen on a **2015-2020 validation era** whose targets all resolve before
   2021, then frozen. The full search grid is committed in
   [`validation_metrics.json`](data/processed/validation_metrics.json) so a
   reviewer can see how many configurations were tried, not just the winner.

---

## Models

| Model | RMSE | vs AR(1) | What it is |
|---|---|---|---|
| AR(1) | 0.5624 | — | The required benchmark. OLS with intercept on the weekly log level, expanding window from 1999, iterated 4 steps. Reported against the better of the log and level variants. |
| Random walk | 0.5600 | +0.43% | No-change. The strongest single benchmark at this horizon. |
| **Combination** | **0.5600** | **+0.42%** | **The submitted model.** Inverse discounted-MSE weighted average of {RW, carry, ridge}, decay 0.97, sharpness 2. |
| Ridge | 0.5605 | +0.34% | 4-week log return on the compact predictor set. Standardised in-window, penalty by time-ordered CV, **no intercept** so heavy shrinkage collapses it into the random walk rather than a stale mean. |
| Carry | 0.5606 | +0.31% | Covered-interest-parity forward rate from the JIBAR minus US T-bill gap. |
| Gradient boosting | 0.6046 | −7.51% | Depth-2 comparator under identical discipline, kept as a control. |

---

## Repository layout

```
├── README.md
├── notebooks/
│   └── walkthrough.ipynb          the analysis end to end, executed
├── docs/
│   ├── METHODOLOGY.md             the full manual
│   └── original_task_brief.pdf    the competition brief
├── src/
│   ├── fetch_data.py              1. download every raw series
│   ├── verify_provenance.py       2. EconData vs the SARB Web API
│   ├── build_dataset.py           3. weekly Friday dataset, backward as-of merges
│   ├── run_backtest.py            4. walk-forward out-of-sample backtest
│   ├── statistical_tests.py       5. DM matrix, power analysis, rolling accuracy
│   ├── make_figures.py            6. report figures
│   ├── make_presentation_figures.py
│   ├── validate_results.py        8. audit every plotted number against raw data
│   ├── make_report.py             9. build the technical report PDF
│   ├── build_notebook.py          regenerate the walkthrough notebook
│   ├── make_presentation.js       rebuild the slide deck (Node)
│   └── run_all.py                 the whole pipeline in order
├── tests/
│   └── test_no_lookahead.py       14 leakage and integrity tests
├── data/
│   ├── raw/                       exactly as downloaded, never hand-edited
│   └── processed/                 weekly.csv, forecast_log.csv, metrics.json,
│                                  statistical_tests.json, validation_metrics.json
├── figures/
└── reports/
    ├── technical_report.pdf
    └── presentation.pptx
```

---

## Reproducing everything

```bash
git clone <this-repo> && cd <this-repo>
pip install -r requirements.txt

python src/run_all.py     # data -> backtest -> statistics -> figures -> report (~4 min)
pytest -q                 # 14 tests
```

No API keys. No paid data. The raw files are committed, so everything from
`build_dataset.py` onwards runs offline. The pipeline is deterministic: rerunning
reproduces every published number to twelve decimal places.

To rebuild the slide deck you also need Node: `cd src && npm install && node make_presentation.js`.

---

## Data sources

| Series | Source | Role |
|---|---|---|
| USDZAR (EXCX135) | SARB via EconData, `MARKET_RATES 1.0.0`, `EXCX135.B.A` | Target |
| JIBAR 3M | SARB Web API | Carry |
| US 3M Treasury bill | FRED (`DTB3`) | Carry |
| Gold, platinum, Brent | SARB, NYMEX, FRED | Commodity block |
| Broad US dollar index, VIX | FRED (`DTWEXBGS`, `VIXCLS`) | Dollar strength, global risk |

Citation: SARB. *MARKET_RATES*. Version 1.0.0. Pretoria: SARB [producer].
Johannesburg: EconData [distributor], 2026.

---

## What is not claimed

- **Statistical significance.** See the power analysis above.
- **Directional predictability.** Directional accuracy sits near 50 percent for
  every model. Nothing here predicts which way the rand moves.
- **Profitability.** Never tested. RMSE and trading P&L are different objectives.
- **Persistence.** 2025 goes the other way, for a reason the mechanism predicts.

The most promising unexplored direction is **option-implied volatility and risk
reversals**, following SARB WP/22/14, and moving from point forecasts to
**density forecasts**, which is the decision-relevant object for anyone actually
hedging currency risk and a better-posed problem than forecasting the mean of a
near-random walk.

---

## Author and provenance

Built by **Aakash Anil** (BCom Honours Economics, Stellenbosch University) with
Stefan von der Heyden, as team *Spurious Decision*, for the SES x Codera Analytics
Hackathon in July 2026. The competition entry did not place. The repository has
since been rebuilt as a portfolio piece, with the statistical testing, power
analysis, test suite and documentation added afterwards.

AI assistance (Anthropic's Claude) was used for pipeline code, literature search
and typesetting. The modelling decisions, validation design and final
specification are mine, and OLS, ridge and weighted averages were chosen
deliberately so that every component can be derived by hand.

MIT licensed. See [LICENSE](LICENSE) for the data terms, which differ.
