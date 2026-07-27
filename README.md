# Forecasting USDZAR one month ahead

**SES x Codera Analytics Hackathon, July 2026**
**Team Spurious Decision — Aakash Anil and Stefan von der Heyden, Stellenbosch University**

One-month-ahead forecasts of the rand, made every Friday from 1 January 2021 to 31 December 2025, benchmarked against an AR(1).

| | |
|---|---|
| **Our model** (forecast combination) | RMSE **0.5600** |
| **AR(1) benchmark** | RMSE **0.5624** |
| **Improvement** | **+0.42%**, and four of our five models beat the benchmark |
| **Forecasts** | 261, every Friday, out of sample, every one logged |
| **Target series** | SARB **EXCX135** via the official EconData export, verified identical to the SARB Web API across 9,141 observations (max difference 0.000000) |

---

## Start here

| To… | Open |
|---|---|
| **Read the submission** | [`report/Project_Report.pdf`](report/Project_Report.pdf) |
| **See the slides** | [`presentation/Deck.pptx`](presentation/Deck.pptx) — 6 presented, references, 7 appendix |
| **Check our numbers yourself** | [`data/processed/forecast_log.csv`](data/processed/forecast_log.csv) — all 261 forecasts with origin date, target date, every model's forecast and the realised value |
| **Audit every chart** | `python code/verify_charts.py` — 96 independent checks against the raw data |
| **Reproduce everything** | See below. About four minutes, no API keys, no paid data |

---

## The argument in one paragraph

At a one-month horizon the rand is close to a random walk. Forty years of literature since Meese and Rogoff (1983) says structural exchange-rate models lose to a no-change forecast, and honest published gains run 1 to 5 per cent in RMSE. So rather than fight that, we built a **forecast combination**: a random-walk anchor, a carry tilt from the JIBAR minus US T-bill gap, and a heavily shrunk ridge regression on commodity, dollar and risk factors, weighted by their recent out-of-sample accuracy.

It beats the AR(1) by 0.42 per cent, and we can say exactly why. The AR(1)'s persistence sits just below one, so every forecast is pulled toward an implied long-run mean of c/(1−φ). We computed that mean at all 261 origins: **it sat below the prevailing spot rate at every single one, by R2.11 on average**, while the rand rose from R14.62 to a peak of R19.74. A small bias, repeated 261 times, and RMSE weights the resulting large misses most heavily.

We also ran a gradient-boosting model under identical discipline and it lost by 7.5 per cent. We kept it in the submission because that failure is evidence for the design.

---

## Reproducing our results

```bash
pip install pandas numpy scikit-learn matplotlib requests reportlab pillow
python code/run_all.py          # data → backtest → figures → report (~4 min)
python code/verify_charts.py    # 96 checks: every plotted number vs the raw data
python code/final_check.py      # 58 checks: rules, rubric, consistency
```

The pipeline is deterministic. Rerunning it reproduces every published number to twelve decimal places; we tested this by deleting `data/processed` and rebuilding from the raw EconData file.

To rebuild the slide deck you also need Node: `cd presentation && npm install && node build_deck.js`.

---

## How the out-of-sample discipline works

These are the things worth checking if you are marking this.

1. **Information sets.** Every predictor enters through a backward as-of merge, so a forecast made on Friday *t* can only see observations dated on or before *t*.
2. **No publication lags.** Every predictor is a daily market price or rate. Never revised, no release delay, so look-ahead bias is impossible by construction rather than merely avoided. We gave up CPI and the current account to buy that guarantee.
3. **Resolved-only training.** The ridge and boosting models train only on origins whose 28-day outcome had already resolved: `tr = tr[tr.index <= i - H]`.
4. **Embargoed weights.** Combination weights use only forecast errors resolved 28 days before the current origin.
5. **Frozen configuration.** The feature set, intercept choice, decay and sharpness were selected on a 2015–2020 validation era whose targets all resolve before 2021, then frozen. The full search grid is in [`data/processed/validation_metrics.json`](data/processed/validation_metrics.json). The judged window was never used to make a modelling decision.
6. **An auditable log.** All 261 forecasts are in `forecast_log.csv`. Our headline RMSE can be recomputed from that file in one line.

---

## Repository layout

```
├── README.md                  you are here
├── brief/                     the official hackathon rules and rubric
├── code/                      the complete pipeline (see code/README.md)
│   ├── fetch_data.py          1. download every raw series
│   ├── econdata_verify.py     2. verify EconData == SARB Web API
│   ├── build_dataset.py       3. build the weekly Friday dataset
│   ├── models_backtest.py     4. walk-forward out-of-sample backtest
│   ├── make_figures.py        5. report charts
│   ├── make_slide_figures.py  6. presentation charts
│   ├── verify_charts.py       7. independent audit of every plotted number
│   ├── make_report.py         8. build the report PDF
│   ├── make_submission.py     assemble the submission package
│   ├── final_check.py         pre-submission audit
│   └── run_all.py             runs the pipeline in order
├── data/
│   ├── raw/                   exactly as downloaded, never edited by hand
│   └── processed/             weekly.csv, forecast_log.csv, metrics.json,
│                              validation_metrics.json, combo_weights.csv
├── figures/                   all charts (slides/ holds the presentation versions)
├── report/                    Project_Report.pdf
├── presentation/              Deck.pptx, Script.md, build_deck.js
└── admin/                     project plan and submission checklist
```

`submission/` is a packaging step and is not tracked here; rebuild it with `python code/make_submission.py`.

---

## Models

| Model | What it is |
|---|---|
| `AR1_log` / `AR1_level` | The required benchmark. OLS AR(1) with intercept on the weekly (log) level, expanding window from 1999, iterated 4 steps. We compare against whichever variant scores better, so we are never beating the weaker one. |
| `RW` | No-change forecast. The strongest single benchmark at this horizon. |
| `CARRY` | Forward-rate tilt: S(t) × (1 + (JIBAR 3M − US T-bill 3M) × 28/365). |
| `RIDGE` | Ridge on the 4-week log return using carry, gold, platinum, broad dollar and VIX z-score. Standardised within each training window, no intercept, penalty by time-ordered cross-validation. |
| `GBM` | Depth-2 gradient boosting under identical discipline, included to measure what flexibility costs here. |
| `COMBO` | **Our submission.** Inverse discounted-MSE weighted average of {RW, CARRY, RIDGE}, weights from resolved past errors only. |

---

## Data sources

| Series | Source | Role |
|---|---|---|
| USDZAR (EXCX135) | SARB via EconData, `MARKET_RATES 1.0.0`, `EXCX135.B.A` | Target |
| JIBAR 3M | SARB Web API | Carry |
| US 3M Treasury bill | FRED (`DTB3`) | Carry |
| Gold, platinum, Brent | SARB, NYMEX, FRED | Commodity block |
| Broad US dollar index, VIX | FRED (`DTWEXBGS`, `VIXCLS`) | Dollar strength and global risk |

Citation: SARB. MARKET_RATES. Version 1.0.0. Pretoria: SARB [producer]. Johannesburg: EconData [distributor], 2026.

---

## What we do not claim

The improvement is **not statistically significant** (Diebold–Mariano p = 0.47). With 261 overlapping forecasts at this signal-to-noise ratio, detecting a difference this size would need an order of magnitude more independent observations. What we claim instead is consistency: the combination beats the benchmark in four years of five, on the full window, on the strict robustness cut, and in the validation era it never saw.

The benchmark is competitive on MAE, and it beats us in 2025 when the rand strengthened back toward its mean. We never tested this as a trading strategy and make no claim about profitability.

## Use of AI

We used Anthropic's Claude as a coding and research assistant: drafting pipeline code, searching the literature, and typesetting the report. The rules permit this. The modelling decisions, validation design and final specification are ours, and we chose OLS, ridge regression and weighted averages precisely so that every component can be derived by hand under questioning.
