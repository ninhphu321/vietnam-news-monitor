"""Static HTML site generator — the read-only web archive companion to
the Telegram feed (per user request, V4). Regenerated from scratch out
of the full database on every crawl cycle (see news-crawl.yml, which
deploys the result to GitHub Pages), so there is no incremental state
to get out of sync: `site/` is always a pure function of `data/news.db`.

Deliberately has zero network/Telegram dependency, so it can also be
run locally (`python -m web.generate_site`) to preview the archive
against whatever `data/news.db` already exists.

UI follows PROJECT design spec v2.0 ("editorial newsroom", not a SaaS
dashboard): Unified News Stream is the default/primary view, Top
Issues sits above it, the old per-source Kanban board survives only as
a secondary "By Source" section, and there is no per-source color or
emoji anywhere (spec: "Never assign different colors to each news
source", "Avoid: Emoji").
"""

import json
import shutil
from collections import Counter, defaultdict
from datetime import date, datetime
from html import escape
from pathlib import Path
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from config import config
from crawlers import CRAWLER_CLASSES
from database import Database
from web.issues import Issue, top_issues

SITE_DIR = Path(__file__).resolve().parent.parent / "site"

# Same display order as the Telegram digest (spec: config order, not
# time-sorted) — a source not in CRAWLER_CLASSES (shouldn't happen,
# but a DB from an older/newer config could have one) is appended
# after, alphabetically, rather than silently dropped.
_SOURCE_ORDER = [cls.source_name for cls in CRAWLER_CLASSES]

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


# Editorial newsroom design system (Financial Times / Reuters / Bloomberg
# reference points, per the v2.0 design spec) — flat neutral surfaces,
# a 1px hairline border and a near-invisible shadow instead of the
# earlier neo-brutalist "hard offset shadow" look. No per-source color,
# no gradients, no emoji, no glassmorphism.
#
# Inter is the primary typeface for all Vietnamese text. Verified via
# Google Fonts' own CSS2 API response before adopting it: it ships a
# dedicated Vietnamese unicode-range subset (U+1EA0-1EF9 etc.), unlike
# "Archivo Black" (used in an earlier revision of this site), which
# had no Vietnamese coverage at all and silently mis-rendered
# diacritics — see README.md's history of that bug.
STYLE = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500;700&display=swap');
:root{
  color-scheme:light;
  --bg:#F5F3EE;
  --surface:#FFFFFF;
  --surface-2:#FAF9F6;

  --text:#111111;
  --text-2:#6B6B6B;
  --muted:#9A978F;

  --border:#DDD9D0;
  --divider:#ECE8E1;

  --accent:#1F4B45;
  --accent-soft:#E8F0EE;
  --live:#C84C3A;

  --radius:16px;
  --shadow:0 1px 2px rgba(0,0,0,.04);
  --sans:"Inter",-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,monospace;
  --header-h:72px;
}
*{box-sizing:border-box;}
html{scroll-behavior:smooth;}
body{margin:0;background:var(--bg);color:var(--text);font-family:var(--sans);line-height:1.55;font-size:14px;}
h2{margin:0;}
a{color:inherit;}

.page{max-width:1320px;margin:0 auto;padding:0 24px;}
@media (max-width:1024px){.page{padding:0 20px;}}
@media (max-width:640px){.page{padding:0 16px;}}

/* ---- Header ---- */
.site-header{position:sticky;top:0;z-index:20;height:var(--header-h);background:var(--surface);
  border-bottom:1px solid var(--border);display:flex;align-items:center;gap:24px;
  max-width:1320px;margin:0 auto;padding:0 24px;}
@media (max-width:1024px){.site-header{padding:0 20px;}}
@media (max-width:640px){.site-header{padding:0 16px;gap:12px;}}
.masthead{font-weight:700;font-size:20px;letter-spacing:.01em;white-space:nowrap;flex:0 0 auto;}
.masthead .dot{color:var(--accent);}
.search-input{flex:1 1 240px;min-width:0;font:inherit;font-size:13px;color:var(--text);
  background:var(--surface-2);border:1px solid var(--border);border-radius:999px;padding:8px 16px;}
.search-input::placeholder{color:var(--muted);}
.main-nav{display:flex;gap:20px;flex:0 0 auto;}
.main-nav a{font-family:var(--mono);font-size:12px;font-weight:500;letter-spacing:.04em;
  text-decoration:none;color:var(--text-2);white-space:nowrap;}
.main-nav a:hover{color:var(--text);}
.header-meta{display:flex;align-items:center;gap:8px;flex:0 0 auto;font-family:var(--mono);
  font-size:11px;font-weight:500;color:var(--text-2);white-space:nowrap;}
.live-dot{width:6px;height:6px;border-radius:50%;background:var(--live);display:inline-block;}
@media (max-width:900px){.main-nav,.header-meta{display:none;}}

/* ---- Scan button (kept from earlier revision; unrelated to design v2.0) ---- */
.scan{flex:0 0 auto;}
.scan button{font:inherit;font-weight:600;font-size:12px;color:var(--text);background:var(--surface);
  border:1px solid var(--border);border-radius:999px;box-shadow:var(--shadow);padding:7px 16px;cursor:pointer;}
.scan button:hover{background:var(--surface-2);}
.scan button:disabled{cursor:wait;opacity:.6;}
.scan .status{display:block;margin-top:4px;font-family:var(--mono);font-size:10px;color:var(--muted);
  position:absolute;white-space:nowrap;}

/* ---- Section scaffolding ---- */
main{padding:32px 0 40px;}
section{scroll-margin-top:calc(var(--header-h) + 12px);margin:0 auto 40px;max-width:1320px;padding:0 24px;}
@media (max-width:1024px){section{padding:0 20px;}}
@media (max-width:640px){section{padding:0 16px;}}
.section-title{font-size:26px;font-weight:650;line-height:1.15;margin-bottom:4px;letter-spacing:-.01em;}
.section-note{color:var(--muted);font-size:12px;font-style:italic;margin:4px 0 16px;}

/* ---- Today overview ---- */
.today-overview .overview-strip{display:flex;flex-wrap:wrap;align-items:baseline;gap:10px;
  margin-top:12px;padding:16px 20px;background:var(--surface);border:1px solid var(--border);
  border-radius:var(--radius);box-shadow:var(--shadow);font-size:14px;color:var(--text-2);}
.overview-strip strong{font-family:var(--mono);font-weight:700;color:var(--text);font-size:15px;}
.dot-sep{color:var(--muted);}

/* ---- Top issues ---- */
.issues-grid{display:grid;grid-template-columns:1fr;gap:12px;margin-top:16px;}
@media (min-width:900px){.issues-grid{grid-template-columns:1fr 1fr;}}
details.issue-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
  box-shadow:var(--shadow);}
details.issue-card>summary{display:flex;gap:14px;align-items:flex-start;padding:18px 20px;
  cursor:pointer;list-style:none;user-select:none;min-height:150px;}
details.issue-card>summary::-webkit-details-marker{display:none;}
/* Clicking an Issue Tag in the news stream jumps to "#issue-{id}" —
   force the detail body visible even without the native [open]
   attribute, so the drill-down works with zero JS. */
details.issue-card:target>*:not(summary){display:block!important;}
.issue-rank{font-family:var(--mono);font-weight:700;font-size:20px;color:var(--muted);flex:0 0 auto;}
.issue-summary{flex:1 1 auto;min-width:0;}
.issue-title-row{display:flex;justify-content:space-between;align-items:baseline;gap:10px;}
.issue-title{font-size:22px;font-weight:650;line-height:1.2;letter-spacing:-.01em;}
.issue-score{flex:0 0 auto;font-family:var(--mono);font-weight:700;font-size:12px;color:var(--accent);
  background:var(--accent-soft);border-radius:999px;padding:3px 10px;white-space:nowrap;}
.issue-stats{font-family:var(--mono);font-size:12px;font-weight:500;color:var(--text-2);margin:6px 0 8px;}
.why-hot-compact{list-style:none;margin:0;padding:0;}
.why-hot-compact li{font-size:13px;color:var(--text-2);padding:1px 0;}
.why-hot-compact li::before{content:"— ";color:var(--muted);}
.issue-detail{padding:0 20px 20px;border-top:1px solid var(--divider);}
.issue-metrics{display:flex;flex-wrap:wrap;gap:20px;padding:16px 0;}
.metric{display:flex;flex-direction:column;gap:2px;}
.metric-label{font-size:11px;color:var(--muted);}
.metric-value{font-family:var(--mono);font-size:16px;font-weight:700;color:var(--text);}
.source-coverage{display:flex;flex-direction:column;gap:8px;padding:8px 0 16px;}
.coverage-row{display:flex;align-items:center;gap:10px;}
.coverage-src{flex:0 0 140px;font-size:12px;color:var(--text-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.coverage-track{flex:1 1 auto;height:6px;background:var(--surface-2);border-radius:999px;overflow:hidden;}
.coverage-fill{height:100%;background:var(--accent);border-radius:999px;}
.coverage-count{flex:0 0 24px;text-align:right;font-family:var(--mono);font-size:12px;color:var(--text-2);}
.related-articles{display:flex;flex-direction:column;}
.related-row{display:flex;align-items:baseline;gap:12px;padding:8px 0;border-top:1px solid var(--divider);font-size:13px;}
.related-row:first-child{border-top:none;}
.related-row .src{font-family:var(--mono);font-size:11px;color:var(--text-2);flex:0 0 120px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.related-row a{flex:1 1 auto;min-width:0;text-decoration:none;color:var(--text);}
.related-row a:hover{color:var(--accent);text-decoration:underline;}

/* ---- Filters ---- */
.filters{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:16px 0;position:sticky;
  top:var(--header-h);z-index:10;background:var(--bg);padding:8px 0;}
.pill-select{font:inherit;font-family:var(--mono);font-size:12px;font-weight:500;color:var(--text);
  background:var(--surface);border:1px solid var(--border);border-radius:999px;padding:7px 14px;cursor:pointer;}
.sort-toggle{display:flex;gap:6px;}
.pill{font:inherit;font-family:var(--mono);font-size:12px;font-weight:500;color:var(--text-2);
  background:var(--surface);border:1px solid var(--border);border-radius:999px;padding:7px 14px;cursor:pointer;}
.pill.active{color:var(--accent);background:var(--accent-soft);border-color:var(--accent-soft);}

/* ---- Pagination (News Stream shows PAGE_SIZE rows at a time) ---- */
.pagination{display:flex;flex-wrap:wrap;align-items:center;justify-content:center;gap:6px;margin:20px 0 4px;}
.page-btn{font:inherit;font-family:var(--mono);font-size:12px;font-weight:500;color:var(--text-2);
  background:var(--surface);border:1px solid var(--border);border-radius:999px;min-width:32px;
  padding:6px 10px;cursor:pointer;}
.page-btn.active{color:var(--accent);background:var(--accent-soft);border-color:var(--accent-soft);}
.page-ellipsis{color:var(--muted);font-family:var(--mono);font-size:12px;padding:0 2px;}

/* ---- Unified news stream ---- */
.news-stream-list{display:flex;flex-direction:column;}
.news-row{display:flex;align-items:center;gap:16px;min-height:64px;padding:8px 0;border-bottom:1px solid var(--divider);}
.news-row .ts{flex:0 0 44px;font-family:var(--mono);font-size:11px;font-weight:500;color:var(--muted);}
.news-row .src{flex:0 0 150px;font-family:var(--mono);font-size:12px;font-weight:500;color:var(--text-2);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.news-row .headline{flex:1 1 auto;min-width:0;font-size:16px;font-weight:500;line-height:1.35;
  text-decoration:none;color:var(--text);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}
.news-row .headline:hover{color:var(--accent);}
.news-row:hover{background:var(--surface-2);}
.news-row .issue-tag{flex:0 0 auto;max-width:200px;font-family:var(--mono);font-size:11px;font-weight:500;
  color:var(--accent);background:var(--accent-soft);border-radius:999px;padding:3px 10px;
  text-decoration:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
@media (max-width:640px){
  .news-row .src{flex-basis:90px;}
  .news-row .issue-tag{display:none;}
}

/* ---- By source (secondary Kanban view) ---- */
.source-board{display:flex;align-items:flex-start;gap:16px;overflow-x:auto;margin-top:16px;}
@media (max-width:900px){.source-board{flex-direction:column;overflow-x:visible;}}
details.source-col{flex:0 0 300px;background:var(--surface);border:1px solid var(--border);
  border-radius:var(--radius);box-shadow:var(--shadow);}
@media (max-width:900px){details.source-col{flex-basis:auto;width:100%;}}
details.source-col>summary{display:flex;align-items:center;gap:10px;padding:12px 16px;cursor:pointer;
  font-size:14px;font-weight:600;color:var(--text);border-bottom:1px solid var(--divider);
  list-style:none;user-select:none;}
details.source-col>summary::-webkit-details-marker{display:none;}
details.source-col .count{margin-left:auto;font-family:var(--mono);font-weight:500;font-size:11px;
  color:var(--text-2);border:1px solid var(--border);border-radius:999px;padding:2px 9px;}
details.source-col .chevron{font-size:10px;color:var(--muted);transition:transform .15s ease;}
details.source-col[open] .chevron{transform:rotate(180deg);}
.source-list-wrap{max-height:min(65vh,600px);overflow-y:auto;padding:4px 16px;}
.source-list-wrap ul{list-style:none;margin:0;padding:0;}
.source-list-wrap li{display:flex;gap:10px;padding:9px 0;border-bottom:1px solid var(--divider);}
.source-list-wrap li:last-child{border-bottom:none;}
.source-list-wrap a{color:var(--text);text-decoration:none;font-size:13px;line-height:1.4;}
.source-list-wrap a:hover{color:var(--accent);text-decoration:underline;}
.source-list-wrap .time{color:var(--muted);font-family:var(--mono);font-size:11px;white-space:nowrap;padding-top:2px;}

/* ---- Archive ---- */
.date-tabs{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px;}
.date-tabs a{font-family:var(--mono);font-size:12px;font-weight:500;text-decoration:none;color:var(--text-2);
  background:var(--surface);border:1px solid var(--border);border-radius:999px;padding:6px 14px;}
.date-tabs a:hover{color:var(--text);}
.date-tabs a.active{color:var(--accent);background:var(--accent-soft);border-color:var(--accent-soft);}
.date-picker{margin-top:10px;font-family:var(--mono);font-size:12px;color:var(--muted);}
.date-picker select{font:inherit;color:var(--text);background:var(--surface);border:1px solid var(--border);
  border-radius:999px;padding:5px 12px;}

.empty{text-align:center;color:var(--muted);padding:60px 0;}
footer{text-align:center;color:var(--muted);font-family:var(--mono);font-size:11px;padding:16px 16px 40px;}
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
<button type="button" onclick="triggerScan(this)">Quét ngay</button>
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
      if (res.ok) {{ status.textContent = res.data.message || 'Đã kích hoạt.'; }}
      else {{ status.textContent = res.data.message || ('Lỗi ' + res.status); }}
    }})
    .catch(function() {{ status.textContent = 'Không kết nối được tới worker.'; }})
    .finally(function() {{ setTimeout(function() {{ btn.disabled = false; }}, 5000); }});
}}
</script>"""


def _issue_lookup(issues: List[Issue]) -> Dict[str, Issue]:
    """Map article URL -> the Issue it belongs to, so the Unified News
    Stream can tag each row (spec: "Issue Tag" column, and clicking it
    jumps to that Issue's detail card) and the Issue filter dropdown can
    select exactly those rows."""
    lookup: Dict[str, Issue] = {}
    for issue in issues:
        for a in issue.all_articles:
            lookup[a["url"]] = issue
    return lookup


def _news_row_html(article: dict, issue_lookup: Dict[str, Issue]) -> str:
    issue = issue_lookup.get(article["url"])
    issue_id = escape(issue.issue_id) if issue else ""
    hot = f"{issue.hot_score:.1f}" if issue else "0"
    ts = _sort_key(article)
    tag_html = ""
    if issue is not None:
        tag_html = f'<a class="issue-tag" href="#issue-{issue_id}">{escape(issue.issue_title)}</a>'
    return (
        f'<div class="news-row" data-source="{escape(article["source"])}" '
        f'data-issue="{issue_id}" data-hot="{hot}" data-ts="{int(ts.timestamp())}">'
        f'<span class="ts">{_time_label(article)}</span>'
        f'<span class="src">{escape(article["source"])}</span>'
        f'<a class="headline" href="{escape(article["url"])}" target="_blank" rel="noopener">{escape(article["title"])}</a>'
        f'{tag_html}</div>'
    )


def _news_stream_html(articles: List[dict], issue_lookup: Dict[str, Issue]) -> str:
    if not articles:
        return '<p class="empty">Không có bài nào.</p>'
    ordered = sorted(articles, key=_sort_key, reverse=True)
    return "".join(_news_row_html(a, issue_lookup) for a in ordered)


def _filters_html(sources_present: List[str], issues: List[Issue]) -> str:
    source_options = "".join(f'<option value="{escape(s)}">{escape(s)}</option>' for s in sources_present)
    issue_options = "".join(
        f'<option value="{escape(i.issue_id)}">{escape(i.issue_title)}</option>' for i in issues
    )
    return f"""<div class="filters">
<select class="pill-select" id="filter-source" onchange="applyFilters()"><option value="">Tất cả nguồn</option>{source_options}</select>
<select class="pill-select" id="filter-issue" onchange="applyFilters()"><option value="">Tất cả issue</option>{issue_options}</select>
<div class="sort-toggle">
<button type="button" class="pill active" data-sort="newest" onclick="setSort(this,'newest')">Mới nhất</button>
<button type="button" class="pill" data-sort="trending" onclick="setSort(this,'trending')">Đang hot</button>
</div>
</div>"""


def _source_coverage_html(issue: Issue) -> str:
    """Horizontal bars, one per source, width relative to that source's
    share of the issue's articles (spec section "Issue Detail": "Source
    Coverage uses horizontal bars. Avoid pie charts.")."""
    counts = Counter(a["source"] for a in issue.all_articles)
    if not counts:
        return ""
    max_count = max(counts.values())
    ordered = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    rows = "".join(
        f'<div class="coverage-row"><span class="coverage-src">{escape(src)}</span>'
        f'<div class="coverage-track"><div class="coverage-fill" style="width:{count / max_count * 100:.0f}%"></div></div>'
        f'<span class="coverage-count">{count}</span></div>'
        for src, count in ordered
    )
    return f'<div class="source-coverage">{rows}</div>'


def _related_articles_html(articles: List[dict]) -> str:
    # Issue.all_articles entries are the lightweight {title, url, source}
    # shape built in web/issues.py — no timestamp per article (the
    # issue-level first/last-seen times are shown once in the metrics
    # row instead, see _issue_card_html).
    return "".join(
        f'<div class="related-row"><span class="src">{escape(a["source"])}</span>'
        f'<a href="{escape(a["url"])}" target="_blank" rel="noopener">{escape(a["title"])}</a></div>'
        for a in articles
    )


def _issue_card_html(rank: int, issue: Issue) -> str:
    # The compact (collapsed) card caps Why Hot at 2 bullets to hit the
    # spec's ~180-220px target height — the full list (already <=4
    # items, see web/issues.py) would push it noticeably taller, and
    # the summary stays visible when expanded too so nothing is lost.
    why_hot = "".join(f"<li>{escape(b)}</li>" for b in issue.why_hot[:2])
    metrics = "".join(
        f'<div class="metric"><span class="metric-label">{label}</span>'
        f'<span class="metric-value">{value:.0f}</span></div>'
        for label, value in (
            ("Khối lượng", issue.volume_score),
            ("Nguồn", issue.source_score),
            ("Tốc độ", issue.velocity_score),
            ("Mới", issue.novelty_score),
        )
    )
    metrics += (
        f'<div class="metric"><span class="metric-label">Lần đầu</span>'
        f'<span class="metric-value">{issue.first_seen_at.strftime("%H:%M")}</span></div>'
        f'<div class="metric"><span class="metric-label">Cập nhật gần nhất</span>'
        f'<span class="metric-value">{issue.last_seen_at.strftime("%H:%M")}</span></div>'
    )
    issue_id = escape(issue.issue_id)
    return (
        f'<details class="issue-card" id="issue-{issue_id}">'
        f'<summary>'
        f'<span class="issue-rank">{rank:02d}</span>'
        f'<div class="issue-summary">'
        f'<div class="issue-title-row"><span class="issue-title">{escape(issue.issue_title)}</span>'
        f'<span class="issue-score">HOT {issue.hot_score:.0f}</span></div>'
        f'<div class="issue-stats">{issue.article_count} bài · {issue.unique_source_count} nguồn</div>'
        f'<ul class="why-hot-compact">{why_hot}</ul>'
        f'</div></summary>'
        f'<div class="issue-detail">'
        f'<div class="issue-metrics">{metrics}</div>'
        f'{_source_coverage_html(issue)}'
        f'<div class="related-articles">{_related_articles_html(issue.all_articles)}</div>'
        f'</div></details>'
    )


def _top_issues_html(issues: List[Issue]) -> str:
    """The "TOP ISSUES" section — only rendered on the latest day's page
    (see build_site), since it is scored against *today* (Asia/Ho_Chi_Minh)
    and would be meaningless attached to an older archive day's page.
    Omitted entirely when nothing currently clears the issue thresholds
    (see web/issues.py) rather than shown empty."""
    if not issues:
        return ""
    cards = "".join(_issue_card_html(rank, issue) for rank, issue in enumerate(issues, start=1))
    return (
        '<section id="issues" class="top-issues">'
        '<h2 class="section-title">Top Issues hôm nay</h2>'
        '<p class="section-note">Trong phạm vi các nguồn báo mà hệ thống đang theo dõi — '
        'không phải xếp hạng mức độ quan trọng khách quan.</p>'
        f'<div class="issues-grid">{cards}</div></section>'
    )


def _today_overview_html(total: int, n_sources: int, issues: List[Issue], now: datetime, is_latest: bool) -> str:
    title = "Today overview" if is_latest else "Overview"
    stats = [f'<span><strong>{total}</strong> bài viết</span>', f'<span><strong>{n_sources}</strong> nguồn</span>']
    if issues:
        stats.append(f'<span><strong>{len(issues)}</strong> issue nổi bật</span>')
    stats.append(f'<span>Cập nhật lúc {now.strftime("%H:%M")}</span>')
    strip = '<span class="dot-sep">·</span>'.join(stats)
    return (
        f'<section id="overview" class="today-overview"><h2 class="section-title">{title}</h2>'
        f'<div class="overview-strip">{strip}</div></section>'
    )


def _by_source_html(sources: Dict[str, List[dict]]) -> str:
    columns = []
    for source in _ordered_sources(sources.keys()):
        items = sources[source]
        rows = "".join(
            f'<li><span class="time">{_time_label(a)}</span>'
            f'<a href="{escape(a["url"])}" target="_blank" rel="noopener">{escape(a["title"])}</a></li>'
            for a in items
        )
        # <details>/<summary> keeps per-column collapse/expand with zero
        # JS, same as before; the header just no longer carries a
        # per-source accent color or icon (spec: "No colorful columns").
        columns.append(
            f'<details class="source-col" open>'
            f'<summary><span class="source-name">{escape(source)}</span>'
            f'<span class="count">{len(items)}</span><span class="chevron">▾</span></summary>'
            f'<div class="source-list-wrap"><ul>{rows}</ul></div></details>'
        )
    body = "".join(columns) if columns else '<p class="empty">Không có bài nào.</p>'
    return f'<section id="sources" class="by-source"><h2 class="section-title">By source</h2><div class="source-board">{body}</div></section>'


def _archive_html(day: date, all_dates: List[date]) -> str:
    window = _tab_window(all_dates, day)
    tab_items = []
    for d in window:
        cls = ' class="active"' if d == day else ""
        tab_items.append(f'<a href="{d.isoformat()}.html"{cls}>{d.strftime("%d/%m")}</a>')
    tabs_html = "".join(tab_items)

    picker_html = ""
    if len(all_dates) > len(window):
        options = "".join(
            f'<option value="{d.isoformat()}.html"{" selected" if d == day else ""}>{d.strftime("%d/%m/%Y")}</option>'
            for d in all_dates
        )
        picker_html = f'<div class="date-picker">Ngày khác: <select onchange="location.href=this.value">{options}</select></div>'

    return (
        f'<section id="archive" class="archive"><h2 class="section-title">Archive</h2>'
        f'<div class="date-tabs">{tabs_html}</div>{picker_html}</section>'
    )


_NEWS_PAGE_SIZE = 15

_INTERACTION_SCRIPT = f"""
var PAGE_SIZE = {_NEWS_PAGE_SIZE};
var currentPage = 1;

function rowsList() {{ return document.querySelectorAll('#news-stream-list .news-row'); }}
function matchingRows() {{
  return Array.prototype.filter.call(rowsList(), function (row) {{ return !row.classList.contains('filtered-out'); }});
}}

function applyFilters() {{
  var q = (document.getElementById('search-news').value || '').trim().toLowerCase();
  var src = document.getElementById('filter-source').value;
  var iss = document.getElementById('filter-issue').value;
  rowsList().forEach(function (row) {{
    var ok = true;
    if (src && row.dataset.source !== src) ok = false;
    if (iss && row.dataset.issue !== iss) ok = false;
    if (ok && q && row.textContent.toLowerCase().indexOf(q) === -1) ok = false;
    row.classList.toggle('filtered-out', !ok);
  }});
  currentPage = 1;
  renderPage();
}}

function setSort(btn, mode) {{
  document.querySelectorAll('.sort-toggle .pill').forEach(function (b) {{ b.classList.remove('active'); }});
  btn.classList.add('active');
  var container = document.getElementById('news-stream-list');
  var arr = Array.prototype.slice.call(rowsList());
  arr.sort(function (a, b) {{
    if (mode === 'trending') {{
      var bh = parseFloat(b.dataset.hot) || 0, ah = parseFloat(a.dataset.hot) || 0;
      if (bh !== ah) return bh - ah;
    }}
    return parseInt(b.dataset.ts, 10) - parseInt(a.dataset.ts, 10);
  }});
  arr.forEach(function (row) {{ container.appendChild(row); }});
  currentPage = 1;
  renderPage();
}}

// Shows only the current page's slice of rows that still pass the
// active filters (so pagination and filtering compose correctly —
// e.g. filtering down to 8 matches collapses to a single page), then
// (re)draws the numbered page buttons below the list.
function renderPage() {{
  var matching = matchingRows();
  var totalPages = Math.max(1, Math.ceil(matching.length / PAGE_SIZE));
  if (currentPage > totalPages) currentPage = totalPages;
  var start = (currentPage - 1) * PAGE_SIZE;
  rowsList().forEach(function (row) {{ row.style.display = 'none'; }});
  matching.slice(start, start + PAGE_SIZE).forEach(function (row) {{ row.style.display = ''; }});
  renderPagination(totalPages);
}}

function goToPage(p) {{
  currentPage = p;
  renderPage();
  document.getElementById('news').scrollIntoView({{behavior: 'smooth', block: 'start'}});
}}

// Windowed page numbers (1 … currentPage-2..currentPage+2 … last) so a
// 400+ article day doesn't render 30 raw page buttons in a row.
function renderPagination(totalPages) {{
  var container = document.getElementById('news-pagination');
  if (totalPages <= 1) {{ container.innerHTML = ''; return; }}
  var pages = [];
  for (var p = 1; p <= totalPages; p++) {{
    if (p === 1 || p === totalPages || Math.abs(p - currentPage) <= 2) {{
      pages.push(p);
    }} else if (pages[pages.length - 1] !== '...') {{
      pages.push('...');
    }}
  }}
  container.innerHTML = pages.map(function (p) {{
    if (p === '...') return '<span class="page-ellipsis">…</span>';
    var cls = 'page-btn' + (p === currentPage ? ' active' : '');
    return '<button type="button" class="' + cls + '" onclick="goToPage(' + p + ')">' + p + '</button>';
  }}).join('');
}}

renderPage();
"""


def render_day_page(
    day: date,
    sources: Dict[str, List[dict]],
    all_dates: List[date],
    trending: Optional[List[Issue]] = None,
) -> str:
    now = datetime.now(ZoneInfo(config.timezone))
    is_latest = trending is not None
    issues = trending or []
    total = sum(len(items) for items in sources.values())
    ordered_sources = _ordered_sources(sources.keys())
    issue_lookup = _issue_lookup(issues)
    all_articles = [a for items in sources.values() for a in items]

    nav_issues = '<a href="#issues">ISSUES</a>' if issues else ""
    header_html = f"""<header class="site-header">
<div class="masthead">Vietnam News<span class="dot">.</span>Monitor</div>
<input type="search" id="search-news" class="search-input" placeholder="Tìm kiếm tiêu đề..." oninput="applyFilters()">
<nav class="main-nav">
<a href="#overview">TODAY</a>
{nav_issues}
<a href="#news">NEWS</a>
<a href="#sources">SOURCES</a>
<a href="#archive">ARCHIVE</a>
</nav>
<div class="header-meta"><span class="live-dot"></span>LIVE&nbsp;·&nbsp;{now.strftime("%H:%M")}</div>
{_scan_button_html()}
</header>"""

    news_html = (
        '<section id="news" class="news-stream"><h2 class="section-title">All news</h2>'
        f'{_filters_html(ordered_sources, issues)}'
        f'<div id="news-stream-list" class="news-stream-list">{_news_stream_html(all_articles, issue_lookup)}</div>'
        '<div id="news-pagination" class="pagination"></div>'
        '</section>'
    )

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vietnam News Monitor — {day.strftime('%d/%m/%Y')}</title>
<style>{STYLE}</style>
</head>
<body>
{header_html}
<main>
{_today_overview_html(total, len(sources), issues, now, is_latest)}
{_top_issues_html(issues)}
{news_html}
{_by_source_html(sources)}
{_archive_html(day, all_dates)}
</main>
<footer><p>Tự động cập nhật mỗi {config.crawl_interval_minutes} phút qua GitHub Actions.</p></footer>
<script>{_INTERACTION_SCRIPT}</script>
</body>
</html>
"""


def build_site(db: Database, out_dir: Path = SITE_DIR) -> None:
    articles = db.get_all_articles()
    by_date = group_by_date_and_source(articles)
    all_dates = sorted(by_date.keys(), reverse=True)

    # Computed once against wall-clock "now" (not tied to any one
    # archive day), scoped to *today* only (spec section 9), and only
    # ever shown on the latest day's page — see _top_issues_html's
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
