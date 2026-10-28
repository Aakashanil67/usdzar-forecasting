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
TESTS = json.load(open(PROC / "statistical_tests.json"))
LOG = pd.read_csv(PROC / "forecast_log.csv", parse_dates=["origin"])

NAVY = "#0E2A3B"      # primary dark
FOCAL = "#1A7A4A"     # the combination, the focal series
MUTED = "#777777"     # the benchmark and axis furniture
GREY = "#AEB6BD"
HIGHLIGHT = "#FFF2CC"
EDGE = "#E6C800"

plt.rcParams.update({
    "font.family": "DejaVu Sans",   # ships with matplotlib; Arial is not on every machine
    "font.size": 17,
    "axes.edgecolor": "#BBBBBB",
    "axes.labelcolor": "#2D2D2D",
    "xtick.color": "#444444",
    "ytick.color": "#777777",
    "axes.grid": True,
    "grid.color": "#E2E8F0",
    "grid.linewidth": 0.8,
})


def rmse_dots():
    """Exhibit for the accuracy slide: each model's RMSE difference from the
    random walk and from the AR(1), with 95% CIs. The two prespecified
    comparisons are filled in the focal colour; the rest are exploratory."""
    rows = ["COMBO", "EQUAL3", "RW_CARRY", "RW_RIDGE", "CARRY", "RIDGE", "GBM",
            "RW", "AR1_log"]
    names = {"COMBO": "Combination", "EQUAL3": "Equal weights", "RW_CARRY":
             "RW + carry", "RW_RIDGE": "RW + ridge", "CARRY": "Carry",
             "RIDGE": "Ridge", "GBM": "Gradient boosting", "RW": "Random walk",
             "AR1_log": "AR(1)"}
    by = {(c["model"], c["benchmark"]): c for c in TESTS["comparisons"]}
    fig, axes = plt.subplots(1, 2, figsize=(8.0, 5.0), sharey=True, sharex=True)
    y = np.arange(len(rows))[::-1]
    for ax, bench, title in zip(axes, ["RW", "AR1_log"],
                                ["vs random walk", "vs AR(1)"]):
        for yy, m in zip(y, rows):
            c = by.get((m, bench))
            if c is None:
                ax.annotate("benchmark", (0, yy), ha="center", va="center",
                            fontsize=13, color=MUTED, style="italic",
                            bbox=dict(fc="white", ec="none", pad=1))
                continue
            pre = c["role"] == "prespecified"
            col = FOCAL if pre else GREY
            ax.plot(c["rmse_difference_ci95"], [yy, yy], color=col,
                    lw=3 if pre else 2.2, solid_capstyle="round", zorder=2)
            ax.plot(c["rmse_difference"], yy, "o", ms=10 if pre else 8,
                    mfc=col if pre else "white", mec=col, mew=2, zorder=3)
        ax.axvline(0, color="#555555", lw=1.1, zorder=1)
        ax.set_title(title, fontsize=16, color=NAVY)
        ax.tick_params(axis="x", labelsize=14)
        ax.grid(axis="y", alpha=0)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_axisbelow(True)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels([names[m] for m in rows], fontsize=15, color="#2D2D2D")
    fig.supxlabel("RMSE difference, rand per US dollar (left = more accurate)",
                  fontsize=14)
    fig.tight_layout()
    fig.savefig(OUT / "rmse.png", dpi=220, facecolor="white")
    plt.close(fig)


def cumulative():
    """Exhibit for the cumulative-error slide, with the peak and the end marked."""
    cum = ((LOG["AR1_log"] - LOG["realized"]) ** 2
           - (LOG["COMBO"] - LOG["realized"]) ** 2).cumsum()
    t = LOG["origin"]

    fig, ax = plt.subplots(figsize=(7.6, 4.3))
    ax.axhspan(0, cum.max() * 1.18, color="#F4F9FD", zorder=0)
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
    ax.set_ylabel("cumulative squared-error\ndifference", fontsize=15)
    ax.annotate("above zero = the combination is ahead of the AR(1)",
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
    """Appendix exhibit: RMSE by year, the combination against the AR(1)."""
    yrs = sorted(MET["_yearly"])
    a = [MET["_yearly"][y]["AR1_log"] for y in yrs]
    c = [MET["_yearly"][y]["COMBO"] for y in yrs]
    x = np.arange(len(yrs))
    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    ax.bar(x - 0.22, a, 0.4, color=MUTED, label="AR(1) benchmark")
    ax.bar(x + 0.22, c, 0.4, color=FOCAL, label="Combination")
    for xx, v in zip(x - 0.22, a):
        ax.annotate(f"{v:.3f}", (xx, v), ha="center", va="bottom", fontsize=10.5,
                    color="#444444", xytext=(0, 3), textcoords="offset points")
    for xx, v in zip(x + 0.22, c):
        ax.annotate(f"{v:.3f}", (xx, v), ha="center", va="bottom", fontsize=10.5,
                    fontweight="bold", color=FOCAL, xytext=(0, 3),
                    textcoords="offset points")
    for i in [i for i, (x, y) in enumerate(zip(a, c)) if y >= x]:
        ax.annotate(f"{yrs[i]}: the benchmark is lower", xy=(i - 0.22, a[i] + 0.06),
                    xytext=(i - 0.9, 0.76), fontsize=13, color="#7A5200",
                    ha="center",
                    bbox=dict(boxstyle="round,pad=0.35", fc=HIGHLIGHT, ec=EDGE,
                              lw=1.1),
                    arrowprops=dict(arrowstyle="->", color=EDGE, lw=1.5))
    ax.set_xticks(x)
    ax.set_xticklabels(yrs, fontsize=15)
    ax.set_ylabel("RMSE", fontsize=15)
    ax.set_ylim(0, 0.95)
    ax.legend(fontsize=13.5, frameon=False, ncol=2, loc="upper left")
    ax.tick_params(axis="y", labelsize=13)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(OUT / "yearly.png", dpi=220, facecolor="white")
    plt.close(fig)


def main():
    rmse_dots()
    cumulative()
    yearly()
    print("slide figures written:", sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()
