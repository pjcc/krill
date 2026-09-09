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

## Output path

`build.py` resolves where `index.html` goes, in this order: `--out PATH` (or `--out=PATH`), then `$KRILLION_OUT`, then `index.html` beside the script. `fetch.py` passes its own argv straight through, so both accept the flag:

```
python fetch.py --out /var/www/piers.qa/krillo/index.html
```

Missing parent directories are created, and the page is written to a `.tmp` then renamed, so a web server never serves a half-written file.

## Cache

`cache.json` is v2: `{"v":2,"entries":{key:{"d":data,"t":epoch}}}`. A v1 flat `key -> data` file is migrated on load and stamped with the file mtime. Entries are touched on every cache hit, so anything still in use survives.

`prune_cache()` runs at the end of `fetch.py`: it drops entries unused for `KRILLION_CACHE_DAYS` (default 7), then evicts least-recently-used until the file fits `KRILLION_CACHE_MB` (default 20). Without it the cache grew ~750 KB a day forever, almost all base64 thumbnails.

Writes are throttled to one every 5 s rather than one per response, with a forced flush before the prune - a 429 backoff is at least 2 s, so a crash mid-run still resumes within a few requests.

## Known outstanding

- Nothing blocking. A daily schedule (Task Scheduler locally, or cron on a host) is the remaining step, and needs no code change
