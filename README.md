# Vietnam News Monitor

Theo dõi 14 chuyên mục kinh tế/tài chính của báo Việt Nam (gồm cả báo nhà nước/thông tấn chính thống) mỗi 15 phút, phát hiện bài mới, chống gửi trùng, và đẩy title (kèm link) + thời gian về Telegram — **group theo từng nguồn báo, có icon riêng để phân biệt nhanh**.

Xem đầy đủ yêu cầu gốc trong `PROJECT SPEC V2` đã cung cấp. README này chỉ tập trung vào cách chạy.

## Nguồn báo

### Đang hoạt động (14 nguồn)

Tất cả đã audit thực tế (không giả định RSS/selector cũ còn đúng) vào ngày 14/09/2026:

| Icon | Nguồn | URL category | RSS feed thực tế đã xác minh |
|---|---|---|---|
| 🔵 | VnExpress | `vnexpress.net/kinh-doanh` | `vnexpress.net/rss/kinh-doanh.rss` |
| 🟠 | Tuổi Trẻ | `tuoitre.vn/kinh-doanh.htm` | `tuoitre.vn/rss/kinh-doanh.rss` |
| 🏦 | CafeF | `cafef.vn/tai-chinh-ngan-hang.chn` | `cafef.vn/tai-chinh-ngan-hang.rss` |
| 📊 | Vietstock | `vietstock.vn/chu-de/1-2/moi-cap-nhat.htm` ("Tin mới" toàn site — đổi theo yêu cầu người dùng ngày 14/09/2026, ban đầu là `tai-chinh/ngan-hang.htm`) | `vietstock.vn/0/tin-moi.rss` |
| 🔴 | Thanh Niên | `thanhnien.vn/kinh-te.htm` | `thanhnien.vn/rss/kinh-te.rss` |
| 🟡 | Dân Trí | `dantri.com.vn/kinh-doanh` | `dantri.com.vn/rss/kinh-doanh.rss` |
| 📈 | VnEconomy | `vneconomy.vn/tai-chinh` | `vneconomy.vn/tai-chinh.rss` (feed "home" tổng của VnEconomy rỗng — `vneconomy.vn/rss/home.rss` trả "No Content" — nên dùng thẳng feed chuyên mục Tài chính) |
| ⚡ | Znews | `znews.vn/kinh-doanh-tai-chinh.html` | `znews.vn/rss/kinh-doanh-tai-chinh.rss` |
| 🟣 | Tiền Phong | `tienphong.vn/kinh-te.html` | `tienphong.vn/rss/kinh-te-3.rss` — **lưu ý:** ID category đoán trước `kinh-te-108.rss` trả HTTP 200 nhưng thực chất là feed tổng hợp lẫn cả giải trí/giáo dục, không đúng chuyên mục kinh tế. ID đúng (`kinh-te-3`) chỉ tìm ra được bằng cách đọc trang `tienphong.vn/rss.html` do chính site liệt kê. |
| 📻 | VOV | `vov.vn/kinh-te` | `vov.vn/rss/kinh-te.rss` — **lưu ý:** WAF của VOV trả HTTP 403 với User-Agent mặc định của app (đã xác minh không phải do hậu tố "NewsMonitor", vì UA Chrome đầy đủ không hậu tố cũng bị chặn), chỉ cho qua UA ngắn `Mozilla/5.0` — `VOVCrawler` override riêng UA này. |
| ➕ | VietnamPlus | `vietnamplus.vn/kinhte` | `vietnamplus.vn/rss/kinhte.rss` (thuộc TTXVN — Thông tấn xã Việt Nam) |
| ⭐ | Nhân Dân | `nhandan.vn/kinhte.htm` | `nhandan.vn/rss/kinhte-1185.rss` — **lưu ý:** ID đoán trước `kinhte-1041.rss` trả HTTP 200 nhưng là feed tổng hợp lẫn tin thời sự/xã hội, không phải kinh tế. ID đúng tìm được qua `<link rel="alternate">` khai báo trên chính trang chuyên mục. |
| 🏛️ | Chính phủ | `baochinhphu.vn/kinh-te.htm` | `baochinhphu.vn/kinh-te.rss` — **lưu ý:** `pubDate` không theo chuẩn RFC-822 (`"9/14/2026 6:44:00 PM"` thay vì `"Mon, 14 Sep 2026 18:44:00 +0700"`), `feedparser` không tự parse được, `BaoChinhPhuCrawler` có logic parse riêng. |
| 📺 | VTV | `vtv.vn/kinh-te.htm` | `vtv.vn/rss/kinh-te.rss` — **lưu ý:** `pubDate` dùng offset giờ rút gọn `+07` thay vì `+0700` chuẩn, cũng khiến `feedparser` không parse được, `VTVCrawler` có logic parse riêng. Feed khá lớn (~500 bài lưu trữ mỗi lần crawl, không phải lỗi category). |

Vì vậy tất cả 14 crawler dùng chung `RSSCrawlerBase` (`crawlers/base.py`) nhưng mỗi site vẫn là **1 file riêng** trong `crawlers/` — nếu sau này RSS của 1 site đổi cấu trúc hoặc ngừng hoạt động, chỉ sửa đúng file đó mà không ảnh hưởng các site còn lại. 3 site (VOV, Chính phủ, VTV) cần override nhỏ (`__init__` cho UA, `_extract_published_at` cho định dạng ngày lạ) — vẫn kế thừa toàn bộ phần còn lại từ `RSSCrawlerBase`, không viết lại từ đầu.

Một chi tiết đáng chú ý khi audit V1: CafeF và Thanh Niên trả `pubDate` với năm 2 chữ số (`"Mon, 14 Sep 26 08:00:00 +0700"`). `feedparser` tự parse đúng thành năm 2026 qua `published_parsed`, nên không cần tự viết logic parse ngày riêng cho từng site. Thanh Niên còn có thêm 1 lỗi double-encode HTML entity trong `<title>` (vd. `n&agrave;y` thay vì `này`) — đã vá bằng `html.unescape()` trong `utils.normalize_title`.

### Chưa triển khai — lý do cụ thể

Audit thực tế nhiều nguồn ứng viên khác (bao gồm cả nguồn spec V2 gốc và nguồn "chính thống" tìm thêm), loại với lý do rõ ràng thay vì đoán bừa:

| Nguồn dự kiến | Vấn đề phát hiện khi audit |
|---|---|
| VietnamNet — Kinh tế | RSS chính thức `vietnamnet.vn/kinh-doanh.rss` (được chính trang khai báo là feed canonical) bị đứng — item mới nhất từ 08/08/2026, hơn 1 tháng không cập nhật. Dùng feed này sẽ không bao giờ có tin mới thật. |
| Người Lao Động — Kinh tế | Domain `nld.com.vn` đã redirect toàn bộ sang `tuoitre.vn` (đã sáp nhập vào Tuổi Trẻ) — không còn là nguồn tin độc lập. |
| VietnamFinance | RSS tồn tại (`vietnamfinance.vn/tai-chinh.rss`) nhưng thực chất là feed proxy qua Google News, `lastBuildDate` cũ hơn 2 tuần tại thời điểm audit — không đủ tin cậy cho chu kỳ 15 phút. |
| Nhịp sống Kinh tế | Đây chính là tagline/tên gọi khác của VnEconomy, không phải một trang riêng biệt — trùng với nguồn VnEconomy đã thêm. |
| Đầu tư Chứng khoán (tinnhanhchungkhoan.vn) | Không tìm thấy RSS hoạt động ở các pattern chuẩn (`/rss/*.rss` đều redirect ra trang 404). Cần khảo sát cấu trúc HTML để viết crawler scrape riêng. |
| BizLIVE | Domain `bizlive.vn` đã redirect sang `nhipsongkinhdoanh.vn` (rebrand), nhưng chưa tìm được RSS của domain mới. |
| Bnews (thuộc TTXVN) | Không tìm thấy RSS ở bất kỳ pattern chuẩn nào (toàn bộ trả HTTP 404/500), trang chủ cũng không khai báo `<link rel="alternate">` nào — có thể site không có RSS. Cần scrape HTML nếu muốn thêm. |

Muốn triển khai tiếp các nguồn còn thiếu, việc chính là viết crawler `crawl()` override dùng `requests` + `beautifulsoup4` (đã có sẵn dependency) thay vì `RSSCrawlerBase`, theo đúng interface `BaseCrawler` trong `crawlers/base.py` — xem mục "Thêm nguồn báo mới" bên dưới.

## Format Telegram

Mỗi nguồn có 1 icon riêng để nhận diện nhanh không cần đọc chữ (bảng icon ở trên). Ví dụ tin nhắn thật:

```
📬 5 bài mới · 3 nguồn

📻 VOV (2 bài)

• Hướng dẫn giới kinh doanh vàng đá quý phòng, chống rửa tiền — 19:42
• Cục Thuế yêu cầu không thêm thủ tục khi đóng mã số thuế — 18:43

🏛️ CHÍNH PHỦ (2 bài)

• Cửa khẩu số hóa, doanh nghiệp thêm lựa chọn thanh toán CNY — 18:44
• Vietjet và Thales mở rộng hợp tác hàng không công nghệ cao — 20:01

🔵 VNEXPRESS (1 bài)

• Tesla lập công ty ở Việt Nam — 14:55
```

Title là link click được (Telegram `parse_mode=HTML`), tên nguồn in đậm kèm số bài. Nếu 1 chu kỳ có nguồn lỗi, dòng `⚠️ Nguồn lỗi: ...` được thêm vào cuối cùng 1 tin nhắn này — không tách thành tin riêng (tối đa 1 batch/chu kỳ, chỉ tách khi vượt 4096 ký tự, xem mục "Luồng xử lý" bên dưới).

## Cài đặt

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Cài dependencies:

```bash
pip install -r requirements.txt
```

Dự án **không dùng Playwright** — không có site nào trong 14 site đang chạy cần browser automation (xem bảng RSS ở trên), đúng theo ưu tiên "chỉ dùng Playwright khi thực sự cần" trong spec.

## Cấu hình

Tạo Telegram Bot:

1. Chat với [@BotFather](https://t.me/BotFather) trên Telegram, dùng lệnh `/newbot` để tạo bot, lấy `TELEGRAM_BOT_TOKEN`.
2. Lấy `TELEGRAM_CHAT_ID`: thêm bot vào group/kênh muốn nhận tin, hoặc chat trực tiếp với bot rồi mở `https://api.telegram.org/bot<TOKEN>/getUpdates` để xem `chat.id`.

Copy file cấu hình mẫu:

```bash
cp .env.example .env
```

Điền vào `.env`:

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

Các biến khác (`CRAWL_INTERVAL_MINUTES`, `REQUEST_TIMEOUT`, `MAX_RETRIES`, `INITIAL_SCAN_SEND`, `LOG_LEVEL`, `TIMEZONE`, `STALE_SOURCE_HOURS`, `STALE_ALERT_COOLDOWN_HOURS`, `BACKUP_KEEP_DAYS`) đã có giá trị mặc định hợp lý (`CRAWL_INTERVAL_MINUTES=15` từ V2), chỉ cần chỉnh nếu muốn.

**Không commit `.env` lên Git** — đã có trong `.gitignore`.

## Chạy thử (không cần Telegram token)

```bash
python main.py --dry-run
```

Dry run: crawl → parse → kiểm tra trùng với database hiện có → in ra terminal. **Không ghi database, không gửi Telegram.** Dùng lệnh này để kiểm tra 14 crawler còn hoạt động tốt không, bất cứ lúc nào.

## Chạy test tự động

```bash
pytest
```

85 test bao phủ: normalize title/URL (kể cả giải mã HTML entity lỗi của Thanh Niên), crawler parse RSS cho cả 14 nguồn (kèm test riêng cho override User-Agent VOV và parse ngày lạ của Chính phủ/VTV) (dùng fixture RSS lấy từ dữ liệu thực tế lúc audit, mock qua thư viện `responses` — không cần mạng), dedup theo URL (không theo title), restart không mất/không gửi lại dữ liệu, format Telegram group-theo-nguồn + chia nhỏ khi vượt giới hạn 4096 ký tự, retry khi gửi Telegram lỗi, cô lập lỗi từng nguồn không làm crash app, giữ đúng thứ tự nguồn theo cấu hình, baseline seeding lần chạy đầu **và** baseline riêng cho nguồn mới thêm vào một DB đã có dữ liệu, toàn bộ luồng `run_cycle` (dry-run / gửi thành công / lỗi 1 phần vẫn gửi tin nguồn OK / tất cả lỗi / Telegram lỗi thì không đánh dấu sent), phát hiện nguồn "chết âm thầm" (mới ở V3: ngưỡng giờ, cooldown cảnh báo, tự gỡ cảnh báo khi hồi phục), và backup database (tạo bản có timestamp + tự xoá bản cũ).

## Chạy lần đầu / chạy thủ công

```bash
python main.py --run-once
```

Nếu đây là lần chạy đầu tiên (database rỗng) và `INITIAL_SCAN_SEND=false` (mặc định): app sẽ **âm thầm ghi nhận toàn bộ bài hiện có làm baseline, không gửi Telegram** — tránh spam hàng trăm tin cũ. Từ lần chạy tiếp theo trở đi, chỉ bài thực sự mới mới được gửi.

Nếu muốn gửi luôn cả các bài đang có ngay từ lần chạy đầu, đặt `INITIAL_SCAN_SEND=true` trong `.env` trước khi chạy lần đầu.

**V2:** nếu database đã có dữ liệu (app đã chạy từ trước) và bạn vừa thêm một crawler mới, app tự phát hiện nguồn đó "chưa có lịch sử" và âm thầm baseline riêng cho đúng nguồn đó — không đụng tới trạng thái của các nguồn cũ, không flood Telegram hàng loạt bài cũ của nguồn mới. Hành vi này chạy tự động, không cần config gì thêm.

## Chạy production (scheduler 15 phút)

```bash
python main.py
```

App sẽ tự động crawl theo chu kỳ đặt trong `CRAWL_INTERVAL_MINUTES` (mặc định 15 phút), canh theo mốc giờ tròn khi có thể (ví dụ 10:00, 10:15, 10:30 — đúng ví dụ trong spec V2) và chạy 1 lần ngay khi khởi động. Dừng bằng `Ctrl+C`.

`APScheduler` được cấu hình `max_instances=1` — nếu chu kỳ trước chưa crawl/gửi xong khi mốc giờ tiếp theo tới, chu kỳ mới **tự động bị bỏ qua** thay vì chạy chồng lên (spec V2 mục 19: không chạy 2 batch cùng lúc). Không cần thêm lock file hay cấu hình gì khác.

## V3 — Cảnh báo nguồn "chết âm thầm"

Một RSS feed có thể vẫn trả về HTTP 200 bình thường (không lỗi, không bị `crawl_all` phát hiện) nhưng **nội dung bên trong không còn cập nhật** — đây là sự cố thật đã gặp với VietnamNet lúc audit V2 (feed đứng >1 tháng, không hề báo lỗi gì). App tự phát hiện kiểu lỗi này:

- Với mỗi nguồn crawl **thành công**, app theo dõi thời điểm bài mới nhất thực sự được ghi vào database (`first_seen_at`, không phải `published_at` — tránh phụ thuộc đồng hồ của từng site).
- Nếu 1 nguồn không có bài mới nào trong hơn `STALE_SOURCE_HOURS` giờ (mặc định **24h**), app gửi cảnh báo riêng:
  ```
  🩺 NEWS MONITOR — Cảnh báo nguồn

  Các nguồn sau không có bài mới nào trong hơn 24h qua — có thể RSS đã hỏng hoặc đổi cấu trúc, nên kiểm tra lại:

  - VietnamNet (bài mới gần nhất: 08/08/2026 10:54)
  ```
- Để tránh spam lặp lại mỗi 15 phút, cùng 1 nguồn chỉ được cảnh báo lại sau mỗi `STALE_ALERT_COOLDOWN_HOURS` giờ (mặc định **24h**).
- Khi nguồn có bài mới trở lại, cảnh báo tự động được "gỡ" — lần chết tiếp theo (nếu có) sẽ báo lại từ đầu.

Chỉnh 2 biến này trong `.env` nếu muốn nhạy hơn/chậm hơn.

## V3 — Backup tự động

App tự backup database **mỗi ngày lúc 03:00** (giờ theo `TIMEZONE`) — job này chạy độc lập với chu kỳ crawl, dùng chung `BlockingScheduler` nên không cần cron ngoài hay dịch vụ nào khác:

```bash
tail -f logs/app.log | grep backup
```

File backup lưu tại `backup/news-YYYYMMDD-HHMMSS.db`, tự động xoá các bản backup cũ hơn `BACKUP_KEEP_DAYS` ngày (mặc định **14 ngày**).

Muốn backup ngay lập tức (không đợi 03:00), hoặc muốn tự đặt lịch qua cron riêng thay vì dùng job tích hợp sẵn:

```bash
python main.py --backup-now
```

Khôi phục: dừng app, copy đè file backup muốn khôi phục vào `data/news.db`, chạy lại app.

## Deploy VPS 24/7

### systemd (khuyến nghị)

Tạo file `/etc/systemd/system/news-monitor.service`:

```ini
[Unit]
Description=Vietnam News Monitor
After=network-online.target

[Service]
Type=simple
User=news-monitor
WorkingDirectory=/opt/news-monitor
ExecStart=/opt/news-monitor/.venv/bin/python main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Kích hoạt:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now news-monitor
sudo systemctl status news-monitor
sudo journalctl -u news-monitor -f
```

`main.py` (không tham số) đã tự chứa scheduler 15 phút bên trong (`BlockingScheduler`), nên chỉ cần systemd giữ tiến trình sống — không cần cron gọi lặp lại.

### Cron (thay thế, nếu không dùng systemd)

Cách khác — theo đúng gợi ý ở spec mục 2 — là để cron gọi `--run-once` mỗi 15 phút thay vì chạy `main.py` daemon:

```cron
*/15 * * * * cd /opt/news-monitor && /opt/news-monitor/.venv/bin/python main.py --run-once >> logs/cron.log 2>&1
```

Cách này restart-safe tự nhiên (mỗi lần chạy là 1 process độc lập, không có state daemon để mất), nhưng **không** có bảo vệ "không chạy chồng" tự động như `max_instances=1` của APScheduler — nếu 1 lần chạy kéo dài hơn 15 phút (mạng chậm/1 nguồn treo), 2 tiến trình có thể trùng nhau. Nếu chọn cách này, nên thêm `flock` để tự loại trừ:

```cron
*/15 * * * * flock -n /tmp/news-monitor.lock -c "cd /opt/news-monitor && .venv/bin/python main.py --run-once >> logs/cron.log 2>&1"
```

**Lưu ý nếu chọn cron thay vì daemon:** job backup tự động 03:00 chỉ chạy bên trong `python main.py` (daemon/scheduler) — `--run-once` không đăng ký job đó. Nếu dùng cron, thêm 1 dòng cron riêng gọi `--backup-now`:

```cron
0 3 * * * cd /opt/news-monitor && .venv/bin/python main.py --backup-now >> logs/cron.log 2>&1
```

## Kiểm tra log

```bash
tail -f logs/app.log
```

Mỗi dòng log có timestamp, level, và nội dung theo format spec mục 18: bắt đầu crawl, số bài mỗi nguồn, số bài mới, lỗi (nếu có), kết quả gửi Telegram. Log tự xoay vòng (`RotatingFileHandler`, tối đa 5MB × 3 file) nên không cần dọn tay.

## Thêm nguồn báo mới

1. Audit thực tế trước — đừng đoán: `curl -A "Mozilla/5.0" <feed-url-nghi-ngờ>` xem có RSS đúng chuyên mục cần không (xem mục "Chưa triển khai trong V2 này" ở trên làm ví dụ về việc audit sai sẽ dẫn tới feed lẫn nội dung không liên quan).
2. Nếu có RSS đúng: tạo `crawlers/<ten_site>.py`, subclass `RSSCrawlerBase`, chỉ cần khai `source_name`, `source_url`, `feed_url` (xem `crawlers/vnexpress.py` làm mẫu tối giản).
3. Nếu không có RSS: subclass `BaseCrawler` trực tiếp, tự viết `crawl()` dùng `requests` + `beautifulsoup4` (đã có trong `requirements.txt`), trả về `List[NewsItem]` giống hệt interface RSS.
4. Thêm crawler mới vào `CRAWLER_CLASSES` trong `crawlers/__init__.py` — thứ tự trong list quyết định thứ tự hiển thị trên Telegram.
5. Thêm 1 fixture RSS/HTML nhỏ (2-3 bài thật) vào `tests/fixtures/`, thêm dòng vào `CRAWLERS_AND_FIXTURES` trong `tests/test_crawlers.py`.
6. Chạy `pytest` rồi `python main.py --dry-run` để xác nhận trước khi chạy production.
7. Không cần migration DB hay đổi schema — nguồn mới tự động được baseline riêng ở lần chạy `--run-once`/scheduler đầu tiên sau khi thêm (xem mục "Chạy lần đầu / chạy thủ công" ở trên).

## Về việc test crawler bằng mạng thật

Toàn bộ crawler đã được audit và test bằng dữ liệu RSS **thực tế** lấy trực tiếp từ 14 site vào ngày 14/09/2026 (xem bảng ở trên). Test tự động (`pytest`) dùng fixture dựng lại từ dữ liệu thật đó, chạy offline, đáng tin cậy và lặp lại được.

Ngoài ra, toàn bộ luồng end-to-end (crawl → dedup → Telegram → sent_at, bao gồm baseline seeding, baseline riêng cho nguồn mới, phát hiện bài mới thật sự, không gửi trùng lần 2, restart không mất dữ liệu, và báo lỗi khi 1 nguồn fail) đã được xác minh bằng cách chạy `main.py --run-once` thật với Telegram Bot API thật (không mock) trong lúc phát triển.

**Việc bạn cần tự làm định kỳ:** chạy `python main.py --dry-run` để xác nhận 14 crawler vẫn lấy đúng dữ liệu tại thời điểm bạn dùng — RSS thường ổn định nhưng không có gì đảm bảo 100% một site sẽ không đổi cấu trúc trong tương lai (xem case Tiền Phong ở trên: 1 category ID sai vẫn trả HTTP 200 bình thường).

## Kiến trúc

```text
news-monitor/
├── main.py           # CLI: --run-once / --dry-run / scheduler mặc định
├── config.py         # Đọc .env, cung cấp Config dùng chung
├── database.py       # SQLite: insert-if-new, get_pending, mark_sent, known_sources
├── telegram.py       # Format message (group theo nguồn) + gửi qua Telegram Bot API
├── scheduler.py       # run_cycle() (luồng chính) + APScheduler + baseline theo nguồn + stale-check
├── backup.py           # Backup SQLite có timestamp + tự xoá bản cũ (V3)
├── models.py          # NewsItem
├── logger.py           # Logging ra console + logs/app.log
├── utils.py             # normalize_title (kèm html.unescape), normalize_url
├── crawlers/
│   ├── base.py          # BaseCrawler (interface) + RSSCrawlerBase (dùng chung)
│   ├── vnexpress.py
│   ├── tuoitre.py
│   ├── cafef.py
│   ├── vietstock.py
│   ├── thanhnien.py
│   ├── dantri.py        # V2
│   ├── vneconomy.py     # V2
│   ├── znews.py         # V2
│   └── tienphong.py     # V2
├── data/news.db         # SQLite (tự tạo khi chạy, không commit)
├── logs/app.log         # Log (tự tạo khi chạy, không commit)
└── tests/
```

### Luồng xử lý mỗi chu kỳ (`scheduler.run_cycle`)

1. Crawl cả 14 nguồn, lỗi 1 nguồn không làm hỏng nguồn khác (`crawl_all`).
2. Với mỗi bài lấy được: normalize title/URL, `INSERT OR IGNORE` vào SQLite theo URL (dedup) — **insert xảy ra trước khi thử gửi Telegram**, nên nếu app crash hoặc Telegram lỗi giữa chừng, bài viết vẫn còn trong DB với `sent_at = NULL` và sẽ được thử gửi lại ở chu kỳ sau (không mất dữ liệu, không tạo bản ghi trùng).
3. Lấy toàn bộ bài chưa gửi (`get_pending`), group theo nguồn theo đúng thứ tự khai báo trong `CRAWLER_CLASSES` (không sort theo thời gian toàn cục — spec V2 mục 12).
4. Chọn đúng 1 trong 4 kịch bản, luôn ưu tiên gửi **1 batch Telegram / chu kỳ** (spec V2 mục 15):
   - **Có bài mới** (dù có hay không có nguồn lỗi): gửi 1 message group-theo-nguồn, kèm dòng "⚠️ Nguồn lỗi: ..." ở cuối nếu có nguồn lỗi. Chỉ tách nhiều message nếu vượt 4096 ký tự.
   - **Không có bài mới, tất cả nguồn đều lỗi**: gửi "🔴 NEWS MONITOR — Không thể hoàn tất lượt quét" kèm danh sách nguồn lỗi.
   - **Không có bài mới, một phần nguồn lỗi**: gửi "⚠️ NEWS MONITOR — Không có tin mới từ các nguồn hoạt động" kèm danh sách nguồn lỗi — **không bao giờ** báo nhầm thành "không có tin mới" khi thực ra có nguồn đang chết.
   - **Không có bài mới, mọi nguồn OK**: gửi "🟢 NEWS MONITOR — Không có tin mới."
5. Chỉ đánh dấu `sent_at` sau khi Telegram xác nhận gửi thành công.

### Vì sao không dùng thư viện `python-telegram-bot`

`python-telegram-bot` (bản v20+) là thư viện async, khá nặng cho nhu cầu ở đây (gọi 1 API POST đơn giản, đồng bộ, mỗi 15 phút). `telegram.py` dùng thẳng `requests` gọi Telegram Bot API (`parse_mode=HTML` để title là hyperlink click được) — ít dependency hơn, dễ đọc từ đầu đến cuối, đúng tinh thần "SIMPLE STABLE MAINTAINABLE" của spec.

## Giới hạn đã biết

Không AI, không dashboard, không Docker/Redis/PostgreSQL, không proxy rotation, không sentiment/event clustering — đúng danh sách "V2 KHÔNG LÀM" trong spec. HTML-scraping fallback (BeautifulSoup) đã có dependency sẵn sàng, sẽ cần dùng cho 2 nguồn còn thiếu RSS (Đầu tư Chứng khoán, BizLIVE/Nhịp sống kinh doanh) ở đợt phát triển tiếp theo — xem mục "Chưa triển khai trong V2 này" ở trên.
