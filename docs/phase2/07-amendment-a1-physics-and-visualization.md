# 07 · Amendment A1 — Độ trung thực vật lý bắt buộc và trực quan hoá 3D cao cấp

Trạng thái: **DRAFT chờ duyệt. Chưa triển khai, chưa cài phụ thuộc, chưa commit/push.** Amendment này **thay thế** mọi chỗ trong 02–05 mô tả mô phỏng là "2D động học nhẹ" hoặc frontend là "replay tĩnh không backend". Các tham số `[PARAM]` chưa kiểm chứng; `[ENG]` là kiến thức kỹ thuật phổ thông, không phải nguồn trong registry.

## 0. Blocker: ảnh tham chiếu chưa được nhận
Bạn nhắc "supplied reference image". **Không có ảnh nào trong phiên này**: `/mnt/user-data/uploads`, `/mnt/attach`, thư mục repo đều trống (đã kiểm). Tôi **không mô tả hay suy diễn** nội dung ảnh. Hệ quả:
- Mục tiêu hình ảnh hiện chỉ dựa vào chữ của bạn: *premium stylized 3D / isometric smart-city diorama*.
- Cổng VIS-08 (so sánh với ảnh) ở trạng thái **BLOCKED** tới khi ảnh được cung cấp (đặt tại `docs/references/` và ghi SHA-256 vào manifest). Quy trình so sánh ở §10.7 đã thiết kế sẵn; ngưỡng và checklist đặc trưng sẽ chốt **sau khi ảnh có mặt và trước khi dựng**.
- Các cổng VIS khác không phụ thuộc ảnh vẫn đặc tả đầy đủ.

## 1. Bất biến kiến trúc và thứ tự bước
```
Physics ──► Perception ──► Communication ──► Fusion ──► Planning ──► Control ──► Physics
 (truth)   (sensor models)  (latency, loss)   (validated)  (EO-N/EO-C)  (actuator cmd)  (next step)
```
Frontend **chỉ tiêu thụ** trạng thái có thẩm quyền của backend (I10, I12). Không có đường điều khiển từ trình duyệt vào vật lý ngoài: chọn kịch bản/seed, play/pause/tốc độ phát, reset.
**Lịch bước cố định** (dt_phys = 10 ms `[PARAM]`; mọi tốc độ khác là bội số nguyên của dt_phys, tránh trôi thời gian):
| Tầng | Tần số `[PARAM]` | Ghi chú |
|---|---|---|
| Vật lý | 100 Hz | RK4 / tích phân chính xác cho phần đa thức |
| Cảm biến ego, CCTV | 10 Hz, pha riêng từng nguồn | mỗi khung có `t_meas` đúng mốc lấy mẫu |
| Truyền thông | theo lịch giao thông điệp | giao khi `t_deliver ≤ t_now` |
| Fusion + lập kế hoạch | 10 Hz | độ trễ tính toán là **tham số mô phỏng**, không đo wall-clock |
| Điều khiển | 50 Hz | lệnh giữ bậc 0 giữa hai lần cập nhật |
**Thứ tự trong một bước** (cố định để tất định): (1) áp lệnh đã có hiệu lực (sau trễ actuator) → (2) tích phân vật lý + va chạm → (3) lấy mẫu cảm biến nếu đến hạn → (4) giao thông điệp đến hạn → (5) chạy fusion/planning/control nếu đến hạn, lệnh mới có `t_effective = t_now + t_compute + t_act` → (6) ghi telemetry. Không bước nào đọc đồng hồ thật.

## 2. Mô hình vật lý xe (ego và AV)
**Trạng thái:** `[x, y, ψ, v, a, δ]` (vị trí điểm giữa trục sau, hướng, tốc độ, gia tốc dọc, góc lái). **Đầu vào:** `a_cmd` (gia tốc dọc yêu cầu), `δ_cmd` (góc lái yêu cầu).
**Động học (mô hình xe đạp động học `[ENG]`):** `ẋ = v cosψ ; ẏ = v sinψ ; ψ̇ = v tanδ / L ; v̇ = a`.
**Actuator:** `a` bám `a_cmd` qua (i) trễ thuần `t_act`, (ii) giới hạn jerk `|ȧ| ≤ j_max` (khác nhau cho nhấn phanh khẩn cấp và êm), (iii) kẹp `a ∈ [−a_brk, a_acc]`; góc lái bám `δ_cmd` với giới hạn tốc độ lái `|δ̇| ≤ δ̇_max` và `|δ| ≤ δ_max`.
**Ma sát (vòng ma sát `[ENG]`):** gia tốc ngang `a_y = v² tanδ / L`; yêu cầu `sqrt(a_x² + a_y²) ≤ μ g`. Vượt → kẹp tỉ lệ (ưu tiên phanh dọc khi khẩn cấp, được ghi `friction_limited=true`). Đây là **trừu tượng**, không phải mô hình lốp.
| Tham số | Mặc định | Ghi chú |
|---|---|---|
| Hình học OBB (D×R) | 4.5 × 1.8 m | `[PARAM]` |
| Chiều dài cơ sở L | 2.7 m | `[PARAM]` |
| Bán kính bánh | 0.32 m | `[PARAM]`; dùng cho quay bánh (VIS-04) |
| δ_max | 35° → R_min = L/tanδ = **3.86 m** | `[PARAM]` |
| δ̇_max | 0.6 rad/s | `[PARAM]` |
| μ khô | 0.8 → μg = **7.85 m/s²** | `[PARAM]`; ODD loại mưa; ẩm 0.5 chỉ làm độ nhạy (μg = 4.91) |
| t_act | 0.15 s | `[PARAM]` |
| j_max khẩn cấp / êm | 10 / 2.5 m/s³ | `[PARAM]` |
| a_brk khẩn cấp / êm | 6.0 / 3.0 m/s² (≤ μg) | `[PARAM]` |
Bài học ngay từ mô hình này: quãng dừng **từ lúc có lệnh phanh** (v₀=8.33 m/s, a=6, j=10, t_act=0.15) là **9.45 m** (công thức đóng và tích phân số khớp tới 0.3 mm), lớn hơn con số lý tưởng 8.70 m đã dùng ở bản trước (vốn gộp cả độ trễ cảm nhận). Với phanh êm (a=3, j=2.5) là **17.64 m**. Các số trong 04 §3 vì vậy là **cận lạc quan** và được thay bằng số từ mô hình này (xem 04 §3 bản sửa).
**Công thức đóng cho PHY-03 (phanh khẩn cấp đạt a_c):** `t_r = a_c/j ; v_r = v₀ − j t_r²/2 ; d = v₀ t_act + v₀ t_r − j t_r³/6 + v_r²/(2 a_c)`.
**Miền hợp lệ:** mô hình xe đạp động học chỉ dùng khi `a_y ≤ 0.5 μ g` `[PARAM]` và v ≤ ODD; vượt ngưỡng → cảnh báo `outside_model_validity` và kịch bản không được dùng để kết luận.

## 3. Người đi bộ, va chạm, tương tác
- **Người đi bộ:** tác tử động học đi theo đường chấp điểm với profile tốc độ (hằng hoặc từng đoạn); hình bao **capsule** bán kính 0.3 m `[PARAM]`; **không phản ứng** với xe (giới hạn đã biết: không gap-acceptance, không social force).
- **Va chạm:** SAT giữa OBB xe và capsule người; OBB–OBB giữa xe với xe/xe tải. Phát hiện liên tục (swept) hoặc chứng minh bằng bất đẳng thức `v_max·dt < 0.5·r_min` (11.1 m/s·0.01 s = 0.11 m < 0.15 m) để không xuyên thủng; test PHY-06 kiểm.
- **Sau va chạm:** latch sự kiện, ghi **tốc độ va chạm tương đối** và điểm chạm, rồi kết thúc kịch bản. **Không** có mô hình chấn thương, biến dạng hay động lực học sau va chạm.

## 4. Cảm biến: FOV, che khuất 2.5D, bất định
- **Hình học 2.5D:** cảm biến có độ cao `h_s`; vật cản (xe tải, xe, toà nhà) có độ cao `h_o`; đối tượng được lấy mẫu tại chân, thân, đầu. Đối tượng **thấy được** nếu ít nhất một điểm mẫu có tia không bị chặn. Vì camera cột cao (≈6 m `[PARAM]`) nhìn qua xe tải thấp hơn nó, mô hình 2D thuần sẽ **đánh giá quá mức** vùng khuất của CCTV; xe (h_s≈1.5 m) bị xe tải 3 m che hoàn toàn. Kiểm chứng giải tích: tia sượt qua mép trên vật cản tại khoảng cách ngang d chạm đất ở `D = d·h_s/(h_s − h_o)` (đồng dạng tam giác; chỉ khi h_s > h_o).
- **Mô hình đo:** FOV (góc, tầm), xác suất phát hiện theo tầm `p_d(r)` (logistic `[PARAM]`), nhiễu vị trí `σ(r)`, bias hiệu chuẩn (extrinsics), miss/false positive theo tham số, `t_meas` theo mốc lấy mẫu, độ trễ xử lý cảm biến `t_proc`. Đây là **mô hình thống kê trên ground truth**, không phải detector học máy (R-PER-03).
- **Hạn chế:** không có suy giảm thời tiết, không rolling shutter, không méo quang học.

## 5. Truyền thông, độ tươi, thời gian tính toán
- Kênh: trễ cố định + jitter, mất gói ngẫu nhiên/burst, blackout, đảo thứ tự, trùng lặp, phát lại (04 §4). Mỗi thông điệp có `t_meas, t_sent, t_deliver`.
- **AoI** tính theo đồng hồ mô phỏng thật; **AoI ước lượng** (bên nhận) tính riêng (ADR-004).
- **Thời gian tính toán** của fusion/planning là tham số (`t_compute`), không đo bằng wall-clock, nên kết quả khoa học **không phụ thuộc hiệu năng máy chạy**.

## 6. Quy tắc tất định
float64 toàn bộ; không dùng thao tác song song không xác định thứ tự; RNG `numpy.random.Generator(PCG64)` sinh từ `SeedSequence` với luồng riêng cho: người đi bộ, cảm biến từng nguồn, kênh; không dùng thứ tự duyệt `set`; telemetry tuần tự hoá canonical (khoá sắp xếp, float dạng ngắn nhất khả hồi) rồi băm SHA-256. **Tất định bit-exact chỉ được hứa trong cùng môi trường** (phiên bản Python/numpy/OS ghi vào manifest); giữa các máy dùng so sánh theo dung sai. Không tuyên bố tái lập bit-exact liên nền tảng khi chưa kiểm.

## 7. Kế hoạch xác thực vật lý (tóm tắt; bảng chính thức ở 02 §12)
| ID | Kiểm | Chuẩn đối chiếu (giải tích/tham chiếu) | Dung sai `[PARAM]` |
|---|---|---|---|
| → PHY-01 | Tất định và bất biến theo bước thời gian thật | Hai lần chạy + chạy với trễ wall-clock tiêm vào + tắt render → cùng hash | bit-exact cùng môi trường |
| → PHY-02 | Động học tuyến tính | `x = x₀ + v₀t + ½at²`, `v = v₀ + at` | ≤ 1e-6 m |
| → PHY-03 | Quãng dừng và ma sát | Công thức đóng §2; lưới v₀∈{5,7,9,11} m/s × {êm, khẩn cấp} × μ∈{0.5,0.8}; kèm tích phân tham chiếu bước nhỏ độc lập | ≤ 1 mm so công thức, ≤ 5 mm so tham chiếu |
| → PHY-04 | Lái và quay đầu | Vòng tròn `R = L/tanδ`; sau thời gian `t` hướng đổi `v t / R`; kẹp ma sát tại `v² tanδ/L = μg` | ≤ 1e-3 rad, ≤ 1 mm bán kính |
| → PHY-05 | Giới hạn gia tốc và jerk | Mọi mẫu `|a| ≤ a_brk`, `|ȧ| ≤ j_max`, `|δ̇| ≤ δ̇_max`; cắt đúng khi bị yêu cầu vượt | 0 vi phạm |
| → PHY-06 | Va chạm hình học | Bảng ca giải tích: chạm mép, chồng lấn, tách rời, xoay góc; không xuyên thủng ở tốc độ lớn nhất | 0 sai trên bảng |
| → PHY-07 | Cảm biến | FOV biên; ray-cast; che khuất 2.5D `D = d h_s/(h_s−h_o)`; thống kê nhiễu và `p_d(r)` khớp tham số | χ² 95% |
| → PHY-08 | Truyền thông và độ tươi | Lịch giao thông điệp biết trước → AoI răng cưa tính tay; thống kê trễ/mất/jitter khớp tham số | chính xác tuyệt đối với lịch xác định |
**"Trusted reference":** các bài giải tích trên là chuẩn tin cậy duy nhất hiện có và độc lập với mã mô phỏng. Chưa có tham chiếu bên ngoài; đối chiếu chéo với CARLA là cổng **tương lai** PX-1 (định nghĩa ở §9), **không** được tuyên bố đã làm.

## 8. Giới hạn trung thực (bắt buộc xuất hiện trong mọi báo cáo kết quả)
1. Mặt phẳng nằm ngang, không dốc/độ cao đường; hệ phẳng với cảm biến 2.5D.
2. Xe đạp động học + vòng ma sát; **không** có trượt lốp, truyền tải trọng, nhún, chúi đầu khi phanh, khí động, lực cản lăn (hoặc chỉ hằng số tham số).
3. Ma sát đồng nhất, không đổi theo vị trí/thời tiết; giá trị μ là tham số, **chưa có nguồn cho đường nội khu Việt Nam**.
4. Hình bao cứng; không biến dạng; chạm = kết thúc.
5. Người đi bộ không phản ứng; không có hành vi đám đông.
6. Cảm biến thống kê trên ground truth; kênh là mô hình, không phải PHY/MAC V2X thật.
7. Đồng hồ nút là mô hình (offset/drift) tham số.
8. **Không tương đương CARLA** (hay bất kỳ bộ sim thương mại nào) về độ trung thực; kết quả chỉ có giá trị trong mô hình.
9. Chỉ hợp lệ trong ODD: v ≤ 40 km/h, `a_y ≤ 0.5 μ g`, trời quang.
10. (Phát hiện ở WP1, làm rõ ở WP2) **Mô hình không thể bảo đảm giới hạn jerk tại v=0:** nếu xe được lệnh phanh tới khi dừng, gia tốc nhảy về 0 trong một bước (jerk tương đương |a|/dt, vd 600 m/s³). Điều này được **báo bằng sự kiện** `standstill_jerk_discontinuity` trong telemetry (không còn là ngoại lệ ngầm); giới hạn chỉ được đáp ứng khi bộ điều khiển nhả phanh về ~0 khi v→0 (soft-stop, có test).
11. Ramp gia tốc không kết thúc đúng ranh giới bước (vd μ=0.5) có sai số quãng dừng đo được ≤ 4.7e-5 m (do giả thiết tuyến tính trong bước).

## 9. Giao diện tích hợp CARLA tương lai (không triển khai, không tuyên bố tương đương)
Cắt đường nối ở biên **vật lý + cảm biến**, giữ nguyên Perception→…→Control phía trên.
```python
class PhysicsBackend(Protocol):
    def reset(self, scenario: ScenarioConfig, seed: int) -> None: ...
    def step(self) -> None: ...                       # tiến đúng một dt_phys
    def apply_control(self, actor_id: str, ctrl: ControlCmd) -> None: ...  # a_cmd, δ_cmd + t_issue
    def truth(self) -> WorldTruth: ...                # chỉ dành metrics, UI, và SensorProvider
    def time(self) -> float: ...                      # đồng hồ mô phỏng
    def metadata(self) -> BackendMetadata: ...        # tên, phiên bản, dt, các giới hạn trung thực

class SensorProvider(Protocol):
    def sample(self, sensor_id: str, truth: WorldTruth, t: float) -> SensorFrame: ...
```
- `LightweightBackend` (mặc định): §2–§4. `CarlaBackend`: **chưa triển khai**; khi làm, phải có lớp dịch `ControlCmd(a_cmd, δ_cmd) → throttle/brake/steer` và lớp dịch hệ toạ độ, **cả hai chưa được xác thực**.
- Mọi kết quả ghi `backend.metadata` để không trộn số liệu giữa hai backend.
- PX-1 (tương lai) · cổng đối chiếu chéo: đối chiếu chéo phanh/lái giữa hai backend trong dung sai do chủ việc đặt. Cho tới khi PX-1 PASS, không có phát biểu nào về tương đương. Tính tất định của CARLA trên các máy khác nhau là điều **chưa biết**, phải kiểm khi tích hợp. Framework co-sim đã có tiền lệ trong tài liệu (C26·OpenCDA), nhưng chưa đọc chi tiết nên không dùng làm bằng chứng cho khả năng tất định.

## 10. Trực quan hoá 3D cao cấp
### 10.1 Lựa chọn công nghệ (ADR-009)
| Lựa chọn | Ưu | Nhược | Quyết định đề xuất |
|---|---|---|---|
| **React Three Fiber + drei + Three.js** | Cảnh khai báo, tái sử dụng thành phần, UI/overlay/panel cùng cây React, hệ sinh thái hậu kỳ (shadow, instancing, post) | Cần bước build; rủi ro hiệu năng nếu để React render mỗi khung | **Đề xuất.** Quy tắc: vòng render đọc trạng thái qua `ref`/store ngoài React, không `setState` mỗi khung |
| Three.js thuần (ES modules, không build) | Ít phụ thuộc, kiểm soát vòng lặp | Tự dựng UI, ít tái sử dụng, dễ thành code rối khi cảnh lớn | Phương án dự phòng nếu R3F không qua cổng hiệu năng |
| Babylon.js | Công cụ mạnh, inspector | Hệ sinh thái React kém, bạn đã quen Three | Không chọn |
| deck.gl / Cesium | Hợp bản đồ địa lý | Không hợp diorama cục bộ chất lượng cao | Không chọn |
Phụ thuộc phải được duyệt trước khi cài (chưa cài): `react`, `react-dom`, `three`, `@react-three/fiber`, `@react-three/drei`, `zustand`, `vite`, `typescript` (tuỳ), cùng `fastapi`/`uvicorn`/`websockets` phía backend. Ghim phiên bản ≥ 2 tuần tuổi và băm khoá (lockfile); vendoring để chạy offline.

### 10.2 Danh mục đối tượng 3D bắt buộc (không dùng icon 2D thay thế)
Đường và làn có vạch kẻ, vạch sang đường (zebra), vỉa hè; ngã tư; **nhiều kiểu toà nhà** (khối, mái, cửa sổ phát sáng theo emissive map); cây đa dạng (instancing); đèn tín hiệu và cột đèn; bàn ghế/thùng rác/trạm xe buýt/biển báo; cột CCTV với camera 3D; xe tự hành chi tiết (thân, kính, đèn, **4 bánh quay**, bánh trước lái); xe tải đỗ; người đi bộ có mô hình 3D có hoạt hoạ bước đi gắn với tốc độ thật; mặt đất/đồ nền kiểu diorama (đế nổi, viền). Tài sản: **dựng thủ tục (procedural) trước**; nếu dùng mô hình glTF ngoài, mỗi tài sản phải có bản ghi nguồn + giấy phép trong `web/ASSETS.md` (đồng nhất với tinh thần provenance); không tải tài sản khi chưa được duyệt.

### 10.3 Ánh sáng, bóng, vật liệu
Một nguồn sáng định hướng chính chung cho mọi vật đổ bóng (bóng **nhất quán**), shadow map phân giải đủ để bóng xe/xe tải/người nhìn rõ, ambient/hemisphere nhẹ, tone mapping, vật liệu PBR phong cách hoá, emissive cho đèn xe/tín hiệu/cửa sổ. Hậu kỳ (ambient occlusion, bloom nhẹ) có thể bật nhưng phải tắt được và không che dữ liệu khoa học.

### 10.4 Chế độ camera
Bốn chế độ bắt buộc: **Vehicle** (góc nhìn ego/chase, có chế độ POV), **CCTV** (từ từng cột, hiển thị đúng FOV), **Bird's-eye** (nhìn từ trên), **City overview** (isometric diorama). Orbit, zoom, pan mượt (damping) và **follow** bám xe. Chuyển chế độ có chuyển động liên tục, không nhảy.

### 10.5 Lớp trực quan hoá cooperative perception
Track (hộp 3D/trụ theo lớp) có **elip bất định** dựng từ covariance thật trong telemetry; **FOV frustum** dựng từ tham số cảm biến thật; **vùng khuất** dựng từ đa giác che khuất backend (VIS-05); **đường kế hoạch** từ đầu ra planner; nhãn nguồn/tuổi dữ liệu; thông điệp bay giữa nguồn → ego (đường cung/hạt) với độ trễ đúng; huy hiệu chế độ (`EO-N`, `coop_lost`…), nguyên nhân phanh. Không truyền thông tin chỉ bằng màu (ký hiệu + nhãn chữ).

### 10.6 Tiêu thụ trạng thái và tách khỏi FPS
Backend chạy bước cố định và phát khung trạng thái (có `t_sim`) ở 25–50 Hz `[PARAM]` qua WebSocket (live) hoặc ghi JSONL (replay). Frontend giữ bộ đệm vài khung, nội suy Hermite theo `t_sim` (dùng v, ψ̇) với độ trễ hiển thị cố định, **chỉ để vẽ**; mọi số trên màn hình lấy từ khung có thẩm quyền, không từ đại lượng nội suy. Chế độ `paced` (1×) cho xem trực tiếp, `free-run` cho thí nghiệm; hai chế độ cho cùng telemetry (PHY-01, VIS-10).

### 10.7 Giao thức bằng chứng hình ảnh và so sánh ảnh tham chiếu
1. **Ảnh chụp từ frontend đang chạy thật** (Playwright điều khiển trình duyệt nạp bản build, kết nối backend thật); manifest kèm commit, hash bản build, chuỗi `renderer` WebGL, độ phân giải, seed, `t_sim`. Mockup, ảnh dựng tay, ảnh render ngoài không được tính.
2. **Khung "hero" cố định** tái tạo góc nhìn của ảnh tham chiếu (khi có) ở 1920×1080; cùng khung cho hàng loạt phiên bản để so sánh tiến bộ.
3. **So sánh với ảnh tham chiếu:** ghép cạnh nhau + **thang đánh giá có cấu trúc** (bố cục diorama, mật độ chi tiết, chất lượng vật liệu/ánh sáng/bóng, bảng màu, chiều sâu, đọc được thông tin nghiệp vụ…), mỗi tiêu chí 0–2 điểm bởi ≥ 2 người chấm (chủ việc + một người khác). **Ngưỡng điểm do chủ việc đặt sau khi xem ảnh và trước khi dựng.** Thước đo tự động (SSIM, v.v.) **không** dùng làm cổng vì hai cảnh khác nội dung.
4. Chế độ hỏng (hình ảnh kém đáng kể) = **thất bại sản phẩm cuối**, bất kể vật lý đúng (§12).

### 10.8 Giao thức đo hiệu năng
Đo trong trình duyệt: thời gian khung (p50/p95/p99), FPS, số draw call, số tam giác, số đối tượng instanced, bộ nhớ GPU ước lượng, thời gian cập nhật trạng thái, trên **máy tham chiếu do chủ việc khai báo** (CPU/GPU/độ phân giải). **Sandbox hiện tại không có GPU**; số đo trong sandbox (render phần mềm) chỉ để phát hiện hồi quy tương đối, **không** được báo như hiệu năng sản phẩm. Ngân sách đề xuất `[PARAM]`: p50 ≥ 60 FPS, p95 khung ≤ 22 ms, sàn ≥ 30 FPS trên máy tham chiếu; ngân sách tam giác/draw call đặt ở WP6c sau khi biết máy.

## 11. Ngoại lệ về tính trung thực nghiên cứu (giữ nguyên)
- **E0-N và E0-C vẫn là hai baseline riêng**, luôn cùng xuất hiện trong bảng.
- **Không tuyên bố** chia sẻ góc nhìn đảm bảo an toàn hơn ego-only. Ngược lại, phanh gấp do dữ liệu chia sẻ có thể gây **rủi ro cho xe theo sau** (A3 đâm đuôi); metric "rủi ro xe theo sau" được thêm ở MVP (04 §5).
- **P1 là ràng buộc thiết kế cần kiểm** (AC-M13, AC-M15, PHY-liên quan), **không** phải tính chất an toàn đã chứng minh.
- Toàn bộ evidence, báo cáo gate và artifact provenance cũ được giữ nguyên (không sửa registry, snapshot, claim, commit cũ).

## 12. Logic chấp nhận sản phẩm cuối
`Chấp nhận = PHY-01..08 đều PASS ∧ VIS-01..10 đều PASS ∧ cổng nghiên cứu (REF/ID/AC-M) PASS ∧ giới hạn được công bố.` Thiếu một vế → **không chấp nhận**: frontend đẹp nhưng vật lý sai thất bại; vật lý đúng nhưng hình ảnh kém rõ rệt so với mức mục tiêu cũng thất bại.

## 13. Câu hỏi mở / cần chủ việc
1. **Cung cấp ảnh tham chiếu** (chặn VIS-08).
2. Máy tham chiếu để đo hiệu năng và ngưỡng FPS.
3. Duyệt danh sách phụ thuộc §10.1 và việc vendoring.
4. Cho phép tài sản glTF ngoài hay chỉ dựng thủ tục.
5. Giá trị μ, t_act, j_max có nguồn nào bạn muốn dùng (hiện UNKNOWN trong registry).
