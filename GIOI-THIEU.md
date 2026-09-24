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
- **Tự động tách "🚨 TIN NÓNG"** lên đầu tin nhắn — nhận diện bằng bộ từ khoá (khủng hoảng, sụp đổ, tăng vọt, giảm sốc, phá sản...) để bài quan trọng không bị chìm giữa hàng chục tin thường.
- Cảnh báo khi 1 nguồn "chết âm thầm" (vẫn phản hồi HTTP 200 nhưng ngừng cập nhật nội dung thật).
- Có nút "🔄 Quét ngay" trên web để tự kích hoạt quét thủ công bất cứ lúc nào.

### 🌐 Trang web tổng hợp (GitHub Pages)
Trang tĩnh tự sinh lại sau mỗi lần quét, lưu toàn bộ lịch sử theo ngày:

- **Bảng Kanban nằm ngang** — mỗi nguồn 1 cột, cuộn ngang toàn hàng, mỗi cột tự cuộn dọc riêng khi quá dài. Bấm vào tiêu đề cột để đóng/mở.
- **Thanh điều hướng 7 ngày** trải đều hết chiều ngang, tự căn giữa quanh ngày đang xem; xem ngày cũ hơn qua dropdown "Ngày khác".
- **🔥 Top 5 Issues hôm nay** (tab gấp/mở, nằm dưới bảng Kanban) — xếp hạng 5 "issue" (1 cặp cụ thể tên riêng + chủ đề, ví dụ "Eximbank · Tăng vốn" — không gộp bừa theo 1 từ trùng lặp bất kỳ nên tránh gộp nhầm 2 tin không liên quan) đang được nhiều báo cùng đưa tin nhất **trong ngày hôm nay**, tính theo **HotScore**:
  - 40% số bài đề cập
  - 25% số nguồn đề cập
  - 20% tốc độ xuất hiện
  - 15% mức độ mới/tăng tốc

  Mỗi issue kèm vài dòng "Vì sao hot" giải thích ngắn gọn, và bấm vào để xem toàn bộ bài viết liên quan. Cập nhật lại **mỗi lần quét**.
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

201 test tự động (`pytest`), chạy offline bằng dữ liệu fixture lấy từ audit thực tế — bao phủ toàn bộ crawler, logic chống trùng, format Telegram, sinh trang web, và thuật toán phát hiện issue.

---

📖 Xem chi tiết kỹ thuật đầy đủ (audit từng nguồn, kiến trúc, hướng dẫn cài đặt/deploy) tại [README.md](README.md).
