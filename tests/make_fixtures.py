#!/usr/bin/env python3
"""Generate synthetic fetch_pageviews.py-shaped JSON for offline pipeline tests.

NOT part of the skill's runtime -- this only exists so the analysis/chart/report
scripts can be exercised end-to-end without live network access. See ../../TESTING_NOTES.md.
"""
import json
import math
import random
from datetime import date, timedelta

random.seed(42)


def make_series(start: date, days: int, base: float, annual_growth: float, weekly_amp: float, spike_days: list[int], noise: float) -> list[dict]:
    series = []
    for i in range(days):
        d = start + timedelta(days=i)
        trend = base * ((1 + annual_growth) ** (i / 365))
        weekday_factor = 1 - weekly_amp * (1 if d.weekday() >= 5 else 0)
        val = trend * weekday_factor * (1 + random.gauss(0, noise))
        if i in spike_days:
            val *= random.uniform(4, 8)
        series.append({"date": d.strftime("%Y%m%d"), "views": max(0, round(val))})
    return series


def write(path, project, article, series):
    out = {
        "project": project, "article": article, "whole_project": False,
        "access": "all-access", "agent": "user", "granularity": "daily",
        "start": series[0]["date"], "end": series[-1]["date"], "series": series,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    start = date(2023, 9, 1)
    days = 730

    pl = make_series(start, days, base=120, annual_growth=0.9, weekly_amp=0.15, spike_days=[300, 301], noise=0.18)
    cs = make_series(start, days, base=40, annual_growth=0.15, weekly_amp=0.15, spike_days=[], noise=0.35)

    write("fixtures/pl_fasting.json", "pl.wikipedia", "Post_przerywany", pl)
    write("fixtures/cs_fasting.json", "cs.wikipedia", "P\u0159eru\u0161ovan\u00fd_p\u016fst", cs)

    pl_total = make_series(start, days, base=9_000_000, annual_growth=0.02, weekly_amp=0.2, spike_days=[], noise=0.05)
    cs_total = make_series(start, days, base=3_000_000, annual_growth=0.02, weekly_amp=0.2, spike_days=[], noise=0.05)
    write("fixtures/pl_total.json", "pl.wikipedia", None, pl_total)
    write("fixtures/cs_total.json", "cs.wikipedia", None, cs_total)

    print("fixtures written")
