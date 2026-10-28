"""
build_notebook.py - Generates notebooks/walkthrough.ipynb

Generated from a single source rather than hand-edited, so it cannot drift out of
step with the pipeline. The cells are executed with nbconvert before the file is
written to notebooks/walkthrough.ipynb, so the committed notebook always carries
its outputs and the file is left alone if a cell fails. Needs the nbconvert and
ipykernel packages from requirements-lock.txt.

Run:  python src/build_notebook.py
"""
import json
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
NB = BASE / "notebooks"
NB.mkdir(exist_ok=True)

cells = []


def _lines(text):
    """nbformat stores source as a list of lines, each keeping its newline."""
    parts = text.strip().split("\n")
    return [p + "\n" for p in parts[:-1]] + [parts[-1]]


def md(text):
    cells.append({"cell_type": "markdown", "metadata": {},
                  "source": _lines(text)})


def code(src):
    cells.append({"cell_type": "code", "execution_count": None,
                  "metadata": {}, "outputs": [], "source": _lines(src)})


# ---------------------------------------------------------------- intro
md("""
# Forecasting USDZAR one month ahead

Can a forecast combination beat an AR(1) benchmark out of sample, and can we say
why?

This notebook walks through the analysis: the data, the models, the out-of-sample
protocol, the results and the statistics. Everything below reads from committed
artefacts, so it runs in seconds and refits nothing. The pipeline that produced
those artefacts is `python src/run_all.py`, which takes about five minutes.

| | |
|---|---|
| Forecasts | 261, one every Friday, 2021-01-01 to 2025-12-26 |
| Horizon | 28 days ahead |
| Our model | Combination of a random walk, a carry tilt and a shrunk ridge |
| Result | RMSE 0.5600 against the AR(1) benchmark's 0.5624, an improvement of 0.42 per cent |
| Significance | Not significant; see section 6 |
""")

code("""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
PROC = ROOT / "data" / "processed"

log = pd.read_csv(PROC / "forecast_log.csv", parse_dates=["origin", "target_date"])
metrics = json.load(open(PROC / "metrics.json"))
stats = json.load(open(PROC / "statistical_tests.json"))

print(f"{len(log)} forecasts, {log.origin.min().date()} to {log.origin.max().date()}")
log.head()
""")

# ---------------------------------------------------------------- 1 problem
md("""
---
## 1. Why this problem is hard

Meese and Rogoff (1983) showed that structural exchange-rate models lose to a
naive no-change forecast out of sample, even when handed the true future values of
their driving variables. Rossi's (2013) survey found the result had largely
survived thirty years of attempts on it.

The mechanism is not mysterious. USDZAR is priced by a deep, liquid market, so
anything publicly knowable is in the price within minutes, and what is left to
forecast a month out is a small and unstable residual. Published improvements over
naive benchmarks run at roughly 1 to 5 per cent in RMSE, and they come from
shrinkage and combination rather than from richer models.

That sets the bar. A result far above that range in this setting points to a data
leak more often than to skill, which is why so much of this project went into
making leakage impossible rather than into model complexity.
""")

# ---------------------------------------------------------------- 2 data
md("""
---
## 2. Data and the information set

The target is EXCX135, the SARB's rand-per-dollar rate, taken from the official
EconData export and checked independently against the SARB Web API: 9 141
overlapping observations, maximum absolute difference 0.000000.

Every predictor is a daily market price or rate.

| Predictor | Why |
|---|---|
| JIBAR 3M minus US 3M T-bill | the carry signal, from covered interest parity |
| Gold, platinum | South Africa exports both, so the commodity-currency channel applies |
| Brent | South Africa imports oil |
| Broad USD index | much of what looks like rand movement is dollar movement |
| VIX | global risk appetite, and the rand trades as a liquid EM proxy |

That was a deliberate constraint. Macro series like CPI and the current account
have a real claim on a rand model, but they are released late and revised
afterwards. Using today's published history inside a simulated 2021 forecast would
mean using numbers that did not exist in 2021. Market prices are known instantly
and never revised, so restricting the information set to them makes look-ahead bias
structurally impossible rather than merely avoided.
""")

code("""
weekly = pd.read_csv(PROC / "weekly.csv", parse_dates=["friday"])
cols = ["spot", "carry_diff", "gold", "platinum", "brent", "usd_broad", "vix"]

fig, axes = plt.subplots(4, 2, figsize=(13, 9), sharex=True)
titles = ["USDZAR (EXCX135)", "JIBAR 3M minus US T-bill 3M", "Gold, USD/oz",
          "Platinum, USD/oz", "Brent, USD/bbl", "Broad USD index", "VIX"]
for ax, c, t in zip(axes.ravel(), cols, titles):
    ax.plot(weekly.friday, weekly[c], lw=0.8, color="#1F5FA8")
    ax.set_title(t, fontsize=10)
    ax.grid(alpha=0.3)
axes.ravel()[-1].axis("off")
fig.suptitle("Every series used, sampled as of each Friday", y=0.995)
fig.tight_layout()
""")

# ---------------------------------------------------------------- 3 protocol
md("""
---
## 3. The out-of-sample protocol

At each Friday `t` we hold only information dated on or before `t`, and forecast
the fixing 28 days later. Five guarantees make that claim auditable.

1. Information sets. Every predictor enters via a backward `merge_asof`.
2. No publication lags. Market prices only, as above.
3. Resolved-only training. The regressions train only on origins whose 28-day
   outcome had already happened: `resolved(w, t)` keeps rows whose target date
   is on or before the origin.
4. Embargoed weights. Combination weights use only errors from forecasts resolved
   28 days before the current origin.
5. Frozen configuration. The feature set, intercept choice, decay and sharpness
   were chosen on validation origins from 2015 to 27 November 2020, the last one
   whose target resolves before 2021,
   then frozen. The judged window never informed a modelling decision.

The fifth is the one most backtests miss. Trying twenty configurations on the
evaluation window and reporting the best makes that best number partly luck, and it
will not repeat. The full search grid is committed in
`data/processed/validation_metrics.json`.

All five are enforced as tests rather than prose. `pytest -q` runs fourteen of
them.
""")

code("""
val = json.load(open(PROC / "validation_metrics.json"))
print("Configuration selected on the validation era and then frozen:")
for k, v in val["chosen_config"].items():
    print(f"  {k:<10} {v}")
print(f"\\nValidation era origins: {val['validation_era']['COMBO']['n']}")
""")

# ---------------------------------------------------------------- 4 models
md("""
---
## 4. The models

| Model | One line |
|---|---|
| AR(1) | The required benchmark. OLS with intercept on the weekly log level, expanding window from 1999, iterated four steps. |
| Random walk | Forecast equals today's rate. The strongest single benchmark at this horizon. |
| Carry | $\\hat S_{t+28d} = S_t\\left(1 + (i^{ZA}_t - i^{US}_t)\\tfrac{28}{365}\\right)$, the covered-interest-parity forward rate. |
| Ridge | 4-week log return on the predictor set chosen in validation (printed above). Scaler and ridge fitted together inside each purged CV fold, penalty re-chosen quarterly, no intercept, so heavy shrinkage collapses the model to the random walk instead of to a stale mean. |
| Gradient boosting | Configuration picked once a year from a 12-point grid by the same purged CV, included to measure what flexibility costs here. |
| Combination | Inverse discounted-MSE weighted average of {RW, carry, ridge}, weights from resolved past errors only. |

The no-intercept choice in the ridge is worth pausing on. Under heavy shrinkage the
predicted return goes to zero, so the forecast becomes $S_t \\cdot e^0 = S_t$ and a
ridge that finds no signal becomes the random walk. The AR(1) instead drifts toward
its long-run mean, which is the failure the next section quantifies.
""")

# ---------------------------------------------------------------- 5 why
md("""
---
## 5. Why the benchmark loses: a measurable bias

An AR(1) has persistence $\\phi$. Ours estimates between 0.9971 and 0.9986, just
below one, so every forecast gets pulled toward an implied long-run mean:

$$\\mu = \\frac{c}{1-\\phi}$$

We recomputed $\\mu$ at all 261 origins and compared it with that day's spot rate.
What comes out is the core finding of the project.
""")

code("""
# Refit the AR(1) at every origin and compare its implied mean with spot.
mus, phis = [], []
for t in log["origin"]:
    h = weekly[weekly.friday <= t]["spot"].dropna().values
    y = np.log(h)
    X = np.column_stack([np.ones(len(y) - 1), y[:-1]])
    c, phi = np.linalg.lstsq(X, y[1:], rcond=None)[0]
    mus.append(np.exp(c / (1 - phi)))
    phis.append(phi)

mus, phis = np.array(mus), np.array(phis)
gap = log["spot"].values - mus

print(f"phi ranges {phis.min():.4f} to {phis.max():.4f}")
print(f"implied mean ranges R{mus.min():.2f} to R{mus.max():.2f}")
print(f"below spot at {(mus < log['spot'].values).sum()} of {len(log)} origins")
print(f"average gap R{gap.mean():.2f}, smallest R{gap.min():.2f}")
""")

code("""
fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(log.origin, log.spot, color="#0E2A3B", lw=2, label="USDZAR spot")
ax.plot(log.origin, mus, color="#B03A2E", lw=2, ls="--",
        label="AR(1) implied long-run mean")
ax.fill_between(log.origin, mus, log.spot, color="#B03A2E", alpha=0.13)
ax.set_title("The AR(1) leaned below the market at every one of the 261 origins",
             fontsize=13, color="#0E2A3B")
ax.set_ylabel("Rand per US dollar")
ax.legend(frameon=False)
ax.grid(alpha=0.3)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
fig.tight_layout()
""")

md("""
The shaded band is the bias. A mean-reverting model applied to a trending series
pulls every forecast the wrong way, and because RMSE squares errors, the occasional
large miss that produces does most of the damage.

Our models do not predict the rand better in any deep sense. They decline to make
this one mistake.
""")

# ---------------------------------------------------------------- 6 results
md("""
---
## 6. Results, and an honest reading of the statistics
""")

code("""
rows = []
base = metrics["AR1_log"]["rmse"]
for m in ["AR1_log", "RW", "CARRY", "RIDGE", "GBM", "COMBO"]:
    rows.append({
        "model": m,
        "RMSE": round(metrics[m]["rmse"], 4),
        "MAE": round(metrics[m]["mae"], 4),
        "vs AR(1) %": round(100 * (1 - metrics[m]["rmse"] / base), 2),
        "DM p vs AR(1)": metrics[m].get("dm_vs_ar1", [None, None])[1],
    })
pd.DataFrame(rows).set_index("model")
""")

md("""
Four of five models beat the benchmark. Gradient boosting, run under identical
rules, loses by 7.5 per cent.

Two comparisons were fixed in advance: the combination against the AR(1) and
against the random walk. The rest are exploratory and carry Holm-adjusted p-values.
The planning table asks how many weekly origins a future holdout would need to
detect RMSE cuts of 1, 2 and 5 per cent.
""")

code("""
pre = [c for c in stats["comparisons"] if c["role"] == "prespecified"]
display(pd.DataFrame([{"comparison": f"{c['model']} vs {c['benchmark']}",
                       "RMSE diff": round(c["rmse_difference"], 5),
                       "DM (lag 3)": round(c["by_lag"]["3"]["dm"], 3),
                       "p": round(c["by_lag"]["3"]["p"], 3)} for c in pre]))
pd.DataFrame([dict(benchmark=b, **r) for b, t in stats["planning"]["vs"].items()
              for r in t["rows"]]).round(3)
""")

md("""
What can honestly be claimed is consistency.
The combination beats the benchmark in four years of five, on the full window, on a
stricter robustness cut, and in the validation era it never saw.

Claiming more than that would be wrong, and the rolling view below shows how thin
the margin really is.
""")

code("""
win = 52
roll = {m: np.sqrt(pd.Series((log[m] - log["realized"]).values ** 2,
                             index=log.origin).rolling(win).mean())
        for m in ["COMBO", "AR1_log"]}
ratio = (roll["COMBO"] / roll["AR1_log"]).dropna()

fig, ax = plt.subplots(figsize=(12, 4.6))
ax.fill_between(ratio.index, 1, ratio.values, where=(ratio.values < 1),
                color="#1A7A4A", alpha=0.3, interpolate=True, label="ours ahead")
ax.fill_between(ratio.index, 1, ratio.values, where=(ratio.values >= 1),
                color="#B03A2E", alpha=0.22, interpolate=True, label="benchmark ahead")
ax.plot(ratio.index, ratio.values, color="#0E2A3B", lw=1.8)
ax.axhline(1, color="#444444", lw=1.2)
ax.set_ylabel("52-week rolling RMSE ratio")
ax.set_title("The edge is real but thin, and it is regime dependent", fontsize=12.5)
ax.legend(frameon=False, ncol=2)
ax.grid(alpha=0.3)
fig.tight_layout()

print(f"ahead of the benchmark in {100 * (ratio < 1).mean():.0f}% of rolling windows")
""")

# ---------------------------------------------------------------- 7 example
md("""
---
## 7. One forecast, end to end

A single origin with every number on it. Friday 3 June 2022, spot R15.4117, target
1 July 2022, actual R16.3482.
""")

code("""
r = log[log.origin == "2022-06-03"].iloc[0]
w = pd.read_csv(PROC / "combo_weights.csv", index_col=0, parse_dates=True)
wr = w.loc[pd.Timestamp("2022-06-03")]

for m in ["RW", "CARRY", "AR1_log", "RIDGE", "GBM", "COMBO"]:
    print(f"{m:<9} forecast {r[m]:.4f}   error {r[m] - r['realized']:+.4f}")
print(f"\\nweights: RW {wr.RW:.3f}, carry {wr.CARRY:.3f}, ridge {wr.RIDGE:.3f}")
print(f"check:   {wr.RW:.3f}*{r.RW:.4f} + {wr.CARRY:.3f}*{r.CARRY:.4f}"
      f" + {wr.RIDGE:.3f}*{r.RIDGE:.4f} = "
      f"{wr.RW * r.RW + wr.CARRY * r.CARRY + wr.RIDGE * r.RIDGE:.4f}")
""")

md("""
Every model was too low that month. The ordering is what matters: the AR(1) has the
largest error of the six, because its implied mean that day was R13.01 and that
pull dragged its forecast down at exactly the moment the rand was rising.

Notice also how tightly the forecasts cluster. From 15.386 to 15.467, a spread of
eight cents, against an actual move of 94 cents. At a one-month horizon no
defensible model strays far from the current price. The competition between models
is fought inside those few cents, which is why 0.42 per cent is a real result and
why a claimed 20 per cent should invite scepticism rather than admiration.
""")

# ---------------------------------------------------------------- 8 close
md("""
---
## 8. What I would claim, and what I would not

What I would claim: an auditable out-of-sample design over 261 origins, an
improvement of 0.42 per cent in RMSE that holds across four years of five and a
stricter robustness cut, and an economic explanation for it that can be quantified
rather than asserted.

What I would not: statistical significance. Directional predictability, which sits
near 50 per cent for every model. Profitability, which was never tested and is a
different objective from RMSE. Or that the advantage persists, since 2025 goes the
other way once the rand strengthens back toward the benchmark's mean.

Where I would go next, in order of expected value.

1. Option-implied volatility and risk reversals. Greenwood-Nimmo, Steenkamp and van
   Jaarsveld (SARB WP/22/14) find that distributional information about rand
   returns improves forecasts. The most promising unexplored input.
2. Density rather than point forecasts. For a treasurer deciding whether to hedge
   the distribution is the decision-relevant object, and it is where forecasting a
   near-random-walk series adds real value.
3. Bayesian model averaging over a wider component set, which handles model
   uncertainty more formally than inverse-error weights.
4. Horizon sensitivity. Repeat at 1, 2, 8 and 12 weeks to map where the benchmark's
   mean-reversion bias starts to bite.

---

*Built for the SES x Codera Analytics Hackathon, July 2026. Full write-up in
[`docs/METHODOLOGY.md`](../docs/METHODOLOGY.md), technical report in
[`reports/technical_report.pdf`](../reports/technical_report.pdf).*
""")

nb = {"cells": cells,
      "metadata": {"kernelspec": {"display_name": "Python 3",
                                  "language": "python", "name": "python3"},
                   "language_info": {"name": "python", "version": "3.10"}},
      "nbformat": 4, "nbformat_minor": 5}

out = NB / "walkthrough.ipynb"
draft = NB / "_draft.ipynb"
draft.write_text(json.dumps(nb, indent=1), encoding="utf-8")
try:
    subprocess.run([sys.executable, "-m", "jupyter", "nbconvert", "--to", "notebook",
                    "--execute", "--output", out.name, str(draft)], check=True)
finally:
    draft.unlink()
print("written:", out, f"({len(cells)} cells, executed)")
