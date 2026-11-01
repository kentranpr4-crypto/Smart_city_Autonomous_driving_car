# WP2 — Cảm biến 2.5D, che khuất, nhiễu, timestamps, tracker; tách ground truth khỏi quan sát

**Trạng thái: PASS cho PHY-07, AC-VS-03, AC-VS-06 và bộ test association/stale/occlusion/failure-mode; PHY-08 vẫn NOT_CHECKED (WP3); VIS-08 vẫn BLOCKED.** Ngày 2026-11-01. Không huấn luyện mô hình, chưa dựng thành phố. Refinery/provenance không đổi (REG-1/2/3 PASS).
Văn bản đối chiếu với định nghĩa chuẩn của PRD (và danh sách các thay đổi thực hiện *sau khi thấy kết quả*): `PHY07-08-reconciliation.md`.

## Mã nguồn chạy được
**Phía truth (được phép đọc ground truth):** `backend/truth.py` (kiểu truth) · `backend/sensor_spec.py` · `backend/sensors.py` (hình học 2.5D, mô hình đo, `SensorProvider`, `FrameLabels` chỉ cho metric) · `backend/rig.py` (World → cảm biến → hàng đợi `t_avail` → tracker) · `backend/rng.py`.
**Ranh giới (dữ liệu thuần):** `backend/observation.py` (`Detection`, `SensorFrame`).
**Phía perception (KHÔNG được chạm truth):** `perception/{stats,hungarian,tracker}.py`.
**Cảnh/scenario:** `scenarios/s01w2_occlusion_rig.yaml`; schema scenario mở rộng (`sensors`, `height`).
Chạy: `make test` · `make check` · `.venv/bin/python scripts/physics_bites.py` · `.venv/bin/python scripts/make_wp2_evidence.py`.

## Thiết kế đáng chú ý
- **Che khuất 2.5D:** tia từ cảm biến (độ cao h_s) tới ba điểm mẫu của mục tiêu (chân/thân/đầu); bị chặn nếu đi qua lăng trụ (đáy OBB × chiều cao h_o) tức độ cao tại điểm vào/ra < h_o. Bóng trên mặt đất là bao lồi của đáy và đỉnh được chiếu từ cảm biến (hệ số h_s/(h_s−h_o)).
- **Ghép cặp seed:** số ngẫu nhiên tiêu thụ cho mỗi mục tiêu cố định, không phụ thuộc nhìn thấy hay không; thêm vật che không làm lệch nhiễu của mục tiêu khác (có test bắt đúng lỗi này).
- **Timestamps:** mỗi frame có `seq`, `t_meas` (mốc lấy mẫu), `t_avail = t_meas + t_proc`; outage tạo khoảng trống `seq` quan sát được; tracker nhận frame theo `t_avail`.
- **Cô lập I9:** tracker chỉ nhận `SensorFrame`. Nhãn truth (`FrameLabels`) nằm ở rig để tính metric và không bao giờ đi vào tracker.
- **Tracker:** Kalman vận tốc không đổi, cổng Mahalanobis 99.9%, gán tối ưu (Hungarian), xác nhận M/N (mặc định 2/3), điểm tồn tại kiểu SPRT (heuristic, **chưa hiệu chuẩn**), hết hạn theo thời gian, loại track trùng, kiểm tra frame (11 lý do từ chối khác nhau), giám sát nhất quán NIS.

## Acceptance criteria và kết quả
| Cổng / tiêu chí | Kết quả | Evidence (thực chạy) |
|---|---|---|
| **PHY-07** (55 test) | **PASS** | Biên FOV chính xác tới 1e-9 rad; biên tầm trong 1 mm; bóng `D=d·h_s/(h_s−h_o)`: 30 ca, sai số lớn nhất **1.4e-14 m** (tiêu chí 1 mm), gồm vật cản mỏng/dày và h_s ≤ h_o (bóng vô hạn); đa giác bóng = kết quả tia trên 8000 điểm (0 sai lệch ngoài dải 1 mm); nhiễu χ² hai phía 95% ở 3 tầm (4143.1 ∈ [3826.6, 4177.2], percentile 94.4%), không thiên lệch, x–y độc lập; `p_d(r)` Pearson χ²=**5.00** < 12.59 (df 6) với công thức logistic độc lập; clutter Poisson + đồng đều theo góc và diện tích; lịch/phase/timestamps chính xác tuyệt đối; outage đúng tần suất dừng; ghép cặp seed bit-giống |
| **AC-VS-03** tracker nhất quán (7 test) | **PASS** | M=100 × K=60: 98% bước nằm trong khoảng χ²(400) 95%; ANEES theo thời gian **3.958** (kỳ vọng 4); NIS **1.994** (kỳ vọng 2). **Test của test:** σ_a nhỏ 10× → ANEES 35.7 (FAIL đúng); cov khai báo 0.5× → ANEES 22.6, NIS 4.42 (FAIL đúng) |
| **AC-VS-06 / I9** cô lập truth (15 test) | **PASS** | AST: `perception/` chỉ import whitelist + `backend.observation`; không tham chiếu định danh truth; tracker chạy trong **tiến trình mà mọi module truth-side bị chặn import** (control: `import backend.world` bị chặn) cho **cùng hash** kết quả với chạy bình thường; rig chỉ truyền `SensorFrame`; sau khi chạy, đồ thị đối tượng của tracker không chứa đối tượng truth-side nào |
| Association (test) | **PASS** | Hungarian = brute force trên 300 ma trận ngẫu nhiên; giao cắt vuông góc cách 1.77 m: 0 ID switch / 20 seed; hai người song song 2 m: 0 / 20; p_d=0.7: ≥ 98% frame có track; độ trễ xác nhận đúng M−1 frame; detection ngoài cổng không bị gán |
| Stale / dữ liệu không hợp lệ (test) | **PASS** | 16 ca (11 lý do khác nhau) bị từ chối đúng lý do (replay, out-of-order, future, stale, sai sensor, schema, NaN/Inf, cov âm/không xác định dương, trùng id, `t_avail<t_meas`, ngoài miền) và **không đổi trạng thái**; track hết hạn theo thời gian; hiệp phương sai chỉ tăng khi coasting; fuzz 250 ví dụ không crash, P luôn đối xứng bán xác định dương |
| Che khuất → coasting → tái bắt (test) | **PASS** | Che 0.96 s: track giữ ID, cov tăng đơn điệu, điểm giảm, bắt lại đúng vị trí; che 4.3 s: track bị bỏ sau 1.5 s, ID mới khi xuất hiện lại |
| Failure modes (test) | **PASS** | Outage: mọi frame mất được tính đúng (`seq_gaps = last_seq+1−frames_ok`), coverage ≥ 0.95; clutter 10/frame: coverage ≥ 0.95; sensor quá tự tin (khai 0.3× σ) bị đánh dấu 20/20, sensor đúng 0/20 báo động giả; nhãn lớp bằng bỏ phiếu đa số |
| Tích hợp rig `s01w2` | **PASS** | Ego bắt đầu thấy ở sensor x = **39.65 m**; frame trước 39.05 m còn bị che; biên giải tích **39.5 m** nằm giữa. Khi bị che ego không phát hiện và không có track; CCTV thấy từ đầu; CCTV có track lúc t=0.18 s, ego lúc 6.45 s (**dẫn trước 6.27 s**); gắn rig không làm đổi hash vật lý |
| Regression dừng xe / jerk (12 test PHY-05) | **PASS (có giới hạn nêu rõ)** | Dừng gấp: jerk tương đương **600 / 300 m/s³** ≫ giới hạn, được **báo bằng sự kiện** `standstill_jerk_discontinuity` (không còn là ngoại lệ ngầm); soft-stop (phanh nhả về 0 khi v→0) đạt giới hạn jerk ở **mọi** bước, dừng đúng vị trí công thức đóng ≤ 1e-6 m; trạng thái đứng yên đóng băng; khởi động lại đúng giới hạn |
| Mutation bites | **PASS** | **35/35** lỗi tiêm vào bị bắt (12 vật lý + 2 dừng xe + 9 cảm biến + 12 tracker/cô lập). Hai mutant ban đầu sống sót (`p_d` tautology, kênh ngầm nhãn truth) → thêm test độc lập công thức `p_d` và quét đồ thị đối tượng |
| Selftest checker tài liệu | **PASS** | 6/6 lỗi tiêm vào bị bắt |
| **PHY-08** | **NOT_CHECKED** | Kênh/AoI thuộc WP3; những gì WP2 có (timestamps, seq gap, từ chối dữ liệu cũ) là tiền đề, **không** được tính là bằng chứng PHY-08 |
| **VIS-08** | **BLOCKED** | `docs/references/` chưa có file ảnh gốc |

Tổng: `make check` = **18 PASS, 0 FAIL, 1 BLOCKED, 10 NOT_CHECKED**; 236 test.

## Metric đo được (không có ngưỡng; chỉ báo cáo) — `evidence/wp2/metrics.json`
| Metric | Giá trị |
|---|---|
| Giao cắt, khoảng cách gần nhất 0.71 m | 0/100 seed có ID switch |
| Giao cắt, đường va chạm (0.00 m) | **70/100 seed** có ≥ 1 ID switch (265 lần) |
| Hai người song song 0.4 m | 17/100 seed có ID switch; trung bình 1.19 track (**hai mục tiêu thật bị gộp**) |
| Track giả xác nhận / frame (λ = 2 clutter/frame, 4000 frame) | 2-of-3: **0.0465** (ước lượng giải tích 0.029); 3-of-4: **0.0015** |
| Thông lượng | rig 11 s mô phỏng chạy trong 0.13 s (~84× thời gian thực, 2 cảm biến) |

## Phát hiện trong quá trình làm (nêu thẳng)
1. **Test AC-VS-03 đã đăng ký trước FAIL** lần chạy đầu (ANEES 4.51; 52% bước trong khoảng). Nguyên nhân chính là **track trùng làm đói track gốc** sau khi một detection đúng bị cổng 99% loại; phần còn lại là thiên lệch do cắt cổng (+0.14). Sửa tracker (cổng 99.9% + khử trùng), **giữ nguyên tiêu chí**, ghi lại thành test đặc trưng. Mô tả nguyên nhân ban đầu của tôi ("chỉ do cắt cổng") **chưa đầy đủ** và đã được đính chính sau phép đo thứ hai.
2. **Lỗi thật trong tracker:** track quá hạn "sống lại" và nuốt detection mới (hết hạn chỉ xảy ra sau bước liên kết). Đã sửa, có regression test.
3. **Lỗi thật trong cảm biến:** xáo thứ tự detection bằng `rng.permutation` làm lệch nhiễu của mục tiêu khác khi thêm vật che, trái với tuyên bố của chính docstring. Test ghép cặp bắt được; đã sửa.
4. Ba lỗi **của test** do tôi viết: ma trận Q hạng 2 không Cholesky được; mẫu số coverage tính cả frame sau khi mục tiêu ra khỏi FOV; tiền điều kiện hình học crossing sai (1.06 m thay vì ≥ 1.2 m). Đã sửa định nghĩa/hình học, **không nới ngưỡng**.
5. Hình học scenario tích hợp lần đầu **không che được ego**; dựng lại theo biên giải tích.
6. Bằng chứng hình: `evidence/wp2/occlusion_rig_topdown.svg` — lần vẽ đầu bị tràn khung và bị vòng tròn pedestrian che mất detection; đã vẽ lại. Vòng cam trên thân ego là CCTV theo dõi chính xe ego (mục tiêu hợp lệ).

## Known limitations
1. **Cảm biến là mô hình thống kê trên ground truth**, không phải detector thật (R-PER-03): nhiễu Gaussian độc lập, miss độc lập (chỉ outage cấp frame có cụm), không thời tiết/méo/rolling shutter, không che khuất từng phần làm giảm `p_d` (nhị phân theo 3 điểm mẫu), người đi bộ không che nhau, FOV/tầm tính theo tâm mục tiêu. Mọi tham số (σ, `p_d`, h_s, chiều cao xe tải 3 m…) là `[PARAM]` **không có nguồn** (D04, D05).
2. **Bias hằng số vô hình với tracker một nguồn** (có test ghi nhận): tracker báo NIS khoẻ trong khi track lệch đúng bằng bias. Phát hiện cần nguồn thứ hai (WP3/WP4); đây là FM08.
3. **Tracker:** chỉ mô hình vận tốc không đổi; **mất danh tính sau che khuất dài hơn `max_coast_s`** (không re-ID); khử trùng **gộp nhầm hai mục tiêu thật đi sát nhau** (17% seed ở 0.4 m); giao cắt trên đường va chạm gây ID switch (70% seed); mặc định xác nhận 2/3 cho độ trễ thấp nhưng **track giả 4.65%/frame ở λ=2** (3/4 thấp hơn 30× nhưng chậm hơn một frame) — cần chủ việc chọn; điểm tồn tại là heuristic, không phải xác suất (D04).
4. Một đồng hồ mô phỏng, chưa có offset/drift (WP3, B04); frame out-of-order bị **từ chối** chứ không xử lý OOSM; chưa có hợp nhất đa nguồn hay validator mâu thuẫn quan sát (WP3/WP4).
5. Gate thống kê dùng **một seed cố định**; ba test nhiễu theo tầm dùng chung seed nên cùng z-score (kiểm tỉ lệ σ(r), không phải ba mẫu độc lập). Hiệu chuẩn bài test qua 60 seed: 98.3% nằm trong khoảng 95% (báo cáo, không phải gate).
6. Các ngưỡng association/tracker (0 ID switch trong 20 seed, coverage ≥ 0.95, v.v.) **do tôi đăng ký trước**, không nằm trong PRD.
7. Giới hạn dừng xe của WP1 (jerk tại v=0) được báo bằng sự kiện nhưng mô hình vẫn **không thể bảo đảm** jerk khi phanh tới v=0; chỉ soft-stop do bộ điều khiển mới đạt.
8. Chưa có telemetry perception trong file vật lý (log perception có hash riêng); schema scenario bị định dạng lại (diff 511 dòng, thay đổi ngữ nghĩa nhỏ).

## Diff
Xem `evidence/wp2/diff_stat.txt`: các file đã theo dõi bị sửa (chủ yếu `backend/{dynamics,world,scenario,params}.py`, schema, `check_repo.py`, `physics_bites.py`, golden, 1 test PHY-05, bằng chứng WP1 tái tạo, và các tài liệu 05/06/07 + báo cáo WP1) cùng các file mới (`backend/{observation,rig,rng,sensor_spec,sensors,truth}.py`, `perception/`, `tests/perception/`, `tests/physics/test_phy05_standstill.py`, scenario, `scripts/make_wp2_evidence.py`, tài liệu và bằng chứng WP2). Registry/`data/`/`.claude/` không đổi.
Thay đổi hành vi vật lý duy nhất: thêm sự kiện `standstill_jerk_discontinuity`; kết quả vật lý bit-giống trước (S00a x_final = 13.613703703703715). Hash golden đổi `ce9dc616…` → `5876d26c…` do header có thêm `height`, sự kiện mới và danh sách hạn chế.
