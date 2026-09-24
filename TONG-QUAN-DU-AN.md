# Vietnam News Monitor — Tổng quan dự án (đầy đủ chi tiết)

> Tài liệu này là bản tổng hợp **đầy đủ nhất**, gộp toàn bộ kiến trúc, luồng xử lý, thuật toán, lịch sử quyết định kỹ thuật và giới hạn đã biết của dự án vào 1 file duy nhất. Các tài liệu khác trong repo phục vụ mục đích hẹp hơn:
> - [README.md](README.md) — tài liệu kỹ thuật gốc, chi tiết cấp code, dùng khi cần tra cứu implementation cụ thể.
> - [GIOI-THIEU.md](GIOI-THIEU.md) — bản giới thiệu ngắn gọn, phi kỹ thuật, để gửi cho người không rành code.
> - [GIAO-DIEN.md](GIAO-DIEN.md) — riêng phần giao diện web (v2.0 editorial redesign).
>
> Repo: `ninhphu321/vietnam-news-monitor` (public). Trang web live: https://ninhphu321.github.io/vietnam-news-monitor/

---

## 1. Dự án này làm gì

Một hệ thống **tự động, chạy 24/7, miễn phí hoàn toàn**, quét 23 trang báo tài chính/kinh doanh Việt Nam mỗi 20 phút, phát hiện bài viết mới (chưa từng thấy), rồi:

1. Gửi thông báo qua **Telegram** (nhóm theo nguồn, đánh dấu tin "nóng").
2. Cập nhật một **trang web tĩnh** (GitHub Pages) hiển thị lại toàn bộ tin theo ngày, kèm 1 bảng "Top Issues" tự phát hiện các sự kiện đang được nhiều báo cùng đưa tin.

Không dùng AI/LLM ở bất kỳ đâu trong hệ thống — toàn bộ là rule-based (RSS parsing, regex, từ khoá tự chọn tay, HotScore tính bằng công thức cố định). Không có server riêng, không trả phí cho bất kỳ dịch vụ nào (GitHub Actions free tier, GitHub Pages free, Cloudflare Workers free tier, cron-job.org free).

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
                                          │  3. Gửi Telegram (nếu có   │
                                          │     bài mới)                │
                                          │  4. Đẩy news.db mới lên     │
                                          │     nhánh db-state          │
                                          │  5. Sinh lại site/ tĩnh      │
                                          │  6. Deploy lên GitHub Pages  │
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

Nhịp quét: **cố định 20 phút/lần, cả ngày lẫn đêm** (`CRAWL_INTERVAL_MINUTES`, đã bỏ việc chia ca ngày/đêm theo yêu cầu đơn giản hoá).

---

## 5. Lưu trữ dữ liệu

- **SQLite** (`data/news.db`), 2 bảng:
  - `news`: `source, title, url (UNIQUE), published_at, first_seen_at, sent_at, initial_seen`.
  - `source_health`: `source, last_alerted_at` — phục vụ cooldown cảnh báo nguồn chết.
- **Vấn đề cần giải quyết:** GitHub Actions runner là máy ảo dùng 1 lần rồi xoá — nếu không lưu DB ở đâu đó bền vững, mỗi lần chạy sẽ coi mọi bài là "mới" và dội tin trùng lặp vô hạn.
- **Giải pháp:** nhánh Git orphan riêng **`db-state`**, chỉ chứa đúng 1 file `data/news.db`. Mỗi lần chạy: đọc DB cũ từ nhánh này (`git show`), chạy chu kỳ quét, rồi **force-push đè** 1 commit mới lên `db-state` bằng git plumbing thuần (`hash-object` → `mktree` → `commit-tree` → `push --force`) — không qua `git checkout`, nên không đụng tới working tree của `main` đang chạy trong cùng job. Không ai đọc lịch sử nhánh này nên force-push mỗi 20 phút không gây hại gì, và giữ `main` sạch (không cộng dồn hàng trăm commit "update db" mỗi ngày).
- **Backup:** timestamped snapshot của `news.db` vào `backup/`, tự xoá bản cũ hơn `BACKUP_KEEP_DAYS` (mặc định 14 ngày). Chạy tự động 03:00 mỗi ngày (`start_scheduler`) hoặc thủ công qua `python main.py --backup-now`.

---

## 6. Gửi Telegram

- Dùng thẳng HTTP Bot API qua `requests` (không dùng thư viện `python-telegram-bot` — thư viện đó async-first, nặng hơn mức cần cho đúng 1 POST đồng bộ/chu kỳ).
- **Định dạng tin nhắn:** nhóm theo nguồn, mỗi nguồn có icon riêng (`SOURCE_ICONS`, nguồn lạ chưa có icon thì lấy fallback theo hash tên nguồn — ổn định qua các lần restart nhờ dùng tổng mã ký tự thay vì `hash()` của Python, vốn bị randomize ngẫu nhiên mỗi lần chạy process), tiêu đề là link HTML bấm được, mở đầu bằng 1 dòng tóm tắt (mấy bài, từ mấy nguồn).
- **Tin "nóng":** tiêu đề khớp 1 trong các cụm từ `HOT_KEYWORDS` (`khẩn cấp`, `khủng hoảng`, `sập sàn`, `tăng vọt`, `lao dốc`, `kỷ lục`...) được tách riêng lên đầu tin nhắn — để không bị chìm lẫn giữa hàng chục tin bình thường khi lướt trên điện thoại. Danh sách này cố ý chọn theo cụm từ, không theo từ đơn lẻ như "tăng" (sẽ khớp gần như mọi tin).
- **Giới hạn 4096 ký tự/tin nhắn của Telegram:** tự động chia nhỏ thành nhiều tin nếu vượt giới hạn.
- **Retry:** gửi lỗi thì thử lại tối đa `MAX_RETRIES` lần (mặc định 3) trước khi coi là thất bại hẳn.
- **Định dạng giờ:** `dd/mm HH:MM` (không chỉ giờ) — vì VTV có thể trả về bài trải dài nhiều ngày trong 1 response, chỉ hiện giờ sẽ khiến các bài từ ngày khác nhau nhìn như bị xáo trộn thứ tự.

---

## 7. Tự động hoá lịch trình — vì sao không dùng cron nội bộ của GitHub

**Vấn đề gặp phải:** GitHub Actions có sẵn trigger `schedule: cron:`, nhưng qua thực tế vận hành, cron này **liên tục bị "đơ"** hàng giờ liền sau mỗi lần sửa chuỗi cron — một lỗi phía GitHub, không phải lỗi code của dự án. Đã thử tắt/bật lại workflow trên UI — không ăn thua. Đổi tên file workflow (`crawl.yml` → `news-crawl.yml`) để buộc GitHub tạo workflow ID mới — có đỡ hơn nhưng vẫn tái phát.

**Giải pháp cuối cùng:** bỏ hẳn cron nội bộ của GitHub, dùng **cron-job.org** (dịch vụ lịch ngoài, miễn phí, đáng tin cậy hơn) để gọi 1 **Cloudflare Worker** mỗi 20 phút, Worker này gọi GitHub API để kích hoạt `workflow_dispatch` (chạy thủ công qua API, không phải qua `schedule:`).

**Vì sao cần Worker trung gian thay vì gọi thẳng GitHub API từ cron-job.org:** kích hoạt `workflow_dispatch` cần 1 token GitHub có quyền ghi (Actions: read/write). Không thể đặt token đó thẳng vào cron-job.org hay vào code của trang web — trang web là GitHub Pages build từ repo **public**, ai cũng xem được mã nguồn (View Source), nhúng token thẳng vào đó là công khai token cho cả Internet. Cloudflare Worker (`web/cloudflare-worker/worker.js`) là nơi duy nhất giữ token thật — nằm trong environment của Cloudflare (secret, mã hoá), không bao giờ lộ ra ngoài. Trang web/cron-job.org chỉ biết URL public của Worker.

Nút **"Quét ngay"** trên trang web dùng đúng cơ chế này để người dùng tự kích hoạt quét thủ công ngay từ trình duyệt.

---

## 8. Trang web (GitHub Pages) — kiến trúc v2.0 "editorial newsroom"

Sinh hoàn toàn từ `data/news.db` mỗi lần crawl (`web/generate_site.py`, chạy `python -m web.generate_site` để xem thử cục bộ) — **zero build tool**, HTML/CSS/JS thuần, phần lớn tương tác dùng `<details>/<summary>` gốc của HTML (không cần JS). Redesign toàn diện ngày 2026-09-16 theo tham khảo Financial Times/Reuters/Bloomberg thay cho bản v1 neo-brutalist/Kanban-first ban đầu.

**Thứ tự các phần trên trang** (từ trên xuống, xem chi tiết ở [GIAO-DIEN.md](GIAO-DIEN.md)):

1. **Header** (sticky, 72px) — masthead, ô tìm kiếm, nav neo (`TODAY/ISSUES/NEWS/SOURCES/ARCHIVE`), trạng thái LIVE + giờ cập nhật, nút "Quét ngay".
2. **Today overview** — 1 dải ngang: tổng bài · tổng nguồn · tổng issue nổi bật · giờ cập nhật.
3. **Top Issues hôm nay** — lưới 2 cột (desktop), 5 thẻ issue gọn, bấm để xem chi tiết (xem mục 9 bên dưới).
4. **All news** — dòng chảy tin **hợp nhất từ cả 23 nguồn** (giờ · nguồn · tiêu đề · nhãn issue nếu có), có tìm kiếm + lọc theo nguồn/issue + sắp xếp Mới nhất/Đang hot, và **phân trang 15 tin/trang** (nút chuyển trang dạng đếm số, rút gọn bằng "…" khi nhiều trang). Đây là trải nghiệm chính của trang — thay cho việc mở thẳng vào bảng Kanban như bản v1.
5. **By source** — bảng Kanban cũ (mỗi nguồn 1 cột, đóng/mở bằng `<details>`, tự xếp dọc trên mobile để tránh cuộn ngang) — vẫn còn nguyên logic, chỉ lùi thành mục phụ, không còn tô màu riêng theo từng nguồn.
6. **Archive** — 7 tab ngày (`dd/mm`) tự căn giữa quanh ngày đang xem + dropdown "Ngày khác" khi có nhiều hơn 7 ngày dữ liệu.
7. **Footer** — tần suất tự động cập nhật.

**Banner "xem tin mới nhất":** mọi trang lưu trữ (không phải ngày mới nhất) có 1 thanh nhỏ trỏ về đúng trang ngày mới nhất — vì URL có ngày cố định (vd `2026-09-16.html`) là snapshot đóng băng vĩnh viễn của đúng ngày đó (đúng bản chất tính năng lưu trữ), chỉ URL gốc (`index.html`, không có tên file) mới luôn tự mirror sang ngày mới nhất.

**"Ngày mới nhất" được xác định như thế nào:** là ngày dương lịch **mới nhất có ít nhất 1 bài đã crawl được** trong dữ liệu — không phải theo đồng hồ hệ thống. Ngay sau nửa đêm, cho tới khi có bài đầu tiên của ngày mới được quét về (tối đa ~1 chu kỳ 20 phút), trang chủ tạm thời vẫn hiện lại ngày hôm qua — hành vi này tự hết sau khi có bài mới, không phải lỗi vĩnh viễn (hiện tại chưa sửa để bám theo đồng hồ thật, xem mục 12).

**Ngôn ngữ hình ảnh:** font chính **Inter** (đã kiểm tra có bộ subset Unicode riêng cho tiếng Việt trong response CSS2 thật của Google Fonts trước khi dùng — rút kinh nghiệm từ lỗi font "Archivo Black" ở bản v1 thiếu dấu tiếng Việt), font phụ **IBM Plex Mono** cho số liệu/nhãn, bảng màu editorial trung tính (nền be nhạt `#F5F3EE`, accent xanh rêu đậm `#1F4B45`, không tô màu riêng theo nguồn, không emoji, không gradient/glassmorphism), viền mỏng 1px + bóng gần như vô hình thay cho style neo-brutalist cũ. Không có dark mode ở bản v2.0 (đặc tả thiết kế chỉ đưa bảng màu sáng).

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

## 10. Testing

**201 test** (`pytest`), chạy hoàn toàn offline bằng fixture lấy từ dữ liệu thực tế lúc audit — không cần mạng, mock qua thư viện `responses`.

| File | Phạm vi |
|------|---------|
| `test_crawlers.py`, `test_html_crawlers.py`, `test_fili_crawler.py` | Parse RSS cho 18 nguồn, HTML scrape cho 4 nguồn, JSON API cho FiLi — bao gồm mọi lỗi thật đã phát hiện qua audit (ngày phi chuẩn, encoding sai, thiếu giờ, cấu trúc trang đổi) |
| `test_database.py` | Dedup theo URL, baseline seeding lần đầu + baseline riêng cho nguồn mới thêm vào DB đã có dữ liệu |
| `test_telegram.py` | Định dạng tin nhắn, tách tin nóng, chia nhỏ khi vượt 4096 ký tự, retry khi lỗi |
| `test_scheduler.py` | Toàn bộ luồng `run_cycle` (dry-run/thành công/lỗi 1 phần/tất cả lỗi), cô lập lỗi từng nguồn, phát hiện + cooldown cảnh báo nguồn chết, lịch quét cố định đúng chu kỳ |
| `test_backup.py` | Backup có timestamp, tự xoá bản cũ |
| `test_utils.py` | Chuẩn hoá URL (bỏ `fbclid`/`utm_*`/fragment) |
| `test_generate_site.py` | Sinh trang web: gom đúng ngày, escape XSS, cửa sổ 7-tab ngày, nút Quét ngay, phân trang, banner "xem tin mới nhất", tích hợp Top Issues |
| `test_issues.py` | Cả 8 kịch bản test bắt buộc theo đặc tả Issue Intelligence V3 (gộp đúng issue giống nhau, không gộp nhầm cùng entity khác topic, không gộp nhầm cùng topic khác entity, đa dạng nguồn, chống thiên vị khối lượng, "vì sao hot" đúng số liệu, ổn định xếp hạng, đúng múi giờ) + regression test cho lỗi "HĐQT" |

---

## 11. Cấu trúc thư mục

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
├── crawlers/                      # 23 crawler, 1 file/nguồn + base.py
├── web/
│   ├── generate_site.py            # sinh trang tĩnh site/ (v2.0 editorial)
│   ├── issues.py                    # Issue Intelligence V3 (Entity/Topic/Issue, HotScore)
│   └── cloudflare-worker/worker.js   # proxy bảo mật cho nút "Quét ngay"
├── tests/                             # 201 test, xem mục 10
├── data/news.db                        # SQLite (local dev; trên CI lấy từ nhánh db-state)
├── backup/                              # snapshot DB có timestamp
├── site/                                 # HTML tĩnh sinh ra (gitignored)
├── .github/workflows/news-crawl.yml       # toàn bộ pipeline CI/CD
├── README.md / GIOI-THIEU.md / GIAO-DIEN.md / TONG-QUAN-DU-AN.md (file này)
```

---

## 12. Giới hạn đã biết

- **HotScore không phải "phủ quyết" tuyệt đối cho đa dạng nguồn** (mục 9) — 1 nguồn đăng nhiều tin gần giống nhau vẫn có thể thắng điểm 1 issue thật sự đa nguồn nếu chênh lệch số bài đủ lớn.
- **"Ngày mới nhất" trễ tối đa ~20 phút sau nửa đêm** cho tới khi có bài đầu tiên của ngày mới (mục 8) — đã thêm banner "xem tin mới nhất" để giảm nhầm lẫn, nhưng chưa sửa tận gốc để trang tự bám theo đồng hồ thật (người dùng đã được hỏi, chọn giữ nguyên).
- **Không dark mode** ở giao diện v2.0 hiện tại — đặc tả thiết kế chỉ đưa bảng màu sáng.
- **Danh sách từ khoá (`HOT_KEYWORDS`, `_TOPIC_KEYWORDS`, `_GENERIC_ACRONYMS`) là tự chọn tay**, không phải NLP thật — cần tinh chỉnh dần khi phát hiện case sai qua vận hành thực tế, không phải giải pháp hoàn hảo 1 lần là xong.
- **API trạng thái của GitHub Actions có thể báo "in_progress" cũ hàng chục phút** dù job thật đã chạy xong từ lâu (gặp thực tế nhiều lần) — luôn nên kiểm tra bằng nội dung trang live thay vì tin tuyệt đối vào API trạng thái khi cần xác minh deploy đã xong hay chưa.
- **Theo dõi thương hiệu (tab Brands) chỉ dựa vào tiêu đề:** bài nhắc tên ngân hàng ở thân bài mà không có trong tiêu đề sẽ bị bỏ sót, và sắc thái chỉ là ước lượng bằng từ khoá (dễ sai với châm biếm, trích dẫn, tiêu đề chỉ gợi ý). Cảnh báo khủng hoảng vì thế là "đáng xem", không phải kết luận — luôn cần người xác nhận.
- **Riêng tư:** trang web và `watchlist.json` nằm trong repo/GitHub Pages **công khai**. Dùng cho mục đích nội bộ của 1 tổ chức (danh sách thương hiệu mình theo dõi, đối thủ) thì cần host riêng tư hoặc thêm đăng nhập trước khi đưa thông tin nhạy cảm vào.
- **Bản quyền:** hệ thống chỉ lưu tiêu đề + đường dẫn gốc (an toàn). Lưu/phát lại toàn văn bài báo để làm báo cáo thương mại cần được các báo cho phép.
- **Báo Đầu tư không có `published_at` cho bất kỳ bài nào** (giới hạn của chính trang nguồn, không phải lỗi crawler) — mọi bài của nguồn này hiển thị giờ `--:--` khi không fetch được trang chi tiết.

---

## 13. Chạy / phát triển cục bộ

```bash
# Cài dependency
pip install -r requirements.txt

# Xem thử trang web (không cần mạng, không cần Telegram)
python -m web.generate_site
# rồi mở site/index.html bằng trình duyệt

# Chạy thử 1 chu kỳ quét, in ra kết quả, không ghi DB, không gửi Telegram
python main.py --dry-run

# Chạy test
pytest
```

Cấu hình qua `.env` (copy từ `.env.example`) — bắt buộc `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` khi chạy thật (không cần cho `--dry-run`). Chi tiết đầy đủ từng biến ở [README.md](README.md).
