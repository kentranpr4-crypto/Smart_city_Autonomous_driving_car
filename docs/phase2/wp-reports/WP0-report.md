# WP0 — Khung repo, phụ thuộc khoá, `make check`, smoke toolchain

**Trạng thái: PASS** (phạm vi WP0). Ngày 2026-11-01. Gate liên quan: AC-VS-13, toolchain. Không động tới Refinery data.

## Mã nguồn chạy được
`Makefile` (`setup`, `check`, `test`, `test-physics`, `build-web`, `smoke-web`) · `scripts/check_repo.py` · `scripts/audit_deps.py` · `scripts/make_lock.py` · `requirements.in/.lock` · `web/` (Vite + R3F smoke) · `schemas/{scenario,telemetry}.schema.json` · `docs/references/` (+README) · `.gitignore`.

## Acceptance criteria và kết quả
| AC | Tiêu chí | Kết quả | Bằng chứng |
|---|---|---|---|
| WP0-01 | Phụ thuộc được kiểm tuổi/license/dung lượng/tương thích **trước khi cài**; lock có băm | **PASS** | `DEPS-audit.md`; `make_lock.py`: 29 gói Python, none < 14 ngày; npm 107 gói, none < 14 ngày; `npm audit` 0 |
| WP0-02 | Tái lập từ cây sạch bằng lockfile | **PASS** | `evidence/wp0/clean_room.txt`: bản sao không có `.venv`/`node_modules`, `make setup` 18 s, `pip check` sạch, `make check` hai lần cho cùng kết quả |
| WP0-03 | `make check` chạy và báo từng gate với PASS/FAIL/BLOCKED/NOT_CHECKED | **PASS** | `evidence/wp0/make_check.txt`: 14 PASS, 0 FAIL, 1 BLOCKED, 11 NOT_CHECKED |
| WP0-04 | Schema hợp lệ | **PASS** | 2 schema Draft 2020-12 qua `check_schema`; dùng trong test scenario/telemetry |
| WP0-05 | Registry/evidence không đổi | **PASS** | REG-1 (git diff vs `66f1a64` rỗng), REG-2 digest `a68fc24fbf62a74a`, REG-3 5/5 bite cắn |
| WP0-06 | Toolchain web build và tạo được WebGL context | **PASS (smoke)** | `npm run build` xong 1.2 s; `evidence/wp0/toolchain-smoke.json`: WebGL2 true, 0 lỗi console |
| WP0-07 | VIS-08 báo đúng trạng thái khi thiếu ảnh | **PASS** (cơ chế) → VIS-08 = **BLOCKED** | `docs/references/` không có ảnh; `make check` in `BLOCKED` |

## Screenshot
`evidence/wp0/toolchain-smoke.png`: khối lập phương R3F + bóng, **chỉ để chứng minh toolchain render**. **Không phải bằng chứng VIS**, không có thành phố, không có trạng thái backend.

## Phát hiện trong quá trình làm (nêu thẳng)
1. **Repo đang theo dõi file bytecode** `.claude/skills/refinery/__pycache__/refinery.cpython-313.pyc` (từ commit cài kit). Lần clean-room đầu báo REG-1 FAIL vì Refinery ghi lại file này bằng interpreter khác. Không phải dữ liệu bằng chứng bị đổi. **Xử lý:** gate chạy với `PYTHONDONTWRITEBYTECODE=1` và REG-1 loại `**/__pycache__/**`. Tôi **không xoá** file tracked; đề xuất bạn quyết định `git rm --cached` cho nó (hygiene), ngoài phạm vi đã duyệt.
2. Lần "clean-room" đầu của tôi **không hợp lệ**: `rsync` không có nên chuỗi lệnh dừng và các lệnh sau chạy trong repo gốc. Đã phát hiện, làm lại đúng bằng `git ls-files` + kiểm tra `.venv`/`node_modules` vắng mặt trước khi chạy.
3. Phụ thuộc bắc cầu quá mới (opentelemetry-api, rolldown…) được ghim; xem `DEPS-audit.md`.

## Known limitations
- Hash khoá Python chỉ cho linux/x86_64 + CPython 3.13.
- Smoke chạy bằng **SwiftShader (render phần mềm)**: `ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device…))`. Frame time đo (p50 16.7 ms, p95 83.3 ms) **không đại diện** hiệu năng sản phẩm; VIS-07 cần máy tham chiếu (OD-9).
- Không quét lỗ hổng Python (chưa cài `pip-audit`).
- `overrides` npm là bản vá tạm theo quy tắc tuổi; khi nâng cấp phải kiểm lại.
- `make reproduce` mới là khung (dùng được từ WP1 qua `backend.run --verify-hash`).

## Chưa làm / không thuộc WP0
PHY-07/08, mọi VIS (ngoài smoke), đo hiệu năng, thành phố 3D, dịch vụ WebSocket.
