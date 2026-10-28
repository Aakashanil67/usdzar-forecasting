"""
make_report.py - Builds reports/technical_report.pdf.

Prose is written with {{key}} placeholders and filled from the saved outputs by
render_docs.fill(); tables come from render_docs.TABLES. Nothing here types a
result by hand. Run render_docs.py (or run_all.py) first.
"""
import json
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

from render_docs import TABLES, fill

BASE = Path(__file__).resolve().parents[1]
PROC, FIG, REP = BASE / "data" / "processed", BASE / "figures", BASE / "reports"
REP.mkdir(exist_ok=True)

VAL = json.load(open(PROC / "validation_metrics.json"))
RIDGE_SET = "full" if VAL["chosen_config"]["ridge"].startswith("RIDGE_f") else "compact"
PREDICTORS = {
    "compact": "carry differential, four-week returns on gold, platinum and "
               "the broad dollar, and the VIX z-score",
    "full": "carry differential and its four-week change, four-week returns "
            "on gold, platinum, Brent, the broad dollar and the rand, the "
            "twelve-week rand return, the VIX z-score and its four-week "
            "change, and the gap to the moving average"}[RIDGE_SET]

TEAM = ["Team: Spurious Decision",
        "Aakash Anil and Stefan von der Heyden",
        "Stellenbosch University"]
if (REP / "team.txt").exists():
    TEAM = [ln.strip() for ln in open(REP / "team.txt", encoding="utf-8")
            if ln.strip()]

S = getSampleStyleSheet()
NAVY, BLUE = colors.HexColor("#123a5f"), colors.HexColor("#1a5f8f")
H1 = ParagraphStyle("h1", parent=S["Heading1"], spaceBefore=14, spaceAfter=6,
                    textColor=NAVY, keepWithNext=True)
H2 = ParagraphStyle("h2", parent=S["Heading2"], spaceBefore=10, spaceAfter=4,
                    textColor=BLUE, keepWithNext=True)
P = ParagraphStyle("p", parent=S["BodyText"], fontSize=9.5, leading=13.5,
                   spaceAfter=6, alignment=4)
SMALL = ParagraphStyle("s", parent=P, fontSize=8, leading=11,
                       textColor=colors.HexColor("#444444"))
TEXT_WIDTH = 17.0                      # cm, A4 less the 2 cm margins


def para(txt, style=P):
    return Paragraph(fill(txt), style)


def figure(name, width, caption):
    """An image and its caption, kept on one page."""
    w, h = PILImage.open(FIG / name).size
    return KeepTogether([Image(str(FIG / name), width=width * cm,
                               height=width * cm * h / w),
                         para(caption, SMALL), Spacer(1, 4)])


def table(rows, widths, bold_row=None, caption=None):
    """Header row repeats if the table runs onto another page."""
    cells = [[Paragraph(c, ParagraphStyle("c", parent=SMALL, alignment=1 if j else 0,
                                          textColor=colors.white if i == 0 else colors.black,
                                          fontName="Helvetica-Bold" if (i == 0 or r[0] == bold_row)
                                          else "Helvetica"))
              for j, c in enumerate(r)] for i, r in enumerate(rows)]
    t = Table(cells, colWidths=[w * cm for w in widths], repeatRows=1)
    style = [("BACKGROUND", (0, 0), (-1, 0), NAVY),
             ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
             ("ROWBACKGROUNDS", (0, 1), (-1, -1),
              [colors.white, colors.HexColor("#f2f6fa")])]
    for i, r in enumerate(rows):
        if bold_row and r[0] == bold_row:
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#e8f4ec")))
    t.setStyle(TableStyle(style))
    return [t] + ([para(caption, SMALL), Spacer(1, 4)] if caption else [Spacer(1, 6)])


def prespecified_rows():
    return [["Comparison", "DM (lag 3)", "p", "95% interval, mean squared-error difference",
             "RMSE difference", "p across four lags"],
            ["Combination vs AR(1)", "{{dm_combo_ar1}}", "{{p_combo_ar1}}",
             "{{ci_combo_ar1_lo}} to {{ci_combo_ar1_hi}}", "{{rmse_diff_combo_ar1}}",
             "{{p_combo_ar1_min}} to {{p_combo_ar1_max}}"],
            ["Combination vs random walk", "{{dm_combo_rw}}", "{{p_combo_rw}}",
             "{{ci_combo_rw_lo}} to {{ci_combo_rw_hi}}", "{{rmse_diff_combo_rw}}",
             "{{p_combo_rw_min}} to {{p_combo_rw_max}}"]]


def filled(rows):
    return [[fill(c) for c in r] for r in rows]


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawRightString(A4[0] - 2 * cm, 1.0 * cm, f"Page {doc.page}")
    canvas.restoreState()


def main():
    doc = SimpleDocTemplate(str(REP / "technical_report.pdf"), pagesize=A4,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            title="USDZAR 1-Month-Ahead Forecasting",
                            author=", ".join(TEAM),
                            invariant=1)       # fixed dates and document id
    E = []

    # ---------------- title ----------------
    E.append(Spacer(1, 3 * cm))
    E.append(para("Forecasting USDZAR one month ahead",
                  ParagraphStyle("t", parent=S["Title"], fontSize=22)))
    E.append(para("a forecast combination against the AR(1) benchmark and the random walk",
                  ParagraphStyle("st", parent=S["Title"], fontSize=15, textColor=BLUE)))
    E.append(Spacer(1, 1 * cm))
    E.append(para("SES x Codera Analytics Hackathon, July 2026",
                  ParagraphStyle("c", parent=P, alignment=1, fontSize=11)))
    E.append(para("<br/>".join(TEAM),
                  ParagraphStyle("c2", parent=P, alignment=1, fontSize=10)))
    E.append(para("Built from the saved pipeline outputs.",
                  ParagraphStyle("c3", parent=SMALL, alignment=1)))
    E.append(PageBreak())

    # ---------------- 1. summary ----------------
    E.append(para("1. Summary", H1))
    E.append(para(
        "We forecast USDZAR four weeks ahead at {{n_origins}} Fridays, from "
        "{{first_origin}} to {{last_origin}}, and scored the forecasts against the "
        "mandated AR(1) benchmark. Our forecast combination, an average of a "
        "random walk, a carry forecast and a shrunk ridge regression, scored an "
        "RMSE of {{rmse_combo}} against {{rmse_ar1_log}} for the "
        "AR(1), which is {{gain_vs_ar1}} per cent lower. The difference is not "
        "statistically established. The Diebold-Mariano p-value is "
        "{{p_combo_ar1}}, and the 95% interval for the mean squared-error "
        "difference runs from {{ci_combo_ar1_lo}} to {{ci_combo_ar1_hi}}, which "
        "includes zero. Against the random walk, whose RMSE is {{rmse_rw}}, the "
        "combination is level (p = {{p_combo_rw}}). In practice it is the random "
        "walk with a small tilt: its forecasts sit {{combo_mean_abs_dev_pct}} per "
        "cent from spot on average."))
    E.append(para(
        "Two further results limit what the combination can claim. An "
        "equal-weight average of the same three components scored "
        "{{rmse_equal3}}, so the adaptive weighting contributes nothing we can "
        "measure. The weights stayed between {{w_min}} and {{w_max}}, because the "
        "components' errors are almost the same series (correlation up to "
        "{{max_err_corr}}). And the one flexible model we ran, gradient boosting, "
        "scored {{rmse_gbm}}, the highest of the {{n_models}} models. That "
        "conclusion covers this specification and nothing broader."))
    E.append(para(
        "The AR(1) differs from the other models in a way we can measure. Its "
        "implied long-run level sat below spot at {{n_below_spot}} of "
        "{{n_origins}} origins, by R{{mean_gap}} on average, and it never "
        "forecast a rise. The difference in squared bias accounts for "
        "{{bias_share_of_gap_pct}} per cent of its excess squared error against "
        "the combination. We report this as an observation and have not shown "
        "that it is the whole explanation."))
    E.append(para(
        "All 2021 to 2025 results are exploratory. The window was scored "
        "repeatedly while the code was built and repaired, comparisons were added "
        "after earlier results had been seen, and no new holdout exists. Section 7 "
        "sets out a protocol for a prospective test."))

    # ---------------- 2. task and protocol ----------------
    E.append(para("2. Task and protocol", H1))
    E.append(para(
        "The brief is to forecast USDZAR (SARB series EXCX135, distributed "
        "through EconData) one month ahead, every Friday, out of sample, over "
        "2021 to 2025, and to compare RMSE against an AR(1) model."))
    E.append(para(
        "We read it this way. Every Friday t from {{first_origin}} to "
        "{{last_origin}} is an origin, which gives {{n_origins}} of them. Spot at "
        "t is the last EXCX135 fixing dated on or before t. The target is the "
        "EXCX135 fixing 28 calendar days later, or the last fixing before that "
        "date when it falls on a holiday. The last target falls on "
        "{{last_target}}, after the end of 2025, and {{n_targets_in_2025}} of the "
        "{{n_origins}} targets fall inside 2025. Twenty-eight days keeps origin and "
        "target on the same weekday. We did not rerun the exercise with calendar "
        "months. The information set at t holds only values that were public by "
        "17:00 Johannesburg time on the Friday, each joined on its publication "
        "time, with the vintage then current for series that are revised "
        "(section 3)."))

    # ---------------- 3. data ----------------
    E.append(para("3. Data", H1))
    E.append(para(
        "<b>Target series.</b> EXCX135 is the rand per US dollar rate, "
        "calculated as the weighted average of the banks' daily rates at "
        "approximately 10:30 and weighted by their foreign exchange turnover. "
        "The SARB publishes it and EconData distributes it. We use the official "
        "EconData export as the primary source: dataset MARKET_RATES v1.0.0, "
        "series key EXCX135.B.A, {{econdata_n}} daily observations from "
        "{{econdata_first}}. The pipeline also downloads the same series from the "
        "SARB Web API under code EXCX135D, and verify_provenance.py compares the "
        "two: {{overlap_n}} overlapping observations, largest absolute "
        "difference {{overlap_max_diff}}, {{overlap_mismatches}} mismatches, "
        "including all {{window_overlap_n}} observations in the forecast window. "
        "Citation: SARB. MARKET_RATES. Version 1.0.0. Pretoria: SARB [producer]. "
        "Johannesburg: EconData [distributor], 2026."))
    E.append(para(
        "<b>Predictors.</b> JIBAR 3M from the SARB and the US 3M Treasury bill "
        "from FRED, whose difference is the carry signal. Gold at the London "
        "fixing, platinum futures from NYMEX and Brent from FRED make up the "
        "commodity block: South Africa exports two of those and imports the "
        "third. The Fed's broad dollar index and the VIX capture dollar strength "
        "and global risk appetite. Technical variables complete the set: the "
        "rand's own four- and twelve-week returns and its gap to the 200-day "
        "moving average. Estimation history starts in {{history_start_year}}."))
    E.append(para(
        "<b>When each value is known.</b> The forecast is issued at 17:00 "
        "Johannesburg time. The SARB rate and JIBAR are public that morning. The "
        "gold fix is public that afternoon in UK summer and a day earlier in UK "
        "winter. Platinum and the VIX are available to the Thursday close, the "
        "T-bill rate to Wednesday, Brent to the Monday and the dollar index to the "
        "previous Friday. The dollar index, Brent, the T-bill rate and the VIX "
        "are revised, so each takes the value ALFRED, the St. Louis Fed's vintage "
        "archive, showed at the time, and a four-week return takes both ends from "
        "one vintage. Before a series' first vintage (for the dollar index, "
        "{{usd_broad_first_vintage}}) the earliest vintage stands in, which is an "
        "approximation. Each series' rule, source and reasoning is in "
        "data/raw/series_metadata.json. The gold rule is the least certain: the "
        "30 minutes after the auction is our allowance, not a published time. "
        "Section 7 reports a rerun with every non-spot predictor a further week "
        "late."))
    E.append(para(
        "<b>What is left out.</b> We used no inflation, current-account or GDP "
        "series. They are published late and revised, and we hold no vintages "
        "for them. Using today's published history in a simulated 2021 forecast "
        "would use numbers that did not exist then."))
    E.append(figure("input_series.png", 14.5,
                    "Figure 3.1. Every series used in the models, as known at each "
                    "Friday 17:00 issuance."))
    E.append(figure("summary_statistics.png", 15.5,
                    "Table 3.1. Observation counts split between the estimation era "
                    "before 2021 and the forecast era from 2021 to 2025, with "
                    "descriptive statistics."))

    # ---------------- 4. methodology ----------------
    E.append(para("4. Methodology", H1))
    E.append(para("4.1 The baseline", H2))
    E.append(para(
        "AR(1) with intercept on the weekly log USDZAR level, re-estimated by "
        "OLS on an expanding window at every origin and iterated four steps "
        "ahead. Its judged-window RMSE is {{rmse_ar1_log}}. It was fixed as the "
        "benchmark before scoring. Three variants appear only as exploratory "
        "comparisons: the same model on the level ({{rmse_ar1_level}}), on a "
        "five-year window ({{rmse_ar1_log_roll}}), and with a retransformation "
        "correction ({{rmse_ar1_log_vc}}). The correction matters because the "
        "exponential of a forecast of the log is a median, not a mean, under "
        "normal errors. For the log AR(1) the level the forecast is pulled towards "
        "is exp(c/(1-phi)), the equilibrium of the log. It is fragile near a unit "
        "root: phi ran from {{phi_min}} to {{phi_max}} across the origins, so "
        "1-phi ran from {{one_minus_phi_min}} to {{one_minus_phi_max}}, and the "
        "level ranged from R{{mu_min}} to R{{mu_max}}. At the worked-example "
        "origin, {{ex_origin}}, the fit on {{ex_ar1_n}} weekly observations gave "
        "c = {{ex_ar1_c}} and phi = {{ex_ar1_phi}}, a level of R{{ex_ar1_mu}} and "
        "a shock half-life of {{ex_half_life}} weeks. Spot that day was "
        "R{{ex_spot_short}}."))
    E.append(para("4.2 Component models", H2))
    E.append(para(
        "<b>Random walk.</b> The forecast is today's rate. <b>Carry.</b> Covered "
        "interest parity ties the forward rate to the interest differential, so "
        "the forecast is the spot rate multiplied by one plus the JIBAR minus "
        "T-bill gap scaled to 28 days. A forward prices a contract that can be "
        "locked in today. It is not the expected future spot rate, and uncovered "
        "parity generally fails, so we treat carry as one component and make no "
        "claim that it forecasts well alone. The inputs also differ in kind (a "
        "bank rate against a government bill) and in tenor (three months against "
        "a 28-day horizon). <b>Ridge regression.</b> The four-week log return "
        "regressed on the {{chosen_ridge_desc}}: " + PREDICTORS + ". The penalty "
        "is re-selected every 13 origins by five-fold time-ordered "
        "cross-validation. A training row whose target date falls on or after "
        "the start of the fold it is scored against is purged, and the "
        "predictors are standardised inside each fold. Training rows are "
        "restricted to origins whose 28-day outcome had already resolved. With "
        "no intercept, heavy shrinkage collapses the model to the random walk. "
        "<b>Gradient boosting.</b> A HistGradientBoosting comparator on the same "
        "rows. Every {{gbm_retune_every}} weeks the same purged "
        "cross-validation picks its depth, learning rate, iteration count, L2 "
        "penalty and leaf size from {{gbm_grid_n}} configurations."))
    E.append(para("4.3 The combination and the selection step", H2))
    E.append(para(
        "The combination weights the random walk, carry and ridge by inverse "
        "discounted mean squared error over resolved past forecasts only, with a "
        "28-day embargo, a window of 156 resolved origins, decay {{chosen_delta}} "
        "and sharpness {{chosen_theta}}. The ridge variant, the decay and the "
        "sharpness were selected on {{val_n}} validation origins from "
        "{{val_first}} to {{val_last}}. The last of them is the final Friday whose "
        "target, {{val_last_target}}, falls before 2021, and the code asserts it. "
        "The chosen ridge variant is {{chosen_ridge_tag}} and the full grid of "
        "{{n_grid}} configurations is in validation_metrics.json. Validation "
        "scores were used to pick the configuration, so they are not independent "
        "evidence. The surface is flat: the fifth-best configuration is "
        "{{val_top5_gap}} worse than the best. Weights for the first judged "
        "forecasts were warmed up on walk-forward forecasts from 2013."))

    # ---------------- 5. results ----------------
    E.append(para("5. Results", H1))
    E += table(filled(TABLES["results"]), [4.9, 1.9, 1.9, 2.8, 1.5, 2.4], "Combination",
               "Table 5.1. Judged window, n = {{n_origins}}. RMSE below AR(1) is the "
               "per cent by which a model's RMSE is under the benchmark's, so a "
               "positive value favours the model. Rank is by RMSE across the "
               "{{n_models}} models. The first row is the mandated benchmark; "
               "the AR(1) variants, the drift, the equal-weight average and the "
               "two adaptive pairs are exploratory. On the strict cut, with "
               "targets inside 2025 only, the combination scores {{strict_combo}}, "
               "the AR(1) {{strict_ar1_log}} and the random walk {{strict_rw}}. "
               "That cut is a subset of the same data.")
    E.append(figure("rmse_by_model.png", 12.0,
                    "Figure 5.1. RMSE by model. The axis starts at zero, so the bars "
                    "look level: the differences are in the third decimal place. "
                    "Figure 5.2 shows them with intervals."))
    E.append(figure("rmse_difference_ci.png", 13.0,
                    "Figure 5.2. RMSE difference from the random walk and from the "
                    "AR(1), with 95% Newey-West intervals (lag 3). Filled points "
                    "are the two prespecified comparisons. Left of zero means the "
                    "model is more accurate."))
    E += table(filled(prespecified_rows()), [3.6, 1.6, 1.4, 4.2, 2.2, 4.0], None,
               "Table 5.2. The two prespecified comparisons. DM is the "
               "Diebold-Mariano statistic on squared error with a Newey-West "
               "variance; a negative value favours the combination. The last "
               "column shows the range of p-values over HAC lags 3, 4, 8 and the "
               "Andrews (1991) automatic choice, which was {{auto_lag_ar1}} "
               "against the AR(1) and {{auto_lag_rw}} against the random walk. "
               "The RMSE interval against the AR(1), holding the "
               "benchmark's MSE fixed, is {{rmse_ci_combo_ar1_lo}} to "
               "{{rmse_ci_combo_ar1_hi}}.")
    E += table(filled(TABLES["dm"]), [4.9, 1.8, 1.4, 1.6, 1.8, 1.4, 1.6], "Combination (prespecified)",
               "Table 5.3. Every model against both benchmarks at HAC lag 3. The "
               "{{n_exploratory}} distinct exploratory hypotheses are adjusted "
               "together by Holm's method ({{n_exploratory_unadjusted}} have an "
               "unadjusted p below 0.05, {{n_holm_significant}} survive). n/a marks "
               "the prespecified comparisons, which are not adjusted.")
    E.append(figure("cumulative_error_difference.png", 14.0,
                    "Figure 5.3. Cumulative squared-error difference, positive when "
                    "the combination is ahead. Against the AR(1) it ends 2021 at "
                    "{{cum_end_2021}}, 2022 at {{cum_end_2022}}, 2023 at "
                    "{{cum_end_2023}} and 2024 at {{cum_end_2024}}, peaks at "
                    "{{cum_peak}} on {{cum_peak_date}} and finishes at "
                    "{{cum_final}}. The line against the random walk stays much "
                    "closer to zero."))
    E.append(figure("rmse_by_year.png", 14.0,
                    "Figure 5.4. RMSE by calendar year of origin. The combination is "
                    "lower than the AR(1) in {{years_ahead_n}} of {{years_n}} years "
                    "({{years_ahead}}). In {{years_behind}} the AR(1) scored "
                    "{{behind_ar1}} against {{behind_combo}} for the combination. We "
                    "have not tested why. Five annual figures cannot show whether "
                    "the pattern is stable."))
    E.append(figure("forecasts_vs_actual.png", 14.0,
                    "Figure 5.5. Forecasts plotted at their target dates against the "
                    "realised series."))
    E.append(figure("combination_weights.png", 14.0,
                    "Figure 5.6. Combination weights through time, computed from "
                    "resolved errors only. They stay between {{w_min}} and "
                    "{{w_max}}, close to one third each."))

    # ---------------- 6. discussion ----------------
    E.append(para("6. Discussion", H1))
    E.append(para(
        "The differences between the leading models are small: the {{n_rw_family}} "
        "models built from the random walk, carry and ridge fall within "
        "{{rmse_spread_rw_family}} of each other in RMSE. A common explanation is "
        "that USDZAR is priced by a deep market, so public information is in the "
        "price quickly and a month-ahead forecast is left with a small residual. "
        "That is plausible and consistent with Meese and Rogoff (1983) and the "
        "survey by Rossi (2013), but nothing here tests it."))
    E.append(para(
        "The combination is almost the random walk. Its forecasts differ from "
        "spot by {{combo_mean_abs_dev_pct}} per cent on average. It forecast a "
        "rise at {{combo_up_pct}} per cent of origins, because carry's tilt is "
        "always upward, while the rand rose at {{realized_up_pct}} per cent of "
        "them, so its directional accuracy ({{combo_dir_acc_pct}} per cent) is just "
        "the share of rises. It carries no directional information. Adaptive "
        "weighting did not help: equal weights scored {{rmse_equal3}} against "
        "{{rmse_combo}}, and the largest gap among the three ablations is "
        "{{ablation_max_gap}}."))
    E.append(para(
        "What we can say about the AR(1) is descriptive. It forecast a rise at "
        "{{ar1_up_pct}} per cent of origins, its mean error was {{ar1_bias}} "
        "against {{combo_bias}} for the combination, and squared bias is "
        "{{ar1_bias_share_pct}} per cent of its mean squared error. The "
        "difference in squared bias is {{bias_share_of_gap_pct}} per cent of the "
        "gap in mean squared error between the AR(1) and the combination, and the "
        "rest is variance. A mean-reverting model does better in a sample where "
        "the series reverts. We do not claim that the downward lean is the full "
        "explanation or that it persists."))
    E.append(para(
        "Gradient boosting scored {{rmse_gbm}}, {{gbm_worse_than_ar1_pct}} per "
        "cent above the AR(1) and {{gbm_worse_than_rw_pct}} per cent above the "
        "random walk. Neither difference is statistically significant (p = "
        "{{gbm_p_vs_ar1}} and {{gbm_p_vs_rw}}). The M5 accuracy results paper "
        "(Makridakis, Spiliotis and Assimakopoulos, 2022, International Journal "
        "of Forecasting) reports that the top methods were machine-learning "
        "methods, mostly LightGBM, and that combinations helped. So that "
        "evidence does not say that simple methods beat flexible ones, and our "
        "boosting result covers one specification on one series. It is also "
        "sensitive to the release-lag assumptions: with every non-spot predictor "
        "a week later its RMSE moves from {{timing_gbm_base}} to "
        "{{timing_gbm_extra}}, while the combination moves from "
        "{{timing_combo_base}} to {{timing_combo_extra}}."))
    E.append(para(
        "The AR(1) and the combination have MAEs of {{mae_ar1_log}} and "
        "{{mae_combo}}. Over {{roll_windows}} rolling {{roll_weeks}}-week windows "
        "the combination had the lower RMSE in {{roll_share}} per cent of them, "
        "with a ratio to the AR(1) between {{roll_best}} and {{roll_worst}}. "
        "Adjacent windows share most of their origins, so that is one comparison "
        "seen through a moving frame."))

    # ---------------- 7. limitations ----------------
    E.append(para("7. Limitations, exploratory status and a prospective test", H1))
    E.append(para(
        "All 2021 to 2025 results are exploratory. The window was scored "
        "repeatedly during development and repair, benchmarks and ablations were "
        "added after "
        "results had been seen, and no new holdout was added. The two prespecified "
        "comparisons are labelled in the code and the outputs, but nothing "
        "registered them outside the repository. Neither "
        "prespecified comparison rejects at 5 per cent, and none of the "
        "{{n_exploratory}} exploratory comparisons survives the Holm adjustment "
        "(smallest adjusted p = {{min_holm_p}})."))
    E.append(para(
        "Tables 7.1 and 7.2 give the number of weekly origins at which a "
        "two-sided 5 per cent test would detect an RMSE reduction fixed in "
        "advance, with 80 per cent power. They depend on their assumptions: the "
        "standard deviation of the loss differential and the benchmark's MSE "
        "stay at their 2021 to 2025 values, and the effect sizes are round "
        "numbers, not a claim about what has been achieved elsewhere. Against "
        "the AR(1), a 2 per cent reduction needs {{plan_ar1_2_n}} origins "
        "({{plan_ar1_2_years}} years) and a 1 per cent reduction {{plan_ar1_1_n}} "
        "({{plan_ar1_1_years}} years). Against the random walk the requirements "
        "are small only because the combination and the random walk are nearly "
        "the same forecast, which keeps the loss differential's standard "
        "deviation at {{plan_rw_sd}}. A 1 to 5 per cent reduction between two "
        "forecasts that differ by {{combo_mean_abs_dev_pct}} per cent of spot is "
        "implausible, so those rows show what the test could detect, not what "
        "a holdout should be expected to find. The table says nothing about any "
        "other forecaster."))
    E += table(filled(TABLES["plan_ar1"]), [3.0, 3.6, 4.6, 4.0], None,
               "Table 7.1. Planning table against the AR(1).")
    E += table(filled(TABLES["plan_rw"]), [3.0, 3.6, 4.6, 4.0], None,
               "Table 7.2. Planning table against the random walk.")
    E.append(para(
        "A prospective holdout would run in five steps. (1) Freeze the design: "
        "record the git commit, the chosen configuration and the raw-data snapshot date, "
        "publish them before the first new origin, and change nothing afterwards "
        "except recorded bug fixes. (2) Prespecify the two comparisons, squared "
        "error, Newey-West lag 3, two-sided 5 per cent, and treat everything "
        "else as exploratory with a Holm adjustment. (3) Fix the sample size and "
        "stop date from the planning table before the first origin. (4) Score each "
        "origin once, after its target is fixed, in a log that is only appended "
        "to. (5) Report the result whatever it is."))
    E.append(para(
        "Overlapping four-week forecasts and the "
        "overlapping cuts (the strict cut, by-year results and rolling windows) are "
        "views of the same {{n_origins}} errors, not independent checks. The "
        "release lags are partly judgement. We tested one alternative, a further "
        "week for every non-spot predictor: the combination's RMSE moved by "
        "{{timing_max_other_change}} or less for every model except gradient "
        "boosting, which moved by {{timing_gbm_change}}. We make no claim about "
        "profitability. RMSE and trading return are different objectives."))
    E.append(para(
        "The first extension we would try is option-implied volatility and risk "
        "reversals, since the SARB's working paper WP/22/14 reports that "
        "information about the distribution of rand returns improves its "
        "forecasts. After that: Bayesian model averaging over a wider component "
        "set, horizons of 1, 2, 8 and 12 weeks, and density rather than point "
        "forecasts, which matter more to anyone deciding whether to hedge."))

    # ---------------- 8. reproducibility ----------------
    E.append(para("8. Code and reproducibility", H1))
    E.append(para(
        "The full pipeline reruns end to end with one command, python "
        "src/run_all.py. By default it needs no network access, no paid data and "
        "no API key, because the raw files are committed. Every number in this "
        "report is read from the saved JSON outputs at build time, so the text "
        "cannot drift from the results. All {{n_origins}} forecasts are logged to "
        "forecast_log.csv with their origin date, target date, each model's "
        "forecast and the realised value, so each RMSE here can be recomputed "
        "from that file in a single line."))

    # ---------------- 9. references ----------------
    E.append(para("9. References", H1))
    for r in [
        "Andrews, D. W. K. (1991). Heteroskedasticity and autocorrelation "
        "consistent covariance matrix estimation. Econometrica 59(3).",
        "Diebold, F. X. and R. S. Mariano (1995). Comparing predictive accuracy. "
        "Journal of Business and Economic Statistics 13(3), 253-263.",
        "Holm, S. (1979). A simple sequentially rejective multiple test "
        "procedure. Scandinavian Journal of Statistics 6(2).",
        "Makridakis, S., E. Spiliotis and V. Assimakopoulos (2022). M5 accuracy "
        "competition: results, findings, and conclusions. International Journal "
        "of Forecasting.",
        "Meese, R. and K. Rogoff (1983). Empirical exchange rate models of the "
        "seventies: do they fit out of sample? Journal of International "
        "Economics 14, 3-24.",
        "Newey, W. K. and K. D. West (1987). A simple, positive semi-definite, "
        "heteroskedasticity and autocorrelation consistent covariance matrix. "
        "Econometrica 55(3).",
        "Rossi, B. (2013). Exchange rate predictability. Journal of Economic "
        "Literature 51(4), 1063-1119.",
        "South African Reserve Bank (2022). Working Paper WP/22/14: can the "
        "distribution of rand returns improve exchange rate forecasts?",
    ]:
        E.append(para("- " + r, SMALL))

    doc.build(E, onFirstPage=footer, onLaterPages=footer)
    print("report written:", REP / "technical_report.pdf")


if __name__ == "__main__":
    main()
