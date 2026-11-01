# Brainstorm · Vinhomes Smart City: xe tự hành + CCTV chia sẻ góc nhìn

> Nhãn: **[EV]** có nguồn từ kết quả tìm kiếm (chưa đọc nguyên văn, xem `SOURCES.md`) · **[INF]** suy luận · **[PROP]** đề xuất · **[ASSUME]** giả định cần xác nhận.
> Số liệu độ trễ/băng thông bên dưới là **mục tiêu thiết kế [ASSUME]**, không phải số đo.

## 1. Vấn đề cốt lõi

Một xe chỉ thấy phần đường nằm trong tầm cảm biến của nó. Ở khu đô thị có khuất tầm (xe đỗ, góc cua, cây xanh, trẻ em chạy ra), **blind spot là nguồn rủi ro chính [INF]**.
Cooperative perception (CP) giải quyết bằng cách để xe và camera hạ tầng *chia sẻ object đã phát hiện* hoặc *đặc trưng trung gian*, để mỗi xe tự tính đường an toàn trên một bức tranh đầy đủ hơn.

**Nguyên tắc kiến trúc [PROP]:** chia sẻ để *tăng nhận thức*, không để *giao quyền điều khiển*. Mỗi xe vẫn phải an toàn khi mất mạng (failsafe), vì vậy dữ liệu chia sẻ chỉ là đầu vào bổ sung, không phải điều kiện bắt buộc để chạy.

## 2. Bằng chứng nền (đã thấy trong tìm kiếm)

| Chủ đề | Điều đã thấy | Nhãn |
|---|---|---|
| ETSI TS 103 324 | Collective Perception Service, V2.1.1 (06/2023), có ASN.1 công khai (BSD-3) | [EV] |
| SAE J3224 | Sensor Data Sharing Message (SDSM), 08/2022; RSU phát hiện VRU qua camera/LiDAR | [EV] |
| Redundancy | Gửi ngây thơ gây trùng lặp và nghẽn kênh; ETSI dùng Value-of-Information để chọn object | [EV] |
| Datasets | OPV2V (CARLA, sim), V2V4Real (thực, V2V), DAIR-V2X (thực, V-I). Số frame giữa các nguồn **mâu thuẫn** | [EV] mâu thuẫn |
| VN pilot | Hà Nội 24 tháng (Phenikaa-X, ≤40 km/h, tuyến cố định + HD map); TP.HCM pilot L4 07–09/2026 | [EV] |
| VinFast | Hợp tác NVIDIA + Autobrains cho robotaxi L4 (05/2026) | [EV] |
| Vinhomes ↔ AV | **Không tìm thấy** nguồn nối Grand Park với pilot xe tự hành | null |

## 3. Kiến trúc 4 tầng [PROP]

```
Tầng 1 EDGE (xe / CCTV / RSU)  →  Tầng 2 ZONE (MEC theo khu)  →  Tầng 3 CITY (Digital Twin + Fleet Ops)  →  Tầng 4 UI (Web)
 detect + track cục bộ            hợp nhất + gating + ghi log     bản đồ sống, quy tắc, replay, KPI       dashboard, giám sát, mô phỏng
```

- **Edge**: mỗi nguồn tự detect/track (YOLO + tracker), tự định vị, tự gắn timestamp đồng bộ (PTP/GNSS).
- **Zone (MEC)**: nhận object list từ nhiều nguồn, đưa về chung hệ tọa độ, loại trùng (data association), phát lại *bản tin tổng hợp* cho xe trong vùng. Giữ băng thông thấp vì chỉ truyền object, không truyền video.
- **City**: digital twin bản đồ (lane graph, HD map), lưu sự kiện, phân tích near-miss, quản lý đội xe và quy tắc ưu tiên.
- **Web**: bản đồ 2D/3D realtime, lớp "góc nhìn chia sẻ", replay, cảnh báo, công cụ mô phỏng.

### Ba mức chia sẻ (đánh đổi cốt lõi)

| Mức | Chia sẻ gì | Băng thông | Chịu lỗi hiệu chuẩn | Khuyến nghị |
|---|---|---|---|---|
| Late (object-level) | Danh sách object + covariance | Thấp | Tốt | **MVP**: khớp với SDSM/CPM |
| Intermediate (feature) | BEV feature đã nén | Trung bình | Kém, cần sync chặt | Giai đoạn sau |
| Early (raw) | Point cloud/ảnh | Rất cao | Rất kém | Không dùng ngoài lab |

**Vì sao chọn late fusion cho MVP [INF]:** chuẩn hóa được (SDSM/CPM), debug được, kênh không nghẽn, và lỗi extrinsic nhỏ không làm sụp cả pipeline.

## 4. Luồng "tự tính an toàn đường đi" [PROP]

1. Xe nhận object list từ nguồn khác → đổi sang frame của mình (cần pose chính xác + time-offset).
2. Hợp nhất với perception cục bộ (EKF/UKF hoặc JPDA), **giữ covariance và tuổi dữ liệu**.
3. Dựng **occupancy/risk map có phần "không biết"**: vùng khuất mà không ai quan sát vẫn coi là *có thể có người* (conservative).
4. Planner (NMPC hoặc lattice + cost) tối ưu quỹ đạo mượt, với ràng buộc khoảng cách an toàn tăng theo độ bất định.
5. Nếu dữ liệu chia sẻ trễ/mất/không tin cậy → **degrade** về perception cục bộ và giảm tốc (minimal-risk maneuver).

Điểm mấu chốt: **dữ liệu chia sẻ chỉ được làm *giảm* bất định khi đã qua kiểm tra; không được dùng để *nới* khoảng cách an toàn nếu chưa được xác thực [PROP].**

## 5. Rủi ro kỹ thuật (xếp theo mức nghiêm trọng)

| # | Rủi ro | Hệ quả | Giảm thiểu [PROP] |
|---|---|---|---|
| R1 | Sai đồng bộ thời gian giữa nguồn | Object "ảo" lệch vị trí khi xe chạy nhanh | PTP/GNSS, gắn timestamp ở sensor, bù chuyển động theo tuổi dữ liệu |
| R2 | Sai extrinsic/pose của CCTV hoặc xe | Object lệch hệ tọa độ | Hiệu chuẩn CCTV bằng landmark HD map, giám sát residual online |
| R3 | Nguồn bị giả mạo / bị hack | Xe phanh gấp hoặc bỏ qua vật cản thật | Chứng thực V2X (PKI/SCMS-kiểu), misbehavior detection, cross-check đa nguồn |
| R4 | Mất kết nối | Xe mất góc nhìn bổ sung | Failsafe độc lập, không phụ thuộc mạng để dừng an toàn |
| R5 | Trùng lặp object, nghẽn kênh | Tăng độ trễ | Gating theo Value-of-Information, chỉ gửi object thay đổi |
| R6 | Quyền riêng tư CCTV (mặt, biển số) | Rủi ro pháp lý | Chỉ truyền object ẩn danh; xử lý ảnh tại edge; **chờ xác nhận điều khoản pháp lý VN (null)** |
| R7 | Domain gap (dataset ngoại ≠ giao thông xe máy VN) | Detector kém | Thu dữ liệu riêng; xe máy là lớp ưu tiên |

> Giao thông Việt Nam có mật độ xe máy cao **[INF, cần dữ liệu]**; đa số dataset CP công khai ở Mỹ/Đức/Trung Quốc, nên đây là khoảng trống nghiên cứu thực sự và là điểm khác biệt của dự án.

## 6. Web app: module đề xuất [PROP]

| Module | Nội dung | MVP? |
|---|---|---|
| Live Map | Bản đồ khu đô thị, xe, camera, object chia sẻ, vùng khuất | ✅ |
| Shared-View Layer | Bật/tắt nguồn, xem object nào do ai thấy, độ tin cậy, tuổi dữ liệu | ✅ |
| Safety Engine | Tính risk map và quỹ đạo an toàn (mô phỏng) | ✅ (sim) |
| Scenario Lab | Kịch bản: trẻ chạy ra sau xe đỗ, ngã tư khuất, xe cấp cứu | ✅ |
| Fleet & Camera Health | Trạng thái, trễ, mất gói, lệch đồng bộ | ⏳ |
| Incident Replay | Phát lại sự kiện, near-miss | ⏳ |
| Policy & Privacy | Cấu hình ẩn danh, quyền truy cập, audit log | ⏳ |

**Stack gợi ý:** mô phỏng CARLA + SUMO (OpenCDA có sẵn CP), backend Python/FastAPI hoặc ROS 2 bridge, truyền realtime qua WebSocket/MQTT, frontend React + MapLibre/deck.gl. Phù hợp stack ROS 2 + Jetson của bạn: mỗi "xe" là một node ROS 2, bridge ra web.

## 7. Lộ trình [PROP]

| Pha | Mục tiêu | Kiểm được (AC) |
|---|---|---|
| P0 | Hoàn thiện nguồn dữ liệu (Refinery) | Mọi claim có snapshot + span |
| P1 | Sim 2D: 3 xe + 2 camera, late fusion, bản đồ web | Scenario "khuất tầm" giảm số lần phanh gấp so với không chia sẻ (đo trong sim) |
| P2 | Thêm trễ/mất gói/giả mạo | Hệ vẫn dừng an toàn khi cắt kết nối |
| P3 | CARLA/OpenCDA + dữ liệu thật (OPV2V/V2V4Real) | Benchmark detection có/không CP |
| P4 | Nhúng: Jetson Orin Nano + STM32, 1 xe mô hình | Chạy realtime, đo latency end-to-end |

## 8. Quyết định cần bạn chốt

1. **Phạm vi đồ án**: web + simulation (khả thi cao) hay có cả xe mô hình thật (P4)?
2. **Mức chia sẻ MVP**: đề xuất late fusion (object-level). Đồng ý?
3. **Nguồn mô phỏng**: CARLA (nặng, thực tế) hay mô phỏng 2D tự viết (nhẹ, nhanh)? Đề xuất 2D trước, CARLA sau.
4. **Cho phép host nào** trong network policy để cào tiếp (xem mục dưới).
