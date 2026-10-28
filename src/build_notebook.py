"""
build_notebook.py - Generates notebooks/walkthrough.ipynb

Generated from a single source rather than hand-edited. Every number in the
markdown is filled in from the saved outputs by render_docs.fill(), so the text
cannot drift from the pipeline. The cells are executed with nbconvert before the file is
written to notebooks/walkthrough.ipynb, so the committed notebook always carries
its outputs and the file is left alone if a cell fails. Needs the nbconvert and
ipykernel packages from requirements-lock.txt.

Run:  python src/build_notebook.py
"""
import json
import subprocess
import sys
from pathlib import Path

from render_docs import fill

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
                  "source": _lines(fill(text))})


def code(src):
    cells.append({"cell_type": "code", "execution_count": None,
                  "metadata": {}, "outputs": [], "source": _lines(src)})


# ---------------------------------------------------------------- intro
md("""
# Forecasting USDZAR one month ahead

Does a forecast combination beat the mandated AR(1) benchmark out of sample?

Everything below reads the saved outputs of `python src/run_all.py`, so it runs
in seconds and refits nothing.

| | |
|---|---|
| Forecasts | {{n_origins}}, one every Friday, {{first_origin}} to {{last_origin}} |
| Horizon | 28 days ahead |
| Combination | A weighted average of a random walk, a carry tilt and a shrunk ridge |
| Result | RMSE {{rmse_combo}} against {{rmse_ar1_log}} for the AR(1), {{gain_vs_ar1}} per cent lower; {{rmse_rw}} for the random walk |
| Significance | Not established against the AR(1) (p = {{p_combo_ar1}}) or the random walk (p = {{p_combo_rw}}); see section 6 |
| Status | All 2021 to 2025 results are exploratory |
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

Meese and Rogoff (1983) found that structural exchange-rate models lose to a
no-change forecast out of sample, even when handed the true future values of
their driving variables. Rossi's (2013) survey finds that forecasting success
depends on the sample, the predictor, the horizon and the benchmark.

A common explanation is that USDZAR is priced by a deep market, so public
information is in the price quickly and a month-ahead forecast is left with a
small residual. That is plausible, and nothing here tests it.

For the design it means differences between sensible forecasts will be small, and
a large improvement would be a reason to look for leakage first. Much of this
project went into making leakage hard to introduce, and into tests that fail if
it appears.
""")

# ---------------------------------------------------------------- 2 data
md("""
---
## 2. Data and the information set

The target is EXCX135, the SARB's rand-per-dollar rate, taken from the official
EconData export and checked independently against the SARB Web API: {{overlap_n}}
overlapping observations, largest absolute difference {{overlap_max_diff}}.

The predictors are daily market prices and rates.

| Predictor | Why |
|---|---|
| JIBAR 3M minus US 3M T-bill | the carry signal, from covered interest parity |
| Gold, platinum | South Africa exports both, so the commodity-currency channel applies |
| Brent | South Africa imports oil |
| Broad USD index | much of what looks like rand movement is dollar movement |
| VIX | global risk appetite, and the rand trades as a liquid EM proxy |

Macro series like CPI and the current account have a claim on a rand model, but
they are released late and revised afterwards, and the repository holds no
vintages for them, so they are left out.

The market series are not free of timing problems either. The forecast is issued
at 17:00 Johannesburg time on the Friday, and each series enters only once it was
public by then: Wednesday's T-bill rate, Thursday's VIX and platinum, the previous
Friday's dollar index, Brent up to the Monday. The dollar index, Brent, the T-bill
rate and the VIX are revised, so they carry the value the ALFRED vintage archive
showed at the time. `data/raw/series_metadata.json` holds each rule and its
source, and `weekly.csv` keeps the observation date and the publication time of
every input.
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
fig.suptitle("Every series used, as known at each Friday issuance", y=0.995)
fig.tight_layout()
""")

# ---------------------------------------------------------------- 3 protocol
md("""
---
## 3. The out-of-sample protocol

At each Friday `t` a forecast may use only what was public by 17:00 Johannesburg
time that day, and forecasts the fixing 28 days later. Five rules make that
auditable.

1. Publication time. Every predictor joins on when its value became public, with
   the vintage then current for revised series.
2. Resolved-only training. A row of training data counts at origin `t` only once
   its target date is on or before `t`: `resolved(w, t)` filters on target dates.
3. Purged cross-validation. Ridge and boosting settings are chosen by time-ordered
   folds that drop training rows whose target date reaches into the validation
   fold, and the scaler is fitted inside each fold.
4. Embargoed weights. Combination weights use only errors from forecasts resolved
   by the current origin.
5. Selection before the judged window. The ridge variant, decay and sharpness were
   chosen on validation origins from {{val_first}} to {{val_last}}, the last whose
   target ({{val_last_target}}) falls before 2021. Those scores were used for
   selection, so they are not independent evidence. The full grid is in
   `data/processed/validation_metrics.json`.

The tests enforce these. One scrambles every raw input dated after a sampled
origin and requires each model's forecast at that origin to be unchanged. `pytest -q`
runs them.
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
| Ridge | 4-week log return on the predictor set chosen in validation (printed above). Scaler and ridge fitted together inside each purged CV fold, penalty re-chosen every 13 origins, no intercept, so heavy shrinkage collapses the model to the random walk. |
| Gradient boosting | Configuration picked every {{gbm_retune_every}} weeks from {{gbm_grid_n}} combinations by the same purged CV, included as a flexible comparator. |
| Combination | Inverse discounted-MSE weighted average of {RW, carry, ridge}, weights from resolved past errors only. |

Carry is the covered-interest-parity forward rate. It prices a forward contract and
is not an expected spot rate, and the three-month rates behind it do not match a
28-day horizon, so it is one component and not a claim about forecasting skill.

The no-intercept choice in the ridge matters. Under heavy shrinkage the predicted
return goes to zero, so the forecast becomes $S_t \\cdot e^0 = S_t$ and a ridge that
finds no signal becomes the random walk.
""")

# ---------------------------------------------------------------- 5 why
md("""
---
## 5. What the AR(1) does differently

An AR(1) has persistence $\\phi$. Ours estimates between {{phi_min}} and {{phi_max}},
just below one, so every forecast gets pulled towards a long-run level. For the log
series that level is

$$\\mu = \\exp\\left(\\frac{c}{1-\\phi}\\right)$$

which is fragile near a unit root, because $1-\\phi$ is small. We recomputed $\\mu$ at
all {{n_origins}} origins and compared it with that day's spot rate.
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
ax.set_title(f"The AR(1)'s implied long-run level was below spot at "
             f"{(mus < log['spot'].values).sum()} of {len(log)} origins",
             fontsize=13, color="#0E2A3B")
ax.set_ylabel("Rand per US dollar")
ax.legend(frameon=False)
ax.grid(alpha=0.3)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
fig.tight_layout()
""")

md("""
The shaded band is the gap between spot and the level the AR(1) is pulled towards. The
AR(1) never forecast a rise ({{ar1_up_pct}} per cent of origins), and its mean error
was {{ar1_bias}} against {{combo_bias}} for the combination. Squared bias is
{{bias_share_of_gap_pct}} per cent of the AR(1)'s excess squared error against the
combination, and the rest is variance.

These are observations. I have not shown that the downward lean is the whole reason
the AR(1) scored worse, or that it would persist in another sample.
""")

# ---------------------------------------------------------------- 6 results
md("""
---
## 6. Results
""")

code("""
rows = []
base = metrics["AR1_log"]["rmse"]
for m in ["AR1_log", "RW", "CARRY", "RIDGE", "GBM", "COMBO", "EQUAL3"]:
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
{{n_beat_ar1}} of the {{n_core_models}} core models scored below the AR(1), but the
margins are small. The random walk scores {{rmse_rw}} and an equal-weight average of
the three components {{rmse_equal3}}, so the adaptive weighting adds nothing we can
measure. Gradient boosting scores {{rmse_gbm}}, the highest of the {{n_models}}
models, and that holds for this specification only.

Two comparisons were fixed in advance: the combination against the AR(1) and
against the random walk. The rest are exploratory and carry Holm-adjusted p-values
({{n_holm_significant}} of {{n_exploratory}} survive). The planning table asks how
many weekly origins a future holdout would need to detect RMSE cuts of 1, 2 and 5
per cent, under stated assumptions. Against the random walk the numbers are small
only because the two forecasts are nearly identical.
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
The combination is below the AR(1) in {{years_ahead_n}} of {{years_n}} years
({{years_ahead}}) and above it in {{years_behind}}. The cuts that look consistent
(the full window, the strict cut with targets inside 2025, the validation era) are
views of the same data or were used for selection, so they are not independent
confirmation. The rolling view below shows how thin the margin is.
""")

code("""
win = 52
roll = {m: np.sqrt(pd.Series((log[m] - log["realized"]).values ** 2,
                             index=log.origin).rolling(win).mean())
        for m in ["COMBO", "AR1_log"]}
ratio = (roll["COMBO"] / roll["AR1_log"]).dropna()

fig, ax = plt.subplots(figsize=(12, 4.6))
ax.fill_between(ratio.index, 1, ratio.values, where=(ratio.values < 1),
                color="#1A7A4A", alpha=0.3, interpolate=True, label="combination ahead")
ax.fill_between(ratio.index, 1, ratio.values, where=(ratio.values >= 1),
                color="#B03A2E", alpha=0.22, interpolate=True, label="AR(1) ahead")
ax.plot(ratio.index, ratio.values, color="#0E2A3B", lw=1.8)
ax.axhline(1, color="#444444", lw=1.2)
ax.set_ylabel("rolling RMSE ratio")
ax.set_title("52-week rolling RMSE, combination over AR(1)", fontsize=12.5)
ax.legend(frameon=False, ncol=2)
ax.grid(alpha=0.3)
fig.tight_layout()

print(f"ahead of the benchmark in {100 * (ratio < 1).mean():.0f}% of rolling windows")
""")

# ---------------------------------------------------------------- 7 example
md("""
---
## 7. One forecast, end to end

A single origin with every number on it. {{ex_origin}}, spot R{{ex_spot}}, target
{{ex_target}}, actual R{{ex_realized}}.
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
{{ex_all_too_low}}. The AR(1) has the largest error of the six. Its fit that day had
phi = {{ex_ar1_phi}} and a long-run level of R{{ex_ar1_mu}}, against spot of
R{{ex_spot_short}}.

The forecasts range from {{ex_forecast_low}} to {{ex_forecast_high}}, a spread of
{{ex_spread_cents}} cents, against an actual move of {{ex_move_cents}} cents. At a
one-month horizon the models stay close to the current price.
""")

# ---------------------------------------------------------------- 8 close
md("""
---
## 8. What the results support, and what they do not

What they support: an out-of-sample design with checks that can fail, over
{{n_origins}} origins, and a combination whose RMSE ({{rmse_combo}}) is
{{gain_vs_ar1}} per cent below the AR(1)'s ({{rmse_ar1_log}}) and level with the
random walk's ({{rmse_rw}}).

What they do not: a statistically established improvement over either benchmark,
any advantage for adaptive weighting over equal weights, directional information
(the combination forecast a rise at {{combo_up_pct}} per cent of origins and its
directional accuracy of {{combo_dir_acc_pct}} per cent equals the share of rises),
profitability, which was never tested, or persistence outside this sample.

All 2021 to 2025 results are exploratory: the window was scored repeatedly while the
code was built and repaired, and comparisons were added after earlier results had
been seen. `docs/METHODOLOGY.md` sets out a prospective-holdout protocol.

Where I would go next.

1. Option-implied volatility and risk reversals. Greenwood-Nimmo, Steenkamp and van
   Jaarsveld (SARB WP/22/14) report that distributional information about rand
   returns improves forecasts.
2. Density rather than point forecasts, which matter more for hedging decisions.
3. Bayesian model averaging over a wider component set.
4. Horizon sensitivity: repeat at 1, 2, 8 and 12 weeks.

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
