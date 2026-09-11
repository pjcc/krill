KRILLION DAILY

Generates a single self-contained page showing the hundred-point ("krillion" tier) answers to today's seven Krillion prompts, each with a Wikipedia summary, image and link.

Published at https://piers.qa/krill/ - rebuilt and redeployed daily by GitHub Actions from the pjcc/krill repo. There is also an artifact copy at https://claude.ai/code/artifact/d375b6fa-2314-42bf-b7d9-0ae3c0aa653c.


RUN IT

python C:\dev\krillion-daily\fetch.py

That captures today into data/<date>.json and rebuilds the whole site into _site/ in one go. Do it after 04:00 UTC, which is when the puzzle rolls over. The hosted site refreshes itself daily; open _site/index.html to check it locally.

--out is the output DIRECTORY (default _site beside the script), or set KRILLION_OUT:

python C:\dev\krillion-daily\fetch.py --out D:\www\krill

Missing directories are created, and each page is written to a .tmp and renamed, so a web server never serves one half-written. With --fragment, --out is a single FILE holding only the latest day and no navigation - that is how the artifact copy is built.


FILES

fetch.py - pulls the date from krillion.io/api/today, the answers from /api/reveal, resolves each answer to a Wikipedia article, embeds the thumbnail as a data URI, writes data.json, then calls build.py
backfill.py - recovers days from before the daily capture began (see BACKFILL below) and enriches them with the same code as fetch.py, then rebuilds
overrides.json - hand-checked Wikipedia titles for answers the search gets wrong; null means show no article rather than the wrong one
reenrich.py - re-resolves every captured answer listed in overrides.json, in place, then rebuilds
build.py - renders data.json into index.html; owns all the styling
_site/ - the generated site: index.html is the latest day, <date>/index.html is each archived day. Self-contained at roughly 441 KB per page (images are inline data URIs)
data/<date>.json - one enriched capture per day. TRACKED IN GIT, not derived: see below
cache.json - every HTTP response, keyed by URL, with a last-used timestamp; delete to force a fully fresh pull
counter/ - the Cloudflare Worker behind the unique-visitors-per-day counter (see VISITOR COUNTER below)
reference/krillion_answers_2026-09-09.txt - full dump of all 4,772 accepted answers for 9 Sep 2026, grouped by tier
reference/reveal_2026-09-09.json - the raw /api/reveal response for the same date


HOW THE DATA IS OBTAINED

GET https://krillion.io/api/reveal?date=YYYY-MM-DD returns the complete scored answer key: every accepted answer with its tier, score and quip. No authentication. It serves the live puzzle only - past and future dates return "That answer sheet is not publicly available", so the sheet has to be pulled on the day.

That is why data/<date>.json is committed rather than regenerated. The daily capture started on 2026-09-09; a day it misses is gone from the free endpoint for good.


BACKFILL

Past days are not gone, only not free. Krillion serves every day from a paid archive (/api/archive/<day number> returns 402 locked without a purchase token), and two public mirrors of the reveal endpoint hold every day from day one, 2026-07-16. backfill.py recovers each missing day from, in order of preference:

1. The Wayback Machine's capture of /api/reveal - official, but it holds only 2026-08-03
2. krillion-game.com/archive/<date> - every answer with its score and prompt. Checked against our own 9 Sep capture: all 4,772 answers and every score identical. No quips
3. krilliongame.net/archive/<date>/ - quips, which it carries from roughly early September, plus any prompt krillion-game.com is missing (2026-07-30 lacks one) or has cut short (five days list a fraction of the answers). A cut-short prompt keeps krillion-game.com's answers and scores and adds only what it lacks, because krilliongame.net's mid-tier scores drift from the official ones. Prompts reworded during the day are paired by position when their answer lists overlap

krilliongame.com and krillion.fun also mirror recent days but disallow AI crawlers in robots.txt, so they are not used. Recovered days carry a "source" field in their data file; the pages do not show it. Days before about September have no quips.

python C:\dev\krillion-daily\backfill.py              every missing day since day one
python C:\dev\krillion-daily\backfill.py 2026-08-03   just that day

Parsed answer keys are kept in .backfill/ (not tracked), so a rerun after a Wikipedia rate limit does not hit the mirrors again.

The Wikipedia title search sometimes lands on the wrong article for short or obscure answers - "Oca", the Andean tuber, found Alexandria Ocasio-Cortez. Wrong matches found by eye go in overrides.json, then:

python C:\dev\krillion-daily\reenrich.py

Each page carries a previous / today / next navigation across whatever days have been captured. Because the enriched data is what is kept, rather than the finished HTML, a design change re-renders the entire archive on the next run.

Tiers are krillion 100, deepcut 85, rare 60, schooler 30, plankton 10. Deepcut is the catch-all bulk tier, so almost any non-obvious answer scores 85; the list worth knowing is the handful of plankton answers to avoid.

Some prompts have no hundred-point answer at all - short closed lists like "a country whose name starts with P", which had ten accepted answers topped by Palau at 85. The data file then records the top-scoring answers as "best", and the page says so under the heading instead of leaving the section empty.


VISITOR COUNTER

Unique visitors (by IP), total hits and hits per visitor, per day, at https://krill-hits.piers.qa/stats - a table, newest day first, with the same data at /stats.json. GitHub Pages keeps no access logs and piers.qa is DNS-only on Cloudflare, so neither sees the traffic - hence a separate Worker.

Every full page ends with a sendBeacon POST to https://krill-hits.piers.qa/hit. The Worker in counter/ rejects anything whose Origin is not https://piers.qa, hashes date + IP + a secret salt, and upserts it into a D1 table keyed on (day, visitor): the first hit of the day adds a row, every later one from the same IP bumps that row's hits. A hit is a page load that runs the script - archive navigation and the root page's stale-day reload count, a back-button return from the browser's page cache does not. Days are UTC calendar days. Raw IPs are never stored, and the date in the hash means one visitor cannot be tracked across days, so hits per visitor is a list of counts with no addresses attached. The artifact (--fragment) build carries no beacon, since its host blocks it by CSP.

It undercounts visitors whose ad blocker drops the beacon or who have JavaScript off, and counts one household behind a shared IP once. Crawlers that do not run JavaScript never register.

Deploy from counter/ (needs `npx wrangler login` once):

npx wrangler d1 create krill-hits                                  then paste the id into wrangler.toml
npx wrangler d1 execute krill-hits --remote --file schema.sql
npx wrangler secret put SALT                                       any long random string; changing it only affects future rows
npx wrangler deploy

To test locally: put SALT=anything in counter/.dev.vars, run `npx wrangler d1 execute krill-hits --local --file schema.sql`, then `npx wrangler dev --local`.


CONSTRAINTS WORTH REMEMBERING

krillion.io sends no CORS headers, so a browser page cannot fetch the answers directly - hence generating the page rather than making it live. Artifacts additionally block all runtime fetch by CSP, and block external images, which is why thumbnails are embedded as data URIs.

Wikipedia's action=query search API returns 429 unconditionally from this network. Resolution goes through rest.php/v1/search/title instead, with the summary coming from api/rest_v1/page/summary. Requests are throttled and every response is cached to cache.json, so a rerun after a rate limit resumes rather than starting over.

The cache would otherwise grow forever - about 750 KB a day, nearly all of it base64 thumbnails that are never reused once the puzzle rolls. Each run now prunes it: entries untouched for KRILLION_CACHE_DAYS (default 7) are dropped, then the least recently used are evicted until the file fits KRILLION_CACHE_MB (default 20). Cache hits refresh the timestamp, so anything still in use survives. The file format carries a version - an old flat cache is migrated automatically on first load.

Two matches are imperfect and the page labels them as such: "Cozido das Furnas" has no article and falls back to "Cocido" with a "closest article" tag, and "Immersive sim" has an article but no image, so it renders a blank plate.

The page is deliberately dark-only and paints its own background rather than inheriting the host's theme.
