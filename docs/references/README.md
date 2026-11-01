# Ảnh tham chiếu thị giác (VIS-08)

Đặt ảnh tham chiếu premium isometric low-poly vào thư mục này (PNG/JPG/WebP). Sau đó chạy:

```bash
sha256sum docs/references/*.{png,jpg,jpeg,webp} 2>/dev/null > docs/references/SHA256SUMS
```

**Trạng thái hiện tại: KHÔNG CÓ ẢNH.** `make check` báo `VIS-08 = BLOCKED` cho tới khi có ít nhất một file ảnh ở đây.
Quy tắc: không ai (kể cả agent) được suy đoán chất lượng hay bố cục từ ảnh không truy cập được. Ngưỡng thang đánh giá VIS-08 do chủ việc đặt sau khi xem ảnh và trước khi dựng (docs/phase2/07 §10.7).
