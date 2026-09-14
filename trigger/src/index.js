// Fires the krill deploy workflow on a schedule Cloudflare actually keeps.
//
// GitHub's own cron is best-effort and this repo gets throttled hard: the
// workflow asks for 36 scheduled triggers a day (every 15 minutes, 04:00-12:00
// UTC) and GitHub created one of them on 2026-09-14, at 09:46 - 5h46m after the
// 04:00 puzzle roll. The site sat a day behind all morning, every morning, and
// the lag was growing (+4h36m on the 12th, +5h27m on the 13th, +5h48m on the
// 14th). Nothing in the workflow can fix that; the trigger has to come from
// outside GitHub. Cloudflare cron fires to the minute.
//
// This does not replace deploy.yml's schedule, which stays as the long-tail
// fallback for a dead token or a broken Worker - late is better than never, and
// that is exactly what it delivers today.
//
// The workflow is idempotent by design: fetch.py skips the pull when
// data/<date>.json already exists, and a scheduled run that finds the day
// captured neither commits nor deploys. So a redundant dispatch is harmless -
// the capture check below only exists to keep the Actions log readable.

const REPO = 'pjcc/krill';
const WORKFLOW = 'deploy.yml';
const API = 'https://api.github.com';
// GitHub rejects an API request with no User-Agent.
const UA = 'krill-trigger (Cloudflare Worker; https://piers.qa/krill/)';

// The puzzle rolls at 04:00 UTC, so the live day is the UTC date four hours ago.
function liveDay(now) {
  return new Date(now.getTime() - 4 * 3600 * 1000).toISOString().slice(0, 10);
}

// Is this day already in the repo? Checked against raw.githubusercontent rather
// than the site, which sits behind a 10-minute CDN cache. A failure here is not
// fatal: it is better to dispatch a run that turns out to be a no-op than to
// skip the one run that mattered, so anything unexpected answers "not yet".
async function captured(day) {
  const url = `https://raw.githubusercontent.com/${REPO}/main/data/${day}.json`;
  try {
    const r = await fetch(url, { method: 'HEAD', headers: { 'User-Agent': UA } });
    return r.status === 200;
  } catch {
    return false;
  }
}

async function dispatch(env) {
  const r = await fetch(`${API}/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${env.GH_TOKEN}`,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': UA,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ ref: 'main' }),
  });
  // 204 is success and has no body. Anything else is worth reading: a 401 means
  // the token expired or was revoked, a 403 that it lost the Actions scope, and
  // neither shows up anywhere else - the symptom is just a stale site.
  return { ok: r.status === 204, status: r.status, body: r.status === 204 ? '' : (await r.text()).slice(0, 300) };
}

export default {
  async scheduled(event, env, ctx) {
    if (!env.GH_TOKEN) {
      console.log('krill-trigger: GH_TOKEN is not set - run `npx wrangler secret put GH_TOKEN`');
      return;
    }
    const day = liveDay(new Date(event.scheduledTime));
    if (await captured(day)) {
      console.log(`krill-trigger: ${day} already captured, not dispatching`);
      return;
    }
    // One retry: a transient 5xx from the API should not cost the whole slot,
    // and the next cron is 15 minutes away.
    for (let attempt = 1; attempt <= 2; attempt++) {
      const r = await dispatch(env);
      if (r.ok) {
        console.log(`krill-trigger: dispatched for ${day} (attempt ${attempt})`);
        return;
      }
      console.log(`krill-trigger: dispatch for ${day} failed with ${r.status} ${r.body}`);
      if (r.status < 500) return;     // 401/403/404 will not fix themselves
      await new Promise(res => setTimeout(res, 5000));
    }
  },

  // Cron only - no route and no workers.dev subdomain, so nothing should reach
  // this. It exists so a stray request gets an answer rather than an exception.
  async fetch() {
    return new Response('krill-trigger runs on a schedule; it serves nothing.', { status: 404 });
  },
};
