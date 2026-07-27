# Code, USDZAR 1-Month-Ahead Forecasting

Team Spurious Decision · SES x Codera Analytics Hackathon

## Reproduce everything

```bash
pip install pandas numpy scikit-learn matplotlib requests reportlab pillow
python code/run_all.py           # steps 1-7 below, about 4 minutes
python code/make_submission.py   # assembles submission/
```

Deterministic (fixed `random_state=42`; OLS and ridge are exact solutions). No API keys, no paid data. Rerunning reproduces every published number to twelve decimal places.

## What each script does

| # | File | Purpose |
|---|---|---|
| 1 | `fetch_data.py` | Downloads USDZAR (SARB EXCX135D), JIBAR 3M and gold from the SARB Web API; US 3M T-bill, VIX, broad USD index and Brent from FRED; platinum from Yahoo Finance. Writes `data/raw/*.csv`. |
| 2 | `econdata_verify.py` | Parses the official EconData export, writes the cleaned target series, and verifies it is numerically identical to the SARB Web API series. Result: 9,141 overlapping observations, max difference 0.000000, zero mismatches. |
| 3 | `build_dataset.py` | Builds the weekly Friday dataset. Every predictor enters via a backward as-of merge, so a forecast at origin *t* can only see data dated on or before *t*. Target = EXCX135 at *t* + 28 days. |
| 4 | `models_backtest.py` | The walk-forward out-of-sample backtest. AR(1) baseline, random walk, carry, ridge, gradient boosting and the inverse discounted-MSE combination. Hyperparameters selected on a 2015–2020 validation era and frozen. Writes `forecast_log.csv`, `metrics.json`, `validation_metrics.json`, `combo_weights.csv`. |
| 5 | `make_figures.py` | RMSE bar chart with values on bars, relative improvement, cumulative squared-error difference, forecasts vs actuals, input-series panel, combination weights, per-year RMSE, summary-statistics table. |
| 6 | `make_report.py` | Builds `report/Project_Report.pdf` from live results. Every number is read from `metrics.json`, nothing is typed by hand. |
| 7 | `make_guide.py` | Builds `report/Complete_Project_Guide.pdf`, the from-first-principles explanation of the whole project. |
| 8 | `make_submission.py` | Assembles `submission/` with the deliverables, a manifest and SHA-256 checksums. |

## Out-of-sample guarantees, what a judge should check

1. **Information sets.** All predictors enter through `merge_asof(..., direction="backward")`. A forecast at origin *t* sees only observations dated ≤ *t*.
2. **No publication lags.** Every predictor is a daily market price or rate, never revised, no release delay, so look-ahead bias is structurally impossible rather than merely avoided.
3. **Resolved-only training.** Ridge and GBM train only on origins whose 28-day target had already resolved: `tr = tr[tr.index <= i - H]`.
4. **Embargoed weights.** Combination weights use only forecast errors already resolved 28 days before the current origin.
5. **Frozen configuration.** Feature set, intercept choice, decay δ and sharpness θ were selected on 2015–2020 (all targets resolving before 2021) and then frozen. The full search grid is in `validation_metrics.json`.
6. **Auditable log.** `data/processed/forecast_log.csv` records all 261 forecasts with origin date, target date, every model's forecast and the realised value.

## Model summary

| Model | One-sentence description |
|---|---|
| `AR1_log` / `AR1_level` | The required benchmark: OLS AR(1) with intercept on the weekly (log) level, expanding window from 1999, iterated 4 steps. We compare against whichever variant scores better. |
| `RW` | No-change forecast, Ŝ = S(t). |
| `CARRY` | Forward-rate tilt: S(t) × (1 + (JIBAR 3M − US T-bill 3M) × 28/365). |
| `RIDGE` | Ridge on the 4-week log return using carry, gold, platinum, broad dollar and VIX z-score. Standardised, no intercept, penalty by time-ordered CV inside the training window. |
| `GBM` | Small gradient-boosting comparator (depth 2) under identical discipline, included to quantify the cost of unconstrained ML at this horizon. |
| `COMBO` | **Our submission.** Inverse discounted-MSE weighted average of {RW, CARRY, RIDGE}, weights from resolved past errors only. |
