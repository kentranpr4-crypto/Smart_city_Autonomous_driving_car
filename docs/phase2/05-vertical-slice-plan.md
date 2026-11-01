# 05 · Kế hoạch vertical slice (T5) — bản sửa theo Amendment A1

Trạng thái: **DRAFT chờ duyệt. Chưa có mã nào được viết, chưa cài phụ thuộc, chưa commit/push.** Slice vẫn là **kịch bản nhỏ nhất** (1 xe + 1 CCTV + 1 người đi bộ bị che + phanh vòng kín), nhưng sau Amendment A1 **không còn là phần việc nhỏ**: vật lý có thẩm quyền (PHY-01..08) và diorama 3D cao cấp (VIS-01..10) là bắt buộc ngay trong slice. Định nghĩa chính thức các cổng ở 02 §12; kỹ thuật ở 07.

## 1. Phạm vi slice
| Có | Không (để sau) |
|---|---|
| Backend vật lý bước cố định, **có thẩm quyền**: xe (xe đạp động học, vòng ma sát, actuator trễ/jerk, OBB), người đi bộ (capsule), xe tải đỗ, va chạm hình học | A2, A3, K2–K4, V2V; follower ảo chỉ để đo rủi ro đuôi (tuỳ chọn) |
| Ego A1, CCTV K1, người đi bộ P, xe tải che | CARLA (chỉ có giao diện `PhysicsBackend`, không `CarlaBackend`) |
| Cảm biến 2.5D (FOV, che khuất theo độ cao, nhiễu), tracker CV-KF | Detector học máy, ảnh, point cloud |
| Kênh: trễ, jitter, mất gói, blackout, phát lại; thời gian tính toán là tham số | Đảo thứ tự/trùng lặp đầy đủ, spoof, drift đồng hồ (thêm sau WP5) |
| Validator I4/I5, safety gate I2, watchdog I7 | Ba topology (slice dùng nguồn trực tiếp; cắm được ở MVP) |
| Chính sách EO-N và EO-C là **hai baseline riêng**; điều kiện E0-N, E0-C, E2, E4a/c/e | E1, E3, E4b/d/f/g/h, EX-ARCH |
| **Diorama 3D thành phố đầy đủ danh mục** (07 §10.2) với đúng một AV hoạt động | Nhiều AV hoạt động, mật độ giao thông |
| Dịch vụ backend phát trạng thái có thẩm quyền (WebSocket) **và** ghi JSONL (replay) | Điều khiển vật lý từ UI (bị cấm, I12) |
Chọn **không** giảm chất lượng trực quan để "giữ slice nhỏ": sản phẩm cuối thất bại nếu hình ảnh kém rõ rệt (07 §12). Điều giữ slice nhỏ là số tác tử và số kịch bản, không phải chất lượng.

## 2. Môi trường quan sát và phụ thuộc cần duyệt (chưa cài)
Quan sát: Python 3.13.18 · Node 22.23.4 · numpy 2.5.3, uvicorn 0.54.0, jsonschema, PyYAML · Playwright (Node) 1.63.0 · `make`. **Sandbox không có GPU.**
| Phụ thuộc | Mục đích | Trạng thái |
|---|---|---|
| fastapi, websockets (hoặc starlette) | Dịch vụ phát trạng thái | cần duyệt |
| pytest, hypothesis | Test đơn vị, property | cần duyệt |
| react, react-dom, three, @react-three/fiber, @react-three/drei, zustand, vite (+typescript tuỳ) | Frontend R3F | cần duyệt; ghim phiên bản ≥ 2 tuần tuổi, lockfile, vendoring |
| (tuỳ chọn) tài sản glTF ngoài | Chất lượng mô hình | cần duyệt riêng, kèm bản ghi nguồn/giấy phép |
Không cài gì cho tới khi bạn duyệt (OD-6).

## 3. Kiến trúc slice
```
scenario.yaml ─► backend/world (fixed dt=10 ms, authoritative) ──truth──► metrics, telemetry(JSONL+hash), stream(WS)
                    ▲  apply_control(t_effective)                    │ truth CHỈ cho sensor models, metrics, UI
                    │                                                ▼
   ego/control ◄ ego/planning(EO-N|EO-C + overlay hạn chế) ◄ ego/fusion ◄ ego/validator ◄ sim/channel ◄ cctv tracker ◄ cctv detector(2.5D)
                    ▲                                                                          ego tracker ◄ ego sensor(2.5D)
   web (R3F) ◄── WebSocket/JSONL (trạng thái có thẩm quyền, mang t_sim) — chỉ đọc; UI→backend: chỉ play/pause/speed/scenario/seed/reset
```
Vòng kín: `Physics → Perception → Communication → Fusion → Planning → Control → Physics`. Ranh giới I9: gói `ego/` không import truth; `SensorProvider` là cầu duy nhất truth→quan sát. Thời gian tính toán là tham số (I11).

## 4. Cấu trúc thư mục đề xuất
```
backend/    world.py dynamics.py actuator.py collision.py occlusion.py sensors.py tracker.py channel.py
            metrics.py telemetry.py scenario.py backend_api.py (PhysicsBackend, SensorProvider) server.py (WS)
ego/        validator.py fusion.py planner.py safety_gate.py watchdog.py
schemas/    trackmsg.schema.json telemetry.schema.json scenario.schema.json state_stream.schema.json
scenarios/  s01_slice.yaml  s01_n1.yaml
web/        src/{scene,vehicles,city,overlays,cameras,ui}/  public/  ASSETS.md  (R3F + Vite)
tests/      physics/ (PHY-01..08)  unit/  property/  scenario/  ui/ (Playwright)
results/    manifest.json  telemetry/*.jsonl  metrics.csv  screenshots/  perf/   (gitignored)
docs/references/   (ảnh tham chiếu + SHA-256; CHƯA CÓ)
Makefile
```
Không sửa `.claude/skills/*` hay `data/refinery/*`.

## 5. Gói công việc, cổng và điểm dừng
Cỡ tương đối S/M/L/XL, không cam kết lịch.
| WP | Nội dung | Cỡ | Cổng ra |
|---|---|---|---|
| WP0 | Khung repo, khoá phụ thuộc (sau duyệt), schema, Makefile, hook `make check` (REF_INTEGRITY + registry không đổi) | S | AC-VS-13 |
| WP1 | **Lõi vật lý**: world, dynamics, actuator, collision, scenario loader, telemetry+hash | L | PHY-01, PHY-02, PHY-03, PHY-04, PHY-05, PHY-06 |
| WP2 | Cảm biến 2.5D, che khuất, tracker | M | PHY-07, AC-VS-03 |
| WP3 | Kênh, TrackMsg, validator, AoI | M | PHY-08, AC-VS-04 |
| WP4 | Planner EO-N/EO-C, safety gate, watchdog, metrics, CAL-0/CAL-1 | L | AC-VS-05, AC-VS-06, AC-VS-08 |
| **Điểm dừng R1** | Báo cáo hiệu chuẩn H1, **toàn bộ PHY PASS**, đặt ngưỡng τ_col/τ_fb/τ_assoc, khoá ngưỡng thị giác | — | Chủ việc duyệt |
| WP5 | Dịch vụ WebSocket + replay; chạy E0-N, E0-C, E2, E4a/c/e (N nhỏ = smoke) | M | AC-VS-07, AC-VS-09, AC-VS-10, VIS-10 |
| WP6a | **Diorama thành phố** (đường, vạch, zebra, vỉa hè, toà nhà, cây, đèn tín hiệu, đồ đường phố, CCTV), ánh sáng/bóng | XL | VIS-01, VIS-03 |
| **Điểm dừng V1** | Ảnh chụp từ frontend thật + **so với ảnh tham chiếu** (cần ảnh); chủ việc chấm | — | VIS-08 (BLOCKED nếu chưa có ảnh) |
| WP6b | Xe chi tiết + bánh quay, người đi bộ hoạt hoạ, camera 4 chế độ, lớp cooperative perception | XL | VIS-02, VIS-04, VIS-05, VIS-06 |
| WP6c | Tối ưu hiệu năng, đo, ảnh chụp bằng chứng, polish | L | VIS-07, VIS-09 |
| WP7 | Báo cáo gate, tái lập, giới hạn | S | AC-VS-12, AC-VS-14, AC-VS-15, AC-VS-16, AC-VS-17 |
| **Điểm dừng R2** | Review slice toàn bộ trước khi mở rộng sang MVP | — | Chủ việc duyệt |

**Trạng thái thực thi (2026-11-01, cập nhật khi triển khai):** WP0 **PASS**; WP1 **PASS** cho PHY-01..06 (báo cáo + bằng chứng tại `docs/phase2/wp-reports/`); PHY-07/08 NOT_CHECKED (WP2/WP3); VIS-08 **BLOCKED** (chưa có ảnh trong `docs/references/`); VIS-01..07, 09, 10 NOT_CHECKED. Đã dừng trước WP2 theo yêu cầu review.

## 6. Tiêu chí chấp nhận của slice
| ID | Tiêu chí | Cách kiểm |
|---|---|---|
| AC-VS-01 | Tất định: cùng config+seed ×2 → SHA-256 telemetry trùng (cùng môi trường) | PHY-01 + `make reproduce` |
| AC-VS-02 | Che khuất 2.5D đúng: người đi bộ sau xe tải không có trong detection của ego; có trong detection K1 khi trong FOV; kiểm biên và công thức `D=d·h_s/(h_s−h_o)` | PHY-07 |
| AC-VS-03 | Tracker CV-KF: NEES trung bình trong khoảng χ² 95% trên quỹ đạo tuyến tính tổng hợp | test thống kê |
| AC-VS-04 | Validator loại đúng lý do: stale, replay, `t_meas` tương lai, sai schema, nguồn lạ, mâu thuẫn quan sát trực tiếp; kênh khớp tham số | test đơn vị + PHY-08 |
| AC-VS-05 | CAL-1: EO-N không phanh va chạm ≥ 19/20 seed; CAL-0 oracle 0/20 | `make cal` |
| AC-VS-06 | I9: `ego/` không import truth; guard runtime | AST test |
| AC-VS-07 | Vòng kín E2: lệnh phanh sau `t_track_validated`, trong giới hạn I6; báo số va chạm kèm cận trên Wilson, **không** phát biểu "an toàn" khi N nhỏ | `make run` |
| AC-VS-08 | I2 (property): với mọi dãy track chia sẻ ngẫu nhiên, tốc độ cho phép cuối ≤ của EO-N. **Đây là kiểm một ràng buộc thiết kế, không chứng minh an toàn** | hypothesis |
| AC-VS-09 | Blackout (E4c) và rỗng-hoá dữ liệu chia sẻ cho lệnh trùng E0-N cặp seed (P1) | test cặp seed |
| AC-VS-10 | Telemetry hợp lệ schema; mọi phanh khẩn cấp có `tracks_used` hoặc `cause=local`; `invariant_violation`=0 | test + đếm |
| AC-VS-11 | Frontend nhận trạng thái có thẩm quyền (live WS + replay); số thực thể/giá trị hiển thị = telemetry tại `t_sim` | Playwright (đọc `window.__state`/DOM) |
| AC-VS-12 | Tái lập từ checkout sạch → cùng hash | CI sạch |
| AC-VS-13 | Registry không đổi (`git diff --stat` rỗng trên `data/refinery`), `refinery.py` PASS, `bites.py` PASS, REF_INTEGRITY PASS | `make check` |
| AC-VS-14 | Mọi báo cáo có khối "Giới hạn mô hình hoá" (07 §8) và `backend.metadata` | kiểm chuỗi tự động |
| AC-VS-15 | **PHY-01..08 đều PASS**, seed cố định, test tái lập một lệnh | `make test-physics` |
| AC-VS-16 | **VIS-01..07, VIS-09, VIS-10 đều PASS**; VIS-08 PASS hoặc ghi rõ BLOCKED kèm lý do (không được ngầm bỏ) | `make test-ui`, `make perf`, `make shots` |
| AC-VS-17 | Báo cáo hiệu năng đo thật trên máy tham chiếu đã khai báo; số đo sandbox gắn nhãn không đại diện | `perf/` |
| AC-VS-18 | Kết quả E0-N và E0-C luôn hiện diện cạnh nhau; không câu nào tuyên bố chia sẻ "đảm bảo an toàn hơn" | rà soát báo cáo |
**Slice chỉ được coi đạt khi AC-VS-15 ∧ AC-VS-16 cùng PASS** (một vế fail = fail).

## 7. Đặc tả frontend (tham chiếu 07 §10)
Công nghệ đề xuất: R3F + drei + Three.js (ADR-009). Lớp hiển thị bắt buộc là **đối tượng 3D thật** (không sprite 2D thay thế).
| Lớp | Nội dung | Ngữ nghĩa / ràng buộc |
|---|---|---|
| Thành phố | Đường + vạch + zebra + vỉa hè, ngã tư, toà nhà (≥3 kiểu), cây (≥2 loài), đèn tín hiệu, đồ đường phố, cột CCTV | instancing; một nguồn sáng định hướng chung |
| Tác tử | AV chi tiết (kính, đèn, 4 bánh quay thật, bánh trước lái), người đi bộ hoạt hoạ bước, xe tải | bánh quay `ω=v/r_w`; góc lái = δ (VIS-04) |
| Ground truth | Người đi bộ thật hiển thị kèm nhãn "truth — không AV nào thấy" | tách khỏi track |
| Cảm biến | Frustum CCTV; vùng thấy của ego; **vùng khuất** dựng từ polygon backend | VIS-05 |
| Track | Hộp/trụ theo lớp + elip 2σ từ covariance thật; màu theo tuổi; gạch/nhãn nếu bị từ chối | VIS-06; không chỉ dùng màu |
| Kế hoạch & an toàn | Đường kế hoạch, cung quãng dừng, vùng xung đột, TTC, huy hiệu chế độ, nguyên nhân phanh | từ đầu ra planner/gate |
| Truyền thông | Thông điệp bay nguồn → ego với độ trễ đúng | từ log kênh |
| Camera | Vehicle, CCTV, Bird's-eye, City overview + orbit/zoom/follow | VIS-02 |
| Telemetry | Biểu đồ v, a, TTC, AoI, trễ chặng, sự kiện; thanh thời gian (replay) | khung có thẩm quyền, không nội suy |
Chọn run (E0-N, E0-C, E2…) bằng chọn kịch bản/điều kiện (backend chạy/tải lại); **không** bật/tắt nguồn trong lúc chạy theo cách làm đổi vật lý. Đánh giá truy cập bằng skill `design:accessibility-review` ở WP6c.

## 8. Lệnh tái lập (đích; **chưa tồn tại**, tạo theo WP)
```bash
make setup         # WP0: cài phụ thuộc đã khoá (CẦN DUYỆT; cần mạng một lần)
make check         # WP0: REF_INTEGRITY + refinery + bites + registry không đổi + schema
make test-physics  # WP1-3: PHY-01..08 (seed cố định)
make test          # đơn vị, property, kịch bản
make cal           # WP4: CAL-0, CAL-1
make run SCEN=scenarios/s01_slice.yaml COND=E2 SEED=7
make serve         # WP5: backend WS + web build
make test-ui       # WP6b: Playwright (VIS-01..06, 10)
make shots         # WP6c: ảnh chụp từ frontend thật + manifest (VIS-09)
make perf          # WP6c: đo hiệu năng (VIS-07)
make reproduce RUN=<run_id>
```
Chạy được **hôm nay** (tài liệu phase 2):
```bash
python3 scripts/check_phase2_docs.py
python3 scripts/selftest_check_phase2_docs.py
python3 .claude/skills/refinery/refinery.py data/refinery/domains/smartcity-v2x-landscape
python3 .claude/skills/refinery/bites.py data/refinery/domains/smartcity-v2x-landscape
```

## 9. Rủi ro và ẩn số
| Rủi ro / ẩn số | Tác động | Giảm thiểu |
|---|---|---|
| **Ảnh tham chiếu chưa nhận** | VIS-08 BLOCKED; không biết "mức mục tiêu" cụ thể | Yêu cầu ảnh; điểm dừng V1; ngưỡng đặt sau khi có ảnh |
| Chất lượng thị giác tốn công mỹ thuật (WP6a/b cỡ XL) | Lịch; thất bại sản phẩm nếu kém | Dựng thủ tục có kiểm soát, vòng lặp chấm điểm sớm ở V1 |
| Không có GPU trong sandbox | Không đo được hiệu năng thật | Máy tham chiếu do chủ việc khai báo; số sandbox chỉ so hồi quy |
| Hiệu năng R3F (re-render React) | Tụt FPS | Đọc state qua ref, instancing, phương án dự phòng Three.js thuần |
| Tài sản ngoài: giấy phép/nguồn | Rủi ro pháp lý, provenance | Thủ tục trước; `web/ASSETS.md` bắt buộc |
| Tham số vật lý chưa có nguồn (V02, V03) | Kết quả phụ thuộc giả định | Quét độ nhạy; công bố trong giới hạn |
| Tất định liên nền tảng | Không tái lập giữa máy | Chỉ hứa bit-exact cùng môi trường; dung sai khác |
| Hình học che khuất sai làm H1 vô nghĩa | Hiệu chuẩn hỏng | CAL-0/CAL-1 cổng cứng |
| Nhầm "va chạm do dựng sẵn" với kết quả khoa học | Hiểu lầm | Nhãn CAL; 04 §3 |
| Slice quá đơn giản → fusion/association chưa bị thử | C03/C04 còn mở | Ghi trong báo cáo; MVP thêm nguồn |
| Chưa đọc CPM/SDSM mã hoá | `TrackMsg` lệch chuẩn | Ghi rõ "trường của dự án" |
