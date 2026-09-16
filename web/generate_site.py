"""Static HTML site generator — the read-only web archive companion to
the Telegram feed (per user request, V4). Regenerated from scratch out
of the full database on every crawl cycle (see news-crawl.yml, which
deploys the result to GitHub Pages), so there is no incremental state
to get out of sync: `site/` is always a pure function of `data/news.db`.

Deliberately has zero network/Telegram dependency, so it can also be
run locally (`python -m web.generate_site`) to preview the archive
against whatever `data/news.db` already exists.
"""

import shutil
from collections import defaultdict
from datetime import date, datetime
from html import escape
from pathlib import Path
from typing import Dict, List

from config import config
from crawlers import CRAWLER_CLASSES
from database import Database
from telegram import _icon_for

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


def render_day_page(day: date, sources: Dict[str, List[dict]], all_dates: List[date]) -> str:
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
</header>
<nav class="dates">
<div class="strip">{tabs_html}</div>
{picker_html}
</nav>
<main>{body_html}</main>
<footer><p>Tự động cập nhật mỗi {config.crawl_interval_minutes} phút qua GitHub Actions.</p></footer>
</body>
</html>
"""


def build_site(db: Database, out_dir: Path = SITE_DIR) -> None:
    articles = db.get_all_articles()
    by_date = group_by_date_and_source(articles)
    all_dates = sorted(by_date.keys(), reverse=True)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    for day in all_dates:
        (out_dir / f"{day.isoformat()}.html").write_text(
            render_day_page(day, by_date[day], all_dates), encoding="utf-8"
        )

    latest = all_dates[0] if all_dates else date.today()
    latest_sources = by_date.get(latest, {})
    (out_dir / "index.html").write_text(
        render_day_page(latest, latest_sources, all_dates), encoding="utf-8"
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
