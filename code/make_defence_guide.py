"""
make_defence_guide.py — Builds report/Defence_Guide.pdf

A condensed version of the full project guide: every explanation you need to
understand the project and defend it under questioning, with nothing you would
not use in the room. Roughly 14 pages against the full guide's 48.

Regenerate: python code/make_defence_guide.py
"""
import datetime as dt
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Image, PageBreak, Paragraph, Preformatted,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

BASE = Path(__file__).resolve().parents[1]
PROC, FIG, REP = BASE / "data" / "processed", BASE / "figures", BASE / "report"
EQD = REP / "_eq_defence"
EQD.mkdir(parents=True, exist_ok=True)
MET = json.load(open(PROC / "metrics.json"))

NAVY = colors.HexColor("#0E2A3B")
GREEN = colors.HexColor("#1A7A4A")
AMBER = colors.HexColor("#8A5A00")
GREY = colors.HexColor("#555555")
BOX = colors.HexColor("#EFF4F9")
WARN = colors.HexColor("#FFF6E5")
CODEBG = colors.HexColor("#F6F8FA")

S = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=S["Heading1"], fontSize=16, spaceBefore=16,
                    spaceAfter=7, textColor=NAVY)
H2 = ParagraphStyle("H2", parent=S["Heading2"], fontSize=11.5, spaceBefore=11,
                    spaceAfter=4, textColor=colors.HexColor("#1a5f8f"))
P = ParagraphStyle("P", parent=S["BodyText"], fontSize=9.6, leading=14,
                   spaceAfter=6, alignment=4)
BUL = ParagraphStyle("B", parent=P, leftIndent=13, bulletIndent=3, spaceAfter=3)
SMALL = ParagraphStyle("S", parent=P, fontSize=8.2, leading=11, textColor=GREY)
CODE = ParagraphStyle("C", parent=S["Code"], fontSize=7.8, leading=10.2)
E = []
_n = [0]


def p(t, s=P):
    E.append(Paragraph(t, s))


def h1(t):
    E.append(Paragraph(t, H1))


def h2(t):
    E.append(Paragraph(t, H2))


def bullets(items):
    for it in items:
        E.append(Paragraph(it, BUL, bulletText="•"))
    E.append(Spacer(1, 4))


def eq(latex, size=12.5, maxw=13.0):
    _n[0] += 1
    path = EQD / f"e{_n[0]:02d}.png"
    fig = plt.figure(figsize=(0.01, 0.01))
    fig.text(0, 0, f"${latex}$", fontsize=size)
    fig.savefig(path, dpi=320, transparent=True, bbox_inches="tight",
                pad_inches=0.04)
    plt.close(fig)
    w, h = PILImage.open(path).size
    wc, hc = w / 320 * 2.54, h / 320 * 2.54
    if wc > maxw:
        hc *= maxw / wc
        wc = maxw
    im = Image(str(path), width=wc * cm, height=hc * cm)
    im.hAlign = "CENTER"
    E.append(Spacer(1, 4))
    E.append(im)
    E.append(Spacer(1, 6))


def panel(title, body, bg, border, tc):
    rows = []
    if title:
        rows.append([Paragraph(f"<b>{title}</b>", ParagraphStyle(
            "pt", parent=P, spaceAfter=3, textColor=tc))])
    rows.append([Paragraph(body, ParagraphStyle("pb", parent=P, spaceAfter=0))])
    t = Table(rows, colWidths=[15.4 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor(border)),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    E.append(t)
    E.append(Spacer(1, 8))


def box(t, b):
    panel(t, b, BOX, "#B7C9D8", NAVY)


def warn(t, b):
    panel(t, b, WARN, "#E0C088", AMBER)


def code(txt):
    t = Table([[Preformatted(txt, CODE)]], colWidths=[15.4 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CODEBG),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D6DEE6")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    E.append(t)
    E.append(Spacer(1, 8))


def table(rows, widths, fs=8.4, align="LEFT"):
    cell = ParagraphStyle("c", parent=P, fontSize=fs, leading=fs + 2.5,
                          spaceAfter=0, alignment=0)
    hc = ParagraphStyle("h", parent=cell, textColor=colors.white,
                        fontName="Helvetica-Bold")
    out = []
    for i, r in enumerate(rows):
        out.append([Paragraph(c, hc if i == 0 else cell)
                    if isinstance(c, str) else c for c in r])
    t = Table(out, colWidths=[w * cm for w in widths], repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), fs),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#AAB4BE")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#F4F7FA")])]))
    E.append(t)
    E.append(Spacer(1, 8))


def img(name, width=13.5, cap=None):
    w, h = PILImage.open(FIG / name).size
    E.append(Image(str(FIG / name), width=width * cm,
                   height=width * cm * h / w))
    if cap:
        E.append(Paragraph(cap, SMALL))
    E.append(Spacer(1, 6))


def f4(x):
    return f"{x:.4f}"


B = MET["AR1_log"]["rmse"]
C = MET["COMBO"]["rmse"]
GAIN = 100 * (1 - C / B)
GBM = 100 * (MET["GBM"]["rmse"] / B - 1)

# ====================================================================== TITLE
E.append(Spacer(1, 3.4 * cm))
p("Defence guide", ParagraphStyle("t", parent=S["Title"], fontSize=26,
                                  textColor=NAVY, spaceAfter=4))
p("everything you need to understand the project and answer for it",
  ParagraphStyle("t2", parent=S["Title"], fontSize=13.5,
                 textColor=colors.HexColor("#1a5f8f")))
E.append(Spacer(1, 0.9 * cm))
p("A condensed version of the full project guide. Same explanations, same "
  "mathematics, none of the material you would not use in the room. Read it "
  "twice before you present.",
  ParagraphStyle("t3", parent=P, alignment=1, leftIndent=34, rightIndent=34))
E.append(Spacer(1, 1.1 * cm))
p("Team <b>Spurious Decision</b><br/>Aakash Anil and Stefan von der Heyden<br/>"
  "SES x Codera Analytics Hackathon, July 2026",
  ParagraphStyle("t4", parent=P, alignment=1, fontSize=10.5))
E.append(PageBreak())

# ====================================================================== 1
h1("1. The one-minute version")
box("If you remember nothing else",
    f"We forecast USDZAR one month ahead, every Friday, for five years. That is "
    f"<b>{MET['COMBO']['n']} forecasts</b>. Our model scores an RMSE of "
    f"<b>{f4(C)}</b>. The AR(1) benchmark scores <b>{f4(B)}</b>. We are "
    f"<b>{GAIN:+.2f}% better</b>.<br/><br/>"
    "We win because the AR(1) has a bias we can measure. Its persistence is "
    "just below one, so every forecast gets pulled toward an implied long-run "
    "mean. We computed that mean at all 261 origins and <b>it sat below the "
    "actual market rate at every single one, by R2.11 on average</b>, while "
    "the rand climbed from R14.62 to R19.74. A small bias, repeated 261 times, "
    "and RMSE punishes the large misses that produces.<br/><br/>"
    "Our model is three simple pieces: a random walk anchor, a carry tilt, and "
    "a heavily shrunk regression. We combine them by how well each has been "
    "doing recently. Nothing is a black box.")

h2("The five numbers to know cold")
table([["Number", "What it is", "Where it comes from"],
       [f"<b>{f4(C)}</b>", "our RMSE", "forecast_log.csv, 261 forecasts"],
       [f"<b>{f4(B)}</b>", "AR(1) benchmark RMSE", "same file, same forecasts"],
       [f"<b>{GAIN:+.2f}%</b>", "our improvement", "1 minus 0.5600/0.5624"],
       ["<b>R2.11</b>", "average amount the AR(1) leaned below the market",
        "AR(1) refitted at each of 261 origins"],
       [f"<b>{GBM:.1f}%</b>", "how much gradient boosting LOST by",
        "same data, same rules, run as a control"],
       ["<b>0.47</b>", "Diebold-Mariano p-value against the benchmark",
        "not significant, and we say so"]],
      [2.3, 5.3, 7.8])

# ====================================================================== 2
h1("2. The problem, and why it is hard")
h2("What we were asked to do")
p("Forecast USDZAR (rand per US dollar) one month ahead, every Friday, from "
  "1 January 2021 to 31 December 2025, out of sample. Compare RMSE against an "
  "AR(1) model. Use the SARB's EXCX135 series from EconData so every team is "
  "scored on identical numbers.")

h2("Why beating the benchmark is genuinely hard")
p("In 1983 Meese and Rogoff showed that structural exchange-rate models lose "
  "to the laziest possible alternative, the no-change forecast, out of sample. "
  "They still lost when handed the true future values of their driving "
  "variables. Rossi's 2013 survey in the Journal of Economic Literature found "
  "the result has largely held.")
p("The reason is that USDZAR is priced by a large, liquid, well-informed "
  "market. Anything publicly knowable is in today's price within minutes. What "
  "is left to forecast a month out is small and unstable.")
warn("The sentence that protects you all evening",
     f"Published gains over naive benchmarks run at roughly <b>1 to 5 per cent "
     f"in RMSE</b>, and come from shrinkage and combination rather than "
     f"complexity (Amat, Michalski and Stoltz 2018; Darvas 2020). Our "
     f"{GAIN:.2f}% sits inside that range. If a team claims 20%, the likely "
     f"explanation is a data leak, not skill. Say this <i>before</i> you show "
     f"your number and a small result reads as honest rather than weak.")

# ====================================================================== 3
E.append(PageBreak())
h1("3. The measure: RMSE, and why it matters here")
p("We have 261 forecasts, so 261 errors, and we need one score. Averaging the "
  "errors does not work because positives and negatives cancel. So we square "
  "each error, average, then take the square root to get back to rand.")
eq(r"\mathrm{RMSE} = \sqrt{\;\frac{1}{N}\sum_{i=1}^{N} e_i^{\,2}\;},"
   r"\qquad e_i = \hat{S}_i - S_i")
p("Squaring means one large miss hurts far more than several small ones. An "
  "error of 2.00 contributes 4.00; four errors of 0.50 contribute 1.00 between "
  "them. <b>RMSE hates occasional disasters.</b> That single fact is why we "
  "beat the AR(1), and you should be able to say it in one breath.")
warn("Volunteer this before a judge finds it",
     f"On <b>MAE</b>, which just averages error sizes without squaring, the "
     f"benchmark is slightly better: {f4(MET['AR1_log']['mae'])} against our "
     f"{f4(MET['COMBO']['mae'])}. Its typical error is fine. It loses on RMSE "
     f"specifically because mean reversion in a trending market produces "
     f"occasional large misses. RMSE is the metric the rules name, so RMSE is "
     f"what we optimise. Saying this yourself is worth more than the half-mark "
     f"it might cost.")

h1("4. Out of sample, and the trap everyone falls into")
p("<b>In sample</b> means measuring a model on data it was fitted to. You can "
  "always fit history well; it proves nothing. <b>Out of sample</b> means the "
  "model is scored only on data it had never seen when it made the prediction. "
  "That is the real test.")
p("The danger is <b>look-ahead bias</b>: accidentally letting a model use "
  "information from the future. It is easy to do and it always makes results "
  "look brilliant.")
box("A concrete example of accidental cheating",
    "Suppose you standardise your predictors using a mean computed over the "
    "whole 1999 to 2026 sample, then run your 2021 forecasts. Your 2021 model "
    "now quietly knows the average level of the rand in 2024. Our code "
    "recomputes every mean, standard deviation and coefficient <b>inside each "
    "forecast's own training window</b> precisely so this cannot happen.")

# ====================================================================== 5
E.append(PageBreak())
h1("5. The models, with the mathematics")
h2("5.1 Notation")
p("S(t) is the rate at time t. A hat means a forecast. We often work in logs, "
  "written with a small s, because differences of logs are percentage changes "
  "and because exponentiating back guarantees a positive forecast.")
eq(r"s_t = \log S_t, \qquad y_t = \log S_{t+28\mathrm{d}} - \log S_t,"
   r"\qquad \hat{S}_{t+28\mathrm{d}} = S_t \cdot e^{\,\hat{y}_t}")

h2("5.2 Random walk: the anchor")
p("The forecast is today's rate. No parameters, nothing to estimate, nothing "
  "to overfit.")
eq(r"\hat{S}_{t+28\mathrm{d}} = S_t")
p("If the market is efficient, today's price already contains everyone's best "
  "collective estimate. Any predictable move would be traded away. So the "
  "no-change forecast is what you get by taking a functioning market "
  "seriously. Its RMSE is " + f4(MET["RW"]["rmse"]) + ", which already beats "
  "the AR(1).")

h2("5.3 AR(1): the benchmark, and exactly why it loses")
p("An AR(1) says the next value is a fraction of the current one, plus a "
  "constant, plus noise. We fit c and phi by ordinary least squares on an "
  "expanding window from 1999, then iterate four steps to reach 28 days.")
eq(r"s_{t+1} = c + \phi\, s_t + \varepsilon_{t+1}")
p("Iterating forever converges to a fixed point, the implied long-run mean:")
eq(r"\mu = c + \phi\mu \quad\Longrightarrow\quad \mu = \frac{c}{1-\phi}")
p("Our phi comes out between 0.9971 and 0.9986 across the 261 origins. Just "
  "below one. So every forecast is dragged toward mu. And here is the finding "
  "the whole project rests on:")
box("The single most important fact in your submission",
    "We computed mu at all 261 origins. It ranged from R11.80 to R19.18 as the "
    "estimation sample grew, and <b>it sat below the prevailing spot rate at "
    "every one of the 261 origins</b>, by R2.11 on average and never by less "
    "than R0.57. Meanwhile the rand rose from R14.62 at the first origin to a "
    "peak of R19.74.<br/><br/>"
    "So the benchmark leaned downward, against a rising currency, for five "
    "years. It is not a broken model. It is a mean-reverting model applied to "
    "a series that was trending.")
p("As one concrete illustration, at the 3 June 2022 origin the fit on 1 222 "
  "weekly observations gave c = 0.006335 and phi = 0.997531, so mu = R13.01 "
  "and a shock half-life of 280 weeks. Spot that day was R15.41. <b>If a judge "
  "asks where R13.01 comes from, say it is that day's estimate, and that "
  "across all 261 origins the implied mean ranged R11.80 to R19.18 and was "
  "below spot at every one.</b>")

h2("5.4 Carry: the forward-rate tilt")
p("South African rates are far above American ones. At our example date JIBAR "
  "3-month paid 4.89% and the US 3-month T-bill 1.17%, a gap of 3.72 points. "
  "Covered interest parity says the forward rate adjusts until both options "
  "pay the same, otherwise banks arbitrage the difference.")
eq(r"\hat{S}_{t+28\mathrm{d}} = S_t\left(1 + \left(i^{\mathrm{ZA}}_t - "
   r"i^{\mathrm{US}}_t\right)\cdot\frac{28}{365}\right)")
p("With real numbers: 15.4117 x (1 + 0.0372 x 28/365) = 15.4557. The rand is "
  "predicted to weaken by about 4.4 cents, exactly the interest advantage "
  "competed away.")
warn("Be ready for the obvious objection",
     "Uncovered interest parity fails empirically. High-interest currencies "
     "have historically weakened <i>less</i> than the differential predicts, "
     "which is why the carry trade has paid for decades. We do not treat this "
     "model as true. We treat it as one informative view, and let its weight "
     "be decided by how it has actually been performing. In 2022 and 2023, "
     "when the gap was wide, it was the single best model we ran.")

h2("5.5 Ridge regression: fundamentals, heavily shrunk")
p("A linear regression predicts the four-week log return as a weighted sum of "
  "predictors. Ordinary least squares picks the weights that minimise squared "
  "error. The problem is that with noisy, correlated predictors and a weak "
  "signal, OLS overfits: it finds combinations that match past wiggles and "
  "gives them large coefficients that do not repeat.")
p("Ridge adds a penalty on the size of the coefficients:")
eq(r"\hat{b}_{\mathrm{ridge}} = \min_{b}\;\left\{\;\sum_t (y_t - x_t b)^2 "
   r"\;+\; \alpha\sum_{j=1}^{k}\beta_j^2\;\right\}", 12.0)
p("The second term is a fine per unit of coefficient size. A predictor is used "
  "only if the improvement in fit is worth the fine. Larger alpha means more "
  "shrinkage. This is the bias-variance trade-off: a little systematic bias in "
  "exchange for far more stability.")
bullets([
    "<b>Predictors:</b> carry differential, four-week returns on gold, "
    "platinum and the broad dollar, and the VIX z-score.",
    "<b>Standardised</b> inside each training window, because the penalty "
    "treats all coefficients equally.",
    "<b>Alpha chosen by time-ordered cross-validation</b> inside the training "
    "window. Ordered, never shuffled, or you would train on 2024 to predict "
    "2019.",
    "<b>No intercept.</b> This matters: under heavy shrinkage the predicted "
    "return goes to zero, so the forecast becomes S(t) and the model collapses "
    "to the random walk rather than drifting toward a stale average the way "
    "the AR(1) does.",
])
box("What the model actually learned, and why it is a good answer",
    "At the final origin, cross-validation chose alpha = 10 000, which is very "
    "heavy shrinkage. The fitted coefficients came out at about <b>8 per cent "
    "of their OLS values</b>. Given full freedom, the model concluded that the "
    "honest signal is very weak and that it should stay close to the no-change "
    "forecast. That is the model independently rediscovering Meese and Rogoff, "
    "and it is a strong thing to be able to say.")

h2("5.6 Gradient boosting: the control that failed on purpose")
p("A decision tree splits data with yes/no questions. Gradient boosting builds "
  "many small trees in sequence, each trained on the previous one's errors, "
  "each scaled down by a learning rate.")
eq(r"F_m(x) = F_{m-1}(x) + \eta\, h_m(x)")
p("We ran it under identical conditions: depth 2, learning rate 0.05, 150 "
  "iterations, L2 regularisation 1.0, fixed seed, same information set, same "
  f"embargo, same walk-forward loop. It lost by <b>{GBM:.1f} per cent</b>.")
warn("Why keeping a losing model is a strength, not an embarrassment",
     "Any judge may ask why you did not use machine learning. The weak answer "
     "is a vague comment about overfitting. Your answer is: we did, under "
     "identical conditions, and here is the exact number it lost by. About 850 "
     "heavily overlapping weekly observations with a tiny signal cannot "
     "support a learner that fits thresholds and interactions. It finds plenty "
     "of both, but they belong to that stretch of history rather than to the "
     "currency. This is the documented M4 and M5 competition conclusion.")

h2("5.7 The combination: our submitted model")
p("Averaging forecasts works for the same reason diversifying a portfolio "
  "works. If two forecasts each have error variance V and correlation rho:")
eq(r"\mathrm{Var}\!\left(\frac{e_1+e_2}{2}\right) = \frac{V(1+\rho)}{2}")
p("If the errors are uncorrelated the average has half the error variance of "
  "either alone. You do not need to know in advance which model is best, and "
  "that is precisely what nobody ever knows.")
p("We weight the random walk, carry and ridge by inverse discounted mean "
  "squared error over <b>resolved</b> past forecasts only:")
eq(r"w_{i,t} = \frac{\left(\mathrm{DMSE}_{i,t}\right)^{-\theta}}"
   r"{\sum_j \left(\mathrm{DMSE}_{j,t}\right)^{-\theta}},"
   r"\qquad \delta = 0.97,\;\; \theta = 2")
p("Lower recent error means higher weight. The decay delta means older errors "
  "count for less, so weight migrates toward whatever suits the current "
  "regime. At our worked example the weights were 0.333 on the random walk, "
  "0.337 on carry and 0.331 on ridge, nearly equal because no component had a "
  "clear edge that week.")

# ====================================================================== 6
E.append(PageBreak())
h1("6. The five guarantees that make it honest")
p("This is the rigour criterion, worth ten marks. Learn these in order; a "
  "sceptical judge will test them in roughly this sequence.")
table([["#", "Guarantee", "How it is enforced"],
       ["1", "Information sets",
        "Every predictor enters through a backward as-of merge. A forecast at "
        "origin t sees only observations dated on or before t."],
       ["2", "No publication lags",
        "Every predictor is a daily market price. Never revised, no release "
        "delay, so look-ahead bias is impossible by construction rather than "
        "merely avoided. We gave up CPI and the current account to buy that."],
       ["3", "Resolved-only training",
        "Ridge and boosting train only on origins whose 28-day outcome had "
        "already happened. One line: tr = tr[tr.index &lt;= i - H]."],
       ["4", "Embargoed weights",
        "Combination weights use only errors from forecasts already resolved "
        "28 days before the current origin."],
       ["5", "Frozen configuration",
        "Feature set, intercept, decay and sharpness were chosen on a 2015 to "
        "2020 validation era whose targets all resolve before 2021, then "
        "frozen. The judged window was never used to make a decision."]],
      [0.8, 3.4, 11.2])
box("Guarantee 5 is the one that separates you from most teams",
    "Almost everyone remembers not to put future data inside a model. Far "
    "fewer notice that <b>the modeller</b> is also a channel for future "
    "information. If you try twenty configurations on 2021 to 2025 and report "
    "the best, that best number is partly luck and will not repeat. By "
    "choosing on 2015 to 2020 and freezing, our judged-window result is the "
    "first time those settings ever met that data. The full search grid is in "
    "validation_metrics.json in the submission.")
p("And the evidence: <b>all 261 forecasts are logged</b> with origin date, "
  "target date, every model's forecast and the realised value. Offer this. "
  "<i>If you want to audit one, we brought the file</i> is a strong "
  "sentence.")

h2("The walk-forward loop, in plain instructions")
code("""for each Friday t from 2021-01-01 to 2025-12-26:
    1. take every observation dated on or before t      (nothing later)
    2. re-estimate the AR(1) on that history            (expanding window)
    3. random walk forecast = S(t)
    4. carry forecast from today's interest gap
    5. ridge trains ONLY on origins already resolved by t
    6. cross-validate alpha inside that training window
    7. combination weights from resolved past errors only
    8. log the forecast, the origin date and the target date

only after the loop finishes, compare the log with what actually happened.""")

# ====================================================================== 7
E.append(PageBreak())
h1("7. The results")
table([["Model", "RMSE", "MAE", "vs AR(1)", "What it is"]] +
      [[n, f4(MET[k]["rmse"]), f4(MET[k]["mae"]),
        "" if k == "AR1_log" else f"{100 * (1 - MET[k]['rmse'] / B):+.2f}%", w]
       for k, n, w in [
           ("AR1_log", "AR(1) benchmark", "the benchmark"),
           ("RW", "Random walk", "beats it"),
           ("CARRY", "Carry", "beats it"),
           ("RIDGE", "Ridge", "beats it"),
           ("GBM", "Gradient boosting", "loses, on purpose"),
           ("COMBO", "<b>Combination</b>", "<b>our submission</b>")]],
      [3.5, 2.0, 2.0, 2.2, 5.7], fs=8.5)
img("fig1_rmse_bars.png", 13.2,
    "The axis starts at 0.50 so the differences are visible. Say that out loud "
    "before a judge spots it.")
img("fig2_cum_se_diff.png", 13.2,
    "Cumulative squared error of the benchmark minus ours. Rising means we are "
    "ahead. It builds through the 2022-23 trend, peaks at 1.29, gives some "
    "back, and ends at 0.69. Show the give-back rather than crop at the peak.")

h2("Year by year, including the year we lose")
table([["Year", "AR(1)", "Ours", "Outcome"]] +
      [[y, f4(v["AR1_log"]), f4(v["COMBO"]),
        "we win" if v["COMBO"] < v["AR1_log"] else "benchmark wins"]
       for y, v in MET["_yearly"].items()],
      [2.4, 3.2, 3.2, 6.6], fs=8.5)
p("We win four years of five. <b>Volunteer the 2025 loss.</b> The rand "
  "strengthened that year and moved back toward the benchmark's long-run mean, "
  "so its built-in bias finally paid. That is regime dependence, and it is the "
  "honest argument for combining models rather than betting on one.")

h2("The robustness cut")
p("Our last origins have target dates in January 2026. So we recomputed using "
  "only origins whose target also falls inside 2025. On that stricter cut the "
  f"combination scores {f4(MET['_targets_within_window']['COMBO'])} and "
  "<b>leads every model we ran, random walk included</b>. The result is not an "
  "artefact of where the boundary was drawn.")

# ====================================================================== 8
E.append(PageBreak())
h1("8. One forecast worked out by hand")
p("This is the fastest way to show a judge you understand your own machine. "
  "Origin Friday 3 June 2022, spot R15.4117. Target 1 July 2022, actual "
  "R16.3482.")
table([["Model", "Forecast", "How it got there", "Error"],
       ["Random walk", "15.4117", "today's rate, unchanged", "-0.9365"],
       ["Carry", "15.4557", "15.4117 x (1 + 0.0372 x 28/365)", "-0.8925"],
       ["AR(1)", "15.3861",
        "iterated 4 steps toward its implied mean, R13.01 that day", "-0.9621"],
       ["Ridge", "15.4089", "a small tilt away from spot", "-0.9393"],
       ["<b>Combination</b>", "<b>15.4256</b>",
        "0.333 x RW + 0.337 x Carry + 0.331 x Ridge", "<b>-0.9226</b>"]],
      [2.6, 1.9, 6.6, 1.9], fs=8.5)
p("Every model was too low that month. But look at the ordering: <b>the AR(1) "
  "was the worst of the sensible models</b>, because its pull toward R13.01 "
  "dragged the forecast down at exactly the moment the rand was heading up. "
  "That single month is the whole project in miniature.")
box("What this teaches about honest forecasting",
    "The forecasts run from 15.386 to 15.467, a spread of eight cents, while "
    "the actual move was 94 cents. At one month no sensible model strays far "
    "from today's price, because there is very little defensible reason to. "
    "The competition between models is fought inside those few cents. That is "
    "why 0.42% is a real result and why a claimed 20% is a warning sign.")

h1("9. Is the result statistically significant? No.")
p("The Diebold-Mariano test asks whether a difference in accuracy is real or "
  "noise. For each origin compute the difference in squared errors, then test "
  "whether its mean differs from zero.")
eq(r"d_t = e_{1,t}^{\,2} - e_{2,t}^{\,2}, \qquad "
   r"\mathrm{DM} = \frac{\bar{d}}{\sqrt{\widehat{\mathrm{Var}}(\bar{d})}}")
p("One correction matters. Our forecasts overlap: the 3 June forecast covers "
  "3 June to 1 July, the 10 June forecast covers 10 June to 8 July, so they "
  "share three weeks of the same market movement and their errors are "
  "correlated. Ordinary standard errors assume independence and would make the "
  "result look more significant than it is. We use <b>Newey-West</b> standard "
  "errors at lag 3, the standard choice for a 4-step forecast.")
warn("Say this plainly, do not hedge",
     f"Our p-value is <b>{MET['COMBO']['dm_vs_ar1'][1]:.2f}</b>. Not "
     "significant. To detect a 0.4% difference with data this noisy you would "
     "need an order of magnitude more independent forecasts, and every honest "
     "team here is in the same position.<br/><br/>"
     "What we claim instead is <b>consistency</b>: the combination beats the "
     "benchmark in four years of five, on the full window, on the strict "
     "robustness cut, and in the 2015-2020 validation era it never saw. "
     "Consistency across independent cuts is real evidence. It is not "
     "significance, and we do not present it as such. A judge who knows "
     "econometrics will respect the distinction and will be suspicious of any "
     "team claiming significance here.")

# ====================================================================== 10
E.append(PageBreak())
h1("10. The questions you will be asked")
qa = [
    ("Why is your improvement so small?",
     "Because that is the size of the true signal at one month. The best "
     "published gains are 1 to 5 per cent. Anything much larger in this "
     "setting usually indicates look-ahead bias rather than skill. We would "
     "rather show 0.42% that survives an audit than 15% that does not."),
    ("Your combination is basically the random walk. Why not just submit that?",
     "On the full window they are nearly tied, but on the robustness cut the "
     "combination is ahead of it. The deeper answer is that the combination is "
     "the random walk plus insurance. When carry held information in 2022 and "
     "23 the weights moved toward it; when nothing worked in 2024 and 25 they "
     "collapsed back to the anchor. A fixed no-change rule cannot do that, and "
     "we did not have to know in advance which regime was coming."),
    ("How do we know you did not tune on 2021 to 2025?",
     "Three artefacts in the submission: the 2015-2020 validation grid that "
     "selected the configuration, the frozen config itself, and the forecast "
     "log. Happy to open validation_metrics.json now."),
    ("Why did the gradient booster fail?",
     "Sample size against capacity. It fits thresholds and interactions, and "
     "with about 850 noisy overlapping weekly observations those patterns are "
     "regime noise that does not repeat. Depth two, learning rate 0.05, L2 "
     "regularisation. We did not sabotage it; the horizon does not contain "
     "what it needs."),
    ("Why no LSTM or deep learning?",
     "Same answer with worse odds. An LSTM has orders of magnitude more "
     "parameters than a depth-two booster, and the booster already lost by "
     "seven and a half per cent. The evidence for deep nets beating no-change "
     "at monthly FX horizons under honest evaluation is essentially nil."),
    ("Your AR(1), levels or logs? Estimated how?",
     "Both. OLS with intercept, expanding window from 1999, iterated four "
     "steps at weekly frequency. Log version 0.5624, level version 0.5629. We "
     "compare against the log version because it is the stronger of the two. "
     "We did not pick the weaker one to beat."),
    ("Why 28 days as one month?",
     "Forecasts are made every Friday, so the natural target is the Friday "
     "four weeks out. It holds origin and target on the same weekday and "
     "avoids month-end irregularity. A calendar-month variant changes no "
     "ranking."),
    ("What about publication lags and revisions?",
     "We designed the problem away. No macro releases at all. Every predictor "
     "is a daily market price, never revised, no release delay, so the as-of "
     "merge alone gives a true real-time information set. That is also why we "
     "left out CPI and GDP despite their theoretical appeal."),
    ("Why these predictors and not others?",
     "Literature first, not search first. Carry from interest parity. Gold and "
     "platinum because the rand is a commodity currency. The dollar index and "
     "VIX because Codera's own research names dollar strength and risk "
     "sentiment among the main rand drivers. We deliberately did not trawl "
     "hundreds of candidates, because that is how you find spurious "
     "predictors."),
    ("Where exactly does the R2.11 come from?",
     "At each of the 261 origins we refit the AR(1) and compute c over one "
     "minus phi, the mean it reverts to, then compare it to that day's spot "
     "rate. It was below spot at all 261, average gap R2.11. The script that "
     "reproduces it is verify_charts.py in the submission."),
    ("What was your AI usage?",
     "AI was used as a coding assistant and for literature search, which the "
     "rules permit. Every modelling decision is ours, and the models are "
     "deliberately simple enough that we can derive them by hand: OLS, ridge, "
     "and a weighted average. Ask us about any line."),
    ("If the rand is a random walk, is forecasting pointless?",
     "Point forecasts are nearly pointless, and that is useful information: it "
     "tells a treasurer to hedge rather than trade on a view. The value beyond "
     "the point forecast is in the conditional distribution, which is where we "
     "would take this next with density forecasts."),
    ("Would this make money as a trading strategy?",
     "We did not test it and we will not claim it. RMSE and profit are "
     "different objectives. A model can win on RMSE and lose money after "
     "costs. That needs transaction costs, position sizing and a Sharpe-based "
     "evaluation, which is a different project."),
]
for q, a in qa:
    p(f"<b>Q. {q}</b>", ParagraphStyle("q", parent=P, spaceAfter=2,
                                       textColor=NAVY))
    p(a, ParagraphStyle("a", parent=P, leftIndent=10, spaceAfter=9))

box("If you are asked something you did not test",
    "Say: <i>We did not test that, and I would rather not guess. Our "
    "design would answer it by...</i> and then describe the approach in "
    "one sentence. That scores higher than bluffing every single time. Judges "
    "are testing whether you know the edge of your own work.")

# ====================================================================== 11
E.append(PageBreak())
h1("11. Technical terms you should be able to define")
gl = [
    ("Out of sample", "Scored only on data the model had not seen when it "
     "made the prediction."),
    ("Look-ahead bias", "Accidentally using information not available at the "
     "time of the forecast."),
    ("As-of merge", "Attaching to each date the most recent <i>earlier</i> "
     "observation of another series. Backward direction only."),
    ("Expanding window", "Re-estimating at each step using all history up to "
     "that point, so the training set grows."),
    ("Overfitting", "Learning noise in the training data rather than the "
     "underlying pattern. Good fit, bad forecasts."),
    ("Shrinkage", "Deliberately pulling coefficients toward zero to improve "
     "out-of-sample performance."),
    ("Ridge regression", "OLS plus a penalty on the sum of squared "
     "coefficients. Penalty strength is alpha."),
    ("Cross-validation", "Training on part of the data and testing on the "
     "rest to choose a setting. Ours is time-ordered, never shuffled."),
    ("Bias-variance trade-off", "Accepting small systematic error for much "
     "greater stability. Why ridge works here."),
    ("Covered interest parity", "The no-arbitrage relation tying the forward "
     "rate to the interest differential."),
    ("Diebold-Mariano test", "A test of whether two models differ in accuracy "
     "by more than chance."),
    ("Newey-West", "A standard-error correction for correlation between "
     "nearby observations. Needed because our forecasts overlap."),
    ("Persistence (phi)", "How much of today carries into tomorrow in an "
     "AR(1). Ours is just below one."),
    ("RMSE vs MAE", "RMSE squares errors so it punishes large misses; MAE "
     "averages sizes and treats them evenly."),
]
table([["Term", "What you say if asked"]] + [[a, b] for a, b in gl],
      [3.6, 11.6], fs=8.3)

h1("12. The night before")
bullets([
    f"<b>Memorise:</b> {f4(C)}, {f4(B)}, {GAIN:+.2f}%, "
    f"{MET['COMBO']['n']} forecasts, R2.11 below spot at 261 of 261, "
    f"DM p = {MET['COMBO']['dm_vs_ar1'][1]:.2f}, booster lost {GBM:.1f}%.",
    "<b>Read Script.md aloud twice, with a timer.</b> Target 4:00 to 4:30. "
    "The slot is 2 to 5 minutes.",
    "<b>Know your backup slides by number.</b> Appendix A is the full results "
    "table, B is by year, C is data provenance, D is the weights, E is why ML "
    "lost, F is forecasts vs actuals, G is the worked example.",
    "<b>Open on your laptop:</b> the deck, Project_Report.pdf, and "
    "forecast_log.csv. Being able to show the log in five seconds is worth "
    "real marks on rigour.",
    "<b>Lead with the team name.</b> A spurious relationship looks real in "
    "your data and is not there in the world. In FX forecasting that is the "
    "default outcome, so the whole project was built to avoid one. That one "
    "sentence states your methodology before you show a single number.",
    "<b>Volunteer the three weaknesses</b> before they are found: not "
    "statistically significant, the benchmark wins on MAE and in 2025, and we "
    "never tested it as a trading strategy.",
])
box("The mindset",
    "Deliver the limitations with confidence, not apology. Professional "
    "forecasters state limits; amateurs hide them, and judges can tell the "
    "difference instantly. Your strongest position all evening is that you "
    "know exactly how big your result is, exactly why it happens, and exactly "
    "what it does not prove.")


def footer(c, d):
    c.saveState()
    c.setFont("Helvetica", 7.5)
    c.setFillColor(GREY)
    c.drawString(2.2 * cm, 1.1 * cm, "Defence guide, team Spurious Decision")
    c.drawRightString(18.8 * cm, 1.1 * cm, f"page {d.page}")
    c.restoreState()


def main():
    doc = SimpleDocTemplate(
        str(REP / "Defence_Guide.pdf"), pagesize=A4,
        leftMargin=2.3 * cm, rightMargin=2.2 * cm,
        topMargin=1.8 * cm, bottomMargin=1.7 * cm,
        title="Defence guide", author="Spurious Decision")
    doc.build(E, onFirstPage=footer, onLaterPages=footer)
    print("defence guide written:", REP / "Defence_Guide.pdf")


if __name__ == "__main__":
    main()
