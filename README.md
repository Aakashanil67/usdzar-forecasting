# Forecasting the rand one month ahead

Nothing I built forecasts the rand meaningfully better than the simplest rule there is: assume that in four weeks it will be where it is today. Over 261 weekly forecasts, my blend of three models missed by 0.5599 rand per dollar in a typical week. The no-change rule missed by 0.5600. That is a gap of 0.01 per cent (p = 0.967), which is noise.

The project began as an entry to the SES x Codera Analytics hackathon in July 2026 (team Spurious Decision: Aakash Anil and Stefan von der Heyden, Stellenbosch University). Entrants had to beat an AR(1), a statistical rule that projects the exchange rate forward from its own history. The blend does beat it, by 0.44 per cent (0.5599 against 0.5624), but 261 forecasts cannot tell a gap that small from luck. The data are consistent with anything from a 1.6 per cent improvement to a 0.7 per cent deterioration (95 per cent interval; p = 0.449).

## The forecasts

Every Friday from 1 January 2021 to 26 December 2025, each model forecasts the rand per US dollar four weeks ahead. The forecast is then scored against the South African Reserve Bank's rate on the target date. Each forecast uses only data that had been published by 17:00 Johannesburg time that Friday. The tests check this by scrambling everything published later and confirming that no forecast moves.

The score below is the typical size of the miss in rand per dollar (root mean squared error). Lower is better.

| Forecast | Typical miss |
|:---|---:|
| No change: the rate in four weeks equals today's | 0.5600 |
| My blend of three simple forecasts | 0.5599 |
| The same three, weighted equally | 0.5599 |
| AR(1), the benchmark the hackathon required | 0.5624 |
| Gradient boosting, a machine-learning model | 0.5745 |

Three things stand out. Weighting the blend's parts by their recent accuracy did no better than weighting them equally, because the parts make almost identical errors. Gradient boosting did worst, about 2.6 per cent behind no change. That is one setup on one dataset, not a verdict on machine learning. The AR(1) pulled every forecast towards a long-run level that sat below the market at 261 of 261 origins, so it never once forecast a rise. That explains how it missed. Whether it explains why it lost is still open.

Read all of these numbers as exploratory. I scored the 2021 to 2025 window many times while building and repairing the code, and the list of comparisons grew along the way. A clean test needs forecasts made after the design is frozen; the methodology sets out how that will be done.

## Reproducing the results

```
pip install -r requirements-lock.txt
python src/run_all.py
```

The second command rebuilds every number, figure and table, along with the report, the notebook and the slides, from the raw data committed in `data/raw/`. It needs Python 3.12 and Node.js, makes no network calls, and takes five to ten minutes on a laptop, most of it the backtest. `python src/run_all.py --refresh` downloads fresh data into a separate snapshot instead, and `pytest -q` runs the checks.

## Where to look

- [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) covers the models, the data timing, the statistical tests and the limits of what they show.
- [`notebooks/walkthrough.ipynb`](notebooks/walkthrough.ipynb) is a short walkthrough with charts.
- [`reports/technical_report.pdf`](reports/technical_report.pdf) and [`reports/presentation.pptx`](reports/presentation.pptx) are the report and the slides.
- [`data/processed/forecast_log.csv`](data/processed/forecast_log.csv) holds every forecast from every model, enough to recompute each score above.

Data: SARB. *MARKET_RATES*. Version 1.0.0. Pretoria: SARB [producer]. Johannesburg: EconData [distributor], 2026. Other series come from FRED, ALFRED and Yahoo Finance; [`data/raw/series_metadata.json`](data/raw/series_metadata.json) lists each source and its publication schedule. The code is MIT licensed and the data terms differ; see [LICENSE](LICENSE).
