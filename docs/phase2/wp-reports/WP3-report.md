# WP3 — V2X Communication & TrackMsg

**Trạng thái: PASS cho COM-01..COM-10 và PHY-08 (định nghĩa PRD, không đổi nghĩa). Tất cả là TỰ KIỂM (cùng một tác nhân viết và kiểm), không phải kiểm độc lập.** Ngày 2026-11-01. Không phần cứng radio; không WP4 (hợp nhất cộng tác), WP5 (web), thành phố đầy đủ. Refinery/dữ liệu nguồn không đổi (REG-1/2/3 PASS). **VIS-08 vẫn BLOCKED** (`docs/references/` chưa có ảnh gốc). Nhánh `claude/amazing-rubin-aywols`, chưa merge main.

Tài liệu yêu cầu (lý do, bằng chứng, giả thuyết/ẩn số, ca lỗi, test): `docs/phase2/08-wp3-comm-requirements.md`. Ngưỡng khai báo **trước** benchmark: `comm/thresholds.json`, SHA-256 `47096a4ea5957f8e1f7f9a180ef379fdd003af3426b8d3a6090f7d7c2d758760` (script benchmark kiểm hash này và dừng nếu khác).

## 1. Kiến trúc
```
 World(truth) ─► SensorProvider ─► SensorFrame ─► Tracker (3-of-4)           ← phía truth/perception (WP2), không đổi
                                                      │ tracks(confirmed_only)
 ┌────────────────────────── comm/ (KHÔNG import truth, KHÔNG đọc wall-clock) ───────────────────────────┐
 │ Publisher ─► TrackMsg ─► serialize (JSON chuẩn tắc + CRC-32) ─► Channel (rời rạc, tất định, 10 số ngẫu │
 │ nhiên/gói) ─► [recv @t_recv] ─► +proc_delay ─► Admission (fail-closed, 25 mã lý do) ─► ReceiverStore   │
 │                     ▲                                  │ admit ─► (tuỳ chọn) relay_message ─► Channel kế │
 │               NodeClock (offset, drift)         CommTelemetry JSONL + SHA-256 + đẳng thức kế toán      │
 └──────────────────────────────────────────────────────────────────────────────────────────────────────┘
 integration/comm_rig.py (ngoài comm/) nối rig WP2 → Publisher → mạng → ego; scripts/make_wp3_evidence.py
```
| Module | Vai trò |
|---|---|
| `comm/trackmsg.py` | dataclass + `to_dict/from_dict` (jsonschema nghiêm ngặt), `serialize` (byte chuẩn tắc, CRC-32), `parse_bytes/deserialize` (từ chối NaN/Infinity, khoá trùng, UTF-8 hỏng), `relay_message`, `track_ref`, `content_key` |
| `comm/channel.py` | `LinkConfig`/`Channel`: trễ+jitter, mất Bernoulli hoặc Gilbert–Elliott, trùng lặp, đảo thứ tự, hỏng byte, blackout, băng thông + hàng đợi; **luôn 10 số uniform/gói** (ghép cặp seed) |
| `comm/clock.py` | `NodeClock(offset_s, drift_ppm)`; thời gian mô phỏng là đồng hồ điều khiển duy nhất |
| `comm/admission.py` | kiểm tra theo thứ tự cố định, mỗi từ chối đúng 1 mã; trạng thái quyết định chỉ đổi khi **chấp nhận** |
| `comm/store.py` | `ReceiverStore`: chỉ thông tin dương, khoá `(source_id, track_id)`, bản cũ không ghi đè bản mới, hết hạn → biến mất (không bao giờ thành "trống") |
| `comm/aoi.py` | AoI theo **thời điểm quan sát**, tích phân/đỉnh chính xác |
| `comm/publisher.py` | chỉ track đã xác nhận, chỉ khi 3-of-4 (hoặc `experimental=True`, gắn nhãn), chỉ khi có quan sát **mới**; `t_meas = tracker.last_frame_time` |
| `comm/network.py` | hàng đợi sự kiện (time, RECV<PROC, counter), `inject` cho tấn công/test, relay xác thực trước khi chuyển tiếp |
| `comm/telemetry.py`, `comm/metrics.py` | JSONL chuẩn tắc, băm SHA-256, đẳng thức kế toán, P50/P95/P99 |

### Schema TrackMsg 0.2.0 (`schemas/trackmsg.schema.json`, object đóng)
| Trường | Ý nghĩa / đơn vị |
|---|---|
| `schema_version` | phải `"0.2.0"` |
| `msg_id`, `tx{node_id, tx_seq, clock_id}` | danh tính **truyền** (đổi qua mỗi hop) |
| `origin{source_id, source_type, orig_seq, orig_msg_id, clock_id, clock_sync, provenance{sensor_model, algo_version, calib_id, privacy_level=object_only, confirmation}}` | danh tính **quan sát** (bất biến qua relay) |
| `t_meas` | s, đồng hồ nguồn: thời điểm quan sát mới nhất; **giữ nguyên qua relay** |
| `t_sent` | s, đồng hồ nút gửi (đổi qua relay); `t_recv`, `t_proc` do phía nhận ghi, **không nằm trong bản tin** |
| `frame="map"`, `origin_frame_id`, `units{...}`, `yaw_convention` | toạ độ tường minh; **không có biến đổi nào được hỗ trợ**, khác → từ chối |
| `ttl_s` (>0), `hop_count`, `relay_path` (≤8) | TTL, giới hạn relay, chống vòng |
| `tracks[≤64]{track_id, cls, cls_prob, x, y, yaw, vx, vy, cov[16], var_yaw, existence, t_upd}` | m, rad, m/s; `track_id` chỉ có nghĩa trong phạm vi `source_id` |
| `crc32` | CRC-32 trên byte chuẩn tắc: phát hiện hỏng **ngẫu nhiên**, **không phải xác thực** |

## 2. Cổng và kết quả (`make check`: 30 PASS, 0 FAIL, 1 BLOCKED, 9 NOT_CHECKED; 387 test = 382 pass + 5 xfail strict)
| Cổng | Kết quả | Evidence (thực chạy) |
|---|---|---|
| COM-01 hợp đồng + (de)serialization | **PASS** (11) | Round-trip chính xác từng bit trên ngẫu nhiên; byte chuẩn tắc ổn định; CRC độc lập; **quét mọi lật 1 byte → 0 lọt**; NaN/Inf/khoá trùng/UTF-8 hỏng/phiên bản lạ/trường lạ bị từ chối đúng lý do |
| COM-02 kênh tất định | **PASS** (9) | Cùng seed → cùng hash; không đổi khi chèn `sleep` wall-clock; độc lập `PYTHONHASHSEED`/tiến trình; seed khác → khác; **số ngẫu nhiên cố định/gói** kể cả gói rơi vào blackout (mutation tìm ra lỗ hổng, đã vá bằng test) |
| COM-03 thống kê kênh | **PASS** (9) | Jitter đều χ² 95%; Bernoulli và GE (tỷ lệ dừng, độ dài cụm); trùng lặp, đảo thứ tự, blackout, băng thông/hàng đợi khớp tham số |
| COM-04 bốn mốc thời gian + đồng hồ | **PASS** (9) | `t_meas ≤ t_sent ≤ t_recv ≤ t_proc`; offset/drift chính xác; tuổi ước lượng − tuổi thật = sai lệch đồng hồ; quét mã nguồn không có wall-clock |
| COM-05 AoI | **PASS** (6) | Răng cưa khớp tính tay; bản cũ/trùng/relay không giảm AoI; trung bình/đỉnh chính xác = brute force (hypothesis); theo nguồn và theo track |
| COM-06 admission | **PASS** (22 gồm injection) | **25/25 mã lý do** đều được kích hoạt đúng một ca; reject không đổi trạng thái; fuzz 500 cấu trúc + 400 byte + 300 lật byte → 0 dữ liệu không hợp lệ vào store; staleness xét tại `t_proc` |
| COM-07 nguồn/provenance/frame | **PASS** (22) | Allowlist; trùng `track_id` giữa hai nguồn không va chạm; frame/origin/units/yaw sai bị từ chối; không có hàm biến đổi toạ độ |
| COM-08 relay | **PASS** (9) | `t_meas`/origin giữ nguyên; hop tăng; vòng lặp, vượt hop bị chặn; khử trùng trực tiếp+relay; relay không làm AoI tốt hơn |
| COM-09 telemetry | **PASS** (8) | Mọi dòng hợp schema (object đóng); đẳng thức kế toán đúng cả với tham số kênh ngẫu nhiên (hypothesis); hash file = hash bộ nhớ; replay bit-giống; không trường truth |
| COM-10 cô lập + P1 + chính sách | **PASS** (35) | AST: `comm/` chỉ import whitelist, không `time/random/os/...`, không định danh truth hay "free space"; tiến trình **chặn import truth-side** cho cùng hash; byte trên dây (110 bản tin rig `s01w2`) không chứa id truth; 3-of-4 được ép; bản tin thực nghiệm bị receiver từ chối mặc định; chỉ track xác nhận, chỉ khi có quan sát mới; hết hạn → **không có dữ liệu**, không "trống" |
| PHY-08 (định nghĩa PRD §12.2) | **PASS** (4) | `tests/comm/test_phy08_aoi_and_link_statistics.py`; định nghĩa không đổi |
| Known failures (xfail strict) | **PASS = 5 còn thất bại đúng như khai báo** | xem §5 |
| Mutation bites | **PASS: 71/71** (35 WP0–2 + 36 comm) | 4 mutant comm ban đầu sống sót → thêm 3 test + thay 1 mutant tương đương (`com_channel_ge_wrong_recovery`); chạy lại: `ALL CAUGHT` |
| Benchmark theo ngưỡng khai báo trước | **PASS** (không FAIL) | §3 |
| AC-VS-04 | **PARTIAL** | stale/replay/future/schema/nguồn lạ được phủ; "mâu thuẫn với quan sát trực tiếp" chỉ phủ xung đột lớp (cờ `class_conflict`), phần còn lại thuộc WP4. **Không tuyên bố hoàn tất** |
| VIS-01..10 | **NOT_CHECKED**; VIS-08 **BLOCKED** | không thuộc WP3 |

## 3. Benchmark (50 seed × 3 điều kiện, rig `s01w2`, 11 s mô phỏng/lần; `evidence/wp3/benchmark.json`, `benchmark_table.md`)
Bản tin: trung bình **1280 byte** (JSON chuẩn tắc — **không phải CPM/SDSM**), 10 Hz → **12.8 kB/s/nguồn**.
| Chỉ số | B0 nominal | B1 degraded | B2 severe |
|---|---|---|---|
| Gửi / chấp nhận | 5500 / 5451 | 5500 / 4994 | 5500 / 3083 |
| Delivery ratio | **0.991** | **0.908** | 0.561 |
| Rơi theo lý do | loss 49 | loss 506 | loss 1466, blackout 500 |
| Từ chối theo lý do | — | duplicate 115 | duplicate 313, stale 421, malformed_bytes 58, integrity 14 |
| Chấp nhận muộn (đảo thứ tự) | 0 | 121 | 59 |
| Trễ mạng P50/P95/P99 (s) | 0.035 / 0.040 / 0.040 | 0.102 / 0.149 / 0.233 | 0.261 / 0.556 / 0.649 |
| Quan sát→dùng P50/P95/P99 (s) | 0.110 / 0.115 / 0.115 | 0.176 / 0.195 / 0.308 | 0.328 / 0.374 / 0.482 |
| AoI P50/P95/P99/max (s) | 0.160 / 0.206 / 0.213 / 0.313 | 0.233 / 0.355 / 0.514 / 0.965 | 0.424 / 1.019 / 1.439 / 1.962 |
| Tuổi quan sát lớn nhất được chấp nhận (s) | 0.115 | 0.340 | **0.4996** (≤ 0.5) |
Phán quyết theo ngưỡng (đầy đủ trong `benchmark_table.md`): 7 bất biến INV-1..7 + `B0-NET-MAX` **PASS**; 7 ngưỡng `provisional_design` **PASS** (B0-DR 0.991≥0.97; B0-E2E-P99 0.115≤0.25; B0-AOI-P95/P99 0.206/0.213; B0-BW 12.8k≤50k; B1-DR 0.908≥0.75; B1-AOI-P95/P99 0.355/0.514); 2 `report_only` ở B2: **REPORTED**.
**Diễn giải trung thực:** ngưỡng `provisional_design` **không có nguồn ngoài** (G05/E04/B04/B06 UNKNOWN) nên PASS ở đây nghĩa là "đạt ngưỡng thiết kế tạm tôi tự đặt", **không** chứng minh đủ an toàn. AoI đo tuổi của **bản tin track**, không phải tuổi của người đi bộ. Ngưỡng không bị sửa sau khi xem kết quả.

## 4. Lệnh tái lập
```bash
make setup && make check                                   # 30 PASS / 0 FAIL / 1 BLOCKED / 9 NOT_CHECKED
.venv/bin/python -m pytest -m "com or phy or known_failure" -q
.venv/bin/python scripts/physics_bites.py                  # 71 mutant, kỳ vọng ALL CAUGHT
.venv/bin/python scripts/make_wp3_evidence.py              # benchmark (≈90 s), kiểm SHA-256 ngưỡng
.venv/bin/python scripts/check_phase2_docs.py && .venv/bin/python scripts/selftest_check_phase2_docs.py
```

## 5. Known failures & giới hạn (liệt kê tường minh)
| ID | Nội dung | Số liệu / nguồn |
|---|---|---|
| KF-1 | Khử trùng gộp hai người đi bộ thật cách 0.4 m | WP2: 17/100 seed |
| KF-2 | Giao cắt trên đường va chạm gây ID switch | WP2: 70/100 seed |
| KF-3 | Nguồn giả mạo có `source_id` trong allowlist **không bị phát hiện** (CRC ≠ xác thực) | E05/E06 UNKNOWN |
| KF-4 | Phát lại bản tin mới còn tươi mà bản gốc chưa từng đến, không phân biệt được | không có nonce/session |
| KF-5 | Lệch đồng hồ nằm trong dung sai (50 ms) làm sai tuổi ước lượng một lượng bằng độ lệch | B04 UNKNOWN |
Giới hạn khác: băng thông là của JSON, không phải CPM/SDSM (W3H-1); mô hình kênh không đại diện V2X thật (E04); ngưỡng chỉ là thiết kế tạm; chưa đo line coverage (không cài công cụ), thay bằng phủ **mã lý do 25/25** + **36 mutant comm**; jerk tại v=0 khi phanh khẩn cấp **không** được tuyên bố tuân thủ (quyết định 5); WP2 giữ nguyên các giới hạn (mô hình vận tốc không đổi, không re-ID sau che dài, điểm tồn tại heuristic); chưa có bất kỳ khẳng định nào về giá trị an toàn của chia sẻ (F09 UNKNOWN); tất cả kiểm tra là tự kiểm.

## 6. Quyết định đã đưa ra / việc cần chủ việc
- Đã áp dụng 6 quyết định của chủ việc (xem doc 08 §1); các thay đổi sau khi viết yêu cầu nằm ở doc 08 §6.
- **Cần chủ việc:** (a) duyệt WP3 để mở WP4; (b) cung cấp ảnh tham chiếu vào `docs/references/` để mở VIS-08; (c) quyết định có đầu tư xác thực mật mã (KF-3/KF-4) trong WP4+ hay giữ ở mức giả định tin cậy; (d) xác nhận ngưỡng `provisional_design` hoặc cung cấp nguồn.
