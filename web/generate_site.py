"""Static HTML site generator — the read-only web archive companion to
the Telegram feed (per user request, V4). Regenerated from scratch out
of the full database on every crawl cycle (see news-crawl.yml, which
deploys the result to GitHub Pages), so there is no incremental state
to get out of sync: `site/` is always a pure function of `data/news.db`.

Deliberately has zero network/Telegram dependency, so it can also be
run locally (`python -m web.generate_site`) to preview the archive
against whatever `data/news.db` already exists.
"""

import json
import shutil
from collections import defaultdict
from datetime import date, datetime
from html import escape
from pathlib import Path
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from config import config
from crawlers import CRAWLER_CLASSES
from database import Database
from telegram import _icon_for
from web.issues import Issue, top_issues

SITE_DIR = Path(__file__).resolve().parent.parent / "site"

# Same display order as the Telegram digest (spec: config order, not
# time-sorted) — a source not in CRAWLER_CLASSES (shouldn't happen,
# but a DB from an older/newer config could have one) is appended
# after, alphabetically, rather than silently dropped.
_SOURCE_ORDER = [cls.source_name for cls in CRAWLER_CLASSES]

# Deep, muted jewel tones rather than bright flat/primary colors — a
# row of 6-7 saturated hues side by side (the first cut of this
# palette) read as loud/carnival rather than professional. Lower
# saturation + darker value keeps each source distinguishable while
# sitting quietly next to its neighbors. One per source, picked by a
# deterministic hash (same trick as telegram._icon_for) rather than
# list position, so a source keeps its color even if CRAWLER_CLASSES
# gets reordered.
_ACCENT_PALETTE = [
    "#8c3a2b", "#8a6a1f", "#2b5a8c", "#2f6b4f", "#5b4a8a",
    "#8a4a2f", "#2f6b66", "#8a3a5a", "#2f5566", "#5c6b2f",
]


def _accent_for(source: str) -> str:
    return _ACCENT_PALETTE[sum(map(ord, source)) % len(_ACCENT_PALETTE)]


# How many date tabs sit in the always-visible horizontal strip (spec:
# "7 tab trải ngang" — spread edge-to-edge, no horizontal scrolling for
# the common case). Older dates beyond this window are still reachable
# through the "Ngày khác" picker rendered alongside the strip.
TAB_WINDOW_SIZE = 7


def _tab_window(all_dates: List[date], day: date, size: int = TAB_WINDOW_SIZE) -> List[date]:
    """Up to `size` dates centered on `day` (all_dates is newest-first),
    clamped to the available range — e.g. viewing the oldest day still
    fills the strip with the `size` oldest dates rather than a lopsided
    handful trailing off on one side."""
    if len(all_dates) <= size:
        return all_dates
    idx = all_dates.index(day)
    start = max(0, idx - size // 2)
    start = min(start, len(all_dates) - size)
    return all_dates[start : start + size]


# Editorial-masthead-meets-neo-brutalist look: flat ink borders and a
# hard offset shadow (no blur, no gradients) instead of the soft
# pastel-glass "AI bento dashboard" look this kind of layout usually
# gets — deliberately picked to not look like every other template.
STYLE = """
@import url('https://fonts.googleapis.com/css2?family=Archivo+Black&family=IBM+Plex+Mono:wght@500;700&display=swap');
:root{
  color-scheme:light dark;
  --bg:#f4f0e6;--fg:#18140f;--muted:#6b6255;--ink:#18140f;--card:#fffdf8;
  --accent:#e63f2e;
  --shadow:4px 4px 0 var(--ink);
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#141210;--fg:#f2ece0;--muted:#a89f8f;--ink:#f2ece0;--card:#1e1b17;
    --accent:#ff6a52;
    --shadow:4px 4px 0 var(--ink);
  }
}
*{box-sizing:border-box;}
body{margin:0;background:var(--bg);color:var(--fg);font-family:-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;line-height:1.5;}
header{padding:32px 16px 20px;text-align:center;border-bottom:3px solid var(--ink);}
header h1{margin:0 0 8px;font-family:"Archivo Black",Impact,sans-serif;font-weight:400;
  font-size:clamp(1.6rem,5vw,2.4rem);letter-spacing:.02em;text-transform:uppercase;color:var(--fg);}
header h1 .dot{color:var(--accent);}
.subtitle{margin:0;color:var(--muted);font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:.8rem;
  text-transform:uppercase;letter-spacing:.03em;}
.scan{margin-top:14px;}
.scan button{font:inherit;font-weight:700;font-size:.82rem;color:var(--fg);background:var(--card);
  border:2px solid var(--ink);box-shadow:3px 3px 0 var(--ink);padding:8px 18px;cursor:pointer;}
.scan button:hover{background:var(--bg);}
.scan button:active,.scan button:disabled{box-shadow:none;transform:translate(3px,3px);}
.scan button:disabled{cursor:wait;opacity:.7;}
.scan .status{display:block;margin-top:8px;font-family:"IBM Plex Mono",ui-monospace,monospace;
  font-size:.75rem;color:var(--muted);min-height:1.2em;}
nav.dates{position:sticky;top:0;z-index:10;background:var(--bg);border-bottom:3px solid var(--ink);}
nav.dates .strip{display:flex;max-width:1200px;margin:0 auto;}
nav.dates a{flex:1 1 0;text-align:center;padding:12px 4px;text-decoration:none;color:var(--fg);
  font-family:"IBM Plex Mono",ui-monospace,monospace;font-weight:700;font-size:.78rem;
  border-right:2px solid var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
nav.dates a:last-child{border-right:none;}
nav.dates a:hover{background:var(--card);}
nav.dates a.active{background:var(--ink);color:var(--bg);}
nav.picker{display:flex;justify-content:center;padding:8px 16px;gap:8px;align-items:center;
  font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:.75rem;color:var(--muted);}
nav.picker select{font:inherit;color:var(--fg);background:var(--card);border:2px solid var(--ink);
  border-radius:0;padding:4px 8px;}
details.trending{max-width:1200px;margin:24px auto 0;padding:0 16px 20px;}
details.trending summary{display:flex;align-items:center;gap:10px;cursor:pointer;list-style:none;
  user-select:none;padding:14px 16px;background:var(--card);border:2px solid var(--ink);
  box-shadow:var(--shadow);font-weight:800;font-size:1.02rem;text-transform:uppercase;letter-spacing:.02em;}
details.trending summary::-webkit-details-marker{display:none;}
details.trending summary .chevron{margin-left:auto;font-size:.8rem;color:var(--muted);
  transition:transform .15s ease;}
details.trending[open] summary .chevron{transform:rotate(180deg);}
details.trending[open] summary{margin-bottom:14px;}
.trending-note{max-width:1200px;margin:0 0 14px;color:var(--muted);font-size:.78rem;font-style:italic;}
.trend-grid{display:flex;flex-direction:column;gap:10px;}
details.issue-card{background:var(--card);border:2px solid var(--ink);box-shadow:var(--shadow);}
details.issue-card>summary{display:flex;gap:14px;align-items:flex-start;padding:12px 16px;
  cursor:pointer;list-style:none;user-select:none;}
details.issue-card>summary::-webkit-details-marker{display:none;}
details.issue-card .chevron{margin-left:auto;font-size:.75rem;color:var(--muted);flex:0 0 auto;
  transition:transform .15s ease;padding-top:.3em;}
details.issue-card[open] .chevron{transform:rotate(180deg);}
.trend-rank{font-weight:900;font-size:1.5rem;color:var(--accent);flex:0 0 auto;line-height:1.2;}
.trend-body{flex:1 1 auto;min-width:0;}
.trend-label{font-weight:700;font-size:1rem;margin-bottom:2px;}
.trend-meta{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:.72rem;color:var(--muted);margin-bottom:6px;}
.why-hot{list-style:none;margin:0 0 6px;padding:0;}
.why-hot li{font-size:.82rem;padding:1px 0;}
.why-hot li::before{content:"→ ";color:var(--accent);}
.trend-links{list-style:none;margin:0;padding:0;}
.trend-links li{font-size:.85rem;padding:2px 0;}
.trend-links a{color:var(--fg);text-decoration:none;}
.trend-links a:hover{color:var(--accent);text-decoration:underline;}
.trend-links .src{color:var(--muted);font-size:.75rem;}
.issue-detail{padding:0 16px 14px 16px;border-top:1px dashed var(--muted);margin-top:8px;}
.issue-timing{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:.72rem;color:var(--muted);
  padding:10px 0 8px;}
.issue-sources{font-size:.8rem;color:var(--muted);margin:0 0 10px;}
main{margin:0;padding:24px 16px 40px;display:flex;align-items:flex-start;gap:18px;overflow-x:auto;}
details.source{flex:0 0 300px;background:var(--card);border:2px solid var(--ink);box-shadow:var(--shadow);
  border-top:5px solid var(--src-color,var(--accent));}
details.source summary{display:flex;align-items:center;gap:10px;padding:12px 14px;cursor:pointer;
  font-size:.95rem;font-weight:700;color:var(--fg);background:var(--card);
  border-bottom:1px solid var(--muted);list-style:none;user-select:none;}
details.source[open] summary{border-bottom-color:var(--ink);}
details.source summary::-webkit-details-marker{display:none;}
details.source summary .icon{display:inline-flex;align-items:center;justify-content:center;
  width:28px;height:28px;flex:0 0 28px;font-size:1.05rem;background:var(--src-color,var(--accent));
  color:#fff;border-radius:6px;}
details.source summary .count{margin-left:auto;font-family:"IBM Plex Mono",ui-monospace,monospace;
  font-weight:700;font-size:.72rem;color:var(--muted);border:1px solid var(--muted);padding:2px 8px;}
details.source summary .chevron{font-size:.7rem;color:var(--muted);transition:transform .15s ease;}
details.source[open] summary .chevron{transform:rotate(180deg);}
details.source .list-wrap{max-height:min(65vh,600px);overflow-y:auto;padding:6px 14px 4px;}
details.source ul{list-style:none;margin:0;padding:0;}
details.source li{display:flex;gap:10px;padding:9px 0;border-bottom:1px dashed var(--muted);}
details.source li:last-child{border-bottom:none;}
details.source a{color:var(--fg);text-decoration:none;font-size:.93rem;line-height:1.4;}
details.source a:hover{color:var(--accent);text-decoration:underline;}
.time{color:var(--muted);font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:.72rem;
  white-space:nowrap;padding-top:2px;}
.empty{flex:1 1 auto;text-align:center;color:var(--muted);padding:60px 0;}
footer{text-align:center;color:var(--muted);font-family:"IBM Plex Mono",ui-monospace,monospace;
  font-size:.72rem;padding:16px 16px 40px;text-transform:uppercase;letter-spacing:.04em;}
""".strip()


def _display_date(article: dict) -> date:
    """The calendar date an article is filed under: its own published_at
    when the source provides one, else the date it was first crawled
    (first_seen_at is always present) — never left ungrouped."""
    dt: datetime = article["published_at"] or article["first_seen_at"]
    return dt.date()


def _sort_key(article: dict) -> datetime:
    return article["published_at"] or article["first_seen_at"]


def group_by_date_and_source(articles: List[dict]) -> Dict[date, Dict[str, List[dict]]]:
    by_date: Dict[date, Dict[str, List[dict]]] = defaultdict(lambda: defaultdict(list))
    for article in articles:
        by_date[_display_date(article)][article["source"]].append(article)
    for sources in by_date.values():
        for items in sources.values():
            items.sort(key=_sort_key, reverse=True)  # newest first within a source
    return by_date


def _ordered_sources(sources_present) -> List[str]:
    ordered = [s for s in _SOURCE_ORDER if s in sources_present]
    extra = sorted(s for s in sources_present if s not in _SOURCE_ORDER)
    return ordered + extra


def _time_label(article: dict) -> str:
    if article["published_at"] is None:
        return "--:--"
    return article["published_at"].strftime("%H:%M")


def _scan_button_html() -> str:
    """The "Quét ngay" button, present only when NEWS_SCAN_WORKER_URL is
    configured (see config.py / web/cloudflare-worker/). Without a
    Worker deployed, there is nothing safe for the button to call, so
    it's simply omitted rather than shown broken.

    The Worker holds the GitHub token server-side — see
    web/cloudflare-worker/worker.js's docstring for why a token that
    can trigger a crawl must never be embedded in this (public) page.
    """
    if not config.scan_worker_url:
        return ""
    worker_url = json.dumps(config.scan_worker_url)  # safe JS string literal
    return f"""<div class="scan">
<button type="button" onclick="triggerScan(this)">🔄 Quét ngay</button>
<span class="status" id="scan-status"></span>
</div>
<script>
function triggerScan(btn) {{
  var status = document.getElementById('scan-status');
  btn.disabled = true;
  status.textContent = 'Đang gửi yêu cầu...';
  fetch({worker_url}, {{ method: 'POST' }})
    .then(function(r) {{ return r.json().catch(function() {{ return {{}}; }}).then(function(data) {{ return {{ok: r.ok, status: r.status, data: data}}; }}); }})
    .then(function(res) {{
      if (res.ok) {{ status.textContent = '✅ ' + (res.data.message || 'Đã kích hoạt.'); }}
      else {{ status.textContent = (res.status === 429 ? '⏳ ' : '❌ ') + (res.data.message || ('Lỗi ' + res.status)); }}
    }})
    .catch(function() {{ status.textContent = '❌ Không kết nối được tới worker.'; }})
    .finally(function() {{ setTimeout(function() {{ btn.disabled = false; }}, 5000); }});
}}
</script>"""


def _issue_links_html(articles: List[dict]) -> str:
    return "".join(
        f'<li><a href="{escape(a["url"])}" target="_blank" rel="noopener">{escape(a["title"])}</a> '
        f'<span class="src">({escape(a["source"])})</span></li>'
        for a in articles
    )


def _issue_card_html(rank: int, issue: Issue) -> str:
    why_hot = "".join(f"<li>{escape(b)}</li>" for b in issue.why_hot)
    top_links = _issue_links_html(issue.representative_articles)

    # The full article list + exact timing/source breakdown is only
    # worth its own expand toggle when there's more to see than the
    # (already-shown) top 3 — spec section 12's "click vào Issue để
    # xem toàn bộ bài liên quan".
    detail_html = ""
    if issue.article_count > len(issue.representative_articles):
        all_links = _issue_links_html(issue.all_articles)
        detail_html = (
            '<div class="issue-detail">'
            f'<div class="issue-timing">Lần đầu: {issue.first_seen_at.strftime("%H:%M")}'
            f' · Cập nhật gần nhất: {issue.last_seen_at.strftime("%H:%M")}</div>'
            f'<div class="issue-sources">Nguồn: {escape(", ".join(issue.sources))}</div>'
            f'<ul class="trend-links">{all_links}</ul></div>'
        )

    return (
        f'<details class="issue-card"><summary><span class="trend-rank">#{rank}</span>'
        f'<div class="trend-body"><div class="trend-label">{escape(issue.issue_title)}</div>'
        f'<div class="trend-meta">🔥 {issue.hot_score:.0f} điểm · {issue.article_count} bài'
        f' · {issue.unique_source_count} nguồn</div>'
        f'<ul class="why-hot">{why_hot}</ul>'
        f'<ul class="trend-links">{top_links}</ul></div>'
        f'<span class="chevron">▾</span></summary>{detail_html}</details>'
    )


def _trending_panel_html(issues: List[Issue]) -> str:
    """The "🔥 Top 5 Issues hôm nay" panel — only rendered on the latest
    day's page (see build_site), since it is scored against *today*
    (Asia/Ho_Chi_Minh) and would be meaningless attached to an older
    archive day's page. Omitted entirely when nothing currently clears
    the issue thresholds (see web/issues.py) rather than shown empty."""
    if not issues:
        return ""
    cards = "".join(_issue_card_html(rank, issue) for rank, issue in enumerate(issues, start=1))
    return (
        '<details class="trending" open>'
        '<summary>🔥 Top 5 Issues hôm nay<span class="chevron">▾</span></summary>'
        '<p class="trending-note">Trong phạm vi các nguồn báo mà hệ thống đang theo dõi — '
        'không phải xếp hạng mức độ quan trọng khách quan.</p>'
        f'<div class="trend-grid">{cards}</div></details>'
    )


def render_day_page(
    day: date,
    sources: Dict[str, List[dict]],
    all_dates: List[date],
    trending: Optional[List[Issue]] = None,
) -> str:
    window = _tab_window(all_dates, day)
    tab_items = []
    for d in window:
        cls = ' class="active"' if d == day else ""
        # dd/mm on its own line reads better than dd/mm/yyyy in a narrow
        # equal-width tab; the year is redundant for a 7-day strip anyway.
        tab_items.append(f'<a href="{d.isoformat()}.html"{cls}>{d.strftime("%d/%m")}</a>')
    tabs_html = "".join(tab_items)

    picker_html = ""
    if len(all_dates) > len(window):
        options = "".join(
            f'<option value="{d.isoformat()}.html"{" selected" if d == day else ""}>{d.strftime("%d/%m/%Y")}</option>'
            for d in all_dates
        )
        picker_html = (
            '<nav class="picker">Ngày khác: '
            f'<select onchange="location.href=this.value">{options}</select></nav>'
        )

    total = sum(len(items) for items in sources.values())

    sections = []
    for source in _ordered_sources(sources.keys()):
        items = sources[source]
        rows = "".join(
            f'<li><span class="time">{_time_label(a)}</span>'
            f'<a href="{escape(a["url"])}" target="_blank" rel="noopener">{escape(a["title"])}</a></li>'
            for a in items
        )
        # <details>/<summary> gives per-source collapse/expand for free,
        # no JS needed — clicking the colored header bar toggles it.
        # `open` by default so the page reads the same as before until
        # the user chooses to close a source they don't care about.
        sections.append(
            f'<details class="source" open style="--src-color:{_accent_for(source)}">'
            f'<summary><span class="icon">{_icon_for(source)}</span>{escape(source)}'
            f'<span class="count">{len(items)}</span><span class="chevron">▾</span></summary>'
            f'<div class="list-wrap"><ul>{rows}</ul></div></details>'
        )
    body_html = "".join(sections) if sections else '<p class="empty">Không có bài nào.</p>'

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vietnam News Monitor — {day.strftime('%d/%m/%Y')}</title>
<style>{STYLE}</style>
</head>
<body>
<header>
<h1>Vietnam News<span class="dot">.</span>Monitor</h1>
<p class="subtitle">Số ra ngày {day.strftime('%d/%m/%Y')} · {total} bài · {len(sources)} nguồn</p>
{_scan_button_html()}
</header>
<nav class="dates">
<div class="strip">{tabs_html}</div>
{picker_html}
</nav>
<main>{body_html}</main>
{_trending_panel_html(trending or [])}
<footer><p>Tự động cập nhật mỗi {config.crawl_interval_minutes} phút qua GitHub Actions.</p></footer>
</body>
</html>
"""


def build_site(db: Database, out_dir: Path = SITE_DIR) -> None:
    articles = db.get_all_articles()
    by_date = group_by_date_and_source(articles)
    all_dates = sorted(by_date.keys(), reverse=True)

    # Computed once against wall-clock "now" (not tied to any one
    # archive day), scoped to *today* only (spec section 9), and only
    # ever shown on the latest day's page — see _trending_panel_html's
    # docstring for why.
    now = datetime.now(ZoneInfo(config.timezone))
    trending = top_issues(articles, now)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    latest = all_dates[0] if all_dates else date.today()
    for day in all_dates:
        (out_dir / f"{day.isoformat()}.html").write_text(
            render_day_page(day, by_date[day], all_dates, trending=(trending if day == latest else None)),
            encoding="utf-8",
        )

    latest_sources = by_date.get(latest, {})
    (out_dir / "index.html").write_text(
        render_day_page(latest, latest_sources, all_dates, trending=trending), encoding="utf-8"
    )

    # Tells GitHub Pages not to run this through Jekyll (irrelevant here
    # since no filenames start with "_", but it's the standard marker
    # and costs nothing to include).
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")


def main() -> None:
    db = Database(config.db_path, config.timezone)
    build_site(db)
    html_files = list(SITE_DIR.glob("*.html"))
    print(f"Site generated at {SITE_DIR} ({len(html_files)} HTML file(s)).")


if __name__ == "__main__":
    main()
