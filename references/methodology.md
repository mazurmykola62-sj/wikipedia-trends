# Methodology -- how to read and explain the numbers

Read this before turning `analyze_trend.py` output into a sentence you say
to the user, especially anything about growth rate or confidence. The goal
of this skill is not just "make a chart" -- it's "help someone make a real
decision", so the caveats matter as much as the headline number.

## What "annualized trend" actually is

`analyze_trend.py` smooths the raw daily views with a 7-day rolling average
(to cancel out the weekday/weekend pattern that most reference-style Wikipedia
articles show), then fits a straight line to `log(views)` over time. The
slope of that line, converted back out of log-space, becomes an **annualized
growth rate** -- e.g. `+0.84` means "views grew at a rate consistent with
+84%/year over this period," not "views were exactly 84% higher at the end
than the start" (that's what `year_over_year_change` reports instead, when
enough data exists).

This is a *trend estimate*, not a forecast and not a hypothesis test. Report
it as "the data is consistent with X% annual growth," not "views will grow
X% next year."

## Why confidence is a label, not a p-value

`confidence_rating()` combines five cheap signals into a High/Medium/Low
label with stated reasons:

1. **Total views** -- under a few thousand total views over the period,
   percentage changes swing wildly from a handful of extra visits. Treat any
   growth number on a low-traffic article as illustrative, not decisive.
2. **Time span** -- under ~6 months, you cannot separate "sustained growth"
   from "this month happens to be a seasonal peak." Under a year, you can't
   compute a real year-over-year comparison at all (the script won't even
   try; `year_over_year_change` will be `null`).
3. **Fit quality (R²)** -- how closely the smoothed data actually follows a
   straight line in log-space. Low R² means the "trend" is a mathematical
   description of noisy data, not a real pattern -- say so plainly rather
   than reporting the growth number with false precision.
4. **Spike days** -- days flagged as statistical outliers (a robust z-score
   on raw daily views) usually mean a news event, a viral social post, or a
   site outage skewing one day, not a change in underlying interest. A
   article that "grew" only because of one spike should be reported as flat
   with a footnote about the spike, not as a growth story.
5. **Coefficient of variation** -- how noisy day-to-day views are relative to
   their average. High volatility makes any single number (this month's
   average, this week's peak) unreliable evidence on its own.

When you write up a finding, prefer sentences like "growth is consistent and
well-supported (High confidence: 2 years of data, clean trend, no major
spikes)" over stripping the label off and just quoting the percentage.

## Comparing across languages fairly

Raw view counts are **not directly comparable** across language editions,
because editions differ hugely in total audience size (English Wikipedia
gets vastly more traffic than Czech Wikipedia regardless of topic). Two
tools handle this:

- **Share of attention** (`--normalize` flag on `analyze_trend.py`): divide
  an article's daily views by that edition's total daily views. This
  answers "how much does this topic punch above/below its edition's normal
  size," which is usually the more honest comparison for market-selection
  questions (e.g. "which language audience is unusually interested in this
  specific topic, relative to how much that audience reads Wikipedia at
  all"). Always fetch a matching `--whole-project` series when comparing
  languages for a business decision.
- **Growth rate comparison** (the default, no normalization needed): compares
  the *rate of change* rather than the absolute level, which is naturally
  more comparable across editions of different size -- but still worth
  pairing with total-views numbers so a 200%/year growth from 10 to 30 views
  isn't mistaken for a real signal.

## What this data can and can't tell you

Be explicit with the user about this, especially in report `summary` /
`recommendation` text:

- Pageview interest is a proxy for **attention**, not for willingness to pay,
  retention, or conversion. Say this in any report that will inform a
  monetization decision (course launches, localization spend, etc.).
- A rising trend on Wikipedia doesn't distinguish "growing genuine curiosity"
  from "one influencer/news cycle causing search traffic" -- the spike
  detection in this skill catches single-day events but not a multi-week
  fad. If growth is very recent (last 1-2 months) and otherwise flat before
  that, flag it as recent and unconfirmed rather than a multi-year pattern.
- Wikipedia readership skews toward people already looking things up
  out of curiosity or research, which correlates with but isn't identical
  to the audience for a paid product on the same topic.
- Absence of an article, or very low views, doesn't mean absence of interest
  -- it can mean the topic doesn't have good Wikipedia coverage in that
  language yet. Don't present "no Wikipedia article" as "no interest."

## Handling follow-up and related questions efficiently

Users will refine their question after seeing a first answer ("now add
Ukrainian", "what about the last 6 months instead", "normalize that").
Because `fetch_pageviews.py` caches every request on disk keyed by the exact
URL, re-running with a wider or narrower date range only re-fetches what's
new -- and re-running the *same* request (e.g. re-generating a chart with a
different title) costs no network calls at all. Prefer:

- Re-fetching a *superset* date range over stitching multiple fetches, when
  practical -- one clean series is easier to re-analyze than several to merge.
- Keeping each topic/language's intermediate files (`data/*.json`,
  `analysis.json`) around during a session instead of deleting them, so a
  follow-up only needs `analyze_trend.py` / `make_chart.py` /
  `make_report.py` re-run on already-fetched data.
- Re-running `resolve_topic.py` once per topic and reusing its output across
  however many follow-up date ranges or normalizations the user asks for.
