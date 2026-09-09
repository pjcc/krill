KRILLION DAILY

Generates a single self-contained page showing the hundred-point ("krillion" tier) answers to today's seven Krillion prompts, each with a Wikipedia summary, image and link.

Published page: https://claude.ai/code/artifact/d375b6fa-2314-42bf-b7d9-0ae3c0aa653c


RUN IT

python C:\dev\krillion-daily\fetch.py

That fetches the data and rebuilds index.html in one go. Do it after 04:00 UTC, which is when the puzzle rolls over. Then republish the artifact to refresh the hosted copy, or just open index.html locally.

To write the page somewhere else - a web root, for a scheduled run - pass --out, or set KRILLION_OUT:

python C:\dev\krillion-dailyetch.py --out D:\www\krillo\index.html

Missing directories are created, and the file is written to a .tmp and renamed, so a web server never serves it half-written.


FILES

fetch.py - pulls the date from krillion.io/api/today, the answers from /api/reveal, resolves each answer to a Wikipedia article, embeds the thumbnail as a data URI, writes data.json, then calls build.py
build.py - renders data.json into index.html; owns all the styling
index.html - the generated page, self-contained at roughly 441 KB (images are inline data URIs)
data.json - the enriched answer set for the current date
cache.json - every HTTP response, keyed by URL, with a last-used timestamp; delete to force a fully fresh pull
reference/krillion_answers_2026-09-09.txt - full dump of all 4,772 accepted answers for 9 Sep 2026, grouped by tier
reference/reveal_2026-09-09.json - the raw /api/reveal response for the same date


HOW THE DATA IS OBTAINED

GET https://krillion.io/api/reveal?date=YYYY-MM-DD returns the complete scored answer key: every accepted answer with its tier, score and quip. No authentication. It serves the live puzzle only - past and future dates return "That answer sheet is not publicly available", so the sheet has to be pulled on the day.

Tiers are krillion 100, deepcut 85, rare 60, schooler 30, plankton 10. Deepcut is the catch-all bulk tier, so almost any non-obvious answer scores 85; the list worth knowing is the handful of plankton answers to avoid.


CONSTRAINTS WORTH REMEMBERING

krillion.io sends no CORS headers, so a browser page cannot fetch the answers directly - hence generating the page rather than making it live. Artifacts additionally block all runtime fetch by CSP, and block external images, which is why thumbnails are embedded as data URIs.

Wikipedia's action=query search API returns 429 unconditionally from this network. Resolution goes through rest.php/v1/search/title instead, with the summary coming from api/rest_v1/page/summary. Requests are throttled and every response is cached to cache.json, so a rerun after a rate limit resumes rather than starting over.

The cache would otherwise grow forever - about 750 KB a day, nearly all of it base64 thumbnails that are never reused once the puzzle rolls. Each run now prunes it: entries untouched for KRILLION_CACHE_DAYS (default 7) are dropped, then the least recently used are evicted until the file fits KRILLION_CACHE_MB (default 20). Cache hits refresh the timestamp, so anything still in use survives. The file format carries a version - an old flat cache is migrated automatically on first load.

Two matches are imperfect and the page labels them as such: "Cozido das Furnas" has no article and falls back to "Cocido" with a "closest article" tag, and "Immersive sim" has an article but no image, so it renders a blank plate.

The page is deliberately dark-only and paints its own background rather than inheriting the host's theme.
