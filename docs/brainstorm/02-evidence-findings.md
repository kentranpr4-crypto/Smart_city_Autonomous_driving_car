# Kết quả cào nguồn (2026-11-01) — những gì đã kiểm và ý nghĩa thiết kế

Registry: `data/refinery/domains/smartcity-v2x-landscape/` · 84 claim, 25 thực thể, 36/41 nguồn thử cào tải được (xem SOURCES.md). Nhãn: **[FACT]** có claim + span; **[INF]** suy luận; **[NULL]** không có nguồn.

## 1. Đính chính so với bản brainstorm đầu (vốn dựa trên tóm tắt tìm kiếm)
| Điểm | Bản đầu | Nguồn gốc cho thấy | Nguồn |
|---|---|---|---|
| DAIR-V2X | "39K frame" (bảng thứ cấp) | **71254 LiDAR + 71254 camera frame** [FACT] | S05 (arXiv abstract) |
| OPV2V | "12K frame, 230K box" | **11,464 frame, 232,913 box** [FACT] | S04 |
| V2V4Real | "năm 2022 hay CVPR 2023?" | arXiv 14/03/2023, **CVPR 2023**; 20K LiDAR / 40K RGB / 240K box / 5 lớp [FACT] | S03 |
| Nghị định 13/2023 | coi là văn bản hiện hành | **Bị NĐ 356/2025/NĐ-CP thay thế từ 01/01/2026** [FACT, tier B: EY + luatvietnam; chưa đọc bản gốc] | L10, L11 |
| Luật xe tự lái | "chờ xác nhận" | Luật 36/2024 (hợp nhất): **không thấy điều khoản riêng về xe tự lái**; chỉ có yêu cầu kỹ thuật cho xe R&D (Điều 42.5.h) [FACT, phạm vi hẹp] | L01 |
| Vinhomes ↔ AV | không thấy liên hệ | Vẫn **không có nguồn** nối Vinhomes với pilot AV [NULL]. Nhưng L4 của VinBigdata (Vingroup) đang pilot ở QTSC TP.HCM 07–09/2026 [FACT, B] | S09 |

## 2. Hạ tầng sẵn có mà dự án có thể tích hợp [FACT, tier B]
- Vinhomes công bố (01/11/2022) hệ thống an ninh đa lớp tại Ocean Park, **Smart City (Hà Nội)**, Grand Park: camera AI + **kiểm soát ra vào bằng nhận diện khuôn mặt** + 5 lớp cảm biến (V01).
- Grand Park: 271 ha, 4 trục Smart Management / Security / Community / Home (S11).
- VinBus: hợp tác Advantech cho camera AI giám sát hành vi lái xe (V04).
- **[INF]** CCTV AI đã có là nguồn object-detection tự nhiên cho "góc nhìn hạ tầng"; chưa có nguồn nói camera đó được hiệu chuẩn hay công bố API cho xe.

## 3. Bức tranh kỹ thuật [FACT, tier A]
- **Chuẩn thông điệp:** ETSI TS 103 324 V2.1.1 (06/2023) cho CPM; SAE J3224 (17/08/2022) cho SDSM. Cả hai là *object-level*, tức late fusion.
- **Demo thật gần nhất với ý tưởng của bạn:** FHWA (FHWA-HRT 26-028) — camera hạ tầng phát hiện người đi bộ → RSU → V2X Hub → SDSM → xe C-ADS nhường đường dù không có line-of-sight; demo tại ITS World Congress 2025 (S14).
- **Thách thức đã được nêu trong chính bài báo gốc:** bất đồng bộ thời gian và chi phí truyền (DAIR-V2X, S05); lỗi pose (CoAlign S21, V2X-ViT S18); băng thông (Where2comm S17: tác giả báo giảm >100,000× lượng truyền trên OPV2V — số của tác giả, chưa tái lập); trùng lặp (S07: ETSI dùng Value-of-Information).
- **Công cụ mô phỏng:** OpenCDA (co-simulation, S20); dataset OPV2V/V2X-Sim/V2V4Real/DAIR-V2X.

## 4. Bối cảnh pháp lý–vận hành Việt Nam
- **Hà Nội (Phenikaa-X, sandbox 24 tháng, ✓✓ hai nguồn):** tuyến cố định + bản đồ HD, **≤40 km/h, chỉ ban ngày 9:00–16:30, không chạy khi mưa lớn/dông/ngập/gió mạnh/sương dày, có safety supervisor**, bus ≤8 khách, robotaxi ≤4 khách (S08; riêng giờ và số khách chỉ có ở S08 nên chưa corroborated).
- **TP.HCM (QTSC, 07–09/2026):** hệ pilot gồm xe, trung tâm vận hành, giám sát từ xa, **nền tảng thu thập–phân tích dữ liệu**, cơ chế an toàn, quy trình đánh giá (S09).
- **Dữ liệu cá nhân (Luật 91/2025/QH15, hiệu lực 01/01/2026, Điều 32; trích qua cổng Hà Tĩnh, tier B):** được ghi hình nơi công cộng không cần đồng ý trong các trường hợp an ninh/trật tự…, **nhưng phải thông báo, dùng đúng mục đích, lưu đủ thời gian cần thiết rồi xoá**; dữ liệu sinh trắc học nằm trong nhóm nhạy cảm theo NĐ 356 (L04, L11).
- **[NULL]** Thông tin có ngoại lệ hay quy định riêng cho xe tự hành thu thập ảnh: không có nguồn.

## 5. Hệ quả thiết kế [INF — đề xuất, không phải nguồn]
1. Dùng **hộp vận hành Hà Nội làm ODD mặc định cho sim MVP** (≤40 km/h, ban ngày, có giám sát): có căn cứ công khai, dễ bảo vệ trước hội đồng.
2. **Chỉ chia sẻ object ẩn danh** (loại, pose, vận tốc, covariance, timestamp), xử lý ảnh tại edge: né rủi ro sinh trắc/ảnh, khớp ETSI CPM/SAE SDSM.
3. Kiến trúc City-layer của bạn trùng cấu trúc pilot TP.HCM (trung tâm vận hành + giám sát từ xa + nền tảng dữ liệu) → dễ trình bày là bản "mở rộng cooperative perception" của mô hình đang được pilot.
4. Đưa **time-offset và pose-error vào Scenario Lab** như tham số bắt buộc (vì DAIR-V2X, CoAlign, V2X-ViT đều coi là vấn đề chính).
5. Điểm khác biệt nghiên cứu: các dataset trên không phải giao thông xe máy VN [INF; chưa tìm nguồn kiểm đặc điểm từng dataset].

## 6. Chưa kiểm / hạn chế
- Spec ETSI/SAE: chỉ đọc scope và front-matter; chưa đọc cơ chế sinh CPM/SDSM chi tiết (SAE bị paywall).
- NĐ 356 và Luật 91/2025: chưa đọc bản gốc (thuvienphapluat 403) → nên đối chiếu trước khi dùng cho báo cáo chính thức.
- NĐ 353/2025 (sandbox), NQ 26/2026 Hà Nội: chưa tải.
- Chưa có nghiên cứu nào về độ trễ V2X thực tế tại VN; các con số độ trễ trong brainstorm 01 vẫn là mục tiêu thiết kế [ASSUME].
