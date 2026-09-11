// Unique visitors per day for piers.qa/krill. Every full page sends a beacon to
// /hit, and the Worker records the visitor once per UTC day. Counting a day's
// rows gives its unique IPs; /stats does that for every day.
//
// Raw IPs are never stored, only a SHA-256 of date + IP + a secret salt. The
// date in the hash means the same visitor on two days cannot be linked, and the
// salt stops anyone reversing it by hashing all four billion IPv4 addresses -
// which is also why a missing salt fails the request rather than hashing
// without one.

const ORIGIN = 'https://piers.qa';

async function sha256(text) {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('');
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
      const ip = req.headers.get('CF-Connecting-IP') || '';
      await env.DB.prepare('INSERT OR IGNORE INTO hits (day, visitor) VALUES (?, ?)')
        .bind(day, await sha256(day + '|' + ip + '|' + env.SALT))
        .run();
      return new Response(null, { status: 204 });
    }

    if (pathname === '/stats' && req.method === 'GET') {
      const { results } = await env.DB.prepare(
        'SELECT day, COUNT(*) AS uniques FROM hits GROUP BY day ORDER BY day DESC'
      ).all();
      return Response.json(results, { headers: { 'Cache-Control': 'no-store' } });
    }

    return new Response('Not found', { status: 404 });
  },
};
