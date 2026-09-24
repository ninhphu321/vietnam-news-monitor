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
from web.analytics import Analytics, IssueStreak, compute_analytics, issue_streaks, trend_from_stats
from web.brands import BrandIndex, Watchlist, load_watchlist
from web.brandwatch import (BrandStat, CrisisAlert, Tagged, crisis_alerts, share_of_voice,
                            tag_articles, tags_by_url)
from web.exports import brands_json, feed_xml, issues_json, stats_json
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
@media (max-width:900px){.main-nav:not(.always),.header-meta{display:none;}}
.main-nav a.active{color:var(--text);}
.masthead a{color:inherit;text-decoration:none;}
.page-title-note{max-width:1320px;margin:0 auto;padding:24px 24px 0;}

/* ---- Scan button (kept from earlier revision; unrelated to design v2.0) ---- */
.scan{flex:0 0 auto;}
.scan button{font:inherit;font-weight:600;font-size:12px;color:var(--text);background:var(--surface);
  border:1px solid var(--border);border-radius:999px;box-shadow:var(--shadow);padding:7px 16px;cursor:pointer;}
.scan button:hover{background:var(--surface-2);}
.scan button:disabled{cursor:wait;opacity:.6;}
.scan .status{display:block;margin-top:4px;font-family:var(--mono);font-size:10px;color:var(--muted);
  position:absolute;white-space:nowrap;}

/* ---- Archived-day notice (points back to the newest day) ---- */
.latest-banner{max-width:1320px;margin:16px auto 0;padding:10px 24px;background:var(--accent-soft);
  color:var(--accent);font-size:13px;text-align:center;}
.latest-banner a{color:var(--accent);font-weight:600;text-decoration:underline;}
@media (max-width:1024px){.latest-banner{padding:10px 20px;}}
@media (max-width:640px){.latest-banner{padding:10px 16px;}}

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

/* ---- Analytics ---- */
.an-grid{display:grid;grid-template-columns:1fr;gap:12px;margin-top:16px;}
@media (min-width:1000px){.an-grid{grid-template-columns:1fr 1fr;}}
details.an-block{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
  box-shadow:var(--shadow);min-width:0;}
details.an-block>summary{padding:14px 20px;cursor:pointer;list-style:none;user-select:none;font-weight:650;font-size:16px;}
details.an-block>summary::-webkit-details-marker{display:none;}
details.an-block[open]>summary{border-bottom:1px solid var(--divider);}
.an-body{padding:14px 20px 18px;overflow-x:auto;}
.an-note{color:var(--muted);font-size:12px;font-style:italic;margin:0 0 10px;}
.an-note.gap{margin-top:14px;}
.an-empty{color:var(--muted);font-size:13px;}
table.an-table{width:100%;border-collapse:collapse;font-size:13px;}
.an-table th{text-align:left;font-family:var(--mono);font-size:11px;font-weight:500;color:var(--muted);
  padding:4px 8px 6px 0;border-bottom:1px solid var(--divider);white-space:nowrap;}
.an-table td{padding:6px 8px 6px 0;border-bottom:1px solid var(--divider);vertical-align:top;}
.an-table td.num,.an-table th.num{text-align:right;font-family:var(--mono);}
.an-table tr:last-child td{border-bottom:none;}
.an-list{list-style:none;margin:0;padding:0;font-size:13px;}
.an-list li{padding:6px 0;border-bottom:1px solid var(--divider);}
.an-list li:last-child{border-bottom:none;}
.an-list .dim,.dim{color:var(--text-2);}
.an-bars{display:flex;align-items:flex-end;gap:3px;height:80px;margin:6px 0 4px;}
.an-bars .bar{flex:1 1 0;background:var(--accent);border-radius:3px 3px 0 0;min-height:2px;}
.an-axis{display:flex;justify-content:space-between;font-family:var(--mono);font-size:10px;color:var(--muted);}
td.heat,th.heat{font-family:var(--mono);text-align:center;}

/* ---- Brand monitoring ---- */
.news-row .sent{flex:0 0 8px;width:8px;height:8px;border-radius:50%;}
.news-row .sent.neg{background:var(--live);}
.news-row .sent.pos{background:var(--accent);}
.news-row .brand-tag{flex:0 0 auto;font-family:var(--mono);font-size:11px;color:var(--text-2);
  border:1px solid var(--border);border-radius:999px;padding:2px 8px;white-space:nowrap;}
@media (max-width:640px){.news-row .brand-tag{display:none;}}
.role-tag{font-family:var(--mono);font-size:10px;border-radius:999px;padding:1px 7px;margin-left:6px;
  background:var(--accent-soft);color:var(--accent);}
.role-tag.comp{background:var(--surface-2);color:var(--text-2);border:1px solid var(--border);}
.crisis-list{list-style:none;margin:0;padding:0;}
.crisis-item{border:1px solid var(--live);border-radius:var(--radius);padding:14px 18px;margin-bottom:10px;background:var(--surface);}
.crisis-item .lvl{font-family:var(--mono);font-size:11px;font-weight:700;color:var(--live);text-transform:uppercase;}
.crisis-ok{color:var(--text-2);font-size:14px;padding:6px 0;}
.sov-bar{min-width:90px;}
.delta-up{color:var(--accent);} .delta-down{color:var(--live);}

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


def _news_row_html(article: dict, issue_lookup: Dict[str, Issue], brand_tags: Optional[Dict[str, Tagged]] = None) -> str:
    issue = issue_lookup.get(article["url"])
    tagged = (brand_tags or {}).get(article["url"])
    brand_attr, extra_html = "", ""
    if tagged is not None:
        brand_attr = "|" + "|".join(escape(b) for b in tagged.brands) + "|"
        label = tagged.sentiment.label
        if label in ("tiêu cực", "tích cực"):
            cls = "neg" if label == "tiêu cực" else "pos"
            why = escape(", ".join(tagged.sentiment.reasons))
            extra_html += f'<span class="sent {cls}" title="{escape(label)} (ước lượng): {why}"></span>'
        extra_html += "".join(f'<span class="brand-tag">{escape(b)}</span>' for b in tagged.brands[:2])
    issue_id = escape(issue.issue_id) if issue else ""
    hot = f"{issue.hot_score:.1f}" if issue else "0"
    ts = _sort_key(article)
    tag_html = ""
    if issue is not None:
        tag_html = f'<a class="issue-tag" href="#issue-{issue_id}">{escape(issue.issue_title)}</a>'
    return (
        f'<div class="news-row" data-source="{escape(article["source"])}" '
        f'data-issue="{issue_id}" data-brand="{brand_attr}" data-hot="{hot}" data-ts="{int(ts.timestamp())}">'
        f'<span class="ts">{_time_label(article)}</span>'
        f'<span class="src">{escape(article["source"])}</span>'
        f'<a class="headline" href="{escape(article["url"])}" target="_blank" rel="noopener">{escape(article["title"])}</a>'
        f'{extra_html}{tag_html}</div>'
    )


def _news_stream_html(articles: List[dict], issue_lookup: Dict[str, Issue],
                      brand_tags: Optional[Dict[str, Tagged]] = None) -> str:
    if not articles:
        return '<p class="empty">Không có bài nào.</p>'
    ordered = sorted(articles, key=_sort_key, reverse=True)
    return "".join(_news_row_html(a, issue_lookup, brand_tags) for a in ordered)


def _filters_html(sources_present: List[str], issues: List[Issue], brands: Optional[List[str]] = None) -> str:
    brand_select = ""
    if brands:
        options = "".join(f'<option value="{escape(b)}">{escape(b)}</option>' for b in brands)
        brand_select = (f'<select class="pill-select" id="filter-brand" onchange="applyFilters()">'
                        f'<option value="">Tất cả thương hiệu</option>{options}</select>\n')
    source_options = "".join(f'<option value="{escape(s)}">{escape(s)}</option>' for s in sources_present)
    issue_options = "".join(
        f'<option value="{escape(i.issue_id)}">{escape(i.issue_title)}</option>' for i in issues
    )
    return f"""<div class="filters">
<select class="pill-select" id="filter-source" onchange="applyFilters()"><option value="">Tất cả nguồn</option>{source_options}</select>
<select class="pill-select" id="filter-issue" onchange="applyFilters()"><option value="">Tất cả issue</option>{issue_options}</select>
{brand_select}<div class="sort-toggle">
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


def _an_table(headers, rows, num_cols=()):
    head = "".join(f'<th class="num">{h}</th>' if i in num_cols else f"<th>{h}</th>" for i, h in enumerate(headers))
    body = "".join(
        "<tr>" + "".join(f'<td class="num">{c}</td>' if i in num_cols else f"<td>{c}</td>" for i, c in enumerate(r)) + "</tr>"
        for r in rows
    )
    return f'<table class="an-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def _an_block(title: str, note: str, body: str, is_open: bool = False) -> str:
    note_html = f'<p class="an-note">{escape(note)}</p>' if note else ""
    return (f'<details class="an-block"{" open" if is_open else ""}><summary>{escape(title)}</summary>'
            f'<div class="an-body">{note_html}{body}</div></details>')


def _an_bars(values, label_left: str, label_right: str) -> str:
    peak = max(values) or 1
    bars = "".join(
        f'<div class="bar" title="{v}" style="height:{max(v / peak * 100, 2):.0f}%"></div>' for v in values
    )
    return (f'<div class="an-bars">{bars}</div>'
            f'<div class="an-axis"><span>{escape(label_left)}</span><span>{escape(label_right)}</span></div>')


def _heat_cell(value: float, peak: float, label: str) -> str:
    alpha = 0.0 if peak <= 0 else min(value / peak, 1.0) * 0.55
    return f'<td class="heat" style="background:rgba(31,75,69,{alpha:.2f})">{label}</td>'


def _an_first_movers(an: Analytics) -> str:
    if an.first_mover_rows:
        rows = [
            (escape(r.source), r.first_count, r.participated, f"{r.first_rate * 100:.0f}%",
             "—" if r.median_lag_min is None else f"+{r.median_lag_min:.0f} phút")
            for r in an.first_mover_rows[:10]
        ]
        body = _an_table(["Nguồn", "Đưa trước", "Tham gia", "Tỷ lệ", "Trễ trung vị"], rows, num_cols=(1, 2, 3, 4))
    else:
        body = '<p class="an-empty">Chưa đủ dữ liệu.</p>'
    today = "".join(
        f'<li><b>{escape(r["title"])}</b> — <span class="dim">{escape(r["first_source"])} đưa trước '
        f'({r["first_at"].strftime("%H:%M")}); '
        + ", ".join(f"{escape(src)} +{lag:.0f}p" for src, lag in r["lags"][:4])
        + "</span></li>"
        for r in an.first_mover_today[:6]
    )
    if today:
        body += f'<p class="an-note gap">Hôm nay</p><ul class="an-list">{today}</ul>'
    return _an_block(
        "Ai đưa tin trước",
        "7 ngày gần nhất, tính theo issue (cùng đối tượng + chủ đề trong ngày) — chỉ là ước lượng, không đảm bảo cùng 1 sự kiện.",
        body, is_open=True)


def _an_gaps(an: Analytics) -> str:
    excl = "".join(
        f'<li><b>{escape(e["title"])}</b> <span class="dim">— chỉ {escape(e["source"])} ({e["articles"]} bài)</span></li>'
        for e in an.exclusives
    ) or '<li class="an-empty">Không có.</li>'
    gaps = "".join(
        f'<li><b>{escape(g["title"])}</b> <span class="dim">({g["sources"]} nguồn) — chưa thấy: '
        f'{escape(", ".join(g["missing"][:6]) or "không (đã phủ hết)")}</span></li>'
        for g in an.gaps
    ) or '<li class="an-empty">Không có.</li>'
    return _an_block(
        "Khoảng trống đưa tin",
        "Hôm nay. Chỉ 1 nguồn đưa có thể là tin độc quyền, hoặc 1 báo tự đăng lặp.",
        f'<p class="an-note">Chỉ 1 nguồn đưa</p><ul class="an-list">{excl}</ul>'
        f'<p class="an-note gap">Nhiều báo đưa nhưng thiếu báo lớn</p><ul class="an-list">{gaps}</ul>')


def _an_lag(an: Analytics) -> str:
    body = _an_table(
        ["Nguồn", "Trung vị", "P90", "Mẫu"],
        [(escape(r.source), f"{r.median_min:.0f} phút", f"{r.p90_min:.0f} phút", r.samples) for r in an.lag_rows],
        num_cols=(1, 2, 3),
    ) if an.lag_rows else '<p class="an-empty">Chưa đủ dữ liệu.</p>'
    return _an_block(
        "Độ trễ thu thập",
        "Giờ hệ thống thấy bài trừ giờ báo đăng, 7 ngày, bỏ độ trễ > 6 giờ (backfill). Chu kỳ quét 20 phút nên trung vị ~10-30 phút là bình thường.",
        body)


def _an_rhythm(an: Analytics) -> str:
    body = _an_bars(an.hourly_overall, "00h", "23h")
    if an.rhythm_rows:
        body += _an_table(
            ["Nguồn", "Giờ đăng nhiều nhất", "Đăng đêm (0-6h)"],
            [(escape(r.source), f"{r.peak_hour:02d}h", f"{r.night_share * 100:.0f}%") for r in an.rhythm_rows],
            num_cols=(1, 2))
    return _an_block("Nhịp đăng bài theo giờ", "Theo giờ đăng của báo, 7 ngày gần nhất.", body)


def _an_volume(an: Analytics) -> str:
    body = _an_bars(an.volume_totals, an.volume_days[0].strftime("%d/%m"), an.volume_days[-1].strftime("%d/%m"))
    body += '<p class="an-note gap">Theo chủ đề (số bài mỗi ngày)</p>'
    peak = max((max(v) for v in an.volume_topics.values()), default=0)
    head = "<th>Chủ đề</th>" + "".join(f'<th class="heat">{d.strftime("%d")}</th>' for d in an.volume_days)
    rows = "".join(
        f"<tr><td>{escape(t)}</td>" + "".join(_heat_cell(c, peak, str(c) if c else "·") for c in counts) + "</tr>"
        for t, counts in an.volume_topics.items()
    )
    body += f'<table class="an-table"><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>'
    return _an_block("Khối lượng tin theo thời gian", "Cột = tổng số bài mỗi ngày, 14 ngày gần nhất.", body)


def _an_reposts(an: Analytics) -> str:
    body = _an_table(
        ["Nguồn", "Đăng lặp", "Tổng bài", "Tỷ lệ"],
        [(escape(r["source"]), r["reposts"], r["total"], f'{r["rate"] * 100:.1f}%') for r in an.repost_stats[:8]],
        num_cols=(1, 2, 3),
    ) if an.repost_stats else '<p class="an-empty">Chưa đủ dữ liệu.</p>'
    examples = "".join(
        f'<li><span class="dim">{escape(e["source"])}:</span> {escape(e["first"])} <span class="dim">→</span> {escape(e["again"])}</li>'
        for e in an.repost_examples
    )
    if examples:
        body += f'<p class="an-note gap">Ví dụ</p><ul class="an-list">{examples}</ul>'
    return _an_block(
        "Tin đăng lặp", "Tiêu đề gần giống (≥80% từ, cùng các con số) do cùng 1 báo đăng lại trong 24 giờ.", body)


def _an_cooccurrence(an: Analytics) -> str:
    et = "".join(
        f'<li><b>{escape(r["entity"])}</b> + {escape(r["topic"])} <span class="dim">— {r["count"]} bài</span></li>'
        for r in an.entity_topic
    ) or '<li class="an-empty">Chưa đủ dữ liệu.</li>'
    ee = "".join(
        f'<li><b>{escape(r["a"])}</b> + <b>{escape(r["b"])}</b> <span class="dim">— {r["count"]} bài</span></li>'
        for r in an.entity_entity
    ) or '<li class="an-empty">Chưa đủ dữ liệu.</li>'
    return _an_block(
        "Đồng xuất hiện", "7 ngày gần nhất.",
        f'<p class="an-note">Đối tượng + chủ đề</p><ul class="an-list">{et}</ul>'
        f'<p class="an-note gap">Đối tượng + đối tượng</p><ul class="an-list">{ee}</ul>')


def _an_topic_mix(an: Analytics) -> str:
    peak = max((v for row in an.mix_matrix.values() for v in row.values()), default=0)
    head = "<th>Nguồn</th>" + "".join(f'<th class="heat">{escape(t)}</th>' for t in an.mix_topics)
    rows = "".join(
        f'<tr><td>{escape(src)} <span class="dim">({an.mix_totals[src]})</span></td>'
        + "".join(_heat_cell(share, peak, f"{share * 100:.0f}%" if share else "·") for share in row.values())
        + "</tr>"
        for src, row in sorted(an.mix_matrix.items())
    )
    return _an_block(
        "Hồ sơ chủ đề từng nguồn", "Tỷ lệ bài của mỗi nguồn thuộc từng chủ đề, 7 ngày (trong ngoặc: số bài).",
        f'<table class="an-table"><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>')


def _an_streaks(streaks: List[IssueStreak]) -> str:
    if streaks:
        rows = [
            (escape(st.title), st.days, st.current_streak, st.best_rank, f"{st.peak_hot:.0f}", st.last_day[5:].replace("-", "/"))
            for st in streaks
        ]
        body = _an_table(["Issue", "Số ngày", "Liên tiếp", "Hạng cao nhất", "Điểm cao nhất", "Gần nhất"], rows,
                         num_cols=(1, 2, 3, 4, 5))
    else:
        body = '<p class="an-empty">Chưa có lịch sử — dữ liệu bắt đầu tích lũy từ lần quét đầu tiên sau khi bật tính năng.</p>'
    return _an_block(
        "Lịch sử Top Issues",
        "Issue từng lọt Top 5 trong ngày. \"Liên tiếp\" = số ngày liền nhau tính tới hôm nay.",
        body, is_open=True)


def _an_trend(trend) -> str:
    days, totals, topics = trend
    body = _an_bars(totals, days[0].strftime("%d/%m"), days[-1].strftime("%d/%m"))
    if topics:
        peak = max(max(v) for v in topics.values())
        head = "<th>Chủ đề</th>" + "".join(f'<th class="heat">{d.strftime("%d")}</th>' for d in days)
        rows = "".join(
            f"<tr><td>{escape(t)}</td>" + "".join(_heat_cell(c, peak, str(c) if c else "·") for c in counts) + "</tr>"
            for t, counts in topics.items()
        )
        body += f'<p class="an-note gap">Theo chủ đề</p><table class="an-table"><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>'
    return _an_block("Xu hướng 30 ngày", "Đọc từ bảng daily_stats đã tổng hợp sẵn (không quét lại toàn bộ bài).", body)


def _analytics_body(an: Analytics, streaks: List[IssueStreak], trend) -> str:
    blocks = [_an_first_movers(an), _an_streaks(streaks), _an_gaps(an), _an_lag(an), _an_rhythm(an)]
    if trend is not None:
        blocks.append(_an_trend(trend))
    if an.volume_days:
        blocks.append(_an_volume(an))
    blocks += [_an_reposts(an), _an_cooccurrence(an)]
    if an.mix_matrix:
        blocks.append(_an_topic_mix(an))
    return (
        '<section id="analytics" class="analytics"><h2 class="section-title">Analytics</h2>'
        '<p class="section-note">Số liệu tính thuần từ các bài đã thu thập — không dùng AI, không dữ liệu ngoài. '
        'Dữ liệu thô: <a href="issues.json">issues.json</a> · <a href="stats.json">stats.json</a> · '
        '<a href="feed.xml">feed.xml</a></p>'
        f'<div class="an-grid">{"".join(blocks)}</div></section>'
    )


def _tab_header(active: str, now: datetime) -> str:
    def link(key, href, label):
        cls = ' class="active"' if key == active else ""
        return f'<a href="{href}"{cls}>{label}</a>'
    return f"""<header class="site-header">
<div class="masthead"><a href="index.html">Vietnam News<span class="dot">.</span>Monitor</a></div>
<nav class="main-nav always" style="margin-left:auto">
{link("home", "index.html", "HOME")}
{link("brands", "brands.html", "BRANDS")}
{link("analytics", "analytics.html", "ANALYTICS")}
</nav>
<div class="header-meta"><span class="live-dot"></span>LIVE&nbsp;·&nbsp;{now.strftime("%H:%M")}</div>
</header>"""


def _role_tag(role: str) -> str:
    if role == "own":
        return '<span class="role-tag">của mình</span>'
    if role == "competitor":
        return '<span class="role-tag comp">đối thủ</span>'
    return ""


def _delta(cur: int, prev: int) -> str:
    if prev == 0:
        return "mới" if cur else "—"
    pct = (cur - prev) / prev * 100
    cls = "delta-up" if pct >= 0 else "delta-down"
    return f'<span class="{cls}">{pct:+.0f}%</span>'


def _sov_table(stats: List[BrandStat], limit: int = 15) -> str:
    shown = [s for s in stats if s.mentions or s.role != "other"][:limit] if stats else []
    if not shown:
        return '<p class="an-empty">Chưa có tin nhắc tới các thương hiệu theo dõi.</p>'
    peak = max(s.share for s in shown) or 1
    rows = []
    for st in shown:
        bar = (f'<div class="coverage-track sov-bar"><div class="coverage-fill" '
               f'style="width:{st.share / peak * 100:.0f}%"></div></div>')
        neg_pct = f"{st.negative / st.mentions * 100:.0f}%" if st.mentions else "—"
        rows.append((f"{escape(st.brand)}{_role_tag(st.role)}", st.mentions, f"{st.share * 100:.1f}%", bar,
                     st.sources, st.positive, st.negative, neg_pct, _delta(st.mentions, st.previous_mentions)))
    return _an_table(["Thương hiệu", "Tin", "Share of voice", "", "Nguồn", "Tích cực", "Tiêu cực", "% tiêu cực", "So kỳ trước"],
                     rows, num_cols=(1, 2, 4, 5, 6, 7, 8))


def _brands_body(stats7: List[BrandStat], stats30: List[BrandStat], alerts: List[CrisisAlert],
                 watch: Watchlist, index: BrandIndex, window_minutes: int) -> str:
    if watch.own or watch.competitors:
        setup = (f'<p class="section-note">Đang theo dõi {len(watch.tracked)} thương hiệu trong watchlist.json '
                 f'({len(watch.own)} của mình, {len(watch.competitors)} đối thủ).</p>')
    else:
        setup = (f'<p class="section-note">Chưa cấu hình thương hiệu của bạn — đang theo dõi toàn bộ '
                 f'{len(index.brands)} thương hiệu trong từ điển. Sửa <code>watchlist.json</code> '
                 f'(own / competitors) để tập trung vào thương hiệu mình và đối thủ.</p>')

    if alerts:
        items = "".join(
            f'<li class="crisis-item"><span class="lvl">{escape(a.level)}</span> — <b>{escape(a.brand)}</b>: '
            f'{len(a.sources)} báo ({escape(", ".join(a.sources))}) trong {a.window_minutes} phút'
            f'<div class="dim" style="margin-top:4px">Từ khoá: {escape(", ".join(a.keywords))}</div>'
            + "".join(f'<div style="font-size:13px;margin-top:4px"><a href="{escape(x["url"])}" target="_blank" '
                      f'rel="noopener">{escape(x["title"])}</a> <span class="dim">({escape(x["source"])})</span></div>'
                      for x in a.articles[:5])
            + "</li>"
            for a in alerts
        )
        crisis = f'<ul class="crisis-list">{items}</ul>'
    else:
        crisis = f'<p class="crisis-ok">Không có cảnh báo leo thang trong {window_minutes} phút qua.</p>'

    blocks = [
        _an_block("Cảnh báo khủng hoảng",
                  "≥3 báo đăng tin tiêu cực mức mạnh về cùng 1 thương hiệu trong 1 giờ (hoặc ≥2 báo với từ khoá nghiêm trọng như khởi tố, vỡ nợ, rút tiền ồ ạt).",
                  crisis, is_open=True),
        _an_block("Share of voice — 7 ngày", "Tỷ trọng số tin nhắc tới mỗi thương hiệu trong tổng tin của các thương hiệu theo dõi.",
                  _sov_table(stats7), is_open=True),
        _an_block("Share of voice — 30 ngày", "", _sov_table(stats30)),
    ]

    top = [s for s in stats7 if s.mentions][:10]
    if top:
        head = "<th>Thương hiệu</th>" + "".join(f'<th class="heat">{i}</th>' for i in range(-13, 1))
        peak = max(max(s.daily) for s in top) or 1
        rows = "".join(
            f"<tr><td>{escape(s.brand)}</td>" + "".join(_heat_cell(c, peak, str(c) if c else "·") for c in s.daily) + "</tr>"
            for s in top
        )
        blocks.append(_an_block("Số tin theo ngày (14 ngày)", "Cột cuối = hôm nay.",
                                f'<table class="an-table"><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>'))

    negatives = sorted(
        (dict(n, brand=s.brand) for s in stats7 for n in s.recent_negative), key=lambda n: n["ts"], reverse=True
    )[:15]
    neg_html = "".join(
        f'<li><b>{escape(n["brand"])}</b> — <a href="{escape(n["url"])}" target="_blank" rel="noopener">{escape(n["title"])}</a> '
        f'<span class="dim">({escape(n["source"])}, {n["ts"].strftime("%d/%m %H:%M")}; {escape(", ".join(n["reasons"]))})</span></li>'
        for n in negatives
    ) or '<li class="an-empty">Không có.</li>'
    blocks.append(_an_block("Tin tiêu cực gần đây",
                            "Nhãn là ước lượng từ tiêu đề bằng từ khoá — hiện kèm từ khoá đã kích hoạt để bạn kiểm chứng.",
                            f'<ul class="an-list">{neg_html}</ul>'))

    return (
        '<section id="brands" class="analytics"><h2 class="section-title">Brands</h2>'
        f'{setup}<p class="section-note">Dữ liệu thô: <a href="brands.json">brands.json</a></p>'
        f'<div class="an-grid">{"".join(blocks)}</div></section>'
    )


def render_brands_page(stats7, stats30, alerts, watch, index, now: datetime, window_minutes: int) -> str:
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Brands — Vietnam News Monitor</title>
<style>{STYLE}</style>
</head>
<body>
{_tab_header("brands", now)}
<main>
{_brands_body(stats7, stats30, alerts, watch, index, window_minutes)}
</main>
<footer><p>Sắc thái tin là ước lượng bằng từ khoá từ tiêu đề — cần người xác nhận trước khi hành động.</p></footer>
</body>
</html>
"""


def render_analytics_page(an: Analytics, streaks: List[IssueStreak], trend, now: datetime) -> str:
    """The separate "ANALYTICS" tab (analytics.html) — kept off the home
    page on purpose so the home page stays a fast news reader."""
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Analytics — Vietnam News Monitor</title>
<link rel="alternate" type="application/rss+xml" title="Vietnam News Monitor" href="feed.xml">
<style>{STYLE}</style>
</head>
<body>
{_tab_header("analytics", now)}
<main>
{_analytics_body(an, streaks, trend)}
</main>
<footer><p>Tự động cập nhật mỗi {config.crawl_interval_minutes} phút qua GitHub Actions.</p></footer>
</body>
</html>
"""


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
  var brandSel = document.getElementById('filter-brand');
  var brd = brandSel ? brandSel.value : '';
  rowsList().forEach(function (row) {{
    var ok = true;
    if (src && row.dataset.source !== src) ok = false;
    if (iss && row.dataset.issue !== iss) ok = false;
    if (brd && (row.dataset.brand || '').indexOf('|' + brd + '|') === -1) ok = false;
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


def _latest_banner_html(latest_href: Optional[str]) -> str:
    """A small notice on every archived (non-latest) day page pointing
    back to the newest day. Without this, a bookmarked/shared link to a
    specific dated URL (e.g. "2026-09-16.html") stays frozen on that
    day forever by design (it's the archive feature) — a user landing
    on it right after midnight, before switching to the fresh
    "index.html"/root URL themselves, has no way to tell they're not
    already on the latest day, or how to get there."""
    if not latest_href:
        return ""
    return (
        '<div class="latest-banner">Bạn đang xem tin lưu trữ, không phải ngày mới nhất — '
        f'<a href="{escape(latest_href)}">xem tin mới nhất →</a></div>'
    )


def render_day_page(
    day: date,
    sources: Dict[str, List[dict]],
    all_dates: List[date],
    trending: Optional[List[Issue]] = None,
    latest_href: Optional[str] = None,
    has_analytics: bool = False,
    brand_tags: Optional[Dict[str, Tagged]] = None,
) -> str:
    now = datetime.now(ZoneInfo(config.timezone))
    is_latest = trending is not None
    issues = trending or []
    total = sum(len(items) for items in sources.values())
    ordered_sources = _ordered_sources(sources.keys())
    issue_lookup = _issue_lookup(issues)
    all_articles = [a for items in sources.values() for a in items]

    nav_issues = '<a href="#issues">ISSUES</a>' if issues else ""
    nav_analytics = (
        '<a href="brands.html">BRANDS</a>\n<a href="analytics.html">ANALYTICS</a>\n' if has_analytics else ""
    )
    brand_names = sorted({b for t in (brand_tags or {}).values() for b in t.brands})
    header_html = f"""<header class="site-header">
<div class="masthead">Vietnam News<span class="dot">.</span>Monitor</div>
<input type="search" id="search-news" class="search-input" placeholder="Tìm kiếm tiêu đề..." oninput="applyFilters()">
<nav class="main-nav">
<a href="#overview">TODAY</a>
{nav_issues}
<a href="#news">NEWS</a>
<a href="#sources">SOURCES</a>
{nav_analytics}<a href="#archive">ARCHIVE</a>
</nav>
<div class="header-meta"><span class="live-dot"></span>LIVE&nbsp;·&nbsp;{now.strftime("%H:%M")}</div>
{_scan_button_html()}
</header>"""

    news_html = (
        '<section id="news" class="news-stream"><h2 class="section-title">All news</h2>'
        f'{_filters_html(ordered_sources, issues, brand_names)}'
        f'<div id="news-stream-list" class="news-stream-list">{_news_stream_html(all_articles, issue_lookup, brand_tags)}</div>'
        '<div id="news-pagination" class="pagination"></div>'
        '</section>'
    )

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vietnam News Monitor — {day.strftime('%d/%m/%Y')}</title>
<link rel="alternate" type="application/rss+xml" title="Vietnam News Monitor" href="feed.xml">
<style>{STYLE}</style>
</head>
<body>
{header_html}
{_latest_banner_html(latest_href)}
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
    has_data = bool(articles)
    index, watch = load_watchlist(config.watchlist_path)
    tagged = tag_articles(articles, index, watch)
    brand_tags = tags_by_url(tagged)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    latest = all_dates[0] if all_dates else date.today()
    for day in all_dates:
        is_latest = day == latest
        (out_dir / f"{day.isoformat()}.html").write_text(
            render_day_page(
                day, by_date[day], all_dates,
                trending=(trending if is_latest else None),
                latest_href=(None if is_latest else f"{latest.isoformat()}.html"),
                has_analytics=has_data, brand_tags=brand_tags,
            ),
            encoding="utf-8",
        )

    latest_sources = by_date.get(latest, {})
    (out_dir / "index.html").write_text(
        render_day_page(latest, latest_sources, all_dates, trending=trending, has_analytics=has_data,
                        brand_tags=brand_tags), encoding="utf-8"
    )

    # Tells GitHub Pages not to run this through Jekyll (irrelevant here
    # since no filenames start with "_", but it's the standard marker
    # and costs nothing to include).
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")

    if has_data:
        analytics = compute_analytics(articles, now)
        streaks = issue_streaks(db.get_issue_history(), now.date())
        daily_stats = db.get_daily_stats()
        trend = trend_from_stats(daily_stats, now.date()) if daily_stats else None
        (out_dir / "analytics.html").write_text(
            render_analytics_page(analytics, streaks, trend, now), encoding="utf-8"
        )
        stats7 = share_of_voice(tagged, index, watch, now, 7)
        stats30 = share_of_voice(tagged, index, watch, now, 30)
        alerts = crisis_alerts(tagged, now, watch, index, config.crisis_window_minutes, config.crisis_min_sources)
        (out_dir / "brands.html").write_text(
            render_brands_page(stats7, stats30, alerts, watch, index, now, config.crisis_window_minutes),
            encoding="utf-8",
        )
        (out_dir / "brands.json").write_text(brands_json(stats7, stats30, alerts, watch, now), encoding="utf-8")
        (out_dir / "issues.json").write_text(issues_json(trending, now), encoding="utf-8")
        (out_dir / "stats.json").write_text(
            stats_json(daily_stats, db.get_issue_history(), now), encoding="utf-8"
        )
        (out_dir / "feed.xml").write_text(feed_xml(articles, config.site_url, now), encoding="utf-8")


def main() -> None:
    db = Database(config.db_path, config.timezone)
    build_site(db)
    html_files = list(SITE_DIR.glob("*.html"))
    print(f"Site generated at {SITE_DIR} ({len(html_files)} HTML file(s)).")


if __name__ == "__main__":
    main()
