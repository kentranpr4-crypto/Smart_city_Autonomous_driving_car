# 02 · MVP Product Requirements Document (T2)

Trạng thái: **DRAFT chờ duyệt**. Mọi giá trị ghi `[PARAM]` là tham số thiết kế **chưa được kiểm chứng**, sẽ được quét/ghi lại trong thí nghiệm; không phải sự kiện. Nhãn nguồn: `[DECISION]` chủ việc đã quyết · `[REF]` tham chiếu registry (xem ma trận 01) · `[ENG]` kiến thức kỹ thuật phổ thông, không phải nguồn.

## 1. Mục tiêu và phi mục tiêu
**Mục tiêu.** *Kiểm tra trong mô phỏng vật lý* liệu chia sẻ track mức object (xe–xe, CCTV–xe) có làm giảm rủi ro va chạm với người đi bộ bị che tại một ngã tư hay không, **mà không tạo phụ thuộc an toàn vào kênh chia sẻ**, và đo chi phí (phanh nhầm, rủi ro cho xe theo sau, trễ, băng thông). **Không tiền giả định rằng chia sẻ làm an toàn hơn ego-only**; đó là giả thuyết cần kiểm với hai baseline riêng E0-N và E0-C.
**Phi mục tiêu.** Không huấn luyện mô hình; không triển khai toàn thành phố; không tuyên bố hệ này mô tả/đã triển khai tại Vinhomes `[DECISION]`; không tuân thủ pháp lý/chứng nhận an toàn; không dùng video thật; không đánh giá phần cứng Jetson/STM32 (giai đoạn sau); **không phải một dashboard hoạt hoạ** — kết quả khoa học đến từ mô phỏng vật lý có thẩm quyền (§12), không từ hoạt cảnh trình duyệt.

## 2. Phạm vi `[DECISION]`
3 xe tự hành (A1 ego, A2, A3) · 4 nút CCTV (K1–K4) · 1 ngã tư · 1 đoạn đường bị che (làn tiếp cận ngã tư bị xe tải đỗ che vạch qua đường).
Vai trò gợi ý (có thể đổi khi duyệt): A1 = ego tiếp cận làn bị che; A2 = xe ngược chiều/ở nhánh vuông góc có tầm nhìn tới người đi bộ; A3 = xe theo sau A1. K1 phủ vạch qua đường; K2 phủ làn tiếp cận phía sau xe tải; K3 phủ tâm ngã tư; K4 phủ đoạn bị che từ phía đối diện.

## 3. ODD (Operational Design Domain)
| ID | Tham số | Giá trị | Nguồn / trạng thái |
|---|---|---|---|
| ODD-01 | Môi trường | Khu đô thị nội khu mô phỏng, mặt đường phẳng, làn 3.5 m `[PARAM]` | `[DECISION]` cảm hứng Vinhomes, **không** là bản đồ thật |
| ODD-02 | Tốc độ tối đa của xe | 40 km/h (11.1 m/s) | `[REF]` C50·Hanoi Phenikaa-X ; tham chiếu sandbox Hà Nội, tier B; **lựa chọn thiết kế, không phải tuân thủ** |
| ODD-03 | Tốc độ danh định S01 | 30 km/h (8.33 m/s) `[PARAM]` | thiết kế |
| ODD-04 | Thời tiết/ánh sáng | Trời quang, ban ngày; mô hình cảm biến không có suy giảm thời tiết | `[REF]` C50·Hanoi Phenikaa-X ; S08:31~9:00 am to 4:30 pm ; hạn chế thời tiết nằm trong claim trên, giờ ban ngày chưa là claim |
| ODD-05 | Giám sát con người | **Không mô phỏng** takeover của safety supervisor | `[REF]` C51·Hanoi Phenikaa-X ; có giám sát trên xe thật; MVP phải tự đứng được → giới hạn đã biết |
| ODD-06 | Đối tượng giao thông | Người đi bộ, xe tải đỗ (che), 3 AV; không có xe máy/xe đạp trong MVP | giới hạn: giao thông VN nhiều xe máy → khoảng trống (xem 01 G07) |
| ODD-07 | Hạ tầng | 4 CCTV cố định, pose đã đăng ký với sai số tham số hoá | A04 UNKNOWN: chỉ là mô hình |
| ODD-08 | Ngoài ODD (phải xử lý an toàn) | Đối tượng ngoài miền hình học, tốc độ vượt ODD-02, nhiều hơn N object vượt tải | xem FM17 |

## 4. Yêu cầu chức năng
| ID | Yêu cầu | Ưu tiên | Kiểm bằng |
|---|---|---|---|
| R-SIM-01 | Mô phỏng vật lý **bước cố định, tất định, backend là nguồn trạng thái có thẩm quyền** (cùng seed → cùng quỹ đạo, cùng hash telemetry); chi tiết ở §12 và tài liệu 07 | Must | AC-M01, PHY-01 |
| R-SIM-02 | Cấu hình kịch bản khai báo (YAML): hình học, diễn viên, nguồn, nhiễu, kênh, seed | Must | AC-M02 |
| R-SIM-03 | Ground truth độc lập: mọi metric an toàn tính từ trạng thái thật, không từ track | Must | AC-M03 |
| R-PER-01 | Mỗi AV có cảm biến cục bộ với FOV, tầm, **che khuất hình học 2.5D theo độ cao** (ray-casting, PHY-07); miss/false-positive/nhiễu vị trí là tham số | Must | AC-M04 |
| R-PER-02 | Mỗi CCTV có FOV/tầm/pose, đăng ký lỗi tham số; xuất detection → tracker | Must | AC-M04 |
| R-PER-03 | Detector là **mô hình thống kê** trên ground truth (không phải YOLO); phải ghi rõ trong mọi báo cáo | Must | AC-M12 |
| R-TRK-01 | Mỗi nguồn chạy tracker CV-KF, xuất track kèm covariance và existence probability | Must | AC-M05 |
| R-COM-01 | Kênh mô phỏng: trễ cố định+jitter, mất gói (ngẫu nhiên/burst), blackout, đảo thứ tự, trùng lặp | Must | AC-M06 |
| R-COM-02 | Mọi thông điệp theo hợp đồng `TrackMsg` (mục 8), có `seq`, `t_meas`, `t_sent`, `source_id`, `provenance` | Must | AC-M07 |
| R-FUS-01 | Ego hợp nhất track cục bộ với track nhận được: liên kết, hợp nhất có tính covariance, chống đếm trùng | Must | AC-M08 |
| R-FUS-02 | Kiến trúc fusion cắm được: `centralized` / `decentralized` / `hybrid` qua cấu hình, cùng giao diện | Must | AC-M09 |
| R-FUS-03 | Mỗi track dùng được gán trạng thái `validated`/`rejected` kèm mã lý do | Must | AC-M10 |
| R-PLN-01 | Planner dọc (tốc độ) đóng vòng với kiểm soát phanh: nhận môi trường hợp nhất, xuất gia tốc | Must | AC-M11 |
| R-PLN-02 | Hai chính sách ego-only chạy song song và cấu hình được: **EO-N** (danh định, không giới hạn theo che khuất) và **EO-C** (thận trọng, tốc độ theo tầm nhìn). Kết quả cuối = `min` hạn chế so với chính sách ego-only của profile (xem I2, DEC-1) | Must | AC-M13 |
| R-SAF-01 | Giám sát an toàn độc lập planner: kiểm độ tươi, nhất quán, watchdog kênh, chế độ suy giảm | Must | AC-M13..M15 |
| R-SAF-02 | Chế độ suy giảm khi mất kênh: về chính sách ego-only của profile. Profile P1 → EO-N (không tệ hơn ego-only, không an toàn hơn). Profile P2 (nếu duyệt) → EO-C (giới hạn theo tầm nhìn) | Must | AC-M14 |
| R-LOG-01 | Telemetry JSONL: trạng thái thật, track, quyết định, track bị từ chối + lý do, độ trễ từng chặng | Must | AC-M16 |
| R-UI-01 | Digital twin 3D: cảnh, xe, CCTV + frustum, người đi bộ, track (kèm elip bất định), lớp an toàn | Must | AC-M17 |
| R-UI-02 | Telemetry panel: tốc độ, gia tốc, TTC, AoI, trễ, trạng thái chế độ, sự kiện an toàn | Must | AC-M17 |
| R-UI-03 | Phát lại từ JSONL (tua, tốc độ, bước) và chế độ trực tiếp | Should | AC-M18 |
| R-UI-04 | Bật/tắt từng nguồn chia sẻ để so sánh E0–E3 trực quan | Should | AC-M18 |
| R-EXP-01 | Bộ chạy thí nghiệm hàng loạt (seed × điều kiện) + bảng metric + khoảng tin cậy | Must | AC-M19 |
| R-DOC-01 | Mỗi kết quả kèm manifest (commit, seed, config hash, phiên bản schema) | Must | AC-M20 |

## 5. Yêu cầu phi chức năng
| ID | Yêu cầu | Chỉ tiêu `[PARAM]` | Kiểm bằng |
|---|---|---|---|
| N-01 | Tất định | Hai lần chạy cùng seed → SHA-256 telemetry giống nhau | AC-M01 |
| N-02 | Hiệu năng sim | ≥ 1× thời gian thực trên máy tham chiếu; bước vật lý 10 ms cố định; chế độ `free-run` cho thí nghiệm | AC-M21 |
| N-03 | Hiệu năng UI | Dựng ≥ 30 fps với ≤ 8 xe/CCTV/diễn viên trên Chromium headless | AC-M17 |
| N-04 | Khả tái lập | Một lệnh dựng môi trường + một lệnh chạy lại bảng kết quả | AC-M20 |
| N-05 | Quan sát được | Mọi quyết định phanh truy ngược về tập track đầu vào | AC-M16 |
| N-06 | Riêng tư | Không hình ảnh/biometric đi qua ranh giới nguồn; chỉ track mức object | AC-M07 |
| N-07 | Mở rộng | Thêm nguồn/xe không đổi giao diện fusion/planner | AC-M09 |
| N-08 | Trung thực kết quả | Báo cáo luôn ghi mô hình hoá, giới hạn, nhãn "chỉ giá trị trong mô phỏng" | AC-M12 |
| N-09 | Phụ thuộc | Python ≥3.11, numpy; không cần GPU, không cần mạng khi chạy | AC-M21 |

## 6. Bất biến an toàn (I1–I12)
Một bất biến là tính chất phải đúng ở **mọi bước mô phỏng**; vi phạm = lỗi nghiêm trọng, chặn bàn giao.
| ID | Bất biến |
|---|---|
| I1 | **Tự chủ cục bộ.** Ego phải đạt trạng thái rủi ro tối thiểu (dừng) chỉ bằng cảm biến + bản đồ onboard; không có đường mã nào mà thiếu dữ liệu ngoài làm chặn hoặc trì hoãn phanh. |
| I2 | **(Ràng buộc thiết kế cần kiểm, không phải tính chất đã chứng minh.)** **Chia sẻ chỉ mang tính tư vấn và đơn điệu hạn chế so với chính sách ego-only của profile.** Dữ liệu chia sẻ chỉ được *thêm* vật cản/ràng buộc hoặc tăng độ tin cậy tồn tại; **không** được xoá, làm giảm tin cậy một đối tượng mà cảm biến cục bộ thấy, mở rộng không gian trống, hay nâng tốc độ cho phép lên trên mức chính sách ego-only của profile (P1: EO-N). (Đánh đổi: có thể phanh nhầm — đo bằng "false braking". **Hệ quả cần chủ việc biết:** vì chia sẻ không được nới tốc độ, lợi ích an toàn so với EO-C bằng 0 theo thiết kế; lợi ích chỉ có so với EO-N. Hạn chế thêm có thể gây phanh gấp và **rủi ro cho xe theo sau**; điều này được đo, không giả định là vô hại. Xem DEC-1.) |
| I3 | **Không thấy ≠ trống.** Báo cáo "không có object" từ bất kỳ nguồn nào (hoặc thiếu thông điệp) không được dùng để xoá vùng bị che; vùng chưa quan sát tự thân vẫn là "có thể có người". (Cơ sở: D02, nhưng ngữ nghĩa chuẩn chưa đọc.) |
| I4 | **Độ tươi.** Track chỉ dùng khi tuổi ≤ τ(v) sau khi bù chuyển động; thông điệp có `t_meas` ở tương lai hơn dung sai ε bị loại. τ(v) là hàm tham số, ghi trong config, không phải hằng số ẩn. |
| I5 | **Nhất quán.** Track chia sẻ chỉ ở trạng thái `validated` khi: hợp lệ schema; trong miền hình học ODD; hợp lý động học (tốc độ/gia tốc ≤ ngưỡng lớp); `seq` đơn điệu (chống phát lại); `source_id` thuộc danh sách cho phép; **không mâu thuẫn** với quan sát trực tiếp của ego trong vùng ego nhìn thấy. Track chưa `validated` không được dẫn tới điều khiển nhưng phải được ghi log. |
| I6 | **Giới hạn điều khiển.** Gia tốc/jerk trong giới hạn; phanh khẩn cấp ≤ a_max; mọi phanh khẩn cấp có nguyên nhân truy được. |
| I7 | **Watchdog kênh.** Mất heartbeat > T_hb → ghi `coop_lost` và chuyển về chính sách ego-only của profile. P1: EO-N (tốc độ không đổi, **không** được hứa an toàn với người bị che — chỉ "không tệ hơn ego-only"). P2: EO-C, với `v·t_r + v²/(2a) ≤ d_sight`. |
| I8 | **Truy vết.** Mỗi quyết định điều khiển ghi: chế độ, track dùng, track bị từ chối + lý do, nguồn, độ tươi. |
| I9 | **Tách ground truth.** Không thành phần nào của AV đọc được ground truth (kiểm bằng kiến trúc + test). |
| I10 | **Backend có thẩm quyền.** Chỉ backend giữ và tiến trạng thái vật lý; frontend không tạo, sửa hay suy ra trạng thái vật lý/an toàn. |
| I11 | **Độc lập khỏi FPS và wall-clock.** Kết quả khoa học (telemetry, metric) không phụ thuộc tốc độ render, tải máy hay độ trễ mạng tới trình duyệt; thời gian tính toán của module là tham số mô phỏng. |
| I12 | **Không có đường điều khiển từ UI vào vật lý.** UI chỉ chọn kịch bản/seed, play/pause/tốc độ phát, reset; mọi thông điệp khác bị từ chối và ghi log. |

## 7. Chế độ lỗi
| ID | Lỗi | Phát hiện | Đáp ứng | Bất biến | Kiểm |
|---|---|---|---|---|---|
| FM01 | Mất kênh hoàn toàn (blackout) | Watchdog heartbeat | Suy giảm (I7); tiếp tục ego-only | I1, I7 | S01-E4c |
| FM02 | Trễ tăng đột biến | Tuổi track > τ(v) | Loại track, ghi log | I4 | S01-E4a |
| FM03 | Mất gói ngẫu nhiên/burst | Khoảng trống `seq`, AoI tăng | Dựa track còn tươi; suy giảm nếu hết | I4, I7 | S01-E4b |
| FM04 | Đảo thứ tự / trùng lặp | `seq` không đơn điệu | Loại/khử trùng | I5 | S01-E4d |
| FM05 | Phát lại thông điệp cũ | `seq`/`t_meas` cũ | Loại | I4, I5 | S01-E4e |
| FM06 | Nguồn giả (ghost object) | Mâu thuẫn quan sát trực tiếp / động học / allowlist | Không dẫn tới điều khiển nếu mâu thuẫn; nếu không phát hiện được → phanh nhầm (đo, chấp nhận có điều kiện) | I5 | S01-E4f, S01-N2 |
| FM07 | CCTV mất nguồn | Heartbeat nguồn | Bỏ nguồn; các nguồn khác tiếp tục | I1 | S01-E4c |
| FM08 | CCTV lệch pose/drift | Residual liên kết tăng; test nhất quán với ego | Hạ trọng số/loại nguồn | I5 | S01-E4h |
| FM09 | Lệch đồng hồ giữa nút | So `t_sent`/`t_recv`, kiểm tuổi âm | Bù hoặc loại | I4 | S01-E4g |
| FM10 | Đổi ID/cắt-ghép track sai | Chỉ số association (ID switch) | Hợp nhất bảo thủ | I2 | EX-ASSOC |
| FM11 | Miss-detection tại CCTV | — (không phát hiện được từ bên ngoài) | Ego-only không phụ thuộc | I1, I3 | S01-E2 biến thể miss |
| FM12 | False positive tại CCTV | Mâu thuẫn quan sát | Như FM06 | I5 | S01-N2 |
| FM13 | Ego mất định vị | Phương sai pose vượt ngưỡng | Không dùng dữ liệu chia sẻ có toạ độ; dừng an toàn | I1 | S01-E5 (mở rộng, sau MVP) |
| FM14 | Quá tải tính toán | Bước sim vượt hạn | Bỏ track ưu tiên thấp theo VoI; ghi log | I1 | EX-LOAD |
| FM15 | Phiên bản schema không khớp | `schema_version` | Từ chối thông điệp | I5 | test hợp đồng |
| FM16 | Phanh–nhả dao động (chatter) | Đếm chuyển trạng thái | Hysteresis + giữ tối thiểu | I6 | S01-N1 |
| FM17 | Đối tượng ngoài ODD | Kiểm miền | Đánh dấu `out_of_odd`, dừng bảo thủ | I1 | test đơn vị |
| FM18 | UI hiển thị lệch dữ liệu | Hash khung vs telemetry | Ghi nhận; không ảnh hưởng điều khiển | — | AC-M17 |

## 8. Hợp đồng dữ liệu
Quy ước: đơn vị SI; khung `map` là ENE cục bộ (x East, y North, mét, gốc cố định trong config); `yaw` rad ngược chiều kim đồng hồ từ +x; thời gian theo giây, hai loại đồng hồ phân biệt rõ.
**Các tên trường dưới đây là của dự án này.** Chưa ánh xạ sang trường CPM/SDSM vì chưa đọc phần mã hoá (xem 01 A06, D01, D02, G01). Ánh xạ là việc cần làm sau khi đọc spec.

### 8.1 `TrackMsg` (JSON Schema 2020-12, rút gọn)
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "TrackMsg", "type": "object",
  "required": ["schema_version","msg_id","seq","source","t_meas","t_sent","frame","tracks"],
  "properties": {
    "schema_version": {"const": "0.1.0"},
    "msg_id": {"type": "string"},
    "seq": {"type": "integer", "minimum": 0, "description": "per-source, strictly increasing"},
    "source": {"type": "object", "required": ["source_id","source_type","clock_id","provenance"],
      "properties": {
        "source_id": {"type": "string"},
        "source_type": {"enum": ["vehicle","cctv","aggregator"]},
        "clock_id": {"type": "string"},
        "clock_sync": {"enum": ["synced","drifting","unknown"]},
        "pose": {"type": "object", "description": "source pose in map + its covariance; required for source_type=vehicle"},
        "provenance": {"type": "object", "required": ["sensor_model","algo_version","calib_id","privacy_level"],
          "properties": {"privacy_level": {"const": "object_only"}}}}},
    "t_meas": {"type": "number", "description": "measurement time on the source clock [s]"},
    "t_sent": {"type": "number", "description": "send time on the source clock [s]"},
    "frame": {"const": "map"},
    "tracks": {"type": "array", "items": {"$ref": "#/$defs/Track"}}
  },
  "$defs": {"Track": {"type": "object",
    "required": ["track_id","class","pose","vel","cov","existence"],
    "properties": {
      "track_id": {"type": "string", "description": "source-local; NOT a global id"},
      "class": {"type": "object", "required": ["label","prob"],
        "properties": {"label": {"enum": ["pedestrian","vehicle","unknown"]}, "prob": {"type": "number","minimum":0,"maximum":1}}},
      "pose": {"type": "object", "required": ["x","y","yaw"]},
      "vel": {"type": "object", "required": ["vx","vy"]},
      "extent": {"type": "object", "properties": {"length":{},"width":{}}},
      "cov": {"type": "object", "required": ["P_xyvxvy","var_yaw"],
        "description": "P_xyvxvy: 4x4 row-major over [x,y,vx,vy]"},
      "existence": {"type": "number", "minimum": 0, "maximum": 1},
      "age_s": {"type": "number", "minimum": 0}}}}
}
```
Quy tắc: `t_recv` do bên nhận gán (đồng hồ bên nhận), không nằm trong thông điệp. Tuổi dữ liệu = `t_now_recv − (t_meas + δ_clock)`; δ_clock chưa biết → xử lý bằng I4/FM09, không giả định bằng 0.

### 8.2 `Telemetry` (một dòng JSONL mỗi bước ghi)
`t_sim`, `truth{actors[]}`, `ego{pose,v,a,mode}`, `sources[{id,status,last_seq}]`, `rx[{msg_id,source,t_meas,t_recv,age,verdict,reason}]`, `fused[{id,pose,cov,from[]}]`, `decision{a_cmd,cause,tracks_used[],tracks_rejected[{id,reason}]}`, `metrics{ttc,min_dist,aoi}`, `events[]`.

### 8.3 `ScenarioConfig` (YAML)
`schema_version, seed, duration, map{...}, actors[...], sensors[...], channel{...}, fusion{topology}, safety{tau_age, T_hb, a_max, ...}, experiment{id, condition}`. Mọi tham số `[PARAM]` nằm ở đây; không hằng số ẩn trong code.

### 8.4 `SafetyEvent`
`{t_sim, type: collision|near_miss|emergency_brake|mode_change|msg_rejected|invariant_violation, actor_ids, details}`.

## 9. Tiêu chí chấp nhận MVP
`AC-Mxx` kiểm *MVP đầy đủ* (sau slice). Tiêu chí của *vertical slice* nằm ở tài liệu 05 (`AC-VS-xx`).
| ID | Tiêu chí | Cách kiểm (lệnh sẽ có sau khi triển khai) |
|---|---|---|
| AC-M01 | Cùng config+seed ×2 → SHA-256 telemetry trùng | `make determinism` |
| AC-M02 | Config sai schema bị từ chối với thông báo định vị lỗi | test đơn vị |
| AC-M03 | Metric an toàn chỉ đọc ground truth; test kiểm AV không import module truth | test kiến trúc |
| AC-M04 | Che khuất đúng hình học: đối tượng sau vật che không xuất hiện trong detection cục bộ (test điểm-đa-giác) | test đơn vị |
| AC-M05 | Tracker: NEES trung bình nằm trong khoảng χ² chấp nhận trên cảnh tuyến tính | test thống kê, seed cố định |
| AC-M06 | Kênh: tỉ lệ mất/trễ đo được khớp tham số trong dung sai trên N mẫu | test thống kê |
| AC-M07 | Mọi thông điệp qua kênh hợp lệ schema; không trường ảnh/biometric | test hợp đồng |
| AC-M08 | Fusion không đếm trùng: cùng đối tượng thật từ 2 nguồn → 1 track hợp nhất, NEES hợp lý | test kịch bản |
| AC-M09 | Ba topology chạy qua cùng giao diện, cùng bộ test | test tham số hoá |
| AC-M10 | Mỗi thông điệp nhận có `verdict`+`reason`; bộ test FM04/05/06/09/15 đều bị loại đúng lý do | test bất biến |
| AC-M11 | Vòng kín: phanh phản ứng với track hợp nhất; gia tốc trong giới hạn I6 | test kịch bản |
| AC-M12 | Báo cáo kết quả luôn có khối "giới hạn mô hình hoá" (detector thống kê, vật lý mặt phẳng + vòng ma sát, kênh mô hình, không tương đương CARLA) | kiểm tự động chuỗi bắt buộc |
| AC-M13 | I2: property test — với mọi đầu vào chia sẻ ngẫu nhiên, lệnh cuối ≤ lệnh ego-only về tốc độ cho phép | property-based test |
| AC-M14 | I7: blackout → `coop_lost` trong ≤ T_resp và hành vi trùng chính sách ego-only của profile (so sánh cặp seed); với P2, tốc độ ≤ v_sd | S01-E4c |
| AC-M15 | I1/I3: với toàn bộ dữ liệu chia sẻ bị xoá/làm rỗng, kết quả = E0-N (P1) — không tệ hơn ego-only | so sánh cặp seed |
| AC-M16 | Telemetry đủ trường §8.2; mỗi lệnh phanh truy được tập track | test truy vết |
| AC-M17 | UI dựng đúng số thực thể = telemetry; ≥30 fps; ảnh chụp lớp an toàn | Playwright + so khớp DOM/canvas |
| AC-M18 | Phát lại từ JSONL tái tạo đúng trạng thái tại t chọn; bật/tắt nguồn đổi kết quả hiển thị tương ứng | Playwright |
| AC-M19 | Bộ chạy xuất bảng metric đủ E0–E4 kèm CI; số chạy = hàng trong CSV | `make experiments` |
| AC-M20 | Manifest (commit, seed, config hash, schema) đi kèm mọi bảng; chạy lại từ manifest ra cùng số | `make reproduce` |
| AC-M21 | Chạy được từ môi trường sạch không mạng sau bước cài phụ thuộc | CI sạch |
| AC-M22 | Không có bất biến nào bị vi phạm trong toàn bộ lượt chạy thí nghiệm (đếm = 0) | báo cáo `invariant_violation` |

## 10. Truy vết tới khoảng trống bằng chứng
Các yêu cầu dựa trên giả định **UNKNOWN/HYPOTHESIS** (01) phải bị kiểm bằng thí nghiệm, không được coi là tiền đề: A03→EX-ABL, B02→EX-TSYNC, B06/G05→suy ra ở 04 §3, C03/C04→EX-ASSOC, D03→EX-ABL, E03→AC-M14/M15, E04→quét tham số (không tuyên bố thực tế), F03→tham số khai báo ở 04, G07→giới hạn N-08.

## 11. Quyết định cần chủ việc
1. Vai trò A2/A3 và vị trí K1–K4 (mục 2) có chấp nhận không?
2. **DEC-1 · Giá trị của chia sẻ trong khuôn khổ "chỉ tư vấn".** Tính toán (04 §3) cho thấy một ego-only thận trọng (EO-C) tránh được va chạm S01 chỉ chậm hơn ~1 s trên 30 m tiếp cận. Hai cách đặt:
   - **P1 (khuyến nghị cho MVP):** chia sẻ chỉ *hạn chế thêm* so với EO-N; claim là "giảm rủi ro khi kênh hoạt động, không bao giờ tệ hơn ego-only". EO-C luôn được báo cáo như baseline đủ năng lực để lợi ích không bị phóng đại; kết quả trung thực có thể là "lợi ích an toàn so với EO-C = 0, lợi ích hiệu quả ≈ 1 s".
   - **P2 (thí nghiệm riêng, cần bạn duyệt):** xe được chạy danh định chỉ khi có *xác nhận bao phủ* còn tươi từ CCTV (nới I2/I3 một cách có kiểm soát); mất kênh → EO-C. Làm chia sẻ trở thành thành phần an toàn-phụ-thuộc → đòi hỏi bằng chứng mà hiện là UNKNOWN (D03, F03).
   Cần bạn chọn P1 hoặc P1+P2 trước khi triển khai.
3. **Ảnh tham chiếu hình ảnh** (chưa nhận được; chặn VIS-08) và máy tham chiếu đo hiệu năng.
4. Ngưỡng chấp nhận phanh nhầm và các ngưỡng quyết định kiến trúc (04 §6) do chủ việc đặt **trước** khi chạy.

## 12. Phụ lục A1 · Độ trung thực vật lý và trực quan hoá (bắt buộc)
Chi tiết kỹ thuật và lý do nằm ở `07-amendment-a1-physics-and-visualization.md`. Phụ lục này là **định nghĩa chính thức** của các cổng.

### 12.1 Yêu cầu bổ sung
| ID | Yêu cầu | Ưu tiên | Kiểm bằng |
|---|---|---|---|
| R-PHY-01 | Vòng bước cố định (dt_phys 10 ms) với thứ tự bước cố định; backend tiến trạng thái; thời gian tính toán module là tham số | Must | PHY-01 |
| R-PHY-02 | Động học xe: vị trí, hướng, vận tốc, gia tốc; lái và ràng buộc quay; vòng ma sát μ; actuator có trễ + giới hạn jerk/gia tốc; hình học OBB | Must | PHY-02..05 |
| R-PHY-03 | Quỹ đạo người đi bộ, phát hiện va chạm hình học, ghi tốc độ va chạm; kết thúc tại va chạm | Must | PHY-06 |
| R-PHY-04 | Cảm biến: FOV, tầm, che khuất 2.5D theo độ cao, bất định đo, xác suất phát hiện | Must | PHY-07 |
| R-PHY-05 | Truyền thông: trễ, jitter, mất gói, tuổi dữ liệu (AoI) theo đồng hồ mô phỏng | Must | PHY-08 |
| R-PHY-06 | Giao diện `PhysicsBackend`/`SensorProvider` để cắm backend khác (CARLA) mà không đổi phần trên; ghi metadata backend vào mọi kết quả; **không** tuyên bố tương đương | Must | AC-M20, PX-1 (tương lai) |
| R-PHY-07 | Tài liệu giới hạn trung thực nằm trong mọi báo cáo kết quả | Must | AC-M12 |
| R-VIS-01 | Diorama 3D thành phố đủ danh mục đối tượng (07 §10.2), không icon 2D thay thế | Must | VIS-01 |
| R-VIS-02 | Bốn chế độ camera (Vehicle, CCTV, Bird's-eye, City overview) + orbit/zoom/follow mượt | Must | VIS-02 |
| R-VIS-03 | Bóng nhất quán, che khuất đúng, bánh xe quay đúng tốc độ thật | Must | VIS-03..05 |
| R-VIS-04 | Lớp cooperative perception: track + bất định, FOV, vùng khuất, đường kế hoạch, thông điệp truyền | Must | VIS-05, VIS-06 |
| R-VIS-05 | Tiêu thụ trạng thái của backend, tách khỏi FPS; không có đường UI→vật lý | Must | VIS-10 |
| R-VIS-06 | Bằng chứng hình ảnh từ frontend thật; đo hiệu năng; so sánh với ảnh tham chiếu | Must | VIS-07..09 |

### 12.2 Cổng vật lý PHY-01 … PHY-08
Mọi cổng PHY: test **tái lập được** (lệnh một dòng), **seed cố định** ghi trong file test, kết quả ghi vào manifest. Dung sai là `[PARAM]` và được khoá trước khi chạy.
| ID | Kiểm | Chuẩn đối chiếu | Tiêu chí PASS |
|---|---|---|---|
| PHY-01 | Tất định và độc lập khỏi wall-clock/FPS | Hai lần chạy cùng seed; chạy với `sleep` ngẫu nhiên tiêm giữa các bước; chạy `paced` vs `free-run` | SHA-256 telemetry trùng (cùng môi trường) |
| PHY-02 | Động học tuyến tính | `x=x₀+v₀t+½at²`, `v=v₀+at` | sai số vị trí ≤ 1e-6 m |
| PHY-03 | Quãng dừng, ma sát | Công thức đóng 07 §2 + tích phân tham chiếu bước nhỏ độc lập; lưới v₀∈{5,7,9,11} m/s × {êm, khẩn cấp} × μ∈{0.5, 0.8} | ≤ 1 mm so công thức; ≤ 5 mm so tham chiếu; kẹp ma sát đúng khi a>μg |
| PHY-04 | Lái và quay đầu | `R=L/tanδ`; hướng đổi `vt/R`; kẹp ma sát khi `v²tanδ/L>μg` | sai số hướng ≤ 1e-3 rad; bán kính ≤ 1 mm |
| PHY-05 | Giới hạn gia tốc/jerk/lái | Quét đầu vào cực đoan và ngẫu nhiên | 0 mẫu vượt `a_brk`, `j_max`, `δ̇_max`, `δ_max` |
| PHY-06 | Va chạm hình học và tương tác người đi bộ | Bảng ca giải tích (chạm mép, chồng lấn, tách rời, xoay) + ca tốc độ lớn nhất không xuyên thủng + ghi tốc độ va chạm | 0 sai trên bảng; không xuyên thủng |
| PHY-07 | Cảm biến: FOV, che khuất 2.5D, bất định | Biên FOV; `D=d·h_s/(h_s−h_o)`; thống kê nhiễu và `p_d(r)` | giải tích ≤ 1 mm; thống kê χ² 95% |
| PHY-08 | Truyền thông và độ tươi | Lịch xác định → AoI tính tay; thống kê trễ/mất/jitter | AoI khớp chính xác; thống kê trong dung sai |
Mọi PHY phải **PASS** trước khi kết quả thí nghiệm nào được công bố. PHY vi phạm = kết quả thí nghiệm bị vô hiệu.

### 12.3 Cổng trực quan VIS-01 … VIS-10
| ID | Kiểm | Cách kiểm | Tiêu chí PASS |
|---|---|---|---|
| VIS-01 | Đủ danh mục đối tượng 3D | `window.__inventory` (đếm theo loại từ scene graph thật): đường, vạch, zebra, vỉa hè, ≥3 kiểu toà nhà, ≥2 loài cây, đèn tín hiệu, ≥4 loại đồ đường phố, CCTV, AV, người đi bộ, xe tải | đạt tối thiểu theo cấu hình; 0 đối tượng bắt buộc là sprite 2D |
| VIS-02 | Camera | Playwright: 4 chế độ, orbit/zoom/follow | chuyển liên tục (bước dịch/khung ≤ ngưỡng), follow giữ ego trong khung |
| VIS-03 | Ánh sáng và bóng nhất quán | Một đèn định hướng chính; so ảnh bật/tắt bóng tại vùng dưới xe/xe tải/người | chênh lệch điểm ảnh vượt ngưỡng ở vùng dự kiến; đánh giá thang "nhất quán" |
| VIS-04 | Bánh xe quay đúng vật lý | Đọc góc quay bánh từ scene graph tại hai `t_sim`; so với `v/r_w` và góc lái δ | sai số ω ≤ 2%; góc lái bánh trước khớp δ |
| VIS-05 | Che khuất nhất quán với backend | So đỉnh polygon vùng khuất vẽ ra với polygon backend; trong camera Vehicle, mặt nạ điểm ảnh của người đi bộ ≈ 0 khi backend nói bị che | polygon ≤ 1 cm; mặt nạ khớp |
| VIS-06 | Lớp cooperative gắn dữ liệu | Số track = telemetry; trục elip = trị riêng covariance (2σ) ≤ 1%; góc FOV = tham số cảm biến; đường kế hoạch = đầu ra planner | khớp tất cả |
| VIS-07 | Hiệu năng **đo được** | Giao thức 07 §10.8: p50/p95/p99 khung, FPS, draw call, tam giác, bộ nhớ, trên máy tham chiếu đã khai báo | đạt ngân sách đã khoá; số đo sandbox gắn nhãn "không đại diện" |
| VIS-08 | So sánh với ảnh tham chiếu | Khung hero ghép cạnh ảnh; thang đánh giá cấu trúc 0–2 bởi ≥2 người | điểm ≥ ngưỡng chủ việc đặt sau khi có ảnh. **BLOCKED**: ảnh chưa được nhận |
| VIS-09 | Ảnh chụp từ frontend đang chạy thật | Playwright + backend thật; manifest (commit, hash build, renderer, độ phân giải, seed, `t_sim`); ≥ khung hero, Vehicle, CCTV, Bird's-eye, overlay tại 3 thời điểm chốt | đủ bộ ảnh và manifest hợp lệ |
| VIS-10 | Tách khỏi FPS, UI không điều khiển vật lý | Giới hạn render 5/30/60 FPS và tắt render → cùng telemetry; gửi thông điệp cấm từ UI | hash trùng; thông điệp cấm bị từ chối + ghi log |

### 12.4 Chấp nhận sản phẩm cuối
`PHY-01..08 PASS ∧ VIS-01..10 PASS ∧ AC-M01..M22 PASS ∧ giới hạn công bố`. Thiếu một vế = **không chấp nhận**. "Frontend đẹp nhưng vật lý sai" thất bại; "vật lý đúng nhưng hình ảnh kém rõ rệt so với mức mục tiêu" thất bại.
