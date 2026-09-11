// Visitors per day for piers.qa/krill. Every full page sends a beacon to /hit,
// and the Worker keeps one row per visitor per UTC day, counting that visitor's
// hits. /stats shows unique visitors, total hits and hits per visitor for each
// day as a table; /stats.json is the same data.
//
// Raw IPs are never stored, only a SHA-256 of date + visitor key + a secret
// salt. The date in the hash means the same visitor on two days cannot be
// linked, and the salt stops anyone reversing it by hashing all four billion
// IPv4 addresses - which is also why a missing salt fails the request rather
// than hashing without one. So hits per visitor is a list of counts, not of
// addresses.

const ORIGIN = 'https://piers.qa';
// Per-visitor counts listed for a day on /stats before the rest collapse into
// '+N more'. The JSON carries every one.
const SHOWN = 20;

async function sha256(text) {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('');
}

// IPv4 counts by address, IPv6 by its /64. Windows and phones reach the web
// from temporary IPv6 addresses that rotate inside the /64 they were given, so
// counting whole addresses split one PC into several visitors in a day - found
// when a test from the same machine added a unique instead of bumping its row.
function visitorKey(ip) {
  if (ip.includes('.')) return ip.slice(ip.lastIndexOf(':') + 1);   // IPv4, or IPv4-mapped IPv6
  if (!ip.includes(':')) return ip;
  const [head, tail] = ip.split('::');
  const h = head ? head.split(':') : [];
  const t = tail ? tail.split(':') : [];
  const groups = tail === undefined ? h : [...h, ...Array(8 - h.length - t.length).fill('0'), ...t];
  return groups.slice(0, 4).map(g => parseInt(g, 16).toString(16)).join(':') + '::/64';
}

async function stats(env) {
  // One row is one visitor-day, so reading them all stays small at this scale.
  const { results } = await env.DB.prepare(
    'SELECT day, hits FROM hits ORDER BY day DESC, hits DESC'
  ).all();
  const days = [];
  for (const r of results) {
    let d = days[days.length - 1];
    if (!d || d.day !== r.day) days.push(d = { day: r.day, uniques: 0, hits: 0, per_visitor: [] });
    d.uniques += 1;
    d.hits += r.hits;
    d.per_visitor.push(r.hits);
  }
  return days;
}

// Every value interpolated here is a count or a date the Worker wrote itself,
// so nothing needs escaping.
function page(days) {
  const rows = days.map(d => {
    const more = d.per_visitor.length > SHOWN ? ' +' + (d.per_visitor.length - SHOWN) + ' more' : '';
    return '<tr><td>' + d.day + '</td><td>' + d.uniques + '</td><td>' + d.hits + '</td><td>'
      + d.per_visitor.slice(0, SHOWN).join(', ') + more + '</td></tr>';
  }).join('') || '<tr><td colspan="4">No visits yet</td></tr>';
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>Krill visitors</title>
<style>
body{margin:0;padding-block:32px;padding-inline:16px;background:#060d16;color:#e9eff6;font:15px/1.5 ui-monospace,Consolas,monospace}
main{max-width:760px;margin:0 auto}
h1{font-size:18px;margin:0 0 6px}
p{color:#92a6bc;margin:0 0 24px}
a{color:#ff7a52}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%}
th,td{text-align:left;padding:8px 16px 8px 0;border-bottom:1px solid #1b2d42;white-space:nowrap;vertical-align:top}
th{color:#92a6bc;font-weight:400}
th:nth-child(2),th:nth-child(3),td:nth-child(2),td:nth-child(3){text-align:right}
td:last-child{white-space:normal;color:#92a6bc}
</style>
</head>
<body>
<main>
<h1>piers.qa/krill visitors</h1>
<p>Per UTC day. A visitor is one IPv4 address, or one IPv6 /64 block, since devices rotate IPv6 addresses within it. Hits are page loads, and hits per visitor lists each visitor's count that day, busiest first. <a href="/stats.json">JSON</a></p>
<div class="scroll"><table>
<thead><tr><th>Day</th><th>Unique</th><th>Hits</th><th>Hits per visitor</th></tr></thead>
<tbody>${rows}</tbody>
</table></div>
</main>
</body>
</html>`;
}

export default {
  async fetch(req, env) {
    const { pathname } = new URL(req.url);

    if (pathname === '/hit' && req.method === 'POST') {
      // Browsers always send Origin on a cross-origin POST, so this keeps out
      // other sites and local file:// previews of the build. It does not stop a
      // hand-made request, which is fine for a counter.
      if (req.headers.get('Origin') !== ORIGIN) return new Response(null, { status: 403 });
      if (!env.SALT) return new Response('SALT is not set', { status: 500 });
      const day = new Date().toISOString().slice(0, 10);
      const key = visitorKey(req.headers.get('CF-Connecting-IP') || '');
      // The primary key keeps a visitor to one row a day; a repeat bumps hits.
      await env.DB.prepare(
        'INSERT INTO hits (day, visitor) VALUES (?, ?) '
        + 'ON CONFLICT (day, visitor) DO UPDATE SET hits = hits + 1'
      ).bind(day, await sha256(day + '|' + key + '|' + env.SALT)).run();
      return new Response(null, { status: 204 });
    }

    if (req.method === 'GET' && (pathname === '/stats' || pathname === '/stats.json')) {
      const days = await stats(env);
      const headers = { 'Cache-Control': 'no-store' };
      if (pathname === '/stats.json') return Response.json(days, { headers });
      return new Response(page(days), { headers: { ...headers, 'Content-Type': 'text/html; charset=utf-8' } });
    }

    return new Response('Not found', { status: 404 });
  },
};
