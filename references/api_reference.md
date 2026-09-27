# Wikimedia Pageviews API -- reference

Read this if a script errors out in a way the summary JSON doesn't explain,
or if you need to call the API in a way the bundled scripts don't cover.

## Base facts

- Base URL: `https://wikimedia.org/api/rest_v1/metrics/pageviews/`
- No API key or account needed.
- Every request needs a descriptive `User-Agent` header with contact info
  (this is a Wikimedia policy, not just politeness) -- `scripts/common.py`
  sets this once for every script. If you fork/modify the code, replace the
  placeholder contact in `USER_AGENT` with a real one before serious use.
- Data availability starts **2015-07-01**. Data for "today" and the last
  1-2 days is usually not published yet.
- Full reference: https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/reference/page-views.html

## Endpoints used by this skill

### Per-article views
```
per-article/{project}/{access}/{agent}/{article}/{granularity}/{start}/{end}
```
- `project`: `{lang}.wikipedia`, e.g. `pl.wikipedia`, `cs.wikipedia`, `uk.wikipedia`, `en.wikipedia`.
  Sister projects also work (`commons.wikimedia`, `www.wikidata`) but this skill
  is written for language-edition Wikipedias.
- `access`: `all-access` (default, almost always right), `desktop`, `mobile-app`, `mobile-web`.
- `agent`: `user` (excludes bots/crawlers -- use this for interest analysis),
  `all-agents`, `spider`, `automated`.
- `article`: exact title, spaces as underscores, URL-encoded. Wrong title ->
  404 or an empty/wrong series with no error. **Always resolve the title
  first** (see resolve_topic.py) rather than guessing a translation.
- `granularity`: `daily` or `monthly`.
- `start`/`end`: `YYYYMMDDHH` (hour is usually `00`).

### Project-wide aggregate (for normalization)
```
aggregate/{project}/{access}/{agent}/{granularity}/{start}/{end}
```
Same parameters, no article. Gives total daily/monthly views for the whole
edition -- used to compute "share of attention" so editions of very
different sizes (e.g. Polish vs. Czech Wikipedia) become comparable.

## Title resolution (not part of the Pageviews API)

The same topic has a different title per language edition, and there's no
"translate this title" endpoint on the Pageviews API itself. `resolve_topic.py`
uses two other public Wikimedia APIs to solve this:

1. MediaWiki search API (`https://{lang}.wikipedia.org/w/api.php?action=query&list=search...`)
   to find the likely article for a natural-language topic string.
2. Wikidata (`https://www.wikidata.org/w/api.php?action=wbgetentities...`) to
   read that article's **sitelinks**, which map the same Wikidata item to its
   title in every other language edition. This is far more reliable than
   searching separately in each language, because search can match a
   related-but-different article.

If a topic has no Wikidata item (rare, but happens for very obscure or very
new topics), `resolve_topic.py` falls back to searching directly in each
target language and flags this in its output (`fallback_search_used`) so you
know to double check the result before trusting it.

## Known limitations worth remembering

- **Redirects**: if an article was renamed or merged, pageviews recorded
  under the old title may not show up under the new one for the whole
  period. Spot-check by fetching the redirect target too if a series looks
  suspiciously low or has a sudden step change.
- **Bot filtering isn't perfect**: `agent=user` removes known crawlers, but
  some automated non-bot traffic can still leak through as apparent human
  views, especially for very low-traffic articles.
- **Mobile app vs. web vs. desktop** don't need separate treatment for most
  questions -- `all-access` sums them. Only split by access method if the
  user specifically asks about a platform shift.
