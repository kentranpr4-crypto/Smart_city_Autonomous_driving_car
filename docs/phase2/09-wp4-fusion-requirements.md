# 09 · WP4 — Hợp nhất nhận thức cộng tác có tính bất định: yêu cầu, giả thuyết, ngưỡng đăng ký trước

Trạng thái: **WP3 được duyệt có điều kiện**; chỉ làm WP4 (không dựng thành phố, không điều khiển/lập kế hoạch vòng kín). Tài liệu này + `fusion/preregistration.json` + `experiments/conditions.py` được **commit trước khi có mã fusion hoặc benchmark cuối**. Mọi thay đổi sau đó phải ghi ở §9 (kèm lý do).
Không bịa nguồn: lý thuyết dùng ở đây (bộ lọc Kalman/thông tin, Covariance Intersection, khoảng cách Mahalanobis) là kiến thức kỹ thuật chuẩn nhưng **chưa nằm trong registry Refinery**; WP4 không thêm claim vào registry (REG-1 phải giữ nguyên) nên chúng được coi là *giả định thiết kế đã nêu rõ*, không phải bằng chứng ngoài.

## 1. Câu hỏi nghiên cứu và phạm vi
**Câu hỏi:** chia sẻ quan sát mức đối tượng giữa xe tự hành và hạ tầng có cải thiện ước lượng trạng thái thế giới khi bị che khuất, nhiễu đo, lệch hệ thống (bias) và truyền thông suy giảm không — và trong điều kiện nào thì nó **làm xấu đi** (tương quan, bias, lệch timestamp, trùng bằng chứng)?
**Giới hạn tuyên bố:** kết quả là **mô phỏng** (cảm biến thống kê 2.5D, kênh rời rạc, không phần cứng); không suy ra an toàn ngoài đời thực (F09 UNKNOWN). Truth chỉ nằm ở bộ đánh giá (`experiments/`), **không** ở đường suy luận (`fusion/`, `comm/`, `perception/`).
Ranh giới bảo mật: CRC-32 chỉ phát hiện hỏng ngẫu nhiên. Giả mạo và phát lại bản bắt được là rủi ro **đã biết** (KF-3/KF-4). WP4 thêm **giao diện** xác thực danh tính nguồn (`SourceIdentityVerifier`) với bản mặc định `UnauthenticatedVerifier`; **không** tuyên bố đã có xác thực/chống phát lại.

## 2. Baseline bắt buộc (cùng dữ liệu vào, cùng thời điểm ra — so sánh ghép cặp)
| ID | Phương pháp | Giả định tường minh |
|---|---|---|
| B0 | chỉ track cục bộ (ego) | — |
| B1 | chỉ track từ xa (nguồn tốt nhất theo vết P nếu nhiều nguồn) | — |
| B2 | hợp nhất ngây thơ: trung bình số học trạng thái, P = trung bình số học các P | không dùng thông tin hiệp phương sai để gán trọng số; không giảm bất định |
| B3 | hợp nhất Kalman/thông tin: P⁻¹=ΣPᵢ⁻¹, x=PΣPᵢ⁻¹xᵢ | **các ước lượng hiện tại của mỗi nguồn độc lập** (sai khi có tương quan: nhiễu chung, bằng chứng lặp, lịch sử lọc chung) |
| B4 | Covariance Intersection (tiêu chí min vết, tìm ω tất định, tuần tự khi >2 nguồn) | tương quan chéo **không biết**; nhất quán với mọi tương quan |
| B4q | (biến thể thêm, không bắt buộc) B4 + cách ly nguồn bị monitor đánh dấu | bias/không nhất quán được phát hiện |
Mỗi nguồn chỉ đóng góp **ước lượng mới nhất** (không tích luỹ theo thời gian) để tránh đếm đôi do tương quan theo thời gian.

## 3. Yêu cầu
| ID | Yêu cầu | Lý do | Bằng chứng | Giả thuyết / ẩn số | Ca lỗi | Test |
|---|---|---|---|---|---|---|
| R-CPF-01 | Căn thời gian theo **thời điểm quan sát gốc** `t_meas` (trạng thái hợp lệ tại `t_meas`, không phải `t_upd`/`t_recv`); dự báo CV với Q cùng mô hình tracker; giới hạn tầm dự báo | tránh nhầm độ trễ với tuổi; relay giữ `t_meas` | Toán chuẩn; khớp tracker (test so sánh) | Mô hình vận tốc không đổi sai với người đổi hướng; đồng bộ đồng hồ UNKNOWN (B04) | t_meas tương lai, quá cũ, vượt tầm | FUS-01 |
| R-CPF-02 | Lan truyền hiệp phương sai khi dự báo (P'=FPFᵀ+Q), tuỳ chọn cộng bất định timestamp σ_t (vvᵀσ_t²) | bất định phải tăng theo tuổi | Toán chuẩn; Monte Carlo NEES | σ_t mặc định 0 (không có số đo) | P không PSD, dt âm | FUS-02 |
| R-CPF-03 | Biến đổi toạ độ SE(2) **tường minh** có lan truyền hiệp phương sai (cả bất định của phép biến đổi) | yêu cầu chủ việc; không biến đổi âm thầm (COM-07 vẫn từ chối frame lạ) | Toán + Jacobian so sai phân hữu hạn | Tương quan chéo do cùng phép biến đổi bị bỏ qua (ghi rõ) | frame lạ, cov biến đổi không PSD | FUS-03 |
| R-CPF-04 | Gán chéo nguồn **không dùng truth**: Hungarian tối ưu trên d² Mahalanobis 4-D, cổng χ²₉₉.₉(4), ràng buộc lớp, cờ mơ hồ | I9 | Hungarian = brute force (WP2); cổng như tracker | KF-1/KF-2 giữ nguyên (người đi sát nhau / giao cắt) | hai người 0.4 m; lớp mâu thuẫn | FUS-04 |
| R-CPF-05 | Cài và so sánh B0..B4 (+B4q) đúng định nghĩa §2 | yêu cầu chủ việc | Công thức đóng; MC với tương quan biết trước | B3 quá tự tin khi tương quan (giả thuyết H4a) | tương quan, echo | FUS-05 |
| R-CPF-06 | Giữ **provenance** nguồn gốc; sổ bằng chứng khoá `(origin source, orig_seq)`; bằng chứng trùng/relay chỉ đóng góp **một lần** | chống đếm đôi (FM04), relay | WP3 COM-08 | Echo qua nguồn **khác danh nghĩa** không phát hiện được bằng sổ → cần CI | relay + trực tiếp; seq lặp | FUS-06 |
| R-CPF-07 | Xử lý stale, mâu thuẫn, thiếu, sai định dạng ở mức fusion (phòng thủ nhiều lớp sau admission): loại + đếm lý do; **vắng mặt ≠ trống** (P1) | I2/I3 | WP3 | Không có thông tin âm (không suy "trống" từ vắng mặt) | NaN, cov không PSD, tuổi quá hạn, lớp xung đột | FUS-07 |
| R-CPF-08 | Trạng thái thế giới hợp tác là **dữ liệu thuần**, độc lập bộ điều khiển/planner; tất định; không import truth/backend | yêu cầu chủ việc; I9/I10 | AST + chặn import | — | import planner/truth | FUS-08 |
| R-CPF-09 | Monitor nhất quán nguồn (tổng d² cặp trong cửa sổ N=10 so χ²₉₉.₉(2N)) + giao diện xác thực nguồn fail-closed | phát hiện bias/nhiễu chung; ranh giới bảo mật | Toán chuẩn | Ngưỡng/cửa sổ là tham số thiết kế | bias hằng, bias thoáng qua | FUS-09 |
| R-CPF-10 | Giao thức thí nghiệm: đăng ký trước, seed tuning ≠ seed đánh giá, 9 thí nghiệm, chỉ số, tái lập, mọi thay đổi sau đăng ký ghi lại | tính toàn vẹn nghiên cứu | git history + hash | — | sửa ngưỡng sau khi thấy kết quả | FUS-10 |

### 3b. Đối chiếu với PRD (không đổi nghĩa)
PRD R-FUS-01 (liên kết + hợp nhất có cov + chống đếm trùng): WP4 phủ cho **track-to-track phi tập trung phía ego**. PRD R-FUS-02 (kiến trúc cắm được centralized/decentralized/hybrid): **chỉ decentralized được cài**; centralized/hybrid **NOT_CHECKED, ngoài WP4**. PRD R-FUS-03 (`validated/rejected` kèm mã lý do): WP4 cung cấp mã lý do loại ở mức fusion (R-CPF-07) nhưng **không** gán nhãn `validated` theo nghĩa AC-M10; AC-M08/M09/M10 không tuyên bố hoàn tất.

## 4. Cổng FUS-01 … FUS-10 (mới; không định nghĩa lại PHY/COM/VIS)
| ID | Tiêu chí quan sát được |
|---|---|
| FUS-01 | Căn thời gian: Q/F bằng tracker (sai số số học ≤1e-12); dự báo về trước/sau; từ chối tầm > max_horizon; dùng `t_meas`; bất định timestamp cộng đúng công thức |
| FUS-02 | Lan truyền cov: đối xứng, PSD, tăng đơn điệu theo tuổi, khớp công thức đóng; Monte Carlo NEES ≈ 4 |
| FUS-03 | Biến đổi SE(2): Jacobian = sai phân hữu hạn; hợp thành/nghịch đảo; Monte Carlo nhất quán gồm bất định biến đổi; frame khai báo; cov biến đổi không PSD bị từ chối |
| FUS-04 | Gán: tối ưu = brute force; cổng; lớp; mơ hồ; không truth (AST, tiến trình chặn import cho cùng kết quả); tất định |
| FUS-05 | B0..B4: công thức đóng; B3 = tổng thông tin; CI: P_ci⁻¹ ≥ ... nhất quán MC với tương quan ρ∈{0,0.5,0.9,1}; B3 quá tự tin ở ρ=1 (test của test); tuần tự đúng |
| FUS-06 | Provenance giữ nguyên; bằng chứng trùng chỉ dùng một lần; relay + trực tiếp; không đếm đôi |
| FUS-07 | Mỗi lý do loại có ca đúng; đầu ra luôn hữu hạn/PSD (fuzz); suy giảm êm khi mất nguồn; không "trống" |
| FUS-08 | Không import truth/backend/planner; tiến trình chặn import; replay bit-giống; đầu ra là dữ liệu bất biến |
| FUS-09 | Monitor: tỉ lệ báo động giả/bắt bias đúng thiết kế; xác thực fail-closed khi bắt buộc; không có đường mã trả `authenticated=True` ngoài test double đặt tên rõ |
| FUS-10 | Hash đăng ký khớp; seed tuning ∩ evaluation = ∅; metric của bộ đánh giá đúng trên ca tổng hợp biết trước; benchmark tái lập bit-giống; mọi invariant FI-1..6 PASS; kết quả giả thuyết được báo cáo đủ |

## 5. Định nghĩa chỉ số (đánh giá phía truth; gộp qua seed)
- **Cửa sổ**: tại mỗi chu kỳ fusion (t=0.09+0.1k) với từng mục tiêu thật; `occluded` = ego không thấy (nhãn `visible`) và nguồn từ xa thấy; `overlap` = cả hai thấy.
- **availability** = tỉ lệ (mục tiêu×chu kỳ) có track fused khớp truth (Hungarian 1-1, cổng 2.0 m); `availability_occluded` chỉ trong cửa sổ occluded; **ttfv** = thời gian từ lúc mục tiêu lần đầu được ít nhất một nguồn thấy đến track fused khớp đầu tiên (censor nếu không có; tính trung vị theo seed).
- **pos_rmse / vel_rmse** trên các cặp khớp sau khởi động 1 s; `pos_rmse_overlap` chỉ trong cửa sổ overlap.
- **coverage95** = tỉ lệ NEES₄ᴅ ≤ χ²₀.₉₅(4)=9.4877; **ANEES** = trung bình NEES (kỳ vọng 4); **NIS** = trung bình d² cặp chéo nguồn (kỳ vọng 4 nếu độc lập và nhất quán).
- **assoc_precision/recall**: cặp fusion (local,remote) đúng nếu cả hai track khớp cùng một truth (khớp từng nguồn riêng, 1-1); precision = đúng/tổng cặp; recall = đúng/số cặp khả dĩ (cả hai nguồn có track khớp cùng truth).
- **id_switch_rate_per_min** từ `id_switches` của WP2 trên đầu ra fused; **id_switch_seed_fraction** = tỉ lệ seed có ≥1 lần.
- **false_tracks_per_cycle** = track fused không khớp truth nào; **excess_vs_B0** = hiệu số với B0 cùng chu kỳ.
- **remote_admitted_fraction** = bản tin admitted/gửi; **distinct_obs_admitted_ratio** = số `(origin, orig_seq)` khác nhau được admitted/gửi.
- **recovery_p95_s**: sau khi blackout kết thúc, thời gian tới khi fused dùng lại bằng chứng từ xa (P95 theo seed).
- **monitor_flag_seed_fraction**: tỉ lệ seed monitor đánh dấu nguồn từ xa ≥1 lần trong 3 s đầu sau khi có cặp liên kết đầu tiên.
- **runtime**: `perf_counter` bao quanh một chu kỳ fusion (phía đánh giá; mã fusion không đọc đồng hồ); **bandwidth** từ telemetry WP3.
- **failure rate theo điều kiện**: tỉ lệ seed có availability < 0.5, hoặc ngoại lệ, hoặc vi phạm invariant.
Thống kê: trung bình ± khoảng tin cậy bootstrap 95% theo seed (RNG cố định); giả thuyết được đánh giá trên số gộp (point estimate) so với ngưỡng đã đăng ký; **không** có hiệu chỉnh đa so sánh (33 ngưỡng; ghi như giới hạn).

## 6. Giao thức
- Seed **tuning** 20261201–20261215 (chỉ để gỡ lỗi, kiểm tra chạy được; không dùng để khẳng định); seed **đánh giá** 20261301–20261330 (chạy một lần sau khi đăng ký và sau khi mã đóng băng). Chạy lại đánh giá chỉ khi sửa lỗi và phải ghi ở §9.
- 21 điều kiện × 6 phương pháp trên cùng dữ liệu. Cảm biến/tracker/kênh: WP2/WP3 không đổi (3-of-4 cho mọi tracker).
- Tham số fusion cố định a priori (`FUSION_PARAMS`); nếu phải chỉnh trên seed tuning thì ghi §9 trước khi chạy đánh giá.

## 7. Thí nghiệm bắt buộc ↔ điều kiện
1 Người đi bộ bị che: C1 · 2 Hai người sát nhau: C2a/C2b · 3 Giao cắt/ID-switch: C3a/C3b · 4 Ước lượng tương quan: C4a (echo ρ=1), C4b (một phần) · 5 Bias hằng: C5a/C5b (+đối chứng C0) · 6 Lệch timestamp: C6a–d · 7 Mất gói/stale: C7a/C7b · 8 Relay nhiều bước + trùng: C8a–c · 9 Camera từ xa mất: C9a/C9b.

## 8. Known failures giữ nguyên (không sửa trong WP4)
KF-1..KF-5 (WP2/WP3) vẫn là xfail strict. WP4 thêm KF-6 nếu thí nghiệm bộc lộ (ghi ở báo cáo).

## 8b. Mã băm đăng ký
`fusion/preregistration.json` sha256 = `600215ad6454c29d0c8ee81229ea13a540ca0c397637810fee863c0842b9d036`; `experiments/conditions.py` sha256 = `f0108f59f404d0fb0079682770a182884e44a5c7df553d8230952c84a0edb950`.

## 9. Thay đổi SAU đăng ký
| # | Thay đổi | Lý do |
|---|---|---|
| 1 | Khoá sổ bằng chứng là `(origin source, origin seq, track_id)` thay vì `(origin source, origin seq)` (R-CPF-06, nền của FI-2) | Phát hiện khi viết test FUS-04: một bản tin chứa nhiều track; khoá hai thành phần sẽ coi hai mục tiêu khác nhau trong cùng bản tin là trùng bằng chứng. Thay đổi chỉ làm khoá **chi tiết hơn**, không đổi ngưỡng/giả thuyết; chưa có benchmark nào chạy |
| 2 | Thêm triệt tiêu **self-track** (`ego_pose` → lý do `self_track`, ngưỡng χ²₉₉.₉(2)) vào fuser; bộ đánh giá khớp các track với **mọi** actor thật (không chỉ mục tiêu) khi đếm track giả | Phát hiện trên **seed tuning** (C1): `false_tracks_per_cycle` = 0.309 vì CCTV thấy chính xe ego và vì track của xe thật không phải mục tiêu bị tính là giả. Ego biết vị trí của chính nó (đầu vào hợp lệ lúc suy luận, nhiễu σ=0.1 m trong mô phỏng). Không đổi ngưỡng/giả thuyết đã đăng ký; chưa chạy seed đánh giá |
| 3 | Thêm tham số `monitor_warmup_s` (mặc định **0 = đúng cấu hình đã đăng ký**). Kết quả chính H5a/H5b dùng cấu hình đăng ký; giá trị 1.0 s chỉ được báo cáo như **bổ sung** | Trên **seed tuning**: monitor báo động giả sớm (1.6–1.9 s) vì quá độ khởi tạo track (đối chứng C0: 20% seed trong 3 s). Warm-up 1.0 s: C0 trong 3 s 0%, nhưng phát hiện bias C5a trong 3 s còn 87% (<90%); báo động muộn còn ~13% seed. Không chỉnh thêm; không dùng làm kết luận |
