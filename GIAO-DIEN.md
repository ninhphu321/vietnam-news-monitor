# Giao diện trang web Vietnam News Monitor

> Bản v3 (2026-09-24) — viết lại giao diện thành khung ứng dụng "SaaS dashboard" responsive (sidebar desktop, drawer mobile, bottom nav) theo 1 bản đặc tả handoff riêng cho desktop/tablet/mobile, thay cho bản v2.0 "editorial newsroom" (Financial Times/Reuters/Bloomberg) trước đó, vốn cũng đã thay bản v1 neo-brutalist/Kanban-first ban đầu.

Tài liệu này mô tả cấu trúc giao diện của trang tĩnh sinh ra bởi [web/generate_site.py](web/generate_site.py) (lắp ráp nội dung) + [web/theme.py](web/theme.py) (khung ứng dụng: CSS, icon, `render_shell`) — không phải hướng dẫn dùng, mà là bản đồ các thành phần trên trang. Xem trực tiếp bằng cách chạy:

```bash
python -m web.generate_site
```

rồi mở `site/index.html`.

## Nguyên tắc thiết kế

- **SaaS dashboard + sản phẩm thông tin dạng editorial** — ưu tiên: dễ đọc, phân cấp thông tin rõ, điều hướng nhanh, responsive đúng nghĩa (không phải desktop thu nhỏ), nhất quán.
- **Không** dùng: gradient mạnh, glassmorphism, neon, bóng đổ nặng, quá nhiều animation, quá nhiều card lồng nhau, emoji làm icon chính.
- **Không tô màu riêng theo từng nguồn báo** — chỉ 1 màu accent duy nhất, dùng tiết chế.
- **Một bộ icon SVG thống nhất** (`<symbol>` khai báo 1 lần trong `web/theme.py`, dùng lại bằng `<use>`) — không trộn emoji với icon.

## 3 trang dùng chung 1 khung

`render_shell()` trong `web/theme.py` dựng khung cho cả 3 trang — **Tổng quan** (`index.html`/theo ngày), **Brands** (`brands.html`), **Analytics** (`analytics.html`) — mỗi trang chỉ khác phần nội dung chính (`body`) truyền vào.

```
┌───────────────────────────────────────────────────────────────┐
│ SIDEBAR │ TOPBAR (breadcrumb · trạng thái LIVE + giờ)          │
│ (260px) ├───────────────────────────────────────────────────────┤
│ Logo    │                                                       │
│ Chính   │  MAIN                                                 │
│  Tổng   │  ┌─ Page header: tiêu đề + mô tả + nút "Quét ngay" ─┐ │
│  quan   │  ├─ 4 thẻ KPI ─────────────────────────────────────┤ │
│  Issues │  ├─ Lưới 12 cột: nội dung chính (8) + panel phụ (4) ┤ │
│  Tin tức│  ├─ Bảng "Tin tức": bộ lọc → bảng/thẻ → phân trang  ┤ │
│ Phân    │  ├─ "Theo nguồn" (Kanban)                            │ │
│  tích   │  └─ "Lưu trữ" (tab ngày)                             │ │
│  Brands │                                                       │
│  Analyt.│                                                       │
│ Quản lý │                                                       │
│ Dữ liệu │                                                       │
│ Thu gọn │                                                       │
└───────────────────────────────────────────────────────────────┘
```

Sidebar chia 4 nhóm: **Chính** (Tổng quan, Issues, Tin tức — neo tới các section trong trang chủ), **Phân tích** (Brands, Analytics — chỉ hiện khi có dữ liệu để tính, tức là còn bài trong DB), **Quản lý** (Theo nguồn, Lưu trữ), **Dữ liệu** (RSS feed, Dữ liệu JSON — trỏ thẳng tới `feed.xml`/`issues.json`).

## Responsive theo 3 mốc

| | Desktop ≥1024px | Tablet 768–1023px | Mobile <768px |
|---|---|---|---|
| Sidebar | 260px, nút "Thu gọn" còn 68px (nhớ lựa chọn qua `localStorage`) | Ép cố định 68px, không có nút thu gọn | Ẩn hẳn, thành **drawer** trượt từ trái khi bấm hamburger |
| Header | 64px | 60px | 56px, có nút hamburger bên trái |
| Điều hướng phụ | — | — | **Bottom navigation** 5 mục cố định đáy màn hình |
| Thẻ KPI | 4 cột | 2 cột | 1 cột (dạng hàng ngang gọn: nhãn+phụ chú bên trái, số bên phải) |
| Lưới 12 cột | 8+4 | gộp về 12 (xếp chồng) | gộp về 12 (xếp chồng) |
| Bảng "Tin tức" | Bảng 4 cột (Nguồn/Tiêu đề/Issue/Giờ), sticky header | Bảng rút gọn 3 cột (bỏ cột Issue) | Mỗi tin 1 **thẻ** (nguồn, tiêu đề, giờ, nhãn issue xếp dọc) |
| Bộ lọc | Nằm ngay trên bảng tin | Nằm ngay trên bảng tin | Nút "Bộ lọc" mở **bottom sheet** (chọn nguồn/issue/thương hiệu/sắp xếp, có "Đặt lại"/"Áp dụng") |
| Cột nguồn (Kanban) | Cuộn ngang | Xếp dọc | Xếp dọc |

**Drawer trên mobile:** có lớp phủ nền mờ (backdrop), đóng bằng bấm ra ngoài, phím ESC, hoặc chọn xong 1 mục điều hướng; khoá vòng lặp Tab bên trong khi mở (focus trap) để không tab ra ngoài drawer. Mọi vùng bấm trên mobile (nút, mục bottom-nav, ô chọn) đều ≥44px theo chuẩn cỡ ngón tay.

## Nội dung trang Tổng quan (từ trên xuống)

1. **Banner "xem tin mới nhất"** — chỉ hiện trên trang lưu trữ (không phải ngày mới nhất), trỏ về `index.html`.
2. **Page header** — tiêu đề "Tổng quan" + mô tả ngắn + nút "Quét ngay" (kích hoạt crawl qua Cloudflare Worker, xem README mục V4).
3. **4 thẻ KPI** — bài viết hôm nay (kèm % so với hôm qua cùng giờ), số nguồn có bài / tổng số nguồn theo dõi, số issue nổi bật, giờ cập nhật gần nhất.
4. **Lưới 12 cột** — panel "Top Issues hôm nay" (8 cột, xem chi tiết ở [README.md](README.md) mục Issue Intelligence V3) + panel "Nguồn đăng nhiều nhất" (4 cột, thanh ngang so sánh 8 nguồn đứng đầu).
5. **"Tin tức"** — bảng/thẻ hợp nhất tin từ cả 23 nguồn, có ô tìm kiếm, bộ lọc theo nguồn/issue/thương hiệu, 2 nút sắp xếp Mới nhất/Đang hot, phân trang 15 tin/trang, trạng thái rỗng có nút "Xoá bộ lọc" khi lọc không ra kết quả.
6. **"Theo nguồn"** — bảng Kanban cũ, mỗi nguồn 1 cột đóng/mở bằng `<details>`, không còn màu/icon riêng theo nguồn.
7. **"Lưu trữ"** — 7 tab ngày (`dd/mm`) tự căn giữa quanh ngày đang xem + dropdown "Ngày khác".
8. **Footer** — tần suất tự động cập nhật.

Trang **Brands** và **Analytics** dùng cùng khung (page header + 4 thẻ KPI riêng) rồi tới các khối nội dung dạng thẻ gập/mở (`<details class="an-block">`) — nội dung từng khối xem ở [README.md](README.md) mục "Theo dõi thương hiệu & cảnh báo khủng hoảng" và mục "Analytics".

## Ngôn ngữ hình ảnh (design tokens)

```css
--bg:#F6F7F9;      --surface:#FFFFFF;   --surface-2:#F9FAFB;
--text:#0F172A;    --text-2:#475569;    --muted:#94A3B8;
--border:#E2E8F0;  --divider:#EEF2F6;
--accent:#2563EB;  --accent-soft:#EAF1FF; --live:#DC2626;
--radius:16px;     --radius-sm:10px;    --shadow:0 1px 2px rgba(15,23,42,.05);
```

Tone màu **SaaS trung tính lạnh** (nền xám xanh nhạt, chữ xanh đen, accent xanh dương, cảnh báo/tiêu cực đỏ) — đổi từ tone editorial be ấm/xanh rêu của bản v2.0 theo yêu cầu người dùng, chưa có bảng màu tối riêng (dark mode).

- **Font chính:** Inter (headline, nav, body, nút). **Font phụ:** IBM Plex Mono (giờ, số liệu, nhãn nguồn/issue/thương hiệu). Đã kiểm tra trước khi dùng: Inter có bộ subset Unicode riêng cho tiếng Việt trong response CSS2 thật của Google Fonts (`U+1EA0-1EF9`...) — rút kinh nghiệm từ lỗi font "Archivo Black" ở bản v1 (không có dấu tiếng Việt, từng gây lỗi hiển thị, xem lịch sử sửa lỗi trong README).
- **Accessibility:** `aria-current="page"` cho mục điều hướng đang active, `aria-expanded` cho nút mở drawer/sheet, trạng thái focus rõ ràng (`:focus-visible`), tôn trọng `prefers-reduced-motion` (tắt animation không cần thiết).
- **Không có JS framework nào** — toàn bộ tương tác (đóng/mở, lọc, sắp xếp, tìm kiếm, drawer, bottom sheet, thu gọn sidebar) là vanilla JS/`<details>`/CSS `:target`, không thêm thư viện hay build tool. Trạng thái thu gọn sidebar lưu qua `localStorage` để nhớ giữa các lần tải trang.
