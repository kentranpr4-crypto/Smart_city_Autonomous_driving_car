# TIP + Báo cáo · Smart City cooperative perception: brainstorm + cào dữ liệu

## TIP
- **Mục tiêu:** brainstorm kiến trúc; dựng registry nguồn bằng Refinery.
- **Đầu ra:** `docs/brainstorm/01-…md`; `data/refinery/domains/smartcity-v2x-landscape/` (domain.yaml, SOURCES.md, claims.jsonl, snapshots/).
- **AC-01** Mọi claim có snapshot và evidence_span khớp (refinery.py PASS + bites.py PASS).
- **AC-02** Chỗ không có nguồn là null, nguồn mâu thuẫn là disputed.
- **AC-03** Brainstorm gắn nhãn EV / INF / PROP / ASSUME.
- **Giới hạn:** không bịa snapshot; không đưa số liệu chưa kiểm vào claims.

## Báo cáo — trạng thái: **PARTIAL**
| AC | Kết quả | Evidence |
|---|---|---|
| AC-01 | **NOT_CHECKED** | claims.jsonl rỗng. `refinery.py` chạy OK trên domain rỗng; `bites.py` lỗi vì không có snapshot để chèn lỗi |
| AC-02 | PARTIAL | S12, S13 (luật VN) ghi null trong SOURCES.md; mâu thuẫn số frame dataset ghi nhận, chưa phân xử |
| AC-03 | PASS (tự kiểm) | Brainstorm dùng nhãn nhất quán |

**Chặn (BLOCKED một phần):** egress của sandbox từ chối arxiv.org, news.tuoitre.vn, saemobilus.sae.org, vneconomy.vn, forge.etsi.org (curl 403 / WebFetch ENOTFOUND). Chỉ WebSearch hoạt động, và kết quả của nó là tóm tắt, không phải nguyên văn nên không dùng làm evidence.
**Cần chủ việc:** cho phép các host trên trong Network access của environment (hoặc nâng mức truy cập), sau đó chạy lại bước cào.


---
# Cập nhật lần 2 · Network Full: cào lọc thật

## Báo cáo — trạng thái: **PARTIAL** (phần lớn đạt, còn nguồn pháp lý gốc chưa đọc)
| AC | Kết quả | Evidence |
|---|---|---|
| AC-01 span khớp + engine | **PASS (tự kiểm bằng engine)** | `build_claims.py` từ chối ghi nếu span lệch; `refinery.py` → `VALIDATION PASSED`, idempotent OK, auditor OK; `bites.py` → 5/5 bite áp dụng được CẮN ✓, 9 gate chuyên ngành N/A (chưa khai) |
| AC-02 null/disputed | **PASS** | Null có chủ đích liệt kê ở SOURCES.md (xe tự lái trong Luật 36/2024, NĐ 353, liên kết Vinhomes–AV). Không có disputed thật: mâu thuẫn số frame ở bản đầu hoá ra là nguồn thứ cấp sai, giải quyết bằng nguồn gốc (xem 02-evidence-findings §1) |
| AC-03 nhãn trong brainstorm | PASS (tự kiểm) | 02-evidence-findings dùng FACT/INF/NULL |
| AC-04 (mới) mỗi claim có URL, thời điểm truy cập, snapshot, bằng chứng | **PASS** | claims.jsonl.capture{url,fetched_at,snapshot,source,origin_id}; sha256 raw trong capture_manifest.jsonl |

**Giới hạn phải nói rõ**
- Engine PASS chứng minh *span có trong snapshot*, không chứng minh value đúng ngữ nghĩa. Tôi đã đọc từng span khi viết claim, đó là tự kiểm, chưa có người thứ hai duyệt (`review.py` chưa dùng).
- Một số span rất ngắn ("Issued", "CVPR2022") là bằng chứng yếu; value ở các claim `normalized` là bản rút gọn của span.
- Nguồn gốc luật VN (thuvienphapluat) bị 403; Luật 91/2025 và NĐ 356 dựa trên nguồn tier B. Cần chủ việc đối chiếu bản chính thức trước khi trích trong báo cáo đồ án.
- Mẫu số 25 là danh mục đóng chọn có chủ đích, không phải coverage của lĩnh vực.
- `bites.py` chỉ chèn lỗi vào snapshot `*.html` nên snapshot văn bản đặt đuôi .html (ghi trong README domain). Kit không bị sửa.

**Cần chủ việc:** (1) xác nhận phạm vi MVP (xem brainstorm 01 §8); (2) đồng ý để tôi cào tiếp nguồn pháp lý bằng host khác nếu bạn tìm được link chính thức (vanban.chinhphu.vn / congbao); (3) chọn người duyệt claim (`review.py --by`).
