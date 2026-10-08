// make_presentation.js — SES x Codera hackathon deck.
//
// Structure follows academic presentation discipline (action titles, one
// exhibit per results slide, annotated findings, references, conclusions last)
// but keeps a bold visual treatment: dark title and closing slides, large
// figures, and a single strong accent colour. Judges here are practising
// econometricians, so the deck aims to look confident rather than decorated.
//
// 6 presented slides (~4:40) + references + 7 appendix slides.
// Run: node make_presentation.js
const pptxgen = require("pptxgenjs");
const path = require("path");

const FIG = path.join(__dirname, "..", "figures");
const SFIG = path.join(FIG, "presentation");
const MET = require(path.join(__dirname, "..", "data", "processed", "metrics.json"));
const VAL = require(path.join(__dirname, "..", "data", "processed", "validation_metrics.json"));

// three content colours plus neutrals
const NAVY = "0E2A3B";    // primary / dark slides
const FOCAL = "1A7A4A";   // our model
const AMBER = "C9A227";   // call-outs, key figures
const INK = "1F2937";
const MUTED = "6B7280";
const PALE = "F1F6F3";
const RULE = "D6DEE6";
const F = "Arial";

const r4 = (x) => x.toFixed(4);
const base = MET.AR1_log.rmse, combo = MET.COMBO.rmse;
const impr = (100 * (1 - combo / base)).toFixed(2);
const gbmLoss = (100 * (MET.GBM.rmse / base - 1)).toFixed(1);

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";              // 13.333 x 7.5 inches
pres.author = "Spurious Decision - Aakash Anil, Stefan von der Heyden";
pres.title = "Forecasting USDZAR one month ahead";

const M = 0.62;                            // left margin
const W = 12.1;                            // content width

function dark() {
  const s = pres.addSlide();
  s.background = { color: NAVY };
  return s;
}

/* Action-title slide: complete sentence stating the takeaway, thin rule under. */
function slide(actionTitle, opts = {}) {
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  const two = actionTitle.length > 58;
  s.addText(actionTitle, {
    x: M, y: 0.34, w: W, h: two ? 1.0 : 0.66, fontFace: F, fontSize: 26,
    bold: true, color: NAVY, margin: 0, valign: "top",
  });
  const ruleY = two ? 1.36 : 1.06;
  s.addShape(pres.ShapeType.rect, {
    x: M, y: ruleY, w: W, h: 0.02, fill: { color: RULE }, line: { color: RULE },
  });
  if (opts.appendix)
    s.addText(opts.appendix, {
      x: M, y: 0.06, w: W, h: 0.26, fontFace: F, fontSize: 13, italic: true,
      color: MUTED, margin: 0,
    });
  s.__bodyY = ruleY + 0.16;
  return s;
}

function cite(s, txt) {
  s.addText(txt, { x: M, y: 6.92, w: W, h: 0.3, fontFace: F, fontSize: 13,
    color: MUTED, margin: 0 });
}

function sectionHead(s, txt, x, y, w) {
  s.addText(txt, { x, y, w, h: 0.34, fontFace: F, fontSize: 20, bold: true,
    color: FOCAL, margin: 0 });
}

/* ================= 1. TITLE ========================================== */
{
  const s = dark();
  s.addText("Don't fight the random walk.\nDiscipline it.", {
    x: 0.9, y: 0.95, w: 11.5, h: 1.8, fontFace: F, fontSize: 42, bold: true,
    color: "FFFFFF", margin: 0, lineSpacingMultiple: 1.05,
  });
  s.addShape(pres.ShapeType.rect, { x: 0.9, y: 2.95, w: 2.2, h: 0.05,
    fill: { color: AMBER }, line: { color: AMBER } });
  s.addText("A combination of three simple models forecasts USDZAR one month ahead more accurately than the AR(1) benchmark, over 261 out-of-sample forecasts.",
    { x: 0.9, y: 3.2, w: 10.9, h: 0.85, fontFace: F, fontSize: 19,
      color: "CADCFC", margin: 0 });

  const stats = [[r4(combo), "our RMSE"], [r4(base), "AR(1) benchmark"],
                 ["+" + impr + "%", "more accurate"], ["261", "logged forecasts"]];
  stats.forEach((st, i) => {
    const x = 0.9 + i * 3.02;
    s.addText(st[0], { x, y: 4.35, w: 2.85, h: 0.85, fontFace: F, fontSize: 34,
      bold: true, color: AMBER, margin: 0 });
    s.addText(st[1], { x, y: 5.18, w: 2.85, h: 0.36, fontFace: F, fontSize: 14,
      color: "CADCFC", margin: 0 });
  });

  s.addText([
    { text: "Team Spurious Decision", options: { bold: true, color: "FFFFFF", breakLine: true } },
    { text: "Aakash Anil and Stefan von der Heyden, Stellenbosch University", options: { color: "9FB3C8", breakLine: true } },
    { text: "SES x Codera Analytics Hackathon, 28 July 2026", options: { color: "9FB3C8" } },
  ], { x: 0.9, y: 6.05, w: 11, h: 1.0, fontFace: F, fontSize: 14, margin: 0 });
  s.addNotes("[0:00-0:40] We're team Spurious Decision, and the name is the warning we set ourselves. A spurious relationship looks real in your data and isn't there in the world. In FX forecasting that's the default outcome, so the whole project was built to avoid one. At one month the rand is almost a random walk. We didn't try to out-muscle that. We disciplined it. 0.5600 against the benchmark's 0.5624.");
}

/* ================= 2. RESEARCH QUESTION ============================== */
{
  const s = slide("Can the AR(1) benchmark be beaten out of sample, and can we say why?");
  s.addShape(pres.ShapeType.roundRect, { x: 1.5, y: 1.5, w: 10.3, h: 1.75,
    rectRadius: 0.1, fill: { color: PALE },
    line: { color: FOCAL, pt: 1.5 } });
  s.addText("Forecast USDZAR 1 month ahead, every Friday, 1 Jan 2021 to 31 Dec 2025.\nBeat an AR(1) on RMSE, out of sample, and explain the mechanism.",
    { x: 1.75, y: 1.68, w: 9.8, h: 1.4, fontFace: F, fontSize: 21,
      color: NAVY, align: "center", valign: "middle", margin: 0 });

  s.addText([
    { text: "Why it is hard. ", options: { bold: true, breakLine: false } },
    { text: "Since Meese and Rogoff (1983), structural FX models lose to a no-change forecast at this horizon. Honest published gains run 1 to 5% (Rossi 2013).", options: { breakLine: true } },
    { text: "Our answer. ", options: { bold: true, breakLine: false } },
    { text: "Yes, by 0.42%, and the mechanism is a measurable bias in the benchmark itself.", options: {} },
  ], { x: M, y: 3.6, w: W, h: 2.0, fontFace: F, fontSize: 20, color: INK,
    bullet: true, paraSpaceAfter: 16, margin: 0 });
  cite(s, "Meese & Rogoff (1983), J. Int. Econ.; Rossi (2013), J. Econ. Lit. Full references on the references slide.");
  s.addNotes("[0:40-1:20] The question. Forecast the rand a month ahead, every Friday, five years, beat an AR(1) on RMSE out of sample. Why it's hard: since Meese and Rogoff in 1983, structural FX models lose to a simple no-change forecast at this horizon, and honest published gains are one to five per cent. Our answer is yes, by 0.42 per cent, and we can name the mechanism.");
}

/* ================= 3. METHOD + RIGOUR ================================ */
{
  const s = slide("Three simple models combined by recent accuracy, with every setting frozen before we saw the judged window");
  sectionHead(s, "The model", M, 1.55, 5.6);
  s.addText([
    { text: "Random walk. ", options: { bold: true, breakLine: false } },
    { text: "No change. The anchor.", options: { breakLine: true } },
    { text: "Carry. ", options: { bold: true, breakLine: false } },
    { text: "Tilt by the JIBAR minus US T-bill gap.", options: { breakLine: true } },
    { text: "Ridge. ", options: { bold: true, breakLine: false } },
    { text: "Gold, platinum, dollar, VIX. Heavily shrunk.", options: { breakLine: true } },
    { text: "Weights. ", options: { bold: true, breakLine: false } },
    { text: "Inverse recent out-of-sample error.", options: {} },
  ], { x: M, y: 1.98, w: 5.7, h: 3.0, fontFace: F, fontSize: 20, color: INK,
    bullet: true, paraSpaceAfter: 13, margin: 0 });

  sectionHead(s, "Why the numbers hold", 6.9, 1.55, 5.8);
  s.addText([
    { text: "Inputs dated on or before each Friday.", options: { breakLine: true } },
    { text: "Training only on already-resolved outcomes.", options: { breakLine: true } },
    { text: "Weights embargoed by 28 days.", options: { breakLine: true } },
    { text: "All settings frozen on 2015 to 2020.", options: { breakLine: true } },
    { text: "All 261 forecasts logged. Audit any one.", options: {} },
  ], { x: 6.9, y: 1.98, w: 5.8, h: 3.0, fontFace: F, fontSize: 20, color: INK,
    bullet: true, paraSpaceAfter: 13, margin: 0 });

  s.addShape(pres.ShapeType.roundRect, { x: M, y: 5.25, w: 12.1, h: 1.15,
    rectRadius: 0.08, fill: { color: NAVY }, line: { color: NAVY } });
  s.addText([
    { text: "Nothing here is a black box. ", options: { bold: true, color: "FFFFFF" } },
    { text: "OLS, ridge regression and a weighted average. We can derive every component by hand under questioning.", options: { color: "CADCFC" } },
  ], { x: 0.95, y: 5.42, w: 11.5, h: 0.85, fontFace: F, fontSize: 18,
    valign: "middle", margin: 0 });
  cite(s, "Data: SARB EXCX135 via EconData (MARKET_RATES 1.0.0); JIBAR, SARB; US T-bill, VIX, dollar index, Brent, FRED; platinum, NYMEX.");
  s.addNotes("[1:20-2:15] Three simple pieces. A random walk anchor. A carry tilt from the interest gap. A heavily regularised regression on gold, platinum, the dollar and the VIX. Combined by inverse recent error, so weight moves to whatever is working. On the right is why the numbers hold: information sets, resolved-only training, embargoed weights, settings frozen on 2015 to 2020 before we touched the judged window, and every forecast logged. Nothing here is a black box.");
}

/* ================= 4. RESULT 1: the mechanism ======================== */
{
  const s = slide("The AR(1)'s implied long-run mean sat below the market at all 261 origins");
  s.addImage({ path: path.join(SFIG, "cumse.png"), x: M, y: 1.5,
    w: 7.6, h: 4.3 });

  sectionHead(s, "What to take away", 8.5, 1.55, 4.3);
  s.addText([
    { text: "Persistence 0.997 to 0.999, just below one, so each forecast is pulled toward c/(1-phi).", options: { breakLine: true } },
    { text: "That mean ranged R11.80 to R19.18 and sat BELOW spot at 261 of 261 origins, by R2.11 on average.", options: { breakLine: true } },
    { text: "A downward lean against a rand that rose from R14.62 to R19.74.", options: {} },
  ], { x: 8.5, y: 2.0, w: 4.3, h: 3.2, fontFace: F, fontSize: 18, color: INK,
    bullet: true, paraSpaceAfter: 14, margin: 0 });

  s.addShape(pres.ShapeType.roundRect, { x: 8.5, y: 5.15, w: 4.3, h: 1.35,
    rectRadius: 0.08, fill: { color: "FFF2CC" }, line: { color: "E6C800", pt: 1 } });
  s.addText([
    { text: "R2.11", options: { bold: true, fontSize: 30, color: "7A5200", breakLine: true } },
    { text: "average gap, below spot at every origin", options: { fontSize: 14, color: "7A5200" } },
  ], { x: 8.65, y: 5.28, w: 4.0, h: 1.1, fontFace: F, align: "center",
    valign: "middle", margin: 0 });
  cite(s, "Own calculation. AR(1) refitted at each of the 261 origins; reproducible via src/validate_results.py in the submission.");
  s.addNotes("[2:15-3:15] Why is the benchmark beatable? Its persistence is just below one, so every forecast is pulled toward an implied long-run mean. We computed that mean at all 261 origins. It sat below the actual spot rate at every single one, by 2.11 rand on average. So it leaned downward for five years against a currency going up. The chart is cumulative squared error: above zero we're ahead. The edge builds through the 2022-23 trend, peaks at 1.29, and gives some back. I'd rather show you that than crop it at the peak.");
}

/* ================= 5. RESULT 2: accuracy ============================= */
{
  const s = slide("The combination cuts RMSE 0.42% below the benchmark; four of five models beat it");
  s.addImage({ path: path.join(SFIG, "rmse.png"), x: M, y: 1.45,
    w: 7.6, h: 4.75 });

  sectionHead(s, "What to take away", 8.35, 1.5, 4.5);
  s.addText([
    { text: "Combination 0.5600 against the AR(1)'s 0.5624, over 261 forecasts.", options: { breakLine: true } },
    { text: "Robustness: with targets strictly inside 2025 we lead every model, random walk included.", options: { breakLine: true } },
    { text: "Gradient boosting, same data and discipline, loses by " + gbmLoss + "%. About 850 noisy observations cannot support a flexible learner.", options: {} },
  ], { x: 8.35, y: 1.95, w: 4.5, h: 4.2, fontFace: F, fontSize: 18, color: INK,
    bullet: true, paraSpaceAfter: 16, margin: 0 });
  cite(s, "Own calculation from forecast_log.csv, n = 261. Simple-beats-complex is the M4 and M5 competition finding (Makridakis et al. 2020, 2022).");
  s.addNotes("[3:15-4:10] The numbers. Benchmark 0.5624, our combination 0.5600, about 0.42 per cent better. Carry and ridge also beat it, so four of five did. Note the axis starts at 0.50 so the differences are visible, I'd rather say that than have you spot it. Two things. On the robustness cut with targets strictly inside 2025 we lead every model including the random walk. And the one model that loses badly is the gradient booster, by seven and a half per cent, same data, same discipline. That's the M4 and M5 finding and we built it into the design.");
}

/* ================= 6. CONCLUSIONS (stays up during Q&A) ============== */
{
  const s = dark();
  s.addText("Conclusions", { x: M, y: 0.4, w: W, h: 0.5, fontFace: F,
    fontSize: 20, color: "A0BBDD", margin: 0 });
  s.addShape(pres.ShapeType.rect, { x: M, y: 0.95, w: W, h: 0.05,
    fill: { color: AMBER }, line: { color: AMBER } });

  s.addText([
    { text: "1.  The benchmark is beatable, and we can say why. ", options: { bold: true, color: "FFFFFF", breakLine: false } },
    { text: "Its implied long-run mean sat below spot at all 261 origins, by R2.11 on average.", options: { color: "CADCFC", breakLine: true } },
    { text: "2.  The gain is real but small. ", options: { bold: true, color: "FFFFFF", breakLine: false } },
    { text: "0.42% in RMSE, holding in four of five years and on the strict robustness cut. That is the size of the true signal at one month.", options: { color: "CADCFC", breakLine: true } },
    { text: "3.  Discipline beat complexity. ", options: { bold: true, color: "FFFFFF", breakLine: false } },
    { text: "Gradient boosting, run under identical rules, lost by " + gbmLoss + "%.", options: { color: "CADCFC", breakLine: true } },
    { text: "4.  What we do not claim. ", options: { bold: true, color: "FFFFFF", breakLine: false } },
    { text: "Not statistically significant (DM p = " + MET.COMBO.dm_vs_ar1[1].toFixed(2) + "). The benchmark wins on MAE and in 2025. Untested as a trading strategy.", options: { color: "CADCFC" } },
  ], { x: M, y: 1.25, w: W, h: 4.5, fontFace: F, fontSize: 19,
    paraSpaceAfter: 17, margin: 0 });

  s.addShape(pres.ShapeType.rect, { x: M, y: 6.15, w: W, h: 0.02,
    fill: { color: "2A4A5E" }, line: { color: "2A4A5E" } });
  s.addText("Full code, forecast log and report in the submission. Reproduces end to end with one command.",
    { x: M, y: 6.3, w: 8.6, h: 0.4, fontFace: F, fontSize: 15,
      color: "A0BBDD", margin: 0 });
  s.addText("Questions and feedback welcome.", { x: 9.4, y: 6.3, w: 3.3, h: 0.4,
    fontFace: F, fontSize: 15, color: AMBER, bold: true, align: "right",
    margin: 0 });
  s.addNotes("[4:10-4:40] So, four things. The benchmark is beatable and we can say why. The gain is real but small, which is the size of the true signal here. Discipline beat complexity. And what we won't claim: it isn't statistically significant, p is 0.47, the benchmark wins on MAE and in 2025, and we never tested it as a trading strategy. Happy to walk through the code line by line. Are there questions or feedback?  --- LEAVE THIS SLIDE UP FOR Q&A ---");
}

/* ================= 7. REFERENCES ===================================== */
{
  const s = slide("References");
  const refs = [
    "Amat, C., Michalski, T. and Stoltz, G. (2018). Fundamentals and exchange rate forecastability with simple machine learning methods. Journal of International Money and Finance, 88, 1-24.",
    "Codera Analytics (2024-25). What drives the rand?; USDZAR Forecasts. codera.co.za.",
    "Darvas, Z. (2020). Forecasting exchange rates of major currencies with long maturity interest rates. Bruegel Working Paper 2020/02.",
    "Diebold, F.X. and Mariano, R.S. (1995). Comparing predictive accuracy. Journal of Business and Economic Statistics, 13(3), 253-263.",
    "Makridakis, S., Spiliotis, E. and Assimakopoulos, V. (2020, 2022). The M4 and M5 accuracy competitions: results, findings and conclusions. International Journal of Forecasting.",
    "Meese, R. and Rogoff, K. (1983). Empirical exchange rate models of the seventies: do they fit out of sample? Journal of International Economics, 14, 3-24.",
    "Rossi, B. (2013). Exchange rate predictability. Journal of Economic Literature, 51(4), 1063-1119.",
    "South African Reserve Bank (2022). Working Paper WP/22/14: can the distribution of rand returns improve exchange rate forecasts?",
  ];
  s.addText(refs.flatMap((r, i) => [{ text: r, options: { breakLine: true } }]),
    { x: M, y: 1.3, w: W, h: 5.2, fontFace: F, fontSize: 14, color: INK,
      paraSpaceAfter: 9, margin: 0 });
  s.addText("Data: SARB series EXCX135 via EconData (MARKET_RATES 1.0.0, EXCX135.B.A). SARB. MARKET_RATES. Pretoria: SARB [producer]. Johannesburg: EconData [distributor], 2026.",
    { x: M, y: 6.6, w: W, h: 0.5, fontFace: F, fontSize: 13, color: MUTED,
      margin: 0 });
  s.addNotes("Not presented. Here so every source cited on a slide has a full reference.");
}

/* ================= APPENDIX ========================================== */
function appx(letter, title) {
  return slide(title, { appendix: "Appendix " + letter });
}

{
  const s = appx("A", "Full results for every model on every metric");
  const hdr = (t) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: NAVY } } });
  const rows = [[hdr("Model"), hdr("RMSE"), hdr("MAE"), hdr("Dir."), hdr("vs AR(1)"), hdr("DM p"), hdr("Targets <=2025")]];
  const nice = { AR1_log: "AR(1) log (baseline)", AR1_level: "AR(1) level", RW: "Random walk", CARRY: "Carry", RIDGE: "Ridge", GBM: "Gradient boosting", COMBO: "Combination (ours)" };
  for (const k of ["AR1_log", "AR1_level", "RW", "CARRY", "RIDGE", "GBM", "COMBO"]) {
    const m = MET[k];
    rows.push([
      { text: nice[k], options: k === "COMBO" ? { bold: true } : {} },
      r4(m.rmse), r4(m.mae),
      k === "RW" ? "n/a" : (100 * m.dir_acc).toFixed(1) + "%",
      k === "AR1_log" ? "-" : ((100 * (1 - m.rmse / base) >= 0 ? "+" : "") + (100 * (1 - m.rmse / base)).toFixed(2) + "%"),
      m.dm_vs_ar1 ? m.dm_vs_ar1[1].toFixed(3) : "-",
      r4(MET._targets_within_window[k]),
    ]);
  }
  s.addTable(rows, { x: M, y: 1.35, w: W, colW: [2.9, 1.5, 1.5, 1.2, 1.5, 1.2, 2.3],
    fontFace: F, fontSize: 13, color: INK, valign: "middle",
    border: { pt: 0.5, color: RULE }, rowH: 0.5, margin: 0.06, align: "center" });
  cite(s, "Own calculation from forecast_log.csv, n = 261. DM = Diebold-Mariano against the AR(1), Newey-West variance at lag 3.");
  s.addNotes("Use for any numeric question: MAE, directional accuracy, DM p-values, robustness cut.");
}
{
  const s = appx("B", "We win four years of five; 2025 goes the other way and we say so");
  s.addImage({ path: path.join(SFIG, "yearly.png"), x: 2.4, y: 1.4,
    w: 8.5, h: 4.7 });
  cite(s, "Own calculation from forecast_log.csv.");
  s.addNotes("2025 goes against us because the rand strengthened back toward the AR(1)'s mean, so its bias finally helped. That is regime dependence, and it is the argument for combining rather than picking one model.");
}
{
  const s = appx("C", "The target series is the one the rules specify, verified against an independent source");
  s.addText([
    { text: "Source. ", options: { bold: true, breakLine: false } },
    { text: "Official EconData export, MARKET_RATES 1.0.0, series EXCX135.B.A, 14 173 daily observations from 2 January 1970.", options: { breakLine: true } },
    { text: "Verification. ", options: { bold: true, breakLine: false } },
    { text: "Checked value by value against the SARB Web API (EXCX135D): 9 141 overlapping observations, maximum difference 0.000000, zero mismatches.", options: { breakLine: true } },
    { text: "Consequence. ", options: { bold: true, breakLine: false } },
    { text: "Backtests run off either source give RMSEs identical to twelve decimal places.", options: { breakLine: true } },
    { text: "Predictors. ", options: { bold: true, breakLine: false } },
    { text: "All daily market prices. Never revised, no publication lag, so look-ahead bias is impossible by construction rather than merely avoided.", options: {} },
  ], { x: M, y: 1.5, w: 6.6, h: 4.8, fontFace: F, fontSize: 18, color: INK,
    bullet: true, paraSpaceAfter: 15, margin: 0 });
  s.addImage({ path: path.join(FIG, "input_series.png"), x: 7.5, y: 1.4,
    w: 5.3, h: 5.15 });
  cite(s, "SARB. MARKET_RATES 1.0.0. Pretoria: SARB [producer]. Johannesburg: EconData [distributor], 2026. Verification script: src/verify_provenance.py.");
  s.addNotes("Use for any data or look-ahead-bias question.");
}
{
  const s = appx("D", "The random walk's role as anchor was learned from performance, not imposed");
  s.addImage({ path: path.join(FIG, "combination_weights.png"), x: M, y: 1.5,
    w: 7.6, h: 3.38 });
  s.addText([
    { text: "Frozen on the 2015 to 2020 validation era:", options: { bold: true, breakLine: true } },
    { text: "ridge on the " + (VAL.chosen_config.ridge.startsWith("RIDGE_f") ? "full" : "compact")
      + " feature set, " + (VAL.chosen_config.ridge.endsWith("0") ? "no" : "with") + " intercept",
      options: { breakLine: true } },
    { text: "decay " + VAL.chosen_config.delta + " on past errors", options: { breakLine: true } },
    { text: "sharpness " + VAL.chosen_config.theta, options: { breakLine: true } },
    { text: "window of 156 resolved origins", options: {} },
  ], { x: 8.5, y: 1.6, w: 4.3, h: 3.2, fontFace: F, fontSize: 17, color: INK,
    bullet: true, paraSpaceAfter: 10, margin: 0 });
  s.addText("When carry earned its way in during 2022 and 2023, weight moved to it. When nothing worked in 2024 and 2025, weight collapsed back to the anchor. A fixed no-change rule cannot do that.",
    { x: M, y: 5.2, w: 12.1, h: 0.9, fontFace: F, fontSize: 18, color: INK,
      margin: 0 });
  cite(s, "Own calculation. Full validation grid in validation_metrics.json.");
  s.addNotes("Use for: how does the combination adapt, and how do we know settings were frozen.");
}
{
  const s = appx("E", "We ran machine learning under identical rules and it lost by " + gbmLoss + "%");
  s.addShape(pres.ShapeType.roundRect, { x: M, y: 1.55, w: 5.9, h: 4.4,
    rectRadius: 0.1, fill: { color: PALE }, line: { color: RULE } });
  sectionHead(s, "What we ran", 0.95, 1.8, 5.2);
  s.addText("HistGradientBoosting with a fixed seed. Once a year, purged cross-validation picks its depth, learning rate, iterations, L2 penalty and leaf size from " + VAL.gbm.grid.length + " configurations. Same information set, same embargo and same walk-forward loop as every other model.",
    { x: 0.95, y: 2.3, w: 5.2, h: 3.4, fontFace: F, fontSize: 18, color: INK,
      margin: 0, valign: "top" });
  s.addShape(pres.ShapeType.roundRect, { x: 6.85, y: 1.55, w: 5.9, h: 4.4,
    rectRadius: 0.1, fill: { color: PALE }, line: { color: RULE } });
  sectionHead(s, "Why it lost", 7.2, 1.8, 5.2);
  s.addText("About 850 weekly observations, heavily overlapping, with a tiny signal. A learner that can represent thresholds and interactions finds plenty of both, but those patterns belong to that stretch of history rather than to the currency, so they do not repeat out of sample.",
    { x: 7.2, y: 2.3, w: 5.2, h: 3.4, fontFace: F, fontSize: 18, color: INK,
      margin: 0, valign: "top" });
  cite(s, "Makridakis, Spiliotis and Assimakopoulos (2020, 2022) report the same conclusion across thousands of series.");
  s.addNotes("Use for: why didn't you use machine learning, deep learning, or an LSTM. We did, honestly, and here is the number.");
}
{
  const s = appx("F", "Forecasts track the realised series closely and lag it slightly, as a near-random walk should");
  s.addImage({ path: path.join(FIG, "forecasts_vs_actual.png"), x: 1.3, y: 1.45,
    w: 10.7, h: 5.03 });
  cite(s, "Own calculation. Forecasts plotted at their target dates against EXCX135.");
  s.addNotes("Use if a judge asks to see the forecasts themselves.");
}
{
  const s = appx("G", "One forecast in full: on 3 June 2022 the AR(1) was the worst of the sensible models");
  const hdr = (t) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: NAVY } } });
  s.addTable([
    [hdr("Model"), hdr("Forecast"), hdr("How it got there"), hdr("Error")],
    ["Random walk", "15.4117", "today's rate, unchanged", "-0.9365"],
    ["Carry", "15.4557", "15.4117 x (1 + 0.0372 x 28/365)", "-0.8925"],
    ["AR(1)", "15.3861", "iterated 4 steps toward its implied mean, R13.01 that day", "-0.9621"],
    ["Ridge", "15.4089", "small tilt away from spot", "-0.9393"],
    [{ text: "Combination", options: { bold: true } }, { text: "15.4256", options: { bold: true } },
     "0.333 x RW + 0.337 x Carry + 0.331 x Ridge", { text: "-0.9226", options: { bold: true } }],
  ], { x: M, y: 1.5, w: W, colW: [2.4, 1.9, 5.6, 2.2], fontFace: F,
    fontSize: 14, color: INK, valign: "middle",
    border: { pt: 0.5, color: RULE }, rowH: 0.55, margin: 0.06 });
  s.addText("Origin Friday 3 June 2022, spot R15.4117. Target 1 July 2022, actual R16.3482. Every model was too low that month. The AR(1) was worst because its implied mean that day was R13.01, and that pull dragged its forecast down exactly when the rand was heading up.",
    { x: M, y: 5.0, w: W, h: 1.2, fontFace: F, fontSize: 18, color: INK,
      margin: 0 });
  cite(s, "Own calculation from forecast_log.csv and combo_weights.csv.");
  s.addNotes("Use if asked what the model actually does. It is the whole project in one month.");
}

pres.writeFile({ fileName: path.join(__dirname, "..", "reports", "presentation.pptx") })
  .then(() => console.log("reports/presentation.pptx written: 6 presented + references + 7 appendix"));
