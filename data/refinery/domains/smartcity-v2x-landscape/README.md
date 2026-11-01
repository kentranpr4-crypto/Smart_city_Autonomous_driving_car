# Domain mới

Điền schema và nguồn; claims.jsonl ban đầu rỗng, không có claim giả.
Mẫu số chỉ điền khi có basis; refresh_days là metadata, chưa có gate độ tươi.
Chạy refinery.py rồi bites.py với đường dẫn domain này. Đọc README của hộp Refinery.

## Quy trình cào (đã chạy 2026-11-01)
`scripts/fetch_snapshot.py` (curl, lưu raw + text + sha256 + thời điểm) → `scripts/claims_data.py` (claim viết tay, mỗi span phải verbatim) → `scripts/build_claims.py` (từ chối ghi nếu span lệch) → `refinery.py` → `bites.py`.
Tier: A = nguồn gốc (tác giả/tổ chức ban hành: arXiv, ETSI, SAE, FHWA, văn bản luật hợp nhất trên chinhphu.vn). B = báo chí/cổng thông tin trung gian. C = trang tổng hợp tự động (OECD AIM, "[AI generated]").
`corroborated` (✓✓) chỉ khi ≥2 origin_id khác nhau cùng value. Origin do người nghiên cứu khai: hai bài Hà Nội và hai bài NĐ 356 có thể cùng bắt nguồn từ một thông cáo, chưa kiểm.
Giá trị có extraction=normalized là bản rút gọn của span; người đọc phải đối chiếu span.
