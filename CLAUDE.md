# Krillion Daily

Scrapes the daily answer key from the game at https://krillion.io and renders the hundred-point answers as a single self-contained page. Built 9 Sep 2026. Not a git repo.

`README.txt` in this folder is the fuller writeup - read it before changing anything.

## Layout

- `fetch.py` - pulls the date and answers, resolves each answer to a Wikipedia article, embeds the thumbnail as a data URI, writes `data.json`, then calls `build.py`
- `build.py` - renders `data.json` into `index.html`; owns all styling
- `backfill.py` - recovers days before the daily capture began from the Wayback Machine and public mirrors, enriched through the same `fetch.enrich()` as a live day
- `overrides.json` - hand-checked Wikipedia titles for answers the search resolves wrongly; `null` means show no article. `fetch.resolve()` consults it before searching
- `reenrich.py` - re-resolves every captured answer listed in `overrides.json`, in place, then rebuilds. Run it after adding an override
- `cache.json` - every HTTP response keyed by URL; delete to force a fresh pull
- `reference/` - raw dumps from the day it was built
- `counter/` - Cloudflare Worker + D1 counting unique visitors per IP per UTC day; see 'Visitor counter' below

Rebuild everything with one command:

```
python C:\dev\krillion-daily\fetch.py
```

## The data source

`GET https://krillion.io/api/reveal?date=YYYY-MM-DD` returns the complete scored answer key - every accepted answer with its tier, score and quip - unauthenticated. It serves **only the live puzzle**: past and future dates return "That answer sheet is not publicly available", so the sheet has to be pulled on the day. The puzzle rolls at 04:00 UTC.

Past days are **not free, but not gone**: Krillion serves every day from a paid archive (`/api/archive/<dayNumber>` returns `402 {"locked":true}` without an `x-krillion-unlock` purchase token), and public mirrors hold every day from day one, 2026-07-16. Do not probe the archive routes without a token - that is testing a paywall for a bypass.

Tiers are krillion 100, deepcut 85, rare 60, schooler 30, plankton 10. Deepcut is the catch-all bulk tier holding roughly 90% of answers, so the only list worth knowing is the handful of plankton answers to avoid.

Short closed lists can have **no hundred-pointer at all** - 8 of the first 58 days had such a prompt, e.g. 'a country whose name starts with P' on 2026-09-11, ten answers topped by Palau at 85. That is not a failed capture. `fetch.enrich()` stores the top-scoring answers as `best` on any prompt with no items, and `build.none_html()` renders 'No answer scored a hundred on this one. The best was ...' in place of the entries. The 8 existing prompts were filled from `.backfill/` and the live reveal on 2026-09-11.

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

`data/<date>.json` is one enriched capture per day, and it is **tracked, not derived**. `/api/reveal` serves only the live puzzle - every other date, past or future, returns "That answer sheet is not publicly available" - so a day the daily run misses is gone from the free endpoint. Daily capture started 2026-09-09; everything earlier came from `backfill.py`.

`build.py` renders every captured day: `/<date>/index.html` for each, plus `/index.html` as a copy of the latest. Each page carries a previous / today / next nav, top and bottom. The root copy uses different link prefixes to the dated pages, since it sits one level up - `nav_html(..., root=True)`.

Because the data is kept rather than the HTML, a design change re-renders the whole archive on the next run.

The root page, and only the root, carries `LIVE_SCRIPT`: on `pageshow` and `visibilitychange`, if its `data-day` is behind the live puzzle day (UTC now minus 4 hours) it fetches itself with `cache: 'no-cache'` and reloads only if the response holds a newer `data-day`. Otherwise it stays put silently - no banner, by the user's choice - and re-checks at most once a minute. It covers a tab left open across the roll and a visit served from the browser's 10-minute Pages cache. A `sessionStorage` flag allows one reload per new day per tab, and no storage means no reload, so it cannot loop. Dated pages never get it, and neither does `--fragment` (the artifact host blocks fetch).

`fetch.py` skips the pull when `data/<date>.json` already exists, so the push and schedule triggers do not re-fetch the same day. `--force` re-pulls if a capture was interrupted.

## Backfill

`backfill.py` fills every missing day from 2026-07-16 (day #1) up to the latest capture, or just the dates given as arguments. Per day, best source first:

1. **Wayback Machine** capture of `/api/reveal` - official, but only 2026-08-03 exists. Found with one CDX prefix query, since per-day CDX calls time out
2. **krillion-game.com** `/archive/<date>` - `answer-row` divs carry `data-answer`, `data-score`, `data-prompt`, `data-text`. Verified identical to our own 9 Sep capture on all 4,772 answers and scores. No quips. Scores map 1:1 to tiers, including `tooclever` at 15; an unknown score fails the day rather than guessing
3. **krilliongame.net** `/archive/<date>/` - `<h2 class="prompt-text">` sections of `chip` spans. Its answer lists matched the official key on 9 Sep, but 134 mid-tier scores differ, so it supplies only: quips (63/63 exact on 9 Sep, present from roughly early September), prompts krillion-game.com is **missing** (2026-07-30 'type of tea'), and answers for prompts krillion-game.com has **cut short** (2026-07-30 rodents: 5 vs 39). Cut short means krilliongame.net has >= 5 answers it lacks and they are >= a quarter of its list; the merge then keeps krillion-game.com's answers and scores and appends only the missing ones - replacing the whole prompt dropped a hundred-pointer on 2026-09-03

Prompts get **reworded during the day** (2026-08-31: 'culinarily and technically' -> 'or'), so when both mirrors list seven prompts, a mismatched wording pairs by position if at least half the smaller answer list is shared. Anything else raises rather than guessing.

**krilliongame.com and krillion.fun are off-limits**: their robots.txt disallows ClaudeBot and other AI crawlers.

Recovered data files carry a `source` field. The pages deliberately do not show it, per day or in the footer, by the user's choice - the footer's line about mirrors was removed on 2026-09-11. Parsed answer keys are cached in `.backfill/` (untracked) so a rerun after a Wikipedia 429 skips the mirrors; the response cache is pruned after every day to stay inside its cap.

`HINTS` in `fetch.py` only covers the 9 Sep prompts, so other days resolve with no search hint, and the title search misfires on short or obscure answers: 'Oca' found Alexandria Ocasio-Cortez, 'Enganche' found Enhanced interrogation techniques, 'The Maschinenmensch' found the article 'The'. Across the 461 hundred-pointers of 2026-07-16 to 2026-09-10, 28 were wrong and now sit in `overrides.json`. Many other matches look wrong and are right - scientific or redirect titles (Pistol shrimp -> Alpheidae), or a parent article (Tatanga -> Super Mario Land) - so review by eye rather than by title similarity. Check a candidate title exists on `api/rest_v1/page/summary` before adding it; a redirect can land somewhere absurd ('Krayon' -> Krita).

## Output path

`--out PATH` (or `--out=PATH`, or `$KRILLION_OUT`) is the **site directory**, default `_site` beside the script:

```
python fetch.py --out /var/www/piers.qa/krill
```

With `--fragment` it is a single **file** instead, holding only the latest day with no nav - for a host that supplies its own document shell and cannot follow links to sibling pages. That is how the artifact copy is built.

Pages are written to a `.tmp` and renamed, so a web server never serves one half-written. `build.py` emits a complete document (doctype, charset, viewport); without the viewport meta a phone lays the page out at 980px virtual width.

## Publishing

The site is public at **https://piers.qa/krill/**, from the `pjcc/krill` repo, deployed by `.github/workflows/deploy.yml`. The schedule fires every 15 minutes from 04:07 to 12:52 UTC, because GitHub cron is best-effort - the original single 04:10 trigger first fired at 08:53, leaving the site a day behind all morning. The first run to land captures and deploys; later scheduled runs find the day captured and skip the deploy. Checkout uses `ref: main`, not the triggering sha, so a queued run sees a capture pushed by the run ahead of it.

`capture.log` is the run history: one line per run that tried to capture a day (each failure, then the success), with time since the 04:00 roll, try number, trigger and run URL. The workflow appends and commits it; runs that find the day already captured add nothing. A day with no line at all means no run fired. The log only starts on 2026-09-10 - the 09 Sep capture was pulled by hand. `piers.qa/krill` works because `pjcc/pjcc.github.io` carries the `piers.qa` CNAME, so project pages inherit it.

The workflow holds `contents: write` in order to commit each day's capture back to `data/`.

There is also an artifact copy at https://claude.ai/code/artifact/d375b6fa-2314-42bf-b7d9-0ae3c0aa653c - build it with `--fragment` and pass that URL as `url` when publishing.

## Cache

`cache.json` is v2: `{"v":2,"entries":{key:{"d":data,"t":epoch}}}`. A v1 flat `key -> data` file is migrated on load and stamped with the file mtime. Entries are touched on every cache hit, so anything still in use survives.

`prune_cache()` runs at the end of `fetch.py`: it drops entries unused for `KRILLION_CACHE_DAYS` (default 7), then evicts least-recently-used until the file fits `KRILLION_CACHE_MB` (default 20). Without it the cache grew ~750 KB a day forever, almost all base64 thumbnails.

Writes are throttled to one every 5 s rather than one per response, with a forced flush before the prune - a 429 backoff is at least 2 s, so a crash mid-run still resumes within a few requests.

`get()` accepts **https only**. Thumbnail URLs come from a remote API response and are inlined into a published page, and `urlopen` otherwise also honours `file:`, `ftp:` and `data:`.

## Visitor counter

Unique visitors (by IP), total hits and hits per visitor per UTC day, read at https://krill-hits.piers.qa/stats (HTML table) or `/stats.json`. GitHub Pages has no access logs, and `piers.qa` is **DNS-only** on Cloudflare (A records point at GitHub), so Cloudflare's zone analytics never see the traffic either. Proxying the zone to get them would cover all of `piers.qa`, not just `/krill`, so the counter is a separate Worker instead.

- `build.py` appends `HIT_SCRIPT`, a `sendBeacon` POST to `HIT_URL`, to every full page in `wrap_doc`. Not in `--fragment`: the artifact host blocks it by CSP
- `counter/src/index.js` rejects any `Origin` but `https://piers.qa` (which also drops local `file://` previews), then upserts `sha256(day|ip|SALT)` into D1 keyed on `(day, visitor)`: the first hit of the day adds a row, later ones bump its `hits`. Uniques are rows, total hits are `SUM(hits)`, so reloads - including `LIVE_SCRIPT`'s - add hits but never a second unique
- **IPv6 counts by /64, not by address.** Windows and phones reach the web from temporary (random-suffix) IPv6 addresses that rotate within their /64, so per-address keys split one device into several visitors in a day. Found 2026-09-11: a live test hit from this PC added a new unique instead of bumping its morning row, and Cloudflare was seeing a temporary address with 50 minutes of preferred lifetime left. `visitorKey()` expands `::` before cutting to four groups, and treats IPv4-mapped addresses as IPv4. Rows written before the change used whole addresses, so 2026-09-11's figures mix both
- `hits` was added after the table went live, so `schema.sql` carries the one-off `ALTER TABLE` for a database created before 2026-09-11. Run a column change **before** deploying the Worker that uses it - the old Worker's insert keeps working against the new column's default
- **No raw IPs are stored.** The date is inside the hash so visitors cannot be linked across days, and a missing `SALT` returns 500 rather than hashing unsalted, because an unsalted IPv4 hash is reversible by brute force
- Served on the custom domain `krill-hits.piers.qa` with `workers_dev = false`, so the beacon URL does not depend on the account's workers.dev subdomain
- Deploy steps and local testing are in `README.txt` under VISITOR COUNTER. `counter/.dev.vars` holds a local-only SALT and is untracked

## Known outstanding

- The archive grows ~440 KB a day in git, nearly all base64 thumbnails, and the backfill added 55 days at once - `data/` was 23 MB on 2026-09-10. Extracting images to separate deduplicated files would roughly halve it; the data files are the source of truth, so that migration stays open
