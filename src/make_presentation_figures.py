"""
make_presentation_figures.py - Presentation-resolution versions of the two exhibits
used on the results slides.

The report figures are built for print, with small fonts and no call-outs. A slide
needs axis labels of at least 16pt and the finding annotated on the chart itself,
so it reads without narration. Written to figures/presentation/.

Run:  python src/make_presentation_figures.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
PROC = BASE / "data" / "processed"
OUT = BASE / "figures" / "presentation"
OUT.mkdir(parents=True, exist_ok=True)

MET = json.load(open(PROC / "metrics.json"))
LOG = pd.read_csv(PROC / "forecast_log.csv", parse_dates=["origin"])

NAVY = "#0E2A3B"      # primary dark
FOCAL = "#1A7A4A"     # our model, the focal series
ACCENT = "#2E75B6"    # comparators
MUTED = "#777777"     # the benchmark and axis furniture
GREY = "#AEB6BD"
HIGHLIGHT = "#FFF2CC"
EDGE = "#E6C800"

plt.rcParams.update({
    "font.family": "DejaVu Sans",   # metric-compatible stand-in for Arial
    "font.size": 17,
    "axes.edgecolor": "#BBBBBB",
    "axes.labelcolor": "#2D2D2D",
    "xtick.color": "#444444",
    "ytick.color": "#777777",
    "axes.grid": True,
    "grid.color": "#E2E8F0",
    "grid.linewidth": 0.8,
})


def rmse_bars():
    """Exhibit for the accuracy slide. Focal bar in navy, benchmark in grey."""
    order = ["AR1_log", "RW", "CARRY", "RIDGE", "GBM", "COMBO"]
    names = ["AR(1)\nbenchmark", "Random\nwalk", "Carry", "Ridge",
             "Gradient\nboosting", "Combination\n(ours)"]
    vals = [MET[k]["rmse"] for k in order]
    cols = [MUTED, GREY, ACCENT, ACCENT, GREY, FOCAL]

    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    bars = ax.bar(names, vals, color=cols, width=0.66)
    for b, v in zip(bars, vals):
        ax.annotate(f"{v:.4f}", (b.get_x() + b.get_width() / 2, v),
                    ha="center", va="bottom", fontsize=16, fontweight="bold",
                    color="#2D2D2D", xytext=(0, 4), textcoords="offset points")

    base = MET["AR1_log"]["rmse"]
    combo = MET["COMBO"]["rmse"]

    # benchmark reference line. Unlabelled: the AR(1) bar sits on it, and the
    # takeaway text names it, so a label here would only collide with the bars.
    ax.axhline(base, color=MUTED, lw=1.3, ls="--", zorder=1)

    # key finding written inside the focal bar, where nothing can overlap it
    ax.annotate(f"{100 * (1 - combo / base):.2f}%", (5, 0.5375),
                ha="center", va="center", fontsize=15, fontweight="bold",
                color="white", zorder=5)
    ax.annotate("better", (5, 0.5225), ha="center", va="center",
                fontsize=13.5, fontweight="bold", color="white", zorder=5)

    ax.set_ylabel("RMSE, rand per US dollar", fontsize=16)
    ax.set_ylim(0.50, 0.625)
    ax.set_yticks([0.50, 0.53, 0.56, 0.59, 0.62])
    ax.tick_params(axis="x", labelsize=13)
    ax.tick_params(axis="y", labelsize=14)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.annotate("Axis truncated at 0.50 to make the differences visible.",
                (0, -0.185), xycoords="axes fraction", fontsize=12.5,
                color=MUTED, style="italic")
    fig.tight_layout()
    fig.savefig(OUT / "rmse.png", dpi=220, facecolor="white")
    plt.close(fig)


def cumulative():
    """Exhibit for the mechanism slide, with the build and give-back marked."""
    cum = ((LOG["AR1_log"] - LOG["realized"]) ** 2
           - (LOG["COMBO"] - LOG["realized"]) ** 2).cumsum()
    t = LOG["origin"]

    fig, ax = plt.subplots(figsize=(7.6, 4.3))
    ax.axhspan(0, cum.max() * 1.18, color="#F4F9FD", zorder=0)
    ax.axvspan(pd.Timestamp("2022-01-01"), pd.Timestamp("2024-01-01"),
               color="#FFF2CC", alpha=0.75, zorder=0)
    ax.plot(t, cum, color=FOCAL, lw=2.6, zorder=3)
    ax.axhline(0, color="#555555", lw=1.1, zorder=2)

    peak_i = int(np.argmax(cum.values))
    ax.plot(t.iloc[peak_i], cum.iloc[peak_i], "o", color=EDGE, ms=9,
            mec="#7A5200", mew=1.4, zorder=4)
    ax.annotate(f"peak {cum.max():.2f}",
                xy=(t.iloc[peak_i], cum.iloc[peak_i]),
                xytext=(12, -6), textcoords="offset points",
                fontsize=14.5, color="#7A5200", fontweight="bold")
    ax.annotate(f"ends {cum.iloc[-1]:.2f}",
                xy=(t.iloc[-1], cum.iloc[-1]), xytext=(-16, -34),
                textcoords="offset points", fontsize=14.5, color=FOCAL,
                fontweight="bold", ha="right")
    ax.annotate("rand trending:\nedge builds here",
                xy=(pd.Timestamp("2023-01-01"), -0.44), fontsize=13.5,
                color="#7A5200", ha="center", va="bottom")

    ax.set_ylabel("cumulative squared-error\ndifference", fontsize=15)
    ax.annotate("above zero = our model is ahead of the benchmark",
                (0.015, 0.93), xycoords="axes fraction", fontsize=13.5,
                color=MUTED, style="italic")
    ax.tick_params(labelsize=14)
    ax.set_ylim(-0.78, cum.max() * 1.18)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(OUT / "cumse.png", dpi=220, facecolor="white")
    plt.close(fig)


def yearly():
    """Appendix exhibit: RMSE by year, ours against the benchmark."""
    yrs = sorted(MET["_yearly"])
    a = [MET["_yearly"][y]["AR1_log"] for y in yrs]
    c = [MET["_yearly"][y]["COMBO"] for y in yrs]
    x = np.arange(len(yrs))
    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    ax.bar(x - 0.22, a, 0.4, color=MUTED, label="AR(1) benchmark")
    ax.bar(x + 0.22, c, 0.4, color=FOCAL, label="Combination (ours)")
    for xx, v in zip(x - 0.22, a):
        ax.annotate(f"{v:.3f}", (xx, v), ha="center", va="bottom", fontsize=10.5,
                    color="#444444", xytext=(0, 3), textcoords="offset points")
    for xx, v in zip(x + 0.22, c):
        ax.annotate(f"{v:.3f}", (xx, v), ha="center", va="bottom", fontsize=10.5,
                    fontweight="bold", color=FOCAL, xytext=(0, 3),
                    textcoords="offset points")
    ax.annotate("2025: rand strengthened back\ntoward the benchmark's mean,\nso its bias finally paid",
                xy=(4.22, c[4]), xytext=(3.05, 0.28), fontsize=13,
                color="#7A5200", ha="center",
                bbox=dict(boxstyle="round,pad=0.35", fc=HIGHLIGHT, ec=EDGE,
                          lw=1.1),
                arrowprops=dict(arrowstyle="->", color=EDGE, lw=1.5))
    ax.set_xticks(x)
    ax.set_xticklabels(yrs, fontsize=15)
    ax.set_ylabel("RMSE", fontsize=15)
    ax.set_ylim(0, 0.82)
    ax.legend(fontsize=13.5, frameon=False, ncol=2, loc="upper left")
    ax.tick_params(axis="y", labelsize=13)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(OUT / "yearly.png", dpi=220, facecolor="white")
    plt.close(fig)


def main():
    rmse_bars()
    cumulative()
    yearly()
    print("slide figures written:", sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()
