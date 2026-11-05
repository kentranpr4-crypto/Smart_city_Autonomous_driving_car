# 10 · WP5 — An toàn vòng kín & lập kế hoạch có hợp tác: ODD, kiến trúc, đặc tả supervisor, kịch bản, giả thuyết đăng ký trước

Trạng thái: **WP4 được chấp nhận về kỹ thuật (kết quả nghiên cứu hỗn hợp được giữ nguyên)**; chỉ làm WP5 (không thành phố 3D, không huấn luyện mô hình, không triển khai thực). Tài liệu này + `closedloop/preregistration.json` + `closedloop/conditions.py` được **commit trước mọi mã planner/supervisor**. Mọi thay đổi sau đó ghi ở §10 (kèm lý do). Mốc đóng băng cuối (hash) ghi ở §11 trước khi chạy đánh giá cuối.
**Không khẳng định an toàn ngoài đời thực.** Mô phỏng hữu hạn, cảm biến thống kê, người đi bộ không phản ứng, một địa hình. "0 va chạm" trong thí nghiệm hữu hạn không chứng minh an toàn.

## 1. Câu hỏi nghiên cứu
Nhận thức hợp tác có tạo **cải thiện đo được về an toàn vòng kín** so với ego-only danh định (E0-N) **và** ego-only thận trọng (E0-C) không? Điều kiện nào thông tin hợp tác gây **phanh có hại, vật cản ma, nguy cơ va chạm đuôi, hoặc điều khiển mất ổn định**? An toàn được đo **độc lập với RMSE ước lượng**.

## 2. ODD (phạm vi mà kết quả được phép áp dụng — và không hơn)
Đường đô thị thẳng khô (μ=0.8, phẳng); ego 6.5–9.0 m/s (trần 11.1 m/s); người đi bộ trưởng thành 1.1–1.6 m/s, **động học, không phản ứng**; một xe tải đỗ (9.0×2.4×3.0 m) che người đi bộ; tối đa một CCTV (h=6 m), một xe V2V đỗ có camera, một xe theo sau mô hình người lái (phản ứng 1.0 s, phanh 5 m/s²); trời quang. Ngoài ODD: không có kết luận.

## 3. Kiến trúc vòng kín
```
Local perception (ego_cam → Tracker 3-of-4)  ┐
Remote tracks (comm: TrackMsg → admission → store) ┤→ fusion.CooperativeFuser (B4/CI)
                                                    ↓
              Evidence/Trust Admission (planning/trust.py)  — mỗi hypothesis: local-supported | corroborated-remote | advisory-remote | rejected
                                                    ↓
              Risk Prediction (planning/risk.py)    — p_conflict, thời gian tới xung đột, a_req, precaution (người đi bộ gần làn)
                                                    ↓
              Safety Supervisor (planning/supervisor.py) — luật P1, trần giảm tốc theo độ tin cậy, nhận biết xe theo sau, fallback
                                                    ↓
              Local Motion Planner (planning/planner.py) — tốc độ dọc: cruise, trần tốc độ (E0-C: người đi bộ ảo sau vật che bản đồ), phanh
                                                    ↓
              Controller (planning/controller.py)   — a_des → a_cmd + mode comfort/emergency
                                                    ↓
              Authoritative physics backend (World.issue, trễ actuator 0.15 s)  → quan sát kế tiếp
```
Cùng backend, cùng seed kịch bản, **cùng bước điều khiển 10 Hz**, cùng phương pháp đánh giá cho mọi chính sách. Planner chỉ có điều khiển dọc (đi thẳng, **không tránh bằng lái**: giới hạn).

### 3.1 Chiến lược hợp nhất có bảo vệ (guarded hybrid)
- **B0 (local-only) là fallback**: không có dữ liệu từ xa hợp lệ ⇒ quyết định **giống hệt E0-N** (kiểm bằng hash quỹ đạo).
- **Remote-only** (không có bằng chứng cục bộ) chỉ cho **rủi ro bảo thủ**, sau khi qua validation (tuổi ≤ 0.5 s, không bị monitor cờ, bền ≥ 3 chu kỳ, `allowlist-only` — **không bao giờ coi là đã xác thực**).
- **B4 (CI)** khi tương quan chéo không biết và gán chéo có cơ sở (cụm có thành viên local+remote, không mơ hồ). **B3 chỉ khi** độc lập đã được chứng minh — **không bật trong WP5** (không có hiệu chuẩn độc lập); B3 chỉ xuất hiện trong ablation `naive`.
- **Mâu thuẫn chưa giải quyết** (gán chéo mơ hồ/cờ `ambiguous`/lớp xung đột): giữ **các giả thuyết riêng**, mỗi cái được xử lý ở mức tin cậy thấp nhất của nó; không hợp nhất.
- **Không dùng ground truth** ở suy luận/lập kế hoạch (kiểm bằng AST + chặn import + duyệt đồ thị đối tượng).

## 4. Đặc tả Safety Supervisor (R-CLP-02)
Đầu vào: gia tốc đề xuất của planner `a_prop`, tập hypothesis đã gắn mức tin cậy, trạng thái ego, đo phía sau (khoảng cách/tốc độ xe theo sau), tuổi bằng chứng. Đầu ra: `a_cmd`, `mode`, nhật ký lý do.
1. **P1 (bất biến)**: `a_cmd ≤ a_local` luôn đúng, với `a_local` = lệnh mà chỉ bằng chứng **cục bộ** sinh ra. Bằng chứng từ xa **chỉ được thêm phanh**, không bao giờ tăng tốc, không nới ràng buộc cục bộ, và **vắng mặt/mất/hết hạn ≠ trống**.
2. **Trần giảm tốc theo mức tin cậy**: local-supported ≤ 6.0 m/s²; corroborated-remote (≥2 nguồn độc lập danh nghĩa, bền) ≤ 6.0 m/s² nhưng bị ràng buộc theo xe sau; advisory-remote (1 nguồn) ≤ 3.0 m/s².
3. **Nhận biết xe theo sau**: lệnh giảm tốc do **từ xa** kích hoạt bị chặn ở `a_f` sao cho `vf·t_r + vf²/(2·a_fdec) ≤ g + v_e²/(2·a_f)` (xe sau phản ứng t_r=1.0 s, phanh a_fdec=5). Với nguy cơ **cục bộ** sắp xảy ra, ưu tiên người đi bộ nhưng **ghi sự kiện `follower_risk_accepted`** (đo được, không giấu).
4. **Mâu thuẫn hình học**: hypothesis từ xa-only nằm trong vùng ego có tầm nhìn thông thoáng (FOV, tầm, không bị vật che bản đồ) nhưng không có phát hiện cục bộ ⇒ hạ xuống "thận trọng": chỉ **trần tốc độ thận trọng** (4 m/s, giảm tốc ≤1.5 m/s²), không dừng. (Đây là thông tin âm dùng để **giảm leo thang phản ứng**, không để tăng tốc quá E0-N.)
5. **Watchdog/fallback**: dữ liệu từ xa hết hạn/không hợp lệ/bị loại ⇒ bỏ qua âm thầm là **cấm**: được đếm (`stale_or_invalid_remote_used` phải =0) và quyết định rơi về E0-N.
6. **Giảm tốc cực đại & jerk**: chế độ `comfort` (3.0 m/s², 2.5 m/s³) hoặc `emergency` (6.0 m/s², 10 m/s³) của backend. **Giới hạn đã biết**: khi phanh tới v=0 backend ép a→0 trong một bước (jerk dừng giật) — được **đếm như sự kiện đo được** (`standstill_jerk_discontinuity`), **không tuyên bố tuân thủ**.

## 5. Kịch bản (mọi chính sách chạy cùng seed)
S1 **hazard**: người đi bộ đứng sau xe tải, bước vào làn; thời điểm đến mép làn so với ego không phanh: `u ~ U(−0.5, 2.2)` s. S2 **control**: người đứng sau xe tải **không bao giờ** vào làn. S3 **ghost**: không có người đi bộ; (tuỳ chọn) nguồn từ xa gửi vật cản ma trong làn cách ego 25 m. +follower: thêm xe theo sau (khoảng cách 10–16 m).
Nhóm chính sách: **E0-N, E0-C, E1 (+V2V), E2 (+CCTV), E3 (+cả hai), E3naive (ablation gây hại)**; **E4** = E3/E3naive với kênh `degraded` + CCTV lệch (0.5,−0.3); **E5** = ghost (giả mạo nguồn allowlist, KF-3), id-churn, nguồn không tin cậy (bị admission loại); **E6** = rủi ro va chạm đuôi (hazard/ghost + xe theo sau). Bảng 26 điều kiện: `closedloop/conditions.py`.

## 6. Chỉ số (phía truth; gộp qua seed; **độc lập với RMSE**)
- **collision_rate** (ego↔người/vật cản), **follower_collision_rate** (xe sau↔ego), **impact_speed** (mức nghiêm trọng), **min_ttc_median_s** (TTC nhỏ nhất mỗi lượt, tính giả định vận tốc không đổi, trần 10 s), **near_miss_rate** (không va chạm nhưng khoảng cách tối thiểu < 1.0 m).
- **warning_lead_s** = thời điểm người đi bộ chạm mép làn − thời điểm bắt đầu phanh của ego (dương = phanh trước); **standoff_m** = khoảng cách ego–người khi dừng/qua.
- **unnecessary_intervention_rate**: lượt có sự kiện bắt đầu phanh (giảm tốc>1.0 m/s²) mà **phản chứng** (giữ tốc độ lúc đó, quỹ đạo người đi bộ thật) cho thấy không cần (khoảng cách tối thiểu ≥1.5 m); **hard_brake_rate** = lượt có giảm tốc >3.5 m/s².
- **max_decel_p95**, **max_jerk_p95**, **standstill_jerk_event_rate**; **rear-end**: follower_min_ttc_median, follower_collision_rate, follower_req_decel_p95.
- **completion_rate**, **completion_time**, **travel_time_penalty_s** (ghép cặp so với E0-N cùng seed trong cùng kịch bản).
- **remote_age_p95_s** tại thời điểm quyết định; **calibration_ece / brier** của `p_conflict` (kết cục: phản chứng giữ-tốc-độ có khoảng cách <0.5 m trong 3 s; các tick tự tương quan — giới hạn); **fallback_identical_fraction** (B_E3: hash quỹ đạo = H_E0N); **decision_latency_p95_ms** (đồng hồ tường phía đánh giá).

## 7. Cổng mới CLS-01 … CLS-10 (không đổi PHY/COM/FUS/VIS)
| ID | Tiêu chí quan sát được |
|---|---|
| CLS-01 | Trust admission: mức tin cậy đúng; không bao giờ `authenticated`; hết hạn/không hợp lệ/mâu thuẫn không ảnh hưởng điều khiển |
| CLS-02 | Risk prediction: công thức đóng, Monte Carlo, bảo thủ ở worst-case, hiệu chuẩn trên ca tổng hợp |
| CLS-03 | Supervisor: P1 (không bao giờ tăng so với local), trần theo tin cậy, nhận biết xe theo sau, ghi sự kiện |
| CLS-04 | Planner/controller: bám tốc độ, chọn mode, công thức quãng dừng, trần tốc độ E0-C |
| CLS-05 | Tích hợp vật lý: cùng backend/dt/bước điều khiển/seed cho mọi chính sách; thời điểm lệnh; tất định |
| CLS-06 | Cô lập truth: AST + chặn import + đồ thị đối tượng cho `planning/` |
| CLS-07 | Fallback: không có dữ liệu từ xa ⇒ quỹ đạo giống hệt E0-N; dữ liệu stale/loại ⇒ không ảnh hưởng |
| CLS-08 | Evaluator đúng trên ca tổng hợp biết đáp án (TTC, near-miss, phản chứng, hiệu chuẩn, jerk, severity) |
| CLS-09 | Phân loại hỏng hóc/tấn công (ghost, id-churn, nguồn không tin cậy, rear-end) xử lý đúng ở mức đơn vị |
| CLS-10 | Toàn vẹn giao thức: hash đăng ký + mốc đóng băng; seed tuning∩eval=∅; evidence cuối đầy đủ; replay bit-giống |

## 8. Yêu cầu (R-CLP-xx) ↔ PRD
| ID | Yêu cầu | Liên hệ PRD |
|---|---|---|
| R-CLP-01 | Planner dọc đóng vòng với backend vật lý có thẩm quyền | R-PLN-01 |
| R-CLP-02 | Safety supervisor độc lập planner: P1, trần theo tin cậy, nhận biết xe sau | R-SAF-01 |
| R-CLP-03 | Fallback khi mất kênh: về E0-N (P1) | R-SAF-02 |
| R-CLP-04 | Hai ego-only song song cấu hình được: E0-N và E0-C | R-PLN-02 |
| R-CLP-05 | Đo an toàn độc lập RMSE ước lượng | R-SIM-03 |
| R-CLP-06 | Phân loại hỏng hóc/tấn công (ghost, id-churn, nguồn không tin cậy, rear-end) | — |
| R-CLP-07 | Giao thức đăng ký trước, tách seed, đóng băng, báo cáo giả thuyết bị bác bỏ | — |
AC-M11..M15 **chỉ phủ một phần** (không lái né, không P2).

## 9. Giao thức
Seed tuning 20261401–15 (gỡ lỗi + chỉnh tham số chính sách **chỉ ở đây**); seed đánh giá 20261501–40 (chạy **một lần** sau đóng băng). Chỉnh tham số sau đăng ký phải ghi §10 **trước** khi đóng băng. Mọi điều kiện, mọi chính sách chạy trên cùng cấu hình vật lý (WI-8). Thống kê: tỉ lệ + khoảng Wilson 95%; chênh lệch ghép cặp bootstrap; ngưỡng đánh giá trên ước lượng điểm; **không hiệu chỉnh đa so sánh** (36 ngưỡng).

## 10. Thay đổi SAU đăng ký
| # | Thay đổi (TRƯỚC khi đóng băng; chưa seed đánh giá nào được dùng) | Lý do / bằng chứng (seed tuning 20261401–15 + seed hiệu chuẩn kịch bản 20261601–40, chỉ chạy E0-N cho hiệu chuẩn độ khó) |
|---|---|---|
| 1 | ODD/kịch bản: người đi bộ 1.1–1.6 → **1.4–2.2 m/s** (đi nhanh/chạy bộ); ego 6.5–9.0 → **7.5–10.0 m/s**; lead `u` ∈ (−0.5, 2.2) → **(−0.5, 1.5)**; `ped_worst_speed` 1.6 → 2.2 | E0-N chỉ va chạm **7%** (< ngưỡng hợp lệ W-V1 ≥ 0.25) vì phanh đủ sớm; sau chỉnh: 32.5% (40 seed hiệu chuẩn), 33% (15 seed tuning). Chỉ E0-N được dùng để hiệu chuẩn độ khó |
| 2 | `DURATION` 13 → **18 s** | hoàn thành chậm bị kiểm duyệt ở 13 s, làm hỏng phép đo travel-time |
| 3 | Thêm `creep_speed=2.5 m/s` (sàn của trần tốc độ worst-case) và luật "beside" của risk (đối tượng đã ngang/sau cản trước không tính xung đột tương lai) | Tuning: ego dừng hẳn cạnh người đứng chờ (p≈0.2 từ bất định vận tốc trên 6 s) → không hoàn thành (control goal 0–7%) |
| 4 | Self-track: so với **tư thế của ego tại thời điểm quan sát từ xa** (lịch sử tư thế) + `self_radius_m=3.0` (mã `fusion/fuser.py`, WP4); `comm/network.py` bỏ qua AoI cho tin nhắn tiêm (không có chú thích mô phỏng) | Tuning: camera từ xa thấy **chính xe ego** đang phanh gấp; ước lượng CV của xe trễ 0.6–1.5 m → vượt cổng Mahalanobis → ego tự coi mình là vật cản "corroborated" và phanh 6 m/s². Tiêm tin giả được chấp nhận làm sập meter AoI đánh giá. Test FUS/COM cũ chạy lại: pass |
| 5 | Supervisor: vật thể từ xa-only "mâu thuẫn" cách < 12 m **không còn bị bỏ qua** mà thành giả thuyết advisory (phanh êm tối đa); cờ `follower_risk_accepted` tính cả khi hazard cục bộ | Bỏ qua hoàn toàn có thể loại bỏ một người thật mới vào tầm nhìn khi tracker cục bộ chưa xác nhận; test bắt lỗi cờ không bao giờ phát |
| 6 | Kẻ tấn công: ghost kiểu 1 (luôn cách ego 25 m, "bóng") **giữ lại làm điều kiện báo cáo GF_* (không có giả thuyết)**; ghost chính thức = **xuất hiện đột ngột ở t=5 s cách trục sau 14 m rồi đứng yên**. Khoảng cách xe sau (10,16) → **(6,11) m** | Tuning: ghost kiểu 1 chỉ làm ego bò chậm (naive không phanh gấp, +7.6 s) và xe sau không va chạm ở 10–16 m. Thiết kế kẻ tấn công sau khi thấy kết quả naive — **ghi rõ đây là thiết kế đối kháng có chủ đích**, không phải đo ngẫu nhiên |
| 7 | **Không đổi**: `p_thr=0.05`, `horizon_s=6.0`, mọi ngưỡng và giả thuyết | Quét p_thr∈{0.1…0.7} và horizon∈{3,4} trên seed tuning: giá trị lớn/ngắn hơn làm **E0-N/E3 va chạm nhiều hơn** (0.13–0.80); giữ giá trị khai báo a priori |
| 8 | Quan sát tuning còn lại (không sửa): W-7/W-8 có vẻ bị bác bỏ (E3 chậm hơn E0-C trong control; mọi chính sách "can thiệp không cần thiết" ở ngưỡng −1 m/s² vì nhiễu vận tốc tracker làm ngay cả E0-N phanh nhẹ với xe đỗ) | giữ nguyên, báo cáo như kết quả |
| 9 | Mutation: 8/34 mutant planning sống sót lần đầu (2 tương đương: bao `min` P1 và kẹp lệnh cuối thừa theo cấu trúc; 6 lỗ hổng test thật → thêm 6 test; kẹp lệnh được test bằng cấu hình sai) | `evidence/wp5/mutation/` |

## 11. Mốc đóng băng
_(sẽ ghi: commit, cây băm mã, trước khi chạy đánh giá cuối)_

## 12. Mã băm đăng ký
`closedloop/preregistration.json` sha256 = `7c6aca4a1b015a1e2ffe08e5e60475760f29d1401d9f5566b27d376af3b33c9c`; `closedloop/conditions.py` sha256 = `ed2e77774e05b648081de528b4781103e20e19ab61f1d4dea55b89d4057a6d0c`. (Phiên bản đăng ký GỐC: commit `76f1f2a`, prereg `98ddf13c…`, conditions `efaef1e1…`.)
