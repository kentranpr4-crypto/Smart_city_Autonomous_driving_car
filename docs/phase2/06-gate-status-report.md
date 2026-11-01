# 06 · Báo cáo trạng thái gate · Phase 2 (T-gate)

**Trạng thái: PARTIAL — sẵn sàng để review, DỪNG trước triển khai. Đã áp dụng Amendment A1 (xem §8).**
Ngày: 2026-11-01 · Cơ sở: commit `66f1a64` + các file chưa commit (xem §5). **Chưa commit, chưa push** theo yêu cầu.

## TIP (tóm tắt, theo AI Work Method)
- **Mục tiêu:** đặc tả MVP có cổng bằng chứng cho cooperative perception Smart City V2X (mô phỏng, cảm hứng Vinhomes).
- **Đầu ra:** 6 deliverable trong `docs/phase2/` + 2 script kiểm (`scripts/check_phase2_docs.py`, `scripts/selftest_check_phase2_docs.py`).
- **Ngoài phạm vi:** triển khai mã mô phỏng/frontend, huấn luyện, toàn thành phố, sửa registry/engine Refinery, commit/push.
- **Ràng buộc đã giữ:** không đổi dữ liệu bằng chứng; không thêm claim/snapshot; không bịa trích dẫn; không bịa mẫu số.

## 1. Deliverable
| # | Deliverable | File | Trạng thái |
|---|---|---|---|
| 1 | Evidence gap matrix | `01-evidence-gap-matrix.md` | Hoàn tất bản nháp (sau A1): **55** giả định → 4 VERIFIED / 15 SUPPORTED / **17** HYPOTHESIS / **19** UNKNOWN (thêm nhóm V: vật lý & hiển thị) |
| 2 | MVP PRD | `02-mvp-prd.md` | Hoàn tất bản nháp: ODD, 23 FR, 9 NFR, 9 bất biến, 18 chế độ lỗi, hợp đồng dữ liệu, 22 AC |
| 3 | Kiến trúc + ADR | `03-architecture-and-adrs.md` | Hoàn tất bản nháp: sơ đồ, so sánh 3 topology, 7 ADR (2 ACCEPTED theo quyết định chủ việc, 5 PROPOSED) |
| 4 | Kịch bản + thí nghiệm | `04-scenario-experiment-spec.md` | Hoàn tất bản nháp: S01, E0–E4 (+E0-N/E0-C), metric, thiết kế thống kê, đe doạ hợp lệ |
| 5 | Kế hoạch vertical slice | `05-vertical-slice-plan.md` | Hoàn tất bản nháp: 8 WP, 14 AC-VS, 2 điểm dừng |
| 6 | Báo cáo gate | file này | — |
| 7 | Amendment A1 (vật lý + 3D) | `07-amendment-a1-physics-and-visualization.md` | Hoàn tất bản nháp; PRD §12, ADR-005/006/008/009, 04 §3, 05 đã sửa theo |

## 2. Gate đã chạy (tự kiểm; chưa có kiểm độc lập)
| Gate | Kết quả | Evidence | Gate này **không** chứng minh |
|---|---|---|---|
| REG-1 Registry không đổi | **PASS** | `git diff --stat HEAD -- data .claude` rỗng trước và sau khi chạy gate; `claims.jsonl` 84 dòng, sha256 `9081c4b3c7dc4d92…` | Không chứng minh claim đúng |
| REG-2 `refinery.py` | **PASS** | `VALIDATION PASSED`, digest `a68fc24fbf62a74a`, idempotent OK, auditor OK | Chỉ chứng minh đoạn trích có trong snapshot, **không** chứng minh ngữ nghĩa |
| REG-3 `bites.py` | **PASS** | 5/5 bite áp dụng được cắn ✓; 9 gate chuyên ngành N/A (domain chưa khai) | Không chứng minh các gate N/A; không thay review người |
| DOC-1 REF_INTEGRITY | **PASS** | 45 tham chiếu claim và 17 tham chiếu snapshot-dòng đều khớp entity/dòng/chuỗi | Không chứng minh tham chiếu **được dùng đúng nghĩa** |
| DOC-2 ID_RESOLVE | **PASS** | 169 ID được tham chiếu, 169 được định nghĩa, không trùng | Không chứng minh nội dung định nghĩa hợp lý |
| DOC-3 Nhãn VERIFIED hợp lệ | **PASS** | Mọi hàng VERIFIED dẫn ≥1 claim tier A | Không chứng minh VERIFIED là đúng ngoài đời |
| DOC-4 Selftest checker | **PASS** | Tiêm 6 lỗi (claim ngoài phạm vi, sai entity, sai dòng snapshot, VERIFIED không tier A, ID chưa định nghĩa, nhãn sai) → checker bắt cả 6; bản sạch PASS | Phạm vi lỗi hạn chế |

## 3. Tiêu chí chấp nhận của Phase 2
| AC | Mô tả | Kết quả | Evidence / lý do |
|---|---|---|---|
| P2-AC-01 | Mọi giả định kiến trúc quan trọng được phân loại 4 nhãn, không trích dẫn bịa | **PASS (tự kiểm cơ học)** + **NOT_CHECKED (ngữ nghĩa)** | DOC-1/DOC-3. Tôi chưa nhờ người thứ hai đọc xem từng nhãn có hợp lý |
| P2-AC-02 | Bộ spec có ODD, FR, NFR, bất biến, lỗi, hợp đồng, AC | **PASS (đủ mục)** | 02 §3–§9. Chất lượng yêu cầu chưa được review |
| P2-AC-03 | ADR so sánh 3 topology theo 6 tiêu chí và nêu đánh đổi, không giả định người thắng | **PASS (đủ mục)** | 03 §3–§4. Mọi đánh giá HYPOTHESIS; khuyến nghị ghi PROPOSED |
| P2-AC-04 | S01 với E0–E4 và đủ metric yêu cầu (va chạm, near-miss, TTC, phanh nhầm, hoàn tất lộ trình, AoI, trễ) | **PASS (đủ mục)** | 04 §4–§5 |
| P2-AC-05 | Kế hoạch slice tối thiểu, có AC và lệnh tái lập | **PASS (đủ mục)** | 05 §5–§8. Lệnh `make` **chưa tồn tại** (đã ghi rõ) |
| P2-AC-06 | Không đổi dữ liệu bằng chứng / engine | **PASS** | REG-1 |
| P2-AC-07 | Không commit/push khi chưa duyệt | **PASS** | `git status`: chỉ file chưa theo dõi; HEAD vẫn `66f1a64` |
| P2-AC-08 | Các số trong 04 §3 đúng | **PASS (tự kiểm)** | Tính bằng Python 2 lần (bảng dừng, v_sd, ngân sách trễ, Wilson); chưa có kiểm độc lập |
| P2-AC-09 | Quyết định chủ việc cần thiết đã được nêu | **PASS** | §4 dưới đây |
| P2-AC-10 | Kết quả thực nghiệm | **NOT_CHECKED (chưa chạy, cố ý)** | Dừng trước triển khai; mọi H2–H7 chưa kiểm |

## 4. Quyết định và việc cần chủ việc (chặn bước sau)
| ID | Quyết định | Tại sao quan trọng | Khuyến nghị |
|---|---|---|---|
| **OD-1** (= DEC-1, xem 02 §11) | Giá trị của chia sẻ khi "chỉ tư vấn": **P1** (đơn điệu hạn chế so với EO-N) hay **P1+P2** (thêm profile phụ thuộc xác nhận bao phủ) | Số học 04 §3: ego-only thận trọng (E0-C) tránh va chạm S01 chỉ chậm ≈0.9–1.5 s. Dưới P1, lợi ích an toàn so với E0-C = 0 theo thiết kế; nếu không nói trước, kết quả sẽ bị hiểu sai | P1 cho MVP; P2 là thí nghiệm riêng và cần bằng chứng hiện UNKNOWN |
| OD-2 | Vai trò A2/A3, vị trí K1–K4 (02 §2) | Quyết định E1 có lợi hay không | Chấp nhận mặc định, xem lại sau CAL-0 |
| OD-3 | Ngưỡng τ_col, τ_fb, τ_assoc và thang near-miss | Không có = H2/H4 NOT_CHECKED; đặt sau khi thấy kết quả = mất giá trị đăng ký trước | Đặt ở điểm dừng R1 |
| OD-4 | Cho phép nâng 10 đoạn snapshot thành claim tier A (01, cuối trang) | Chuyển nhiều SUPPORTED → VERIFIED; **thay đổi dữ liệu bằng chứng** nên cần duyệt | Duyệt, qua `review.py --by` |
| OD-5 | Cho phép tìm nguồn cho các UNKNOWN trọng yếu (hiệu chuẩn camera hạ tầng, đồng bộ thời gian V2X, association, lỗi mạng, SOTIF, mô hình kênh) | Hiện UNKNOWN; không được dùng làm tiền đề an toàn | Duyệt nghiên cứu vòng 3 trước hoặc song song với WP0 |
| OD-6 | Cài `pytest`, `hypothesis`, vendoring three.js; commit/push tài liệu này | Cần cho WP0; commit cần phê duyệt | Chờ lệnh của bạn |
| OD-7 | Rà soát pháp lý cho dữ liệu track người đi bộ (G08 UNKNOWN) trước thực địa | Không chặn mô phỏng | Ngoài MVP, ghi nhận |

## 5. Trạng thái repo
`HEAD = 66f1a64` (đã push ở phiên trước). **Chưa theo dõi (chưa commit):** `docs/phase2/` (6 file), `scripts/check_phase2_docs.py`, `scripts/selftest_check_phase2_docs.py`. Không file nào đã theo dõi bị sửa.

## 6. Blocker và ẩn số (nêu thẳng)
**Không còn blocker kỹ thuật cho bước sau. Có ba điều kiện chặn triển khai:** DEC-1 (cách lượng giá trị), OD-3 (ngưỡng đăng ký trước), và phê duyệt của bạn để bắt đầu.
**Hạn chế của chính bản đặc tả này:**
1. **Chưa đọc mã hoá CPM/SDSM** (SAE sau paywall; ETSI mới đọc đoạn chọn lọc). `TrackMsg` là trường của dự án, **chưa** ánh xạ sang chuẩn. Giả định G01 và A06 dựa trên scope.
2. **Không nguồn nào trong registry so sánh topology**, đánh giá lỗi mạng, hiệu chuẩn CCTV, đồng bộ thời gian V2X, association, SOTIF (xem 15 UNKNOWN). Các phần dựa vào kiến thức kỹ thuật phổ thông của tôi được gắn `ENG`/HYPOTHESIS, **không phải bằng chứng**.
3. **Mọi đánh giá topology (Thấp/Vừa/Cao) là phán đoán kỹ thuật của tôi**, chưa kiểm. Khuyến nghị HYB-L ở trạng thái PROPOSED, có điều kiện đảo ngược.
4. Các con số ODD lấy cảm hứng từ sandbox Hà Nội (tier B, báo chí), không phải yêu cầu pháp lý và không phải tuân thủ.
5. `VERIFIED` nghĩa là *nguồn tier A nói vậy và đoạn trích khớp*, không phải "đúng cho hệ của ta".
6. Số học 04 §3 phụ thuộc `[PARAM]` (t_r, a, T_pre) chưa có nguồn; chúng chỉ để dựng dải quét, không phải kết luận.
7. ID claim (`Cnn`) là số dòng, dễ vỡ nếu registry build lại; checker sẽ báo lỗi nếu lệch, nhưng cần `claim_id` bền khi OD-4 được duyệt.
8. Tôi tự soạn và tự kiểm; **chưa có người/agent thứ hai review độc lập**.

## 7. Lệnh tái lập các gate hôm nay
```bash
python3 .claude/skills/refinery/refinery.py data/refinery/domains/smartcity-v2x-landscape
python3 .claude/skills/refinery/bites.py data/refinery/domains/smartcity-v2x-landscape
python3 scripts/check_phase2_docs.py
python3 scripts/selftest_check_phase2_docs.py
git diff --stat HEAD -- data .claude   # phải rỗng
```

## 8. Amendment A1 — Độ trung thực vật lý và trực quan hoá 3D
Áp dụng **trước triển khai**. Chưa cài phụ thuộc, chưa viết mã, chưa commit/push. Evidence, báo cáo gate và artifact provenance cũ không bị sửa (REG-1 vẫn PASS: `git diff --stat HEAD -- data .claude` rỗng; `claims.jsonl` sha256 `9081c4b3c7dc4d92…`; HEAD `66f1a64`).

### 8.1 Đối chiếu từng yêu cầu của amendment
| Mục | Yêu cầu | Đã làm ở | Trạng thái |
|---|---|---|---|
| A | Mô phỏng tất định bước cố định, backend có thẩm quyền | 07 §1–§6; PRD R-PHY-01, I10–I12 | Thiết kế xong; chưa triển khai |
| A | Động lực học: vị trí/hướng/vận tốc/gia tốc, lái và ràng buộc quay, quãng phanh và ma sát, hình học và va chạm, giới hạn gia tốc/jerk | 07 §2–§3; PRD R-PHY-02, R-PHY-03 | Thiết kế xong |
| A | Người đi bộ, FOV, che khuất, bất định đo, trễ/mất gói/độ tươi | 07 §3–§5; R-PHY-04, R-PHY-05 | Thiết kế xong (che khuất **2.5D** theo độ cao) |
| A | Ghi giới hạn trung thực + xác thực bằng giải tích | 07 §7–§8; PRD §12.2 | PHY-01..08 định nghĩa; **chưa chạy** |
| A | Giao diện CARLA tương lai, không tuyên bố tương đương | 07 §9; ADR-005, ADR-008; PX-1 | Giao diện thiết kế; `CarlaBackend` **chưa triển khai**; PX-1 chưa làm |
| B | Diorama 3D cao cấp, đủ danh mục, bóng, camera, lớp cooperative | 07 §10; PRD §12.1 và VIS-01..10; ADR-009 | Thiết kế xong |
| B | Three.js / R3F hoặc biện minh | 07 §10.1 | Đề xuất R3F + phương án dự phòng; **cần duyệt phụ thuộc** |
| B | **Ảnh tham chiếu** làm chuẩn tối thiểu | 07 §0, §10.7 | **BLOCKED: ảnh chưa được nhận** (đã kiểm `/mnt/user-data/uploads`, `/mnt/attach`, repo đều trống) |
| C | Vòng `Physics→…→Physics`; frontend tiêu thụ trạng thái; không phụ thuộc FPS | 07 §1, §10.6; 03 §1; I10–I12; VIS-10 | Thiết kế xong |
| D | PHY-01..08 + cổng thị giác vào PRD và slice | 02 §12; 05 §5–§6 (AC-VS-15..18) | Xong |
| D | 6 yêu cầu bằng chứng (test tái lập, seed cố định, ảnh thật, so ảnh tham chiếu, đo hiệu năng, tài liệu giới hạn) | PHY (seed cố định), VIS-09, VIS-08, VIS-07, 07 §8 | Quy định xong; **chưa có bằng chứng thực thi** |
| E | Giữ E0-N / E0-C tách biệt; không tuyên bố an toàn hơn; P1 là ràng buộc cần kiểm | 02 §1, I2; 04 §1; 07 §11; AC-VS-18 | Xong |
| E | Giữ evidence/gate/provenance | REG-1, REG-2, REG-3 | PASS |

### 8.2 Gate chạy lại sau amendment (tự kiểm)
| Gate | Kết quả | Ghi chú |
|---|---|---|
| REG-1 registry không đổi | PASS | diff rỗng, sha256 không đổi |
| REG-2 `refinery.py` | PASS | digest `a68fc24fbf62a74a`, idempotent OK, auditor OK |
| REG-3 `bites.py` | PASS | 5/5 bite áp dụng được cắn ✓ |
| DOC-1/2/3 REF_INTEGRITY + ID_RESOLVE + nhãn | PASS | 47 tham chiếu claim, 17 tham chiếu snapshot-dòng, 226 ID định nghĩa = 226 tham chiếu; checker đã mở rộng nhận diện PHY-, VIS-, OD-, I10..I12, nhóm V |
| DOC-4 selftest checker | PASS | 6/6 lỗi tiêm bị bắt |
Giới hạn của gate: chỉ chứng minh tham chiếu và ID nhất quán, **không** chứng minh nội dung đúng.

### 8.3 Thay đổi thực chất so với bản trước (cần bạn đọc)
1. **Số học phanh bị sửa.** Với actuator trễ + giới hạn jerk, quãng dừng *từ lúc có lệnh* là **9.45 m** (khẩn cấp) và **17.64 m** (êm), lớn hơn con số lý tưởng 8.70/14.49 m trước đó. Ngân sách trễ chuỗi cảnh báo với T_pre=2.0 s chỉ còn **≈0.87 s** (khẩn cấp), và phanh êm **không khả thi** (−0.12 s). Chi phí của EO-C tăng từ ≈0.9–1.5 s lên **≈1.5 s**. Mọi số vẫn phụ thuộc `[PARAM]` chưa có nguồn.
2. **Che khuất chuyển sang 2.5D.** CCTV cột cao nhìn qua xe tải thấp hơn nó; mô hình 2D sẽ đánh giá quá mức vùng khuất của CCTV.
3. **Backend dịch vụ trở thành bắt buộc** (thay quyết định "replay tĩnh không backend") vì backend phải có thẩm quyền và frontend tiêu thụ luồng trạng thái.
4. **Slice không còn nhỏ về công sức**: WP6a/6b cỡ XL do yêu cầu hình ảnh bắt buộc.
5. **Rủi ro mới được đo:** phanh gấp do dữ liệu chia sẻ có thể gây đâm đuôi xe theo sau; metric "rủi ro xe theo sau" được thêm.

### 8.4 Blocker và việc cần chủ việc (bổ sung)
| ID | Việc | Lý do |
|---|---|---|
| OD-8 | **Cung cấp ảnh tham chiếu** (đặt ở `docs/references/` hoặc gửi lại trong chat) | VIS-08 BLOCKED; không thể đặt ngưỡng chất lượng hình ảnh |
| OD-9 | Khai báo máy tham chiếu (CPU/GPU/độ phân giải) và ngân sách FPS | Sandbox không có GPU; VIS-07 không đo được ở đây |
| OD-10 | Duyệt phụ thuộc §2 của kế hoạch slice và chính sách tài sản (thủ tục / glTF có giấy phép) | Chưa cài gì cho tới khi duyệt |
| OD-11 | Nguồn cho μ, t_act, j_max nếu bạn có (hiện UNKNOWN) | Nếu không, giữ làm tham số + quét độ nhạy |
Các quyết định OD-1..OD-7 ở §4 vẫn mở.

### 8.5 Trạng thái cuối của amendment
**PARTIAL:** thiết kế đầy đủ và nhất quán theo kiểm máy; **chưa có** bằng chứng thực thi cho bất kỳ cổng PHY hoặc VIS nào; VIS-08 bị chặn do thiếu ảnh. Không có công bố nào về độ trung thực vật lý hoặc chất lượng hình ảnh được đưa ra ngoài thiết kế.

## 9. Triển khai WP0 + WP1 (2026-11-01) — cập nhật trạng thái
Chủ việc đã duyệt có điều kiện: OD-1 → P1 cho MVP (P2 để nghiên cứu), physics backend bước cố định, R3F hiển thị trạng thái authoritative, cài phụ thuộc đã đề xuất sau kiểm tra, commit cục bộ (chưa push). Báo cáo chi tiết: `docs/phase2/wp-reports/{WP0,WP1,DEPS-audit}.md`; bằng chứng: `docs/phase2/wp-reports/evidence/`.
| Hạng mục | Trạng thái | Ghi chú |
|---|---|---|
| Gói WP0: khung + phụ thuộc khoá + `make check` + smoke | **PASS** | clean-room tái lập được (`make setup` 18 s) |
| Cổng PHY-01 … PHY-06 | **PASS** (98 test; 12/12 mutant bị bắt) | đối chiếu mã tham chiếu độc lập; **chưa** xác thực với xe thật/CARLA |
| Cổng PHY-07, PHY-08 | NOT_CHECKED | WP2, WP3 |
| Cổng VIS-08 | **BLOCKED** | không có ảnh ở `docs/references/` |
| Cổng VIS-01..07, 09, 10 | NOT_CHECKED | thành phố 3D chưa dựng (WP6a–c); screenshot WP0 chỉ là smoke toolchain |
| Registry / evidence Refinery | **không đổi** | REG-1/2/3 PASS |
Phát hiện cần bạn biết: (i) repo đang theo dõi một file bytecode `.pyc` trong `.claude/skills/refinery/__pycache__/` (từ lần cài kit), làm REG-1 báo sai khi đổi interpreter — gate đã được sửa, không xoá file; (ii) gia tốc snap về 0 khi xe dừng hẳn (giới hạn jerk không thi hành tại bước đó, đã ghi vào danh sách hạn chế); (iii) sandbox chạy bằng **SwiftShader (render phần mềm)** nên số đo FPS không đại diện sản phẩm.
**Điểm dừng:** dừng sau WP0 + physics sandbox để review trước khi dựng thành phố và các WP kế tiếp. Còn mở: OD-3 (ngưỡng đăng ký trước), OD-8 (ảnh tham chiếu), OD-9 (máy tham chiếu), OD-11 (nguồn tham số vật lý).
