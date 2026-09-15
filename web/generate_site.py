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

SITE_DIR = Path(__file__).resolve().parent.parent / "site"

# Same display order as the Telegram digest (spec: config order, not
# time-sorted) — a source not in CRAWLER_CLASSES (shouldn't happen,
# but a DB from an older/newer config could have one) is appended
# after, alphabetically, rather than silently dropped.
_SOURCE_ORDER = [cls.source_name for cls in CRAWLER_CLASSES]

STYLE = """
:root{color-scheme:light dark;--bg:#f7f7f8;--fg:#1a1a1a;--muted:#666;--accent:#2563eb;--border:#e2e2e2;--card:#fff;}
@media (prefers-color-scheme: dark){:root{--bg:#0f1115;--fg:#e6e6e6;--muted:#9aa0a6;--accent:#60a5fa;--border:#2a2d34;--card:#171a21;}}
*{box-sizing:border-box;}
body{margin:0;background:var(--bg);color:var(--fg);font-family:-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;line-height:1.5;}
header{padding:24px 16px 8px;text-align:center;}
header h1{margin:0 0 4px;font-size:1.4rem;}
.subtitle{margin:0;color:var(--muted);font-size:.9rem;}
nav.dates{overflow-x:auto;white-space:nowrap;padding:8px 16px;border-bottom:1px solid var(--border);}
nav.dates ul{list-style:none;display:inline-flex;gap:8px;margin:0;padding:0;}
nav.dates a{display:inline-block;padding:6px 12px;border-radius:999px;background:var(--card);border:1px solid var(--border);color:var(--fg);text-decoration:none;font-size:.85rem;}
nav.dates a.active{background:var(--accent);color:#fff;border-color:var(--accent);}
main{max-width:720px;margin:0 auto;padding:16px;}
section.source{margin-bottom:24px;}
section.source h2{font-size:1rem;margin:0 0 8px;padding-bottom:4px;border-bottom:1px solid var(--border);}
.count{color:var(--muted);font-weight:normal;font-size:.85rem;}
section.source ul{list-style:none;margin:0;padding:0;}
section.source li{padding:8px 0;border-bottom:1px dashed var(--border);}
section.source li:last-child{border-bottom:none;}
.time{color:var(--muted);font-size:.8rem;margin-right:8px;font-variant-numeric:tabular-nums;}
a{color:var(--accent);}
.empty{text-align:center;color:var(--muted);padding:40px 0;}
footer{text-align:center;color:var(--muted);font-size:.8rem;padding:24px 16px;}
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
    nav_items = []
    for d in all_dates:
        cls = ' class="active"' if d == day else ""
        nav_items.append(f'<li><a href="{d.isoformat()}.html"{cls}>{d.strftime("%d/%m/%Y")}</a></li>')
    nav_html = "".join(nav_items)

    total = sum(len(items) for items in sources.values())

    sections = []
    for source in _ordered_sources(sources.keys()):
        items = sources[source]
        rows = "".join(
            f'<li><span class="time">{_time_label(a)}</span>'
            f'<a href="{escape(a["url"])}" target="_blank" rel="noopener">{escape(a["title"])}</a></li>'
            for a in items
        )
        sections.append(
            f'<section class="source"><h2>{escape(source)} '
            f'<span class="count">({len(items)})</span></h2><ul>{rows}</ul></section>'
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
<h1>📰 Vietnam News Monitor</h1>
<p class="subtitle">{day.strftime('%d/%m/%Y')} — {total} bài, {len(sources)} nguồn</p>
</header>
<nav class="dates"><ul>{nav_html}</ul></nav>
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
