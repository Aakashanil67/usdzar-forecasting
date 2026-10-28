# Forecasting the rand one month ahead

This project forecasts the South African rand against the US dollar four weeks ahead, once a week, for 261 Fridays from 1 January 2021 to 26 December 2025, and scores each forecast against what the rand did. It began as an entry to the SES x Codera Analytics hackathon in July 2026 (team Spurious Decision: Aakash Anil and Stefan von der Heyden, Stellenbosch University). The hackathon required one benchmark, a simple statistical rule called an AR(1) that projects the rate forward from its own history. I have kept working on it since.

## What I found

The score is the typical size of the miss in rand per dollar (RMSE). Lower is better.

| Forecast | Typical miss |
|:---|---:|
| AR(1), the required benchmark | 0.5624 |
| "No change": next month's rate equals today's | 0.5600 |
| My blend of three simple forecasts | 0.5599 |
| The same three forecasts, equally weighted | 0.5599 |
| Gradient boosting, a machine-learning model | 0.5745 |

The blend scored 0.44 per cent better than the AR(1). With 261 forecasts a gap that small is well within what luck produces, and the standard test agrees (p = 0.449). Against "no change" the difference is 0.01 per cent (p = 0.967), so the blend is in practice the no-change forecast with a small tilt. Weighting the three forecasts by their recent accuracy did no better than weighting them equally, and gradient boosting did worst of everything I tried.

The AR(1) pulls its forecasts towards a long-run level that sat below the market at 261 of 261 origins, and it never forecast a rise. That describes how it missed. I have not shown that it is why it lost.

Treat every 2021 to 2025 number as exploratory. The window was scored many times while the code was built and repaired, and the list of comparisons grew along the way. A clean test needs forecasts made after the design is frozen, and the methodology sets one out.

## Run it

```
pip install -r requirements-lock.txt
python src/run_all.py
```

This rebuilds every number, figure, the report, the notebook and the slides from the raw data committed here, with no network access. The slides need Node.js. `pytest -q` runs the checks.

## Where to look

- [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md): the method, the results and their limits.
- [`notebooks/walkthrough.ipynb`](notebooks/walkthrough.ipynb): a short executed walkthrough with charts.
- [`reports/technical_report.pdf`](reports/technical_report.pdf) and [`reports/presentation.pptx`](reports/presentation.pptx): the report and slides.
- [`data/processed/forecast_log.csv`](data/processed/forecast_log.csv): all 261 forecasts from every model, enough to recompute every score above.

Data: SARB. *MARKET_RATES*. Version 1.0.0. Pretoria: SARB [producer]. Johannesburg: EconData [distributor], 2026. The code is MIT licensed and the data terms differ; see [LICENSE](LICENSE).
