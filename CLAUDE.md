# Krillion Daily

Scrapes the daily answer key from the game at https://krillion.io and renders the hundred-point answers as a single self-contained page. Built 9 Sep 2026. Not a git repo.

`README.txt` in this folder is the fuller writeup - read it before changing anything.

## Layout

- `fetch.py` - pulls the date and answers, resolves each answer to a Wikipedia article, embeds the thumbnail as a data URI, writes `data.json`, then calls `build.py`
- `build.py` - renders `data.json` into `index.html`; owns all styling
- `cache.json` - every HTTP response keyed by URL; delete to force a fresh pull
- `reference/` - raw dumps from the day it was built

Rebuild everything with one command:

```
python C:\dev\krillion-daily\fetch.py
```

## The data source

`GET https://krillion.io/api/reveal?date=YYYY-MM-DD` returns the complete scored answer key - every accepted answer with its tier, score and quip - unauthenticated. It serves **only the live puzzle**: past and future dates return "That answer sheet is not publicly available", so the sheet has to be pulled on the day. The puzzle rolls at 04:00 UTC.

Tiers are krillion 100, deepcut 85, rare 60, schooler 30, plankton 10. Deepcut is the catch-all bulk tier holding roughly 90% of answers, so the only list worth knowing is the handful of plankton answers to avoid.

## Constraints - do not rediscover these

- **krillion.io sends no CORS headers**, so a browser page cannot fetch the answers directly. That is why the page is generated rather than live. Artifacts additionally block all runtime `fetch` by CSP and block external images, hence thumbnails as data URIs
- **`/api/today` has no date in its URL.** It must bypass the response cache (`fresh=True`) or the cache pins the date permanently and every run rebuilds the same day. This was a real bug; do not reintroduce it. The same applies to any URL whose response changes without the URL changing
- **Wikipedia's `action=query` search API returns 429 unconditionally from this network**, regardless of User-Agent. Resolution goes through `rest.php/v1/search/title`, with summaries from `api/rest_v1/page/summary`. Requests are throttled and cached
- Output is written as **pure ASCII with entity escapes**, because the extracts are full of non-breaking spaces and accents and the page renders in hosts that may not declare a charset
- The design is **deliberately dark-only** and paints its own background rather than inheriting the host theme

## Publishing

The page is published at https://claude.ai/code/artifact/d375b6fa-2314-42bf-b7d9-0ae3c0aa653c

To update it, pass that URL as `url` when publishing. Publishing without it creates a second, separate artifact.

## Archive and navigation

`data/<date>.json` is one enriched capture per day, and it is **tracked, not derived**. `/api/reveal` serves only the live puzzle - every other date, past or future, returns "That answer sheet is not publicly available" - so a day that is not captured on the day is gone permanently. The archive starts 2026-09-09 and cannot be backfilled.

`build.py` renders every captured day: `/<date>/index.html` for each, plus `/index.html` as a copy of the latest. Each page carries a previous / today / next nav, top and bottom. The root copy uses different link prefixes to the dated pages, since it sits one level up - `nav_html(..., root=True)`.

Because the data is kept rather than the HTML, a design change re-renders the whole archive on the next run.

`fetch.py` skips the pull when `data/<date>.json` already exists, so the push and schedule triggers do not re-fetch the same day. `--force` re-pulls if a capture was interrupted.

## Output path

`--out PATH` (or `--out=PATH`, or `$KRILLION_OUT`) is the **site directory**, default `_site` beside the script:

```
python fetch.py --out /var/www/piers.qa/krill
```

With `--fragment` it is a single **file** instead, holding only the latest day with no nav - for a host that supplies its own document shell and cannot follow links to sibling pages. That is how the artifact copy is built.

Pages are written to a `.tmp` and renamed, so a web server never serves one half-written. `build.py` emits a complete document (doctype, charset, viewport); without the viewport meta a phone lays the page out at 980px virtual width.

## Publishing

The site is public at **https://piers.qa/krill/**, from the `pjcc/krill` repo, deployed by `.github/workflows/deploy.yml` on a daily 04:10 UTC schedule. `piers.qa/krill` works because `pjcc/pjcc.github.io` carries the `piers.qa` CNAME, so project pages inherit it.

The workflow holds `contents: write` in order to commit each day's capture back to `data/`.

There is also an artifact copy at https://claude.ai/code/artifact/d375b6fa-2314-42bf-b7d9-0ae3c0aa653c - build it with `--fragment` and pass that URL as `url` when publishing.

## Cache

`cache.json` is v2: `{"v":2,"entries":{key:{"d":data,"t":epoch}}}`. A v1 flat `key -> data` file is migrated on load and stamped with the file mtime. Entries are touched on every cache hit, so anything still in use survives.

`prune_cache()` runs at the end of `fetch.py`: it drops entries unused for `KRILLION_CACHE_DAYS` (default 7), then evicts least-recently-used until the file fits `KRILLION_CACHE_MB` (default 20). Without it the cache grew ~750 KB a day forever, almost all base64 thumbnails.

Writes are throttled to one every 5 s rather than one per response, with a forced flush before the prune - a 429 backoff is at least 2 s, so a crash mid-run still resumes within a few requests.

`get()` accepts **https only**. Thumbnail URLs come from a remote API response and are inlined into a published page, and `urlopen` otherwise also honours `file:`, `ftp:` and `data:`.

## Known outstanding

- The archive grows ~440 KB a day in git, nearly all base64 thumbnails. Extracting images to separate deduplicated files would roughly halve it; the data files are the source of truth, so that migration stays open
