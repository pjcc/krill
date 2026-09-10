"""Recover the days before the daily capture began, and enrich them exactly as
fetch.py enriches a live day. /api/reveal refuses every date but today and
Krillion's own archive is paid, so these come from copies of the reveal that
outlived it. Sources, best first, per day:

  1. The Wayback Machine's capture of /api/reveal - official, but it holds 3 Aug only
  2. krillion-game.com/archive/<date> - every accepted answer with its score and
     prompt. Matched our own 9 Sep capture exactly, all 4,772 answers. No quips
  3. krilliongame.net/archive/<date>/ - quips, which it carries from about early
     September, and any prompt krillion-game.com lacks or cuts short. Its answer
     lists matched the official key on 9 Sep, but 134 mid-tier scores drifted, so
     otherwise krillion-game.com's scores stand

krilliongame.com and krillion.fun are not used: their robots.txt disallows AI crawlers.

    python backfill.py                 every missing day from day one, then rebuild
    python backfill.py 2026-08-03 ...  just those days
"""
import datetime, gzip, html, json, os, re, sys, time, traceback
import urllib.error, urllib.request

import build, fetch

DAY_ONE = datetime.date(2026, 7, 16)     # day #1; /api/today called 10 Sep day #57
# Parsed answer keys, so a rerun after a Wikipedia 429 does not fetch the mirrors
# again. The mirror pages run to 5 MB, far too big for the response cache.
CACHE_DIR = os.path.join(fetch.DIR, '.backfill')
PAUSE = 1.5                              # between mirror requests; they are small sites
UA = {'User-Agent': 'krillion-daily/1.0 (one-off archive backfill)'}
TIERS = {100: 'krillion', 85: 'deepcut', 60: 'rare', 30: 'schooler', 15: 'tooclever', 10: 'plankton'}


def fetch_text(url):
    """GET as text. None on 404; retries timeouts, 429 and 5xx."""
    for wait in (PAUSE, 5, 15, 45):
        time.sleep(wait)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                body = r.read()
            if body[:2] == b'\x1f\x8b':
                body = gzip.decompress(body)
            return body.decode('utf-8', 'replace')
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code not in (429, 500, 502, 503, 504):
                raise
        except (urllib.error.URLError, TimeoutError):
            pass
    raise RuntimeError('gave up on ' + url)


def wayback_index():
    """date -> timestamp for every successful Wayback capture of /api/reveal.
    One prefix query rather than one per day: the CDX API times out often."""
    try:
        text = fetch_text('https://web.archive.org/cdx/search/cdx?url=krillion.io/api/reveal'
                          '&matchType=prefix&fl=timestamp,original&filter=statuscode:200')
    except Exception as e:
        print('wayback index unavailable (%s) - mirrors only' % e)
        return {}
    found = {}
    for line in (text or '').splitlines():
        m = re.match(r'(\d{14}) \S*date=(\d{4}-\d{2}-\d{2})', line)
        if m:
            found[m.group(2)] = m.group(1)
    return found


def from_wayback(date, stamp):
    text = fetch_text('https://web.archive.org/web/%sid_/https://krillion.io/api/reveal?date=%s' % (stamp, date))
    try:
        r = json.loads(text or '')
    except ValueError:
        return None
    # a capture of the "not publicly available" refusal has no prompts
    if len(r.get('prompts') or []) == 7 and all(p.get('answers') for p in r['prompts']):
        return r
    return None


def from_krillion_game(date):
    page = fetch_text('https://krillion-game.com/archive/' + date)
    if not page:
        return None
    prompts = {}
    for attrs in re.findall(r'<div class="answer-row[^"]*"([^>]*)>', page):
        a = {k: html.unescape(v) for k, v in re.findall(r'data-([a-z-]+)="([^"]*)"', attrs)}
        if 'answer' not in a or 'prompt' not in a:
            continue
        i, score = int(a['prompt']), int(a['score'])
        p = prompts.setdefault(i, {'id': 'p%d' % (i + 1), 'text': a['text'], 'answers': []})
        # KeyError on a score we have never seen: fail the day loudly rather than guess a tier
        p['answers'].append({'answer': a['answer'], 'tier': TIERS[score], 'score': score})
    # Can be short: 2026-07-30 has no 'Name a type of tea' here. recover() fills the gap.
    return {'date': date, 'prompts': [prompts[i] for i in sorted(prompts)]} if prompts else None


def from_krilliongame_net(date):
    """Every prompt with its answers, grouped by the page's prompt headings. Only
    used to fill prompts krillion-game.com lacks: its mid-tier scores drift."""
    page = fetch_text('https://krilliongame.net/archive/%s/' % date)
    if not page:
        return None
    parts = re.split(r'<h2 class="prompt-text">(.*?)</h2>', page, flags=re.S)
    prompts = []
    # parts alternates [before, heading, section, heading, section, ...]
    for n, (heading, section) in enumerate(zip(parts[1::2], parts[2::2])):
        answers = []
        for attrs, body in re.findall(r'<span class="chip"([^>]*)>(.*?)</li>', section, re.S):
            a = {k: html.unescape(v) for k, v in re.findall(r'data-([a-z-]+)="([^"]*)"', attrs)}
            score = int(a['tier-score'])
            item = {'answer': a['copy'], 'tier': TIERS[score], 'score': score}
            q = re.search(r'<span class="quip">(.*?)</span>', body, re.S)
            if q:
                item['quip'] = html.unescape(q.group(1)).strip()
            answers.append(item)
        prompts.append({'id': 'p%d' % (n + 1), 'text': html.unescape(heading).strip(), 'answers': answers})
    return {'date': date, 'prompts': prompts} if len(prompts) == 7 else None


def prompt_key(text):
    """The mirrors differ in quote style and spacing around the same prompt."""
    text = text.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
    return re.sub(r'\s+', ' ', text).strip().casefold()


def merge_mirrors(date, kg, net):
    """krillion-game.com's scores matched the official key exactly, so its prompts
    stand - unless missing, or cut short: on 2026-07-30 it lists 5 rodents where
    krilliongame.net lists 39. A prompt counts as cut short when krilliongame.net
    has at least 5 answers it lacks and they are a quarter of its list; a handful
    of extras is ordinary drift, as on 2026-08-03. krilliongame.net fills those
    prompts and supplies every quip it has."""
    if not net:
        if kg and len(kg['prompts']) == 7:
            return dict(kg, source='krillion-game.com')
        raise ValueError('%s: krillion-game.com is incomplete and krilliongame.net has no page' % date)
    kg_prompts = (kg or {}).get('prompts', [])
    exact = {prompt_key(p['text']): p for p in kg_prompts}
    # Prompts get reworded during the day - 2026-08-31 went from 'culinarily and
    # technically' to 'or'. When both lists are complete, a prompt whose wording
    # differs pairs with the one in the same position, provided at least half of
    # the smaller answer list is shared. krillion-game.com's wording is kept.
    positional = len(kg_prompts) == len(net['prompts'])
    used = set()

    prompts, filled = [], 0
    for n, p in enumerate(net['prompts']):
        g = exact.get(prompt_key(p['text']))
        if g is None and positional:
            cand = kg_prompts[n]
            mine, theirs = {a['answer'] for a in cand['answers']}, {a['answer'] for a in p['answers']}
            if mine and theirs and len(mine & theirs) >= 0.5 * min(len(mine), len(theirs)):
                g = cand
        if g is not None:
            used.add(id(g))
        if not g:
            prompts.append(p)
            filled += 1
            continue
        have = {a['answer'] for a in g['answers']}
        lacking = [a for a in p['answers'] if a['answer'] not in have]
        answers = list(g['answers'])
        if len(lacking) >= max(5, len(p['answers']) // 4):
            # Cut short: keep krillion-game.com's answers at its exact scores and
            # add only what it is missing. Taking krilliongame.net's whole list
            # instead dropped 'Crying Obsidian' from 2026-09-03's hundred-pointers.
            answers += [dict(a) for a in lacking]
            filled += 1
        prompts.append(dict(g, id=p['id'], answers=answers))
    if len(used) != len(kg_prompts):
        raise ValueError('%s: the two mirrors disagree on the prompts' % date)

    # Chips carry the answer, not the prompt, but quips are looked up per prompt
    # here, so an answer accepted for two prompts keeps the right one.
    quipped = 0
    for mine, theirs in zip(prompts, net['prompts']):
        quips = {a['answer'].casefold(): a['quip'] for a in theirs['answers'] if a.get('quip')}
        for a in mine['answers']:
            q = quips.get(a['answer'].casefold())
            if q and not a.get('quip'):
                a['quip'] = q
            quipped += bool(a.get('quip')) and a['tier'] == 'krillion'

    if not exact:
        source = 'krilliongame.net'
    else:
        source = 'krillion-game.com'
        if filled:
            source += ' + %d prompt(s) from krilliongame.net' % filled
        if quipped:
            source += ' + krilliongame.net quips'
    return {'date': date, 'prompts': prompts, 'source': source}


def recover(date, index):
    path = os.path.join(CACHE_DIR, date + '.json')
    if os.path.exists(path):
        return json.load(open(path, encoding='utf-8'))

    reveal = from_wayback(date, index[date]) if date in index else None
    if reveal:
        reveal['source'] = 'wayback'
    else:
        kg, net = from_krillion_game(date), from_krilliongame_net(date)
        if not kg and not net:
            return None
        reveal = merge_mirrors(date, kg, net)

    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(path + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(reveal, f, ensure_ascii=False)
    os.replace(path + '.tmp', path)
    return reveal


def main():
    have = {n[:-5] for n in os.listdir(build.DATA_DIR) if n.endswith('.json')}
    dates = [a for a in sys.argv[1:] if re.fullmatch(r'\d{4}-\d{2}-\d{2}', a)]
    if not dates:
        last = datetime.date.fromisoformat(max(have))
        span = (last - DAY_ONE).days
        dates = [(DAY_ONE + datetime.timedelta(n)).isoformat() for n in range(span)]
    dates = [d for d in dates if d not in have]
    print('backfilling %d day(s): %s .. %s' % (len(dates), dates[0], dates[-1]) if dates else 'nothing to backfill')

    index = wayback_index() if dates else {}
    done, failed = {}, []
    for date in dates:
        print('\n==', date, flush=True)
        try:
            reveal = recover(date, index)
            if not reveal:
                print('  no source holds this day')
                failed.append(date)
                continue
            out = fetch.enrich(reveal, date)
            out['source'] = reveal['source']
            fetch.write_day(out)
            done[date] = reveal['source']
            quipped = sum(1 for p in out['prompts'] for it in p['items'] if it['quip'])
            items = sum(len(p['items']) for p in out['prompts'])
            print('  wrote %s from %s - %d hundred-pointers, %d with quips' % (date, reveal['source'], items, quipped))
        except Exception:
            traceback.print_exc()
            failed.append(date)
        finally:
            fetch.save_cache(force=True)
            fetch.prune_cache()

    print('\nrecovered %d day(s), failed %d' % (len(done), len(failed)))
    for source in sorted(set(done.values())):
        print('  %-40s %d' % (source, sum(1 for s in done.values() if s == source)))
    if failed:
        print('  failed:', ' '.join(failed))
    if done:
        build.main(build.resolve_out())


if __name__ == '__main__':
    main()
