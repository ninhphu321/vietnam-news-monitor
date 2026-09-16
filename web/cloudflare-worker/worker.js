/**
 * Scan-trigger proxy for the "Quét ngay" button on the static site.
 *
 * Why this exists: the site is a static GitHub Pages page with no
 * backend, and triggering a GitHub Actions run requires a token with
 * write access. A token like that can NEVER be embedded in the site's
 * own HTML/JS — anyone visiting the (public) page could read it out of
 * the page source and reuse it. This Worker is the fix: the token
 * lives only here, in Cloudflare's environment (set via `wrangler
 * secret put` or the dashboard's "encrypt" option), and the site's
 * button just calls this public endpoint, which calls GitHub on the
 * site's behalf.
 *
 * Required environment (Worker Settings -> Variables):
 *   GITHUB_TOKEN     (secret)  fine-grained PAT scoped to ONLY this repo,
 *                              permission "Actions: Read and write" — nothing else.
 *   GITHUB_OWNER     (var)     e.g. "ninhphu321"
 *   GITHUB_REPO      (var)     e.g. "vietnam-news-monitor"
 *   GITHUB_WORKFLOW  (var)     workflow filename, e.g. "news-crawl.yml"
 *   GITHUB_BRANCH    (var)     branch to run on, e.g. "main"
 *   ALLOWED_ORIGIN   (var)     the site's origin, e.g. "https://ninhphu321.github.io"
 *   COOLDOWN_SECONDS (var, optional) minimum gap between triggers, default 300
 *
 * Optional: bind a KV namespace as SCAN_COOLDOWN to enforce the
 * cooldown across all visitors (shared, persisted) — the button is on
 * a public page, so without this, anyone could spam-click it and burn
 * through the repo's GitHub Actions minutes. Works fine without KV too
 * (cooldown check is just skipped), it's only the abuse guard.
 */

export default {
  async fetch(request, env) {
    const corsHeaders = {
      "Access-Control-Allow-Origin": env.ALLOWED_ORIGIN || "*",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders });
    }
    if (request.method !== "POST") {
      return json({ message: "Method not allowed" }, 405, corsHeaders);
    }

    const cooldownSeconds = parseInt(env.COOLDOWN_SECONDS || "300", 10);
    const now = Math.floor(Date.now() / 1000);

    if (env.SCAN_COOLDOWN) {
      const last = await env.SCAN_COOLDOWN.get("last_trigger");
      if (last) {
        const elapsed = now - parseInt(last, 10);
        if (elapsed < cooldownSeconds) {
          const waitMin = Math.ceil((cooldownSeconds - elapsed) / 60);
          return json(
            { message: `Vừa quét gần đây, vui lòng đợi thêm khoảng ${waitMin} phút.` },
            429,
            corsHeaders
          );
        }
      }
    }

    const ghResponse = await fetch(
      `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/actions/workflows/${env.GITHUB_WORKFLOW}/dispatches`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${env.GITHUB_TOKEN}`,
          Accept: "application/vnd.github+json",
          "User-Agent": "news-monitor-scan-button",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ ref: env.GITHUB_BRANCH || "main" }),
      }
    );

    // GitHub returns 204 No Content on a successful dispatch.
    if (ghResponse.status === 204) {
      if (env.SCAN_COOLDOWN) {
        await env.SCAN_COOLDOWN.put("last_trigger", String(now));
      }
      return json({ message: "Đã kích hoạt crawl — chờ khoảng 1-2 phút rồi tải lại trang." }, 200, corsHeaders);
    }

    const detail = await ghResponse.text();
    return json({ message: `GitHub API trả lỗi (${ghResponse.status})`, detail }, 502, corsHeaders);
  },
};

function json(body, status, corsHeaders) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}
