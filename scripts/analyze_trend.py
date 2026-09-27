#!/usr/bin/env python3
"""
Turn raw pageviews series (from fetch_pageviews.py) into a trend analysis:
growth rate, fit quality, spike/outlier flags, and a plain-language confidence
rating -- plus a side-by-side comparison when multiple series are given.

This is the step that does the actual "how much can we trust this growth
number" thinking, so downstream chart/report generation and the agent's
final answer to the user can stay grounded in numbers instead of vibes.
See references/methodology.md for the reasoning behind each heuristic --
read it once before explaining results to a user, especially confidence
ratings and normalization.

Usage:
    # one series
    python analyze_trend.py --series pl=data/pl_fasting.json --output analysis.json

    # multiple series compared side by side (e.g. two languages)
    python analyze_trend.py --series pl=data/pl_fasting.json --series cs=data/cs_fasting.json \\
        --output analysis.json

    # normalize each series by its project's total traffic ("share of attention"),
    # recommended whenever comparing across languages/editions of very different size
    python analyze_trend.py --series pl=data/pl_fasting.json --series cs=data/cs_fasting.json \\
        --normalize pl=data/pl_total.json --normalize cs=data/cs_total.json \\
        --output analysis.json

Output (stdout): compact JSON summary. Full analysis written to --output.
"""
import argparse
import json
import statistics
from datetime import datetime

from common import print_summary, ensure_parent, eprint

try:
    import numpy as np
except ImportError:
    np = None


def load_series(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def to_day_index(dates: list[str]) -> list[int]:
    base = datetime.strptime(dates[0], "%Y%m%d")
    return [(datetime.strptime(d, "%Y%m%d") - base).days for d in dates]


def rolling_average(values: list[float], window: int) -> list[float]:
    out = []
    for i in range(len(values)):
        lo = max(0, i - window + 1)
        chunk = values[lo:i + 1]
        out.append(sum(chunk) / len(chunk))
    return out


def robust_outliers(values: list[float]) -> list[int]:
    """Indices flagged as spikes using a robust (median/MAD) z-score.

    A spike usually means a news event drove one-off traffic, not sustained
    growing interest -- worth flagging separately rather than folding into
    a trend line. Threshold of 5 is deliberately conservative (see methodology.md).
    """
    if len(values) < 10:
        return []
    med = statistics.median(values)
    abs_dev = [abs(v - med) for v in values]
    mad = statistics.median(abs_dev) or 1.0
    flagged = []
    for i, v in enumerate(values):
        z = 0.6745 * (v - med) / mad
        if z > 5:
            flagged.append(i)
    return flagged


def log_linear_trend(day_idx: list[int], views: list[float]) -> dict:
    """Fit log(views+1) ~ a + b*day using least squares (no scipy dependency).

    Returns slope, r_squared, and an estimated annualized growth rate.
    """
    n = len(day_idx)
    if n < 2:
        return {"slope_per_day": 0.0, "r_squared": 0.0, "annual_growth_rate": None}
    y = [np.log1p(v) for v in views] if np is not None else [_log1p(v) for v in views]
    x = day_idx
    x_mean = sum(x) / n
    y_mean = sum(y) / n
    ss_xy = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
    ss_xx = sum((x[i] - x_mean) ** 2 for i in range(n))
    if ss_xx == 0:
        return {"slope_per_day": 0.0, "r_squared": 0.0, "annual_growth_rate": None}
    slope = ss_xy / ss_xx
    intercept = y_mean - slope * x_mean
    y_pred = [intercept + slope * xi for xi in x]
    ss_res = sum((y[i] - y_pred[i]) ** 2 for i in range(n))
    ss_tot = sum((yi - y_mean) ** 2 for yi in y) or 1e-9
    r_squared = 1 - ss_res / ss_tot
    annual_growth_rate = (_exp(slope * 365.0) - 1)
    return {"slope_per_day": slope, "r_squared": round(r_squared, 3), "annual_growth_rate": round(annual_growth_rate, 4)}


def _log1p(v):
    import math
    return math.log1p(v)


def _exp(v):
    import math
    return math.exp(v)


def confidence_rating(total_views: int, span_days: int, r_squared: float, outlier_fraction: float, cv: float) -> dict:
    """Plain-language confidence in the growth-rate estimate, from cheap
    heuristics rather than a formal test -- good enough to warn a user when
    a "trend" is actually noise, not good enough to be quoted as a p-value.
    """
    reasons = []
    score = 0

    if total_views >= 50_000:
        score += 2
    elif total_views >= 5_000:
        score += 1
    else:
        reasons.append("very low total view count -- percentages will be noisy")

    if span_days >= 365:
        score += 2
    elif span_days >= 180:
        score += 1
        reasons.append("less than a year of data -- can't fully rule out seasonality")
    else:
        reasons.append("less than 6 months of data -- too short for a reliable trend")

    if r_squared >= 0.5:
        score += 2
    elif r_squared >= 0.2:
        score += 1
        reasons.append("moderate scatter around the trend line")
    else:
        reasons.append("the data doesn't follow a clean trend line (low R\u00b2) -- day-to-day noise dominates")

    if outlier_fraction <= 0.01:
        score += 1
    else:
        reasons.append(f"{outlier_fraction:.1%} of days look like one-off traffic spikes (news events), not sustained interest")

    if cv <= 1.0:
        score += 1
    else:
        reasons.append("day-to-day views are highly volatile relative to their average")

    if score >= 7:
        label = "High"
    elif score >= 4:
        label = "Medium"
    else:
        label = "Low"

    return {"label": label, "score": score, "max_score": 8, "reasons": reasons}


def analyze_one(name: str, data: dict, normalize_data: dict | None) -> dict:
    series = data["series"]
    if len(series) < 2:
        return {"name": name, "error": "not enough data points to analyze"}

    dates = [r["date"] for r in series]
    views = [r["views"] for r in series]
    day_idx = to_day_index(dates)

    total_views = sum(views)
    mean_views = total_views / len(views)
    stdev = statistics.pstdev(views) if len(views) > 1 else 0.0
    cv = (stdev / mean_views) if mean_views else 0.0

    smoothed = rolling_average(views, window=7)
    trend = log_linear_trend(day_idx, smoothed)

    outlier_idx = robust_outliers(views)
    outlier_fraction = len(outlier_idx) / len(views)

    span_days = day_idx[-1] - day_idx[0]

    # simple year-over-year: compare last 365 days to the 365 days before that, if available
    yoy = None
    if span_days >= 365:
        cutoff = day_idx[-1] - 365
        prior_cutoff = cutoff - 365
        last_year = [views[i] for i in range(len(views)) if day_idx[i] > cutoff]
        prior_year = [views[i] for i in range(len(views)) if prior_cutoff < day_idx[i] <= cutoff]
        if prior_year and sum(prior_year) > 0:
            yoy = round((sum(last_year) - sum(prior_year)) / sum(prior_year), 4)

    conf = confidence_rating(total_views, span_days, trend["r_squared"], outlier_fraction, cv)

    result = {
        "name": name,
        "project": data.get("project"),
        "article": data.get("article"),
        "date_range": [dates[0], dates[-1]],
        "total_views": total_views,
        "mean_daily_views": round(mean_views, 1),
        "coefficient_of_variation": round(cv, 2),
        "trend": trend,
        "year_over_year_change": yoy,
        "spike_days": [dates[i] for i in outlier_idx][:15],
        "spike_day_count": len(outlier_idx),
        "confidence": conf,
        "smoothed_series_7d": [{"date": dates[i], "views_7d_avg": round(smoothed[i], 1)} for i in range(len(dates))],
    }

    if normalize_data:
        norm_series = {r["date"]: r["views"] for r in normalize_data["series"]}
        share = []
        for r in series:
            total = norm_series.get(r["date"])
            if total:
                share.append({"date": r["date"], "share": r["views"] / total})
        if share:
            mean_share = sum(s["share"] for s in share) / len(share)
            result["share_of_project_traffic"] = {
                "mean_share": mean_share,
                "note": "views for this article divided by the whole project's daily views -- "
                        "makes editions of very different sizes comparable (see methodology.md)",
            }

    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--series", action="append", required=True, metavar="NAME=FILE",
                     help="A label and the fetch_pageviews.py output file, repeatable")
    ap.add_argument("--normalize", action="append", default=[], metavar="NAME=FILE",
                     help="Matching whole-project totals file for the same NAME, for share-of-attention normalization")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    series_map = dict(s.split("=", 1) for s in args.series)
    normalize_map = dict(s.split("=", 1) for s in args.normalize)

    results = []
    for name, path in series_map.items():
        data = load_series(path)
        norm_data = load_series(normalize_map[name]) if name in normalize_map else None
        results.append(analyze_one(name, data, norm_data))

    comparison = None
    if len(results) > 1:
        ranked = sorted(
            [r for r in results if "trend" in r and r["trend"]["annual_growth_rate"] is not None],
            key=lambda r: r["trend"]["annual_growth_rate"],
            reverse=True,
        )
        comparison = {
            "ranked_by_growth_rate": [
                {"name": r["name"], "annual_growth_rate": r["trend"]["annual_growth_rate"], "confidence": r["confidence"]["label"]}
                for r in ranked
            ]
        }

    out = {"series": results, "comparison": comparison}
    out_path = ensure_parent(args.output)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print_summary({
        "status": "ok",
        "output_file": str(out_path),
        "summary": [
            {
                "name": r["name"],
                "total_views": r.get("total_views"),
                "annual_growth_rate": r.get("trend", {}).get("annual_growth_rate"),
                "confidence": r.get("confidence", {}).get("label"),
            }
            for r in results
        ],
    })


if __name__ == "__main__":
    main()
