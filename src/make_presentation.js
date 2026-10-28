// make_presentation.js — SES x Codera hackathon deck.
//
// Structure follows academic presentation discipline (action titles, one
// exhibit per results slide, annotated findings, references, conclusions last)
// with dark title and closing slides, large figures and a single accent colour.
//
// Every number comes from data/processed/doc_keys.json, which render_docs.py
// writes from the saved outputs. Text is written with {{key}} placeholders and
// filled by F(); an unknown key throws.
//
// 6 presented slides (~4:40) + references + 8 appendix slides.
// Run: node make_presentation.js
const pptxgen = require("pptxgenjs");
const path = require("path");

const FIG = path.join(__dirname, "..", "figures");
const SFIG = path.join(FIG, "presentation");
const DK = require(path.join(__dirname, "..", "data", "processed", "doc_keys.json"));
const K = DK.keys, T = DK.tables;

function F(text) {
  return text.replace(/\{\{(\w+)\}\}/g, (_, key) => {
    if (!(key in K)) throw new Error("unknown doc key: " + key);
    return K[key];
  });
}

// three content colours plus neutrals
const NAVY = "0E2A3B";    // primary / dark slides
const FOCAL = "1A7A4A";   // the combination
const AMBER = "C9A227";   // call-outs, key figures
const INK = "1F2937";
const MUTED = "6B7280";
const PALE = "F1F6F3";
const RULE = "D6DEE6";
const F_ = "Arial";

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
  const title = F(actionTitle);
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  const two = title.length > 58;
  s.addText(title, {
    x: M, y: 0.34, w: W, h: two ? 1.0 : 0.66, fontFace: F_, fontSize: 26,
    bold: true, color: NAVY, margin: 0, valign: "top",
  });
  const ruleY = two ? 1.36 : 1.06;
  s.addShape(pres.ShapeType.rect, {
    x: M, y: ruleY, w: W, h: 0.02, fill: { color: RULE }, line: { color: RULE },
  });
  if (opts.appendix)
    s.addText(opts.appendix, {
      x: M, y: 0.06, w: W, h: 0.26, fontFace: F_, fontSize: 13, italic: true,
      color: MUTED, margin: 0,
    });
  return s;
}

function cite(s, txt) {
  s.addText(F(txt), { x: M, y: 6.92, w: W, h: 0.3, fontFace: F_, fontSize: 13,
    color: MUTED, margin: 0 });
}

function sectionHead(s, txt, x, y, w) {
  s.addText(txt, { x, y, w, h: 0.34, fontFace: F_, fontSize: 20, bold: true,
    color: FOCAL, margin: 0 });
}

/* Bold lead-in followed by plain text, one paragraph per pair. */
function leadIns(pairs) {
  const runs = [];
  pairs.forEach(([lead, body], i) => {
    const last = i === pairs.length - 1;
    if (lead) runs.push({ text: F(lead) + " ", options: { bold: true, breakLine: false } });
    runs.push({ text: F(body), options: last ? {} : { breakLine: true } });
  });
  return runs;
}

function bullets(lines) {
  return lines.map((t, i) => ({ text: F(t), options: i < lines.length - 1 ? { breakLine: true } : {} }));
}

/* ================= 1. TITLE ========================================== */
{
  const s = dark();
  s.addText("Don't fight the random walk.\nDiscipline it.", {
    x: 0.9, y: 0.95, w: 11.5, h: 1.8, fontFace: F_, fontSize: 42, bold: true,
    color: "FFFFFF", margin: 0, lineSpacingMultiple: 1.05,
  });
  s.addShape(pres.ShapeType.rect, { x: 0.9, y: 2.95, w: 2.2, h: 0.05,
    fill: { color: AMBER }, line: { color: AMBER } });
  s.addText(F("A combination of three simple models scores {{gain_vs_ar1}}% lower RMSE than the AR(1) benchmark over {{n_origins}} out-of-sample forecasts. The gap is not statistically significant, and the combination is level with the random walk."),
    { x: 0.9, y: 3.2, w: 10.9, h: 0.95, fontFace: F_, fontSize: 19,
      color: "CADCFC", margin: 0 });

  const stats = [[K.rmse_combo, "combination RMSE"], [K.rmse_ar1_log, "AR(1) benchmark"],
                 [K.rmse_rw, "random walk"], ["p = " + K.p_combo_ar1, "against the AR(1)"]];
  stats.forEach((st, i) => {
    const x = 0.9 + i * 3.02;
    s.addText(st[0], { x, y: 4.35, w: 2.85, h: 0.85, fontFace: F_, fontSize: 34,
      bold: true, color: AMBER, margin: 0 });
    s.addText(st[1], { x, y: 5.18, w: 2.85, h: 0.36, fontFace: F_, fontSize: 14,
      color: "CADCFC", margin: 0 });
  });

  s.addText([
    { text: "Team Spurious Decision", options: { bold: true, color: "FFFFFF", breakLine: true } },
    { text: "Aakash Anil and Stefan von der Heyden, Stellenbosch University", options: { color: "9FB3C8", breakLine: true } },
    { text: "SES x Codera Analytics Hackathon, 28 July 2026", options: { color: "9FB3C8" } },
  ], { x: 0.9, y: 6.05, w: 11, h: 1.0, fontFace: F_, fontSize: 14, margin: 0 });
  s.addNotes(F("[0:00-0:40] We're team Spurious Decision, and the name is the warning we set ourselves. A spurious relationship looks real in your data and isn't there in the world. At one month the rand is almost a random walk, so we didn't try to out-muscle it. Our combination scores {{rmse_combo}} against the AR(1)'s {{rmse_ar1_log}} and the random walk's {{rmse_rw}}. That gap is not statistically significant, and we'll say so throughout."));
}

/* ================= 2. RESEARCH QUESTION ============================== */
{
  const s = slide("Can the AR(1) benchmark be beaten out of sample, and by how much?");
  s.addShape(pres.ShapeType.roundRect, { x: 1.5, y: 1.5, w: 10.3, h: 1.75,
    rectRadius: 0.1, fill: { color: PALE },
    line: { color: FOCAL, pt: 1.5 } });
  s.addText("Forecast USDZAR 1 month ahead, every Friday, 1 Jan 2021 to 31 Dec 2025.\nCompare RMSE with an AR(1), out of sample, and say how far the result can be trusted.",
    { x: 1.75, y: 1.68, w: 9.8, h: 1.4, fontFace: F_, fontSize: 21,
      color: NAVY, align: "center", valign: "middle", margin: 0 });

  s.addText(leadIns([
    ["Why it is hard.", "Since Meese and Rogoff (1983), structural FX models lose to a no-change forecast at this horizon. Rossi (2013) finds that success depends on the sample, predictor, horizon and benchmark."],
    ["Our answer.", "A gain of {{gain_vs_ar1}}% in RMSE over the AR(1) that is not statistically established, and no gain over the random walk."],
  ]), { x: M, y: 3.6, w: W, h: 2.4, fontFace: F_, fontSize: 20, color: INK,
    bullet: true, paraSpaceAfter: 16, margin: 0 });
  cite(s, "Meese & Rogoff (1983), J. Int. Econ.; Rossi (2013), J. Econ. Lit. Full references on the references slide.");
  s.addNotes(F("[0:40-1:20] The question. Forecast the rand a month ahead, every Friday, five years, and compare RMSE with an AR(1) out of sample. It is hard because since Meese and Rogoff in 1983 structural models lose to a no-change forecast at this horizon. Our answer is a small gain over the AR(1), {{gain_vs_ar1}} per cent, that we cannot distinguish from noise, and no gain over the random walk."));
}

/* ================= 3. METHOD + RIGOUR ================================ */
{
  const s = slide("Three simple models combined by recent accuracy, with settings chosen on 2015 to 2020, before the judged window");
  sectionHead(s, "The model", M, 1.55, 5.6);
  s.addText(leadIns([
    ["Random walk.", "No change. The anchor."],
    ["Carry.", "Tilt by the JIBAR minus US T-bill gap."],
    ["Ridge.", "Commodity, dollar and risk predictors. Heavily shrunk."],
    ["Weights.", "Inverse recent out-of-sample error."],
  ]), { x: M, y: 1.98, w: 5.7, h: 3.0, fontFace: F_, fontSize: 20, color: INK,
    bullet: true, paraSpaceAfter: 13, margin: 0 });

  sectionHead(s, "How the test is protected", 6.9, 1.55, 5.8);
  s.addText(bullets([
    "Inputs public by Friday 17:00 Johannesburg.",
    "Training only on already-resolved outcomes.",
    "Purged cross-validation, scaler inside folds.",
    "Weights use only resolved errors.",
    "All {{n_origins}} forecasts logged. Audit any one.",
  ]), { x: 6.9, y: 1.98, w: 5.8, h: 3.0, fontFace: F_, fontSize: 20, color: INK,
    bullet: true, paraSpaceAfter: 13, margin: 0 });

  s.addShape(pres.ShapeType.roundRect, { x: M, y: 5.25, w: 12.1, h: 1.15,
    rectRadius: 0.08, fill: { color: NAVY }, line: { color: NAVY } });
  s.addText([
    { text: "Nothing here is a black box. ", options: { bold: true, color: "FFFFFF" } },
    { text: "OLS, ridge regression and a weighted average. We can derive every component by hand under questioning.", options: { color: "CADCFC" } },
  ], { x: 0.95, y: 5.42, w: 11.5, h: 0.85, fontFace: F_, fontSize: 18,
    valign: "middle", margin: 0 });
  cite(s, "Data: SARB EXCX135 via EconData (MARKET_RATES 1.0.0); JIBAR, SARB; US T-bill, VIX, dollar index, Brent, FRED; platinum, NYMEX.");
  s.addNotes(F("[1:20-2:15] Three simple pieces. A random walk anchor. A carry tilt from the interest gap. A heavily regularised regression on commodity, dollar and risk predictors. Combined by inverse recent error. On the right is how the test is protected: every input joined on when it was public, training only on resolved outcomes, purged cross-validation, weights from resolved errors, and every forecast logged. The ridge variant, decay and sharpness were chosen on {{val_n}} validation origins from {{val_first}} to {{val_last}}. Those scores were used for selection, so they are not independent evidence."));
}

/* ================= 4. RESULT 1: cumulative error ===================== */
{
  const s = slide("The combination gained on the AR(1) until {{cum_peak_date}}, then gave most of it back");
  s.addImage({ path: path.join(SFIG, "cumse.png"), x: M, y: 1.5,
    w: 7.6, h: 4.3 });

  sectionHead(s, "What to take away", 8.5, 1.55, 4.3);
  s.addText(bullets([
    "Cumulative squared-error gain peaked at {{cum_peak}} and ended at {{cum_final}}.",
    "The AR(1)'s implied long-run level sat below spot at {{n_below_spot}} of {{n_origins}} origins, by R{{mean_gap}} on average, and it never forecast a rise.",
    "Squared bias is {{bias_share_of_gap_pct}}% of its excess squared error. The rest is variance.",
  ]), { x: 8.5, y: 2.0, w: 4.3, h: 3.2, fontFace: F_, fontSize: 17, color: INK,
    bullet: true, paraSpaceAfter: 14, margin: 0 });

  s.addShape(pres.ShapeType.roundRect, { x: 8.5, y: 5.15, w: 4.3, h: 1.35,
    rectRadius: 0.08, fill: { color: "FFF2CC" }, line: { color: "E6C800", pt: 1 } });
  s.addText([
    { text: "R" + K.mean_gap, options: { bold: true, fontSize: 30, color: "7A5200", breakLine: true } },
    { text: "average gap, implied level below spot", options: { fontSize: 14, color: "7A5200" } },
  ], { x: 8.65, y: 5.28, w: 4.0, h: 1.1, fontFace: F_, align: "center",
    valign: "middle", margin: 0 });
  cite(s, "Own calculation from forecast_log.csv. The downward lean is an observation, not shown to be the full explanation.");
  s.addNotes(F("[2:15-3:15] The chart is the cumulative squared-error difference against the AR(1); above zero the combination is ahead. It peaked at {{cum_peak}} on {{cum_peak_date}} and finished at {{cum_final}}, so most of the gain was given back. Separately, the AR(1) is pulled towards a long-run level that sat below spot at every origin, by R{{mean_gap}} on average, and it never forecast a rise. Squared bias accounts for {{bias_share_of_gap_pct}} per cent of its excess squared error against the combination. That is an observation. We have not shown it is the whole explanation."));
}

/* ================= 5. RESULT 2: accuracy ============================= */
{
  const s = slide("The combination's RMSE is {{gain_vs_ar1}}% below the AR(1)'s and level with the random walk's");
  s.addImage({ path: path.join(SFIG, "rmse.png"), x: M, y: 1.45,
    w: 7.6, h: 4.75 });

  sectionHead(s, "What to take away", 8.35, 1.5, 4.5);
  s.addText(bullets([
    "Combination {{rmse_combo}}, AR(1) {{rmse_ar1_log}}, random walk {{rmse_rw}}, over {{n_origins}} forecasts.",
    "Both prespecified intervals include zero: p = {{p_combo_ar1}} against the AR(1), {{p_combo_rw}} against the random walk.",
    "Equal weights score {{rmse_equal3}}, so adaptive weighting adds nothing measurable.",
    "Gradient boosting scores {{rmse_gbm}}, the highest of {{n_models}} models. This specification only.",
  ]), { x: 8.35, y: 1.95, w: 4.5, h: 4.4, fontFace: F_, fontSize: 17, color: INK,
    bullet: true, paraSpaceAfter: 14, margin: 0 });
  cite(s, "Own calculation from forecast_log.csv, n = {{n_origins}}. Intervals: Newey-West, lag 3. None of {{n_exploratory}} exploratory comparisons survives Holm adjustment.");
  s.addNotes(F("[3:15-4:10] The chart shows each model's RMSE difference from the random walk on the left and from the AR(1) on the right, with 95 per cent intervals. Green is the two comparisons we fixed in advance. The combination is {{gain_vs_ar1}} per cent below the AR(1) but the interval includes zero, and against the random walk it is level. An equal-weight average of the same three scores {{rmse_equal3}}. Gradient boosting scores {{rmse_gbm}}, the highest of the {{n_models}} models, and that covers this specification only."));
}

/* ================= 6. CONCLUSIONS (stays up during Q&A) ============== */
{
  const s = dark();
  s.addText("Conclusions", { x: M, y: 0.4, w: W, h: 0.5, fontFace: F_,
    fontSize: 20, color: "A0BBDD", margin: 0 });
  s.addShape(pres.ShapeType.rect, { x: M, y: 0.95, w: W, h: 0.05,
    fill: { color: AMBER }, line: { color: AMBER } });

  const item = (n, lead, body, last) => [
    { text: n + ".  " + F(lead) + " ", options: { bold: true, color: "FFFFFF", breakLine: false } },
    { text: F(body), options: Object.assign({ color: "CADCFC" }, last ? {} : { breakLine: true }) },
  ];
  s.addText([].concat(
    item(1, "A small gain over the AR(1).", "{{gain_vs_ar1}}% lower RMSE, not statistically established (p = {{p_combo_ar1}}). Level with the random walk (p = {{p_combo_rw}}).", false),
    item(2, "Adaptive weighting adds nothing measurable.", "Equal weights score {{rmse_equal3}}. The weights stayed between {{w_min}} and {{w_max}}.", false),
    item(3, "The AR(1) leans downward.", "Its implied level was below spot at {{n_below_spot}} of {{n_origins}} origins. That is an observation, not shown to be the full explanation.", false),
    item(4, "What we do not claim.", "Significance, directional skill (the combination's {{combo_dir_acc_pct}}% accuracy equals the share of rises), or profitability. All 2021 to 2025 results are exploratory.", true),
  ), { x: M, y: 1.25, w: W, h: 4.7, fontFace: F_, fontSize: 19,
    paraSpaceAfter: 17, margin: 0 });

  s.addShape(pres.ShapeType.rect, { x: M, y: 6.15, w: W, h: 0.02,
    fill: { color: "2A4A5E" }, line: { color: "2A4A5E" } });
  s.addText("Full code, forecast log and report in the submission. Reproduces end to end with one command.",
    { x: M, y: 6.3, w: 8.6, h: 0.4, fontFace: F_, fontSize: 15,
      color: "A0BBDD", margin: 0 });
  s.addText("Questions and feedback welcome.", { x: 9.4, y: 6.3, w: 3.3, h: 0.4,
    fontFace: F_, fontSize: 15, color: AMBER, bold: true, align: "right",
    margin: 0 });
  s.addNotes(F("[4:10-4:40] Four things. A small gain over the AR(1) that is not statistically established, p {{p_combo_ar1}}, and level with the random walk. Adaptive weighting adds nothing measurable. The AR(1) leans downward, which we report as an observation. And what we won't claim: significance, directional skill, or profitability, and every 2021 to 2025 result is exploratory. Happy to walk through the code line by line. Are there questions or feedback?  --- LEAVE THIS SLIDE UP FOR Q&A ---"));
}

/* ================= 7. REFERENCES ===================================== */
{
  const s = slide("References");
  const refs = [
    "Amat, C., Michalski, T. and Stoltz, G. (2018). Fundamentals and exchange rate forecastability with simple machine learning methods. Journal of International Money and Finance, 88, 1-24.",
    "Darvas, Z. (2020). Forecasting exchange rates of major currencies with long maturity interest rates. Bruegel Working Paper 2020/02.",
    "Diebold, F.X. and Mariano, R.S. (1995). Comparing predictive accuracy. Journal of Business and Economic Statistics, 13(3), 253-263.",
    "Makridakis, S., Spiliotis, E. and Assimakopoulos, V. (2022). M5 accuracy competition: results, findings, and conclusions. International Journal of Forecasting.",
    "Meese, R. and Rogoff, K. (1983). Empirical exchange rate models of the seventies: do they fit out of sample? Journal of International Economics, 14, 3-24.",
    "Rossi, B. (2013). Exchange rate predictability. Journal of Economic Literature, 51(4), 1063-1119.",
    "South African Reserve Bank (2022). Working Paper WP/22/14: can the distribution of rand returns improve exchange rate forecasts?",
  ];
  s.addText(refs.map((r) => ({ text: r, options: { breakLine: true } })),
    { x: M, y: 1.3, w: W, h: 5.2, fontFace: F_, fontSize: 14, color: INK,
      paraSpaceAfter: 9, margin: 0 });
  s.addText("Data: SARB series EXCX135 via EconData (MARKET_RATES 1.0.0, EXCX135.B.A). SARB. MARKET_RATES. Pretoria: SARB [producer]. Johannesburg: EconData [distributor], 2026.",
    { x: M, y: 6.6, w: W, h: 0.5, fontFace: F_, fontSize: 13, color: MUTED,
      margin: 0 });
  s.addNotes("Not presented. Here so every source cited on a slide has a full reference.");
}

/* ================= APPENDIX ========================================== */
function appx(letter, title) {
  return slide(title, { appendix: "Appendix " + letter });
}
const hdr = (t) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: NAVY } } });

{
  const s = appx("A", "Full results for every model: the leaders differ by {{rmse_spread_rw_family}} in RMSE");
  const rows = [T.results[0].map(hdr)];
  T.results.slice(1).forEach((r) => {
    const bold = r[0] === "Combination";
    rows.push(r.map((c, i) => (bold ? { text: c, options: { bold: true } } : (i === 0 ? c : c))));
  });
  s.addTable(rows, { x: M, y: 1.5, w: W, colW: [4.3, 1.4, 1.4, 2.0, 1.1, 1.9],
    fontFace: F_, fontSize: 12, color: INK, valign: "middle",
    border: { pt: 0.5, color: RULE }, rowH: 0.34, margin: 0.05, align: "center" });
  cite(s, "Own calculation from forecast_log.csv, n = {{n_origins}}. RMSE below AR(1) is positive when a model beats the benchmark. Only the first row and the two prespecified comparisons were fixed in advance.");
  s.addNotes(F("Use for any numeric question: MAE, rank, share of origins at which each model forecast a rise. The AR(1) variants, drift, equal-weight average and adaptive pairs are exploratory."));
}
{
  const s = appx("B", "The combination is below the AR(1) in {{years_ahead_n}} of {{years_n}} years; {{years_behind}} goes the other way");
  s.addImage({ path: path.join(SFIG, "yearly.png"), x: 2.4, y: 1.5,
    w: 8.5, h: 4.7 });
  cite(s, "Own calculation from forecast_log.csv. Five annual figures cannot show whether the pattern is stable. We have not tested why {{years_behind}} differs.");
  s.addNotes(F("The AR(1) scored {{behind_ar1}} in {{behind_year}} against {{behind_combo}} for the combination and {{behind_rw}} for the random walk. We have not tested a reason."));
}
{
  const s = appx("C", "The target is verified against an independent source, and predictors join on publication time");
  s.addText(leadIns([
    ["Source.", "Official EconData export, MARKET_RATES 1.0.0, series EXCX135.B.A, {{econdata_n}} daily observations from {{econdata_first}}."],
    ["Verification.", "Compared value by value with the SARB Web API (EXCX135D): {{overlap_n}} overlapping observations, largest difference {{overlap_max_diff}}, {{overlap_mismatches}} mismatches."],
    ["Predictors.", "Daily market series joined on when each value became public, with the vintage then current for revised series. Rules and sources are in series_metadata.json."],
    ["Timing check.", "With every non-spot predictor a week later the combination moves from {{timing_combo_base}} to {{timing_combo_extra}}."],
  ]), { x: M, y: 1.5, w: 6.6, h: 4.8, fontFace: F_, fontSize: 17, color: INK,
    bullet: true, paraSpaceAfter: 15, margin: 0 });
  s.addImage({ path: path.join(FIG, "input_series.png"), x: 7.5, y: 1.4,
    w: 5.3, h: 5.15 });
  cite(s, "SARB. MARKET_RATES 1.0.0. Pretoria: SARB [producer]. Johannesburg: EconData [distributor], 2026. Verification script: src/verify_provenance.py.");
  s.addNotes("Use for any data or look-ahead-bias question.");
}
{
  const s = appx("D", "Adaptive weights stayed between {{w_min}} and {{w_max}}, close to equal weighting");
  s.addImage({ path: path.join(FIG, "combination_weights.png"), x: M, y: 1.5,
    w: 7.6, h: 3.38 });
  s.addText([{ text: F("Chosen on {{val_first}} to {{val_last}}:"),
               options: { bold: true, breakLine: true } }].concat(bullets([
    "ridge on {{chosen_ridge_desc}}",
    "decay {{chosen_delta}} on past errors",
    "sharpness {{chosen_theta}}",
    "window of 156 resolved origins",
  ])), { x: 8.5, y: 1.6, w: 4.3, h: 3.2, fontFace: F_, fontSize: 17, color: INK,
      bullet: true, paraSpaceAfter: 10, margin: 0 });
  s.addText(F("The three components' errors are almost the same series (correlation up to {{max_err_corr}}), so inverse-error weights barely move off one third each. An equal-weight average scores {{rmse_equal3}} against {{rmse_combo}} for the adaptive combination."),
    { x: M, y: 5.2, w: 12.1, h: 1.2, fontFace: F_, fontSize: 18, color: INK,
      margin: 0 });
  cite(s, "Own calculation. Full validation grid in validation_metrics.json; those scores were used for selection.");
  s.addNotes("Use for: how does the combination adapt, and how do we know settings were frozen before the judged window.");
}
{
  const s = appx("E", "Gradient boosting scored {{rmse_gbm}}, the highest of {{n_models}} models, for this specification");
  s.addShape(pres.ShapeType.roundRect, { x: M, y: 1.55, w: 5.9, h: 4.4,
    rectRadius: 0.1, fill: { color: PALE }, line: { color: RULE } });
  sectionHead(s, "What we ran", 0.95, 1.8, 5.2);
  s.addText(F("HistGradientBoosting with a fixed seed. Every {{gbm_retune_every}} weeks, purged cross-validation picks its depth, learning rate, iterations, L2 penalty and leaf size from {{gbm_grid_n}} configurations. Same information set, same embargo and same walk-forward loop as every other model."),
    { x: 0.95, y: 2.3, w: 5.2, h: 3.4, fontFace: F_, fontSize: 18, color: INK,
      margin: 0, valign: "top" });
  s.addShape(pres.ShapeType.roundRect, { x: 6.85, y: 1.55, w: 5.9, h: 4.4,
    rectRadius: 0.1, fill: { color: PALE }, line: { color: RULE } });
  sectionHead(s, "What we can say", 7.2, 1.8, 5.2);
  s.addText(F("It is {{gbm_worse_than_ar1_pct}}% above the AR(1) and {{gbm_worse_than_rw_pct}}% above the random walk, and neither difference is significant (p = {{gbm_p_vs_ar1}}, {{gbm_p_vs_rw}}). With every predictor a week later its RMSE moves from {{timing_gbm_base}} to {{timing_gbm_extra}}. We have not diagnosed why it does worse, and the result covers this feature set, grid and sample only."),
    { x: 7.2, y: 2.3, w: 5.2, h: 3.4, fontFace: F_, fontSize: 18, color: INK,
      margin: 0, valign: "top" });
  cite(s, "The M5 accuracy results paper (Makridakis, Spiliotis and Assimakopoulos, 2022) reports that the top methods were ML methods, mostly LightGBM, and that combinations helped.");
  s.addNotes("Use for: why didn't you use machine learning. We did, with a small tuned grid, and it scored worst here. That says nothing general about machine learning: the M5 results paper reports the top methods there were ML methods, mostly LightGBM, and that combinations helped.");
}
{
  const s = appx("F", "Forecasts stay close to the current rate and lag the realised series");
  s.addImage({ path: path.join(FIG, "forecasts_vs_actual.png"), x: 1.3, y: 1.45,
    w: 10.7, h: 5.03 });
  cite(s, "Own calculation. Forecasts plotted at their target dates against EXCX135.");
  s.addNotes("Use if a judge asks to see the forecasts themselves.");
}
{
  const s = appx("G", "One forecast in full: {{ex_origin}}");
  const how = {
    "Random walk": "today's rate, unchanged",
    "Carry": F("{{ex_spot}} x (1 + {{ex_carry_diff}} x 28/365)"),
    "AR(1), log level (benchmark)": F("iterated 4 steps towards its long-run level, R{{ex_ar1_mu}} that day"),
    "Ridge": "small tilt away from spot",
    "Gradient boosting": "boosted trees on the same predictors",
    "Combination": F("{{ex_w_rw}} x RW + {{ex_w_carry}} x Carry + {{ex_w_ridge}} x Ridge"),
  };
  const rows = [[hdr("Model"), hdr("Forecast"), hdr("How it got there"), hdr("Error")]];
  T.worked.slice(1).forEach((r) => {
    const b = r[0] === "Combination";
    const o = b ? { bold: true } : {};
    rows.push([{ text: r[0], options: o }, { text: r[1], options: o }, how[r[0]], { text: r[2], options: o }]);
  });
  s.addTable(rows, { x: M, y: 1.5, w: W, colW: [3.2, 1.7, 5.2, 2.0], fontFace: F_,
    fontSize: 14, color: INK, valign: "middle",
    border: { pt: 0.5, color: RULE }, rowH: 0.5, margin: 0.06 });
  s.addText(F("Origin {{ex_origin}}, spot R{{ex_spot}}. Target {{ex_target}}, actual R{{ex_realized}}. {{ex_all_too_low}}. The forecasts span {{ex_spread_cents}} cents against an actual move of {{ex_move_cents}} cents."),
    { x: M, y: 5.3, w: W, h: 1.2, fontFace: F_, fontSize: 18, color: INK,
      margin: 0 });
  cite(s, "Own calculation from forecast_log.csv and combo_weights.csv. Rows sorted by forecast.");
  s.addNotes("Use if asked what the model actually does. It is the whole project in one month.");
}
{
  const s = appx("H", "All 2021 to 2025 results are exploratory; a prospective test needs forecasts made after the design is frozen");
  const rows = [[hdr("RMSE cut"), hdr("Origins needed vs AR(1)"), hdr("Origins needed vs RW")]];
  T.plan_ar1.slice(1).forEach((r, i) => rows.push([r[0], r[1], T.plan_rw[i + 1][1]]));
  s.addTable(rows, { x: M, y: 1.65, w: 5.9, colW: [1.4, 2.4, 2.1], fontFace: F_,
    fontSize: 15, color: INK, valign: "middle", align: "center",
    border: { pt: 0.5, color: RULE }, rowH: 0.5, margin: 0.06 });
  s.addText(F("Two-sided 5% test, 80% power, with the loss differential's spread and the benchmark's MSE held at their 2021 to 2025 values. Against the random walk the counts are small only because the combination and the random walk are nearly the same forecast, so a 1 to 5% cut between them is implausible. Effect sizes are round numbers fixed in advance. The table says nothing about any other forecaster."),
    { x: M, y: 4.3, w: 5.9, h: 2.4, fontFace: F_, fontSize: 14, color: INK, margin: 0 });
  sectionHead(s, "Protocol", 7.0, 1.55, 5.6);
  s.addText(bullets([
    "Freeze the commit, the chosen configuration and the data snapshot before the first new origin.",
    "Prespecify two tests: combination against the AR(1) and against the random walk.",
    "Fix the sample size and stop date from the planning table.",
    "Score each origin once, in a log that is only appended to.",
    "Report the result whatever it is.",
  ]), { x: 7.0, y: 2.0, w: 5.7, h: 4.4, fontFace: F_, fontSize: 17, color: INK,
    bullet: true, paraSpaceAfter: 12, margin: 0 });
  cite(s, "Details in docs/METHODOLOGY.md, section 13.");
  s.addNotes("Use for: how would you test this properly. The 2021 to 2025 window was scored repeatedly during development, so a clean test needs new origins.");
}

pres.writeFile({ fileName: path.join(__dirname, "..", "reports", "presentation.pptx") })
  .then(() => console.log("reports/presentation.pptx written: 6 presented + references + 8 appendix"));
