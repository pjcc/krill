// Visitors per day for piers.qa/krill. Every full page sends a beacon to /hit,
// and the Worker keeps one row per visitor per UTC day, counting that visitor's
// hits. /stats.json gives unique visitors, total hits and hits per visitor for
// each day; the page that shows them is https://piers.qa/krill/stats/, built
// by build.py and served by GitHub Pages with the rest of the site.
//
// Raw IPs are never stored, only a SHA-256 of date + visitor key + a secret
// salt. The date in the hash means the same visitor on two days cannot be
// linked, and the salt stops anyone reversing it by hashing all four billion
// IPv4 addresses - which is also why a missing salt fails the request rather
// than hashing without one. So hits per visitor is a list of counts, not of
// addresses.

const ORIGIN = 'https://piers.qa';
const STATS_PAGE = 'https://piers.qa/krill/stats/';

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

    if (pathname === '/stats.json' && req.method === 'GET') {
      // The stats page on piers.qa reads this from the browser, so that origin
      // needs CORS. The counts are public anyway; the header only decides which
      // pages may read them in script.
      return Response.json(await stats(env), {
        headers: { 'Cache-Control': 'no-store', 'Access-Control-Allow-Origin': ORIGIN, 'Vary': 'Origin' },
      });
    }

    // The table used to be served here; it moved to the site.
    if (pathname === '/stats') return Response.redirect(STATS_PAGE, 301);

    return new Response('Not found', { status: 404 });
  },
};
