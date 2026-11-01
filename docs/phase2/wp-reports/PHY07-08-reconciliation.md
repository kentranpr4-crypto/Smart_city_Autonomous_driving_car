# Đối chiếu PHY-07 / PHY-08 với định nghĩa chuẩn (WP2)

Yêu cầu của chủ việc: *"Đối chiếu lại PHY-07/08 với định nghĩa chuẩn trong PRD. Không được âm thầm thay đổi ý nghĩa acceptance gate."*
Văn bản dưới đây **trích nguyên văn bằng script** từ `docs/phase2/02`, `05`, `07` (không gõ lại bằng tay) rồi ánh xạ từng thành phần tới test cụ thể.
Lưu ý về thời điểm: văn bản tổng hợp này được viết **sau** khi các test WP2 đã chạy. Chỉ các ngưỡng nằm trong chú thích của từng test mới được đăng ký trước khi chạy; những gì đã đổi *sau khi thấy kết quả* được liệt kê thẳng ở §6.

## 1. Định nghĩa chuẩn (nguyên văn)
**PRD §12 và liên quan (02):**
| R-PER-01 | Mỗi AV có cảm biến cục bộ với FOV, tầm, **che khuất hình học 2.5D theo độ cao** (ray-casting, PHY-07); miss/false-positive/nhiễu vị trí là tham số | Must | AC-M04 |
| R-PER-02 | Mỗi CCTV có FOV/tầm/pose, đăng ký lỗi tham số; xuất detection → tracker | Must | AC-M04 |
| R-PER-03 | Detector là **mô hình thống kê** trên ground truth (không phải YOLO); phải ghi rõ trong mọi báo cáo | Must | AC-M12 |
| R-TRK-01 | Mỗi nguồn chạy tracker CV-KF, xuất track kèm covariance và existence probability | Must | AC-M05 |
| AC-M04 | Che khuất đúng hình học: đối tượng sau vật che không xuất hiện trong detection cục bộ (test điểm-đa-giác) | test đơn vị |
| AC-M05 | Tracker: NEES trung bình nằm trong khoảng χ² chấp nhận trên cảnh tuyến tính | test thống kê, seed cố định |
| AC-M06 | Kênh: tỉ lệ mất/trễ đo được khớp tham số trong dung sai trên N mẫu | test thống kê |
| R-PHY-04 | Cảm biến: FOV, tầm, che khuất 2.5D theo độ cao, bất định đo, xác suất phát hiện | Must | PHY-07 |
| R-PHY-05 | Truyền thông: trễ, jitter, mất gói, tuổi dữ liệu (AoI) theo đồng hồ mô phỏng | Must | PHY-08 |
| PHY-07 | Cảm biến: FOV, che khuất 2.5D, bất định | Biên FOV; `D=d·h_s/(h_s−h_o)`; thống kê nhiễu và `p_d(r)` | giải tích ≤ 1 mm; thống kê χ² 95% |
| PHY-08 | Truyền thông và độ tươi | Lịch xác định → AoI tính tay; thống kê trễ/mất/jitter | AoI khớp chính xác; thống kê trong dung sai |

**Kế hoạch slice (05):**
| WP2 | Cảm biến 2.5D, che khuất, tracker | M | PHY-07, AC-VS-03 |
| WP3 | Kênh, TrackMsg, validator, AoI | M | PHY-08, AC-VS-04 |
| AC-VS-02 | Che khuất 2.5D đúng: người đi bộ sau xe tải không có trong detection của ego; có trong detection K1 khi trong FOV; kiểm biên và công thức `D=d·h_s/(h_s−h_o)` | PHY-07 |
| AC-VS-03 | Tracker CV-KF: NEES trung bình trong khoảng χ² 95% trên quỹ đạo tuyến tính tổng hợp | test thống kê |
| AC-VS-04 | Validator loại đúng lý do: stale, replay, `t_meas` tương lai, sai schema, nguồn lạ, mâu thuẫn quan sát trực tiếp; kênh khớp tham số | test đơn vị + PHY-08 |
| AC-VS-06 | I9: `ego/` không import truth; guard runtime | AST test |

**Tóm tắt trong 07 §7 (chỉ tham chiếu, định nghĩa chính thức ở PRD):**
| → PHY-07 | Cảm biến | FOV biên; ray-cast; che khuất 2.5D `D = d h_s/(h_s−h_o)`; thống kê nhiễu và `p_d(r)` khớp tham số | χ² 95% |
| → PHY-08 | Truyền thông và độ tươi | Lịch giao thông điệp biết trước → AoI răng cưa tính tay; thống kê trễ/mất/jitter khớp tham số | chính xác tuyệt đối với lịch xác định |

## 2. Ánh xạ thành phần PRD → test
| Thành phần của PHY-07 trong PRD | Test thực thi (WP2) | Dung sai |
|---|---|---|
| "Biên FOV" | `test_phy07_sensor_statistics.py::test_fov_boundary_is_inclusive_and_exact_to_1e9_rad`, `::test_range_boundary_located_within_1mm` | 1e-9 rad; 1 mm |
| `D = d·h_s/(h_s−h_o)` | `test_phy07_sensor_geometry.py::test_ground_shadow_end_matches_analytic_within_1mm` (30 ca: h_s∈(4, 6, 8), h_o∈(1, 3), 5 hình học vật cản mỏng và dày); `::test_sensor_not_above_obstacle_gives_unbounded_shadow` (h_s ≤ h_o) | ≤ 1 mm (đo thực ≈ 1e-14 m) |
| "che khuất 2.5D" / AC-M04 "test điểm-đa-giác" | `::test_shadow_polygon_equals_ray_test_everywhere_outside_a_1mm_band` (8000 điểm ngẫu nhiên: kết quả tia = nằm trong đa giác bóng); `::test_head_visible_over_low_wall_but_not_over_tall_wall`; `::test_cctv_sees_behind_a_truck_that_hides_the_ground_from_a_vehicle_sensor`; `::test_vehicle_occluders_block_but_own_vehicle_and_target_do_not` | 0 sai lệch ngoài dải 1 mm quanh biên |
| "thống kê nhiễu" | `::test_position_noise_matches_sigma_of_range_chi2_95` (3 tầm; χ² hai phía 95%, trung bình, độc lập x–y, cov khai báo) | χ² 95% |
| "`p_d(r)`" | `::test_detection_rate_matches_pd_of_range_chi2_95` (6 bin; công thức logistic **độc lập** với mã) | χ² 95% (df = số bin) |
| R-PHY-04 "bất định đo", R-PER-01/02 | cov khai báo = σ² thật; `declared_sigma_scale`; bias không lộ ra cho consumer | — |
| (liên quan) timestamps | `test_phy07_sensor_statistics.py::test_schedule_phase_timestamps_and_sequence_numbers_are_exact`, outage/seq gap | chính xác tuyệt đối |
| AC-VS-02 | `test_rig_integration.py::test_ego_sensor_sees_the_pedestrian_exactly_when_the_analytic_line_of_sight_opens`, `::test_cctv_sees_it_from_the_start...` | biên giải tích 39.5 m nằm giữa hai frame liên tiếp |

## 3. Làm rõ (clarification) — KHÔNG đổi ý nghĩa gate
1. **`d` trong công thức D** là khoảng cách ngang tới **mép trên phía xa** của vật cản. Với vật cản mỏng (độ dày → 0) trùng với cách đọc "mép trên vật cản" ở 07 §4; với vật cản dày, tia sượt mép phía **gần** đi xuyên vào lăng trụ nên bị chặn, nên mép phía xa mới quyết định điểm kết thúc bóng. Cả hai trường hợp (mỏng/dày) được test đến 1 mm.
2. **"χ² 95%"** được cụ thể hoá thành khoảng hai phía [χ²₀.₀₂₅, χ²₀.₉₇₅] cho tổng bình phương phần dư chuẩn hoá (nhiễu, df = 2N) và cận trên χ²₀.₉₅ cho thống kê Pearson của `p_d(r)` (df = số bin). Một seed cố định (20261101), **không chọn lại seed khi fail**. Hàm phân vị χ² tự viết được kiểm với bảng chuẩn (3.841459, 5.991465, 9.487729, 18.307038, 9.210340, 74.221927, 129.561197).
3. **AC-VS-03** ("NEES trung bình trong khoảng χ² 95%") được diễn giải và **đăng ký trước** như sau: M=100 lượt Monte-Carlo, K=60 bước; với mỗi k∈[10,59], `M·ANEES_k` nằm trong khoảng hai phía 95% của χ²(4M). PASS nếu ≥ 90% số bước nằm trong khoảng (kỳ vọng 95%), ANEES trung bình theo thời gian ∈ [3.6, 4.4] và NIS trung bình = 2 ± 4 SE. Đây là một **diễn giải của câu chữ gốc**, được ghi rõ ở đây để chủ việc duyệt hoặc đổi.
4. **Phạm vi:** PHY-07 trong PRD chỉ gồm cảm biến (FOV, che khuất, bất định, `p_d`). Tracker thuộc **AC-VS-03** và các test `test_trk_*`; cô lập ground truth thuộc **AC-VS-06**. Chúng được báo cáo thành dòng riêng trong `make check`, **không** được gộp vào PHY-07 để làm đẹp con số.

## 4. Phần hoãn sang WP3 (không bị âm thầm bỏ)
| Gate | Nội dung | Trạng thái |
|---|---|---|
| **PHY-08** | "Lịch giao thông điệp biết trước → AoI răng cưa tính tay; thống kê trễ/mất/jitter khớp tham số" | **NOT_CHECKED** (chưa có kênh, thuộc WP3). WP2 chỉ cung cấp tiền đề: `t_meas`, `t_avail`, `seq`, khoảng trống seq do outage, và việc tracker từ chối dữ liệu cũ. **Những thứ này không được tính là bằng chứng PHY-08.** |
| AC-VS-04 / AC-M06 | Validator ở phía nhận và kênh | WP3 |
Tracker WP2 đã có kiểm tra khung (replay, out-of-order, future, stale, schema, non-finite, covariance không hợp lệ…) như một lớp phòng thủ; validator chính thức của AC-VS-04 (nguồn lạ, mâu thuẫn quan sát trực tiếp) vẫn thuộc WP3.

## 5. Khẳng định tính nguyên vẹn
- Không tiêu chí PRD nào bị nới lỏng hay đổi đơn vị. Dung sai giải tích vẫn ≤ 1 mm; thống kê vẫn χ² 95%.
- Các test được **thêm** làm gate chặt hơn (ví dụ công thức `p_d` độc lập; quét đồ thị đối tượng chống kênh ngầm) sau khi bộ mutation phát hiện hai khoảng hở.
- Một số ngưỡng ở tầng tracker/association (ví dụ "0 ID switch trong 20 seed", "coverage ≥ 0.95") do tôi **đăng ký trước trong chú thích từng test**; chúng không nằm trong PRD. Chủ việc có thể đổi chúng, nhưng phải đổi **trước** khi chạy lại.

## 6. Những thay đổi thực hiện SAU khi thấy kết quả (nêu thẳng)
| # | Điều gì xảy ra | Cái gì đổi | Tiêu chí có đổi không? |
|---|---|---|---|
| 1 | Test AC-VS-03 đã đăng ký trước **FAIL** (ANEES 4.51, 52% bước trong khoảng) với cổng 99% | Sửa tracker: cổng mặc định 99.9% **và** thêm khử track trùng (nguyên nhân chính: track trùng làm đói track gốc; phần còn lại là thiên lệch do cắt cổng, +0.14). Ghi lại hiện tượng thành test đặc trưng | **Không** |
| 2 | Test stale: track quá hạn "sống lại" và nuốt detection mới sau khoảng trống 9.4 s | Sửa lỗi tracker: hết hạn track **trước** bước liên kết | Không |
| 3 | Test coverage khi outage: mẫu số tính cả frame sau khi mục tiêu ra khỏi FOV | Sửa **định nghĩa metric** (chỉ tính frame mà mục tiêu nằm trong FOV/tầm) | Ngưỡng 0.95 giữ nguyên; định nghĩa metric đổi |
| 4 | Test crossing: tiền điều kiện hình học "khoảng cách gần nhất ≥ 1.2 m" sai (thực tế 1.06 m) | Đổi hình học cảnh (đo giải tích 1.77 m); đổi tên test | Ngưỡng "0 ID switch" giữ nguyên |
| 5 | Test nhiễu RNG ghép cặp bắt được lỗi **thiết kế** (`rng.permutation` tiêu thụ số ngẫu nhiên theo số detection) | Sửa cảm biến: khoá xáo trộn cố định mỗi mục tiêu | Không |
| 6 | Mutation bite: 2 mutant sống sót (`p_d` tautology; kênh ngầm nhãn truth → tracker) | Thêm test độc lập công thức `p_d`; thêm quét đồ thị đối tượng | Chặt hơn, không nới |
| 7 | Hình học kịch bản tích hợp ban đầu không che được ego (ego thấy từ t=0) | Dựng lại hình học theo biên giải tích x_s = 39.5 m | Đây là thiết kế cảnh, không phải ngưỡng |
