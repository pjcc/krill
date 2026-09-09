"""Render data.json into a self-contained single page."""
import json, os, sys, html, datetime

DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.join(DIR, 'index.html')


# Served from a web root there is no host to supply a document shell, and with
# no viewport meta a phone lays the page out at a 980px virtual width - the
# 760px column then sits centred behind wide gutters, scaled down. Artifact
# hosts inject their own shell and reject a nested one, hence --fragment.
DOC_OPEN = ('<!doctype html>\n<html lang="en">\n<head>\n'
            '<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            '<meta name="color-scheme" content="dark">\n'
            '<meta name="description" content="The rarest accepted answer to each of '
            "today's seven Krillion prompts, and what each one actually is.\">\n")
DOC_MID = '</head>\n<body>\n'
DOC_CLOSE = '\n</body>\n</html>\n'


def resolve_out(out=None, argv=None):
    """Output path: explicit argument, then --out PATH / --out=PATH, then
    $KRILLION_OUT, then index.html beside the script. A cron job needs to write
    straight into a web root rather than here."""
    if out:
        return os.path.abspath(out)
    argv = list(sys.argv[1:] if argv is None else argv)
    for i, a in enumerate(argv):
        if a == '--out' and i + 1 < len(argv):
            return os.path.abspath(argv[i + 1])
        if a.startswith('--out='):
            return os.path.abspath(a.split('=', 1)[1])
    return os.path.abspath(os.environ.get('KRILLION_OUT') or DEFAULT_OUT)

HEAD = """<title>The Krillion Dive</title>
<link rel="icon" href="data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%20100%20100'%3E%3Ctext%20y='.9em'%20font-size='90'%3E%F0%9F%A6%90%3C/text%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,500;0,9..144,700;1,9..144,500&family=IBM+Plex+Mono:wght@400;500&family=Newsreader:opsz,wght@6..72,400;6..72,500&display=swap">
<style>
:root{
  --abyss:#060d16;
  --trench:#0c1725;
  --line:#1b2d42;
  --line-soft:#122033;
  --foam:#e9eff6;
  --mist:#92a6bc;
  --read:#ccd9e8;   /* body copy: brighter than mist, which is for labels */
  --dimmer:#546b85;
  --krill:#ff7a52;
  --krill-soft:#c9553a;
  --caution:#c8a05a;
  --caution-line:#5c4a2a;
}
*{box-sizing:border-box}
body{
  margin:0;
  background:var(--abyss);
  color:var(--foam);
  font-family:Newsreader,Georgia,"Times New Roman",serif;
  font-weight:400;
  font-size:17px;
  line-height:1.62;
  -webkit-font-smoothing:antialiased;
}
.wrap{max-width:760px;margin:0 auto;padding:0 28px 96px}
.mono{
  font-family:"IBM Plex Mono",ui-monospace,Consolas,monospace;
  font-weight:400;
  letter-spacing:.09em;
  text-transform:uppercase;
  font-size:11px;
  color:var(--dimmer);
}

header{padding:64px 0 0}
.eyebrow{display:flex;justify-content:space-between;align-items:baseline;gap:16px;flex-wrap:wrap}
h1{
  font-family:Fraunces,Georgia,"Times New Roman",serif;
  font-weight:700;
  font-size:clamp(40px,8vw,66px);
  line-height:1.02;
  letter-spacing:-.015em;
  margin:22px 0 0;
  text-wrap:balance;
}
h1 em{font-style:italic;font-weight:500;color:var(--krill)}
.standfirst{color:var(--mist);font-size:17px;margin:16px 0 0;max-width:52ch}
.gauge{
  display:grid;
  grid-template-columns:repeat(3,1fr);
  margin:38px 0 0;
  border-top:1px solid var(--line);
  border-bottom:1px solid var(--line);
}
.gauge div{padding:18px 22px 19px}
.gauge div + div{border-left:1px solid var(--line-soft)}
.gauge div:first-child{padding-left:0}
.gauge b{
  display:block;
  font-family:"IBM Plex Mono",monospace;
  font-variant-numeric:tabular-nums;
  font-weight:500;font-size:27px;line-height:1.1;letter-spacing:-.02em;
  color:var(--foam);
}
.gauge span{display:block;margin-top:7px;color:var(--mist)}

section{margin-top:56px}
.phead{display:flex;align-items:baseline;gap:14px;padding-bottom:14px;border-bottom:1px solid var(--line)}
.pnum{
  font-family:"IBM Plex Mono",monospace;
  font-variant-numeric:tabular-nums;
  font-size:11px;letter-spacing:.09em;color:var(--krill-soft);
  flex:none;
}
h2{
  font-family:Fraunces,Georgia,"Times New Roman",serif;
  font-weight:500;font-size:25px;line-height:1.25;margin:0;
  text-wrap:balance;flex:1;
}
.pmeta{flex:none;text-align:right}

.entry{
  display:grid;
  grid-template-columns:132px 1fr;
  gap:24px;
  padding:26px 0;
  border-bottom:1px solid var(--line-soft);
}
.entry:last-child{border-bottom:0;padding-bottom:4px}
.plate{
  width:132px;height:132px;
  background:var(--trench);
  border:1px solid var(--line);
  overflow:hidden;
  display:flex;align-items:center;justify-content:center;
}
.plate img{width:100%;height:100%;object-fit:cover;display:block;filter:saturate(.92) contrast(1.04)}
.plate.empty{background:radial-gradient(circle at 50% 42%,#16283c 0%,var(--trench) 72%)}
.top{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
h3{
  font-family:Fraunces,Georgia,"Times New Roman",serif;
  font-weight:700;font-size:22px;line-height:1.18;margin:0;
  letter-spacing:-.005em;text-wrap:balance;
}
h3 a{
  color:var(--foam);
  text-decoration:underline;
  text-decoration-color:rgba(255,122,82,.45);
  text-decoration-thickness:1px;
  text-underline-offset:3px;
}
h3 a:hover{color:var(--krill);text-decoration-color:var(--krill)}
.desc{margin:6px 0 0;font-size:14.5px;font-style:italic;color:var(--mist);
  letter-spacing:0;text-transform:none;font-family:inherit}
.extract{margin:12px 0 0;color:var(--read);font-size:18px;line-height:1.64}
.quip{
  margin:14px 0 0;padding-left:14px;
  border-left:2px solid var(--line);
  font-style:italic;font-size:16.5px;color:var(--foam);
}
a{color:var(--krill);text-decoration:underline;text-decoration-color:rgba(255,122,82,.4);
  text-decoration-thickness:1px;text-underline-offset:2px}
a:hover{text-decoration-color:var(--krill)}
a:focus-visible{outline:2px solid var(--krill);outline-offset:3px}
.approx{
  font-family:"IBM Plex Mono",monospace;
  font-size:10px;letter-spacing:.08em;text-transform:uppercase;
  color:var(--caution);border:1px solid var(--caution-line);padding:2px 6px 1px;
}

footer{margin-top:64px;padding-top:22px;border-top:1px solid var(--line)}
footer p{margin:0 0 7px;font-size:11px;line-height:1.7;color:var(--dimmer)}
footer code{font-family:"IBM Plex Mono",monospace;color:var(--mist);text-transform:none;letter-spacing:0}

@media (max-width:560px){
  .wrap{padding:0 18px 64px}
  header{padding:40px 0 0}
  h1{font-size:38px;letter-spacing:-.01em}
  .standfirst{font-size:16px;margin-top:14px}
  .gauge{margin-top:28px}
  /* These were flex rules left over from a flex .gauge and did nothing to a
     grid, so the three cells stayed at desktop padding on a phone. */
  .gauge div{padding:13px 12px 14px}
  .gauge div:first-child{padding-left:0}
  .gauge b{font-size:21px}
  .gauge span{margin-top:5px;font-size:10px;letter-spacing:.06em}
  section{margin-top:40px}
  .phead{flex-wrap:wrap;gap:10px}
  h2{font-size:22px}
  /* Beside an 84px plate the measure was down to 278px, with a tall dead
     gutter under the image. Floating it lets the text reclaim the full width
     once the image ends. */
  .entry{display:block;padding:20px 0}
  .plate{float:left;width:84px;height:84px;margin:5px 14px 6px 0}
  .entry::after{content:"";display:block;clear:both}
  h3{font-size:20px}
  .extract{font-size:17px}
}
</style>"""


def esc(s):
    return html.escape(s or '', quote=True)


def entry_html(it):
    if it.get('image'):
        plate = ('<div class="plate"><img src="' + esc(it['image']) + '" alt="'
                 + esc(it.get('title') or it['answer']) + '"></div>')
    else:
        plate = '<div class="plate empty"><span class="mono">no plate</span></div>'

    # the answer itself is the link out; the tag only appears when the article
    # we found is a near miss rather than the answer
    name = esc(it['answer'])
    if it.get('url'):
        name = ('<a href="' + esc(it['url']) + '" target="_blank" rel="noopener">'
                + name + '</a>')
        tag = ('<span class="approx">' + esc(it['title']) + '</span>') if it.get('approx') else ''
    else:
        tag = '<span class="approx">no article</span>'

    bits = ['<div class="top"><h3>' + name + '</h3>' + tag + '</div>']
    if it.get('description'):
        bits.append('<p class="desc">' + esc(it['description']) + '</p>')
    if it.get('extract'):
        bits.append('<p class="extract">' + esc(it['extract']) + '</p>')
    if it.get('quip'):
        bits.append('<p class="quip">' + esc(it['quip']) + '</p>')

    return '<div class="entry">' + plate + '<div>' + ''.join(bits) + '</div></div>'


def main(out=None, fragment=None):
    path = resolve_out(out)
    if fragment is None:
        fragment = '--fragment' in sys.argv[1:]
    d = json.load(open(os.path.join(DIR, 'data.json'), encoding='utf-8'))
    date = d['date']
    pretty = datetime.date.fromisoformat(date).strftime('%d %B %Y').lstrip('0')

    n_answers = sum(len(p['items']) for p in d['prompts'])
    n_total = sum(p.get('total', 0) for p in d['prompts'])
    n_obvious = sum(p.get('tiers', {}).get('plankton', 0) for p in d['prompts'])

    secs = []
    for i, p in enumerate(d['prompts'], 1):
        entries = ''.join(entry_html(it) for it in p['items'])
        secs.append(
            '<section><div class="phead">'
            + '<span class="pnum">' + '%02d' % i + '</span>'
            + '<h2>' + esc(p['text']) + '</h2>'
            + '<span class="pmeta mono">' + format(p.get('total', 0), ',') + ' accepted</span>'
            + '</div>' + entries + '</section>'
        )

    body = (
        '<div class="wrap">\n<header>\n'
        '  <div class="eyebrow">'
        '<span class="mono">Krillion &middot; the daily dive</span>'
        '<span class="mono">' + esc(pretty) + '</span></div>\n'
        '  <h1>Krillion <em>top hits</em> today</h1>\n'
        '  <p class="standfirst">The rarest accepted answer to each of today\'s seven prompts, '
        'and what each one actually is.</p>\n'
        '  <div class="gauge">'
        '<div><b>' + format(n_total, ',') + '</b><span class="mono">answers accepted</span></div>'
        '<div><b>' + str(n_answers) + '</b><span class="mono">worth a hundred</span></div>'
        '<div><b>' + str(n_obvious) + '</b><span class="mono">worth only ten</span></div>'
        '</div>\n</header>\n'
        + ''.join(secs) +
        '\n<footer>\n'
        '  <p>Answers from <code>krillion.io/api/reveal?date=' + esc(date) + '</code>, '
        'which serves the live puzzle only. Summaries and images from Wikipedia, CC BY-SA, linked per entry.</p>\n'
        '</footer>\n</div>'
    )

    # Emit pure ASCII: Wikipedia extracts are full of non-breaking spaces and
    # accents, and the page renders in hosts that may not declare a charset.
    if fragment:
        doc = HEAD + body
    else:
        doc = DOC_OPEN + HEAD + DOC_MID + body + DOC_CLOSE
    doc = doc.encode('ascii', 'xmlcharrefreplace').decode('ascii')
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    # write-then-rename, so a web server never serves a half-written page
    tmp = path + '.tmp'
    open(tmp, 'w', encoding='ascii').write(doc)
    os.replace(tmp, path)
    print('wrote', path, '(%.0f KB)' % (len(doc) / 1024))


if __name__ == '__main__':
    main()
