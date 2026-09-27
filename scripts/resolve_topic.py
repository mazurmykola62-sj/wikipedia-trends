#!/usr/bin/env python3
"""
Resolve a topic to the correct article title in one or more Wikipedia language
editions. This matters because the same topic has a *different* title in each
language ("Intermittent fasting" / "Post przerywany" / "Přerušovaný půst"), and
pageviews must be fetched per exact title -- guessing titles silently produces
wrong or empty data.

Strategy:
1. Search for the topic in a "source" language edition (default: en) using the
   MediaWiki search API to find the most likely article.
2. Read that article's Wikidata item id (pageprops.wikibase_item).
3. Ask Wikidata for that item's sitelinks in each requested target language.

Usage:
    python resolve_topic.py --topic "intermittent fasting" --langs pl,cs,uk
    python resolve_topic.py --topic "astronomy" --langs uk --source-lang en

Output (stdout): one compact JSON object mapping lang -> resolved info.
Also writes the same JSON to --output (default: resolved_<topic-slug>.json).
"""
import argparse
import json
import re
import sys
from pathlib import Path

from common import get_json, print_summary, eprint, ensure_parent

WIKIDATA_API = "https://www.wikidata.org/w/api.php"


def search_title(lang: str, query: str) -> dict | None:
    url = (
        f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search"
        f"&srsearch={requests_quote(query)}&format=json&srlimit=1"
    )
    data = get_json(url)
    results = data.get("query", {}).get("search", [])
    if not results:
        return None
    return {"title": results[0]["title"], "snippet": strip_html(results[0].get("snippet", ""))}


def get_wikibase_item(lang: str, title: str) -> str | None:
    url = (
        f"https://{lang}.wikipedia.org/w/api.php?action=query&prop=pageprops"
        f"&titles={requests_quote(title)}&format=json"
    )
    data = get_json(url)
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        qid = page.get("pageprops", {}).get("wikibase_item")
        if qid:
            return qid
    return None


def get_sitelinks(qid: str, langs: list[str]) -> dict:
    sitefilter = "|".join(f"{lang}wiki" for lang in langs)
    url = (
        f"{WIKIDATA_API}?action=wbgetentities&ids={qid}&props=sitelinks"
        f"&sitefilter={sitefilter}&format=json"
    )
    data = get_json(url)
    entity = data.get("entities", {}).get(qid, {})
    sitelinks = entity.get("sitelinks", {})
    out = {}
    for lang in langs:
        key = f"{lang}wiki"
        if key in sitelinks:
            out[lang] = sitelinks[key]["title"]
    return out


def requests_quote(s: str) -> str:
    from urllib.parse import quote
    return quote(s, safe="")


def strip_html(s: str) -> str:
    return re.sub("<[^<]+?>", "", s)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--topic", required=True, help="Topic in natural language, e.g. 'intermittent fasting'")
    ap.add_argument("--langs", required=True, help="Comma-separated target language codes, e.g. pl,cs,uk")
    ap.add_argument("--source-lang", default="en", help="Language to run the initial search in (default: en)")
    ap.add_argument("--output", default=None, help="Where to write the full JSON result")
    args = ap.parse_args()

    langs = [l.strip() for l in args.langs.split(",") if l.strip()]
    slug = re.sub(r"[^a-z0-9]+", "-", args.topic.lower()).strip("-")
    out_path = args.output or f"data/resolved_{slug}.json"

    found = search_title(args.source_lang, args.topic)
    if not found:
        print_summary({"status": "error", "message": f"No article found for '{args.topic}' in {args.source_lang}wiki"})
        sys.exit(1)

    qid = get_wikibase_item(args.source_lang, found["title"])
    result = {
        "topic_query": args.topic,
        "source_lang": args.source_lang,
        "source_title": found["title"],
        "source_snippet": found["snippet"],
        "wikidata_id": qid,
        "languages": {},
        "missing_languages": [],
    }

    if qid:
        sitelinks = get_sitelinks(qid, langs)
        for lang in langs:
            if lang in sitelinks:
                result["languages"][lang] = sitelinks[lang]
            else:
                result["missing_languages"].append(lang)
    else:
        # No Wikidata item -- fall back to searching directly in each target wiki.
        # Less reliable: this can match a related-but-different article.
        for lang in langs:
            hit = search_title(lang, args.topic)
            if hit:
                result["languages"][lang] = hit["title"]
                result.setdefault("fallback_search_used", []).append(lang)
            else:
                result["missing_languages"].append(lang)

    ensure_parent(out_path)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print_summary({
        "status": "ok",
        "source_title": result["source_title"],
        "resolved": result["languages"],
        "missing_languages": result["missing_languages"],
        "output_file": str(out_path),
        "note": "Review 'missing_languages' -- the topic may not have an article in that edition, "
                "or may need a manual title override passed straight to fetch_pageviews.py.",
    })


if __name__ == "__main__":
    main()
