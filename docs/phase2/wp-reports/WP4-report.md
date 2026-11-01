# WP4 — Hợp nhất nhận thức cộng tác có tính bất định (cooperative perception & uncertainty-aware fusion)

**Trạng thái: DONE cho cổng kỹ thuật (FUS-01..10 PASS, 6/6 invariant PASS) — kết quả nghiên cứu là HỖN HỢP.** 24/27 giả thuyết đăng ký trước được ủng hộ, **3 bị bác bỏ** (H1a, H4a, H6b), 8 known failure còn nguyên. Nếu người duyệt coi giả thuyết là tiêu chí chấp nhận, hãy đọc WP4 là **PARTIAL**: tôi không tự quyết định điều đó. Mọi kiểm tra là **tự kiểm** (cùng tác nhân viết và kiểm). Ngày 2026-11-01. Không WP5, không thành phố, không planner vòng kín. VIS-08 vẫn BLOCKED.

> **Ba mức khẳng định khác nhau — đừng gộp:**
> 1. **Đúng số học** (phép biến đổi, lan truyền cov, CI, gán tối ưu): được kiểm bằng test đóng + Monte Carlo độc lập + 36 mutant. 
> 2. **Nhất quán thống kê** (NEES/coverage, ANEES): đo trên mô phỏng 30 seed × 21 điều kiện; nói về *độ tin cậy của hiệp phương sai khai báo*, không phải sai số tuyệt đối.
> 3. **Cải thiện an toàn thực tế**: **KHÔNG được chứng minh và KHÔNG được tuyên bố.** Không có điều khiển vòng kín, không có đo va chạm/khoảng cách phanh, cảm biến là mô hình thống kê, truth là mô phỏng. Availability/RMSE tốt hơn ≠ lái xe an toàn hơn (F09 UNKNOWN).

## 1. Mã nguồn và kiến trúc
`fusion/` (thuần dữ liệu; **không** import backend/comm/random/time): `model.py` (CV + Q DWNA, bất định timestamp), `transform.py` (SE(2) + cov của phép biến đổi), `associate.py` (Hungarian 4-D Mahalanobis, cổng χ²₉₉.₉(4)=18.4668, ràng buộc lớp, cờ mơ hồ), `combine.py` (naive / thông tin / CI min-vết, golden-section tất định, CI tuần tự), `fuser.py` (`CooperativeFuser`: kiểm tra đầu vào, dự báo về cùng thời điểm từ **`t_meas` gốc**, sổ bằng chứng `(origin, orig_seq, track_id)`, gom cụm, ID bền, triệt tiêu self-track, cách ly nguồn), `monitor.py`, `identity.py` (giao diện xác thực), `adapters.py`, `types.py`. Đầu ra `WorldState` bất biến, không có bề mặt planner. `experiments/` (phía truth: cảnh, harness, bộ đánh giá). `comm/store.py` mở rộng nhẹ (`StoredTrack.orig_seq/relay_path`, mặc định giữ nguyên WP3 test).

## 2. Cổng (`make check`: 40 PASS, 0 FAIL, 1 BLOCKED, 9 NOT_CHECKED; mọi COM/PHY/VIS cũ không đổi định nghĩa)
| Cổng | Kết quả | Evidence |
|---|---|---|
| FUS-01 căn thời gian (5) | PASS | Q/F = tracker đến 1e-15; dùng `t_meas`; từ chối future/stale/horizon; adapter giữ `t_meas` |
| FUS-02 lan truyền cov (4) | PASS | công thức đóng; **mô phỏng độc lập định nghĩa mô hình** NEES≈4; phát hiện σ_a sai; *phát hiện: Q là DWNA, không hợp thành* (ghi trong test) |
| FUS-03 SE(2)+cov (5) | PASS | Jacobian = sai phân hữu hạn; nghịch đảo/hợp thành; MC nhất quán có bất định biến đổi; bỏ qua bất định → quá tự tin (test của test) |
| FUS-04 gán không truth (8) | PASS | tối ưu = brute force; cổng; lớp; mơ hồ; id nguồn không va chạm; 0.4 m bị cờ mơ hồ (KF-1/6) |
| FUS-05 B0..B4 (14) | PASS | công thức đóng; CI nhất quán ρ∈{0,.5,.9,1}; **B3 quá tự tin ở ρ=1** (NEES≈8); CI = tối ưu vết trên lưới 201 điểm |
| FUS-06 provenance (5) | PASS | bản trùng/relay chỉ dùng 1 lần; relay gắn cờ; echo đổi nhãn **không** phát hiện được (KF-8) |
| FUS-07 stale/mâu thuẫn/thiếu/sai (12) | PASS | 10 mã lý do (kể cả `self_track`); fuzz 250: luôn hữu hạn/PSD; mất remote → đúng bằng B0; vắng mặt ≠ trống |
| FUS-08 cô lập+tất định (14) | PASS | AST; tiến trình chặn import truth/comm/backend cho cùng hash; bất biến; replay độc lập thứ tự |
| FUS-09 monitor + xác thực (7) | PASS | báo động giả/phát hiện đúng thiết kế; hysteresis; **xác thực fail-closed; không đường mã nào trả `authenticated`** ngoài test double |
| FUS-10 giao thức+evaluator (13) | PASS | hash đăng ký khớp; seed tuning∩eval=∅; metric đúng trên ca tính tay; reachability detector bắt đối tượng cài sẵn; replay bit-giống; evidence cuối đầy đủ |
| Mutation bites | PASS **36/36 fusion bị diệt**, 0 sống sót, 0 timeout, 0 tương đương | §6 |
| Known failures | PASS (8 còn thất bại đúng khai báo) | KF-1..5 cũ + KF-6 gán sai ở 0.4 m, KF-7 bias không khai → track ma, KF-8 echo đổi nhãn |
| Invariant FI-1..6 trên 30 seed | **6/6 PASS** | không NaN/PSD sai; 0 dùng bằng chứng đôi; tuổi remote lớn nhất 0.46 s ≤ 0.5; 0 replay lệch; 0 ngoại lệ; 0 đối tượng truth tới được từ fuser |

## 3. Đánh giá cuối (đăng ký trước; chạy MỘT lần; 30 seed 20261301–20261330; 21 điều kiện × 6 phương pháp)
Giao thức/ngưỡng đóng băng ở commit `13500d3` (sha256 `fusion/preregistration.json` = `600215ad…`, `experiments/conditions.py` = `f0108f59…`). Seed tuning 20261201–15 tách biệt, chỉ để gỡ lỗi. Kết quả gốc **giữ nguyên, kể cả bác bỏ**: `evidence/wp4/eval/{results.json, verdicts.md, eval_run.log}`.

**Phán quyết 33 ngưỡng:** FI-1..6 PASS · SUPPORTED: H1b–H1g, H2a–H2c, H3a–H3b, H4b–H4c, H5a*, H5b, H5c–H5d, H6a, H7a, H8a, H9a, H10, H11, H12 · **REFUTED: H1a, H4a, H6b**. (*H5a = 0.900 đúng bằng ngưỡng, 27/30 seed — ủng hộ sát biên.)
- **H1a bác bỏ:** B0 availability_occluded = 0.151 > 0.05, vì cửa sổ "ego không thấy" gồm cả lúc mục tiêu ra khỏi FOV và track cục bộ còn *coast* tới 1.5 s — định nghĩa cửa sổ của tôi rộng hơn "bị che".
- **H4a bác bỏ:** dưới echo (ρ=1) B3 có coverage95 = 0.957 (≥0.9) dù ANEES tăng 1.997→3.52. Nguyên nhân: tracker nền **bảo thủ** (ANEES≈2, không phải 4) nên gấp đôi NEES vẫn nằm trong vùng 95%. Xu hướng đúng, ngưỡng sai.
- **H6b bác bỏ:** skew −0.3 s làm B3 coverage 0.964 (≥0.9); chỉ B1 (remote-only) tụt rõ (0.810).

### 3.1 So sánh B0–B4 (pooled; RMSE m; cov = coverage95 của NEES 4-D; ANEES kỳ vọng 4, <4 = bảo thủ)
| Điều kiện | Avail B0→B4 | pos RMSE B0 / B1 / B2 / B3 / B4 | cov B3 / B4 | ANEES B3 / B4 |
|---|---|---|---|---|
| C1 bị che (nominal) | **0.425→0.969** | 0.205 / 0.130 / 0.129 / **0.120** / 0.130 | 0.996 / 0.997 | 1.82 / 1.76 |
| C0 đối chứng (cả hai thấy) | 0.980→0.980 | 0.204 / 0.217 / 0.149 / **0.148** / 0.204 | 0.996 / 0.999 | 1.88 / 1.99 |
| C4a echo ρ=1 | = | 0.204 / 0.224 / 0.205 / 0.203 / 0.204 | **0.957** / 0.999 | **3.52** / 2.00 |
| C5a bias 0.58 m không khai | = | 0.204 / **0.610** / 0.313 / 0.293 / 0.209 | **0.489** / 0.992 | **10.1** / 2.14 |
| C5b bias có khai (transform+cov) | = | 0.204 / 0.610 / 0.326 / 0.174 / 0.204 | 0.998 / 0.999 | 1.98 / 2.00 |
| C6a skew −0.3 s | = | 0.204 / 0.486 / 0.265 / 0.208 / 0.204 | 0.964 / 0.999 | 3.32 / 2.00 |
| C6c skew +0.1 s | = | 0.204 / 0.253 / 0.161 / 0.161 / **0.237** | 0.973 / **0.955** | 2.90 / **3.47** |
| C6d skew +0.3 s | = (0 remote nhận) | 0.204 / — / = / = / = | = | = |
| C7a link degraded | 0.425→0.955 | 0.205 / 0.147 / 0.142 / 0.136 / 0.147 | 0.997 / 0.998 | 1.71 / 1.65 |
| C7b link severe | 0.425→0.841 | 0.205 / 0.172 / 0.163 / 0.161 / 0.171 | 0.997 / 0.999 | 1.68 / 1.65 |
| C8b relay 1 hop (direct severe) | 0.425→0.969 | = C1 | | |
| C9b blackout remote khi bị che | 0.425→0.702 | 0.205 / 0.144 / 0.139 / 0.129 / 0.143 | 0.993 / 0.995 | 1.94 / 1.87 |
Khoảng tin cậy bootstrap 95% (theo seed) của pos RMSE: C1 B0 [0.192, 0.218], B3 [0.116, 0.124], B4 [0.126, 0.133]; C0 B0 [0.196, 0.211], B3 [0.142, 0.153], B4 [0.196, 0.211].

### 3.2 Nơi hợp nhất **cải thiện / không cải thiện / làm xấu đi** so với chỉ ego (B0)
| Loại | Điều kiện | Bằng chứng |
|---|---|---|
| **Cải thiện** | Bị che (C1, C7, C8b/c) | availability 0.425→0.84–0.97; thời gian tới track hợp lệ đầu tiên 4.7 s→0.3 s; vel RMSE 0.43→0.17; vẫn còn lợi ở link severe (0.84) và nhờ relay (0.97 vs 0.84 chỉ trực tiếp) |
| **Cải thiện** (chỉ B2/B3) | Cả hai thấy, độc lập (C0, C2b, C3b) | pos RMSE −27% (0.204→0.148) với B3; **B4 = B0** (CI không thu được lợi — đánh đổi lấy nhất quán) |
| **Không cải thiện** | echo/tương quan (C4), blackout khi ego tự thấy (C9a), skew +0.3 (C6d: remote bị từ chối hoàn toàn → = B0) | B4 RMSE = B0; B3 không tốt hơn nhưng *quá tự tin* (ANEES 3.5) |
| **Làm xấu đi** | Bias hằng không khai (C5a): B1 RMSE 0.61 (3×), B3 0.293 và coverage 0.49, B2 0.313; B2–B4 sinh **0.162 track ma/chu kỳ** (remote lệch tách khỏi cụm) | B4 giữ nhất quán (cov 0.992) nhưng **không cải thiện** và vẫn có track ma |
| **Làm xấu đi** | Skew +0.1 s (C6c): B4 RMSE 0.237 > B0 0.204, ANEES 3.47; B1 coverage 0.94 | dữ liệu *được chấp nhận* nhưng sai căn thời gian ~v·δ |
| **Làm xấu đi** | Hai người đi bộ cách 0.4 m (C2a): precision gán **0.496**; ID-switch 6.7/phút (B4) vs 3.5 (B0); failure rate 0.70 | KF-1/KF-6 |
| **Không cải thiện** | Giao cắt trên đường va chạm (C3a): ID-switch 18.5/phút (B4) vs 17.4 (B0), 80% seed cả hai | KF-2 |
| **Làm xấu đi (biến thể thêm)** | B4q (cách ly nguồn khi monitor báo động): **0.58 track ma/chu kỳ ở C2b**, 0.32 ở C3 | monitor báo động giả → tách một mục tiêu thành hai; **không khuyến nghị** B4q |

### 3.3 Chỉ số khác
- **Gán chéo nguồn (B4):** precision/recall — 0.4 m: **0.496/0.975**; 1.5 m: 0.997/0.995; giao cắt va chạm: 0.981/0.981; miss 1.77 m: 1.000/1.000.
- **Monitor:** bắt bias C5a trong 3 s ở 27/30 seed (0.90); báo động giả đối chứng C0 = 0/30 trong 3 s (bổ sung: 2/30 báo động bất kỳ lúc nào với warm-up 1 s; **với warm-up, phát hiện C5a chỉ 73%** — không dùng làm kết luận).
- **Stale/mất gói:** tuổi remote lớn nhất được dùng 0.46 s; không có dữ liệu stale nào lọt (FI-3); phục hồi sau blackout 0.49 s (P95).
- **Runtime:** B4 trung bình 0.65 ms, P95 **1.49 ms**/chu kỳ trên CPU sandbox (H11 P95 pooled 2.38 ms ≤ 5 ms) — **không** phải số đo Jetson. **Băng thông:** ~12–15 kB/s/nguồn JSON (24 kB/s khi thêm relay).
- **Failure rate theo điều kiện** (availability<0.5 của seed): B0 = 1.0 ở mọi điều kiện bị che; B4 = 0 ngoại trừ C2a (0.70).

## 4. Phát hiện trong quá trình làm (nêu thẳng)
1. **Chạy mutation đầu tiên báo "ALL CAUGHT" là SAI:** 6 mutant bị "diệt" chỉ vì test băm đăng ký fail trong bản sao (thiếu `docs/`). Sửa runner (sao chép `docs/phase2`), chạy lại: **5 mutant thực sự sống sót** — trọng số CI cố định 0.5, monitor không hysteresis, B0 đọc cả nguồn remote, adapter cộng tuổi vào `t_meas`, NEES chỉ dùng P[0,0]. Cả 5 là lỗ hổng test thật (không tương đương) → thêm 5 test (`ci_weight_is_the_trace_optimum…`, `monitor_stays_flagged_between…`, `b0_and_b1_do_not_even_look…`, `adapters_keep_the_original_observation_time…`, `nees_uses_the_full_covariance…`); chạy lại: **36/36 diệt**. (Mutant thứ 6 `evaluator_gate_ignored` bị diệt đúng bởi test evaluator.)
2. Q của tracker là DWNA, không hợp thành (test ban đầu của tôi sai) — đã ghi.
3. Trên seed tuning: 0.309 track giả/chu kỳ do CCTV thấy chính xe ego → thêm `self_track` (ego_pose) và đếm track của actor thật không-mục-tiêu là không-giả; khoá bằng chứng thêm `track_id`; thêm `monitor_warmup_s` (mặc định 0). Toàn bộ ở `docs/phase2/09` §9 (3 thay đổi), **chưa seed đánh giá nào được dùng**. Không đổi ngưỡng.
4. Sau đăng ký: `scripts/physics_bites.py` sửa để sao chép `fusion/experiments/docs` và hỗ trợ `--only=` (hạ tầng kiểm thử, không phải thuật toán).

## 5. Ranh giới bảo mật (không đổi)
CRC-32 chỉ phát hiện hỏng ngẫu nhiên. Giả mạo nguồn hợp lệ allowlist (KF-3), phát lại bản bắt được (KF-4), lệch đồng hồ trong dung sai (KF-5) và echo đổi nhãn (KF-8) **chưa được giải quyết**. `SourceIdentityVerifier` chỉ là giao diện; verifier duy nhất trả `allowlist-only`; chính sách `require_assurance="authenticated"` fail-closed (từ chối mọi remote). **Không có mật mã, không có chống phát lại → không tuyên bố xác thực.**

## 6. Giới hạn
Cảm biến/kênh là mô hình thống kê (E04); scene đơn giản (1–2 người đi bộ, 1 CCTV + ego, ego đứng yên hoặc thẳng); tracker nền bảo thủ (ANEES≈2) nên coverage≥0.9 dễ đạt và làm yếu các giả thuyết "quá tự tin"; không có thông tin âm (P1); mô hình CV; mỗi nguồn chỉ đóng góp ước lượng mới nhất; đồng bộ đồng hồ giả định chung (B04); 33 ngưỡng không hiệu chỉnh đa so sánh; ngưỡng là thiết kế tạm; PRD R-FUS-02 (centralized/hybrid) và AC-M10 (`validated/rejected`) **chưa làm**; AC-VS-04 vẫn PARTIAL; runtime không phải của Jetson; đối chiếu "mô phỏng ≠ an toàn".

## 7. Quyết định thiết kế chưa giải quyết (cần chủ việc)
1. B3 (−27% RMSE, nhưng quá tự tin khi tương quan/bias) hay B4 (nhất quán, không cải thiện độ chính xác khi cả hai thấy) làm mặc định? Hay lai (B4 khi monitor/đa nguồn nghi tương quan)?
2. Bỏ B4q hay thiết kế lại monitor (hiện còn báo động giả muộn, cách ly sinh ghost).
3. Có đầu tư xác thực mật mã + chống phát lại (KF-3/4/8) trước khi dùng dữ liệu V2X làm ràng buộc hay giữ giả định tin cậy.
4. Cách xử lý bias đã biết: khai báo bất định extrinsic (C5b hiệu quả) vs hiệu chuẩn online.
5. Xem 3 giả thuyết bị bác bỏ là kết quả nghiên cứu hay tiêu chí chấp nhận (PARTIAL).
6. Mở khoá VIS-08 bằng ảnh tham chiếu; WP5 chỉ bắt đầu khi được duyệt.

## 8. Lệnh tái lập
```bash
make setup && make check                                   # 40 PASS / 0 FAIL / 1 BLOCKED / 9 NOT_CHECKED
.venv/bin/python scripts/physics_bites.py --only=fus_      # 36 mutant fusion, kỳ vọng ALL CAUGHT
.venv/bin/python scripts/run_wp4_experiments.py eval       # ≈11 phút; kiểm hash đăng ký; ghi evidence/wp4/eval
sha256sum -c docs/phase2/wp-reports/evidence/wp4/MANIFEST.sha256
```
