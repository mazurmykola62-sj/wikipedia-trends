# Roadmap -- growing this skill beyond the basics

The current version handles the three example use cases well: single-topic
trend + confidence, single-topic multi-language comparison, and multi-topic
"where should we look next" ranking. Here's how to grow it further, roughly
in the order it's likely to pay off.

## 1. Topic discovery, not just topic confirmation
Right now the skill answers "how is X doing" -- it doesn't yet answer "what
topics are trending that we haven't thought of." The `top/{project}/{access}/{Y}/{M}/{D}`
and `top-per-country/{country}/{access}/{Y}/{M}/{D}` endpoints (documented in
`api_reference.md` conceptually, not yet wrapped in a script) return the
most-viewed articles for a day/month/country. A `discover_trending.py` script
that pulls several months of "top" lists, diffs them, and surfaces articles
with the fastest *rank* improvement (not just raw views) would directly
support "what should we build next" questions instead of only "how is our
idea doing."

## 2. Category/portfolio-level analysis
Right now every query is per-article. A founder often thinks in categories
("health & wellness topics", "beginner programming topics"). Wikipedia's
category system and PetScan-style category-intersection tooling could let a
script pull a whole category's article list via the MediaWiki API
(`action=query&list=categorymembers`), fetch pageviews for all of them
(batched, respecting rate limits), and produce a portfolio-level view --
e.g. "average growth across N articles in this category" alongside the
current single-article view.

## 3. Real statistical rigor for the confidence rating
`confidence_rating()` is a fast, explainable heuristic, not a hypothesis
test. A meaningful next step is a proper trend-significance test (e.g. a
Mann-Kendall trend test, or bootstrapped confidence intervals on the
log-linear slope) so "High confidence" comes with an actual interval instead
of a five-point heuristic score. This matters more as usage grows past
quick sanity checks into decisions with real budget behind them. Keep the
heuristic as a fast pre-check even after adding this -- most queries don't
need a full statistical test, and it keeps things usable on a cheap model
that shouldn't need to reason about p-values.

## 4. Handling much larger date ranges and batches efficiently
The Pageviews API returns daily granularity even over multi-year ranges in
one call, which is fine for one or a few series. It stops being fine once a
user wants, say, 20 language editions x 10 topics. At that scale:
- Switch to `monthly` granularity for the initial scan, and only re-fetch
  `daily` for the languages/topics that clear a first-pass threshold.
- Add concurrency (a small thread pool) to `fetch_pageviews.py`, still
  respecting the rate limit in `common.py`, since Wikimedia's API handles
  parallel read traffic fine as long as clients aren't hammering it.
- Consider downloading the raw Wikimedia pageview dump files directly
  (https://dumps.wikimedia.org/other/pageviews/) for very large historical
  or cross-topic analyses -- the REST API is the right tool for targeted
  queries, but dumps are the right tool for "analyze everything."

## 5. Multi-topic, multi-language cross tabulation in one report
The current `make_report.py` produces one chart + one table per invocation.
A "language x topic" grid (which topics are hot in which languages) is a
natural next report type once category-level analysis (#2) exists --
probably a small-multiples chart (one mini chart per topic or per language)
rather than trying to cram everything into one line chart.

## 6. Sanity-check layer using a second, independent signal
Wikipedia interest is one proxy. A natural trust-building addition (not
required for this skill's scope, but worth flagging to a user who's about to
make a real spending decision) is cross-checking a Wikipedia trend against
an independent signal -- Google Trends, App Store category rankings, or
subreddit growth -- before treating "Wikipedia says it's growing" as
sufficient evidence on its own. If/when this skill grows a connector to
another data source, the report should show both signals side by side
rather than have the agent silently pick one.

## Suggested order if starting today
1 (discovery) unlocks the most new question types users will actually ask.
3 (real stats) matters most once reports start driving real budget.
2 and 4 matter once someone tries a portfolio-scale question and the current
single-article-at-a-time flow gets tedious or slow.
