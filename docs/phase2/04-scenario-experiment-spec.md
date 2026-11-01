# 04 · Đặc tả kịch bản và thí nghiệm (T4)

Trạng thái: **DRAFT chờ duyệt**. Mọi `[PARAM]` là giá trị thiết kế chưa kiểm chứng. Không có kết quả thí nghiệm nào tồn tại; mọi mệnh đề "sẽ/phải" là kế hoạch. Toạ độ ở §2 là **minh hoạ**; giá trị cuối cùng do file cấu hình và lượt hiệu chuẩn CAL-0 quyết định.

## 1. Câu hỏi nghiên cứu và giả thuyết đăng ký trước
Câu hỏi: *chia sẻ track mức object có giảm rủi ro va chạm với người đi bộ bị che tại ngã tư — so với ego-only đủ năng lực — và phải trả giá gì?* (F09 UNKNOWN)
| ID | Giả thuyết | Tiêu chí bác bỏ (đặt trước) |
|---|---|---|
| H1 (hiệu chuẩn) | Kịch bản hợp lệ: EO-N va chạm ≥ 95% seed; oracle (thấy hết) va chạm 0% | Nếu sai, kịch bản vô hiệu — sửa cấu hình, **không** chạy E1–E4 |
| H2 | E2 và E3 với kênh danh định có tỉ lệ va chạm ≤ τ_col (do chủ việc đặt) | Cận trên Wilson 95% > τ_col |
| H3 (không tệ hơn) | Với mọi ô E4, tỉ lệ va chạm và khoảng cách tối thiểu không tệ hơn EO-N (cặp seed) | Bất kỳ ô nào tệ hơn EO-N ngoài CI |
| H4 | Phanh nhầm ở N1/N2 ≤ τ_fb (do chủ việc đặt) | Vượt ngưỡng |
| H5 (nhất quán mô hình) | Va chạm bắt đầu xuất hiện khi trễ chuỗi vượt ngân sách §3 ± dung sai | Điểm gãy lệch đáng kể → mô hình kênh/độ tươi sai, điều tra |
| H6 | Kết quả EX-ARCH áp dụng quy tắc đổi quyết định ở 03 §4 | Không áp dụng được → ghi UNKNOWN, không chọn |
| H7 (khai báo, không định hướng) | Báo cáo chênh lệch giữa E3 và EO-C về va chạm, thời gian qua đoạn, tỉ lệ hoàn tất | Không có tiêu chí thắng/thua; chỉ báo cáo |
**Giả thuyết này kiểm điều gì, không kiểm điều gì:** không giả định chia sẻ làm an toàn hơn ego-only; E0-N và E0-C là hai baseline riêng, và kết quả có thể là "không lợi" hoặc "gây hại" (ví dụ phanh gấp làm xe theo sau đâm đuôi). P1 là **ràng buộc thiết kế cần kiểm**, không phải tính chất đã chứng minh.
Ngưỡng τ_col, τ_fb, τ_assoc **chưa có**; chủ việc đặt trước khi chạy. Nếu không, các giả thuyết H2/H4 ở trạng thái NOT_CHECKED.

## 2. Kịch bản S01 · Người đi bộ bị che tại ngã tư
**Hình học (minh hoạ, đơn vị m):** ngã tư tâm (0,0); ego A1 chạy hướng bắc trên làn x=1.75; vạch qua đường tại y≈−10 (rộng 3); xe tải đỗ ở làn đậu bên phải, hộp x∈[4.0,6.5], y∈[−24,−14], che tầm nhìn từ ego tới vỉa hè bên phải cho tới khi ego còn ≈5–6 m cách vạch (kiểm bằng ray-casting, đầu ra CAL-0).
**Diễn viên:** A1 ego (mục tiêu: vượt ngã tư tới y=+30); A2 dừng ở nhánh vuông góc có tầm nhìn thẳng tới vạch; A3 chạy theo sau A1 cùng làn (cũng bị xe tải che — nên E1 chỉ có lợi nhờ A2, và đó là **kết quả hình học**, không phải đặc tính V2V nói chung); người đi bộ P đi từ vỉa hè bên phải ngang qua vạch với v_p ∈ U(1.2,1.6) m/s `[PARAM]`; xe tải tĩnh.
**CCTV:** K1 (cột phía tây vạch, thấy khu sau xe tải), K2 (làn tiếp cận), K3 (tâm ngã tư), K4 (đoạn bị che nhìn từ phía đối diện). Mỗi nút: FOV, tầm, pose, lỗi pose `[PARAM]`.
**Thời điểm xung đột:** người đi bộ được lập lịch để đến làn ego đúng lúc ego tới vạch nếu ego không phanh (`t_conflict` do cấu hình). `T_pre` = thời gian từ lúc K1 có track *xác nhận* tới `t_conflict` (mặc định 2.0 s, quét {1,2,3}) `[PARAM]`.
**Biến ngẫu nhiên:** v_p, jitter thời điểm xuất phát, nhiễu detector, jitter/mất gói kênh, tốc độ ban đầu ego ±5%.
**Biến thể phủ định (đo phanh nhầm):**
- **S01-N1:** người đi bộ chờ sau xe tải rồi *không* qua đường (không xung đột); đo chatter và phanh không cần thiết.
- **S01-N2:** tiêm "ma" (ghost) từ CCTV tại vạch khi không có ai; đo FM06/FM12.

## 3. Số học thiết kế (bản sửa theo Amendment A1; suy ra từ `[PARAM]`, không phải kết quả)
**Thay thế** bảng lý tưởng hoá của bản trước (quãng dừng 8.70 m / 14.49 m, vốn gộp độ trễ cảm nhận 0.35 s và bỏ qua giới hạn jerk): các số đó là **cận lạc quan** và không còn được dùng. Số dưới đây xuất phát từ mô hình actuator của 07 §2 (trễ thuần + giới hạn jerk + kẹp gia tốc) và khớp công thức đóng với tích phân số tới 0.3 mm. Sau khi PHY-03 chạy, **số do mô phỏng sinh ra là số có thẩm quyền**; bảng này chỉ để dựng dải quét.
Tham số: v₀ = 8.33 m/s (30 km/h) · t_pd = 0.20 s (cảm nhận+quyết định, tham số tính toán mô phỏng) · t_act = 0.15 s · phanh khẩn cấp a=6.0 m/s², j=10 m/s³ · phanh êm a=3.0 m/s², j=2.5 m/s³ · μ=0.8 (μg=7.85, nên a≤μg).
| Đại lượng | Khẩn cấp | Êm |
|---|---|---|
| Quãng dừng **từ lúc có lệnh phanh** | **9.45 m** | **17.64 m** |
| Quãng trôi trong t_pd (v₀·t_pd) | 1.67 m | 1.67 m |
| Tổng từ lúc ego thấy hiểm hoạ | **≈ 11.1 m** | **≈ 19.3 m** |
**Hệ quả thiết kế:** nếu ego chỉ thấy người đi bộ khi còn ≈5–6 m (hình học kịch bản ở §2) thì E0-N **không thể dừng kịp** (cần ≈11.1 m) → va chạm là kết quả *do dựng sẵn*; H1 chỉ kiểm dựng đúng. Mô phỏng sẽ báo **tốc độ va chạm** còn lại.
**Tốc độ ego-only thận trọng (EO-C):** `d_stop(v) = v·t_pd + x_phanh(v) ≤ d` (d = khoảng cách tới điểm xung đột), giải số:
| d (m) | 30 | 20 | 15 | 10 | 7 | 5 | 3 |
|---|---|---|---|---|---|---|---|
| v_sd (km/h), khẩn cấp | 55.8 | 43.6 | 36.4 | 28.0 | 22.0 | 17.4 | 12.0 |
Tốc độ thực dùng = min(v_sd, 30 km/h danh định, 40 km/h trần ODD). Đi 30 m cuối: EO-C mất **≈ 5.0 s** so với **3.5 s** danh định, tức chậm **≈ 1.5 s** mỗi lần tiếp cận (xấp xỉ: dừng tại điểm xung đột, bỏ qua việc thấy lại khi qua vật che). Đây là cận chi phí của baseline thận trọng và lý do F09 là câu hỏi mở (DEC-1).
**Ngân sách trễ chuỗi cảnh báo** (từ lúc K1 có track xác nhận tới lúc **lệnh phanh được phát**), d_det = v₀·T_pre:
| T_pre | d_det | Ngân sách phanh khẩn cấp | Ngân sách phanh êm |
|---|---|---|---|
| 2.0 s | 16.67 m | **≈ 0.87 s** | **−0.12 s (không khả thi)** |
| 3.0 s | 25.00 m | ≈ 1.87 s | ≈ 0.88 s |
Ngân sách gồm: đo→track, gửi, kênh, nhận/xác thực, fusion, t_compute. Với T_pre=2.0 s chỉ phanh khẩn cấp có thể cứu; phanh êm đã quá muộn ngay cả với kênh lý tưởng. Dải quét E4a (đến 1200 ms) vì thế cố ý vượt ngân sách để thấy điểm gãy (H5). G05 vẫn UNKNOWN: đây là suy ra từ tham số, không phải ngưỡng nguồn cho.

## 4. Điều kiện thí nghiệm
**Hiệu chuẩn (bắt buộc trước E0–E4, không báo như kết quả):**
- CAL-0 **Oracle:** ego có ground truth (chỉ để hiệu chuẩn, vi phạm I9 có chủ đích trong lượt này). Kỳ vọng 0% va chạm; ghi d_vis thực.
- CAL-1 **EO-N không phanh:** xác nhận va chạm do dựng sẵn.
**Điều kiện chính** (nguồn chia sẻ bật/tắt; mọi điều kiện chạy cả ba topology khi có CCTV):
| ID | Mô tả | Nguồn bật | Ghi chú |
|---|---|---|---|
| E0 | Ego-only. Hai chính sách: **E0-N** (danh định) và **E0-C** (thận trọng theo tầm nhìn) | không | E0-C là baseline đủ năng lực, bắt buộc báo cáo |
| E1 | V2V | A2, A3 → A1; CCTV tắt | Lợi ích phụ thuộc hình học A2 |
| E2 | V2I | K1–K4 → A1 (qua topology); V2V tắt | |
| E3 | Hợp tác đầy đủ | A2, A3, K1–K4 | × topology {CEN, DEC, HYB} = EX-ARCH |
| E4 | Kênh suy yếu (E3 + một yếu tố) | như E3 | các nhánh dưới |
**E4 — quét một yếu tố mỗi lần (OFAT), chọn thêm vài tổ hợp:**
| ID | Yếu tố | Dải `[PARAM]` | Liên hệ |
|---|---|---|---|
| E4a | Trễ kênh một chiều | {20, 50, 100, 200, 400, 800, 1200} ms (+jitter) | FM02, H5 |
| E4b | Mất gói | {0, 10, 30, 50, 80}% ngẫu nhiên; thêm mô hình burst (Gilbert–Elliott) | FM03 |
| E4c | Blackout | cửa sổ 0.5 s … toàn bộ; bắt đầu tại {trước, đúng, sau} lúc phát hiện | FM01, FM07, I7 |
| E4d | Đảo thứ tự/trùng lặp | xác suất {5, 20}% | FM04 |
| E4e | Phát lại thông điệp cũ | thông điệp trễ {1, 3, 10} s | FM05 |
| E4f | Ma từ nguồn (spoof) | tại vạch, thời lượng {0.5, 2} s | FM06 |
| E4g | Lệch đồng hồ nguồn | offset {0, ±100, ±500} ms; drift {0, 50 ppm} | FM09, B04 |
| E4h | Lệch pose CCTV | σ {0, 0.3, 1.0} m; bias {0, 0.5} m | FM08, A04 |
| E4x | Tổ hợp chọn lọc | (a)+(b) cao; (g)+(h) | chỉ nhánh có lý do |
**Phụ:** EX-ABL (có/không covariance; có/không chống đếm trùng — D03, C04), EX-TSYNC (có/không bù thời gian — B02), EX-ASSOC (mật độ nhiều người đi bộ — C03, mở rộng sau MVP).

## 5. Định nghĩa metric (tính từ ground truth trừ khi ghi khác)
| Metric | Định nghĩa vận hành |
|---|---|
| Collision | Hai hình bao vật lý (ego: OBB 4.5×1.8 m; người đi bộ: capsule r=0.3 m `[PARAM]`) giao nhau theo SAT, có kiểm không xuyên thủng (PHY-06) tại bất kỳ bước nào. Tỉ lệ = số run có ≥1 collision / N. |
| Near-miss | Run không collision nhưng khoảng cách hình bao tối thiểu < d_nm (1.0 m `[PARAM]`) **hoặc** TTC_min < τ_nm (1.5 s `[PARAM]`). Cả hai ngưỡng chưa có nguồn (F03 UNKNOWN); báo cáo kèm đường cong theo ngưỡng. |
| TTC | Tại mỗi bước: thời gian đến giao hình bao theo ngoại suy vận tốc không đổi của ego và người đi bộ; ∞ nếu không giao trong tầm H=6 s `[PARAM]`. Ghi TTC_min mỗi run và thời điểm. |
| False braking | Sự kiện giảm tốc > a_fb (2.0 m/s² `[PARAM]`) kéo dài ≥ 0.3 s mà trong cửa sổ đó TTC_truth ≥ H (không xung đột thật). Đo ở S01-N1/N2 và ở phần run sau khi xung đột đã hết. Báo cáo: số sự kiện/run, % run có ≥1 sự kiện, gia tốc cực đại, tổng thời gian trễ do phanh. |
| Route completion | Ego tới đường đích trong T_max (60 s `[PARAM]`) **và** không đứng yên > T_stall (5 s `[PARAM]`) trừ khi bắt buộc; ghi cả thời gian qua đoạn 30 m cuối. Va chạm ⇒ không hoàn tất. |
| AoI | Tại ego, cho đối tượng người đi bộ: `AoI(t)=t − t_meas` của track *được chấp nhận* mới nhất (sau xác thực), tính theo đồng hồ thật; báo cáo trung bình, đỉnh, p95 trong cửa sổ [t_conflict−6 s, t_conflict]; **AoI ước lượng** (bên nhận) ghi riêng; khác biệt thật–ước lượng là chỉ số mù (B04). |
| Latency | Phân rã bằng mốc thời gian: L₁ cảm biến→detection, L₂ detection→track xác nhận, L₃ gửi→kênh→nhận, L₄ nhận→xác thực→fusion, L₅ fusion→lệnh phanh, L_tổng = tổng. Báo cáo trung vị, p95, tối đa mỗi chặng. |
| Warning lead time | `t_conflict − t_track_đầu_tiên_được_chấp_nhận` (âm = không kịp). |
| Bandwidth | Byte/s mỗi liên kết = kích thước JSON mã hoá; **không** quy đổi sang CPM/SDSM (chưa đọc mã hoá). |
| Impact speed | Tốc độ tương đối ego–người đi bộ tại thời điểm va chạm (chỉ mô tả động học, không phải thước đo chấn thương). |
| Rủi ro xe theo sau | Chỉ ở MVP có A3 (hoặc follower ảo trong slice): TTC/khoảng cách tối thiểu của xe theo sau tới ego khi ego phanh; va chạm đuôi. Bắt buộc báo cáo vì phanh gấp do dữ liệu chia sẻ có thể gây rủi ro. |
| Comfort | Gia tốc/jerk cực đại; số lần phanh–nhả (chatter). |
| Invariant violations | Số `invariant_violation` (kỳ vọng 0; ≥1 = lỗi nghiêm trọng, chặn bàn giao). |
| Rejections | Số thông điệp theo `reason` (stale, replay, schema, contradiction, kinematic…). |

## 6. Thiết kế thống kê
- **Mẫu:** N = 100 seed mỗi ô `[PARAM]`. Với 0/100 va chạm, cận trên Wilson 95% ≈ 3.7% (quy tắc "3/N" ≈ 3%); với 0/200 ≈ 1.9%. N=100 **không** đủ để khẳng định tỉ lệ rất thấp; mọi kết luận về an toàn được phát biểu bằng cận trên, không bằng "0%".
- **Seed cặp:** cùng seed → cùng quỹ đạo người đi bộ và nhiễu cảm biến giữa các điều kiện (luồng ngẫu nhiên tách cho kênh), để so sánh cặp.
- **Phân tích đăng ký trước:** tỉ lệ → khoảng Wilson; liên tục → bootstrap 95% (percentile); so sánh cặp bằng hiệu seed-theo-seed. Không dò p-value, không bỏ run; run lỗi hạ tầng được báo riêng kèm lý do.
- **Ngưỡng cần chủ việc đặt trước khi chạy:** τ_col, τ_fb, τ_assoc. Chưa đặt = không đánh giá PASS/FAIL cho giả thuyết liên quan.
- **Sai khác với baseline:** mọi kết luận "hợp tác tốt hơn" phải nêu rõ so với E0-N hay E0-C.

## 7. Đe doạ tính hợp lệ (phải xuất hiện trong báo cáo kết quả)
1. Detector là mô hình thống kê trên ground truth, không đại diện YOLO/camera thật (D04, D05).
2. Mô phỏng mặt phẳng với xe đạp động học + vòng ma sát: không trượt lốp, truyền tải trọng, nhún; không thời tiết; không xe máy (V01, V02, V03, ODD-06). **Không tương đương CARLA.**
3. Kênh là mô hình tham số, không phải số đo V2X/5G (E04).
4. Một hình học, một kịch bản, người đi bộ theo kịch bản; kết quả không tổng quát hoá.
5. A2/A3 dựng sao cho E1 phụ thuộc hình học; không suy ra "V2V luôn kém hơn V2I".
6. Ngưỡng near-miss/TTC chưa có nguồn (F03).
7. Kết quả không chuyển giao sang thực địa (F05).
8. Số liệu băng thông là JSON, không phải CPM/SDSM.

## 7b. Điều kiện tiên quyết
Trước khi bất kỳ ô thí nghiệm nào được chạy hoặc công bố: PHY-01..08 phải PASS (02 §12.2), ngưỡng τ đã khoá, và manifest ghi `backend.metadata`. Kết quả chạy khi PHY chưa PASS bị vô hiệu.

## 8. Đầu ra
`results/<run_id>/{manifest.json, telemetry/*.jsonl, metrics.csv, summary.md}`; manifest gồm commit, config hash, seed list, schema_version, phiên bản thư viện. `summary.md` luôn mở đầu bằng khối "Giới hạn mô hình hoá" (§7). Lệnh dự kiến (chưa tồn tại, tạo ở WP tương ứng của tài liệu 05): `make cal`, `make experiments EXP=S01`, `make report`, `make reproduce RUN=<run_id>`.
