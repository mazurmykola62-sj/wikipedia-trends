#!/usr/bin/env python3
"""
Fetch a daily (or monthly) pageviews time series from the Wikimedia Pageviews
REST API, for either a single article or a whole project (used to normalize
topic interest against overall edition size -- see references/methodology.md).

Data is only available from 2015-07-01 onward, and is usually a few days
behind "today". Requests are cached on disk (scripts/../cache/), so re-running
the same request -- e.g. because the user asked a follow-up question -- is
free and instant.

Usage:
    # single article, daily granularity
    python fetch_pageviews.py --project pl.wikipedia --article "Post_przerywany" \\
        --start 2022-09-01 --end 2024-09-01 --output data/pl_fasting.json

    # whole-project totals, for normalizing "share of attention"
    python fetch_pageviews.py --project pl.wikipedia --whole-project \\
        --start 2022-09-01 --end 2024-09-01 --output data/pl_total.json

Output (stdout): compact JSON summary. Full daily series written to --output.
"""
import argparse
import json
import sys
from urllib.parse import quote

from common import get_json, parse_date, to_api_date, clamp_to_data_availability, print_summary, eprint, ensure_parent, DATA_START

BASE = "https://wikimedia.org/api/rest_v1/metrics/pageviews"


def fetch_per_article(project: str, article: str, access: str, agent: str, granularity: str, start: str, end: str) -> dict:
    encoded_article = quote(article.replace(" ", "_"), safe="")
    url = f"{BASE}/per-article/{project}/{access}/{agent}/{encoded_article}/{granularity}/{start}/{end}"
    return get_json(url)


def fetch_aggregate(project: str, access: str, agent: str, granularity: str, start: str, end: str) -> dict:
    url = f"{BASE}/aggregate/{project}/{access}/{agent}/{granularity}/{start}/{end}"
    return get_json(url)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True, help="e.g. pl.wikipedia, cs.wikipedia, en.wikipedia, uk.wikipedia")
    ap.add_argument("--article", help="Exact article title (use resolve_topic.py to find it). Omit if --whole-project.")
    ap.add_argument("--whole-project", action="store_true", help="Fetch project-wide totals instead of one article")
    ap.add_argument("--start", required=True, help="YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD")
    ap.add_argument("--access", default="all-access", choices=["all-access", "desktop", "mobile-app", "mobile-web"])
    ap.add_argument("--agent", default="user", choices=["user", "all-agents", "spider", "automated"],
                     help="'user' excludes bots/crawlers -- almost always what you want for interest analysis")
    ap.add_argument("--granularity", default="daily", choices=["daily", "monthly"])
    ap.add_argument("--output", required=True, help="Where to write the full time series JSON")
    args = ap.parse_args()

    if not args.article and not args.whole_project:
        print_summary({"status": "error", "message": "Provide --article or --whole-project"})
        sys.exit(1)

    start_d = parse_date(args.start)
    end_d = parse_date(args.end)
    if start_d < DATA_START:
        eprint(f"Note: pageviews data starts {DATA_START.isoformat()}; clamping start date.")
        start_d = clamp_to_data_availability(start_d)
    if end_d < start_d:
        print_summary({"status": "error", "message": "--end is before --start"})
        sys.exit(1)

    start_api = to_api_date(start_d)
    end_api = to_api_date(end_d)

    try:
        if args.whole_project:
            raw = fetch_aggregate(args.project, args.access, args.agent, args.granularity, start_api, end_api)
        else:
            raw = fetch_per_article(args.project, args.article, args.access, args.agent, args.granularity, start_api, end_api)
    except RuntimeError as e:
        print_summary({"status": "error", "message": str(e)})
        sys.exit(1)

    items = raw.get("items", [])
    series = [{"date": it["timestamp"][:8], "views": it["views"]} for it in items]
    series.sort(key=lambda r: r["date"])

    out = {
        "project": args.project,
        "article": args.article,
        "whole_project": args.whole_project,
        "access": args.access,
        "agent": args.agent,
        "granularity": args.granularity,
        "start": args.start,
        "end": args.end,
        "series": series,
    }
    out_path = ensure_parent(args.output)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    total_views = sum(r["views"] for r in series)
    print_summary({
        "status": "ok",
        "project": args.project,
        "article": args.article or "(whole project)",
        "rows": len(series),
        "date_range": [series[0]["date"], series[-1]["date"]] if series else None,
        "total_views": total_views,
        "output_file": str(out_path),
    })


if __name__ == "__main__":
    main()
