# 📰 Vietnam News Monitor

Hệ thống tự động theo dõi tin tức kinh tế/tài chính từ **23 đầu báo Việt Nam**, gửi tin mới về Telegram theo thời gian thực, đồng thời có 1 trang web tổng hợp lưu lại toàn bộ lịch sử để tra cứu. Chạy **hoàn toàn tự động, 24/7, miễn phí** — không cần VPS, không cần server riêng.

---

## Tính năng chính

### 🔍 Thu thập tin từ 23 nguồn báo
Quét đồng thời 23 chuyên mục kinh tế/tài chính, mỗi nguồn có cách lấy dữ liệu riêng tuỳ theo hạ tầng thực tế của từng trang:

| Cách lấy dữ liệu | Số nguồn | Ví dụ |
|---|---|---|
| RSS feed chuẩn | 18 | VnExpress, CafeF, Tuổi Trẻ, Vietstock, VietnamNet, Người Quan Sát... |
| Scrape HTML (không có RSS) | 4 | CafeBiz, Đầu tư Chứng khoán, Diễn đàn Doanh nghiệp, Báo Đầu tư |
| JSON API ẩn sau ứng dụng web (SPA) | 1 | FiLi |

Mỗi nguồn được audit thực tế trên dữ liệu sống (không đoán cấu trúc), tự phát hiện khi selector/feed thay đổi và báo lỗi thay vì âm thầm im lặng.

### ⏱️ Quét tự động mỗi 20 phút, cả ngày lẫn đêm
- **GitHub Actions** chạy `workflow_dispatch` được kích hoạt bởi **cron-job.org** đúng lịch mỗi 20 phút (đáng tin cậy hơn lịch `schedule` gốc của GitHub, vốn có thể trễ hàng giờ với tần suất quét dày).
- Chống trùng lặp bằng URL — bài đã gửi rồi sẽ không gửi lại, kể cả khi nguồn trả về cùng 1 bài nhiều lần.
- Lần chạy đầu tiên tự động "làm nền" (baseline) toàn bộ bài đang có, không spam hàng loạt tin cũ ngay khi mới thêm nguồn.

### 📬 Gửi tin qua Telegram
- Gom bài theo từng nguồn, mỗi nguồn 1 icon riêng để phân biệt nhanh.
- **"📡 TOP TÍN HIỆU" dẫn đầu tin nhắn** (roadmap V2) — Top 5 issue đang hot nhất hôm nay theo SignalScore, kèm trạng thái (★ Mới xuất hiện / ↑ Đang tăng tốc / ● Ổn định / ↓ Đang hạ nhiệt), để biết ngay chuyện gì đáng chú ý trước khi đọc từng title.
- **Tự động tách "🚨 TIN NÓNG"** lên đầu tin nhắn — nhận diện bằng bộ từ khoá (khủng hoảng, sụp đổ, tăng vọt, giảm sốc, phá sản...) để bài quan trọng không bị chìm giữa hàng chục tin thường.
- **"🎯 Tín hiệu đang tăng tốc"** (tin nhắn riêng, roadmap V3) — chỉ gửi khi 1 issue vừa thực sự tăng tốc mạnh (đủ nguồn + đủ điểm), không phải mỗi chu kỳ, để không bị dội thông báo dù có tin dài ngày.
- **"📡 MY RADAR" — Watchlist cá nhân riêng tư** (tuỳ chọn, roadmap V4) — tự thêm công ty/mã/chủ đề bạn cá nhân quan tâm vào 1 file **không bao giờ công khai** (không nằm trong repo GitHub), chỉ bạn tự cấu hình trên máy/server của mình. Có tin mới khớp thì nhận thêm 1 tin Telegram riêng, không có trang web nào hiển thị lại.
- Cảnh báo khi 1 nguồn "chết âm thầm" (vẫn phản hồi HTTP 200 nhưng ngừng cập nhật nội dung thật).
- Có nút "🔄 Quét ngay" trên web để tự kích hoạt quét thủ công bất cứ lúc nào.

### 🌐 Trang web tổng hợp (GitHub Pages)
Trang tĩnh tự sinh lại sau mỗi lần quét, lưu toàn bộ lịch sử theo ngày:

- **Bảng Kanban nằm ngang** — mỗi nguồn 1 cột, cuộn ngang toàn hàng, mỗi cột tự cuộn dọc riêng khi quá dài. Bấm vào tiêu đề cột để đóng/mở.
- **Thanh điều hướng 7 ngày** trải đều hết chiều ngang, tự căn giữa quanh ngày đang xem; xem ngày cũ hơn qua dropdown "Ngày khác".
- **🔥 Top 5 Issues hôm nay** (tab gấp/mở, nằm dưới bảng Kanban) — xếp hạng 5 "issue" (1 cặp cụ thể tên riêng + chủ đề, ví dụ "Eximbank · Tăng vốn" — không gộp bừa theo 1 từ trùng lặp bất kỳ nên tránh gộp nhầm 2 tin không liên quan) đang được nhiều báo cùng đưa tin nhất **trong ngày hôm nay**, tính theo **SignalScore** (roadmap V2, xem TONG-QUAN-DU-AN.md):
  - 30% đa dạng nguồn
  - 25% tốc độ xuất hiện
  - 20% mức độ mới/tăng tốc
  - 15% số bài đề cập
  - 10% trọng số nguồn (`source_registry.json`)

  Mỗi issue kèm vài dòng "Vì sao hot" giải thích ngắn gọn, nhãn vòng đời (Mới xuất hiện/Đang tăng tốc/Ổn định/Đang hạ nhiệt), tốc độ 1 giờ qua + mức độ đồng thuận nguồn, Coverage Map (nguồn nào đưa trước) + so sánh với 1 giờ trước (roadmap V3), và bấm vào để xem toàn bộ bài viết liên quan. Cập nhật lại **mỗi lần quét**.
- **📡 Radar** (mục nav riêng, roadmap V3) — chỉ liệt kê những issue **đang thực sự tăng tốc** ngay lúc này (thường 0-1 issue), trả lời đúng câu hỏi "vấn đề nào cần chú ý ngay?" thay vì phải tự lọc trong cả Top 5.
- **🕘 Lịch sử** (mục nav riêng, roadmap V5) — so sánh hôm nay/tuần/tháng với kỳ trước, tìm lại 1 issue từng nổi (phát hiện lúc nào, nổi mấy ngày, đỉnh khi nào), xem 1 issue đã đổi trạng thái ra sao theo giờ, và "trí nhớ" báo chí 30/90 ngày (issue/chủ đề/thương hiệu/nguồn nổi bật). Có thể tải dữ liệu thô dạng JSON/CSV.
- Giao diện phong cách biên tập báo chí (viền đen, đổ bóng cứng, không dùng gradient màu mè), hỗ trợ sẵn dark mode theo hệ thống.

### 🤖 Hạ tầng miễn phí, tự vận hành
```
cron-job.org (lịch đúng giờ)
        │  gọi mỗi 20 phút
        ▼
Cloudflare Worker (giữ token an toàn)
        │  kích hoạt workflow_dispatch
        ▼
GitHub Actions
        │  crawl → gửi Telegram → build web
        ▼
GitHub Pages (trang web) + nhánh db-state (lưu database)
```

- Database SQLite được lưu trên 1 nhánh Git riêng (`db-state`), tách biệt hoàn toàn khỏi code (`main`) — mỗi lần chạy chỉ ghi đè 1 commit duy nhất, không phình dung lượng repo.
- Token GitHub (dùng để kích hoạt crawl) chỉ tồn tại phía **Cloudflare Worker**, không bao giờ xuất hiện trong code hay trang web công khai.
- Toàn bộ chi phí vận hành: **0 đồng** (GitHub Actions/Pages, Cloudflare Worker, cron-job.org đều dùng gói miễn phí).

---

## Công nghệ sử dụng

- **Python 3.11** — `requests`, `feedparser`, `BeautifulSoup4`, `APScheduler`, `sqlite3`
- **GitHub Actions** — lập lịch & chạy crawler
- **GitHub Pages** — hosting trang web tĩnh
- **Cloudflare Workers** — proxy an toàn cho nút "Quét ngay"
- **cron-job.org** — kích hoạt đúng giờ, thay thế lịch cron thiếu ổn định của GitHub
- **Telegram Bot API** — kênh nhận tin chính

## Chất lượng & kiểm thử

326 test tự động (`pytest`), chạy offline bằng dữ liệu fixture lấy từ audit thực tế — bao phủ toàn bộ crawler, logic chống trùng, format Telegram, sinh trang web, và thuật toán phát hiện issue.

---

📖 Xem chi tiết kỹ thuật đầy đủ (audit từng nguồn, kiến trúc, hướng dẫn cài đặt/deploy) tại [README.md](README.md).
