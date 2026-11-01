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
