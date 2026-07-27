# Presentation Script, built for a 2 to 5 minute slot
**Team Spurious Decision, Aakash Anil and Stefan von der Heyden**

**6 presented slides. Slide 7 is references, slides 8 to 14 are appendix A to G, for questions only.**

Target runtime: **4 minutes 40 seconds** at a calm pace. Inside the 5-minute cap with room to breathe. If the slot is tightened, use the short version at the bottom.

---

## Three rules for a slot this short

1. **The headline numbers are on screen from second one.** Slide 1 shows 0.5600 against 0.5624 before you speak. If you are cut off at ninety seconds, the judges have still seen the result.
2. **Do not explain the task back to them.** They wrote it.
3. **Do not read the slides.** Say the line, let them read the detail.

---

# SLIDE 1, Title [0:00 to 0:40]

> "We're team Spurious Decision, and the name is the warning we set ourselves. A spurious relationship is one that looks real in your data and isn't there in the world. In FX forecasting that's the default outcome, so the whole project was built to avoid one.
>
> At one month the rand is almost a random walk. We didn't try to out-muscle that. We disciplined it. Our RMSE is 0.5600 against the benchmark's 0.5624, over 261 forecasts we can audit."

*Pause. Move on.*

---

# SLIDE 2, The question [0:40 to 1:20]

> "The task: forecast the rand a month ahead, every Friday for five years, and beat an AR(1) on RMSE out of sample.
>
> Why that's hard. Since Meese and Rogoff in 1983, structural exchange-rate models lose to a simple no-change forecast at this horizon, and the honest published gains are one to five per cent. So we set ourselves a second question as well: we asked whether we could also say why.
>
> The answer to both is yes. 0.42 per cent, and the mechanism is a measurable bias in the benchmark itself."

---

# SLIDE 3, Method and rigour [1:20 to 2:15]

> "Three simple pieces. A random walk anchor. A carry tilt, which is just the JIBAR minus US T-bill gap. And a heavily regularised regression on gold, platinum, the dollar index and the VIX. We combine them by inverse recent error, so weight moves toward whatever is actually working.
>
> On the right is why the numbers hold. Every input is dated on or before the forecast Friday. The models train only on forecasts whose outcome had already resolved. Weights are embargoed by 28 days. And every setting was frozen on 2015 to 2020 before we ever touched the judged window. All 261 forecasts are logged. You can audit any one of them."

*Say the right column briskly. They are reading it while you talk.*

---

# SLIDE 4, Why the benchmark loses [2:15 to 3:15]

> "So why is the AR(1) beatable? Its persistence comes out just below one, which means every forecast is pulled toward an implied long-run mean.
>
> We computed that mean at all 261 origins. It sat below the actual spot rate at every single one, by two rand eleven on average. So for five years it was leaning downward against a currency that went from fourteen-sixty up to nearly nineteen-seventy.
>
> The chart is cumulative squared error. Above zero we're ahead. The edge builds right through the 2022-23 trend, peaks at one-point-two-nine, and then gives some back. I'd rather show you that than crop the chart at the peak."

*This is your best slide. If you only nail one, nail this one.*

---

# SLIDE 5, Results [3:15 to 4:10]

> "The numbers. Benchmark 0.5624. Our combination 0.5600, about 0.42 per cent better. Carry and ridge also beat it, so four of five did. The axis starts at 0.50 so the differences are visible, and I'd rather say that than have you spot it.
>
> Two things. On the robustness cut, where every target date falls strictly inside 2025, our combination leads every model we ran, random walk included.
>
> And the one model that loses badly is the gradient booster, by seven and a half per cent. Same data, same discipline. About 850 noisy observations can't support a flexible learner. That's the M4 and M5 finding, and we built it into the design rather than discovering it the hard way."

---

# SLIDE 6, Conclusions [4:10 to 4:40].  LEAVE THIS SLIDE UP FOR Q&A

> "Four things to close on.
>
> The benchmark is beatable and we can say why. The gain is real but small, which is the size of the true signal at this horizon. Discipline beat complexity, and we have the losing machine-learning model to prove it.
>
> And what we don't claim: it isn't statistically significant, p is 0.47. The benchmark wins on MAE and it wins in 2025. And we never tested this as a trading strategy.
>
> Happy to walk through the code line by line. Are there questions or feedback?"

*Say the limitations with confidence, not apology. Then stop talking.*

---

# THE SHORT VERSION

If the slot is tightened on the day. Slides 1, 4, 5, 6. About 1 minute 20.

> "We're Spurious Decision. At one month the rand is almost a random walk, so we didn't fight it, we disciplined it.
>
> **[Slide 4]** The AR(1) benchmark is pulled toward an implied long-run mean that sat below the actual rate at all 261 origins, by two rand on average. It leaned the wrong way for five years, and RMSE punishes that.
>
> **[Slide 5]** Our model combines a random walk, a carry tilt and a shrunk regression, weighted by recent performance. RMSE 0.5600 against 0.5624. Four of five models beat the benchmark. The gradient booster we ran as a control lost by seven and a half per cent, which tells you why simple wins here.
>
> **[Slide 6]** Every setting was frozen on 2015 to 2020 before we touched the judged window, and all 261 forecasts are logged for audit. It is not statistically significant, p is 0.47, and we say so. Thank you."

---

# WHICH SLIDE TO JUMP TO IN Q&A

Know these by number. Fumbling costs more than the answer gains.

| Slide | Contents | Jump to it when asked about |
|---|---|---|
| 7 | References | a source you cited |
| 8 (App. A) | Full results table | any number: MAE, directional accuracy, DM p-values, robustness |
| 9 (App. B) | RMSE by year | consistency, or why 2025 went against you |
| 10 (App. C) | Data and provenance | data sources, EconData, look-ahead bias |
| 11 (App. D) | Combination weights | how the weighting adapts, proof settings were frozen |
| 12 (App. E) | Why ML lost | "why not machine learning / deep learning / an LSTM" |
| 13 (App. F) | Forecasts vs actuals | "show me the forecasts" |
| 14 (App. G) | One forecast by hand | "what does the model actually do" |

---

# Q&A BANK
**Lead with the direct answer, give one supporting fact, then stop. Do not fill silence.**

**Q: Why is your improvement so small?**
"Because that's the size of the true signal at one month. The best published gains are one to five per cent. Improvements much larger than that in this setting usually indicate look-ahead bias rather than skill. We'd rather show you 0.42% that survives an audit than 15% that doesn't."

**Q: Your combination is basically the random walk. Why not just submit that?**
"On the full window they're nearly tied, but in the robustness cut with targets inside 2025 the combination is ahead of it. The deeper answer is that the combination is the random walk plus insurance. When carry had information in 2022 and 23, weight moved to it. When nothing worked in 2024 and 25, it collapsed back to the anchor. A fixed no-change rule can't do that, and we didn't have to know in advance which regime was coming."

**Q: Is 0.42% statistically significant?**
"No, and we say so on the final slide. DM p is 0.47. With around 260 overlapping monthly forecasts you'd need roughly a ten per cent edge for conventional significance. What we claim is consistency, not significance: it holds across four of five years, the robustness cut, and the validation era."

**Q: How do we know you didn't tune on 2021 to 2025?**
"Three artefacts in the submission. The validation grid over 2015 to 2020 that selected the configuration, the frozen config itself, and the forecast log. The feature set, the decay and the sharpness all came from the validation era. Happy to open validation_metrics.json now." *(Slide 9.)*

**Q: Where exactly does the 2.11 rand come from?**
"At each of the 261 origins we refit the AR(1) and compute c over one minus phi, which is the mean it reverts to. We compared that to the spot rate on the day. It was below spot at all 261, and the average gap was 2.11 rand. The script that reproduces it is verify_charts.py in the submission." *(Slide 2.)*

**Q: Why did the gradient booster fail?**
"Sample size against capacity. It fits thresholds and interactions, and with about 850 noisy weekly observations those fitted patterns are regime noise that doesn't repeat. Depth two, learning rate 0.05, L2 regularisation. We didn't sabotage it; the horizon just doesn't contain what it needs." *(Slide 10.)*

**Q: Why no LSTM or deep learning?**
"Same answer with worse odds. An LSTM has orders of magnitude more parameters than a depth-two booster, and the booster already lost by seven and a half per cent. The evidence for deep nets beating no-change at monthly FX horizons under honest evaluation is essentially nil."

**Q: Your AR(1), levels or logs? Estimated how?**
"Both. OLS with intercept, expanding window from 1999, iterated four steps at weekly frequency. Log version 0.5624, level version 0.5629. We compare against the log version because it's the stronger of the two. We didn't pick the weaker one to beat."

**Q: Why 28 days as one month?**
"Forecasts are made every Friday, so the natural target is the Friday four weeks out. It keeps origin and target on the same weekday and avoids month-end irregularity. We ran a calendar-month variant and it changes none of the rankings."

**Q: What about publication lags and revisions?**
"We designed the problem away. No macro releases at all. Every predictor is a daily market price, which is never revised and has no publication lag, so the as-of merge alone gives a true real-time information set. That's also why we left out CPI and GDP despite their theoretical appeal." *(Slide 8.)*

**Q: Why these predictors and not others?**
"Literature first, not search first. Carry from interest parity. Gold and platinum because the rand is a commodity currency. The dollar index and VIX because Codera's own research names dollar strength and risk sentiment among the main rand drivers. We deliberately didn't trawl hundreds of candidates, because that's how you find spurious predictors."

**Q: What was your AI usage?**
"AI was used as a coding assistant and for literature search, which the rules permit. Every modelling decision is ours, and the models are deliberately simple enough that we can derive them by hand: OLS, ridge, and a weighted average. Ask us about any line."
*(Be ready: ridge is OLS plus a penalty on coefficient size, which shrinks noisy coefficients toward zero, with the penalty chosen by time-ordered cross-validation. The DM test is a t-test on the difference of squared errors with Newey-West standard errors, because overlapping four-week forecasts have correlated errors.)*

**Q: If the rand is a random walk, is forecasting pointless?**
"Point forecasts are nearly pointless, and that's useful information in itself: it tells a treasurer to hedge rather than trade on a view. The value beyond the point forecast is in the conditional distribution, which is where we'd take this next with density forecasts."

**Q: Would this make money as a trading strategy?**
"We didn't test it and we won't claim it. RMSE and profit are different objectives. A model can win on RMSE and lose money after costs. That needs transaction costs, position sizing and a Sharpe-based evaluation, which is a different project."

---

# LOGISTICS

- **Who says what.** With a slot this short, one presenter is cleaner than two. If you do split it, one person takes slides 1 to 3 and the other takes 4 and 5. Do not swap more than once.
- **Rehearse with a timer.** Twice minimum. If you land over 4:40, cut the third bullet on slide 2 and the robustness sentence on slide 4.
- **Memorise cold:** 0.5600, 0.5624, +0.42%, 261 forecasts, DM p = 0.47, R2.11 average lean below spot at 261 of 261 origins, minus 7.5% for the booster.
- **If asked something you didn't test:** "We didn't test that, and I'd rather not guess. Our design would answer it by..." That scores higher than bluffing every time.
- **Have open on the laptop:** the deck, Project_Report.pdf, and forecast_log.csv. Being able to show the log within five seconds is worth real marks on the rigour criterion.
