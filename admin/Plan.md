# SES x Codera Hackathon, Project Plan
**Team Spurious Decision, Aakash Anil, Stefan von der Heyden**
**Goal: Win. Deadline: Monday 27 July 2026, 23:59. Presentation + prize-giving: Tuesday 28 July, 18:00–21:00.**

## 0. Execution environment
Entire project runs in Cowork (this session). Cowork has the shell, Python, file access, and PDF/PPTX generation, Claude Code adds nothing for this task. All files live in `C:\Users\aakas\Documents\Projects\Hackathon`.

## 1. The task (from Rules.pdf)
- 1-month-ahead USDZAR forecasts made **every Friday**, out of sample, forecast-error window **1 Jan 2021 – 31 Dec 2025**.
- Target series: SARB **EXCX135** (rand per US dollar, daily 10:30 weighted average) via EconData.
- Compare RMSE of our model vs an **AR(1)** baseline. Chart RMSEs with numbers on the chart.
- Describe model + data, summary statistics, observation counts, plots of all series used.
- Prove true out-of-sample discipline. Share code. AI allowed but must be fully explainable.

## 2. Rubric → strategy (50 pts)
| Criterion (10 each) | How we win it |
|---|---|
| Model performance vs AR(1) | Combination model beats AR(1) decisively (AR(1) mean-reverts to stale means over a trending 2021–25 rand; even RW beats it). Also aim to edge RW, Codera's own credibility bar. |
| Methodology & rigor | Strict expanding-window walk-forward; only data dated ≤ each Friday; **financial-market predictors only (no publication lags, no revisions)**; forecast log CSV as proof; Diebold–Mariano test. |
| Code quality & defense | Small, clean, seeded, one-command reproducible pipeline; README; every model explainable in 2 sentences. |
| Data visualization | RMSE bar chart with numbers, cumulative squared-error-difference curve, forecast-vs-actual overlay, predictor small-multiples, summary-stats table. |
| Presentation & intuition | Story: "Don't fight the random walk, discipline it." Cite Meese–Rogoff, M4/M5 lessons, and Codera's own BMA/combination philosophy. Scripted talk + rehearsed Q&A. |

## 3. Research conclusions (basis for design)
- [Certain] Meese–Rogoff: fundamentals rarely beat naive at 1-month; realistic edge is 1–5% RMSE via shrinkage/combination (Amat–Michalski–Stoltz; Darvas).
- [Likely] AR(1)-in-levels on long samples is a weak baseline in trending regimes → beatable.
- Commodity-factor and carry signals help commodity currencies (incl. ZAR) modestly; volatility/risk info helps direction.
- M4/M5/Kaggle: **ensembles of simple models win**; rolling-origin validation is non-negotiable; complexity loses.
- Judges (Codera) publish combination/BMA fundamentals models for the rand, our approach speaks their language.

## 4. Forecast protocol (locked)
- **Origin grid:** every Friday t from 2021-01-01 to 2025-12-31 (~261 origins).
- **Target:** EXCX135 value at t+28 calendar days (the Friday 4 weeks ahead); if no fixing that day, last available fixing on or before the target date. Interpretation of "1-month ahead" documented; calendar-month robustness check included.
- **Information set at t:** all series with observation date ≤ t. Daily market data only → no vintage/lag issues.
- **Estimation sample:** daily from 1999 (floating-rand, inflation-targeting era), weekly (Friday) frequency, expanding window re-estimated at every origin.
- **Metrics:** RMSE (headline), MAE, directional accuracy; DM tests vs AR(1) and vs RW; per-year RMSE; full forecast log saved to CSV.

## 5. Model suite
1. **AR(1)** on weekly log level, intercept, expanding window, iterated 4 steps, the required baseline, implemented faithfully.
2. **Random walk** (no-change), the honest benchmark.
3. **Carry / forward-rate:** ŝ_{t+4w} = s_t × (1 + (i^ZA_t − i^US_t)·28/365), JIBAR 3M vs US 3M T-bill.
4. **Regularised fundamentals (ridge/LASSO)** on 4-week log return: interest differential (level, Δ), gold/platinum/Brent 4-week returns, VIX (z-score, Δ), broad USD index return, own momentum (4w, 12w), deviation from 200-day MA. Standardised, expanding window, penalty chosen by time-series CV inside the training window only.
5. **Gradient boosting (small)** on same features, breadth + ML talking point; capped depth to avoid overfit.
6. **Combination (headline): inverse-MSFE weights over {RW, carry, ridge} with shrinkage toward RW**, weights from past OOS errors only (rolling window), first year uses equal weights (burn-in, no peeking).

Rules allow multiple models, judged on the most accurate, we report the suite, headline the winner.

## 6. Data sources (all tested and working)
| Series | Source | Code |
|---|---|---|
| USDZAR daily (target) | SARB Web API (identical series to EconData EXCX135) + EconData pull for official comparability | EXCX135D |
| JIBAR 3M | SARB Web API | MMRD403A |
| US 3M T-bill | FRED | DTB3 |
| VIX | FRED | VIXCLS |
| Broad USD index | FRED | DTWEXBGS |
| Brent | FRED | DCOILBRENTEU |
| Gold (USD, London) | SARB Web API | GDPL201D |
| Platinum futures | Yahoo Finance | PL=F |

EconData: Aakash registers free account → generate 1-hour API token → run `code/00_econdata_pull.py` before submission to produce the official EXCX135 extract; pipeline verifies it matches the SARB API series.

## 7. Deliverables & file map
```
Hackathon/
  Plan.md                      ← this file
  code/                        ← numbered scripts + README, one-command run
  data/raw/  data/processed/   ← CSVs incl. forecast_log.csv (OOS proof)
  figures/                     ← all charts (PNG, 300dpi)
  report/Project_Report.pdf    ← living document, regenerated at every milestone
  presentation/Deck.pptx       ← judge-facing deck mapped to rubric
  presentation/Script.md       ← word-for-word talk track + Q&A prep
```

## 8. Timeline (60h to deadline)
- **Sat:** pipeline + backtest running end-to-end, first RMSEs, report v1. ✅ target today
- **Sun:** model tuning/robustness, all figures final, report v2, deck built, script drafted.
- **Mon:** EconData official pull with Aakash's token, full clean rerun, report final, deck final, rehearse Q&A, **submit well before 23:59 to 28399323@sun.ac.za with completed submission form**.
- **Tue:** rehearse with script; present.

## 9. Aakash's to-dos (cannot be automated)
1. Confirm team of 2–4 is registered via poster link. **Blocking for eligibility.**
2. Register free account at econdata.co.za (needed Monday for official pull).
3. Obtain the submission form referenced in the rules (from SES/info session), not in the folder.
4. Rehearse the script Sunday night + Monday.
