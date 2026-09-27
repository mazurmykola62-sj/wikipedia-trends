---
name: wikipedia-trends
description: Analyze Wikipedia pageview trends to help B2C product teams decide what topics to build next or which languages to localize into. Use this whenever someone wants to know whether interest in a topic is growing on Wikipedia, wants to compare interest across language editions, wants to know how much to trust a trend before acting on it, or wants a short shareable report (chart + one-page PDF) backing a product/localization decision. Trigger this for phrases like "is interest in X growing", "compare interest in X between languages", "should we build a course/feature on X", "which language should we launch in next", or any request to analyze Wikipedia pageviews/traffic data -- even if the user doesn't name Wikipedia explicitly and just describes wanting to validate a product idea against public interest data.
---

# Wikipedia Trends Analyst

Helps a B2C product team decide where to invest next -- a new topic, a new
language -- by turning Wikipedia's public pageview data into a trend,
a confidence rating, and a short shareable report. The point isn't the
chart; it's giving the team a number they can act on and know how much to
trust.

## Why this skill exists instead of writing code ad hoc

Fetching Wikipedia pageviews, resolving the right article title per
language, fitting a trend, and laying out a one-page PDF is the same
several-hundred-line job every time. The scripts in `scripts/` do that job
once, well, so you can spend your reasoning on the part that actually needs
judgment: which questions to ask, how to read the confidence rating, and
what recommendation the numbers actually support. Run the scripts; don't
reimplement pageviews fetching or trend math inline.

**Before writing any custom code for this task, check whether one of the five
scripts below already does it.** They cover: resolving a topic to per-language
article titles, fetching a pageviews series, computing a trend + confidence,
drawing a comparison chart, and assembling a one-page PDF report.

## One-time setup

```bash
cd <this skill's directory>
pip install -r requirements.txt --break-system-packages
```

All five scripts live in `scripts/` and are run as `python3 scripts/<name>.py
--help` to see full options. Run them from a working directory where you're
happy to accumulate a `data/` and `cache/` folder for this session's files --
per-run temp directories are fine, that data doesn't need to persist beyond
the conversation.

## The five scripts, in the order you'll normally use them

1. **`resolve_topic.py`** -- turn a topic ("intervalno holodannya" / a natural
   language description) into the exact article title in each target
   language edition. **Always do this before fetching**, even if you think
   you know the title -- guessing produces silent wrong-or-empty data rather
   than an error, because a plausible-looking title may just not exist or
   may be a different, related article.
2. **`fetch_pageviews.py`** -- fetch the daily pageviews series for one
   article, or for a whole project (use `--whole-project` when you'll need
   to normalize across languages later -- see step 3).
3. **`analyze_trend.py`** -- compute growth rate, year-over-year change,
   spike days, and a confidence rating from one or more fetched series.
   Read `references/methodology.md` before explaining its output to a user
   -- the confidence rating and "annualized trend" number both need honest
   framing, not just quoting the percentage.
4. **`make_chart.py`** -- render the comparison chart (PNG) from analysis
   output.
5. **`make_report.py`** -- assemble chart + stats table + your narrative
   findings into a one-page shareable PDF.

Every script prints a small JSON summary to stdout and writes full data to
the file you asked for. Read the summary, don't cat the full JSON file into
your own context -- these series can be thousands of rows and the summary
has everything you need to decide the next step or talk to the user.

## Worked example: comparing two languages

```bash
# 1. Resolve the topic in both target languages
python3 scripts/resolve_topic.py --topic "intermittent fasting" --langs pl,cs \
    --output data/resolved.json
# -> {"resolved": {"pl": "Post przerywany", "cs": "Přerušovaný půst"}, ...}

# 2. Fetch each language's article series, and (for a fair comparison)
#    each edition's whole-project totals
python3 scripts/fetch_pageviews.py --project pl.wikipedia --article "Post_przerywany" \
    --start 2022-09-01 --end 2024-09-01 --output data/pl_topic.json
python3 scripts/fetch_pageviews.py --project cs.wikipedia --article "Přerušovaný_půst" \
    --start 2022-09-01 --end 2024-09-01 --output data/cs_topic.json
python3 scripts/fetch_pageviews.py --project pl.wikipedia --whole-project \
    --start 2022-09-01 --end 2024-09-01 --output data/pl_total.json
python3 scripts/fetch_pageviews.py --project cs.wikipedia --whole-project \
    --start 2022-09-01 --end 2024-09-01 --output data/cs_total.json

# 3. Analyze, with normalization since PL and CS Wikipedia are very different sizes
python3 scripts/analyze_trend.py --series pl=data/pl_topic.json --series cs=data/cs_topic.json \
    --normalize pl=data/pl_total.json --normalize cs=data/cs_total.json \
    --output data/analysis.json

# 4. Chart
python3 scripts/make_chart.py --analysis data/analysis.json --output data/chart.png \
    --title "Intermittent fasting: PL vs CS Wikipedia"

# 5. Write findings.json yourself (this is where your judgment goes -- see
#    the schema in make_report.py's docstring), then:
python3 scripts/make_report.py --analysis data/analysis.json --chart data/chart.png \
    --title "Intermittent fasting: PL vs CS Wikipedia" --findings data/findings.json \
    --output report.pdf
```

Then present `report.pdf` to the user (or use it as an artifact source) and
summarize the headline finding in your reply -- don't make them open the PDF
to learn the one-sentence answer.

## Mapping the three common question shapes

- **"Is interest in X growing, and can we trust it?"** -> resolve (1 language)
  -> fetch (article only, whole-project not needed for a single series) ->
  analyze -> read the confidence label and reasons -> answer in prose,
  offering a chart/report if the finding is report-worthy. Don't build a PDF
  for a single quick yes/no unless asked -- see `<file_creation_advice>` in
  your general instructions; a one-line confident/hedged answer is often
  enough.
- **"Compare growth of X between language A and B"** -> resolve both ->
  fetch both articles + both whole-project totals -> analyze with
  `--normalize` -> chart -> report if the user wants something shareable.
- **"Compare topic X across several language editions we've picked, and tell
  us which audiences to look at next"** -> resolve once per language ->
  fetch each -> analyze all together (more than 2 `--series` flags works
  fine; `analyze_trend.py` returns a `comparison.ranked_by_growth_rate` you
  can turn directly into a "look at these next, in this order" answer,
  explaining *why* using the confidence + total-views numbers, not just the
  ranking).

Real requests will deviate from these three shapes -- different date ranges,
a single language instead of a comparison, three topics instead of two,
"forget the PDF, just tell me." Adapt the scripts to the actual question
rather than forcing it into one of these templates; the scripts compose
freely (any number of `--series`, optional `--normalize`, chart and report
are both optional if the user just wants an answer in chat).

## Follow-up and refinement questions

Users will ask "now add Ukrainian", "what about just the last 6 months",
"show me that normalized" after seeing a first answer. `fetch_pageviews.py`
caches every request on disk, so:
- Re-running the exact same fetch is instant and free (no network call).
- A narrower or wider date range on an already-fetched project/article is a
  new cache entry but still cheap and fast.
- Keep the `data/*.json` intermediate files around for the rest of the
  session instead of deleting them -- a follow-up usually only needs
  `analyze_trend.py` re-run (fast, no network) rather than re-fetching.

See `references/methodology.md`'s "Handling follow-up questions efficiently"
section for more.

## When something goes wrong

- **A script's summary has `"status": "error"`** -- the message explains
  what happened (bad date range, article not found, etc.); read it and
  adjust rather than retrying blindly.
- **`fetch_pageviews.py` 404s** -- almost always a wrong title. Re-run
  `resolve_topic.py`, and if it also fails, the topic may genuinely lack an
  article in that edition -- say so rather than guessing a title.
- **A trend looks like growth but confidence is Low** -- read the `reasons`
  list in the confidence object and say what's actually driving the
  uncertainty (too little data, one spike, high volatility) rather than
  hedging vaguely. See `references/methodology.md`.
- **Deep API or endpoint questions** the scripts don't cover -- see
  `references/api_reference.md` before improvising a new endpoint call.

## Growing this skill further

Once basic requests work well, see `references/roadmap.md` for how to extend
this toward topic discovery (not just confirmation), category-level
analysis, more rigorous statistics, and larger-scale batch queries.
