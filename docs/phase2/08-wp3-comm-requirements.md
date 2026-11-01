# 08 · WP3 — V2X Communication & TrackMsg: yêu cầu, lý do, bằng chứng, giả thuyết, ca lỗi, kiểm thử

Trạng thái: **ĐÃ DUYỆT PHẠM VI bởi chủ việc** (WP3 only; không WP4/WP5/thành phố). Mọi yêu cầu bên dưới là **yêu cầu mới hoặc đã đổi**; theo AI-Native mỗi yêu cầu có lý do, bằng chứng (nếu có), giả thuyết/ẩn số, ca lỗi và kiểm thử thực thi. **Không có nguồn nào được bịa**: chỗ nào registry không có bằng chứng thì ghi UNKNOWN.
Ngưỡng: `comm/thresholds.json` được khai báo **trước** mọi benchmark (SHA-256 ghi ở báo cáo WP3). `invariant` = phải đúng tuyệt đối, chứng minh bằng test thực thi (không phải bằng nguồn ngoài); `provisional_design` = giá trị thiết kế tạm, **không có nguồn ngoài**; `report_only` = chỉ báo cáo.

## 1. Quyết định của chủ việc áp dụng cho WP3
| # | Quyết định | Hệ quả thiết kế |
|---|---|---|
| 1 | Xuất bản track đã xác nhận lên V2X dùng **3-of-4**; giữ 2-of-3 làm baseline thực nghiệm | `Publisher` từ chối tracker không phải 3-of-4 trừ khi `experimental=True`; thông điệp ghi `confirmation` trong provenance; receiver mặc định **từ chối** thông điệp thực nghiệm |
| 2 | Giữ nguyên các ca hợp nhất người đi bộ gần nhau / đổi ID nghiêm trọng như **known failure tường minh** | `tests/perception/test_known_failures.py` dùng `xfail(strict=True)`; `make check` liệt kê riêng, không tính PASS |
| 3 | Track ID **gắn theo nguồn**, không phải định danh toàn cục | Khoá luôn là `(origin.source_id, track_id)`; relay giữ nguồn gốc, không đổi phạm vi ID |
| 4 | Giữ ràng buộc an toàn **P1** | Dữ liệu V2X chỉ tư vấn, chỉ có thông tin dương (có object); không có ngữ nghĩa "trống/an toàn"; thiếu/stale/bị từ chối = bỏ qua, **không** = trống (I3) |
| 5 | Không tuyên bố tuân thủ jerk tại v=0 khi phanh khẩn cấp | Không đụng tới; ghi lại ở mục giới hạn |
| 6 | Không định nghĩa lại cổng PHY/VIS | PHY-08 được cài **đúng định nghĩa PRD §12.2** (xem §5); COM-01..10 là cổng **mới** của WP3 |

## 2. Hợp đồng TrackMsg 0.2.0 — thay đổi so với bản nháp 0.1.0 trong PRD §8.1
| Thay đổi | Lý do | Bằng chứng |
|---|---|---|
| Tách **danh tính truyền** `tx` {node_id, tx_seq, clock_id} khỏi **danh tính quan sát** `origin` {source_id, orig_seq, orig_msg_id, clock_id, clock_sync, provenance} | Yêu cầu "giữ nguyên thời điểm quan sát qua truyền lại/relay" và "ID theo nguồn" | Không có nguồn trong registry cho relay; thiết kế riêng (UNKNOWN: ánh xạ CPM/SDSM, A06) |
| Bốn mốc thời gian tách bạch: `t_meas` (quan sát, đồng hồ nguồn), `t_sent` (truyền, đồng hồ nút gửi), `t_recv` và `t_proc` (phía nhận, **không nằm trong thông điệp**) | Yêu cầu phân tách; tránh nhầm "tuổi thông tin" với "độ trễ mạng" | S01b:975~referenceTime ; S01b:819~T_GenCpm ; CPM có `referenceTime` và chu kỳ sinh (B03 SUPPORTED, chưa claim) |
| Khai báo tường minh `frame`="map", `origin_id`, `units`, `yaw_convention` | "Không chấp nhận âm thầm biến đổi toạ độ không hỗ trợ" | B01 VERIFIED ; C14·DAIR-V2X ; nêu bất đồng bộ là vấn đề thật ; A06 SUPPORTED (S01b:1262~referenceTime) |
| `ttl_s`, `hop_count`, `relay_path` | TTL, giới hạn relay, phát hiện vòng lặp | Không có nguồn (thiết kế) |
| `t_upd` mỗi track (lần cập nhật đo thật cuối) | AoI thông tin ≠ thời điểm trạng thái; track đang coasting không được coi là tươi | Thiết kế; liên quan C30·CPS redundancy (chỉ nói redundancy) |
Schema chính thức: `schemas/trackmsg.schema.json`. Phiên bản không khớp → từ chối `unsupported_version` (không đoán).

## 3. Yêu cầu
| ID | Yêu cầu | Lý do | Bằng chứng | Giả thuyết / ẩn số | Ca lỗi (phải xử lý) | Kiểm thử thực thi |
|---|---|---|---|---|---|---|
| R-MSG-01 | Hợp đồng TrackMsg 0.2.0 có phiên bản, JSON Schema, changelog | Hợp đồng dữ liệu bắt buộc của WP3 | PRD §8.1 (bản nháp) | A06, D01: mã hoá CPM/SDSM chưa đọc; tên trường là của dự án | Phiên bản lạ; trường lạ; thiếu trường | `tests/comm/test_com01_trackmsg_contract.py` |
| R-MSG-02 | Tuần tự hoá chuẩn tắc, giải tuần tự hoá nghiêm ngặt, round-trip chính xác từng bit | Tất định + so khớp byte | — | Băng thông là của JSON, **không** phải CPM/SDSM (W3H-1) | JSON hỏng, UTF-8 hỏng, quá lớn, bool thay số | COM-01 |
| R-MSG-03 | Đơn vị và quy ước toạ độ tường minh; frame/origin/units/yaw sai → từ chối | Không biến đổi âm thầm | B01 (C14·DAIR-V2X) | Chưa có biến đổi toạ độ nào được hỗ trợ; mọi biến đổi bị từ chối | `frame`≠map, origin lạ, units lạ, yaw convention lạ | COM-07 |
| R-TIM-01 | Bốn mốc thời gian tách bạch + mô hình đồng hồ (offset, drift) từng nút; tuổi **ước lượng** (phía nhận thấy) tách khỏi tuổi **thật** (chỉ phía đánh giá) | Yêu cầu phân tách; B04 UNKNOWN | S01b:975~referenceTime | B04: độ chính xác đồng bộ UNKNOWN; dung sai đồng hồ 50 ms là PARAM | Lệch đồng hồ ±; drift; thời điểm tương lai | COM-04 |
| R-TIM-02 | Chỉ dùng đồng hồ mô phỏng; không phụ thuộc wall-clock hay tốc độ render | Kết quả khoa học tách khỏi FPS (I11) | — | — | Observer ngủ ngẫu nhiên; PYTHONHASHSEED | COM-02 |
| R-CHN-01 | Kênh sự kiện rời rạc tất định: trễ, jitter, mất (Bernoulli và Gilbert–Elliott), trùng lặp, đảo thứ tự, hỏng byte, blackout, băng thông + hàng đợi | R-COM-01 của PRD, mức chi tiết hơn | S14:186~under varying latency ; FHWA ghi đánh giá dưới trễ/mất gói/lỗi là việc tương lai (E01 UNKNOWN) | E04: mô hình kênh không đại diện V2X thật (UNKNOWN) | Mất cả loạt; trùng lặp muộn; đảo thứ tự; queue tràn | `test_com03_channel_statistics.py`, PHY-08 |
| R-CHN-02 | Replay tất định; tiêu thụ số ngẫu nhiên cố định mỗi gói (ghép cặp seed) | Hệ quả bài học WP2 (RNG phụ thuộc visibility) | — | — | Seed khác; thứ tự gửi | COM-02 |
| R-AOI-01 | AoI theo **thời điểm quan sát**: `t − freshest t_meas đã nhận`; bản cũ/trùng/relay không làm giảm tuổi; tính chính xác theo lịch biết trước | Yêu cầu của chủ việc; PHY-08 của PRD | B01 | B06: ngưỡng độ tươi UNKNOWN | Đến muộn bản cũ; trùng lặp; relay | COM-05, PHY-08 |
| R-ADM-01 | Admission phía nhận **fail-closed**, theo thứ tự cố định, mã lý do duy nhất; reject không đổi trạng thái quyết định | Không để NaN/Inf, cov sai, seq trùng, timestamp sai, malformed tới fusion (WP4) | — | Mâu thuẫn quan sát trực tiếp (AC-VS-04) chỉ có kiểm tra xung đột lớp; phần còn lại thuộc WP4 | Mọi mã lý do (`REASONS`) | COM-06 |
| R-ADM-02 | Chính sách seq/replay/reorder: trùng nội dung bị loại; cửa sổ reorder W; ngoài cửa sổ = replay cũ | Chống replay (FM05), trùng (FM04) | — | W=8 là PARAM | Phát lại; trùng qua relay | COM-06, COM-08 |
| R-ADM-03 | TTL do nguồn khai + tuổi tối đa do receiver; bản "tương lai" quá dung sai bị loại | FM02, FM09 | — | B06; dung sai PARAM | Stale; hết TTL; t_meas tương lai | COM-04, COM-06 |
| R-SRC-01 | Allowlist nguồn, provenance bắt buộc, khoá track = `(source_id, track_id)` | Quyết định 3; I5 | E05: spec CPM chỉ tham chiếu bảo mật (C36·ETSI TS 103 324) | **E05/E06 UNKNOWN**: chưa có xác thực mật mã → nguồn giả hợp lệ-allowlist **không phát hiện được** (known failure) | Nguồn lạ; trùng track_id giữa hai nguồn; giả mạo | COM-07, known failures |
| R-REL-01 | Relay giữ `t_meas`, `origin`, tăng `hop_count`, ghi `relay_path`; chống vòng; khử trùng bản trực tiếp + relay | Yêu cầu "giữ thời điểm quan sát qua relay" | — | Không có nguồn về relay; thiết kế | Vòng lặp; vượt hop; relay làm "tươi giả" | COM-08 |
| R-TEL-01 | Telemetry truyền thông JSONL chuẩn tắc + SHA-256 + đẳng thức kế toán | Quan sát được; replay | — | — | Sự kiện thiếu/đếm sai | COM-09 |
| R-POL-01 | Xuất bản: chỉ track đã xác nhận 3-of-4; 2-of-3 chỉ ở chế độ thực nghiệm có nhãn; chỉ khi có quan sát mới | Quyết định 1 | WP2: track giả 4.65%/frame ở 2/3 vs 0.15% ở 3/4 (số đo trong mô phỏng WP2, không phải nguồn ngoài) | Chưa biết tác động độ trễ xác nhận lên an toàn (F09) | Tracker sai cấu hình; republish nội dung cũ như mới | COM-10 |
| R-POL-02 | P1: tư vấn, chỉ thông tin dương; thiếu/stale/reject ≠ trống | Quyết định 4; I2, I3 | D02 SUPPORTED (S01b:846~shadowingApplies ; spec có khái niệm vùng quan sát; chưa đọc ngữ nghĩa) | Giá trị an toàn của chia sẻ chưa được chứng minh (F09 UNKNOWN) | Store trả "trống"; stale được coi là tươi | COM-10 |
| R-ISO-01 | Không rò truth vào đường truyền thông (AST, import bị chặn, quét byte) | I9 | — | — | Truth id trong byte; import truth | COM-10 |
| R-KNF-01 | Known failure tường minh, không che giấu | Quyết định 2 | Số đo WP2 (`evidence/wp2/metrics.json`) | — | Hợp nhất người gần nhau; ID switch; spoof; bias hằng số | `tests/perception/test_known_failures.py`, `tests/comm/test_known_failures.py` |

## 4. Cổng WP3 mới (COM-01 … COM-10)
Mọi cổng: test tái lập một lệnh, seed cố định, đối chiếu mã tham chiếu độc lập khi có thể, có mutation bite.
| ID | Nội dung | Tiêu chí PASS |
|---|---|---|
| COM-01 | Hợp đồng TrackMsg + (de)serialization | JSON Schema hợp lệ; round-trip chính xác từng bit trên ngẫu nhiên; byte chuẩn tắc ổn định; phiên bản/trường lạ/kiểu sai bị từ chối đúng lý do |
| COM-02 | Kênh tất định + replay | Cùng seed → cùng hash nhật ký giao nhận; không đổi khi chèn trễ wall-clock; độc lập PYTHONHASHSEED/tiến trình; seed khác → khác; tiêu thụ RNG cố định mỗi gói |
| COM-03 | Thống kê kênh | Trễ/jitter, mất Bernoulli và GE (tỉ lệ dừng, độ dài cụm), trùng lặp, đảo thứ tự, blackout, băng thông/hàng đợi khớp tham số (χ² 95% hoặc chính xác) |
| COM-04 | Bốn mốc thời gian + đồng hồ | Thứ tự `t_meas ≤ t_sent ≤ t_recv ≤ t_proc` trong mô phỏng; mô hình offset/drift chính xác; tuổi ước lượng ≠ thật đúng bằng sai lệch đồng hồ; không đọc wall-clock |
| COM-05 | AoI theo thời điểm quan sát | Răng cưa khớp tính tay chính xác; bản cũ/trùng/relay không làm giảm AoI; trung bình theo thời gian và đỉnh đúng; theo nguồn và theo track |
| COM-06 | Admission fail-closed | Mỗi mã lý do được kích hoạt đúng bởi đúng ca; reject không đổi trạng thái; fuzz: không có dữ liệu không hợp lệ vào store |
| COM-07 | Nguồn, provenance, frame | Allowlist; track ID theo nguồn không va chạm; frame/origin/units/yaw sai bị từ chối; không biến đổi âm thầm |
| COM-08 | Relay/truyền lại | `t_meas`/origin giữ nguyên; hop limit; loop; khử trùng; relay không làm AoI tốt hơn |
| COM-09 | Telemetry truyền thông | Hợp lệ schema; đẳng thức kế toán đúng; replay hash; không trường truth |
| COM-10 | Cô lập + ràng buộc P1 + chính sách xuất bản | AST/import-chặn cho `comm/`; không rò truth vào byte; 3-of-4 được áp; không có ngữ nghĩa "trống"; known failures liệt kê tường minh |
Cổng tồn tại sẵn **không bị đổi nghĩa**: PHY-08 (PRD §12.2) được cài đúng như viết; AC-VS-04 chỉ hoàn thành một phần (xem §5).

## 5. Đối chiếu PHY-08 và AC-VS-04 với định nghĩa chuẩn (không đổi nghĩa)
| Định nghĩa chuẩn (PRD) | Cài đặt WP3 | Ghi chú |
|---|---|---|
| Chuẩn của cổng PHY-08: "Lịch giao thông điệp biết trước → AoI răng cưa tính tay; thống kê trễ/mất/jitter khớp tham số"; tiêu chí "AoI khớp chính xác; thống kê trong dung sai" | `tests/comm/test_phy08_aoi_and_link_statistics.py`: lịch xác định, AoI tính tay độc lập; thống kê trễ/mất/jitter | Đúng nguyên văn; dung sai thống kê = χ² 95% như PHY-07 |
| Chuẩn của AC-VS-04: validator loại stale, replay, `t_meas` tương lai, sai schema, nguồn lạ, mâu thuẫn quan sát trực tiếp; kênh khớp tham số | COM-06/07 phủ stale, replay, future, schema, nguồn lạ | **"Mâu thuẫn quan sát trực tiếp" chỉ phủ phần xung đột lớp** (lớp khác lớp track cục bộ đã xác nhận); phần còn lại cần hợp nhất → **WP4**. Không tuyên bố AC-VS-04 hoàn tất |

## 6. Thay đổi SAU khi viết tài liệu này (nêu thẳng — được phát hiện bằng thực nghiệm khi làm, không phải kế hoạch ban đầu)
| # | Thay đổi | Lý do / bằng chứng | Hệ quả cho yêu cầu |
|---|---|---|---|
| 1 | Thêm trường `crc32` (CRC-32 trên byte chuẩn tắc) và mã từ chối `integrity` | Thí nghiệm nháp: 5/320 gói bị hỏng 1 byte vẫn được chấp nhận (byte hỏng rơi vào chỗ vẫn parse + qua schema + qua kiểm tra số). Sau CRC: quét **toàn bộ** lật 1 byte → 0 lọt | R-MSG-01/R-ADM-01 mở rộng; **CRC không phải xác thực** — kẻ giả mạo tính lại CRC được → known failure KF-3 |
| 2 | `AoIMeter` gộp các cập nhật cùng thời điểm | Hypothesis tìm được đỉnh AoI độ dài 0 khi hai bản tin xử lý cùng t | R-AOI-01 làm rõ: chỉ quan sát **mới hơn hẳn** mới reset tuổi |
| 3 | `CommNetwork.step` gọi `pump` trước khi publish | Hash nhật ký phụ thuộc tần suất gọi `step` (0.01 s vs 0.05 s) | R-TIM-02 / COM-02: thứ tự log chuẩn tắc, độc lập bước render |
| 4 | Khối `units` trong schema là chuỗi tự do, ép đúng giá trị ở admission | Để mã lý do là `units_mismatch` thay vì `schema` chung chung | Không đổi nghĩa; mã lý do cụ thể hơn |
| 5 | Mutation phát hiện 4 lỗ hổng test (staleness phải xét ở `t_proc`, guard non-finite độc lập parser, tiêu thụ RNG khi blackout, hồi phục Gilbert–Elliott) → thêm 3 test | `scripts/physics_bites.py` (36 mutant comm) | Chỉ tăng test; không đổi ngưỡng |
| 6 | Hàm benchmark: tên metric INV-3 ánh xạ vào tuổi **thật** (đồng hồ mô phỏng) | Lỗi script `KeyError` lần chạy đầu, không phải đổi ngưỡng; `comm/thresholds.json` giữ nguyên SHA-256 | — |
