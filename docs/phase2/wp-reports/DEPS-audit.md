# Kiểm toán phụ thuộc trước khi cài (2026-11-01)

Phạm vi: dependency đã được duyệt trong OD-10. Quy tắc áp dụng: phiên bản **≥ 14 ngày tuổi** tại 2026-11-01 (cutoff 2026-10-18), peer deps tương thích, license rõ, ghi dung lượng, lockfile có băm. Script tái lập: `scripts/audit_deps.py`, `scripts/make_lock.py`. Dữ liệu thô: `evidence/wp0/deps-audit-direct.json`.

## Trực tiếp (npm, `web/package.json`, phiên bản chính xác)
| Gói | Phiên bản | Công bố | License | Unpacked | Ghi chú tương thích |
|---|---|---|---|---|---|
| react / react-dom | 19.3.1 | 2026-10-14 | MIT | 174 KB / 7.9 MB | thoả `@react-three/fiber` peer `>=19 <19.4` |
| three | 0.186.1 | 2026-09-24 | MIT | 20 MB | mới nhất 0.187.0 bị loại (quá mới) |
| @react-three/fiber | 9.8.2 | 2026-10-14 | MIT | 2.3 MB | cần React 19 |
| @react-three/drei | 10.7.9 | 2026-09-25 | MIT | 1.7 MB | cần fiber ^9, React ^19 |
| zustand | 5.0.15 | 2026-08-13 | MIT | 93 KB | 5.0.16 quá mới |
| vite | 8.3.4 | 2026-10-08 | MIT | 2.3 MB | 8.3.5 quá mới |
| @vitejs/plugin-react | 6.1.2 | 2026-10-05 | MIT | 45 KB | cần vite ^8 |
TypeScript **không** dùng (giảm bề mặt phụ thuộc).

## Trực tiếp (Python, `requirements.in` → `requirements.lock`, băm sha256)
numpy 2.5.4 (BSD-3 + MIT/Zlib/CC0, wheel 16.6 MB) · PyYAML 6.0.3 (MIT) · jsonschema 4.26.0 (MIT) · pytest 9.1.1 (MIT) · **hypothesis 6.170.1 (MPL-2.0, chỉ dùng khi test, không đóng gói)** · fastapi 0.146.0 (MIT) · starlette 1.9.0 (BSD-3) · pydantic 2.14.1 (MIT) · uvicorn 0.54.0 (BSD-3) · websockets 17.2 (BSD-3). Cây đầy đủ: **29 gói**, `pip check` sạch.

## Phát hiện và xử lý
| Phát hiện | Xử lý |
|---|---|
| `opentelemetry-api` 1.45.2 (bắc cầu qua fastapi) mới 3 ngày tuổi | Ghim 1.45.1 (2026-10-06) trong `requirements.in`; `make_lock.py` **thất bại** nếu còn gói < 14 ngày |
| 21 gói npm bắc cầu < 14 ngày (rolldown 1.2.16 + 15 binding, `@oxc-project/types` 0.156.0, postcss 8.5.32, `@monogrid/gainmap-js` 3.7.2, `@types/three` 0.187.0, hls.js 1.7.4) | `overrides` trong `web/package.json`: rolldown 1.2.14, `@oxc-project/types` 0.154.0, postcss 8.5.31, gainmap-js 3.6.0, `@types/three` 0.186.0, hls.js 1.7.3. Sau đó: **107 gói trong lock, 0 gói < 14 ngày** |
| `webgl-constants` 1.1.1 không khai `license` trong package.json | Đọc tarball: có `LICENSE` là **MIT** (© 2019 Tim van Scherpenzeel). Ghi nhận, không chặn |
| `lightningcss*` (12 gói) MPL-2.0 | Công cụ build (vite), không nằm trong sản phẩm chạy; ghi nhận |
| `fsevents` có install script | Chỉ macOS; cài với `--ignore-scripts`; không cài trên Linux |
| Lỗ hổng | `npm audit` (cả prod và dev): **0 vulnerabilities**. Python: **NOT_CHECKED** (`pip-audit` chưa cài) |

## Dung lượng thực tế sau cài
`.venv` ≈ 129–132 MB · `web/node_modules` ≈ 237 MB · `web/dist` ≈ 1.1 MB (bundle 1.13 MB, 310 KB gzip). Đĩa còn trống ≈ 30 GB trước khi cài.

## Giới hạn
Hash trong `requirements.lock` ghim wheel cho **linux/x86_64, CPython 3.13**; nền tảng khác phải sinh lại. Quy tắc tuổi chỉ đúng tại ngày kiểm; lockfile giữ phiên bản, không tự cập nhật. Tính hợp lệ license dựa trên metadata registry và (cho 1 gói) tarball, không phải rà soát pháp lý.
