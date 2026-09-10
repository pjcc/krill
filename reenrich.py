"""Re-resolve every captured hundred-pointer that has an entry in overrides.json,
in place, then rebuild. Only those items change - answers, quips, totals and
tiers are untouched - so it is safe on days the free endpoint no longer serves.

    python reenrich.py
"""
import json, os

import build, fetch


def main():
    days = 0
    for name in sorted(os.listdir(build.DATA_DIR)):
        if not name.endswith('.json'):
            continue
        day = json.load(open(os.path.join(build.DATA_DIR, name), encoding='utf-8'))
        touched = False
        for p in day['prompts']:
            for n, it in enumerate(p['items']):
                if it['answer'] not in fetch.OVERRIDES:
                    continue
                new = fetch.enrich_item(it['answer'], it.get('quip', ''), fetch.hint_for(p['text']))
                if new != it:
                    p['items'][n] = new
                    touched = True
        if touched:
            fetch.write_day(day)
            days += 1
            print('rewrote', day['date'])
    fetch.save_cache(force=True)
    fetch.prune_cache()
    print('%d day(s) changed' % days)
    if days:
        build.main(build.resolve_out())


if __name__ == '__main__':
    main()
