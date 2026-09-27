#!/usr/bin/env python3
"""
Render a clean line chart (PNG) from analyze_trend.py output: one line per
series, using the 7-day-smoothed values so weekday noise doesn't dominate the
picture. Spike days are marked with a small dot so the reader can tell "sudden
news spike" apart from "sustained growth" at a glance.

Usage:
    python make_chart.py --analysis analysis.json --output chart.png --title "Intermittent fasting: PL vs CS"

Output (stdout): compact JSON summary with the output path.
"""
import argparse
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

from common import print_summary, ensure_parent

COLORS = ["#3B6FA0", "#C0562B", "#4C9A6A", "#8B5FA8", "#B8862B", "#5A5A5A"]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--analysis", required=True, help="Output of analyze_trend.py")
    ap.add_argument("--output", required=True, help="PNG path")
    ap.add_argument("--title", default="Wikipedia pageviews over time")
    ap.add_argument("--ylabel", default="Views/day (7-day average)")
    ap.add_argument("--log-scale", action="store_true", help="Use a log y-axis -- useful when series differ a lot in size")
    args = ap.parse_args()

    with open(args.analysis, "r", encoding="utf-8") as f:
        analysis = json.load(f)

    fig, ax = plt.subplots(figsize=(9, 4.2), dpi=150)

    for i, s in enumerate(analysis["series"]):
        if "smoothed_series_7d" not in s:
            continue
        dates = [datetime.strptime(p["date"], "%Y%m%d") for p in s["smoothed_series_7d"]]
        values = [p["views_7d_avg"] for p in s["smoothed_series_7d"]]
        color = COLORS[i % len(COLORS)]
        ax.plot(dates, values, label=s["name"], color=color, linewidth=1.8)

        spike_dates = set(s.get("spike_days", []))
        if spike_dates:
            sx = [datetime.strptime(p["date"], "%Y%m%d") for p in s["smoothed_series_7d"] if p["date"] in spike_dates]
            sy = [p["views_7d_avg"] for p in s["smoothed_series_7d"] if p["date"] in spike_dates]
            ax.scatter(sx, sy, color=color, s=18, zorder=5, marker="o", edgecolors="white", linewidths=0.5)

    if args.log_scale:
        ax.set_yscale("log")

    ax.set_title(args.title, fontsize=13, fontweight="bold", loc="left")
    ax.set_ylabel(args.ylabel, fontsize=10)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    if len(analysis["series"]) > 1:
        ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()

    out_path = ensure_parent(args.output)
    fig.savefig(out_path)
    plt.close(fig)

    print_summary({"status": "ok", "output_file": str(out_path)})


if __name__ == "__main__":
    main()
