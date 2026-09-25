"""App shell + design system for the generated site (UI handoff spec:
"Modern SaaS dashboard + editorial information product").

Layout
  desktop  >=1024  sidebar 260px (collapsible to 68px) + 64px header
  tablet   768-1023 sidebar forced to 68px, header 60px
  mobile   <768    sidebar becomes a drawer (min(320px, 85vw)) with a
                   backdrop, 56px header, bottom navigation, filters in a
                   bottom sheet, tables as cards

Everything here is presentation only: no framework, no build step, the
JS is a few dozen lines for drawer / sidebar collapse / bottom sheet.
Icons are one consistent inline-SVG set (no emoji, no CDN font).
"""

from html import escape
from typing import List, Optional

FONT_IMPORT = (
    "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700"
    "&family=IBM+Plex+Mono:wght@500;700&display=swap');"
)

ICONS = """<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false"><defs>
<symbol id="i-home" viewBox="0 0 24 24"><path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/><path d="M10 20v-6h4v6"/></symbol>
<symbol id="i-flame" viewBox="0 0 24 24"><path d="M12 3c1 3 5 5 5 10a5 5 0 0 1-10 0c0-2 1-3 2-4 0 2 1 3 2 3 0-3-1-5 1-9z"/></symbol>
<symbol id="i-news" viewBox="0 0 24 24"><rect x="4" y="4" width="16" height="16" rx="2"/><path d="M8 9h8M8 13h8M8 17h5"/></symbol>
<symbol id="i-building" viewBox="0 0 24 24"><path d="M4 21V7l8-4 8 4v14"/><path d="M9 21v-6h6v6M9 10h.01M15 10h.01"/></symbol>
<symbol id="i-chart" viewBox="0 0 24 24"><path d="M4 20V10M10 20V4M16 20v-8M22 20H2"/></symbol>
<symbol id="i-db" viewBox="0 0 24 24"><ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/></symbol>
<symbol id="i-archive" viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="4" rx="1"/><path d="M5 8v11h14V8M10 12h4"/></symbol>
<symbol id="i-rss" viewBox="0 0 24 24"><path d="M5 19h.01M5 12a7 7 0 0 1 7 7M5 5a14 14 0 0 1 14 14"/></symbol>
<symbol id="i-json" viewBox="0 0 24 24"><path d="M8 4c-2 0-3 1-3 3v2c0 1-1 2-2 3 1 1 2 2 2 3v2c0 2 1 3 3 3M16 4c2 0 3 1 3 3v2c0 1 1 2 2 3-1 1-2 2-2 3v2c0 2-1 3-3 3"/></symbol>
<symbol id="i-menu" viewBox="0 0 24 24"><path d="M4 6h16M4 12h16M4 18h16"/></symbol>
<symbol id="i-x" viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></symbol>
<symbol id="i-collapse" viewBox="0 0 24 24"><path d="M11 7l-5 5 5 5M18 7l-5 5 5 5"/></symbol>
<symbol id="i-filter" viewBox="0 0 24 24"><path d="M4 5h16l-6 8v6l-4-2v-4z"/></symbol>
<symbol id="i-search" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></symbol>
<symbol id="i-refresh" viewBox="0 0 24 24"><path d="M20 11a8 8 0 1 0-2 6M20 5v6h-6"/></symbol>
</defs></svg>"""


def icon(name: str) -> str:
    return f'<svg class="ic" aria-hidden="true" focusable="false"><use href="#i-{name}"/></svg>'


STYLE = FONT_IMPORT + """
:root{
  color-scheme:light;
  --bg:#F6F7F9;--surface:#FFFFFF;--surface-2:#F9FAFB;
  --text:#0F172A;--text-2:#475569;--muted:#94A3B8;
  --border:#E2E8F0;--divider:#EEF2F6;
  --accent:#2563EB;--accent-soft:#EAF1FF;--live:#DC2626;
  --radius:16px;--radius-sm:10px;
  --shadow:0 1px 2px rgba(15,23,42,.05);
  --sans:"Inter",-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,monospace;
  --sp-1:4px;--sp-2:8px;--sp-3:12px;--sp-4:16px;--sp-5:24px;--sp-6:32px;--sp-7:48px;
  --pad:32px;
  --z-header:100;--z-dropdown:200;--z-tooltip:300;--z-backdrop:390;--z-drawer:400;--z-modal:500;--z-toast:600;
  --t-fast:150ms;--t-mid:220ms;
}
*{box-sizing:border-box;}
html{scroll-behavior:smooth;}
body{margin:0;background:var(--bg);color:var(--text);font-family:var(--sans);font-size:14px;line-height:1.55;}
a{color:inherit;}
h1,h2,h3,p{margin:0;}
button,select,input{font:inherit;color:inherit;}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;}
.ic{width:20px;height:20px;flex:0 0 20px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round;}
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;}
[hidden]{display:none!important;}

/* ================= app shell ================= */
.app{--sb-w:260px;--label:block;--header-h:64px;
  display:grid;grid-template-columns:var(--sb-w) minmax(0,1fr);grid-template-rows:var(--header-h) 1fr;
  grid-template-areas:"sidebar header" "sidebar main";min-height:100vh;
  transition:grid-template-columns var(--t-mid) ease;}
.app.sb-collapsed{--sb-w:68px;--label:none;}
@media (min-width:768px) and (max-width:1023px){.app{--sb-w:68px;--label:none;--header-h:60px;}}

.sidebar{grid-area:sidebar;position:sticky;top:0;height:100vh;background:var(--surface);
  border-right:1px solid var(--border);display:flex;flex-direction:column;padding:var(--sp-4) var(--sp-3);
  overflow-x:hidden;overflow-y:auto;z-index:var(--z-header);}
.brand{display:flex;align-items:center;gap:var(--sp-3);padding:0 var(--sp-2);height:40px;margin-bottom:var(--sp-5);
  text-decoration:none;white-space:nowrap;}
.logo-mark{flex:0 0 32px;width:32px;height:32px;border-radius:9px;background:var(--accent);color:#fff;
  display:grid;place-items:center;font-family:var(--mono);font-weight:700;font-size:12px;}
.brand-name{display:var(--label);font-weight:700;font-size:15px;line-height:1.15;}
.brand-name small{display:block;font-weight:500;font-size:11px;color:var(--muted);}
.nav-group-title{display:var(--label);font-family:var(--mono);font-size:11px;font-weight:500;letter-spacing:.06em;
  color:var(--muted);text-transform:uppercase;padding:var(--sp-4) var(--sp-2) var(--sp-2);}
.nav{display:flex;flex-direction:column;gap:2px;}
.nav-item{display:flex;align-items:center;gap:var(--sp-3);min-height:40px;padding:0 var(--sp-3);
  border-radius:var(--radius-sm);text-decoration:none;color:var(--text-2);font-weight:500;white-space:nowrap;
  transition:background var(--t-fast) ease,color var(--t-fast) ease;}
.nav-item:hover{background:var(--surface-2);color:var(--text);}
.nav-item[aria-current="page"]{background:var(--accent-soft);color:var(--accent);}
.nav-label{display:var(--label);}
.sb-spacer{flex:1 1 auto;min-height:var(--sp-4);}
.sb-toggle{display:flex;align-items:center;gap:var(--sp-3);min-height:40px;padding:0 var(--sp-3);border:0;
  background:none;border-radius:var(--radius-sm);color:var(--text-2);cursor:pointer;white-space:nowrap;}
.sb-toggle:hover{background:var(--surface-2);color:var(--text);}
.sb-toggle .ic{transition:transform var(--t-mid) ease;}
.app.sb-collapsed .sb-toggle .ic{transform:rotate(180deg);}
@media (min-width:768px) and (max-width:1023px){.sb-toggle{display:none;}}
.nav-item .ic,.sb-toggle .ic{margin:0;}
.app.sb-collapsed .nav-item,.app.sb-collapsed .sb-toggle{justify-content:center;padding:0;}
@media (min-width:768px) and (max-width:1023px){.nav-item{justify-content:center;padding:0;}}

.topbar{grid-area:header;position:sticky;top:0;z-index:var(--z-header);height:var(--header-h);background:var(--surface);
  border-bottom:1px solid var(--border);display:flex;align-items:center;gap:var(--sp-4);padding:0 var(--pad);}
.icon-btn.menu-btn{display:none;}
.icon-btn{display:inline-grid;place-items:center;width:44px;height:44px;border:0;border-radius:var(--radius-sm);
  background:none;color:var(--text);cursor:pointer;}
.icon-btn:hover{background:var(--surface-2);}
.crumb{display:flex;align-items:center;gap:var(--sp-2);min-width:0;font-size:13px;color:var(--text-2);white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis;}
.crumb b{color:var(--text);font-weight:600;}
.crumb .sep{color:var(--muted);}
.topbar-actions{margin-left:auto;display:flex;align-items:center;gap:var(--sp-4);}
.live{display:flex;align-items:center;gap:var(--sp-2);font-family:var(--mono);font-size:11px;font-weight:500;color:var(--text-2);}
.live-dot{width:7px;height:7px;border-radius:50%;background:var(--live);}

.main{grid-area:main;min-width:0;padding:var(--pad);padding-bottom:var(--sp-7);}
.container{width:100%;max-width:1440px;margin:0 auto;}
@media (min-width:1440px){.app{--pad:44px;}}
@media (min-width:768px) and (max-width:1023px){.app{--pad:24px;}}

.backdrop{position:fixed;inset:0;background:rgba(0,0,0,.35);z-index:var(--z-backdrop);opacity:0;pointer-events:none;
  transition:opacity var(--t-mid) ease;}
.bottom-nav{display:none;}

/* ================= mobile (<768) ================= */
@media (max-width:767px){
  .app{--header-h:56px;--pad:16px;--label:block;grid-template-columns:minmax(0,1fr);
    grid-template-areas:"header" "main";}
  .sidebar{position:fixed;left:0;top:0;bottom:0;height:auto;width:min(320px,85vw);z-index:var(--z-drawer);
    transform:translateX(-100%);visibility:hidden;transition:transform var(--t-mid) ease,visibility 0s linear var(--t-mid);}
  .app.drawer-open .sidebar{transform:none;visibility:visible;transition:transform var(--t-mid) ease;}
  .app.drawer-open .backdrop,.app.sheet-open .backdrop{opacity:1;pointer-events:auto;}
  .sb-toggle{display:none;}
  .icon-btn.menu-btn{display:inline-grid;}
  .topbar{padding:0 var(--sp-2);gap:var(--sp-2);}
  .topbar .live span.t{display:none;}
  .main{padding-bottom:calc(56px + env(safe-area-inset-bottom,0px) + var(--sp-5));}
  .bottom-nav{display:grid;grid-template-columns:repeat(5,1fr);position:fixed;left:0;right:0;bottom:0;
    z-index:var(--z-header);height:calc(56px + env(safe-area-inset-bottom,0px));padding-bottom:env(safe-area-inset-bottom,0px);
    background:var(--surface);border-top:1px solid var(--border);}
  .bn-item{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;min-height:44px;
    border:0;background:none;text-decoration:none;color:var(--text-2);font-size:11px;font-weight:500;cursor:pointer;}
  .bn-item[aria-current="page"]{color:var(--accent);}
}

/* ================= page header ================= */
.page-head{display:flex;justify-content:space-between;align-items:flex-end;gap:var(--sp-4);margin-bottom:var(--sp-5);flex-wrap:wrap;}
.page-head h1{font-size:34px;line-height:1.15;font-weight:700;letter-spacing:-.02em;}
.page-head p{color:var(--text-2);margin-top:var(--sp-1);max-width:70ch;}
.page-actions{display:flex;flex-direction:column;align-items:flex-end;gap:var(--sp-2);}
@media (max-width:767px){
  .page-head{flex-direction:column;align-items:stretch;}
  .page-head h1{font-size:26px;}
  .page-actions{align-items:stretch;}
}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:var(--sp-2);min-height:40px;padding:0 var(--sp-4);
  border-radius:var(--radius-sm);border:1px solid var(--border);background:var(--surface);color:var(--text);
  font-weight:600;cursor:pointer;transition:background var(--t-fast) ease;}
.btn:hover{background:var(--surface-2);}
.btn.primary{background:var(--accent);border-color:var(--accent);color:#fff;}
.btn.primary:hover{background:#1D4ED8;}
.btn:disabled{opacity:.6;cursor:wait;}
@media (max-width:767px){.btn{min-height:44px;}.page-actions .btn{width:100%;}}
.scan .status{display:block;font-family:var(--mono);font-size:11px;color:var(--muted);min-height:1.2em;text-align:right;}
@media (max-width:767px){.scan .status{text-align:left;}}

.latest-banner{display:flex;gap:var(--sp-2);flex-wrap:wrap;align-items:center;margin-bottom:var(--sp-5);padding:var(--sp-3) var(--sp-4);
  background:var(--accent-soft);color:var(--accent);border-radius:var(--radius-sm);font-size:13px;}
.latest-banner a{font-weight:600;}

/* ================= grid + cards ================= */
.kpi-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:var(--sp-4);margin-bottom:var(--sp-5);}
@media (min-width:768px) and (max-width:1023px){.kpi-grid{grid-template-columns:repeat(2,minmax(0,1fr));}}
@media (max-width:767px){.kpi-grid{grid-template-columns:1fr;gap:var(--sp-3);}}
.kpi{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);padding:var(--sp-4) var(--sp-5);}
.kpi-label{font-size:12px;color:var(--text-2);font-weight:500;}
.kpi-value{font-family:var(--mono);font-size:30px;font-weight:700;letter-spacing:-.02em;line-height:1.2;margin:var(--sp-2) 0 var(--sp-1);}
.kpi-sub{font-size:12px;color:var(--text-2);}
.kpi-sub .up{color:var(--accent);font-weight:600;}.kpi-sub .down{color:var(--live);font-weight:600;}
@media (max-width:767px){
  .kpi{display:grid;grid-template-columns:minmax(0,1fr) auto;grid-template-areas:"label value" "sub value";
    align-items:center;column-gap:var(--sp-4);padding:var(--sp-3) var(--sp-4);}
  .kpi-label{grid-area:label;}.kpi-sub{grid-area:sub;}
  .kpi-value{grid-area:value;font-size:24px;margin:0;}
}

.content-grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:var(--sp-5);margin-bottom:var(--sp-6);}
.col-8{grid-column:span 8;}.col-4{grid-column:span 4;}.col-12{grid-column:span 12;}
@media (max-width:1023px){.col-8,.col-4{grid-column:span 12;}}
.panel{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);padding:var(--sp-5);}
.panel-title{font-size:16px;font-weight:650;margin-bottom:var(--sp-1);}
.panel-note{font-size:12px;color:var(--muted);margin-bottom:var(--sp-4);}
@media (max-width:767px){.panel{padding:var(--sp-4);}}

.section{margin-bottom:var(--sp-6);scroll-margin-top:calc(var(--header-h) + var(--sp-4));}
.section-title{font-size:22px;font-weight:650;letter-spacing:-.01em;line-height:1.2;}
.section-note{color:var(--muted);font-size:12px;margin:var(--sp-1) 0 var(--sp-4);}
.section-head{display:flex;align-items:baseline;justify-content:space-between;gap:var(--sp-4);flex-wrap:wrap;margin-bottom:var(--sp-3);}
.count-chip{font-family:var(--mono);font-size:12px;color:var(--text-2);}
@media (max-width:767px){.section-title{font-size:20px;}}

/* ---- Top issues (list inside the 8-col panel) ---- */
.issues-grid{display:flex;flex-direction:column;gap:var(--sp-3);}
details.issue-card{background:var(--surface-2);border:1px solid var(--border);border-radius:var(--radius);}
details.issue-card>summary{display:flex;gap:var(--sp-4);align-items:flex-start;padding:var(--sp-4) var(--sp-5);cursor:pointer;list-style:none;user-select:none;}
details.issue-card>summary::-webkit-details-marker{display:none;}
details.issue-card:target>*:not(summary){display:block!important;}
.issue-rank{font-family:var(--mono);font-weight:700;font-size:18px;color:var(--muted);flex:0 0 auto;}
.issue-summary{flex:1 1 auto;min-width:0;}
.issue-title-row{display:flex;justify-content:space-between;align-items:baseline;gap:var(--sp-3);flex-wrap:wrap;}
.issue-title{font-size:18px;font-weight:650;line-height:1.25;letter-spacing:-.01em;}
.issue-score{flex:0 0 auto;font-family:var(--mono);font-weight:700;font-size:12px;color:var(--accent);background:var(--accent-soft);
  border-radius:999px;padding:3px 10px;white-space:nowrap;}
.issue-stats{font-family:var(--mono);font-size:12px;color:var(--text-2);margin:var(--sp-1) 0 var(--sp-2);}
.why-hot-compact{list-style:none;margin:0;padding:0;}
.why-hot-compact li{font-size:13px;color:var(--text-2);padding:1px 0;}
.why-hot-compact li::before{content:"— ";color:var(--muted);}
.issue-detail{padding:0 var(--sp-5) var(--sp-5);border-top:1px solid var(--divider);}
.issue-metrics{display:flex;flex-wrap:wrap;gap:var(--sp-5);padding:var(--sp-4) 0;}
.metric{display:flex;flex-direction:column;gap:2px;}
.metric-label{font-size:11px;color:var(--muted);}
.metric-value{font-family:var(--mono);font-size:16px;font-weight:700;}
.source-coverage{display:flex;flex-direction:column;gap:var(--sp-2);padding:var(--sp-2) 0 var(--sp-4);}
.coverage-row{display:flex;align-items:center;gap:var(--sp-3);}
.coverage-src{flex:0 0 130px;font-size:12px;color:var(--text-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.coverage-track{flex:1 1 auto;height:6px;background:var(--bg);border-radius:999px;overflow:hidden;}
.coverage-fill{height:100%;background:var(--accent);border-radius:999px;}
.coverage-count{flex:0 0 24px;text-align:right;font-family:var(--mono);font-size:12px;color:var(--text-2);}
.related-articles{display:flex;flex-direction:column;}
.related-row{display:flex;align-items:baseline;gap:var(--sp-3);padding:var(--sp-2) 0;border-top:1px solid var(--divider);font-size:13px;}
.related-row:first-child{border-top:none;}
.related-row .src{font-family:var(--mono);font-size:11px;color:var(--text-2);flex:0 0 110px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.related-row a{flex:1 1 auto;min-width:0;text-decoration:none;}
.related-row a:hover{color:var(--accent);text-decoration:underline;}
@media (max-width:767px){details.issue-card>summary{padding:var(--sp-4);gap:var(--sp-3);}.related-row{flex-direction:column;gap:2px;}
  .related-row .src{flex:none;}}

/* sources side panel */
.bar-list{display:flex;flex-direction:column;gap:var(--sp-3);}
.bar-row{display:grid;grid-template-columns:110px minmax(0,1fr) 34px;gap:var(--sp-3);align-items:center;font-size:13px;}
.bar-row .name{color:var(--text-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.bar-row .val{font-family:var(--mono);font-size:12px;text-align:right;}

/* ================= toolbar / filters / sheet ================= */
.toolbar{display:flex;align-items:center;gap:var(--sp-2);flex-wrap:wrap;margin-bottom:var(--sp-3);}
.search-box{position:relative;flex:1 1 280px;min-width:0;}
.search-box .ic{position:absolute;left:14px;top:50%;transform:translateY(-50%);color:var(--muted);pointer-events:none;}
.search-input{width:100%;min-height:44px;padding:0 14px 0 42px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-sm);}
.search-input::placeholder{color:var(--muted);}
.filter-btn{display:none;}
.filter-sheet{display:contents;}
.sheet-head,.sheet-foot{display:none;}
.fields{display:flex;gap:var(--sp-2);flex-wrap:wrap;align-items:center;}
.field label{display:none;font-size:12px;font-weight:600;margin-bottom:var(--sp-1);}
.pill-select{min-height:44px;padding:0 var(--sp-4);background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-sm);cursor:pointer;max-width:220px;}
.sort-toggle{display:flex;gap:6px;}
.pill{min-height:44px;padding:0 var(--sp-4);font-weight:500;color:var(--text-2);background:var(--surface);border:1px solid var(--border);
  border-radius:var(--radius-sm);cursor:pointer;}
.pill.active{color:var(--accent);background:var(--accent-soft);border-color:var(--accent-soft);}
@media (max-width:767px){
  .toolbar{flex-direction:column;align-items:stretch;}
  .filter-btn{display:inline-flex;}
  .filter-sheet{display:flex;flex-direction:column;position:fixed;left:0;right:0;bottom:0;z-index:var(--z-modal);max-height:85vh;overflow-y:auto;
    background:var(--surface);border-radius:20px 20px 0 0;padding:var(--sp-4) var(--sp-4) calc(var(--sp-4) + env(safe-area-inset-bottom,0px));
    transform:translateY(100%);visibility:hidden;transition:transform var(--t-mid) ease,visibility 0s linear var(--t-mid);}
  .app.sheet-open .filter-sheet{transform:none;visibility:visible;transition:transform var(--t-mid) ease;}
  .sheet-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--sp-3);font-weight:650;font-size:16px;}
  .sheet-foot{display:flex;gap:var(--sp-3);margin-top:var(--sp-4);}
  .sheet-foot .btn{flex:1;}
  .fields{flex-direction:column;align-items:stretch;gap:var(--sp-4);}
  .field label{display:block;}
  .pill-select{width:100%;max-width:none;}
  .sort-toggle .pill{flex:1;}
}

/* ================= news list (table on desktop, cards on mobile) ================= */
.news-table{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);overflow:clip;}
.news-head,.news-row{display:grid;grid-template-columns:150px minmax(0,1fr) 210px 56px;gap:var(--sp-4);align-items:center;padding:0 var(--sp-5);}
.news-head{position:sticky;top:var(--header-h);z-index:10;min-height:40px;background:var(--surface-2);border-bottom:1px solid var(--border);
  font-family:var(--mono);font-size:11px;font-weight:500;color:var(--muted);letter-spacing:.04em;text-transform:uppercase;}
.news-head span:last-child{text-align:right;}
.news-stream-list{display:flex;flex-direction:column;}
.news-row{min-height:64px;padding-top:var(--sp-2);padding-bottom:var(--sp-2);border-bottom:1px solid var(--divider);transition:background var(--t-fast) ease;}
.news-row:last-child{border-bottom:none;}
.news-row:hover{background:var(--surface-2);}
.news-row .src{font-family:var(--mono);font-size:12px;font-weight:500;color:var(--text-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.news-row .hl{min-width:0;display:flex;flex-direction:column;gap:4px;}
.news-row .headline{font-size:15px;font-weight:500;line-height:1.4;text-decoration:none;display:-webkit-box;-webkit-line-clamp:2;
  -webkit-box-orient:vertical;overflow:hidden;transition:color var(--t-fast) ease;}
.news-row .headline:hover{color:var(--accent);}
.hl-meta{display:flex;align-items:center;gap:6px;flex-wrap:wrap;}
.hl-meta:empty{display:none;}
.news-row .issue-tag{justify-self:start;max-width:100%;font-family:var(--mono);font-size:11px;font-weight:500;color:var(--accent);background:var(--accent-soft);
  border-radius:999px;padding:3px 10px;text-decoration:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.news-row .ts{font-family:var(--mono);font-size:12px;color:var(--muted);text-align:right;}
.news-row .sent{width:8px;height:8px;border-radius:50%;flex:0 0 8px;}
.news-row .sent.neg{background:var(--live);}.news-row .sent.pos{background:var(--accent);}
.brand-tag{font-family:var(--mono);font-size:11px;color:var(--text-2);border:1px solid var(--border);border-radius:999px;padding:1px 8px;white-space:nowrap;}
@media (min-width:768px) and (max-width:1023px){
  .news-head,.news-row{grid-template-columns:120px minmax(0,1fr) 56px;}
  .news-head span:nth-child(3),.news-row .issue-tag{display:none;}
}
@media (max-width:767px){
  .news-head{display:none;}
  .news-table{border:0;box-shadow:none;background:none;}
  .news-stream-list{gap:var(--sp-3);}
  .news-row{grid-template-columns:minmax(0,1fr) auto;grid-template-areas:"hl hl" "src ts" "tag tag";gap:var(--sp-2) var(--sp-3);
    padding:var(--sp-4);background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);}
  .news-row:last-child{border-bottom:1px solid var(--border);}
  .news-row .hl{grid-area:hl;}.news-row .src{grid-area:src;}.news-row .ts{grid-area:ts;}.news-row .issue-tag{grid-area:tag;}
  .news-row .headline{font-size:16px;}
}
.pagination{display:flex;flex-wrap:wrap;align-items:center;justify-content:center;gap:6px;margin-top:var(--sp-5);}
.page-btn{min-width:40px;min-height:40px;padding:0 var(--sp-3);font-family:var(--mono);font-size:12px;font-weight:500;color:var(--text-2);
  background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-sm);cursor:pointer;}
.page-btn.active{color:var(--accent);background:var(--accent-soft);border-color:var(--accent-soft);}
.page-ellipsis{color:var(--muted);font-family:var(--mono);padding:0 2px;}
@media (max-width:767px){.page-btn{min-width:44px;min-height:44px;}}

/* ================= states ================= */
.state{display:flex;flex-direction:column;align-items:center;gap:var(--sp-2);text-align:center;padding:var(--sp-7) var(--sp-4);color:var(--text-2);}
.state b{color:var(--text);font-size:16px;}
.state.error b{color:var(--live);}
.skeleton{display:block;height:14px;border-radius:6px;background:linear-gradient(90deg,var(--divider),var(--surface-2),var(--divider));
  background-size:200% 100%;animation:sk 1.2s ease-in-out infinite;}
@keyframes sk{from{background-position:200% 0}to{background-position:-200% 0}}
@media (prefers-reduced-motion:reduce){.skeleton{animation:none}*{transition-duration:.01ms!important}}

/* ================= by source (Kanban) + archive ================= */
.source-board{display:flex;align-items:flex-start;gap:var(--sp-4);overflow-x:auto;padding-bottom:var(--sp-2);}
details.source-col{flex:0 0 300px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);}
details.source-col>summary{display:flex;align-items:center;gap:var(--sp-3);min-height:48px;padding:0 var(--sp-4);cursor:pointer;font-weight:600;
  border-bottom:1px solid var(--divider);list-style:none;user-select:none;}
details.source-col>summary::-webkit-details-marker{display:none;}
details.source-col .count{margin-left:auto;font-family:var(--mono);font-weight:500;font-size:11px;color:var(--text-2);border:1px solid var(--border);border-radius:999px;padding:2px 9px;}
details.source-col .chevron{font-size:10px;color:var(--muted);transition:transform var(--t-fast) ease;}
details.source-col[open] .chevron{transform:rotate(180deg);}
.source-list-wrap{max-height:min(65vh,600px);overflow-y:auto;padding:4px var(--sp-4);}
.source-list-wrap ul{list-style:none;margin:0;padding:0;}
.source-list-wrap li{display:flex;gap:10px;padding:9px 0;border-bottom:1px solid var(--divider);}
.source-list-wrap li:last-child{border-bottom:none;}
.source-list-wrap a{text-decoration:none;font-size:13px;line-height:1.4;}
.source-list-wrap a:hover{color:var(--accent);text-decoration:underline;}
.source-list-wrap .time{color:var(--muted);font-family:var(--mono);font-size:11px;white-space:nowrap;padding-top:2px;}
@media (max-width:1023px){.source-board{flex-direction:column;overflow-x:visible;}details.source-col{flex-basis:auto;width:100%;}}
.date-tabs{display:flex;flex-wrap:wrap;gap:6px;}
.date-tabs a{min-height:40px;display:inline-flex;align-items:center;padding:0 var(--sp-4);font-family:var(--mono);font-size:12px;font-weight:500;text-decoration:none;
  color:var(--text-2);background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-sm);}
.date-tabs a:hover{color:var(--text);}
.date-tabs a.active{color:var(--accent);background:var(--accent-soft);border-color:var(--accent-soft);}
.date-picker{margin-top:var(--sp-3);font-family:var(--mono);font-size:12px;color:var(--muted);display:flex;align-items:center;gap:var(--sp-2);}
.date-picker select{min-height:40px;padding:0 var(--sp-3);background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-sm);}

/* ================= analytics / brands blocks ================= */
.an-grid{display:grid;grid-template-columns:1fr;gap:var(--sp-4);}
@media (min-width:1100px){.an-grid{grid-template-columns:1fr 1fr;}}
details.an-block{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);min-width:0;}
details.an-block>summary{padding:var(--sp-4) var(--sp-5);min-height:52px;display:flex;align-items:center;cursor:pointer;list-style:none;user-select:none;font-weight:650;font-size:16px;}
details.an-block>summary::-webkit-details-marker{display:none;}
details.an-block[open]>summary{border-bottom:1px solid var(--divider);}
.an-body{padding:var(--sp-4) var(--sp-5) var(--sp-5);overflow-x:auto;}
.an-note{color:var(--muted);font-size:12px;margin:0 0 var(--sp-3);}
.an-note.gap{margin-top:var(--sp-4);}
.an-empty{color:var(--muted);font-size:13px;}
table.an-table{width:100%;border-collapse:collapse;font-size:13px;}
.an-table th{text-align:left;font-family:var(--mono);font-size:11px;font-weight:500;color:var(--muted);padding:4px 8px 6px 0;border-bottom:1px solid var(--divider);white-space:nowrap;}
.an-table td{padding:8px 8px 8px 0;border-bottom:1px solid var(--divider);vertical-align:top;}
.an-table td.num,.an-table th.num{text-align:right;font-family:var(--mono);}
.an-table tr:last-child td{border-bottom:none;}
.an-table tbody tr:hover{background:var(--surface-2);}
.an-list{list-style:none;margin:0;padding:0;font-size:13px;}
.an-list li{padding:8px 0;border-bottom:1px solid var(--divider);}
.an-list li:last-child{border-bottom:none;}
.dim,.an-list .dim{color:var(--text-2);}
.an-bars{display:flex;align-items:flex-end;gap:3px;height:80px;margin:6px 0 4px;}
.an-bars .bar{flex:1 1 0;background:var(--accent);border-radius:3px 3px 0 0;min-height:2px;}
.an-axis{display:flex;justify-content:space-between;font-family:var(--mono);font-size:10px;color:var(--muted);}
td.heat,th.heat{font-family:var(--mono);text-align:center;}
.role-tag{font-family:var(--mono);font-size:10px;border-radius:999px;padding:1px 7px;margin-left:6px;background:var(--accent-soft);color:var(--accent);}
.role-tag.comp{background:var(--surface-2);color:var(--text-2);border:1px solid var(--border);}
.crisis-list{list-style:none;margin:0;padding:0;}
.crisis-item{border:1px solid var(--live);border-radius:var(--radius);padding:var(--sp-4) var(--sp-5);margin-bottom:var(--sp-3);background:var(--surface);}
.crisis-item .lvl{font-family:var(--mono);font-size:11px;font-weight:700;color:var(--live);text-transform:uppercase;}
.crisis-ok{color:var(--text-2);font-size:14px;padding:6px 0;}
.sov-bar{min-width:90px;}
.delta-up{color:var(--accent);}.delta-down{color:var(--live);}
.empty{text-align:center;color:var(--muted);padding:var(--sp-7) 0;}
.footer{margin-top:var(--sp-6);text-align:center;color:var(--muted);font-family:var(--mono);font-size:11px;}
"""

SHELL_SCRIPT = """
(function () {
  var app = document.getElementById('app');
  var menuBtn = document.getElementById('menu-btn');
  var sbToggle = document.getElementById('sb-toggle');
  var sidebar = document.getElementById('sidebar');
  var mobile = window.matchMedia('(max-width: 767px)');
  function store(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } }

  if (store('sb') === 'collapsed' && !mobile.matches) { app.classList.add('sb-collapsed'); }
  if (sbToggle) {
    sbToggle.setAttribute('aria-expanded', String(!app.classList.contains('sb-collapsed')));
    sbToggle.addEventListener('click', function () {
      var c = app.classList.toggle('sb-collapsed');
      sbToggle.setAttribute('aria-expanded', String(!c));
      store('sb', c ? 'collapsed' : 'expanded');
    });
  }

  var lastFocus = null;
  function openDrawer() {
    lastFocus = document.activeElement;
    app.classList.add('drawer-open');
    menuBtn && menuBtn.setAttribute('aria-expanded', 'true');
    var first = sidebar.querySelector('a,button');
    first && first.focus();
  }
  function closeDrawer(restore) {
    if (!app.classList.contains('drawer-open')) return;
    app.classList.remove('drawer-open');
    menuBtn && menuBtn.setAttribute('aria-expanded', 'false');
    if (restore !== false && lastFocus) lastFocus.focus();
  }
  function openSheet() { app.classList.add('sheet-open'); var f = document.querySelector('.filter-sheet select'); f && f.focus(); }
  function closeSheet() { app.classList.remove('sheet-open'); }

  document.querySelectorAll('[data-open-drawer]').forEach(function (b) { b.addEventListener('click', openDrawer); });
  document.querySelectorAll('[data-open-sheet]').forEach(function (b) { b.addEventListener('click', openSheet); });
  document.querySelectorAll('[data-close-sheet]').forEach(function (b) { b.addEventListener('click', closeSheet); });
  document.getElementById('backdrop').addEventListener('click', function () { closeDrawer(); closeSheet(); });
  sidebar.addEventListener('click', function (e) { if (e.target.closest('a')) closeDrawer(false); });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { closeDrawer(); closeSheet(); return; }
    if (e.key === 'Tab' && app.classList.contains('drawer-open')) {
      var items = sidebar.querySelectorAll('a,button');
      if (!items.length) return;
      var first = items[0], last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  });
  mobile.addEventListener && mobile.addEventListener('change', function () { closeDrawer(false); closeSheet(); });
})();
"""


def _nav_item(href: str, label: str, ic: str, key: str, active: str) -> str:
    current = ' aria-current="page"' if key == active else ""
    return (f'<a class="nav-item" href="{escape(href)}" title="{escape(label)}"{current}>'
            f'{icon(ic)}<span class="nav-label">{escape(label)}</span></a>')


def render_shell(
    *,
    active: str,
    title: str,
    crumb: str,
    body: str,
    now_label: str,
    has_data: bool,
    has_issues: bool,
    extra_head: str = "",
    scripts: str = "",
    footer: str = "",
) -> str:
    """Full HTML document: sidebar + topbar + main + mobile drawer/bottom nav."""
    main_items: List[str] = [_nav_item("index.html#overview", "Tổng quan", "home", "home", active)]
    if has_issues:
        main_items.append(_nav_item("index.html#issues", "Issues", "flame", "issues", active))
    main_items.append(_nav_item("index.html#news", "Tin tức", "news", "news", active))

    analysis = ""
    if has_data:
        analysis = (
            '<div class="nav-group-title">Phân tích</div><nav class="nav" aria-label="Phân tích">'
            + _nav_item("brands.html", "Brands", "building", "brands", active)
            + _nav_item("analytics.html", "Analytics", "chart", "analytics", active)
            + "</nav>"
        )
    data_links = ""
    if has_data:
        data_links = (
            '<div class="nav-group-title">Dữ liệu</div><nav class="nav" aria-label="Dữ liệu">'
            + _nav_item("feed.xml", "RSS feed", "rss", "rss", active)
            + _nav_item("issues.json", "Dữ liệu JSON", "json", "json", active)
            + "</nav>"
        )

    sidebar = f"""<aside class="sidebar" id="sidebar" aria-label="Điều hướng chính">
<a class="brand" href="index.html" aria-label="Vietnam News Monitor"><span class="logo-mark">VN</span><span class="brand-name">Vietnam News<small>Monitor</small></span></a>
<div class="nav-group-title">Chính</div>
<nav class="nav" aria-label="Chính">{"".join(main_items)}</nav>
{analysis}
<div class="nav-group-title">Quản lý</div>
<nav class="nav" aria-label="Quản lý">{_nav_item("index.html#sources", "Theo nguồn", "db", "sources", active)}{_nav_item("index.html#archive", "Lưu trữ", "archive", "archive", active)}</nav>
{data_links}
<div class="sb-spacer"></div>
<button class="sb-toggle" id="sb-toggle" type="button" aria-expanded="true" aria-controls="sidebar" title="Thu gọn thanh điều hướng">{icon("collapse")}<span class="nav-label">Thu gọn</span></button>
</aside>"""

    def bn(href, label, ic, key):
        current = ' aria-current="page"' if key == active else ""
        return f'<a class="bn-item" href="{href}"{current}>{icon(ic)}<span>{label}</span></a>'

    bottom = ""
    bottom_items = [bn("index.html#overview", "Tổng quan", "home", "home"), bn("index.html#news", "Tin tức", "news", "news")]
    if has_data:
        bottom_items += [bn("brands.html", "Brands", "building", "brands"), bn("analytics.html", "Analytics", "chart", "analytics")]
    else:
        bottom_items += [bn("index.html#sources", "Nguồn", "db", "sources"), bn("index.html#archive", "Lưu trữ", "archive", "archive")]
    bottom = (f'<nav class="bottom-nav" aria-label="Điều hướng nhanh">{"".join(bottom_items)}'
              f'<button class="bn-item" type="button" data-open-drawer aria-label="Mở menu">{icon("menu")}<span>Menu</span></button></nav>')

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<link rel="alternate" type="application/rss+xml" title="Vietnam News Monitor" href="feed.xml">
{extra_head}
<style>{STYLE}</style>
</head>
<body>
{ICONS}
<div class="app" id="app">
{sidebar}
<header class="topbar">
<button class="icon-btn menu-btn" id="menu-btn" type="button" data-open-drawer aria-label="Mở menu" aria-expanded="false" aria-controls="sidebar">{icon("menu")}</button>
<div class="crumb"><span>Vietnam News Monitor</span><span class="sep">/</span><b>{escape(crumb)}</b></div>
<div class="topbar-actions"><div class="live" role="status"><span class="live-dot"></span><span class="t">LIVE ·</span><span>{escape(now_label)}</span></div></div>
</header>
<main class="main" id="main"><div class="container">
{body}
<p class="footer">{footer}</p>
</div></main>
<div class="backdrop" id="backdrop"></div>
{bottom}
</div>
<script>{SHELL_SCRIPT}</script>
{scripts}
</body>
</html>
"""
