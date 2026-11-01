# 01 · Evidence Gap Matrix (Phase 2, T1)

Trạng thái: **DRAFT chờ duyệt**. Không có claim hay snapshot nào được thêm hoặc sửa. Registry: `data/refinery/domains/smartcity-v2x-landscape/` (84 claim, 25 thực thể; số `Cnn` = số dòng trong `claims.jsonl` tại commit `66f1a64`).

## Quy ước phân loại
| Nhãn | Điều kiện (kiểm được) |
|---|---|
| **VERIFIED** | Có claim tier **A** mà span *trực tiếp* nêu mệnh đề, và mệnh đề là phát biểu của chính nguồn (không phải ngoại suy của tôi). "Verified" = đúng với nguồn đã trích, **không** = đúng ngoài đời hay cho hệ của ta. |
| **SUPPORTED** | Có bằng chứng trong repo nhưng yếu hơn: claim tier B/C, số do tác giả tự báo, hoặc văn bản nguồn gốc nằm trong snapshot **chưa được nâng thành claim** (ghi `Sxx:dòng~từ khoá`). |
| **HYPOTHESIS** | Giả định thiết kế/kỹ thuật có lý do nhưng không có bằng chứng trong registry. Kiến thức kỹ thuật phổ thông của tôi được gắn `ENG` — **không phải nguồn**. Phải bị kiểm bằng thí nghiệm mô phỏng hoặc đọc nguồn. |
| **UNKNOWN** | Không có bằng chứng, không có cơ sở để đặt giá trị. Không được dùng làm tiền đề an toàn. |

Phạm vi nhãn: cho **MVP mô phỏng**. Chỗ khác biệt giữa mô phỏng và thực địa được ghi ở cột hành động.
Tham chiếu: `C25·CoAlign` (claim số 25, entity chứa "CoAlign") · `S01b:975~referenceTime` (dòng 975 của snapshot `S01b-*.html` chứa chuỗi). Cả hai được `scripts/check_phase2_docs.py` kiểm.

## A · Căn chỉnh toạ độ
| ID | Giả định | Nhãn | Bằng chứng | Khoảng trống / hành động |
|---|---|---|---|---|
| A01 | Sai số pose của tác tử làm lệch thông điệp không gian và giảm hiệu năng cộng tác | **VERIFIED** | C25·CoAlign | Chỉ là phát biểu của một bài báo (cơ chế); không có ngưỡng sai số chấp nhận được |
| A02 | Có thể xử lý lỗi pose/bất đồng bộ trong khung cộng tác | **VERIFIED** | C22·V2X-ViT | Nguồn nói *phương pháp của họ* xử lý; không chứng minh cho late fusion |
| A03 | Late fusion (object-level) chịu lỗi hiệu chuẩn tốt hơn feature-level | HYPOTHESIS | — (ENG) | Không có claim so sánh. Kiểm bằng E-ablation: quét pose-error σ cho fusion mức object |
| A04 | Camera cố định (CCTV) có thể được đăng ký vào khung bản đồ chung với sai số bị chặn | UNKNOWN | C66·Vinhomes multi ; chỉ nói camera AI tồn tại | Không có nguồn về hiệu chuẩn camera. Sim: tham số tiêm sai. Thực địa: chưa biết, cần khảo sát ngoài registry |
| A05 | Định vị xe (ego pose) có mô hình lỗi Gaussian không thiên lệch | UNKNOWN | — | Cần nguồn hoặc đo; sim phải chạy cả lỗi có bias |
| A06 | CPM/SDSM quy định khung toạ độ tham chiếu đủ để quy đổi | SUPPORTED | S01b:1262~referenceTime | Có `referencePosition` trong management container; **chưa đọc** phần định nghĩa khung/độ chính xác. SAE J3224 sau paywall: UNKNOWN |

## B · Đồng bộ thời gian
| ID | Giả định | Nhãn | Bằng chứng | Khoảng trống / hành động |
|---|---|---|---|---|
| B01 | Bất đồng bộ thời gian xe–hạ tầng và chi phí truyền là vấn đề thật phải xử lý | **VERIFIED** | C14·DAIR-V2X | — |
| B02 | Bù thời gian (ngoại suy theo chuyển động) trước khi hợp nhất giảm tác hại bất đồng bộ | HYPOTHESIS | S05:11~Time Compensation Late Fusion | Snapshot chỉ *nêu tên* TCLF; chưa đọc kết quả định lượng. Ứng viên claim (cần duyệt) |
| B03 | Thông điệp chia sẻ mang mốc thời gian tham chiếu để tính tuổi dữ liệu | SUPPORTED | S01b:975~referenceTime ; S01b:819~T_GenCpm | Spec CPM có `referenceTime` và chu kỳ sinh T_GenCpm; chưa nâng thành claim; độ phân giải/độ chính xác của mốc chưa đọc |
| B04 | Đồng hồ các nút được đồng bộ đến mức đủ cho fusion (PTP/GNSS) | UNKNOWN | — | Không có nguồn. Sim: tiêm clock offset/drift làm tham số quét; không được hard-code "đồng bộ hoàn hảo" |
| B05 | Age of Information (AoI) là thước đo độ tươi phù hợp | HYPOTHESIS | — (ENG) | Khái niệm kỹ thuật phổ thông; chưa có nguồn trong registry. Định nghĩa vận hành nằm ở tài liệu 04 |
| B06 | Ngưỡng độ tươi tối đa chấp nhận được cho quyết định phanh | UNKNOWN | — | Không có nguồn; ngưỡng là tham số phải suy ra từ thí nghiệm (stopping-distance), không phải hằng số |

## C · Liên kết đối tượng (association)
| ID | Giả định | Nhãn | Bằng chứng | Khoảng trống / hành động |
|---|---|---|---|---|
| C01 | Trùng lặp object giữa nhiều nguồn là vấn đề cần giảm | SUPPORTED | C29·CPS redundancy ; C30·CPS redundancy ; S07:12~Value of Information | Câu then chốt ở snapshot, claim hiện chỉ giữ tiêu đề + phân loại |
| C02 | ETSI chọn object gửi theo giá trị thông tin (VoI) | SUPPORTED | S01b:933~should be omitted | Chưa nâng thành claim; công thức VoI nằm ở Annex E, **chưa đọc** |
| C03 | Liên kết track chéo nguồn (global ID) làm được với track CV + gating Mahalanobis | HYPOTHESIS | — (ENG) | Không có claim về association. Là rủi ro lớn khi mật độ cao; MVP chỉ 1 ngã tư nên chưa thử được giới hạn |
| C04 | Hợp nhất track đã hợp nhất sẽ gây đếm trùng/tương quan sai; cần phương pháp an toàn với tương quan chưa biết (vd. covariance intersection) | HYPOTHESIS | — (ENG) | Không có nguồn trong registry. Phải có test chứng minh: ghi lại tính nhất quán (NEES) với và không có biện pháp này |
| C05 | ID track nội bộ của nguồn ổn định đủ lâu để liên kết | UNKNOWN | — | Phụ thuộc tracker; chưa có gì |

## D · Fusion có tính đến bất định
| ID | Giả định | Nhãn | Bằng chứng | Khoảng trống / hành động |
|---|---|---|---|---|
| D01 | Object chia sẻ nên kèm độ tin cậy phân loại | SUPPORTED | S01b:350~classification confidence level | Định nghĩa trong spec; chưa claim; chưa đọc cách mã hoá |
| D02 | Thông điệp cho phép khai báo *vùng quan sát* và *vùng bị che* (shadowing), nên "không thấy" ≠ "trống" | SUPPORTED | S01b:846~shadowingApplies ; S01b:392~perception region confidence | Quan trọng cho invariant I3 (Safety). Chưa đọc chi tiết ngữ nghĩa |
| D03 | Fusion có covariance cải thiện an toàn so với fusion không có | UNKNOWN | — | Chưa có bằng chứng hay thí nghiệm. Phải là một ablation, không phải tiền đề |
| D04 | Độ tin cậy do detector báo đã hiệu chuẩn (calibrated) | UNKNOWN | — | Sim dùng detector mô hình hoá; phải ghi rõ không đại diện YOLO thật |
| D05 | Lỗi cảm biến mô hình hoá bằng nhiễu Gaussian đại diện đủ cho failure thực | HYPOTHESIS | — (ENG) | Cần thêm kiểu lỗi nặng đuôi, miss-detection theo cụm, ghost |

## E · Lỗi mạng và độ tin cậy kênh
| ID | Giả định | Nhãn | Bằng chứng | Khoảng trống / hành động |
|---|---|---|---|---|
| E01 | Ảnh hưởng của trễ/mất gói/lỗi cảm biến lên cooperative perception đã được định lượng | **UNKNOWN** | S14:186~under varying latency | Chính tài liệu FHWA ghi đây là **việc cần làm tiếp** ("evaluate CP performance under varying latency, packet loss, and sensor error"). Đây là khoảng trống có chứng cứ |
| E02 | Băng thông là nút thắt thúc đẩy chia sẻ thưa | SUPPORTED | C19·Where2comm ; C20·Where2comm | C20·Where2comm ; số **do tác giả tự báo** (>100,000×), chưa tái lập; không áp dụng cho object-level |
| E03 | Khi mất kết nối, xe lùi về ego-only mà vẫn an toàn | HYPOTHESIS | — | Đây là *yêu cầu thiết kế* (R-SAF-01), không phải sự kiện. Kiểm bằng E4 |
| E04 | Mô hình kênh (trễ, mất gói) trong sim đại diện cho V2X/5G thật | UNKNOWN | — | Không có số đo. Quét tham số công khai, không tuyên bố "thực tế" |
| E05 | Spec CPM đề cập cơ chế bảo mật thông điệp | SUPPORTED | C36·ETSI TS 103 324 | Chỉ là tham chiếu chuẩn (TS 103 097). Hiệu quả chống giả mạo/ghost: UNKNOWN |
| E06 | Kênh thông tin có thể bị giả mạo hoặc phát lại | HYPOTHESIS | — (ENG) | Cần test tiêm thông điệp cũ/giả; không có bằng chứng về mức độ rủi ro tại VN |

## F · Đánh giá an toàn
| ID | Giả định | Nhãn | Bằng chứng | Khoảng trống / hành động |
|---|---|---|---|---|
| F01 | Chia sẻ góc nhìn giúp "nhìn xuyên" vật che | **VERIFIED** | C18·V2VNet ; C28·Collaborative perception survey | Là phát biểu mục tiêu/động cơ của các bài báo; không phải kết quả cho kịch bản của ta |
| F02 | Camera hạ tầng → RSU → SDSM giúp xe nhường đường cho người đi bộ bị che | SUPPORTED | C45·FHWA CDA ; S14:109~smoothly yield | Kết quả demo do FHWA mô tả, một cấu hình; chưa nâng thành claim; không có số liệu thống kê |
| F03 | Ngưỡng TTC/near-miss/khoảng cách phanh phù hợp | UNKNOWN | — | Không có nguồn. Là tham số khai báo ở tài liệu 04 và phải được ghi vào kết quả |
| F04 | Khung an toàn SOTIF (ISO 21448) áp dụng được | UNKNOWN | — | Trang ISO trả 403; chưa đọc. Không được trích dẫn như đã tuân thủ |
| F05 | Kết quả mô phỏng chuyển giao sang thực địa | UNKNOWN | — | Không có nguồn; MVP phải ghi "kết quả chỉ có giá trị trong mô hình" |
| F06 | Bao ODD tham chiếu: ≤40 km/h, hạn chế thời tiết, có giám sát | SUPPORTED | C50·Hanoi Phenikaa-X ; C51·Hanoi Phenikaa-X ; S08:31~9:00 am to 4:30 pm | Tier B (báo). Giờ 9:00–16:30 + ban ngày chưa là claim. ODD của ta là **lựa chọn thiết kế lấy cảm hứng**, không phải tuân thủ pháp lý |
| F07 | Không có điều khoản riêng cho xe tự lái trong luật giao thông hợp nhất | SUPPORTED | C74·Luật TT-ATGT | Chỉ trong văn bản hợp nhất đã quét; không suy rộng ra toàn hệ pháp luật |
| F08 | Ego-only thận trọng (giới hạn tốc độ theo khoảng cách tới điểm xung đột) tránh được va chạm với người đi bộ bị che | HYPOTHESIS | — (ENG, số học động học ở 04 §3) | Không có nguồn. Là phép tính với tham số `[PARAM]`; chi phí thời gian ước tính ~1 s trên 30 m tiếp cận. Phải đo trong sim, và phải là baseline bắt buộc (E0-C) |
| F09 | Lợi ích của chia sẻ góc nhìn còn tồn tại khi so với baseline ego-only *đủ năng lực* (E0-C), không chỉ với baseline danh định (E0-N) | UNKNOWN | — | Không có nguồn nào so sánh như vậy. Đây là câu hỏi nghiên cứu trung tâm của MVP và quyết định cách đặt bất biến I2 (xem 02 §6, quyết định DEC-1) |

## G · Giả định kiến trúc và triển khai
| ID | Giả định | Nhãn | Bằng chứng | Khoảng trống / hành động |
|---|---|---|---|---|
| G01 | Chuẩn mô tả bên gửi phát danh sách object, bên nhận tự hợp nhất | SUPPORTED | C34·ETSI TS 103 324 ; C41·SAE J3224 | Từ scope; **chưa đọc** quy tắc nhận/xử lý. Nếu thiếu, mô hình "bên nhận tự hợp nhất" là diễn giải |
| G02 | Vai trò trung tâm (backend/cloud) là một ITS-S được công nhận | SUPPORTED | S01b:347~central ITS-S | Định nghĩa thuật ngữ; chưa claim |
| G03 | Pilot có trung tâm vận hành và nền tảng dữ liệu tập trung | SUPPORTED | C58·HCMC QTSC ; C57·HCMC QTSC | Tier B; không nói gì về việc *fuse* tập trung |
| G04 | Mô hình hạ tầng→RSU→broadcast có tiền lệ | SUPPORTED | C45·FHWA CDA | Một demo |
| G05 | Ngân sách trễ đầu–cuối chấp nhận được là X ms | UNKNOWN | — | Không có nguồn. Sẽ suy ra từ khoảng cách phanh (tài liệu 04), không giả định |
| G06 | CCTV Vinhomes dùng làm nguồn cảm biến | HYPOTHESIS | C66·Vinhomes multi | Chỉ chứng minh camera AI tồn tại (tier B, 2022). Không có nguồn nào cho API/hiệu chuẩn/chia sẻ. **Kịch bản là mô phỏng, không phải triển khai Vinhomes** |
| G07 | Mô hình vật lý nhẹ (mặt phẳng + cảm biến 2.5D) đủ trung thực cho logic cần kiểm — **đã thay bằng V01..V06 sau Amendment A1; giữ lại để truy vết** | HYPOTHESIS | — | Giới hạn: không kiểm động lực học xe, nhiễu cảm biến thật |
| G08 | Dữ liệu track (không ảnh) không phải dữ liệu cá nhân | UNKNOWN | C77·Luật BVDLCN ; C83·Nghị định 356 | Là câu hỏi pháp lý, chưa có nguồn; nguồn B không đủ. Cần tư vấn pháp lý, không tự kết luận |

## V · Vật lý và hiển thị (Amendment A1)
Nhãn áp dụng cho MVP mô phỏng. Registry **không có nguồn** về động lực học xe, ma sát đường nội khu, thông số actuator, hay độ trung thực mô phỏng; các giá trị này là `[PARAM]` và bài giải tích (PHY-02..05) chỉ chứng minh *mã khớp công thức*, không chứng minh công thức khớp xe thật.
| ID | Giả định | Nhãn | Bằng chứng | Khoảng trống / hành động |
|---|---|---|---|---|
| V01 | Xe đạp động học + vòng ma sát đủ cho v ≤ 11 m/s và `a_y ≤ 0.5 μg` | HYPOTHESIS | — (ENG) | Chỉ đối chiếu giải tích (PHY-02..05); không có dữ liệu xe thật. Cảnh báo `outside_model_validity` khi vượt miền |
| V02 | μ = 0.8 đại diện đường nội khu khô tại Việt Nam | UNKNOWN | — | Không có nguồn; quét độ nhạy μ∈{0.5, 0.8}; không dùng làm kết luận |
| V03 | t_act, j_max, a_brk đại diện xe tự hành thật | UNKNOWN | — | Không có nguồn; tham số công khai trong cấu hình; quét độ nhạy |
| V04 | Va chạm OBB/capsule và kết thúc tại va chạm đủ cho metric va chạm và tốc độ va chạm | HYPOTHESIS | — (ENG) | Không có mô hình chấn thương/biến dạng; "tốc độ va chạm" không là thước đo hậu quả thật |
| V05 | Cảm biến 2.5D thống kê (FOV, che khuất theo độ cao, nhiễu) đại diện camera/lidar thật | HYPOTHESIS | — (ENG) | Liên quan D04/D05; không đại diện detector học máy |
| V06 | Người đi bộ động học không phản ứng đủ cho S01 | HYPOTHESIS | — | Không có hành vi phản ứng/đám đông; kết quả không tổng quát hoá |
| V07 | Tất định bit-exact tái lập trong cùng môi trường | HYPOTHESIS | — (ENG) | Kiểm bằng PHY-01; liên nền tảng chưa biết, chỉ hứa dung sai |
| V08 | Giao diện `PhysicsBackend` cho phép thay bằng CARLA mà không đổi logic phía trên | UNKNOWN | C26·OpenCDA ; chỉ chứng minh có framework co-sim | Chưa đọc; lớp dịch điều khiển/toạ độ chưa xác thực; cổng PX-1 chưa làm |
| V09 | R3F + instancing đạt ngân sách khung hình với cảnh diorama | HYPOTHESIS | — (ENG) | Sandbox không GPU nên không đo được hiệu năng thật; cần máy tham chiếu |
| V10 | Tài sản dựng thủ tục đạt mức "premium" theo ảnh tham chiếu | UNKNOWN | — | **Ảnh tham chiếu chưa được nhận**; không thể đánh giá |

## Việc cần làm với registry (ứng viên, **chưa thực hiện**, cần bạn duyệt)
1. Nâng thành claim tier A từ snapshot sẵn có: `S01b:975`, `S01b:1262`, `S01b:846`, `S01b:350`, `S01b:933`, `S14:186`, `S14:109`, `S05:11`, `S07:12`, `S08:31`.
2. Các cặp claim cùng entity/field/value nhưng khác origin — C47·Hanoi Phenikaa-X ; C48·Hanoi Phenikaa-X ; và C81·Nghị định 356 ; C82·Nghị định 356 — là cố ý để corroborate, không phải trùng lỗi.
3. Nguồn cần tìm (hiện **không có**): hiệu chuẩn camera hạ tầng, đồng bộ thời gian V2X, association đa nguồn, đánh giá lỗi mạng, SOTIF, mô hình kênh V2X.
4. ID claim hiện là số dòng, **không ổn định** nếu build lại. Đề xuất thêm `claim_id` bền khi được duyệt (sẽ đổi dữ liệu, nên chưa làm).
