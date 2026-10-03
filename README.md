# Vietnam News Monitor

Theo dõi 19 chuyên mục kinh tế/tài chính của báo Việt Nam (gồm cả báo nhà nước/thông tấn chính thống), phát hiện bài mới, chống gửi trùng, và đẩy title (kèm link) + thời gian về Telegram — **group theo từng nguồn báo (icon riêng để phân biệt nhanh), tách riêng tin nóng lên đầu**. Quét mỗi 20 phút/lần, cả ngày lẫn đêm (không phân biệt khung giờ).

Xem đầy đủ yêu cầu gốc trong `PROJECT SPEC V2` đã cung cấp. README này chỉ tập trung vào cách chạy.

## Nguồn báo

### Đang hoạt động (23 nguồn)

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
| 💱 | VietnamBiz | `vietnambiz.vn/tai-chinh` | `vietnambiz.vn/tai-chinh.rss` — **lưu ý:** `pubDate` dùng `"GMT+7"` thay vì `+0700` chuẩn (một quirk khác với `+07` của VTV), cũng khiến `feedparser` không parse được, `VietnamBizCrawler` có logic parse riêng. Cũng dính lỗi double-encode HTML entity giống Thanh Niên trong `<title>` — đã tự được vá bởi fix chung, không cần thêm gì. **Audit 2026-09-16:** feed từng báo lỗi "not well-formed" toàn bộ — nguyên nhân là XML prolog khai `encoding="utf-16"` trong khi nội dung thực là UTF-8, khiến parser XML (expat) đọc sai ngay từ đầu. `VietnamBizCrawler._preprocess_raw` sửa lại đúng khai báo trước khi đưa cho `feedparser`. |
| 🌐 | VietnamNet | `vietnamnet.vn/kinh-doanh` | `vietnamnet.vn/rss/kinh-doanh.rss` — feed rất lớn (~1000 bài, quay lại tới đầu tháng 8), an toàn nhờ dedup URL và baseline riêng cho nguồn mới (audit 24/09/2026) |
| 🔭 | Người Quan Sát | `nguoiquansat.vn` | Gộp 5 feed chuyên mục kinh tế `nguoiquansat.vn/rss/{tai-chinh-ngan-hang,vi-mo,doanh-nghiep,chung-khoan,bat-dong-san}` (audit lại 03/10/2026: feed `trang-chu` cũ có 23/40 bài ngoài kinh tế — kỷ luật Đảng, hình sự, giáo dục, quân sự) |
| 🌆 | SGGP | `sggp.org.vn/kinhte/` | `sggp.org.vn/rss/kinh-te-89.rss` — **lưu ý:** `kinhte-3.rss` nghe giống nhưng thực chất là mục "Đô thị"; `pubDate` dạng `+07:00` (audit 24/09/2026) |
| 🌏 | VnExpress Intl | `e.vnexpress.net/news/business` | `e.vnexpress.net/rss/business.rss` — tiêu đề tiếng Anh, hiện trong luồng tin nhưng không được gom vào issue (engine từ khoá tiếng Việt) |

Vì vậy 18/23 crawler dùng chung `RSSCrawlerBase` (`crawlers/base.py`) nhưng mỗi site vẫn là **1 file riêng** trong `crawlers/` — nếu sau này RSS của 1 site đổi cấu trúc hoặc ngừng hoạt động, chỉ sửa đúng file đó mà không ảnh hưởng các site còn lại. 4 site (Chính phủ, VTV, VietnamBiz, Tuổi Trẻ) cần override nhỏ (`_extract_published_at` cho định dạng ngày lạ) — vẫn kế thừa toàn bộ phần còn lại từ `RSSCrawlerBase`, không viết lại từ đầu.

Một chi tiết đáng chú ý khi audit V1: CafeF và Thanh Niên trả `pubDate` với năm 2 chữ số (`"Mon, 14 Sep 26 08:00:00 +0700"`). `feedparser` tự parse đúng thành năm 2026 qua `published_parsed`, nên không cần tự viết logic parse ngày riêng cho từng site. Thanh Niên còn có thêm 1 lỗi double-encode HTML entity trong `<title>` (vd. `n&agrave;y` thay vì `này`) — đã vá bằng `html.unescape()` trong `utils.normalize_title`.

### 4 nguồn không có RSS — scrape HTML bằng BeautifulSoup

`crawlers/base.py`'s `BaseCrawler` giờ tự chứa sẵn `_fetch()` (HTTP + retry, dùng chung cho cả RSS lẫn HTML), nên 1 crawler HTML chỉ cần override `crawl()`, tự parse bằng `BeautifulSoup` — không cần viết lại phần fetch/retry.

| Icon | Nguồn | Trang scrape | Ghi chú audit |
|---|---|---|---|
| ☕ | CafeBiz | `cafebiz.vn/cau-chuyen-kinh-doanh.chn` | Không có RSS cho chuyên mục này (home.rss lẫn thời tiết/công nghệ/giải trí). Trang chuyên mục cũng trộn 2 phần: khối "nổi bật" phía trên (đôi khi lẫn tin thể thao/giải trí, **không có giờ**) và danh sách chính bên dưới (đúng chủ đề, có giờ). Lọc theo "có giờ hay không" để loại khối nổi bật, không cần đoán chủ đề. |
| 📉 | Đầu tư Chứng khoán | `tinnhanhchungkhoan.vn/chung-khoan/` | Không tìm được RSS ở bất kỳ pattern nào. **Lưu ý quan trọng:** cùng 1 bài có thể xuất hiện tới 4 lần trên 1 trang (danh sách chính + các widget "liên quan" khác), mỗi lần 1 giờ khác nhau hoặc không giờ — lấy đúng lần xuất hiện **đầu tiên** (danh sách chính, mới nhất) thay vì để lần cuối ghi đè. Bài nào listing không có giờ (widget con) thì crawler tự fetch thêm trang chi tiết bài đó để lấy `<time datetime="...">` — chỉ tốn thêm request cho đúng số bài thiếu giờ, không phải toàn bộ (audit 2026-09-16). |
| 🏢 | Diễn đàn Doanh nghiệp | `diendandoanhnghiep.vn/chinh-tri-xa-hoi/kinh-te` | Không có RSS, không khai báo `<link rel="alternate">`. Định dạng giờ dạng text `dd/mm/yyyy HH:MM` (không phải ISO). Bài nổi bật đầu trang không có giờ trong listing → crawler fetch thêm trang chi tiết, lấy từ `<meta name="article:published_time">` (audit 2026-09-16). |
| 💼 | Báo Đầu tư | `baodautu.vn/dau-tu-tai-chinh-d6/` | RSS luôn trả kênh rỗng bất kể slug (xem bảng dưới). Trang chuyên mục **không hiển thị giờ đăng ở bất kỳ đâu** trong toàn bộ danh sách (mọi cỡ thẻ). Audit 2026-09-16: trang chi tiết từng bài lại có (`.post-time`) — nên giờ crawler fetch thêm mỗi trang bài để lấy giờ thật, đổi lấy N+1 request/lượt quét thay vì 1 (chấp nhận theo yêu cầu, vì thiếu giờ ảnh hưởng nhiều hơn phần traffic tăng thêm). |

Cả 4 crawler đều tự phát hiện khi selector không còn khớp gì cả (0 bài) và báo lỗi thay vì âm thầm báo "0 bài mới" mãi mãi — HTML không có "chuẩn" như RSS để biết chắc site có đổi cấu trúc hay không, nên đây là tín hiệu thay thế.

### FiLi — scrape HTML (trước 03/10/2026 là JSON API ẩn)

| Icon | Nguồn | Trang | Ghi chú audit |
|---|---|---|---|
| 🛡️ | FiLi | `fili.vn/ngan-hang-bao-hiem.htm` | Audit lại 2026-10-03: API cũ `POST /_Partials/ListPageArticle` trả **405** và trang chuyển từ SPA AngularJS sang HTML render sẵn (không có RSS: mọi biến thể `.rss` đều 404). Giờ `crawlers/fili.py` đọc `article.search-card-item` (10 bài/trang). Giờ đăng chỉ có dạng "4 giờ trước" hoặc "02/10/2026 20:58" — crawler đổi cả hai ra thời điểm thật (dạng tương đối tính theo lúc quét, chính xác tới đơn vị hiển thị). Lỗi này phát hiện nhờ crawl thật cả 23 nguồn khi rà soát lại; không có cảnh báo tự động nào bắt được nếu không chạy tay. |

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
📡 TOP TÍN HIỆU

1. Eximbank · Nhân sự lãnh đạo
17 bài / 6 nguồn
↑ Đang tăng tốc

2. Fed · Lãi suất
8 bài / 5 nguồn
● Ổn định

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

### Top tín hiệu (📡 TOP TÍN HIỆU) — roadmap V2 §19

Dẫn đầu tin nhắn (trước cả 🚨 TIN NÓNG), lấy đúng Top 5 issue theo SignalScore mà `scheduler.snapshot_data()` đã tính cho hôm nay (mục "Top 5 Issues hôm nay" bên dưới) — không tính lại lần 2, chỉ tái sử dụng. Mỗi dòng kèm trạng thái vòng đời (★ Mới xuất hiện / ↑ Đang tăng tốc / ● Ổn định / ↓ Đang hạ nhiệt). Chỉ xuất hiện khi chu kỳ đó có bài mới để gửi và khi có ít nhất 1 issue đạt ngưỡng Top Issues; `snapshot_data()` thất bại (best-effort, hiếm) thì digest vẫn gửi, chỉ thiếu mục này. Lý do đặt lên đầu, đúng như nguyên tắc gốc của roadmap: người xem cần biết chuyện gì đáng chú ý trước khi đọc từng title riêng lẻ.

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

## Watchlist cá nhân — riêng tư, chỉ qua Telegram (roadmap V4)

Muốn được ping riêng khi có tin mới về công ty/mã/chủ đề bạn cá nhân quan tâm (khác với watchlist thương hiệu công khai ở mục "Trang web tổng hợp" bên dưới, vốn phục vụ trang `brands.html` công khai)? Copy file mẫu:

```bash
cp personal_watchlist.example.json personal_watchlist.json
```

rồi sửa danh sách `entities` theo ý bạn, ví dụ:

```json
{
  "entities": ["Vietcombank", "ACB", "MWG", "FPT", "Lãi suất", "Bất động sản"],
  "extra_aliases": {}
}
```

**File này đã có sẵn trong `.gitignore` — không bao giờ bị commit lên GitHub.** Đây là quyết định cố ý: repo của dự án là public, nên danh sách "tôi đang quan tâm công ty/mã nào" là thông tin cá nhân, không nên công khai cho cả internet xem (xem TONG-QUAN-DU-AN.md mục 17 để hiểu đầy đủ lý do). Vì vậy tính năng này **chỉ gửi qua Telegram**, không có trang web nào hiển thị lại danh sách hay dữ liệu liên quan — không cấu hình file này thì tính năng tự động tắt, không ảnh hưởng gì tới phần còn lại của hệ thống.

> **Giới hạn quan trọng:** file này bị gitignore nên **không có trên GitHub Actions** — tính năng chỉ chạy khi bạn tự chạy app trên máy/VPS (`python main.py`), còn bản deploy qua Actions thì tự động bỏ qua nó. Muốn chạy trên Actions cần đưa nội dung file vào 1 GitHub Secret và sửa workflow (chưa làm — xem TONG-QUAN-DU-AN.md mục 17).

Mỗi chu kỳ có bài mới khớp với 1 mục trong `entities`, bạn sẽ nhận thêm 1 tin nhắn "📡 MY RADAR" riêng (tách biệt với digest chính) liệt kê tên + số bài/nguồn mới — không gửi lại nguyên title (đã có trong digest chính rồi).

## Chỉ tin kinh tế (bộ lọc tiêu đề)

Dù mọi nguồn đã trỏ vào chuyên mục kinh tế, vẫn có tin ngoài lề lọt vào (mưa lũ, xổ số Vietlott, kỷ luật Đảng, tìm người mất tích...). `core/relevance.py` loại những tin đó **ngay lúc crawl** (không vào DB, không gửi Telegram) theo quy tắc thận trọng: tiêu đề khớp **từ xã hội rõ ràng** **và không** có bất kỳ từ kinh tế nào. Tin lưng chừng được **giữ lại** — loại nhầm giấu mất tin kinh tế thật, còn giữ nhầm chỉ thừa 1 dòng. Mỗi chu kỳ log ghi tên + từ khớp của từng tin bị bỏ (`skipped N non-economic article(s)`), nên loại nhầm sẽ thấy ngay trong log. Bài cũ đã lưu mà nay bị coi là ngoài lề được ẩn khỏi trang web và phân tích nhưng dòng trong DB không bị xoá. Chỉnh `ECON_TERMS`/`SOCIAL_TERMS` trong file đó nếu thấy còn lọt tin xã hội. Lý do thiết kế và số liệu audit: TONG-QUAN-DU-AN.md mục 19.

## Bản tin & bằng chứng thông tin (roadmap V6, phase 1)

Mục nav **"Bản tin"** (`briefing.html`) là Financial Radar hôm nay gói trong 5 điểm cố định: sự kiện mới nổi, vấn đề tăng tốc nhanh nhất, được nhiều nguồn đưa nhất, đối tượng mới, tín hiệu từ nguồn chính thống. Mỗi điểm kèm bằng chứng (ai đưa tin, báo nào đầu tiên, từ lúc nào) — **không có AI tóm tắt**, vị trí nào không có gì phù hợp thì ghi rõ thay vì lấp chỗ. Mỗi thẻ issue cũng có 1 dòng **bằng chứng thông tin**: có nguồn chính thống nào đưa không, bao nhiêu nguồn truyền thông, báo nào đưa đầu tiên.

Đây là **cấu trúc bằng chứng, không phải điểm tin cậy** và **không phải dự báo thị trường**: nhãn "chú ý cao" chỉ nghĩa là có nguồn chính thống và truyền thông đang tăng tốc. `source_registry.json` có thêm trường `type` (hiện chỉ "Chính phủ" là `OFFICIAL`, còn lại `MEDIA`) — sửa ở đó nếu bạn đánh giá khác. Dữ liệu thô: `events.json`. Phase 1 chưa có crawler nguồn chính thống mới (cơ quan quản lý, công bố thông tin doanh nghiệp...), nên "chưa phát hiện nguồn chính thống" **không** có nghĩa là chưa có thông báo chính thức. Chi tiết và phần cố ý chưa làm: TONG-QUAN-DU-AN.md mục 20.

## Chạy thử (không cần Telegram token)

```bash
python main.py --dry-run
```

Dry run: crawl → parse → kiểm tra trùng với database hiện có → in ra terminal. **Không ghi database, không gửi Telegram.** Dùng lệnh này để kiểm tra 19 crawler còn hoạt động tốt không, bất cứ lúc nào.

## Chạy test tự động

```bash
pytest
```

393 test bao phủ: normalize title/URL (kể cả giải mã HTML entity lỗi của Thanh Niên/VietnamBiz), crawler parse RSS cho 18 nguồn (kèm test riêng cho 4 kiểu parse ngày phi chuẩn của Chính phủ/VTV/VietnamBiz/Tuổi Trẻ, và test riêng cho việc VietnamBiz tự sửa khai báo encoding sai `utf-16`→`utf-8` trước khi parse XML) và crawler scrape HTML cho 4 nguồn còn lại (lọc khối "nổi bật" không có giờ ở CafeBiz, chống 1 bài xuất hiện nhiều lần với giờ khác nhau ở Đầu tư Chứng khoán, báo lỗi khi selector không khớp gì thay vì âm thầm "0 bài mới", fallback fetch trang chi tiết khi listing thiếu giờ ở Đầu tư Chứng khoán/Diễn đàn Doanh nghiệp/Báo Đầu tư — cả khi thành công lẫn khi trang chi tiết lỗi/không parse được) (dùng fixture lấy từ dữ liệu thực tế lúc audit, mock qua thư viện `responses` — không cần mạng), dedup theo URL (không theo title), restart không mất/không gửi lại dữ liệu, format Telegram group-theo-nguồn + tách tin nóng + mục TOP TÍN HIỆU dẫn đầu tin nhắn theo SignalScore/vòng đời Signal (roadmap V2 §19) + chia nhỏ khi vượt giới hạn 4096 ký tự, retry khi gửi Telegram lỗi, cô lập lỗi từng nguồn không làm crash app, giữ đúng thứ tự nguồn theo cấu hình, baseline seeding lần chạy đầu **và** baseline riêng cho nguồn mới thêm vào một DB đã có dữ liệu, toàn bộ luồng `run_cycle` (dry-run / gửi thành công / lỗi 1 phần vẫn gửi tin nguồn OK / tất cả lỗi / Telegram lỗi thì không đánh dấu sent), phát hiện nguồn "chết âm thầm" (ngưỡng giờ, cooldown cảnh báo, tự gỡ cảnh báo khi hồi phục), backup database (tạo bản có timestamp + tự xoá bản cũ), và **lịch quét cố định** — kiểm tra thời điểm bắn thật của `CronTrigger` (APScheduler) khớp đúng mỗi `CRAWL_INTERVAL_MINUTES` phút, xuyên suốt nửa đêm không hở/chồng giờ nào; hiển thị ngày kèm giờ (`dd/mm HH:MM`) cho batch trải dài nhiều ngày, và trang web tĩnh (`web/generate_site.py`) — gom bài theo đúng ngày kể cả khi thiếu `published_at`, sắp mới nhất lên đầu trong từng nguồn, escape HTML tiêu đề (chống XSS từ tiêu đề bài crawl được), luôn dọn sạch `site/` cũ trước khi sinh lại thay vì cộng dồn file rác, cửa sổ 7-tab ngày (`_tab_window`) tự căn giữa quanh ngày đang xem kể cả 2 trường hợp biên (ít hơn 7 ngày dữ liệu, đang xem đúng ngày cũ nhất), nút "Quét ngay" — chỉ hiện khi đã cấu hình `NEWS_SCAN_WORKER_URL`, gọi đúng URL đó qua `fetch()`, và không bao giờ để lộ token trên trang, crawler FiLi (JSON API) — parse đúng định dạng ngày ASP.NET `/Date(...)/`, gửi đúng `channelid` dạng chuỗi nhiều ID (không phải ID chuyên mục đơn), và báo lỗi thay vì âm thầm trả rỗng khi response API đổi cấu trúc hoặc trả 0 bài, và panel "Top 5 Issues hôm nay" / Issue Intelligence V3 (`web/issues.py`) — phân biệt đúng entity/topic (kể cả loại các từ viết hoa chung chung như "HĐQT" khỏi bị nhận nhầm thành entity, tránh gộp nhầm 2 tin không liên quan), chỉ gộp thành issue khi có cặp (entity, topic) hoặc (topic, topic) chứ không bao giờ theo 1 entity/topic trơn, gộp đúng các cách diễn đạt khác nhau của cùng 1 issue, không gộp nhầm cùng entity khác topic hay cùng topic khác entity, chấm điểm SignalScore đúng trọng số với từng thành phần lộ ra được để dò lỗi, không để 1 nguồn duy nhất áp đảo hoàn toàn nhờ đăng nhiều, sinh "Vì sao hot" đúng từ số liệu thật, áp đúng ngưỡng ổn định xếp hạng cấu hình được, chỉ tính đúng phạm vi ngày hôm nay theo giờ Việt Nam, chỉ gắn vào đúng trang ngày mới nhất chứ không phải các trang lưu trữ ngày cũ, Velocity Engine + Media Consensus (`web/velocity.py`, roadmap V3 §22-24) — tính đúng tốc độ hiện tại/trước đó theo cửa sổ (mặc định 1 giờ, cấu hình được), phân loại đúng emerging/accelerating/peak/cooling ở từng trường hợp biên (2 khung trống, chỉ khung hiện tại có bài, nhanh/chậm hơn khung trước), và phân loại đúng nhãn đồng thuận theo số nguồn, "what changed" (`web.issues.issue_diff`, roadmap V3 §27) — báo đúng tăng trưởng hoặc trả `None` khi issue chưa tồn tại ở mốc so sánh, Signal Alert (`web.signals.should_alert`, roadmap V3 §26) — cần đủ cả 2 ngưỡng nguồn/điểm mới báo, cấu hình được, trang Radar (`render_radar_page`, roadmap V3 §21) — chỉ liệt kê đúng issue đang tăng tốc thật sự kèm đầy đủ Coverage Map/what-changed, hiện đúng trạng thái rỗng khi không có issue nào, và Watchlist cá nhân (`personal_watchlist.py`, roadmap V4) — file thiếu/hỏng/rỗng đều tắt tính năng an toàn, khớp đúng tên + alias tuỳ chỉnh, mã ngắn khớp phân biệt hoa/thường, đếm đúng số bài/nguồn mới mỗi chu kỳ, và luồng `run_cycle` gửi/không gửi tin Telegram đúng theo có/không cấu hình file.

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

- Module sinh trang: [web/generate_site.py](web/generate_site.py) — đọc toàn bộ `data/news.db` (`Database.get_all_articles`), gom theo **ngày** (theo `published_at`, hoặc theo `first_seen_at` khi hiếm hoi 1 bài vẫn không lấy được giờ — ví dụ trang chi tiết bị lỗi khi fetch) rồi theo **nguồn** (đúng thứ tự cấu hình như Telegram), xuất ra các file HTML tĩnh thuần (gần như không JS, không build tool) vào thư mục `site/`.
- Mỗi ngày có 1 file `site/YYYY-MM-DD.html`; `site/index.html` luôn là bản sao của ngày mới nhất.
- **Giao diện (v3 — khung ứng dụng SaaS responsive, viết lại 2026-09-24):** sidebar desktop (260px, thu gọn còn 68px) + header, chuyển thành drawer + bottom navigation trên mobile, theo 1 bản đặc tả handoff desktop/tablet/mobile riêng. Tone màu SaaS trung tính lạnh (nền xám xanh, accent xanh dương), viền mỏng 1px, bóng gần như vô hình, không gradient/glassmorphism/emoji, không còn tô màu riêng theo từng nguồn. Font chính **Inter** (đã kiểm tra có bộ subset tiếng Việt riêng qua chính response CSS2 API của Google Fonts trước khi dùng — rút kinh nghiệm từ lỗi "Archivo Black" thiếu dấu tiếng Việt ở bản trước), font phụ **IBM Plex Mono** cho số liệu/nhãn. Trang "Tổng quan" mở ra với 4 thẻ KPI rồi tới **"Tin tức"** — 1 dòng chảy tin hợp nhất từ toàn bộ 23 nguồn (mỗi dòng: nguồn · tiêu đề · nhãn issue/thương hiệu nếu có · giờ), có ô tìm kiếm, bộ lọc theo nguồn/issue/thương hiệu, và 2 chế độ sắp xếp "Mới nhất"/"Đang hot". Bảng Kanban cũ (mỗi nguồn 1 cột, đóng/mở bằng `<details>/<summary>` gốc, không cần JS) vẫn còn nguyên logic, lùi xuống thành mục phụ **"Theo nguồn"**; thanh điều hướng ngày (7 tab + dropdown "Ngày khác") lùi xuống mục **"Lưu trữ"** ở cuối trang. Hai bản thiết kế trước (v1 neo-brutalist/Kanban-first, v2.0 "editorial newsroom" kiểu Financial Times/Reuters/Bloomberg) đã được thay thế hoàn toàn. Xem chi tiết từng vùng giao diện ở [GIAO-DIEN.md](GIAO-DIEN.md).
- Xem thử ở máy (không cần mạng, không cần Telegram):
  ```bash
  python -m web.generate_site
  ```
  rồi mở `site/index.html` bằng trình duyệt bất kỳ.
- **Deploy:** [.github/workflows/news-crawl.yml](.github/workflows/news-crawl.yml) tự sinh lại `site/` và deploy lên **GitHub Pages** sau mỗi lần crawl, bằng action chính chủ của GitHub (`actions/upload-pages-artifact` + `actions/deploy-pages`) — không cần thêm nhánh riêng hay dịch vụ hosting nào khác.
- **Cần bật 1 lần duy nhất:** Settings → Pages → Build and deployment → Source → chọn **"GitHub Actions"** (không chọn "Deploy from a branch"). Sau đó URL trang sẽ hiện ở đúng mục Settings → Pages này (dạng `https://<username>.github.io/<repo>/`), và cũng hiện trong output của mỗi lần chạy workflow (bước "Deploy to GitHub Pages").

### Panel "Top Issues hôm nay" (Issue Intelligence V3)

Trên trang ngày **mới nhất** (không hiện ở các trang lưu trữ ngày cũ — xem lý do bên dưới), nằm trong lưới 12 cột của trang "Tổng quan" (8 cột) xếp hạng 5 "issue" (sự kiện cụ thể) được nhiều báo cùng đưa tin nhất **trong ngày hôm nay** (theo giờ Việt Nam), để nắm nhanh tình hình chung mà không cần đọc hết từng nguồn. Mỗi thẻ issue gọn (~180-220px khi thu gọn: hạng, tiêu đề, điểm SignalScore, số bài/nguồn, 2 dòng "Vì sao hot"), bấm vào để xem chi tiết đầy đủ (5 thành phần SignalScore, biểu đồ thanh ngang mức độ đưa tin theo từng nguồn, toàn bộ bài liên quan). Logic tính toán là bản viết lại từ đầu của panel "Sự kiện nổi bật" cũ, theo đặc tả `PROJECT_SPEC_V3_ISSUE_INTELLIGENCE.md` — xem GIAO-DIEN.md cho phần giao diện hiện tại.

- Module: [web/issues.py](web/issues.py) (thay cho `web/trending.py` cũ, đã xoá). **Không dùng AI/LLM/embedding nào** — toàn bộ vẫn là luật + từ khoá tự chọn tay, cùng tinh thần `HOT_KEYWORDS` trong `telegram.py`, cần tinh chỉnh dần theo dữ liệu thật, không phải giải pháp hoàn hảo.
- **Entity ≠ Topic ≠ Issue** — điểm khác biệt cốt lõi so với bản cũ (bản cũ gộp theo cụm từ trùng lặp bất kỳ, dễ gộp nhầm 2 tin không liên quan chỉ vì chung 1 từ):
  - **Entity**: tên riêng — 1 từ viết hoa toàn bộ dài ≥2 ký tự ("SCIC", "EIB", trừ các từ viết hoa chung chung trong `_GENERIC_ACRONYMS` như "HĐQT", "CEO", "IPO", "USD"...) hoặc 1 từ viết hoa chữ cái đầu dài ≥6 ký tự ("Eximbank", "Vietcombank").
  - **Topic**: nhãn chủ đề tài chính lấy từ danh sách `_TOPIC_KEYWORDS` tự chọn tay (lãi suất, tăng vốn, nhân sự lãnh đạo, nợ xấu, sáp nhập...).
  - **Issue**: 1 cặp cụ thể **(entity, topic)** hoặc **(topic, topic)** — không bao giờ chỉ 1 entity trơn hay 1 topic trơn. Vì vậy "Eximbank tăng lãi suất" và "Eximbank tuyển dụng" luôn là 2 issue khác nhau dù chung entity "Eximbank"; và 2 tin chỉ chung 1 từ khoá chung chung như "HĐQT" (một chức danh, không phải tên công ty) sẽ không bị gộp — lỗi gộp nhầm này từng xảy ra thật (tin Eximbank đề cử nhân sự HĐQT bị gộp với tin 1 cựu HLV bóng đá tham gia HĐQT 1 công ty cảng biển hoàn toàn không liên quan), phát hiện bằng cách chạy thử trên dữ liệu sản xuất thật ngày 2026-09-16, đã sửa bằng cách thêm `_GENERIC_ACRONYMS` — xem test `test_generic_role_acronym_does_not_falsely_merge_unrelated_companies` trong `tests/test_issues.py`.
- **Cửa sổ tính:** đúng 1 ngày dương lịch theo giờ Việt Nam (`Asia/Ho_Chi_Minh`), không phải cửa sổ trượt 48 giờ như bản cũ — vì panel tự nhận là "hôm nay" nên phải khớp đúng ngày dương lịch đó.
- **Ngưỡng ổn định xếp hạng** (chống 1 issue "rung" lên xuống top 5 chỉ vì 1-2 bài lẻ tẻ): phải đạt `article_count >= 3` **HOẶC** `unique_source_count >= 2` mới được xét — 2 số này cấu hình được qua tham số `top_issues(min_articles=..., min_sources=...)`.
- **SignalScore** (trước đây gọi là HotScore — công thức đổi trên nhánh `A_VMNs` theo Roadmap V1→V6 mục V2 §13, xem [TONG-QUAN-DU-AN.md](TONG-QUAN-DU-AN.md) mục 9) — mỗi thành phần chuẩn hoá riêng 0-100 theo giá trị cao nhất trong đợt tính hiện tại (và hiển thị được từng thành phần để dò lỗi, không chỉ điểm tổng), rồi nhân trọng số:
  - 30% Số nguồn đề cập (`source_score`)
  - 25% Tốc độ xuất hiện — số bài / số giờ kể từ lần đầu thấy issue đó (`velocity_score`)
  - 20% Mức độ mới/tăng tốc — so nhịp ra bài ở 1/4 thời gian gần nhất so với trước đó, cộng thêm số nguồn mới chỉ xuất hiện gần đây (`novelty_score`)
  - 15% Số bài đề cập (`volume_score`)
  - 10% Trọng số nguồn (`source_weight_score`) — trung bình trọng số các nguồn đưa tin, lấy từ [source_registry.json](source_registry.json) (mặc định mọi nguồn tier A/weight 1.0, không đổi thứ hạng gì cho tới khi có người chỉnh tay)
  - **Giới hạn thật đã biết:** trọng số cho đa dạng nguồn là 1 "lực đối trọng" chứ không phải "phủ quyết" — 1 nguồn đăng đủ nhiều tin gần giống nhau vẫn có thể vượt điểm 1 issue thật sự đa nguồn nếu chênh lệch số bài đủ lớn (xem docstring `_score_all()` trong `web/issues.py` và test tương ứng trong `tests/test_issues.py`).
  - Tên trường trong code vẫn giữ `hot_score` (không đổi tên hàng loạt chỉ vì đổi công thức — xem docstring `_score_all()`); giao diện vẫn hiện nhãn "HOT {điểm}".
- **Vòng đời Signal** ([web/signals.py](web/signals.py), roadmap V2 §15-16): mỗi issue được gắn nhãn EMERGING (mới xuất hiện) / ACCELERATING (velocity ≥1.15× chu kỳ trước) / PEAK (ổn định) / COOLING (velocity ≤0.85× chu kỳ trước), hiện thành badge nhỏ trên thẻ issue. Mỗi lần đổi trạng thái thật sự được ghi 1 dòng bất biến vào bảng `signal_events` để trả lời được "vì sao đang tăng tốc" chứ không chỉ có con số cuối cùng.
- **Velocity Engine + Media Consensus** ([web/velocity.py](web/velocity.py), roadmap V3 §22-24): riêng biệt hoàn toàn với `velocity`/`acceleration` dùng để chấm SignalScore ở trên (2 con số đó so "1/4 gần đây nhất" với "phần trước đó" trong đời issue, tốt cho xếp hạng — không trả lời được "đang nhanh hay chậm ngay lúc này" theo cách so sánh được giữa các issue). `calculate_velocity()` so 1 giờ gần nhất với 1 giờ ngay trước đó (cửa sổ cấu hình được), dùng lại đúng ngưỡng ±15% và 4 trạng thái của Vòng đời Signal thay vì bịa thêm bộ trạng thái mới. Hiện trên thẻ issue dưới dạng số thô ("Tốc độ 1h qua: X bài/giờ"), cố ý **không** làm thành badge màu thứ 2 — có thể lệch với badge vòng đời (đo 2 khung thời gian khác nhau), hiện badge thứ 2 dễ trông như 2 kết luận mâu thuẫn. Đi kèm nhãn "Đồng thuận" (1 nguồn / Nhiều nguồn / Bao phủ rộng theo số nguồn — không phải điểm tin cậy, roadmap cấm hiểu "nhiều nguồn đưa = chắc chắn đúng"). Không tính lại/lưu thêm bảng DB nào — tính thẳng từ timestamp bài viết có sẵn mỗi lần build, giống cách Top Issues vốn đã tính lại từ đầu mỗi chu kỳ.
- **"Vì sao hot" (`why_hot`):** mỗi issue có 2-4 dòng giải thích ngắn, sinh thẳng từ số liệu đã tính (số nguồn, số bài, có tăng tốc hay không, có nguồn mới hay không) — không bịa, không suy diễn.
- **Click để xem toàn bộ bài liên quan:** mỗi thẻ issue là 1 `<details>` — click vào để mở phần chi tiết: 5 thành phần SignalScore, giờ thấy đầu tiên/gần nhất, biểu đồ thanh ngang số bài theo từng nguồn (`_source_coverage_html`, không dùng pie chart), **Coverage Map** (roadmap V3 §25) — nguồn nào đăng trước, các nguồn sau trễ bao nhiêu phút (chỉ mô tả thứ tự, không kết luận nguồn nào đúng), dòng **"what changed"** (roadmap V3 §27) — so với chính issue đó 1 giờ trước ("+2 nguồn · +5 bài", hoặc "Mới xuất hiện trong giờ qua" nếu chưa tồn tại 1 giờ trước — tính lại bằng `top_issues()` với `now` sớm hơn, không lưu bảng snapshot riêng), và toàn bộ bài viết thuộc issue đó (không chỉ phần tóm tắt trên thẻ thu gọn). Trong "Tin tức", các dòng tin thuộc 1 issue có thêm nhãn nhỏ link thẳng tới đúng thẻ issue đó (`href="#issue-{id}"`), tự mở ra nhờ CSS `:target` — không cần JS.
- **Vì sao không hiện ở trang ngày cũ:** SignalScore tính theo "hiện tại" (thời điểm build site), gắn nó vào 1 trang lưu trữ của ngày trong quá khứ sẽ gây hiểu lầm là phản ánh đúng lúc đó. `build_site` chỉ tính 1 lần và chỉ gắn vào đúng trang ngày mới nhất.
- **Vị trí panel:** nằm trong lưới 12 cột của trang "Tổng quan" (8 cột), cạnh panel "Nguồn đăng nhiều nhất" (4 cột) — xem GIAO-DIEN.md.

### Radar (`radar.html`, roadmap V3 §21)

Trang riêng, mục nav "Radar" cạnh "Issues" trong sidebar. Chỉ liệt kê những issue trong Top Issues hôm nay đang **thực sự** ở trạng thái ACCELERATING (đọc lại `issue_history` — thường 0-1 issue, có thể rỗng, hiện dòng "Hiện không có vấn đề nào... đang tăng tốc" khi đó). Trả lời câu hỏi roadmap đặt ra cho V3: **"Vấn đề nào đang tăng tốc và cần chú ý ngay?"** — khác với panel "Top Issues hôm nay" ở Tổng quan vốn luôn liệt kê đủ Top 5 bất kể trạng thái đang là gì. Dùng lại đúng thẻ issue (`_issue_card_html`) của Tổng quan — cùng Coverage Map, "what changed", tốc độ 1h, đồng thuận — nên 2 nơi không bao giờ hiện thông tin lệch nhau cho cùng 1 issue.

### Signal Alert — Telegram (roadmap V3 §26)

Ngoài mục "📡 TOP TÍN HIỆU" dẫn đầu mọi digest (mục "Format Telegram" ở trên, luôn hiện Top 5 bất kể ngưỡng), hệ thống còn gửi 1 tin nhắn **riêng** khi 1 issue **vừa** chuyển sang ACCELERATING **và** đạt cả 2 ngưỡng: `source_count >= 3` (`SIGNAL_ALERT_MIN_SOURCES`, khớp `CRISIS_MIN_SOURCES`) và `hot_score >= 70` (`SIGNAL_ALERT_MIN_SCORE` — SignalScore chuẩn hoá theo đợt tính hiện tại, nên đây là "rõ ràng dẫn đầu đợt này", không phải ngưỡng tuyệt đối). **Chống spam:** không cần cooldown/bảng DB riêng — điều kiện "**vừa** chuyển trạng thái" (không phải "đang" ở trạng thái đó) tự nhiên chỉ đúng 1 lần cho tới khi issue hạ nhiệt rồi tăng tốc lại; 1 issue tăng tốc liên tục 10 chu kỳ chỉ tạo 1 alert.

### Lịch sử (`history.html`, roadmap V5)

Mục nav "Lịch sử" (nhóm Phân tích) trả lời "dòng tin đã diễn biến thế nào" thay vì chỉ "hôm nay". Tính hoàn toàn từ dữ liệu crawl job đã ghi sẵn, không thêm bảng DB nào:

- **So sánh theo kỳ:** hôm nay/hôm qua, tuần này/tuần trước, tháng này/tháng trước — bài viết, nguồn có bài, issue lọt Top 5, lượt nhắc thương hiệu, signal tăng tốc. Kỳ trước được cắt đúng bằng thời gian đã trôi qua của kỳ hiện tại (15h hôm nay so với 15h hôm qua). Nếu hệ thống mới bắt đầu thu thập sau đầu kỳ trước, trang ghi rõ và **không hiện % thay đổi** (tránh số kiểu +39000% do "chưa chạy" chứ không phải do tăng thật).
- **Lịch sử issue + tìm kiếm:** từng issue từng lọt Top 5 — lần đầu phát hiện, số ngày, tổng bài, ngày đỉnh, tốc độ đỉnh; ô tìm chạy ngay trên trình duyệt.
- **Dòng thời gian Signal:** các lần đổi trạng thái trong ngày theo thứ tự (Mới xuất hiện → Đang tăng tốc → Ổn định…).
- **Media Memory 30/90 ngày:** issue nhiều bài nhất / bền nhất, chủ đề tăng nhanh nhất, thương hiệu và nguồn được nhắc/đăng nhiều nhất.
- **Media Gap** trên thẻ issue: nguồn lớn nào "chưa phát hiện bài khớp" (không bao giờ khẳng định nguồn đó bỏ qua tin — so khớp theo tiêu đề có thể sót).
- **Xuất dữ liệu:** `history.json`, `signals.json`, `issues_history.csv` cạnh các file JSON sẵn có.

Giới hạn: lịch sử issue chỉ gồm issue từng lọt Top 5 (không phải mọi issue). Chi tiết và những gì cố ý chưa làm (tầng API riêng, trang Source Behavior): TONG-QUAN-DU-AN.md mục 18.

### Mục "Analytics" (nhóm tính năng dữ liệu A)

Module [web/analytics.py](web/analytics.py) — nằm ở **tab riêng `analytics.html`** (link `ANALYTICS` trên thanh nav của mọi trang), không nhúng vào trang chủ để trang chủ luôn nhẹ. Tính **thuần từ các bài đã thu thập** (không AI, không dữ liệu ngoài), dùng chung từ vựng Entity/Topic/Issue với `web/issues.py`. Các khối (ngoài 8 khối dưới đây còn có **Lịch sử Top Issues** và **Xu hướng 30 ngày**, lấy từ hạ tầng dữ liệu ở mục kế tiếp):

1. **Ai đưa tin trước** — với mỗi issue nhiều nguồn trong ngày, nguồn nào đăng sớm nhất và các nguồn khác trễ bao nhiêu phút; bảng xếp hạng 7 ngày (chỉ hiện nguồn tham gia ≥2 issue). Là ước lượng theo issue (cùng đối tượng + chủ đề trong ngày), không đảm bảo cùng 1 sự kiện.
2. **Khoảng trống đưa tin** — issue chỉ 1 nguồn đưa (≥3 bài), và issue ≥4 nguồn đưa nhưng thiếu các báo lớn (10 nguồn đăng nhiều nhất).
3. **Độ trễ thu thập** — `first_seen_at − published_at` theo nguồn (trung vị, P90), bỏ độ trễ >6 giờ (backfill).
4. **Nhịp đăng bài theo giờ** — histogram 24 giờ + giờ đăng nhiều nhất/tỷ lệ đăng đêm từng nguồn.
5. **Khối lượng tin theo thời gian** — số bài/ngày 14 ngày, và heatmap theo chủ đề.
6. **Tin đăng lặp** — tiêu đề gần giống (≥80% từ, **cùng các con số**) cùng 1 báo trong 24 giờ; điều kiện "cùng con số" để bản tin mẫu hằng ngày ("… phiên 15/09" vs "… 16/09") không bị tính là đăng lặp.
7. **Đồng xuất hiện** — cặp đối tượng+chủ đề và đối tượng+đối tượng hay đi cùng nhau.
8. **Hồ sơ chủ đề từng nguồn** — heatmap tỷ lệ bài theo chủ đề của từng nguồn.

Mọi thống kê theo nguồn đều bị ẩn khi có <5 mẫu để tránh số liệu ngẫu nhiên.

### Hạ tầng dữ liệu (nhóm D)

- **Bảng `daily_stats`** (`day, kind, name, articles`; kind = `source`/`topic`): số bài theo ngày/nguồn/chủ đề, tổng hợp sẵn. Thuần dẫn xuất từ `news` nên luôn dựng lại được. Lần đầu (bảng trống) backfill toàn bộ lịch sử, sau đó mỗi chu kỳ chỉ tính lại 3 ngày gần nhất.
- **Bảng `issue_history`** (`day, issue_id, title, rank, hot_score, ...`): mỗi ngày mỗi issue từng lọt Top 5 có 1 dòng (giá trị của chu kỳ mới nhất). Issue vốn được tính lại từ đầu mỗi lần và biến mất khi qua ngày — bảng này cho phép hiện "issue hot N ngày liên tiếp".
- **Vì sao ghi trong `run_cycle` (`scheduler.snapshot_data`) chứ không phải lúc build site:** workflow đẩy `news.db` lên nhánh `db-state` *trước* bước build site; dữ liệu ghi lúc build sẽ không bao giờ được lưu. `snapshot_data` là bước phụ (best-effort), lỗi chỉ ghi log, không ảnh hưởng crawl/Telegram. Bảng mới tạo bằng `CREATE TABLE IF NOT EXISTS` nên DB cũ trên `db-state` tự nâng cấp.
- **Xuất dữ liệu** ([web/exports.py](web/exports.py)), ghi cạnh các trang HTML mỗi lần build: `issues.json` (Top Issues + 5 thành phần SignalScore), `stats.json` (`daily_stats` + `issue_history`), `feed.xml` (RSS 100 bài mới nhất, URL kênh lấy từ `NEWS_SITE_URL`).
- **Lưu trữ theo tháng** ([archive.py](archive.py)): `python main.py --archive-old` xuất các bài cũ hơn `ARCHIVE_KEEP_DAYS` (mặc định 90) ra `data/archive/news-YYYY-MM.jsonl.gz`. **Mặc định chỉ xuất, không xoá**; thêm `--delete-archived` mới xoá khỏi DB (khi đó các ngày đó biến mất khỏi trang lưu trữ, và nguồn có feed dài như VietnamNet — ~2 tháng — có thể nạp lại URL đã xoá nếu `ARCHIVE_KEEP_DAYS` quá nhỏ). **Cố ý không gắn vào CI** vì file archive không nằm trên nhánh `db-state`, chạy ở đó sẽ mất.

### Theo dõi thương hiệu & cảnh báo khủng hoảng (tab `brands.html`)

Dành cho phòng truyền thông/PR ngành ngân hàng - tài chính. Toàn bộ là luật + từ khoá (không AI), mọi nhãn đều kèm từ khoá đã kích hoạt để người dùng kiểm chứng. Module: [web/brands.py](web/brands.py) (nhận diện thương hiệu), [web/sentiment.py](web/sentiment.py) (sắc thái), [web/brandwatch.py](web/brandwatch.py) (share of voice + cảnh báo).

**Từ điển & watchlist**
- Từ điển sẵn có ~28 ngân hàng (tên + mã + tên cũ, vd "Vietcombank / VCB / Ngân hàng Ngoại thương") và Ngân hàng Nhà nước. **Không bundle tên người** (chủ tịch, người phát ngôn) vì hay đổi và dễ sai — thêm theo từng tổ chức qua `watchlist.json`.
- Mã ngắn viết hoa (≤4 ký tự: `MB`, `ACB`, `VIB`...) khớp **phân biệt hoa/thường** và theo ranh giới từ, để "20 mb" hay "5MB" không bị nhận nhầm.
- [watchlist.json](watchlist.json): `own` (thương hiệu của mình), `competitors`, `extra_aliases`, `extra_brands`, `extra_negative_keywords`. Tên lạ trong `own`/`competitors` tự thành thương hiệu tuỳ chỉnh. Để trống = theo dõi toàn bộ từ điển. ⚠ File này nằm trong repo **public**: đừng đưa thông tin nội bộ nhạy cảm vào đó.

**Share of voice** — tỷ trọng số tin nhắc tới mỗi thương hiệu trong tổng tin của các thương hiệu được theo dõi, 7 và 30 ngày, kèm số nguồn, phân bố tích cực/tiêu cực/trung tính, % tiêu cực và so kỳ trước. Một tiêu đề nhắc nhiều thương hiệu tính cho từng thương hiệu (cố ý thiên về báo động thừa hơn bỏ sót).

**Sắc thái** — 3 mức từ khoá: nghiêm trọng (khởi tố, vỡ nợ, rút tiền ồ ạt...), mạnh (tin đồn, bị phạt, rò rỉ...), nhẹ (nợ xấu, cảnh báo, rủi ro...) và các từ tích cực. Hai quy tắc giảm sai lầm, đều tìm ra từ dữ liệu thật: (1) tiêu đề **bác bỏ/đính chính** ("bác bỏ tin đồn") là phản hồi của ngân hàng → trung tính; (2) tiêu đề mô tả **nỗ lực bảo vệ** ("mở rộng tính năng cảnh báo lừa đảo") không bị coi là tin xấu. Chỉ mức mạnh/nghiêm trọng mới được tính vào cảnh báo; mức nhẹ chỉ tô màu thống kê. Đây là **ước lượng từ tiêu đề**, không phải kết luận.

**Cảnh báo khủng hoảng** (`scheduler.check_crisis`, chạy mỗi chu kỳ): ≥3 báo khác nhau đăng tin tiêu cực mức mạnh về cùng 1 thương hiệu trong 60 phút → "leo thang"; ≥2 báo với từ khoá nghiêm trọng → "khẩn". Gửi Telegram kèm từ khoá và từng tiêu đề; mỗi thương hiệu 1 cảnh báo/3 giờ (bảng `crisis_alerts`), riêng cảnh báo "khẩn" được vượt cooldown của "leo thang". Gửi lỗi thì không ghi nhận → chu kỳ sau thử lại. Cấu hình: `CRISIS_MIN_SOURCES`, `CRISIS_WINDOW_MINUTES`, `CRISIS_COOLDOWN_HOURS`. Bước phụ (best-effort): lỗi chỉ ghi log, không ảnh hưởng crawl.

**Trên web:** tab `BRANDS` (cảnh báo hiện hành, 2 bảng share of voice, số tin theo 14 ngày, tin tiêu cực gần đây), mỗi dòng "Tin tức" có chấm màu sắc thái + nhãn thương hiệu, bộ lọc theo thương hiệu, và xuất `brands.json`.

### Nút "Quét ngay" trên web

Trang web có 1 nút để tự kích hoạt crawl ngay từ trình duyệt, không cần vào tab Actions bấm tay.

**Vì sao không làm đơn giản bằng cách nhúng thẳng token vào trang:** kích hoạt crawl cần gọi GitHub API bằng 1 token có quyền ghi. Trang này là GitHub Pages build từ repo **public** — bất kỳ ai cũng xem được mã nguồn trang (View Source), nên nhúng token thẳng vào HTML/JS nghĩa là **công khai token đó cho cả Internet**, ai cũng lấy được và lạm dụng. Vì vậy nút này gọi tới 1 **Cloudflare Worker** trung gian (miễn phí) — Worker giữ token thật ở phía server (Cloudflare), trang web chỉ biết URL công khai của Worker, không bao giờ thấy token.

Sơ đồ: `Nút trên web → gọi Worker (Cloudflare) → Worker gọi GitHub API bằng token riêng → GitHub chạy workflow_dispatch`.

**Cách deploy Worker** (dùng dashboard Cloudflare, không cần cài gì ở máy):

1. Tạo tài khoản [Cloudflare](https://dash.cloudflare.com) (miễn phí) nếu chưa có.
2. Vào **Workers & Pages → Create → Create Worker**, đặt tên bất kỳ (ví dụ `news-monitor-scan-trigger`) → Deploy để tạo worker rỗng.
3. Bấm **Edit code**, xoá hết code mẫu, dán toàn bộ nội dung [web/cloudflare-worker/worker.js](web/cloudflare-worker/worker.js) vào → **Save and Deploy**.
4. Vào **Settings → Variables** của Worker, thêm các **biến thường**:
   - `GITHUB_OWNER` = `ninhphu321`
   - `GITHUB_REPO` = `vietnam-news-monitor`
   - `GITHUB_WORKFLOW` = `news-crawl.yml`
   - `GITHUB_BRANCH` = `main`
   - `ALLOWED_ORIGIN` = `https://ninhphu321.github.io` (đúng domain trang GitHub Pages của bạn)
   - `COOLDOWN_SECONDS` = `300` (không bắt buộc, mặc định 300 nếu bỏ trống)
5. Thêm 1 **biến bí mật** (chọn "Encrypt"): `GITHUB_TOKEN` — giá trị là 1 **fine-grained personal access token** tạo tại GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens, giới hạn **chỉ repo `vietnam-news-monitor`**, quyền **Actions: Read and write** (không cấp quyền nào khác). Dán token vào đây, **không paste vào bất kỳ đâu khác** (không vào file trong repo, không gửi cho ai kể cả Claude).
6. *(Khuyến nghị, chống spam)* Tạo 1 **KV namespace** (Workers & Pages → KV → Create), đặt tên tuỳ ý, rồi vào lại Worker → Settings → Variables → **KV Namespace Bindings** → bind namespace đó với tên biến `SCAN_COOLDOWN`. Có bước này thì nút bị giới hạn tối đa 1 lần kích hoạt mỗi `COOLDOWN_SECONDS` giây cho **tất cả người xem** — tránh bị bấm dồn dập tốn phút chạy Actions. Bỏ qua bước này vẫn chạy được, chỉ là không có giới hạn.
7. Copy URL Worker (dạng `https://news-monitor-scan-trigger.<subdomain>.workers.dev`, hiện ngay đầu trang Worker).
8. Thêm URL đó vào repo dưới dạng **GitHub Actions variable** (không phải secret, vì URL này không nhạy cảm): Settings → Secrets and variables → Actions → tab **Variables** → **New repository variable** → tên `NEWS_SCAN_WORKER_URL`, giá trị là URL vừa copy.
9. Chạy lại workflow 1 lần (Run workflow) để `site/` được sinh lại có nút — hoặc chờ lần cron kế tiếp.

Nếu không muốn setup Worker, cứ để `NEWS_SCAN_WORKER_URL` trống — trang vẫn hoạt động bình thường, chỉ là không có nút "Quét ngay" (vào tab Actions bấm "Run workflow" như trước).

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
3. Nếu không có RSS: subclass `BaseCrawler` trực tiếp (đã có sẵn `_fetch()` dùng chung, không cần viết lại phần HTTP/retry), tự viết `crawl()` parse HTML bằng `beautifulsoup4` (đã có trong `requirements.txt`), trả về `List[NewsItem]` giống hệt interface RSS — xem `crawlers/cafebiz.py` làm mẫu, đặc biệt chú ý: kiểm tra bài có bị lặp lại nhiều lần trên cùng 1 trang không (widget "liên quan" hay lấy lại link ảnh + link tiêu đề cùng class), và nếu trang danh sách không hiện giờ đăng ở đâu cả: trước tiên thử fetch thêm trang chi tiết từng bài xem có giờ ở đó không (`crawlers/baodautu.py`, `crawlers/tinnhanhchungkhoan.py` — chấp nhận đổi N+1 request lấy giờ thật), chỉ để `published_at=None` (đừng đoán giờ) khi cả trang chi tiết cũng không có.
4. Thêm crawler mới vào `CRAWLER_CLASSES` trong `crawlers/__init__.py` — thứ tự trong list quyết định thứ tự hiển thị trên Telegram.
5. Thêm 1 fixture RSS/HTML nhỏ (2-3 bài thật) vào `tests/fixtures/`, thêm dòng vào `CRAWLERS_AND_FIXTURES` trong `tests/test_crawlers.py` (RSS) hoặc viết test riêng trong `tests/test_html_crawlers.py` (HTML).
6. Chạy `pytest` rồi `python main.py --dry-run` để xác nhận trước khi chạy production.
7. Không cần migration DB hay đổi schema — nguồn mới tự động được baseline riêng ở lần chạy `--run-once`/scheduler đầu tiên sau khi thêm (xem mục "Chạy lần đầu / chạy thủ công" ở trên).

## Về việc test crawler bằng mạng thật

Toàn bộ crawler đã được audit và test bằng dữ liệu **thực tế** lấy trực tiếp từ 18 site vào ngày 14-15/09/2026 (xem bảng ở trên). Test tự động (`pytest`) dùng fixture dựng lại từ dữ liệu thật đó, chạy offline, đáng tin cậy và lặp lại được.

Ngoài ra, toàn bộ luồng end-to-end (crawl → dedup → Telegram → sent_at, bao gồm baseline seeding, baseline riêng cho nguồn mới, phát hiện bài mới thật sự, không gửi trùng lần 2, restart không mất dữ liệu, và báo lỗi khi 1 nguồn fail) đã được xác minh bằng cách chạy `main.py --run-once` thật với Telegram Bot API thật (không mock) trong lúc phát triển.

**Việc bạn cần tự làm định kỳ:** chạy `python main.py --dry-run` để xác nhận 19 crawler vẫn lấy đúng dữ liệu tại thời điểm bạn dùng — RSS/HTML thường ổn định nhưng không có gì đảm bảo 100% một site sẽ không đổi cấu trúc trong tương lai (xem case Tiền Phong ở trên: 1 category ID sai vẫn trả HTTP 200 bình thường; 4 crawler HTML tự báo lỗi nếu selector không còn khớp gì).

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
│   ├── baodautu.py          # V3 (scrape HTML, fetch thêm trang chi tiết để lấy giờ)
│   └── fili.py              # HTML scrape (trước 10/2026: JSON API ẩn phía sau SPA Angular)
├── data/news.db         # SQLite (tự tạo khi chạy, không commit)
├── logs/app.log         # Log (tự tạo khi chạy, không commit)
└── tests/
```

### Luồng xử lý mỗi chu kỳ (`scheduler.run_cycle`)

1. Crawl cả 23 nguồn, lỗi 1 nguồn không làm hỏng nguồn khác (`crawl_all`).
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
