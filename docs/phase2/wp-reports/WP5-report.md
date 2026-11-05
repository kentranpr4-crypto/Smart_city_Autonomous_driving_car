# WP5 — An toàn vòng kín & lập kế hoạch có hợp tác (closed-loop cooperative safety & planning)

**Trạng thái: cổng kỹ thuật DONE (CLS-01..10 PASS, 8/8 invariant PASS); kết quả nghiên cứu HỖN HỢP — PARTIAL nếu coi giả thuyết là tiêu chí chấp nhận.** 22 giả thuyết đã đăng ký được đánh giá cuối trên 40 seed: **16 SUPPORTED, 6 REFUTED** (W-V1, W-7, W-8, W-11, W-18, W-22) + 3 mục chỉ báo cáo. Mọi kiểm tra là **tự kiểm**. Ngày 2026-11-05. Không thành phố 3D, không huấn luyện, không triển khai thực. VIS-08 vẫn BLOCKED. `main` không đụng tới.

> **Điều KHÔNG được suy ra từ báo cáo này.** "0 va chạm trên 40 seed" cho E3 là kết quả của **mô phỏng hữu hạn** (khoảng Wilson 95% của 0/40 là **[0, 8.8]%**), một ODD hẹp (một người đi bộ không phản ứng, một xe tải, một CCTV), cảm biến thống kê, kênh mô phỏng, xe theo sau là mô hình người lái. **Không chứng minh an toàn ngoài đời thực.** Ngoài ra kịch bản nguy hiểm yếu hơn đã đăng ký (W-V1 bị bác bỏ: E0-N chỉ va chạm 12.5% < 25%) nên **công suất thống kê cho so sánh chính còn thấp** (5 va chạm E0-N vs 0).

## 1. Kiến trúc vòng kín (deliverable 1, 3)
```
ego_cam → Tracker(3-of-4) ┐                                         ┌─ trust: LOCAL | CORROBORATED | ADVISORY | PENDING | REJECTED
remote TrackMsg → admission → store ┴→ CooperativeFuser(B4/CI, ego_pose lúc quan sát) → TrustAdmission → Supervisor{Planner, Risk} → a_cmd,mode
                                                                                                       │  World.issue(ScriptedCmd)  @10 Hz, trễ actuator 0.15 s
                                                              Authoritative physics backend (World) ◄──┘  → quan sát kế tiếp (sensors → trackers → comm)
```
- `planning/` (thuần, **không** import backend/comm/time/random): `trust.py`, `risk.py` (xác suất xung đột dạng đóng, tiên liệu worst-case, `a_req`), `planner.py` (dọc, stop-only; E0-C = người đi bộ ảo sau vật che), `supervisor.py`, `stack.py`.
- `closedloop/runner.py` (phía truth): một lần chạy = chính sách × kịch bản × seed trên **cùng** backend (`World.issue`), bước điều khiển 10 Hz, seed kịch bản/cảm biến/mạng cho mọi chính sách (kiểm bằng CLS-05, WI-8); ego chỉ nhận định vị riêng nhiễu, track cục bộ/từ xa, đo phía sau nhiễu, chướng ngại tĩnh từ "bản đồ".
- Fallback: không có dữ liệu từ xa hợp lệ ⇒ **quỹ đạo giống hệt E0-N, 40/40 seed** (B_E3, W-15 SUPPORTED, so hash).

## 2. Đặc tả Safety Supervisor (deliverable 2) — chi tiết ở `docs/phase2/10` §4
P1 bất biến (`a_cmd ≤ a_local`; **0 vi phạm** trong ~mọi tick của 28 điều kiện × 40 seed, WI-3); trần giảm tốc: LOCAL 6.0, CORROBORATED ≤6.0 (ràng buộc xe sau), ADVISORY **3.0**; PENDING/REJECTED bị bỏ qua và đếm (WI-2: **0** bằng chứng từ xa cũ/không hợp lệ được dùng); nhận biết xe sau (công thức đóng, kiểm bằng test); "contradicted hold" (vật thể từ xa-only trong tầm nhìn thông thoáng: trần tốc độ 4 m/s khi >12 m, hazard advisory khi <12 m — không bị bỏ qua); không bao giờ gắn nhãn `authenticated` (WI-7: 0). **Jerk dừng gấp** là giới hạn đã biết, được **đếm** (§5).

## 3. Kết quả đánh giá cuối (đăng ký trước; đóng băng tại `7a61d97`/`f645b7b`; chạy MỘT lần; 40 seed 20261501–40)
Bản gốc giữ nguyên: `evidence/wp5/eval/{results.json, verdicts.md, eval_run.txt}` + `MANIFEST.sha256`.

**Phán quyết:** WI-1..8 **PASS**. SUPPORTED: W-V2, W-V3, W-1..W-6, W-9, W-10, W-12..W-17, W-19..W-21. **REFUTED: W-V1** (E0-N va chạm 0.125 < 0.25: kịch bản yếu hơn dự kiến), **W-7** (E3 tốn travel-time hơn E0-C trong control: +3.91 s vs +2.23 s), **W-8** (can thiệp "không cần thiết" của E3 = 100% > 30%), **W-11** (ghost+xe theo sau: naive **không** gây va chạm đuôi: 0/40), **W-18** (U_E3 unnecessary 0.85 ≠ 0 — xem lưu ý), **W-22** (D_E3naive hard-brake 0.025 < D_E3+0.05).

### 3.1 So sánh E0-N / E0-C / E1 / E2 / E3 — kịch bản hazard (người đi bộ từ sau xe tải; 40 seed)
| Chính sách | Va chạm ego (Wilson 95%) | Vận tốc va chạm TB | Near-miss | Min-TTC trung vị | Phanh gấp >3.5 | Max decel P95 | Hoàn thành | Thời gian (s) |
|---|---|---|---|---|---|---|---|---|
| E0-N | **5/40 = 12.5%** [5.5, 26] | 5.66 m/s | 17.5% | 1.30 s | 57% | 6.0 | 88% | 13.6 |
| E0-C | 1/40 = 2.5% [0.4, 13] | 2.28 | 22.5% | 1.38 | 57% | 6.0 | 97% | 13.1 |
| E1 (+V2V) | 0/40 [0, 8.8] | — | 0% | 2.88 | 5% | 3.25 | 100% | 12.7 |
| E2 (+CCTV) | 0/40 [0, 8.8] | — | 2.5% | 2.75 | 5% | 2.89 | 100% | 12.4 |
| **E3 (V2V+CCTV)** | **0/40 [0, 8.8]** | — | 5% | **2.78** | 5% | 2.38 | 100% | 12.6 |
| E3-naive (ablation) | 0/40 | — | **12.5%** | 2.65 | **15%** | 3.95 | 100% | 12.3 |
Kiểm định (Fisher một phía, **chỉ mô tả, chưa hiệu chỉnh đa so sánh**): E0-N vs E3/E2/E1 **p = 0.027**; E0-N vs E0-C p = 0.10; E0-C vs E3 p = 0.5 (không phân biệt được).
Cùng bài toán **có xe theo sau** (R): E0-N **12/40 = 30%** [18, 45] va chạm vs E3 **0/40** (p = 1e-4); gộp hazard+R: **17/80 vs 0/80** (p ≈ 3e-6). Đây là bằng chứng mạnh hơn cho hướng cải thiện, nhưng vẫn là mô phỏng.
**Diễn giải cẩn trọng:** E3 không va chạm trong mọi seed, **không kém hơn** E0-C (W-4) và tốt hơn E0-N có ý nghĩa thống kê ở hazard (p=0.027) và rõ rệt khi có xe theo sau; nhưng E0-N-vs-E0-C và E3-vs-E0-C **không phân biệt được** ở n=40. Min-TTC cao hơn 1.5 s so với E0-N (W-6). Hiệu chuẩn rủi ro: ECE **0.042** (W-19; các tick tự tương quan).

### 3.2 Nơi hợp tác gây HẠI (taxonomy thất bại, deliverable 6)
| Loại thất bại | Điều kiện | Số liệu (40 seed) | Kiểm soát / trạng thái |
|---|---|---|---|
| **Phanh có hại do ghost** (naive) | G_E3naive: vật ma xuất hiện đột ngột 14 m trước | phanh gấp **90%**, giảm tốc P95 **6.0**, jerk P95 600 m/s³, +5.3 s | **Guarded: 0%** phanh gấp, giảm tốc 3.0 (comfort), +1.6 s |
| **Rủi ro va chạm đuôi** | RG_E3naive (ghost + xe theo sau) | **0 va chạm** (xe theo sau mô hình người lái 5 m/s²), nhưng min-TTC xe sau **1.36 s** (guarded 10 s), giảm tốc cần thiết P95 **3.0** m/s² (guarded 1.23) | W-11 bị bác bỏ về *va chạm*; rủi ro tăng rõ về *margin* |
| **Ghost từ nguồn allowlist** | G_E3 | vẫn phanh êm 3.0 m/s², +1.6 s (KF-11) | cần xác thực; admission không loại được (KF-3) |
| **Nguồn không tin cậy** | U_E3 (gói từ `rogue_9`) | bị admission loại; quỹ đạo **giống hệt** G_E0N (travel penalty 0.00) | metric "unnecessary" của W-18 bị E0-N nhiễu (xem lưu ý); **không có ảnh hưởng thật** |
| **ID churn** | I_E3 | 0 va chạm nhưng "unnecessary" 0.62 vs 0.23 (E3 thường) — churn làm giả thuyết không bền | chi phí, không phải nguy hiểm |
| **Bias CCTV + link suy giảm** | D_E3 | 0/40 va chạm (không tệ hơn E0-N) | W-16 SUPPORTED |
| **Đầu độc số thứ tự (DoS)** | tin giả `seq` rất lớn từ nguồn allowlist | nguồn thật bị từ chối `replay_old` | KF-10 (chưa giải quyết) |
| **Đóng băng trước người đứng chờ** | C_E3 (control) | +3.91 s so với E0-N (E0-C +2.23 s); 100% "can thiệp" (ngưỡng −1 m/s²) | W-7, W-8 bác bỏ; chi phí hiệu năng thật của thận trọng hợp tác |
| **Tự thấy mình** (đã sửa) | camera từ xa thấy xe ego đang phanh | từng gây phanh 6 m/s² giả | sửa ở `fusion` (tư thế lúc quan sát + bán kính), có test |
| **Jerk dừng gấp** | mọi chính sách dừng tới v=0 | tỉ lệ sự kiện: E0-N 32%, E3 2.5%, G_E3naive 100%; jerk P95 E0-N 524, naive 600 m/s³, E3 10 | KF-9: **đo, không tuyên bố tuân thủ** |

**Lưu ý metric (W-18/W-8):** ngưỡng "can thiệp không cần thiết" (giảm tốc >1 m/s², phản chứng khoảng cách ≥1.5 m) bị **nhiễu vận tốc của tracker** làm cho ngay cả E0-N có 85–90% lượt "không cần thiết" (xe đỗ bên đường). Vì vậy U_E3 = G_E0N ≈ 0.85 là **mức nền**, không phải ảnh hưởng của kẻ tấn công (so sánh quỹ đạo cho thấy giống hệt). Tôi **không** sửa định nghĩa metric sau khi thấy kết quả.

### 3.3 Chỉ số khác
Độ trễ quyết định: P50/P95 **1.4/2.3 ms** (CPU sandbox, **không** phải Jetson). Tuổi quan sát từ xa lúc quyết định P95 **0.17 s**, tối đa ≤0.5 s (WI-2). Thời gian cảnh báo trung vị (hazard, E3): phanh **3.4 s trước** khi người đi bộ chạm mép làn (E0-N: 2.3 s, đa phần do phản ứng sát giờ). Hoàn thành tuyến: E3 100%, E0-N 88%.

## 4. Mutation & hồi quy (deliverable 7)
- **Planning/evaluator:** 34 mutant. Lần 1 sống sót **8**: **1 tương đương** (bao `min` P1: planner đã lấy min trên tập con nên `a_all ≤ a_local` theo cấu trúc; ghi chú trong `scripts/physics_bites.py`), **7 lỗ hổng thật** (sàn creep không được thực thi vì ca test không kích hoạt precaution; ngưỡng p bị bỏ; kẹp lệnh cuối chỉ thừa với cấu hình đúng; nominal planner chỉ được bảo vệ bởi bộ lọc B0 của fuser (lớp 2); naive dùng CI thay B3; ngưỡng 'không cần thiết' và trọng số bin của ECE) → thêm **5 test** + sửa mục tiêu test của 1 mutant. Lần 2: 1 sống sót do mục tiêu test sai → sửa → **33/33 mutant thực thi bị diệt, 1 tương đương có ghi chú**. Logs: `evidence/wp5/mutation/`.
- **Hồi quy:** `make check` = **50 PASS / 0 FAIL / 1 BLOCKED / 9 NOT_CHECKED**; mọi PHY/COM/FUS cũ không đổi định nghĩa. Mutant comm/fusion: xem WP3/WP4 (mã chạm tới: `fusion/fuser.py`, `comm/network.py` — xem §7). 
- **11 known failure** còn nguyên (KF-1..8 cũ + **KF-9** jerk dừng, **KF-10** đầu độc seq, **KF-11** ghost allowlist gây phanh êm).

## 5. Giới hạn đã biết (rõ ràng)
Planner **chỉ phanh** (không lái né); một địa hình và một ODD hẹp; người đi bộ không phản ứng (không né xe); xe theo sau là mô hình người lái đơn giản; cảm biến/kênh thống kê; tracker vận tốc ồn gây phanh êm dư thừa; **W-V1 bị bác bỏ** (độ khó thấp → công suất thấp); 36 ngưỡng không hiệu chỉnh đa so sánh; 11 known failure; xác thực nguồn **chưa có** nên mọi nguồn từ xa chỉ `allowlist-only`; P2 (EO-C khi mất kênh) không làm; **không có đo bằng phần cứng/Jetson**. Thiết kế đối kháng (ghost đột ngột) được chọn **sau khi** thấy naive không hại ở thiết kế đầu (ghi §10 doc 10).

## 6. Thay đổi sau đăng ký (đầy đủ ở `docs/phase2/10` §10)
9 mục: hiệu chuẩn kịch bản (chỉ E0-N), `DURATION`, creep/"beside", self-track (cũng chạm `fusion/` và `comm/`), supervisor, ghost, các tham số **không đổi** (`p_thr=0.05`, `horizon=6 s`) và bằng chứng quét tuning, quan sát tuning còn lại, mutation.

## 7. Hồi quy cho WP3/WP4 (mã chung bị chạm)
Cuối cùng chạy lại **toàn bộ** đánh giá WP4 từ mã hiện tại và so digest tất định (xem §8).

## 8. Tái lập (clean-room)
```bash
make setup && make check                                         # 50 PASS / 0 FAIL / 1 BLOCKED / 9 NOT_CHECKED
.venv/bin/python scripts/run_wp5_closedloop.py eval              # ≈14 phút; từ chối chạy nếu mã/giao thức đóng băng đổi
.venv/bin/python scripts/wp5_digest.py <results.json>            # so với eval/deterministic_digest.txt
(cd docs/phase2/wp-reports/evidence/wp5 && sha256sum -c MANIFEST.sha256)
.venv/bin/python scripts/physics_bites.py --only=pln_,cls_       # 33 mutant, kỳ vọng ALL CAUGHT
```
Kết quả clean-room ghi ở §9 sau khi chạy.

## 9. Kết quả clean-room
Clone mới + `make setup` (commit `1194d2a`): `MANIFEST.sha256` **7/7 tệp OK**; `make check` giống hệt (**50 PASS / 0 FAIL / 1 BLOCKED / 9 NOT_CHECKED**, gồm FREEZE và evidence cuối được kiểm). Chạy lại **toàn bộ** đánh giá cuối WP5 trong clone (28 điều kiện × 40 seed, ≈14 phút): digest tất định `f20828f1…7974` **trùng bit-giống** với bản gốc; mọi phán quyết trùng (kể cả 6 REFUTED); chỉ độ trễ quyết định P95 khác (2.202 vs 2.271 ms, phụ thuộc đồng hồ tường, loại khỏi digest). Cơ chế "chạy một lần" bị bỏ qua **chỉ trong clone** bằng cách xoá `results.json` của clone (bản gốc trong repo không đổi).
**Hồi quy WP4:** chạy lại toàn bộ đánh giá cuối WP4 từ mã hiện tại (đã có `fusion/fuser.py`, `comm/network.py` sửa trong WP5): digest `54d91faa…a31fb` **trùng bit-giống** với bản gốc WP4 ⇒ các thay đổi dùng chung không làm đổi kết quả WP4 đã đóng băng.

## 10. Khuyến nghị cho frontend thành phố 3D (WP6)
**Tiến hành WP6 có điều kiện, chỉ như lớp hiển thị**: backend là nguồn trạng thái có thẩm quyền, telemetry/frames đã sẵn (I10/I12); frontend **không** tính an toàn. Nên hiển thị: mức tin cậy từng giả thuyết (local/corroborated/advisory/rejected), tuổi dữ liệu từ xa, sự kiện `follower_risk_accepted`, `contradicted_hold`, `standstill_jerk_discontinuity`, và nhãn "mô phỏng — không phải bằng chứng an toàn". **Chưa nên** quảng bá kết quả an toàn trong UI.
Việc cần trước hoặc song song: (1) **chủ việc quyết** mặc định guarded vs bổ sung xác thực mật mã (KF-3/10/11); (2) tăng độ khó/đa dạng kịch bản để W-V1 đạt (công suất so sánh E0-N/E0-C); (3) cân chỉnh chi phí đóng băng trước người đứng chờ (W-7/W-8) và định nghĩa metric "can thiệp không cần thiết" chống nhiễu; (4) lái né; (5) sửa jerk dừng ở backend (KF-9) nếu muốn tuyên bố tuân thủ; (6) ảnh tham chiếu cho VIS-08.

## 11. Quyết định cần chủ việc
Xem §10; thêm: có coi giả thuyết bị bác bỏ là tiêu chí chấp nhận (PARTIAL) không; có mở rộng ODD (nhiều người đi bộ, giao lộ) trước WP6 không.
