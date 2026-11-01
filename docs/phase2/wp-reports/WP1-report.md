# WP1 — Physics sandbox đầu tiên (backend vật lý có thẩm quyền, bước cố định)

> **Bổ sung sau WP2 (2026-11-01):** theo yêu cầu của chủ việc, đã thêm regression moving→stopping→stationary (`tests/physics/test_phy05_standstill.py`, PHY-05 từ 6 lên 12 test) và sự kiện `standstill_jerk_discontinuity` để giới hạn jerk tại v=0 được **báo trong telemetry** thay vì là ngoại lệ ngầm. Header telemetry có thêm `height` nên hash golden đổi từ `ce9dc616…` sang `5876d26c…`; kết quả vật lý không đổi (S00a x_final = 13.613703703703715). Các con số "98 test PHY" bên dưới là số tại thời điểm WP1; số hiện hành xem `make check` và `WP2-report.md`.

**Trạng thái: PASS cho PHY-01…PHY-06 trong phạm vi đã định; PHY-07/PHY-08 NOT_CHECKED (thuộc WP2/WP3).** Ngày 2026-11-01. Không có VIS nào được chạy trong WP này.

## Mã nguồn chạy được
`backend/{params,dynamics,collision,scenario,telemetry,world,backend_api,run}.py` · `schemas/` · `scenarios/s00a_*.yaml`, `s00b_*.yaml` · `tests/physics/*` (98 test PHY) + `tests/unit/*` (11 test) · `scripts/{physics_bites,make_wp1_evidence,update_golden}.py`.
Chạy: `make test-physics` · `python -m backend.run scenarios/s00a_physics_sandbox_brake_early.yaml --seed 7 --out results/s00a` · `.venv/bin/python scripts/physics_bites.py`.
Mô hình: xe đạp động học, tích phân dọc **chính xác** cho gia tốc tuyến tính từng đoạn, hình học đường đi RK4 theo cung, actuator (trễ thuần + giới hạn jerk + kẹp gia tốc), vòng ma sát μg có ưu tiên dọc, OBB/capsule SAT, người đi bộ động học theo chấp điểm, RNG tách luồng theo id (PCG64 + SeedSequence), telemetry JSONL chuẩn tắc + SHA-256.

## Acceptance criteria và kết quả
Mọi PHY: seed cố định trong mã test, một lệnh tái lập, đối chiếu **mã tham chiếu độc lập** (`tests/physics/reference.py`, không chung mã với `backend/`).
| Cổng | Kiểm | Kết quả | Evidence (thực chạy) |
|---|---|---|---|
| PHY-01 | Tất định; độc lập wall-clock | **PASS** (8 test) | Cùng seed ×2 → cùng hash; seed khác → hash khác; observer ngủ ngẫu nhiên mỗi bước → hash không đổi; 2 tiến trình với `PYTHONHASHSEED` 0 và 12345 → cùng hash; luồng RNG độc lập thứ tự actor; −0.0 chuẩn hoá; golden anchor `ce9dc616…` cùng môi trường |
| PHY-02 | Động học tuyến tính | **PASS** (8 test) | 7 ca (tăng tốc, giảm tốc êm/khẩn cấp, trôi) khớp công thức đóng ≤ 1e-6 m (thực tế ≪); lệnh có hiệu lực đúng sau `t_act` (bước 115) |
| PHY-03 | Quãng dừng + ma sát | **PASS** (29 test) | Lưới 16 ca (v₀ 5–11 m/s × {êm, khẩn cấp} × μ {0.5, 0.8}): sai số lớn nhất so công thức đóng **4.74e-5 m** (tiêu chí 1e-3), so tích phân độc lập **4.74e-5 m** (tiêu chí 5e-3); ca bước-thẳng-hàng đúng tới **1e-9** (thực đo ~5e-14); kẹp ma sát μg khi μ=0.5; dừng giữa đoạn ramp; không lùi. Số công bố: **9.45 m** và **17.64 m** ở 30 km/h, μ=0.8 (`evidence/wp1/phy03_error_table.json`) |
| PHY-04 | Lái và quay đầu | **PASS** (9 test) | `R = L/tanδ` và `ψ = v tanδ t/L` đúng ≤ 1e-9 (tiêu chí 1e-3); kẹp ma sát cho `R = v²/(μg)` = 8.85 m ≤ 1 mm; giới hạn tốc độ lái + trễ lái chính xác; `δ_max`; bán kính nhỏ nhất 3.856 m |
| PHY-05 | Giới hạn gia tốc/jerk/lái | **PASS** (6 test) | Property test (hypothesis, `derandomize`, 150 ví dụ) + lệnh cực đoan: 0 vi phạm `a_brk`, `a_acc`, `j_max`, `δ_max`, `δ̇_max`, vòng ma sát; jerk đỉnh đúng 2.5 / 10 m/s³ |
| PHY-06 | Va chạm + người đi bộ | **PASS** (38 test) | Bảng SAT 9 ca (chạm mép, chồng lấn, xoay); khoảng cách điểm/đoạn; thời điểm chạm đầu tiên khớp giải tích trong ≤ 1 bước cho 24 tổ hợp (v × lệch ngang, gồm sượt góc); không xuyên thủng ở 40 km/h trên 41 độ lệch; người đi bộ chuyển động: tốc độ va chạm = √(v²+vp²) ≤ 1e-9; run kết thúc tại va chạm; tunnelling guard từ chối dt thô |
| PHY-07 | Cảm biến FOV/che khuất/bất định | **NOT_CHECKED** | Chưa có mã/test (WP2) |
| PHY-08 | Truyền thông, độ tươi | **NOT_CHECKED** | Chưa có mã/test (WP3) |
| Meta | Test có bắt được lỗi? | **PASS** | `evidence/wp1/physics_bites.txt`: **12/12 lỗi tiêm vào (integrator, jerk, ma sát dọc/ngang, wheelbase, rate lái, trễ actuator, SAT, khoảng cách đoạn, stop_on_collision, nhiễu wall-clock, nghiệm dừng trong bước) đều bị test giải tích bắt** (golden bị loại khỏi phép thử này) |
| AC-VS-10 (phần vật lý) | Telemetry hợp lệ schema | **PASS** | Mọi dòng của S00a/S00b hợp lệ `telemetry.schema.json` |
| AC-M02 (một phần) | Scenario sai bị từ chối có vị trí lỗi | **PASS** | 8 ca sai (thiếu field, field lạ, dt âm, id trùng, v vượt ODD, thời gian không bội dt, μ=0…) |

## Bằng chứng thực thi
`evidence/wp1/`: `pytest_physics_verbose.txt` (98 PASSED) · `physics_bites.txt` · `phy03_error_table.json` · `braking_profile_vs_closed_form.svg` (mô phỏng chồng khít đường tham chiếu độc lập; nhìn thấy cả bước dừng hẳn) · `s00a/`, `s00b/` (manifest + đầu/cuối telemetry) · `summary.json`.
Sandbox (chỉ minh hoạ vật lý, **không phải kết quả khoa học**; lệnh phanh theo kịch bản, chưa có perception/closed-loop): S00a phanh sớm → dừng tại x=13.614 m, không va chạm, khoảng cách tối thiểu 7.59 m; S00b phanh muộn → va chạm với tốc độ tương đối 2.82 m/s, ego còn 2.33 m/s.
Tốc độ (thông tin, không phải gate): 10 s mô phỏng 1 xe chạy trong ≈ 0.03 s (≈ 330× thời gian thực, gồm ghi telemetry trong bộ nhớ).

## Quá trình và lỗi đã gặp (trung thực)
- 14 test fail lần chạy đầu. **Cả ba nguyên nhân đều ở test, không ở backend:** (1) công thức giải tích điểm chạm của tôi sai khi người đi bộ nằm trong bề rộng xe (phải `x_ped − R`); (2) ca v=3 m/s chạy quá ngắn để xe tới nơi; (3) đo jerk đỉnh lẫn bước dừng hẳn.
- Mutation bite đầu: golden-hash che mất việc test giải tích có bắt lỗi hay không → loại golden khỏi bite. Sau đó mutant `stop_snap_exact_removed` **sống sót** vì sai số của nó (≤ 0.3 mm) nằm dưới dung sai 1 mm → thêm test bước-thẳng-hàng 1e-9 và chặn trên 1e-4 cho ca không thẳng hàng; mutant bị bắt.
- Phát hiện **giới hạn thật của mô hình** (không phải lỗi test): gia tốc **nhảy về 0 trong một bước** khi xe dừng hẳn, nên giới hạn jerk không được thi hành tại khoảnh khắc dừng (có trong đồ thị). Đã ghi vào `LIMITATIONS` và 07 §8.

## Known limitations (đầy đủ ở `backend/params.py: LIMITATIONS` và 07 §8)
1. Chỉ xác thực **so với giải tích**; **chưa** so với xe thật hay CARLA (PX-1 chưa làm). Không tuyên bố tương đương CARLA.
2. Mọi tham số (μ, t_act, jerk, a_brk, hình học) là `[PARAM]` **không có nguồn** (V02, V03). PASS chứng minh *mã khớp công thức*, không chứng minh *công thức khớp xe*.
3. Xe đạp động học + vòng ma sát: không trượt lốp, truyền tải trọng, nhún. Hợp lệ chỉ khi `a_y ≤ 0.5 μg`; vượt ngưỡng sinh sự kiện `outside_model_validity` (đã test).
4. Gia tốc snap về 0 khi dừng hẳn (jerk không thi hành tại bước đó).
5. Ramp không thẳng hàng bước (vd μ=0.5) có sai số ≤ 4.7e-5 m (đã đo, đã chặn trong test).
6. Va chạm là hình học cứng, kết thúc run; không có mô hình chấn thương/biến dạng; người đi bộ không phản ứng.
7. PHY-01 hiện chỉ phủ **lõi mô phỏng**: phần "paced vs free-run qua luồng WebSocket" chưa tồn tại → thuộc WP5 (`VIS-10`/`PHY-01` mở rộng). Bit-exact chỉ trong cùng môi trường (Python 3.13.18, numpy 2.5.4, Linux x86_64); golden bị **skip** (không bao giờ tính là pass) ở môi trường khác.
8. Property test PHY-05 là 150 ví dụ có seed cố định, không vét cạn.
9. Chưa có sensor, kênh, fusion, planner, closed-loop; scenario S00 dùng lệnh phanh theo kịch bản.
