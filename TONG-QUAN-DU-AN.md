# Vietnam News Monitor — Tổng quan dự án (đầy đủ chi tiết)

> Tài liệu này là bản tổng hợp **đầy đủ nhất**, gộp toàn bộ kiến trúc, luồng xử lý, thuật toán, lịch sử quyết định kỹ thuật và giới hạn đã biết của dự án vào 1 file duy nhất. Các tài liệu khác trong repo phục vụ mục đích hẹp hơn:
> - [README.md](README.md) — tài liệu kỹ thuật gốc, chi tiết cấp code, dùng khi cần tra cứu implementation cụ thể.
> - [GIOI-THIEU.md](GIOI-THIEU.md) — bản giới thiệu ngắn gọn, phi kỹ thuật, để gửi cho người không rành code.
> - [GIAO-DIEN.md](GIAO-DIEN.md) — riêng phần giao diện web (v3, khung ứng dụng SaaS responsive).
>
> Repo: `ninhphu321/vietnam-news-monitor` (public). Trang web live: https://ninhphu321.github.io/vietnam-news-monitor/

---

## 1. Dự án này làm gì

Một hệ thống **tự động, chạy 24/7, miễn phí hoàn toàn**, quét 23 trang báo tài chính/kinh doanh Việt Nam mỗi 20 phút, phát hiện bài viết mới (chưa từng thấy), rồi:

1. Gửi thông báo qua **Telegram** (nhóm theo nguồn, đánh dấu tin "nóng", cảnh báo khủng hoảng theo thương hiệu).
2. Cập nhật một **trang web dạng ứng dụng** (GitHub Pages, giao diện SaaS 3 trang: Tổng quan / Brands / Analytics) hiển thị lại toàn bộ tin theo ngày, "Top Issues" tự phát hiện sự kiện đang được nhiều báo cùng đưa tin, theo dõi share of voice theo thương hiệu, và các phân tích dòng tin (ai đưa trước, khoảng trống đưa tin, nhịp đăng bài...).

Không dùng AI/LLM ở bất kỳ đâu trong hệ thống — toàn bộ là rule-based (RSS parsing, regex, từ khoá tự chọn tay, HotScore/sắc thái tính bằng công thức và từ điển cố định). Không có server riêng, không trả phí cho bất kỳ dịch vụ nào (GitHub Actions free tier, GitHub Pages free, Cloudflare Workers free tier, cron-job.org free).

---

## 2. Kiến trúc tổng thể

```
┌─────────────────┐  ping mỗi 20 phút   ┌──────────────────────┐
│  cron-job.org    │ ──────────────────▶ │  Cloudflare Worker    │
│ (lịch bên ngoài, │                      │  (giữ GitHub token    │
│  thay cho cron   │                      │   server-side)        │
│  nội bộ GitHub)  │                      └──────────┬───────────┘
└─────────────────┘                                  │ workflow_dispatch
                                                       ▼
                                          ┌─────────────────────────┐
                                          │   GitHub Actions          │
                                          │   (news-crawl.yml)        │
                                          │  1. Khôi phục news.db     │
                                          │     từ nhánh db-state     │
                                          │  2. Quét 23 nguồn          │
                                          │  3. Ghi snapshot + kiểm      │
                                          │     tra cảnh báo khủng hoảng │
                                          │  4. Gửi Telegram (nếu có   │
                                          │     bài mới/cảnh báo)      │
                                          │  5. Đẩy news.db mới lên     │
                                          │     nhánh db-state          │
                                          │  6. Sinh lại site/ tĩnh      │
                                          │  7. Deploy lên GitHub Pages  │
                                          └───────────┬─────────────┘
                                                       │
                                    ┌──────────────────┼──────────────────┐
                                    ▼                                     ▼
                          ┌──────────────────┐              ┌────────────────────────┐
                          │  Telegram (bot)   │              │  GitHub Pages (site)     │
                          │  → chat cá nhân    │              │  ninhphu321.github.io/   │
                          └──────────────────┘              │  vietnam-news-monitor/    │
                                                              └────────────────────────┘
```

Nhánh `main` (code) và nhánh `db-state` (chỉ chứa 1 file `data/news.db`, bị force-push đè mỗi lần chạy) hoàn toàn tách biệt — `main` không bao giờ bị workflow tự động commit vào, nên lịch sử code luôn sạch.

---

## 3. 23 nguồn tin và cách lấy dữ liệu

| # | Nguồn | Phương thức | Ghi chú kỹ thuật đặc biệt |
|---|-------|--------------|---------------------------|
| 1 | VnExpress | RSS | — |
| 2 | Tuổi Trẻ | RSS | `<pubDate>` dùng định dạng ngày kiểu Mỹ với dấu cách hẹp U+202F trước AM/PM — feedparser không parse được, phải tự viết parser riêng |
| 3 | CafeF | RSS | — |
| 4 | Vietstock | RSS | — |
| 5 | Thanh Niên | RSS | — |
| 6 | Dân Trí | RSS | — |
| 7 | VnEconomy | RSS | — |
| 8 | Znews | RSS | — |
| 9 | Tiền Phong | RSS | — |
| 10 | VietnamPlus | RSS | — |
| 11 | Nhân Dân | RSS | — |
| 12 | Chính phủ | RSS | — |
| 13 | VTV | RSS | 1 response có thể chứa tin trải dài nhiều tuần (không chỉ tin mới) |
| 14 | VietnamBiz | RSS | XML khai báo sai `encoding="utf-16"` trong khi bytes thật là UTF-8 → phải tự "sửa" phần khai báo trước khi feedparser parse (`RSSCrawlerBase._preprocess_raw()`) |
| 15 | CafeBiz | HTML scrape | Lọc bỏ khối "nổi bật" không có giờ đăng |
| 16 | Đầu tư Chứng khoán | HTML scrape | Trang danh sách thiếu giờ cho 1 số bài → fallback fetch trang chi tiết từng bài để lấy giờ thật |
| 17 | Diễn đàn Doanh nghiệp | HTML scrape | Cùng cơ chế fallback fetch trang chi tiết như trên |
| 18 | Báo Đầu tư | HTML scrape | Không có `published_at` cho bất kỳ bài nào (giới hạn của chính trang nguồn) — cùng cơ chế fallback, và khi fallback cũng thất bại thì dùng `first_seen_at` để không mất bài |
| 19 | FiLi | **JSON API** (reverse-engineered) | Trang chuyên mục là SPA AngularJS — endpoint thật là `POST /_Partials/ListPageArticle`; tham số `channelid` phải là chuỗi nhiều ID (chuyên mục cha + toàn bộ chuyên mục con) chứ không phải 1 ID đơn — phát hiện bằng cách soi network request thật của trang |
| 20 | VietnamNet | RSS | Feed ~1000 bài (tới đầu tháng 8), an toàn nhờ dedup + baseline riêng cho nguồn mới |
| 21 | Người Quan Sát | RSS | Chuyên tài chính/chứng khoán/BĐS |
| 22 | SGGP | RSS | Dùng `kinh-te-89.rss` (`kinhte-3.rss` thực chất là mục Đô thị) |
| 23 | VnExpress Intl | RSS | Tiêu đề tiếng Anh, không vào được issue (engine từ khoá tiếng Việt) |

**Tổng: 18 RSS + 4 HTML scrape + 1 JSON API = 23 nguồn.** (4 nguồn RSS mới thêm 2026-09-24: VietnamNet, Người Quan Sát, SGGP, VnExpress Intl.)

Tất cả crawler kế thừa `crawlers/base.py` (`RSSCrawlerBase` hoặc `BaseCrawler`), implement 1 phương thức `fetch()` trả về `List[NewsItem]`. Thêm nguồn mới = viết 1 file `crawlers/<site>.py` + thêm vào `crawlers/__init__.py`, không cần sửa gì khác.

---

## 4. Luồng 1 chu kỳ quét (`scheduler.run_cycle`)

1. **`crawl_all()`** — gọi `fetch()` của cả 23 crawler. Lỗi ở 1 nguồn (timeout, HTML đổi cấu trúc, API đổi format...) bị cô lập bằng try/except riêng — không làm sập cả chu kỳ, chỉ ghi log + tính vào `CrawlStatus` (nguồn nào lỗi, nguồn nào OK).
2. Với mỗi bài lấy được, `Database.insert_if_new()` chèn vào SQLite nếu **URL** (đã normalize — bỏ `fbclid`, `utm_*`, fragment `#...`) chưa từng thấy. Dedup theo URL, không theo tiêu đề (tiêu đề có thể bị sửa nhẹ giữa các lần đăng lại).
3. Bài mới được **nhóm theo nguồn** (giữ đúng thứ tự cấu hình trong `crawlers/__init__.py`), gắn cờ "nóng" nếu tiêu đề khớp `HOT_KEYWORDS`, rồi định dạng thành tin nhắn Telegram và gửi.
4. Chỉ sau khi Telegram xác nhận gửi thành công, `sent_at` mới được cập nhật trong DB — nếu Telegram lỗi, bài vẫn nằm trong DB (không mất), lần sau **không** gửi lại (đã có trong DB rồi) nhưng cũng không đánh dấu "đã gửi" giả — tránh vừa mất tin vừa gửi trùng.
5. **Lần chạy đầu tiên trên 1 DB trống** (`ensure_initial_baseline`): toàn bộ bài hiện có trên các trang được ghi nhận vào DB với cờ `initial_seen=1` nhưng **không gửi Telegram** (tránh dội hàng trăm tin cũ ngay lần đầu bật máy) — trừ khi `INITIAL_SCAN_SEND=true`. Nếu sau này thêm 1 nguồn mới vào 1 DB đã có dữ liệu, nguồn đó cũng được baseline riêng theo cùng logic (không dội tin cũ của riêng nguồn mới).
6. **Phát hiện nguồn "chết âm thầm"** (`_detect_stale_sources`): 1 nguồn vẫn trả về HTTP 200 nhưng ngừng có bài mới thật sự trong `STALE_SOURCE_HOURS` giờ (mặc định 24h) → cảnh báo qua Telegram, cooldown `STALE_ALERT_COOLDOWN_HOURS` giờ (mặc định 24h) để không spam cảnh báo mỗi 20 phút, tự gỡ cảnh báo khi nguồn hồi phục.
7. **`snapshot_data()`** (chạy ngay sau khi crawl xong, trước khi gửi Telegram): tính lại Top Issues của hôm nay và ghi vào bảng `issue_history`, tổng hợp số bài theo nguồn/chủ đề vào `daily_stats` — đây là dữ liệu nền cho tab Analytics (mục 10) và trang xuất dữ liệu (mục 12). Bước phụ, best-effort: lỗi chỉ ghi log, không làm hỏng chu kỳ crawl/gửi tin chính.
8. **`check_crisis()`** (ngay sau bước trên): gắn nhãn thương hiệu + sắc thái cho mọi bài, kiểm tra ngưỡng cảnh báo khủng hoảng theo thương hiệu, gửi Telegram nếu vượt ngưỡng và chưa trong thời gian cooldown — xem mục 11. Cũng là bước phụ, best-effort.

Nhịp quét: **cố định 20 phút/lần, cả ngày lẫn đêm** (`CRAWL_INTERVAL_MINUTES`, đã bỏ việc chia ca ngày/đêm theo yêu cầu đơn giản hoá).

---

## 5. Lưu trữ dữ liệu

- **SQLite** (`data/news.db`), 5 bảng:
  - `news`: `source, title, url (UNIQUE), published_at, first_seen_at, sent_at, initial_seen`.
  - `source_health`: `source, last_alerted_at` — phục vụ cooldown cảnh báo nguồn chết.
  - `daily_stats`, `issue_history`: dữ liệu nền cho tab Analytics — chi tiết ở mục 12.
  - `crisis_alerts`: `brand, level, last_alerted_at` — cooldown cảnh báo khủng hoảng theo thương hiệu, xem mục 11.
- **Vấn đề cần giải quyết:** GitHub Actions runner là máy ảo dùng 1 lần rồi xoá — nếu không lưu DB ở đâu đó bền vững, mỗi lần chạy sẽ coi mọi bài là "mới" và dội tin trùng lặp vô hạn.
- **Giải pháp:** nhánh Git orphan riêng **`db-state`**, chỉ chứa đúng 1 file `data/news.db`. Mỗi lần chạy: đọc DB cũ từ nhánh này (`git show`), chạy chu kỳ quét, rồi **force-push đè** 1 commit mới lên `db-state` bằng git plumbing thuần (`hash-object` → `mktree` → `commit-tree` → `push --force`) — không qua `git checkout`, nên không đụng tới working tree của `main` đang chạy trong cùng job. Không ai đọc lịch sử nhánh này nên force-push mỗi 20 phút không gây hại gì, và giữ `main` sạch (không cộng dồn hàng trăm commit "update db" mỗi ngày).
- **Backup:** timestamped snapshot của `news.db` vào `backup/`, tự xoá bản cũ hơn `BACKUP_KEEP_DAYS` (mặc định 14 ngày). Chạy tự động 03:00 mỗi ngày (`start_scheduler`) hoặc thủ công qua `python main.py --backup-now`.
- **Lưu trữ dài hạn theo tháng:** `python main.py --archive-old` ([archive.py](archive.py)) xuất bài cũ hơn `ARCHIVE_KEEP_DAYS` (mặc định 90 ngày) ra `data/archive/news-YYYY-MM.jsonl.gz`, mặc định chỉ xuất chứ không xoá khỏi `news`; xem mục 12.

---

## 6. Gửi Telegram

- Dùng thẳng HTTP Bot API qua `requests` (không dùng thư viện `python-telegram-bot` — thư viện đó async-first, nặng hơn mức cần cho đúng 1 POST đồng bộ/chu kỳ).
- **Định dạng tin nhắn:** nhóm theo nguồn, mỗi nguồn có icon riêng (`SOURCE_ICONS`, nguồn lạ chưa có icon thì lấy fallback theo hash tên nguồn — ổn định qua các lần restart nhờ dùng tổng mã ký tự thay vì `hash()` của Python, vốn bị randomize ngẫu nhiên mỗi lần chạy process), tiêu đề là link HTML bấm được, mở đầu bằng 1 dòng tóm tắt (mấy bài, từ mấy nguồn).
- **Tin "nóng":** tiêu đề khớp 1 trong các cụm từ `HOT_KEYWORDS` (`khẩn cấp`, `khủng hoảng`, `sập sàn`, `tăng vọt`, `lao dốc`, `kỷ lục`...) được tách riêng lên đầu tin nhắn — để không bị chìm lẫn giữa hàng chục tin bình thường khi lướt trên điện thoại. Danh sách này cố ý chọn theo cụm từ, không theo từ đơn lẻ như "tăng" (sẽ khớp gần như mọi tin).
- **Giới hạn 4096 ký tự/tin nhắn của Telegram:** tự động chia nhỏ thành nhiều tin nếu vượt giới hạn.
- **Retry:** gửi lỗi thì thử lại tối đa `MAX_RETRIES` lần (mặc định 3) trước khi coi là thất bại hẳn.
- **Định dạng giờ:** `dd/mm HH:MM` (không chỉ giờ) — vì VTV có thể trả về bài trải dài nhiều ngày trong 1 response, chỉ hiện giờ sẽ khiến các bài từ ngày khác nhau nhìn như bị xáo trộn thứ tự.
- **Cảnh báo khủng hoảng thương hiệu:** loại tin nhắn riêng (`format_crisis_alert`), tách biệt hoàn toàn khỏi digest bài mới thường ngày — xem mục 11.

---

## 7. Tự động hoá lịch trình — vì sao không dùng cron nội bộ của GitHub

**Vấn đề gặp phải:** GitHub Actions có sẵn trigger `schedule: cron:`, nhưng qua thực tế vận hành, cron này **liên tục bị "đơ"** hàng giờ liền sau mỗi lần sửa chuỗi cron — một lỗi phía GitHub, không phải lỗi code của dự án. Đã thử tắt/bật lại workflow trên UI — không ăn thua. Đổi tên file workflow (`crawl.yml` → `news-crawl.yml`) để buộc GitHub tạo workflow ID mới — có đỡ hơn nhưng vẫn tái phát.

**Giải pháp cuối cùng:** bỏ hẳn cron nội bộ của GitHub, dùng **cron-job.org** (dịch vụ lịch ngoài, miễn phí, đáng tin cậy hơn) để gọi 1 **Cloudflare Worker** mỗi 20 phút, Worker này gọi GitHub API để kích hoạt `workflow_dispatch` (chạy thủ công qua API, không phải qua `schedule:`).

**Vì sao cần Worker trung gian thay vì gọi thẳng GitHub API từ cron-job.org:** kích hoạt `workflow_dispatch` cần 1 token GitHub có quyền ghi (Actions: read/write). Không thể đặt token đó thẳng vào cron-job.org hay vào code của trang web — trang web là GitHub Pages build từ repo **public**, ai cũng xem được mã nguồn (View Source), nhúng token thẳng vào đó là công khai token cho cả Internet. Cloudflare Worker (`web/cloudflare-worker/worker.js`) là nơi duy nhất giữ token thật — nằm trong environment của Cloudflare (secret, mã hoá), không bao giờ lộ ra ngoài. Trang web/cron-job.org chỉ biết URL public của Worker.

Nút **"Quét ngay"** trên trang web dùng đúng cơ chế này để người dùng tự kích hoạt quét thủ công ngay từ trình duyệt.

---

## 8. Trang web (GitHub Pages) — khung ứng dụng SaaS responsive

Sinh hoàn toàn từ `data/news.db` mỗi lần crawl (`web/generate_site.py` lắp ráp nội dung, `web/theme.py` giữ toàn bộ khung ứng dụng/CSS/JS — chạy `python -m web.generate_site` để xem thử cục bộ) — **zero build tool**, HTML/CSS/JS thuần. Trải qua 3 lần thiết kế lại: v1 neo-brutalist/Kanban-first → v2.0 "editorial newsroom" (tham khảo Financial Times/Reuters/Bloomberg) → **v3 hiện tại**, khung "SaaS dashboard" theo 1 bản đặc tả handoff riêng cho desktop/tablet/mobile, áp dụng cho cả 3 trang (Tổng quan, Brands, Analytics).

**Bố cục khung** (`render_shell` trong `web/theme.py`):

| | Desktop (≥1024px) | Tablet (768–1023px) | Mobile (<768px) |
|---|---|---|---|
| Sidebar | 260px, thu gọn còn 68px (nhớ lựa chọn qua `localStorage`) | Ép cố định 68px | Biến thành drawer trượt từ trái (`min(320px, 85vw)`), có backdrop, đóng bằng bấm ngoài/ESC/chọn mục, khoá focus |
| Header | 64px | 60px | 56px, có nút hamburger |
| Điều hướng phụ | — | — | Bottom navigation 5 mục cố định dưới màn hình |
| Thẻ KPI | 4 cột | 2 cột | 1 cột |
| Bảng tin | Bảng 4 cột có sticky header | Bảng rút gọn 3 cột | Mỗi tin 1 thẻ (card) |
| Bộ lọc | Nằm ngay trên bảng tin | Nằm ngay trên bảng tin | Nút "Bộ lọc" mở bottom sheet (Đặt lại/Áp dụng) |

Sidebar chia 4 nhóm điều hướng: **Chính** (Tổng quan, Issues, Tin tức), **Phân tích** (Brands, Analytics — chỉ hiện khi có dữ liệu), **Quản lý** (Theo nguồn, Lưu trữ), **Dữ liệu** (RSS feed, Dữ liệu JSON). Toàn bộ tương tác đóng/mở dùng `<details>/<summary>` gốc của HTML khi có thể (cột nguồn, thẻ issue/analytics); JS chỉ phục vụ: drawer/sidebar/bottom-sheet, nút "Quét ngay", tìm kiếm + lọc + sắp xếp + phân trang của All news, dropdown chọn ngày.

**Nội dung trang Tổng quan** (`render_day_page`): banner "xem tin mới nhất" (nếu đang ở trang lưu trữ) → tiêu đề trang + nút "Quét ngay" → 4 thẻ KPI (bài viết hôm nay kèm % so với hôm qua cùng giờ, số nguồn có bài, số issue nổi bật, giờ cập nhật) → lưới 12 cột (Top Issues 8 cột + panel "Nguồn đăng nhiều nhất" 4 cột) → bảng "Tin tức" hợp nhất 23 nguồn (tìm kiếm, lọc nguồn/issue/thương hiệu, sắp xếp Mới nhất/Đang hot, phân trang 15 tin/trang, trạng thái rỗng có nút "Xoá bộ lọc") → "Theo nguồn" (Kanban cũ, vẫn nguyên logic, không tô màu riêng theo nguồn) → "Lưu trữ" (7 tab ngày + dropdown "Ngày khác").

**"Ngày mới nhất" được xác định như thế nào:** là ngày dương lịch **mới nhất có ít nhất 1 bài đã crawl được** trong dữ liệu — không phải theo đồng hồ hệ thống. Ngay sau nửa đêm, cho tới khi có bài đầu tiên của ngày mới được quét về (tối đa ~1 chu kỳ 20 phút), trang chủ tạm thời vẫn hiện lại ngày hôm qua (banner "xem tin mới nhất" giảm nhầm lẫn, chưa sửa tận gốc — xem mục 15).

**Ngôn ngữ hình ảnh:** font chính **Inter** (đã kiểm tra có bộ subset Unicode riêng cho tiếng Việt trong response CSS2 thật của Google Fonts trước khi dùng — rút kinh nghiệm từ lỗi font "Archivo Black" ở bản v1 thiếu dấu tiếng Việt), font phụ **IBM Plex Mono** cho số liệu/nhãn. Bảng màu hiện tại là tone **SaaS trung tính lạnh** (nền xám xanh `#F6F7F9`, chữ `#0F172A`, accent xanh dương `#2563EB`, cảnh báo/tiêu cực đỏ `#DC2626`) — đổi từ tone editorial be ấm/xanh rêu của bản v2.0 theo yêu cầu. Bộ icon SVG tự vẽ dùng chung 1 chỗ (`<symbol>` trong `web/theme.py`), không emoji, không gradient/glassmorphism, viền mỏng 1px + bóng gần như vô hình. Có `aria-current`/`aria-expanded`, focus rõ, tôn trọng `prefers-reduced-motion`. Chưa có dark mode.

---

## 9. Issue Intelligence V3 — thuật toán "Top Issues hôm nay"

Module: [web/issues.py](web/issues.py). Hoàn toàn rule-based, **không dùng AI/LLM/embedding** — cùng tinh thần "danh sách từ khoá tự chọn tay" như `HOT_KEYWORDS` của Telegram, cần tinh chỉnh dần theo dữ liệu thật.

### Entity ≠ Topic ≠ Issue

Nguyên tắc cốt lõi, khác hẳn bản "trending" đời đầu (gộp theo cụm từ trùng lặp bất kỳ, dễ gộp nhầm 2 tin không liên quan chỉ vì chung 1 từ):

- **Entity** (thực thể — tên riêng): 1 từ viết hoa toàn bộ dài ≥2 ký tự (vd "SCIC", "EIB" — trừ các từ trong `_GENERIC_ACRONYMS` như "HĐQT", "CEO", "IPO", "USD" — đây là chức danh/đơn vị chung, không phải tên riêng công ty cụ thể), **hoặc** 1 từ viết hoa chữ cái đầu dài ≥6 ký tự (vd "Eximbank", "Vietcombank" — ngưỡng 6 ký tự để loại các từ ngắn như "Trung" trong "Trung Quốc").
- **Topic** (chủ đề): nhãn tài chính lấy từ danh sách `_TOPIC_KEYWORDS` tự chọn tay (lãi suất, tăng vốn, nhân sự lãnh đạo, nợ xấu, cổ tức, trái phiếu, sáp nhập, niêm yết, khối ngoại, tỷ giá, giá vàng, bất động sản, chứng khoán, thuế, fed...).
- **Issue** (sự kiện cụ thể): **luôn luôn** là 1 cặp — **(entity, topic)** hoặc **(topic, topic)** — không bao giờ chỉ 1 entity trơn hay 1 topic trơn. Vì vậy "Eximbank tăng lãi suất" và "Eximbank tuyển dụng" luôn là 2 issue khác nhau dù chung entity "Eximbank".

**Lỗi thật đã phát hiện và sửa (2026-09-16):** tin "Eximbank gia hạn đề cử nhân sự HĐQT" (Vietstock, FiLi) từng bị gộp nhầm với tin hoàn toàn không liên quan "Cựu HLV trưởng bóng đá Việt Nam tham gia HĐQT một công ty khai thác cảng" (Dân Trí) — chỉ vì cả 2 cùng nhắc tới từ "HĐQT" (Hội đồng quản trị, một chức danh chung mà công ty nào cũng có, không phải tên riêng). Phát hiện qua kiểm tra trên dữ liệu sản xuất thật, sửa bằng cách thêm `_GENERIC_ACRONYMS` — có test hồi quy riêng (`test_generic_role_acronym_does_not_falsely_merge_unrelated_companies`) đảm bảo không tái phát.

### HotScore

Mỗi issue được chấm 4 thành phần, mỗi thành phần chuẩn hoá **riêng** về thang 0-100 (so với giá trị cao nhất trong đợt tính hiện tại, và **được lộ ra để dò lỗi** chứ không chỉ có điểm tổng), rồi nhân trọng số theo đúng công thức người dùng yêu cầu:

```
├── Số bài đề cập (volume_score)         40%
├── Số nguồn đề cập (source_score)       25%
├── Tốc độ xuất hiện (velocity_score)    20%   — số bài / số giờ kể từ lần đầu thấy issue
└── Mức độ mới/tăng tốc (novelty_score)  15%   — so nhịp ra bài 1/4 thời gian gần nhất
                                                  với trước đó, cộng số nguồn mới xuất hiện gần đây
```

**Giới hạn thật đã biết:** trọng số 25% cho đa dạng nguồn là 1 "lực đối trọng" chứ không phải "phủ quyết" tuyệt đối — 1 nguồn đăng đủ nhiều tin gần giống nhau vẫn có thể vượt điểm 1 issue thật sự đa nguồn nếu chênh lệch số bài đủ lớn (có test minh chứng riêng cho giới hạn này).

### Các cơ chế đảm bảo chất lượng khác

- **Cửa sổ tính:** đúng 1 ngày dương lịch theo giờ Việt Nam (`Asia/Ho_Chi_Minh`), không phải cửa sổ trượt 48 giờ như bản đầu tiên.
- **Ngưỡng ổn định xếp hạng** (chống 1 issue "rung" lên xuống top 5 chỉ vì 1-2 bài lẻ tẻ): phải đạt `article_count >= 3` **HOẶC** `unique_source_count >= 2`, cấu hình được qua tham số `top_issues(min_articles=..., min_sources=...)`.
- **"Vì sao hot" (why_hot):** 2-4 dòng giải thích sinh thẳng từ số liệu đã tính (số nguồn, số bài, có tăng tốc hay không, có nguồn mới hay không) — không bịa, không suy diễn.
- **Chống trùng lặp gần đúng:** 2 issue key phủ gần hết cùng 1 tập bài (vd "topic_topic" và "entity_topic" cùng match phần lớn bài giống nhau) được gộp, ưu tiên key bao phủ nhiều bài hơn, sau đó ưu tiên `entity_topic` (cụ thể hơn) trước `topic_topic`.

---

## 10. Analytics — phân tích dòng tin

Module [web/analytics.py](web/analytics.py), hiện ở **trang riêng `analytics.html`** (không nhúng vào trang chủ để trang chủ luôn nhẹ). Tính thuần từ các bài đã thu thập, không AI, không dữ liệu ngoài, dùng chung từ vựng Entity/Topic/Issue với `web/issues.py`. Các khối:

1. **Ai đưa tin trước** — với mỗi issue nhiều nguồn trong ngày, nguồn nào đăng sớm nhất và các nguồn khác trễ bao nhiêu phút; bảng xếp hạng 7 ngày (chỉ hiện nguồn tham gia ≥2 issue để tránh số liệu ngẫu nhiên).
2. **Khoảng trống đưa tin** — issue chỉ 1 nguồn đưa (≥3 bài, có thể là tin độc quyền hoặc 1 báo tự đăng lặp), và issue ≥4 nguồn đưa nhưng thiếu các báo lớn (10 nguồn đăng nhiều nhất).
3. **Độ trễ thu thập** — `first_seen_at − published_at` theo nguồn (trung vị, P90), bỏ độ trễ >6 giờ (backfill/baseline).
4. **Nhịp đăng bài theo giờ** — histogram 24 giờ + giờ đăng nhiều nhất/tỷ lệ đăng đêm (0-6h) từng nguồn.
5. **Lịch sử Top Issues** (`issue_streaks`, đọc từ bảng `issue_history` — mục 12) — issue nào từng lọt Top 5 mấy ngày, có đang "hot liên tiếp" tính đến hôm nay không, hạng cao nhất và điểm cao nhất từng đạt.
6. **Xu hướng 30 ngày** (`trend_from_stats`, đọc từ bảng `daily_stats` — mục 12, không quét lại toàn bộ bài) + **khối lượng theo chủ đề 14 ngày** tính trực tiếp từ dữ liệu hiện có.
7. **Tin đăng lặp** — tiêu đề gần giống (≥80% từ, **cùng các con số** trong tiêu đề) do cùng 1 báo đăng lại trong 24 giờ; điều kiện "cùng con số" để loại bản tin mẫu hằng ngày (vd "Top cổ phiếu... phiên 15/09" vs "...16/09") khỏi bị tính nhầm là đăng lặp — lỗi thật phát hiện khi chạy trên dữ liệu sản xuất.
8. **Đồng xuất hiện** — cặp đối tượng+chủ đề và đối tượng+đối tượng hay đi cùng nhau, 7 ngày gần nhất (đã lọc các token nhiễu như "TP"/"HCM"/"VN" tách từ tên địa danh).
9. **Hồ sơ chủ đề từng nguồn** — heatmap tỷ lệ bài của mỗi nguồn thuộc từng chủ đề.

Mọi thống kê theo nguồn đều bị ẩn khi có <5 mẫu.

---

## 11. Theo dõi thương hiệu & cảnh báo khủng hoảng

Dành cho phòng truyền thông/PR ngành ngân hàng - tài chính. Toàn bộ là luật + từ khoá (không AI), mọi nhãn đều kèm từ khoá đã kích hoạt để người dùng kiểm chứng. Module: [web/brands.py](web/brands.py) (nhận diện thương hiệu), [web/sentiment.py](web/sentiment.py) (sắc thái), [web/brandwatch.py](web/brandwatch.py) (share of voice + cảnh báo). Hiện ở trang riêng `brands.html`.

**Từ điển & watchlist:**
- Từ điển sẵn có ~28 ngân hàng (tên + mã + tên cũ, vd "Vietcombank / VCB / Ngân hàng Ngoại thương") và Ngân hàng Nhà nước.
- Mã ngắn viết hoa (≤4 ký tự: `MB`, `ACB`, `VIB`...) khớp **phân biệt hoa/thường** và theo ranh giới từ, để "20 mb" hay "5MB" không bị nhận nhầm.
- [watchlist.json](watchlist.json) (nằm ở thư mục gốc, hiện để trống = theo dõi cả từ điển): `own` (thương hiệu của mình), `competitors`, `extra_aliases`, `extra_brands`, `extra_negative_keywords`. Tên lạ trong `own`/`competitors` tự thành thương hiệu tuỳ chỉnh. ⚠ File này nằm trong repo **public**, không đưa thông tin nội bộ nhạy cảm vào.

**Sắc thái** — 3 mức từ khoá xấu (nghiêm trọng: khởi tố, vỡ nợ, rút tiền ồ ạt...; mạnh: tin đồn, bị phạt, rò rỉ...; nhẹ: nợ xấu, cảnh báo, rủi ro...) và từ khoá tích cực. Chỉ mức mạnh/nghiêm trọng mới tính vào cảnh báo khủng hoảng. Hai quy tắc giảm sai lầm, tìm ra từ chạy thử trên dữ liệu thật: (1) tiêu đề **bác bỏ/đính chính** ("bác bỏ tin đồn") là phản hồi của ngân hàng → trung tính; (2) tiêu đề mô tả **nỗ lực bảo vệ** ("mở rộng tính năng cảnh báo lừa đảo") không bị coi là tin xấu. Đây là **ước lượng từ tiêu đề**, không phải kết luận.

**Share of voice** — tỷ trọng số tin nhắc tới mỗi thương hiệu trong tổng tin của các thương hiệu theo dõi, 7 và 30 ngày, kèm số nguồn, tích cực/tiêu cực/trung tính, % tiêu cực, so kỳ trước. Một tiêu đề nhắc nhiều thương hiệu tính cho từng thương hiệu (cố ý thiên về báo thừa hơn bỏ sót).

**Cảnh báo khủng hoảng** (`scheduler.check_crisis`, chạy mỗi chu kỳ): ≥3 báo khác nhau đăng tin tiêu cực mức mạnh về cùng 1 thương hiệu trong 60 phút → "leo thang"; ≥2 báo với từ khoá nghiêm trọng → "khẩn". Gửi Telegram kèm từ khoá và từng tiêu đề; mỗi thương hiệu tối đa 1 cảnh báo/3 giờ (bảng `crisis_alerts`), riêng "khẩn" được vượt cooldown của "leo thang". Gửi lỗi thì không ghi nhận, chu kỳ sau thử lại. Cấu hình qua `CRISIS_MIN_SOURCES`, `CRISIS_WINDOW_MINUTES`, `CRISIS_COOLDOWN_HOURS`. Bước phụ best-effort: lỗi chỉ ghi log.

**Trên web:** tab `Brands` (4 thẻ KPI, cảnh báo hiện hành, 2 bảng share of voice 7/30 ngày, số tin theo 14 ngày, tin tiêu cực gần đây), mỗi dòng "Tin tức" có chấm màu sắc thái + nhãn thương hiệu, bộ lọc theo thương hiệu, xuất `brands.json`.

---

## 12. Hạ tầng dữ liệu

- **`daily_stats`** (`day, kind, name, articles`; kind = `source`/`topic`): số bài theo ngày/nguồn/chủ đề, tổng hợp sẵn để tab Analytics không phải quét lại toàn bộ bài mỗi lần build. Lần đầu (bảng trống) backfill toàn bộ lịch sử, sau đó mỗi chu kỳ chỉ tính lại 3 ngày gần nhất.
- **`issue_history`** (`day, issue_id, title, rank, hot_score, article_count, source_count, first_seen_at, last_seen_at, updated_at`): mỗi ngày mỗi issue từng lọt Top 5 có 1 dòng (giá trị của chu kỳ mới nhất, upsert). Issue vốn tính lại từ đầu mỗi lần và biến mất khi qua ngày — bảng này là nền cho "Lịch sử Top Issues" ở mục 10.
- **Vì sao ghi trong `run_cycle` (`scheduler.snapshot_data`) chứ không phải lúc build site:** workflow đẩy `news.db` lên nhánh `db-state` *trước* bước build site; dữ liệu ghi lúc build sẽ không bao giờ được lưu. Bảng mới tạo bằng `CREATE TABLE IF NOT EXISTS` nên DB cũ trên `db-state` tự nâng cấp.
- **Xuất dữ liệu** ([web/exports.py](web/exports.py)), ghi cạnh các trang HTML mỗi lần build: `issues.json` (Top Issues + 4 thành phần HotScore), `stats.json` (`daily_stats` + `issue_history`), `feed.xml` (RSS 100 bài mới nhất, URL kênh lấy từ `NEWS_SITE_URL`), `brands.json` (share of voice + cảnh báo khủng hoảng — mục 11).
- **Lưu trữ theo tháng** ([archive.py](archive.py)): `python main.py --archive-old` xuất bài cũ hơn `ARCHIVE_KEEP_DAYS` (mặc định 90) ra `data/archive/news-YYYY-MM.jsonl.gz`. **Mặc định chỉ xuất, không xoá**; thêm `--delete-archived` mới xoá khỏi DB (khi đó các ngày đó biến mất khỏi trang lưu trữ, và nguồn có feed dài như VietnamNet — ~2 tháng — có thể nạp lại URL đã xoá nếu `ARCHIVE_KEEP_DAYS` quá nhỏ). **Cố ý không gắn vào CI** vì file archive không nằm trên nhánh `db-state`, chạy ở đó sẽ mất.

---

## 13. Testing

**201 test** (`pytest`), chạy hoàn toàn offline bằng fixture lấy từ dữ liệu thực tế lúc audit — không cần mạng, mock qua thư viện `responses`.

| File | Phạm vi |
|------|---------|
| `test_crawlers.py`, `test_html_crawlers.py`, `test_fili_crawler.py` | Parse RSS cho 18 nguồn, HTML scrape cho 4 nguồn, JSON API cho FiLi — bao gồm mọi lỗi thật đã phát hiện qua audit (ngày phi chuẩn, encoding sai, thiếu giờ, cấu trúc trang đổi) |
| `test_database.py` | Dedup theo URL, baseline seeding lần đầu + baseline riêng cho nguồn mới thêm vào DB đã có dữ liệu |
| `test_telegram.py` | Định dạng tin nhắn, tách tin nóng, chia nhỏ khi vượt 4096 ký tự, retry khi lỗi |
| `test_scheduler.py` | Toàn bộ luồng `run_cycle` (dry-run/thành công/lỗi 1 phần/tất cả lỗi), cô lập lỗi từng nguồn, phát hiện + cooldown cảnh báo nguồn chết, lịch quét cố định đúng chu kỳ |
| `test_backup.py` | Backup có timestamp, tự xoá bản cũ |
| `test_utils.py` | Chuẩn hoá URL (bỏ `fbclid`/`utm_*`/fragment) |
| `test_generate_site.py` | Sinh trang web: gom đúng ngày, escape XSS, cửa sổ 7-tab ngày, nút Quét ngay, phân trang, banner "xem tin mới nhất", tích hợp Top Issues, khung SaaS (sidebar/nav/KPI), trang Brands/Analytics riêng, các file xuất dữ liệu |
| `test_issues.py` | Cả 8 kịch bản test bắt buộc theo đặc tả Issue Intelligence V3 (gộp đúng issue giống nhau, không gộp nhầm cùng entity khác topic, không gộp nhầm cùng topic khác entity, đa dạng nguồn, chống thiên vị khối lượng, "vì sao hot" đúng số liệu, ổn định xếp hạng, đúng múi giờ) + regression test cho lỗi "HĐQT" |
| `test_analytics.py` | 8 khối phân tích dòng tin ở mục 10 (ai đưa trước, khoảng trống đưa tin, độ trễ, nhịp giờ, khối lượng theo chủ đề, đăng lặp — kể cả case bản tin mẫu theo ngày không bị tính nhầm, đồng xuất hiện, hồ sơ chủ đề) |
| `test_brandwatch.py` | Từ điển thương hiệu (mã viết hoa phân biệt hoa/thường, ranh giới từ), watchlist tuỳ chỉnh, sắc thái (kể cả case bác bỏ tin đồn và nỗ lực bảo vệ không bị tính tiêu cực), share of voice, ngưỡng cảnh báo khủng hoảng, cooldown + "khẩn" vượt cooldown của "leo thang" trong `scheduler.check_crisis` |
| `test_datainfra.py` | Bảng `daily_stats`/`issue_history`, `snapshot_data` (kể cả không được raise lỗi), các hàm xuất `issues.json`/`stats.json`/`feed.xml`, lưu trữ theo tháng (xuất không xoá theo mặc định, xoá + giữ nguyên file khi chạy lại) |

---

## 14. Cấu trúc thư mục

```
news-monitor/
├── main.py                 # CLI: --run-once / --dry-run / --backup-now / (mặc định: scheduler)
├── scheduler.py            # crawl_all, run_cycle, baseline, phát hiện nguồn chết, APScheduler
├── config.py                # đọc .env, mọi hằng số cấu hình
├── database.py              # SQLite: schema, insert_if_new, get_all_articles
├── models.py                 # dataclass NewsItem
├── telegram.py                # định dạng + gửi tin Telegram
├── backup.py                   # backup DB có timestamp
├── utils.py                     # normalize_url
├── logger.py                     # setup logging
├── archive.py                      # lưu trữ bài cũ theo tháng (--archive-old)
├── watchlist.json                   # thương hiệu của mình/đối thủ theo dõi (mục 11)
├── crawlers/                          # 23 crawler, 1 file/nguồn + base.py
├── web/
│   ├── theme.py                        # khung ứng dụng SaaS: CSS, icon SVG, render_shell (mục 8)
│   ├── generate_site.py                # lắp ráp nội dung từng trang, gọi render_shell
│   ├── issues.py                        # Issue Intelligence V3 (Entity/Topic/Issue, HotScore)
│   ├── analytics.py                      # phân tích dòng tin (mục 10)
│   ├── brands.py                          # từ điển thương hiệu + watchlist (mục 11)
│   ├── sentiment.py                        # sắc thái theo luật + từ khoá (mục 11)
│   ├── brandwatch.py                        # share of voice + cảnh báo khủng hoảng (mục 11)
│   ├── exports.py                            # issues.json/stats.json/feed.xml/brands.json (mục 12)
│   └── cloudflare-worker/worker.js            # proxy bảo mật cho nút "Quét ngay"
├── tests/                                       # 201 test, xem mục 13
├── data/news.db                                  # SQLite (local dev; trên CI lấy từ nhánh db-state)
├── data/archive/                                  # file lưu trữ theo tháng (--archive-old)
├── backup/                                         # snapshot DB có timestamp
├── site/                                            # HTML/JSON/RSS sinh ra (gitignored)
├── .github/workflows/news-crawl.yml                  # toàn bộ pipeline CI/CD
├── README.md / GIOI-THIEU.md / GIAO-DIEN.md / TONG-QUAN-DU-AN.md (file này)
```

---

## 15. Giới hạn đã biết

- **HotScore không phải "phủ quyết" tuyệt đối cho đa dạng nguồn** (mục 9) — 1 nguồn đăng nhiều tin gần giống nhau vẫn có thể thắng điểm 1 issue thật sự đa nguồn nếu chênh lệch số bài đủ lớn.
- **"Ngày mới nhất" trễ tối đa ~20 phút sau nửa đêm** cho tới khi có bài đầu tiên của ngày mới (mục 8) — đã thêm banner "xem tin mới nhất" để giảm nhầm lẫn, nhưng chưa sửa tận gốc để trang tự bám theo đồng hồ thật (người dùng đã được hỏi, chọn giữ nguyên).
- **Chưa có dark mode** ở giao diện hiện tại.
- **Danh sách từ khoá (`HOT_KEYWORDS`, `_TOPIC_KEYWORDS`, `_GENERIC_ACRONYMS`, sắc thái ở mục 11) là tự chọn tay**, không phải NLP thật — cần tinh chỉnh dần khi phát hiện case sai qua vận hành thực tế, không phải giải pháp hoàn hảo 1 lần là xong. Chưa đo precision/recall trên tập dữ liệu dán nhãn tay, nên không có con số "độ chính xác X%" đáng tin để công bố.
- **API trạng thái của GitHub Actions có thể báo "in_progress" cũ hàng chục phút** dù job thật đã chạy xong từ lâu (gặp thực tế nhiều lần) — luôn nên kiểm tra bằng nội dung trang live thay vì tin tuyệt đối vào API trạng thái khi cần xác minh deploy đã xong hay chưa.
- **Theo dõi thương hiệu (tab Brands) chỉ dựa vào tiêu đề** (mục 11): bài nhắc tên ngân hàng ở thân bài mà không có trong tiêu đề sẽ bị bỏ sót, và sắc thái chỉ là ước lượng bằng từ khoá (dễ sai với châm biếm, trích dẫn, tiêu đề chỉ gợi ý). Cảnh báo khủng hoảng vì thế là "đáng xem", không phải kết luận — luôn cần người xác nhận, chưa có bước ghi nhận ai đã xác nhận.
- **"Ai đưa tin trước" (mục 10) chỉ là ước lượng**, gộp theo issue (cùng đối tượng+chủ đề trong ngày) nên đôi khi ghép nhầm 2 sự kiện khác nhau cùng chủ đề.
- **Riêng tư:** trang web và `watchlist.json` nằm trong repo/GitHub Pages **công khai**. Dùng cho mục đích nội bộ của 1 tổ chức (danh sách thương hiệu mình theo dõi, đối thủ) thì cần host riêng tư hoặc thêm đăng nhập trước khi đưa thông tin nhạy cảm vào.
- **Bản quyền:** hệ thống chỉ lưu tiêu đề + đường dẫn gốc (an toàn). Lưu/phát lại toàn văn bài báo để làm báo cáo thương mại cần được các báo cho phép.
- **Chưa có tuyên bố miễn trừ/điều khoản sử dụng** — cần ghi rõ đây không phải tư vấn đầu tư trước khi đưa ra ngoài phạm vi cá nhân.
- **Vận hành:** CI hiện không chạy `pytest` trước khi deploy (code lỗi có thể lên production ở lần chạy kế tiếp); backup (`--backup-now`) không được gọi trong workflow CI (chỉ gắn với chế độ scheduler chạy dài hạn); không có giám sát độc lập cho chuỗi cron-job.org → Cloudflare Worker → GitHub Actions — nếu 1 mắt xích ngừng chạy, hệ thống im lặng không ai biết.
- **Báo Đầu tư không có `published_at` cho bất kỳ bài nào** (giới hạn của chính trang nguồn, không phải lỗi crawler) — mọi bài của nguồn này hiển thị giờ `--:--` khi không fetch được trang chi tiết.

---

## 16. Chạy / phát triển cục bộ

```bash
# Cài dependency
pip install -r requirements.txt

# Xem thử trang web (không cần mạng, không cần Telegram)
python -m web.generate_site
# rồi mở site/index.html bằng trình duyệt

# Chạy thử 1 chu kỳ quét, in ra kết quả, không ghi DB, không gửi Telegram
python main.py --dry-run

# Lưu trữ bài cũ hơn ARCHIVE_KEEP_DAYS (mặc định chỉ xuất, không xoá)
python main.py --archive-old

# Chạy test
pytest
```

Cấu hình qua `.env` (copy từ `.env.example`) — bắt buộc `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` khi chạy thật (không cần cho `--dry-run`). Muốn tab Brands phân biệt "của mình"/"đối thủ" thay vì theo dõi cả từ điển, sửa [watchlist.json](watchlist.json) ở thư mục gốc (mục 11). Chi tiết đầy đủ từng biến ở [README.md](README.md).
