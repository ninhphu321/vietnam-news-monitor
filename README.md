# Vietnam News Monitor

Theo dõi 18 chuyên mục kinh tế/tài chính của báo Việt Nam (gồm cả báo nhà nước/thông tấn chính thống), phát hiện bài mới, chống gửi trùng, và đẩy title (kèm link) + thời gian về Telegram — **group theo từng nguồn báo (icon riêng để phân biệt nhanh), tách riêng tin nóng lên đầu**. Quét mỗi 20 phút/lần, cả ngày lẫn đêm (không phân biệt khung giờ).

Xem đầy đủ yêu cầu gốc trong `PROJECT SPEC V2` đã cung cấp. README này chỉ tập trung vào cách chạy.

## Nguồn báo

### Đang hoạt động (18 nguồn)

Tất cả đã audit thực tế (không giả định RSS/selector cũ còn đúng) vào ngày 14-15/09/2026:

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
| ➕ | VietnamPlus | `vietnamplus.vn/kinhte` | `vietnamplus.vn/rss/kinhte.rss` (thuộc TTXVN — Thông tấn xã Việt Nam) |
| ⭐ | Nhân Dân | `nhandan.vn/kinhte.htm` | `nhandan.vn/rss/kinhte-1185.rss` — **lưu ý:** ID đoán trước `kinhte-1041.rss` trả HTTP 200 nhưng là feed tổng hợp lẫn tin thời sự/xã hội, không phải kinh tế. ID đúng tìm được qua `<link rel="alternate">` khai báo trên chính trang chuyên mục. |
| 🏛️ | Chính phủ | `baochinhphu.vn/kinh-te.htm` | `baochinhphu.vn/kinh-te.rss` — **lưu ý:** `pubDate` không theo chuẩn RFC-822 (`"9/14/2026 6:44:00 PM"` thay vì `"Mon, 14 Sep 2026 18:44:00 +0700"`), `feedparser` không tự parse được, `BaoChinhPhuCrawler` có logic parse riêng. |
| 📺 | VTV | `vtv.vn/kinh-te.htm` | `vtv.vn/rss/kinh-te.rss` — **lưu ý:** `pubDate` dùng offset giờ rút gọn `+07` thay vì `+0700` chuẩn, cũng khiến `feedparser` không parse được, `VTVCrawler` có logic parse riêng. Feed khá lớn (~500 bài lưu trữ mỗi lần crawl, không phải lỗi category). |
| 💱 | VietnamBiz | `vietnambiz.vn/tai-chinh` | `vietnambiz.vn/tai-chinh.rss` — **lưu ý:** `pubDate` dùng `"GMT+7"` thay vì `+0700` chuẩn (một quirk khác với `+07` của VTV), cũng khiến `feedparser` không parse được, `VietnamBizCrawler` có logic parse riêng. Cũng dính lỗi double-encode HTML entity giống Thanh Niên trong `<title>` — đã tự được vá bởi fix chung, không cần thêm gì. |

Vì vậy 14/18 crawler dùng chung `RSSCrawlerBase` (`crawlers/base.py`) nhưng mỗi site vẫn là **1 file riêng** trong `crawlers/` — nếu sau này RSS của 1 site đổi cấu trúc hoặc ngừng hoạt động, chỉ sửa đúng file đó mà không ảnh hưởng các site còn lại. 3 site (Chính phủ, VTV, VietnamBiz) cần override nhỏ (`_extract_published_at` cho định dạng ngày lạ) — vẫn kế thừa toàn bộ phần còn lại từ `RSSCrawlerBase`, không viết lại từ đầu.

Một chi tiết đáng chú ý khi audit V1: CafeF và Thanh Niên trả `pubDate` với năm 2 chữ số (`"Mon, 14 Sep 26 08:00:00 +0700"`). `feedparser` tự parse đúng thành năm 2026 qua `published_parsed`, nên không cần tự viết logic parse ngày riêng cho từng site. Thanh Niên còn có thêm 1 lỗi double-encode HTML entity trong `<title>` (vd. `n&agrave;y` thay vì `này`) — đã vá bằng `html.unescape()` trong `utils.normalize_title`.

### 4 nguồn không có RSS — scrape HTML bằng BeautifulSoup

`crawlers/base.py`'s `BaseCrawler` giờ tự chứa sẵn `_fetch()` (HTTP + retry, dùng chung cho cả RSS lẫn HTML), nên 1 crawler HTML chỉ cần override `crawl()`, tự parse bằng `BeautifulSoup` — không cần viết lại phần fetch/retry.

| Icon | Nguồn | Trang scrape | Ghi chú audit |
|---|---|---|---|
| ☕ | CafeBiz | `cafebiz.vn/cau-chuyen-kinh-doanh.chn` | Không có RSS cho chuyên mục này (home.rss lẫn thời tiết/công nghệ/giải trí). Trang chuyên mục cũng trộn 2 phần: khối "nổi bật" phía trên (đôi khi lẫn tin thể thao/giải trí, **không có giờ**) và danh sách chính bên dưới (đúng chủ đề, có giờ). Lọc theo "có giờ hay không" để loại khối nổi bật, không cần đoán chủ đề. |
| 📉 | Đầu tư Chứng khoán | `tinnhanhchungkhoan.vn/chung-khoan/` | Không tìm được RSS ở bất kỳ pattern nào. **Lưu ý quan trọng:** cùng 1 bài có thể xuất hiện tới 4 lần trên 1 trang (danh sách chính + các widget "liên quan" khác), mỗi lần 1 giờ khác nhau hoặc không giờ — lấy đúng lần xuất hiện **đầu tiên** (danh sách chính, mới nhất) thay vì để lần cuối ghi đè. ~36% bài không có giờ hiển thị (widget con không có time), dùng `published_at=None`. |
| 🏢 | Diễn đàn Doanh nghiệp | `diendandoanhnghiep.vn/chinh-tri-xa-hoi/kinh-te` | Không có RSS, không khai báo `<link rel="alternate">`. Định dạng giờ dạng text `dd/mm/yyyy HH:MM` (không phải ISO). Bài nổi bật đầu trang không có giờ → `published_at=None`. |
| 💼 | Báo Đầu tư | `baodautu.vn/dau-tu-tai-chinh-d6/` | RSS luôn trả kênh rỗng bất kể slug (xem bảng dưới). Trang chuyên mục **không hiển thị giờ đăng ở bất kỳ đâu** trong toàn bộ danh sách (mọi cỡ thẻ) — muốn có giờ phải fetch riêng từng trang bài, quá tốn tài nguyên cho 1 nguồn. Toàn bộ bài từ nguồn này luôn có `published_at=None`. |

Cả 4 crawler đều tự phát hiện khi selector không còn khớp gì cả (0 bài) và báo lỗi thay vì âm thầm báo "0 bài mới" mãi mãi — HTML không có "chuẩn" như RSS để biết chắc site có đổi cấu trúc hay không, nên đây là tín hiệu thay thế.

### Chưa triển khai — lý do cụ thể

Audit thực tế nhiều nguồn ứng viên khác (bao gồm cả nguồn spec V2 gốc và nguồn "chính thống" tìm thêm), loại với lý do rõ ràng thay vì đoán bừa:

| Nguồn dự kiến | Vấn đề phát hiện khi audit |
|---|---|
| VietnamNet — Kinh tế | RSS chính thức `vietnamnet.vn/kinh-doanh.rss` (được chính trang khai báo là feed canonical) bị đứng — item mới nhất từ 08/08/2026, hơn 1 tháng không cập nhật. Dùng feed này sẽ không bao giờ có tin mới thật. |
| Người Lao Động — Kinh tế | Domain `nld.com.vn` đã redirect toàn bộ sang `tuoitre.vn` (đã sáp nhập vào Tuổi Trẻ) — không còn là nguồn tin độc lập. |
| VietnamFinance | RSS tồn tại (`vietnamfinance.vn/tai-chinh.rss`) nhưng thực chất là feed proxy qua Google News, `lastBuildDate` cũ hơn 2 tuần tại thời điểm audit — không đủ tin cậy cho chu kỳ ngắn. |
| Nhịp sống Kinh tế | Đây chính là tagline/tên gọi khác của VnEconomy, không phải một trang riêng biệt — trùng với nguồn VnEconomy đã thêm. |
| BizLIVE | Domain `bizlive.vn` đã redirect sang `nhipsongkinhdoanh.vn` (rebrand), nhưng chưa tìm được RSS lẫn cấu trúc HTML rõ ràng để scrape ở domain mới. |
| Bnews (thuộc TTXVN) | Không tìm thấy RSS ở bất kỳ pattern chuẩn nào (toàn bộ trả HTTP 404/500), trang chủ cũng không khai báo `<link rel="alternate">` nào — có thể site không có RSS. Chưa audit HTML scraping. |
| VOV | **Đã từng thêm ở đợt trước, sau đó loại bỏ (15/09/2026)** — WAF chặn User-Agent mặc định của app, phải override UA riêng mới qua được, và trên thực tế vẫn thỉnh thoảng lỗi trong lúc chạy production (xuất hiện `⚠️ Nguồn lỗi: VOV` dù đã override UA) — không đủ ổn định để giữ lại. |

Muốn triển khai tiếp BizLIVE/Bnews, việc chính là audit cấu trúc HTML của domain hiện tại rồi viết crawler `crawl()` override theo đúng mẫu 4 crawler HTML ở trên.

## Format Telegram

Mỗi nguồn có 1 icon riêng để nhận diện nhanh không cần đọc chữ (bảng icon ở trên). Ví dụ tin nhắn thật:

```
📬 5 bài mới · 3 nguồn

🚨 TIN NÓNG

💱 Ngân hàng Nhà nước bất ngờ tăng lãi suất điều hành — 14/09 14:32 (VietnamBiz)

🏛️ CHÍNH PHỦ (2 bài)

• Cửa khẩu số hóa, doanh nghiệp thêm lựa chọn thanh toán CNY — 14/09 18:44
• Vietjet và Thales mở rộng hợp tác hàng không công nghệ cao — 13/09 20:01

🔵 VNEXPRESS (1 bài)

• Tesla lập công ty ở Việt Nam — 14/09 14:55

💱 VIETNAMBIZ (1 bài)

• Tỷ giá euro ngày 15/9: Euro tiếp tục mất giá — 15/09 09:02
```

Title là link click được (Telegram `parse_mode=HTML`), tên nguồn in đậm kèm số bài. Nếu 1 chu kỳ có nguồn lỗi, dòng `⚠️ Nguồn lỗi: ...` được thêm vào cuối cùng 1 tin nhắn này — không tách thành tin riêng (tối đa 1 batch/chu kỳ, chỉ tách khi vượt 4096 ký tự, xem mục "Luồng xử lý" bên dưới).

**Vì sao mỗi giờ luôn kèm ngày (`dd/mm HH:MM`) thay vì chỉ `HH:MM`:** một số feed (VTV rõ nhất — audit cho thấy 1 lần fetch có thể chứa bài trải dài **~25 ngày** khác nhau) khiến 1 đợt "bài mới" đôi khi gồm cả bài từ nhiều ngày khác nhau, không chỉ hôm nay. Sắp xếp bên trong luôn đúng theo ngày-giờ đầy đủ, nhưng nếu chỉ hiện giờ thì nhìn vào sẽ tưởng thứ tự bị lộn xộn (bài "12:45" đứng trước "04:26" chẳng hạn) — trong khi thực ra chúng thuộc 2 ngày khác nhau và đã đúng thứ tự.

### Tin nóng (🚨 TIN NÓNG)

Vấn đề gốc: khi nhiều bài đổ về cùng lúc, thứ tự hiển thị chỉ theo cấu hình nguồn (cố định) — 1 tin thị trường quan trọng từ nguồn cấu hình cuối cùng (VD: VTV) có thể nằm tuốt cuối tin nhắn, dễ bị bỏ sót nếu chỉ lướt nhanh vài giây.

Cách xử lý: `telegram.HOT_KEYWORDS` (rule-based, không dùng AI) là danh sách từ khóa mang tính khẩn cấp/đột biến trong tài chính (`tăng vọt`, `giảm sốc`, `lao dốc`, `phá sản`, `khủng hoảng`, `kỷ lục`...). Bài nào khớp bất kỳ từ khóa nào (không phân biệt hoa/thường) được **tách ra khỏi khối nguồn của nó**, gộp vào 1 khối `🚨 TIN NÓNG` ở **đầu tin nhắn**, kèm icon + tên nguồn để không mất ngữ cảnh.

Đây chỉ là bộ lọc từ khóa đơn giản, không hiểu ngữ nghĩa — có thể bỏ sót tin quan trọng không dùng đúng từ trong danh sách, hoặc thỉnh thoảng bắt nhầm tin không thật sự khẩn cấp. Chỉnh danh sách `HOT_KEYWORDS` trong [telegram.py](telegram.py) dựa trên thực tế dùng (thêm từ hay bị bỏ sót, bớt từ hay bắt nhầm).

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

Dự án **không dùng Playwright** — không có site nào trong 18 site đang chạy cần browser automation (kể cả 4 site scrape HTML — toàn bộ đều lấy được qua HTML tĩnh, không cần JS render) (xem bảng RSS ở trên), đúng theo ưu tiên "chỉ dùng Playwright khi thực sự cần" trong spec.

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

Các biến khác (`CRAWL_INTERVAL_MINUTES`, `REQUEST_TIMEOUT`, `MAX_RETRIES`, `INITIAL_SCAN_SEND`, `LOG_LEVEL`, `TIMEZONE`, `STALE_SOURCE_HOURS`, `STALE_ALERT_COOLDOWN_HOURS`, `BACKUP_KEEP_DAYS`) đã có giá trị mặc định hợp lý (20 phút/lần, cả ngày lẫn đêm), chỉ cần chỉnh nếu muốn.

**Không commit `.env` lên Git** — đã có trong `.gitignore`.

## Chạy thử (không cần Telegram token)

```bash
python main.py --dry-run
```

Dry run: crawl → parse → kiểm tra trùng với database hiện có → in ra terminal. **Không ghi database, không gửi Telegram.** Dùng lệnh này để kiểm tra 18 crawler còn hoạt động tốt không, bất cứ lúc nào.

## Chạy test tự động

```bash
pytest
```

109 test bao phủ: normalize title/URL (kể cả giải mã HTML entity lỗi của Thanh Niên/VietnamBiz), crawler parse RSS cho 14 nguồn (kèm test riêng cho 3 kiểu parse ngày phi chuẩn của Chính phủ/VTV/VietnamBiz) và crawler scrape HTML cho 4 nguồn còn lại (lọc khối "nổi bật" không có giờ ở CafeBiz, chống 1 bài xuất hiện nhiều lần với giờ khác nhau ở Đầu tư Chứng khoán, báo lỗi khi selector không khớp gì thay vì âm thầm "0 bài mới") (dùng fixture lấy từ dữ liệu thực tế lúc audit, mock qua thư viện `responses` — không cần mạng), dedup theo URL (không theo title), restart không mất/không gửi lại dữ liệu, format Telegram group-theo-nguồn + tách tin nóng + chia nhỏ khi vượt giới hạn 4096 ký tự, retry khi gửi Telegram lỗi, cô lập lỗi từng nguồn không làm crash app, giữ đúng thứ tự nguồn theo cấu hình, baseline seeding lần chạy đầu **và** baseline riêng cho nguồn mới thêm vào một DB đã có dữ liệu, toàn bộ luồng `run_cycle` (dry-run / gửi thành công / lỗi 1 phần vẫn gửi tin nguồn OK / tất cả lỗi / Telegram lỗi thì không đánh dấu sent), phát hiện nguồn "chết âm thầm" (ngưỡng giờ, cooldown cảnh báo, tự gỡ cảnh báo khi hồi phục), backup database (tạo bản có timestamp + tự xoá bản cũ), và **lịch quét cố định** — kiểm tra thời điểm bắn thật của `CronTrigger` (APScheduler) khớp đúng mỗi `CRAWL_INTERVAL_MINUTES` phút, xuyên suốt nửa đêm không hở/chồng giờ nào; hiển thị ngày kèm giờ (`dd/mm HH:MM`) cho batch trải dài nhiều ngày, và trang web tĩnh (`web/generate_site.py`) — gom bài theo đúng ngày kể cả khi thiếu `published_at`, sắp mới nhất lên đầu trong từng nguồn, escape HTML tiêu đề (chống XSS từ tiêu đề bài crawl được), luôn dọn sạch `site/` cũ trước khi sinh lại thay vì cộng dồn file rác, và cửa sổ 7-tab ngày (`_tab_window`) tự căn giữa quanh ngày đang xem, kể cả 2 trường hợp biên: ít hơn 7 ngày dữ liệu, và đang xem đúng ngày cũ nhất.

## Chạy lần đầu / chạy thủ công

```bash
python main.py --run-once
```

Nếu đây là lần chạy đầu tiên (database rỗng) và `INITIAL_SCAN_SEND=false` (mặc định): app sẽ **âm thầm ghi nhận toàn bộ bài hiện có làm baseline, không gửi Telegram** — tránh spam hàng trăm tin cũ. Từ lần chạy tiếp theo trở đi, chỉ bài thực sự mới mới được gửi.

Nếu muốn gửi luôn cả các bài đang có ngay từ lần chạy đầu, đặt `INITIAL_SCAN_SEND=true` trong `.env` trước khi chạy lần đầu.

**V2:** nếu database đã có dữ liệu (app đã chạy từ trước) và bạn vừa thêm một crawler mới, app tự phát hiện nguồn đó "chưa có lịch sử" và âm thầm baseline riêng cho đúng nguồn đó — không đụng tới trạng thái của các nguồn cũ, không flood Telegram hàng loạt bài cũ của nguồn mới. Hành vi này chạy tự động, không cần config gì thêm.

## Chạy production (scheduler tần suất cố định)

```bash
python main.py
```

App tự động crawl **mỗi `CRAWL_INTERVAL_MINUTES` phút, cả ngày lẫn đêm** (mặc định 20 phút, không còn phân biệt khung giờ ngày/đêm — bản trước có tách lịch nhanh/chậm theo giờ nhưng đã bỏ theo yêu cầu người dùng vì thêm phức tạp không cần thiết), canh theo mốc giờ tròn, và chạy 1 lần ngay khi khởi động. Dừng bằng `Ctrl+C`.

Đây là 1 `CronTrigger` duy nhất của `APScheduler` với `max_instances=1` — nếu 1 chu kỳ chưa crawl/gửi xong khi mốc tiếp theo tới, chu kỳ mới **tự động bị bỏ qua** thay vì chạy chồng lên (spec V2 mục 19). Không cần thêm lock file hay cấu hình gì khác.

## V3 — Cảnh báo nguồn "chết âm thầm"

Một RSS feed có thể vẫn trả về HTTP 200 bình thường (không lỗi, không bị `crawl_all` phát hiện) nhưng **nội dung bên trong không còn cập nhật** — đây là sự cố thật đã gặp với VietnamNet lúc audit V2 (feed đứng >1 tháng, không hề báo lỗi gì). App tự phát hiện kiểu lỗi này:

- Với mỗi nguồn crawl **thành công**, app theo dõi thời điểm bài mới nhất thực sự được ghi vào database (`first_seen_at`, không phải `published_at` — tránh phụ thuộc đồng hồ của từng site).
- Nếu 1 nguồn không có bài mới nào trong hơn `STALE_SOURCE_HOURS` giờ (mặc định **24h**), app gửi cảnh báo riêng:
  ```
  🩺 NEWS MONITOR — Cảnh báo nguồn

  Các nguồn sau không có bài mới nào trong hơn 24h qua — có thể RSS đã hỏng hoặc đổi cấu trúc, nên kiểm tra lại:

  - VietnamNet (bài mới gần nhất: 08/08/2026 10:54)
  ```
- Để tránh spam lặp lại mỗi chu kỳ, cùng 1 nguồn chỉ được cảnh báo lại sau mỗi `STALE_ALERT_COOLDOWN_HOURS` giờ (mặc định **24h**).
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

## Deploy bằng GitHub Actions (miễn phí, không cần VPS)

Đây là cách chạy 24/7 hoàn toàn miễn phí mà không cần quản lý server nào — dùng chính GitHub để tự động chạy `python main.py --run-once` mỗi 20 phút, cả ngày lẫn đêm (xem workflow). Workflow đã có sẵn tại [.github/workflows/news-crawl.yml](.github/workflows/news-crawl.yml).

### Vấn đề kỹ thuật đã xử lý sẵn

Máy chạy GitHub Actions là **tạm thời** — mỗi lần chạy là 1 máy ảo mới tinh, không giữ được `data/news.db` giữa các lần như chạy trên VPS. Nếu không xử lý, app sẽ coi mọi bài là "mới" mỗi lần chạy và spam Telegram vô tận.

Cách giải quyết: workflow lưu `data/news.db` trên 1 **nhánh riêng** `db-state`, hoàn toàn tách biệt khỏi `main`. Mỗi lần chạy: đọc `data/news.db` từ `db-state` (nếu đã có) → chạy `--run-once` → build commit mới chỉ chứa file db bằng git plumbing (`hash-object`/`mktree`/`commit-tree`, không cần checkout đổi nhánh) → force-push đè commit đó lên `db-state`. Nhánh này luôn chỉ có đúng 1 commit (không có "lịch sử" gì để giữ), nên không bao giờ phình dù chạy hàng nghìn lần — và quan trọng nhất, **`main` không bao giờ bị workflow này đụng vào**.

> **Vì sao không force-push thẳng lên `main` như thiết kế ban đầu:** phiên bản đầu tiên của workflow amend + force-push commit database ngay trên `main`. Sau đó, lịch `schedule` (cron) tự nhiên **ngừng tự kích hoạt** dù chạy tay (`workflow_dispatch`) vẫn hoạt động bình thường. Ban đầu nghi ngờ do force-rewrite đầu nhánh mặc định. Tuy nhiên, sau khi tách database ra nhánh riêng (loại bỏ hoàn toàn việc đụng vào `main`), hiện tượng "cron ngừng tự chạy" vẫn lặp lại **chỉ từ việc sửa nội dung `schedule: cron` trong workflow** — bằng chứng cho thấy nguyên nhân thật sự là: **mỗi lần sửa biểu thức cron, hệ thống lập lịch nền của GitHub cần một khoảng thời gian (quan sát được là ~1-2 tiếng) để đăng ký lại lịch mới**, hoàn toàn ở phía GitHub, không phải do code hay cấu trúc repo. Vì vậy sau khi sửa cron (như lần đổi sang 20 phút/lần này), cron tự động có thể im lặng một thời gian trước khi chạy lại — dùng **Run workflow** để chạy tay ngay lập tức, không cần chờ.

**Đánh đổi cần biết:** vì `db-state` bị force-push đè mỗi lần, git history **không** giữ lại lịch sử database theo từng mốc thời gian (khác với backup thật ở chế độ VPS) — chỉ có bản mới nhất. Job backup nội bộ 03:00 hàng ngày (`run_backup` trong `scheduler.py`) cũng **không chạy** ở chế độ này vì `--run-once` không khởi động `BlockingScheduler`. Nếu cần point-in-time backup thật khi chạy bằng GitHub Actions, đây là điểm có thể mở rộng thêm sau.

### Cách setup

1. **Thêm GitHub Secrets** (Settings → Secrets and variables → Actions → New repository secret):
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`

2. **Đẩy code lên GitHub** (nếu chưa) — workflow tự động kích hoạt ngay khi file `.github/workflows/news-crawl.yml` có mặt trên nhánh mặc định.

3. **Chạy thử thủ công** để xác nhận hoạt động ngay, không cần đợi lịch: vào tab **Actions** trên GitHub → chọn workflow **Crawl news** → **Run workflow**.

4. Từ đó app tự chạy mỗi 20 phút, xem log từng lần chạy trong tab **Actions**.

### Lưu ý quan trọng

- **Không nên chạy đồng thời cả VPS/local daemon lẫn GitHub Actions** — dù từ bản cập nhật này database của 2 chế độ đã tách biệt (`data/news.db` cục bộ cho VPS/local vs. nhánh `db-state` riêng cho GitHub Actions, không còn tranh nhau ghi file/git nữa), 2 tiến trình độc lập vẫn sẽ **tự dedup riêng và gửi trùng tin lên cùng 1 Telegram chat**. Chọn 1 trong 2 cách để chạy production thật.
- Lịch chạy của GitHub Actions (`schedule: cron`) là **best-effort** — GitHub không đảm bảo đúng giờ tuyệt đối, có thể trễ vài phút khi hệ thống tải cao (bình thường, không phải lỗi app).
- Nếu repo không có commit nào trong 60 ngày, GitHub tự tắt scheduled workflow — nhưng vì chính workflow này commit database định kỳ nên tự nó giữ repo "hoạt động", không bị tắt.
- Cần bật quyền ghi cho Actions nếu tổ chức/tài khoản bạn đã tắt mặc định: Settings → Actions → General → Workflow permissions → **Read and write permissions**.

## V4 — Trang web tổng hợp tin tức (GitHub Pages)

Ngoài Telegram, mỗi lần crawl cũng sinh ra 1 **trang web tĩnh** liệt kê lại toàn bộ tin đã thu thập, xem lại được theo từng ngày — hữu ích khi cần tra cứu lịch sử thay vì chỉ xem được đúng đợt tin mới nhất trên Telegram.

- Module sinh trang: [web/generate_site.py](web/generate_site.py) — đọc toàn bộ `data/news.db` (`Database.get_all_articles`), gom theo **ngày** (theo `published_at`, hoặc theo `first_seen_at` nếu nguồn không có ngày — ví dụ Báo Đầu tư) rồi theo **nguồn** (đúng thứ tự cấu hình như Telegram), xuất ra các file HTML tĩnh thuần (gần như không JS, không build tool) vào thư mục `site/`.
- Mỗi ngày có 1 file `site/YYYY-MM-DD.html`; `site/index.html` luôn là bản sao của ngày mới nhất.
- **Giao diện:** dạng bảng Kanban nằm ngang — mỗi nguồn 1 cột (viền đen + đổ bóng cứng offset, không dùng gradient/soft-shadow kiểu SaaS phổ biến), cả hàng **cuộn ngang**, mỗi cột **tự cuộn dọc riêng** khi quá dài (VTV có ngày lên tới 500 bài) thay vì kéo dài cả trang. Bấm vào thanh tiêu đề của 1 cột để **đóng/mở** cột đó — dùng `<details>/<summary>` gốc của HTML nên không cần JS. Màu riêng theo từng nguồn chỉ xuất hiện ở 1 viền trên mỏng + 1 ô icon nhỏ (không tô cả thanh tiêu đề) — ban đầu dùng màu phẳng sặc sỡ nhìn "chợ Tết" khi nhiều cột đứng cạnh nhau, đã đổi sang tông trầm/muted hơn cho chuyên nghiệp hơn theo phản hồi thực tế. Thanh điều hướng ngày cố định **7 tab trải đều hết chiều ngang** (theo yêu cầu), tự căn giữa quanh ngày đang xem; ngày cũ hơn 7 tab đó vẫn xem được qua dropdown "Ngày khác" ngay bên dưới.
- Xem thử ở máy (không cần mạng, không cần Telegram):
  ```bash
  python -m web.generate_site
  ```
  rồi mở `site/index.html` bằng trình duyệt bất kỳ.
- **Deploy:** [.github/workflows/news-crawl.yml](.github/workflows/news-crawl.yml) tự sinh lại `site/` và deploy lên **GitHub Pages** sau mỗi lần crawl, bằng action chính chủ của GitHub (`actions/upload-pages-artifact` + `actions/deploy-pages`) — không cần thêm nhánh riêng hay dịch vụ hosting nào khác.
- **Cần bật 1 lần duy nhất:** Settings → Pages → Build and deployment → Source → chọn **"GitHub Actions"** (không chọn "Deploy from a branch"). Sau đó URL trang sẽ hiện ở đúng mục Settings → Pages này (dạng `https://<username>.github.io/<repo>/`), và cũng hiện trong output của mỗi lần chạy workflow (bước "Deploy to GitHub Pages").

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

`main.py` (không tham số) đã tự chứa scheduler bên trong (`BlockingScheduler`), nên chỉ cần systemd giữ tiến trình sống — không cần cron gọi lặp lại.

### Cron (thay thế, nếu không dùng systemd)

Cách khác — theo đúng gợi ý ở spec mục 2 — là để cron gọi `--run-once` thay vì chạy `main.py` daemon (giả định crontab của VPS đã đặt múi giờ `Asia/Ho_Chi_Minh` — nếu không, đổi giờ cho khớp UTC như cách làm ở mục GitHub Actions bên trên):

```cron
*/20 * * * * cd /opt/news-monitor && /opt/news-monitor/.venv/bin/python main.py --run-once >> logs/cron.log 2>&1
```

Cách này restart-safe tự nhiên (mỗi lần chạy là 1 process độc lập, không có state daemon để mất), nhưng **không** có bảo vệ "không chạy chồng" tự động như `max_instances=1` của APScheduler — nếu 1 lần chạy kéo dài hơn khoảng cách giữa 2 lần cron (mạng chậm/1 nguồn treo), 2 tiến trình có thể trùng nhau. Nếu chọn cách này, nên thêm `flock` để tự loại trừ:

```cron
*/20 * * * * flock -n /tmp/news-monitor.lock -c "cd /opt/news-monitor && .venv/bin/python main.py --run-once >> logs/cron.log 2>&1"
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
3. Nếu không có RSS: subclass `BaseCrawler` trực tiếp (đã có sẵn `_fetch()` dùng chung, không cần viết lại phần HTTP/retry), tự viết `crawl()` parse HTML bằng `beautifulsoup4` (đã có trong `requirements.txt`), trả về `List[NewsItem]` giống hệt interface RSS — xem `crawlers/cafebiz.py` làm mẫu, đặc biệt chú ý: kiểm tra bài có bị lặp lại nhiều lần trên cùng 1 trang không (widget "liên quan" hay lấy lại link ảnh + link tiêu đề cùng class), và nếu trang không hiện giờ đăng ở đâu cả thì cứ để `published_at=None` (đừng đoán giờ) — xem `crawlers/baodautu.py`.
4. Thêm crawler mới vào `CRAWLER_CLASSES` trong `crawlers/__init__.py` — thứ tự trong list quyết định thứ tự hiển thị trên Telegram.
5. Thêm 1 fixture RSS/HTML nhỏ (2-3 bài thật) vào `tests/fixtures/`, thêm dòng vào `CRAWLERS_AND_FIXTURES` trong `tests/test_crawlers.py` (RSS) hoặc viết test riêng trong `tests/test_html_crawlers.py` (HTML).
6. Chạy `pytest` rồi `python main.py --dry-run` để xác nhận trước khi chạy production.
7. Không cần migration DB hay đổi schema — nguồn mới tự động được baseline riêng ở lần chạy `--run-once`/scheduler đầu tiên sau khi thêm (xem mục "Chạy lần đầu / chạy thủ công" ở trên).

## Về việc test crawler bằng mạng thật

Toàn bộ crawler đã được audit và test bằng dữ liệu **thực tế** lấy trực tiếp từ 18 site vào ngày 14-15/09/2026 (xem bảng ở trên). Test tự động (`pytest`) dùng fixture dựng lại từ dữ liệu thật đó, chạy offline, đáng tin cậy và lặp lại được.

Ngoài ra, toàn bộ luồng end-to-end (crawl → dedup → Telegram → sent_at, bao gồm baseline seeding, baseline riêng cho nguồn mới, phát hiện bài mới thật sự, không gửi trùng lần 2, restart không mất dữ liệu, và báo lỗi khi 1 nguồn fail) đã được xác minh bằng cách chạy `main.py --run-once` thật với Telegram Bot API thật (không mock) trong lúc phát triển.

**Việc bạn cần tự làm định kỳ:** chạy `python main.py --dry-run` để xác nhận 18 crawler vẫn lấy đúng dữ liệu tại thời điểm bạn dùng — RSS/HTML thường ổn định nhưng không có gì đảm bảo 100% một site sẽ không đổi cấu trúc trong tương lai (xem case Tiền Phong ở trên: 1 category ID sai vẫn trả HTTP 200 bình thường; 4 crawler HTML tự báo lỗi nếu selector không còn khớp gì).

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
│   ├── base.py          # BaseCrawler (fetch/retry dùng chung) + RSSCrawlerBase
│   ├── vnexpress.py
│   ├── tuoitre.py
│   ├── cafef.py
│   ├── vietstock.py
│   ├── thanhnien.py
│   ├── dantri.py            # V2 (RSS)
│   ├── vneconomy.py         # V2 (RSS)
│   ├── znews.py             # V2 (RSS)
│   ├── tienphong.py         # V2 (RSS)
│   ├── vietnamplus.py       # V2 (RSS)
│   ├── nhandan.py           # V2 (RSS)
│   ├── baochinhphu.py       # V2 (RSS, parse ngày riêng)
│   ├── vtv.py               # V2 (RSS, parse ngày riêng)
│   ├── vietnambiz.py        # V3 (RSS, parse ngày riêng)
│   ├── cafebiz.py           # V3 (scrape HTML)
│   ├── tinnhanhchungkhoan.py # V3 (scrape HTML)
│   ├── diendandoanhnghiep.py # V3 (scrape HTML)
│   └── baodautu.py          # V3 (scrape HTML, luôn published_at=None)
├── data/news.db         # SQLite (tự tạo khi chạy, không commit)
├── logs/app.log         # Log (tự tạo khi chạy, không commit)
└── tests/
```

### Luồng xử lý mỗi chu kỳ (`scheduler.run_cycle`)

1. Crawl cả 18 nguồn, lỗi 1 nguồn không làm hỏng nguồn khác (`crawl_all`).
2. Với mỗi bài lấy được: normalize title/URL, `INSERT OR IGNORE` vào SQLite theo URL (dedup) — **insert xảy ra trước khi thử gửi Telegram**, nên nếu app crash hoặc Telegram lỗi giữa chừng, bài viết vẫn còn trong DB với `sent_at = NULL` và sẽ được thử gửi lại ở chu kỳ sau (không mất dữ liệu, không tạo bản ghi trùng).
3. Lấy toàn bộ bài chưa gửi (`get_pending`), group theo nguồn theo đúng thứ tự khai báo trong `CRAWLER_CLASSES` (không sort theo thời gian toàn cục — spec V2 mục 12).
4. Chọn đúng 1 trong 4 kịch bản, luôn ưu tiên gửi **1 batch Telegram / chu kỳ** (spec V2 mục 15):
   - **Có bài mới** (dù có hay không có nguồn lỗi): gửi 1 message group-theo-nguồn, kèm dòng "⚠️ Nguồn lỗi: ..." ở cuối nếu có nguồn lỗi. Chỉ tách nhiều message nếu vượt 4096 ký tự.
   - **Không có bài mới, tất cả nguồn đều lỗi**: gửi "🔴 NEWS MONITOR — Không thể hoàn tất lượt quét" kèm danh sách nguồn lỗi.
   - **Không có bài mới, một phần nguồn lỗi**: gửi "⚠️ NEWS MONITOR — Không có tin mới từ các nguồn hoạt động" kèm danh sách nguồn lỗi — **không bao giờ** báo nhầm thành "không có tin mới" khi thực ra có nguồn đang chết.
   - **Không có bài mới, mọi nguồn OK**: gửi "🟢 NEWS MONITOR — Không có tin mới."
5. Chỉ đánh dấu `sent_at` sau khi Telegram xác nhận gửi thành công.

### Vì sao không dùng thư viện `python-telegram-bot`

`python-telegram-bot` (bản v20+) là thư viện async, khá nặng cho nhu cầu ở đây (gọi 1 API POST đơn giản, đồng bộ, vài chục lần mỗi ngày). `telegram.py` dùng thẳng `requests` gọi Telegram Bot API (`parse_mode=HTML` để title là hyperlink click được) — ít dependency hơn, dễ đọc từ đầu đến cuối, đúng tinh thần "SIMPLE STABLE MAINTAINABLE" của spec.

## Giới hạn đã biết

Không AI, không dashboard, không Docker/Redis/PostgreSQL, không proxy rotation, không sentiment/event clustering — đúng danh sách "V2 KHÔNG LÀM" trong spec. HTML-scraping fallback (BeautifulSoup) đã có dependency sẵn sàng, sẽ cần dùng cho 2 nguồn còn thiếu RSS (Đầu tư Chứng khoán, BizLIVE/Nhịp sống kinh doanh) ở đợt phát triển tiếp theo — xem mục "Chưa triển khai trong V2 này" ở trên.
