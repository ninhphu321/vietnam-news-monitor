# Giao diện trang web Vietnam News Monitor

> Bản v2.0 (2026-09-16) — viết lại toàn bộ giao diện theo hướng "editorial newsroom" (Financial Times/Reuters/Bloomberg), thay cho bản v1 neo-brutalist/Kanban-first trước đó.

Tài liệu này mô tả cấu trúc giao diện của trang tĩnh sinh ra bởi [web/generate_site.py](web/generate_site.py) — không phải hướng dẫn dùng, mà là bản đồ các thành phần trên trang, thứ tự xuất hiện, và vì sao mỗi phần được làm như vậy. Xem trực tiếp bằng cách chạy:

```bash
python -m web.generate_site
```

rồi mở `site/index.html`.

## Nguyên tắc thiết kế

- **Editorial, không phải SaaS dashboard** — thông tin dày đặc, tìm tin nhanh, chữ là chính, hạn chế trang trí.
- **Không** dùng: glassmorphism, gradient, bóng đổ nặng, hiệu ứng 3D, emoji, thẻ (card) quá cầu kỳ.
- **Không tô màu riêng theo từng nguồn báo** (khác hẳn bản v1) — chỉ 1 màu accent duy nhất (`#1F4B45`), dùng rất tiết chế (~5% diện tích).

## Sơ đồ tổng thể (từ trên xuống dưới)

```
┌───────────────────────────────────────────────────────────┐
│ HEADER (sticky, 72px) — masthead · ô tìm kiếm ·            │
│         nav (TODAY/ISSUES/NEWS/SOURCES/ANALYTICS↗/ARCHIVE) │
│         trạng thái LIVE + giờ cập nhật · nút "Quét ngay"   │
├───────────────────────────────────────────────────────────┤
│ TODAY OVERVIEW — 1 dải ngang: tổng bài · tổng nguồn ·      │
│                  tổng issue nổi bật · giờ cập nhật         │
├───────────────────────────────────────────────────────────┤
│ TOP ISSUES — lưới 2 cột (desktop), 5 thẻ issue gọn         │
├───────────────────────────────────────────────────────────┤
│ ALL NEWS (mặc định, quan trọng nhất) — bộ lọc + dòng chảy  │
│           tin hợp nhất từ toàn bộ 23 nguồn, mới nhất trước │
├───────────────────────────────────────────────────────────┤
│ BY SOURCE — bảng Kanban cũ, lùi xuống thành mục phụ        │
├───────────────────────────────────────────────────────────┤
│ ARCHIVE — 7 tab ngày + dropdown "Ngày khác"                │
├───────────────────────────────────────────────────────────┤
│ FOOTER — tần suất cập nhật tự động                         │
└───────────────────────────────────────────────────────────┘
```

Các mục nav trong header (`TODAY`/`ISSUES`/`NEWS`/`SOURCES`/`ARCHIVE`) là **link neo** (`<a href="#overview">`...) cuộn mượt tới đúng section — toàn trang vẫn là 1 trang cuộn dài, không phải ứng dụng nhiều view ẩn/hiện bằng JS. Mọi collapse/expand (cột nguồn, chi tiết issue) vẫn dùng `<details>/<summary>` gốc của HTML, gần như không cần JS — JS chỉ dùng cho: nút "Quét ngay", ô tìm kiếm + bộ lọc + sắp xếp của All News, và dropdown "Ngày khác".

## 1. Header

- Cố định trên cùng (`position:sticky`), cao đúng 72px.
- Masthead "Vietnam News.Monitor" (dấu chấm tô màu accent).
- Ô tìm kiếm lọc trực tiếp tiêu đề trong "All news" (client-side, không gọi server).
- Trạng thái "LIVE · giờ cập nhật" — chấm tròn màu đỏ (`--live: #C84C3A`), không dùng emoji.
- Trên màn hình hẹp (<900px), nav và trạng thái LIVE tự ẩn để nhường chỗ cho ô tìm kiếm.

## 2. Today overview

Một dải ngang duy nhất (không phải 4 ô thống kê tách rời): **N bài viết · N nguồn · N issue nổi bật · Cập nhật lúc HH:MM**. Trang lưu trữ ngày cũ không có mục "issue nổi bật" (vì Top Issues chỉ tính cho hôm nay) và tiêu đề đổi thành "Overview" thay vì "Today overview" để không gây hiểu lầm.

## 3. Top Issues

- Lưới 2 cột trên desktop, 1 cột trên mobile/tablet.
- Mỗi thẻ ở trạng thái **thu gọn** (~180-220px) chỉ có: hạng (01-05), tiêu đề "Entity · Topic", điểm HotScore, số bài/số nguồn, tối đa 2 dòng "Vì sao hot".
- Bấm vào thẻ (`<details>`) để xem **chi tiết đầy đủ**: 4 thành phần HotScore (Khối lượng/Nguồn/Tốc độ/Mới), giờ thấy đầu tiên/gần nhất, **biểu đồ thanh ngang** mức độ đưa tin theo từng nguồn (không dùng biểu đồ tròn), và toàn bộ bài viết liên quan.
- Xem thuật toán xếp hạng (Entity/Topic/Issue, HotScore, ngưỡng ổn định...) ở [README.md](README.md) mục "Panel Top Issues hôm nay" và module [web/issues.py](web/issues.py).

## 4. All News — dòng chảy tin hợp nhất (trải nghiệm chính)

Đây là phần **mặc định và quan trọng nhất** của trang — khác biệt lớn nhất so với bản v1 (trước đây trang chủ mở thẳng vào bảng Kanban theo từng nguồn).

- Mỗi dòng tin chỉ có: **giờ · nguồn · tiêu đề (tối đa 2 dòng) · nhãn issue (nếu tin đó thuộc 1 trong 5 issue đang hot)**. Không ảnh đại diện, không tác giả, không tóm tắt, không nút chia sẻ — giữ mật độ thông tin cao, mục tiêu nhìn được 20-30 tiêu đề trong 1 màn hình desktop.
- **Bộ lọc** (ngay trên dòng chảy tin, dính lại khi cuộn): lọc theo nguồn, lọc theo issue, và 2 nút sắp xếp "Mới nhất"/"Đang hot" (toàn bộ chạy bằng JS thuần, không tải lại trang).
- Bấm vào nhãn issue trên 1 dòng tin sẽ nhảy tới đúng thẻ issue đó ở mục Top Issues và tự mở ra (dùng CSS `:target`, không cần JS).

## 5. By Source (mục phụ)

Giữ nguyên logic bảng Kanban cũ — mỗi nguồn 1 cột, cuộn ngang trên desktop (tự xếp dọc trên màn hình hẹp để tránh cuộn ngang theo đúng yêu cầu responsive), mỗi cột tự cuộn dọc riêng khi quá dài, đóng/mở bằng `<details>`. Khác bản v1: **không còn màu/icon riêng theo từng nguồn** — chỉ còn tên nguồn + số bài dạng chữ.

## 6. Archive

7 tab ngày (`dd/mm`) trải ngang, tự căn giữa quanh ngày đang xem, cộng dropdown "Ngày khác" khi có nhiều hơn 7 ngày dữ liệu — logic y hệt bản v1, chỉ đổi vị trí xuống cuối trang và đổi kiểu hiển thị (pill viền mỏng, không còn khối đen/trắng đảo màu).

## Ngôn ngữ hình ảnh (design tokens)

```css
--bg:#F5F3EE;        --surface:#FFFFFF;     --surface-2:#FAF9F6;
--text:#111111;      --text-2:#6B6B6B;      --muted:#9A978F;
--border:#DDD9D0;    --divider:#ECE8E1;
--accent:#1F4B45;    --accent-soft:#E8F0EE; --live:#C84C3A;
--radius:16px;       --shadow:0 1px 2px rgba(0,0,0,.04);
```

- **Font chính:** Inter (headline, nav, body, nút). **Font phụ:** IBM Plex Mono (giờ, số liệu, nhãn nguồn/issue). Đã kiểm tra trước khi dùng: Inter có bộ subset Unicode riêng cho tiếng Việt trong response CSS2 thật của Google Fonts (`U+1EA0-1EF9`...) — rút kinh nghiệm từ lỗi font "Archivo Black" ở bản v1 (không có dấu tiếng Việt, từng gây lỗi hiển thị, xem lịch sử sửa lỗi trong README).
- **Không dark mode** ở bản v2.0 này — đặc tả thiết kế chỉ đưa ra bảng màu sáng (light theme); bản v1 từng có dark mode tự động theo hệ điều hành nhưng bị bỏ khi viết lại theo đúng token màu được chỉ định. Có thể bổ sung lại sau nếu cần, dùng chung tông màu editorial này.
- **Không có JS layout framework nào** — toàn bộ tương tác (đóng/mở, lọc, sắp xếp, tìm kiếm) là vanilla JS/`<details>`/CSS `:target`, không thêm thư viện hay build tool.

## Tab Analytics (trang riêng `analytics.html`)

Link `ANALYTICS` trên thanh nav mở trang riêng (không nhúng vào trang chủ để trang chủ luôn nhẹ và tập trung vào đọc tin). Trang có header riêng (`HOME` / `ANALYTICS`, nav luôn hiện kể cả trên mobile) và lưới thẻ gập/mở `<details>` cùng phong cách với Top Issues: Ai đưa tin trước, Lịch sử Top Issues, Khoảng trống đưa tin, Độ trễ thu thập, Nhịp đăng bài theo giờ, Xu hướng 30 ngày, Khối lượng tin theo thời gian, Tin đăng lặp, Đồng xuất hiện, Hồ sơ chủ đề từng nguồn. Cuối phần mô tả có link tới dữ liệu thô `issues.json`, `stats.json`, `feed.xml`.
