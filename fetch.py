"""Pull today's Krillion krillion-tier answers, enrich each with a Wikipedia
summary + image, and write a self-contained page. Run once a day."""
import json, urllib.parse, urllib.request, urllib.error, base64, time, os, sys

DIR = os.path.dirname(os.path.abspath(__file__))
UA = {'User-Agent': 'krillion-daily/1.0 (local single-page summary generator)'}
THROTTLE = 1.0
BACKOFF = [2, 5, 10, 20, 40]

# Wikipedia rate-limits this network hard, so every response is cached to disk.
# A rerun after a 429 resumes instead of starting over. Entries carry a last-used
# timestamp so the cache can be pruned: a day of thumbnails is ~750 KB of base64
# and none of it is reused once the puzzle rolls, so under cron it grows forever.
CACHE_PATH = os.path.join(DIR, 'cache.json')
CACHE_DAYS = float(os.environ.get('KRILLION_CACHE_DAYS', 7))
CACHE_MB = float(os.environ.get('KRILLION_CACHE_MB', 20))
SAVE_EVERY = 5.0   # seconds between writes; a 429 backoff is >=2s, so a crash
                   # mid-run still resumes from within a few requests

def load_cache():
    """v2 is {'v':2,'entries':{key:{'d':data,'t':epoch}}}. A v1 file is a flat
    key->data dict with no times; stamp those with the file mtime so the first
    prune has something to judge them by."""
    try:
        raw = json.load(open(CACHE_PATH, encoding='utf-8'))
    except Exception:
        return {}
    if isinstance(raw, dict) and raw.get('v') == 2:
        return raw.get('entries', {})
    t = os.path.getmtime(CACHE_PATH)
    return {k: {'d': v, 't': t} for k, v in raw.items()}

CACHE = load_cache()
_last_save = [0.0]

def save_cache(force=False):
    if not force and time.time() - _last_save[0] < SAVE_EVERY:
        return
    tmp = CACHE_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump({'v': 2, 'entries': CACHE}, f)
    os.replace(tmp, CACHE_PATH)
    _last_save[0] = time.time()

def prune_cache():
    """Drop anything unused for CACHE_DAYS, then evict least-recently-used until
    the file fits CACHE_MB. Sizes are measured once rather than after every
    eviction - the cache is mostly base64 images, so re-serialising per drop is
    quadratic on megabytes."""
    before = len(CACHE)
    cut = time.time() - CACHE_DAYS * 86400
    for k in [k for k, e in CACHE.items() if e.get('t', 0) < cut]:
        del CACHE[k]
    sizes = {k: len(json.dumps(e)) for k, e in CACHE.items()}
    total = sum(sizes.values())
    cap = CACHE_MB * 1024 * 1024
    for k in sorted(CACHE, key=lambda k: CACHE[k].get('t', 0)):
        if total <= cap:
            break
        total -= sizes[k]
        del CACHE[k]
    save_cache(force=True)
    print('cache: %d entries, %.1f MB (dropped %d)'
          % (len(CACHE), total / 1048576.0, before - len(CACHE)))

def get(url, raw=False, fresh=False):
    """fresh=True skips the cache both ways - needed for any URL whose response
    changes without the URL changing, or the cache pins it forever."""
    # urlopen also speaks file:, ftp: and data:. Thumbnail URLs come from a
    # remote API response, and whatever they point at is base64'd straight into
    # a published page, so only https is allowed through. data_uri swallows the
    # error and renders an empty plate.
    if not url.startswith('https://'):
        raise ValueError('refusing non-https URL: ' + url[:80])
    key = ('raw:' if raw else '') + url
    if not fresh and key in CACHE:
        e = CACHE[key]
        e['t'] = time.time()          # touch, so what is still in use survives a prune
        return base64.b64decode(e['d']) if (raw and e['d']) else e['d']
    for n in range(len(BACKOFF) + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=25) as r:
                body = r.read()
            val = body if raw else json.loads(body)
            if not fresh:
                CACHE[key] = {'d': base64.b64encode(body).decode() if raw else val,
                              't': time.time()}
                save_cache()
            return val
        except urllib.error.HTTPError as e:
            if e.code == 404:
                CACHE[key] = {'d': None, 't': time.time()}
                save_cache()
                return None
            if e.code in (429, 503) and n < len(BACKOFF):
                time.sleep(BACKOFF[n])
                continue
            raise
    return None

# search hint per prompt, to keep homonyms honest
HINTS = {
    'city in California': 'California',
    'horns or antlers': 'animal',
    'Spanish or Portuguese dish': 'dish',
    'aquatic mammal': 'mammal',
    'carnivorous mammal': 'mammal',
    'video game genre': 'video game',
    'street suffix': 'road type',
}
def hint_for(prompt):
    return next((v for k, v in HINTS.items() if k in prompt), '')

# Hand-checked Wikipedia titles for answers the search resolves wrongly - 'Oca',
# the Andean tuber, found Alexandria Ocasio-Cortez. Consulted before any search.
# A null title means showing no article beats showing the one the search found.
# reenrich.py applies a change here to days already captured.
OVERRIDES_PATH = os.path.join(DIR, 'overrides.json')
OVERRIDES = json.load(open(OVERRIDES_PATH, encoding='utf-8')) if os.path.exists(OVERRIDES_PATH) else {}

def enc(t):
    return urllib.parse.quote(t.replace(' ', '_'), safe='')

def search(term, hint):
    q = urllib.parse.quote(f'{term} {hint}'.strip())
    time.sleep(THROTTLE)
    d = get(f'https://en.wikipedia.org/w/rest.php/v1/search/title?q={q}&limit=4')
    return [p['key'] for p in (d or {}).get('pages', [])]

def summary(title):
    time.sleep(THROTTLE)
    return get(f'https://en.wikipedia.org/api/rest_v1/page/summary/{enc(title)}')

def resolve(answer, hint):
    """Try the literal title, then search hits, then shorter prefixes of the
    answer. Returns (summary, approx) - approx flags a prefix fallback, which is
    a related article rather than the answer itself."""
    if answer in OVERRIDES:
        s = summary(OVERRIDES[answer]) if OVERRIDES[answer] else None
        return (s if s and s.get('extract') else None), False
    for title in [answer] + search(answer, hint):
        s = summary(title)
        if s and s.get('extract') and s.get('type') != 'disambiguation':
            return s, False
    words = answer.split()
    for n in range(len(words) - 1, 0, -1):
        stem = ' '.join(words[:n])
        for title in [stem] + search(stem, hint):
            s = summary(title)
            if s and s.get('extract') and s.get('type') != 'disambiguation':
                return s, True
    return None, False

def data_uri(url):
    if not url:
        return None
    try:
        if url.startswith('//'):
            url = 'https:' + url
        time.sleep(THROTTLE)
        blob = get(url, raw=True)
        if not blob:
            return None
        ext = url.rsplit('.', 1)[-1].lower().split('?')[0]
        mime = {'jpg': 'jpeg', 'jpeg': 'jpeg', 'png': 'png', 'gif': 'gif', 'webp': 'webp'}.get(ext, 'jpeg')
        return f'data:image/{mime};base64,' + base64.b64encode(blob).decode()
    except Exception:
        return None

def enrich_item(answer, quip, hint):
    """One hundred-pointer, resolved to its Wikipedia summary and thumbnail."""
    s, approx = resolve(answer, hint)
    thumb = (s.get('thumbnail') or {}).get('source') if s else None
    item = {
        'answer': answer,
        'quip': quip,
        'title': s['title'] if s else None,
        'description': s.get('description') if s else None,
        'extract': s['extract'] if s else None,
        'url': s['content_urls']['desktop']['page'] if s else None,
        'image': data_uri(thumb),
        'approx': approx,
    }
    print(f"  {answer} -> {item['title']}{' (approx)' if approx else ''} | img: {bool(item['image'])}", flush=True)
    return item

def enrich(reveal, date):
    """A reveal-shaped answer key -> one day's data file: the hundred-pointers
    resolved to Wikipedia, plus per-prompt totals and tier counts. Shared with
    backfill.py, so a recovered day renders exactly like a captured one."""
    out = {'date': date, 'prompts': []}
    for p in reveal['prompts']:
        hint = hint_for(p['text'])
        items = []
        for a in p['answers']:
            if a['tier'] != 'krillion':
                continue
            items.append(enrich_item(a['answer'], a.get('quip', ''), hint))
        tiers = {}
        for a in p['answers']:
            tiers[a['tier']] = tiers.get(a['tier'], 0) + 1
        entry = {
            'text': p['text'],
            'total': len(p['answers']),
            'tiers': tiers,
            'items': items,
        }
        if not items:
            entry['best'] = best_of(p['answers'], hint)
        out['prompts'].append(entry)
    return out

def best_of(answers, hint):
    """The top-scoring answers, kept for a prompt where nothing scored a
    hundred. Short closed lists do this - 'a country whose name starts with P'
    has ten accepted answers, the best at 85 - and without it the section is a
    bare heading that reads as a failed capture. Each is linked to its article
    but gets no summary or image: they are a footnote to an empty section, not
    entries."""
    if not answers:
        return None
    top = max(a['score'] for a in answers)
    return {'score': top,
            'answers': [link_item(a['answer'], hint) for a in answers if a['score'] == top]}

def link_item(answer, hint):
    """An answer and its Wikipedia link, with no summary or thumbnail. A prefix
    fallback gets no link: with no 'closest article' tag beside it, a related
    article would pass for the answer's own."""
    s, approx = resolve(answer, hint)
    ok = bool(s) and not approx
    item = {'answer': answer,
            'title': s['title'] if ok else None,
            'url': s['content_urls']['desktop']['page'] if ok else None}
    print(f"  {answer} -> {item['title']}{' (approx, unlinked)' if s and approx else ''}", flush=True)
    return item

def write_day(out):
    """Written the same way as the pages: a half-written capture cannot be
    re-pulled the next day, because the endpoint has moved on by then."""
    import build
    os.makedirs(build.DATA_DIR, exist_ok=True)
    day_path = os.path.join(build.DATA_DIR, out['date'] + '.json')
    tmp = day_path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    os.replace(tmp, day_path)
    return day_path

def main():
    import build
    out_path = build.resolve_out()   # --out PATH / $KRILLION_OUT / next to the script
    date = get('https://krillion.io/api/today', fresh=True)['date']

    os.makedirs(build.DATA_DIR, exist_ok=True)
    day_path = os.path.join(build.DATA_DIR, date + '.json')
    # The workflow runs on every push as well as on the schedule, and a day's
    # answers never change once captured, so re-fetching is pure waste. --force
    # re-pulls if a capture was interrupted and left a partial file.
    if os.path.exists(day_path) and '--force' not in sys.argv[1:]:
        print(date, 'already captured - rebuilding only (--force to re-pull)')
        build.main(out_path)
        return

    reveal = get(f'https://krillion.io/api/reveal?date={date}')
    write_day(enrich(reveal, date))
    print()
    print('wrote', day_path)

    save_cache(force=True)
    prune_cache()
    build.main(out_path)


if __name__ == '__main__':
    main()
