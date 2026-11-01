# Nhật ký cào nguồn (sinh từ capture_manifest.jsonl, lần thử cuối của mỗi ID)

Quy ước: `snapshots/<ID>.html` là **văn bản đã trích** từ `raw/<ID>.*` (đuôi .html chỉ vì `bites.py` chỉ glob *.html). `raw/` giữ byte gốc, `sha256` là của byte gốc.
Trạng thái `BLOCKED_OR_FAILED` = không lấy được; **không có claim nào dựa vào các nguồn này**.

| ID | Trạng thái | HTTP | Truy cập (UTC) | sha256 raw | URL |
|---|---|---|---|---|---|
| S03-v2v4real | OK | 200 | 2026-11-01T04:43:11Z | 4980134412f8 | https://arxiv.org/abs/2303.07601 |
| S04-opv2v | OK | 200 | 2026-11-01T04:43:12Z | c1b815132cfe | https://arxiv.org/abs/2109.07644 |
| S05-dairv2x | OK | 200 | 2026-11-01T04:43:12Z | 19c3af9b0aed | https://arxiv.org/abs/2204.05575 |
| S06-cp-survey | OK | 200 | 2026-11-01T04:43:12Z | 4974f177959f | https://arxiv.org/abs/2301.06262 |
| S07-voi-review | OK | 200 | 2026-11-01T04:43:12Z | 3a4fed998997 | https://arxiv.org/abs/2501.01200 |
| S15-v2xsim | OK | 200 | 2026-11-01T04:43:12Z | a300607ad692 | https://arxiv.org/abs/2202.08449 |
| S16-v2vnet | OK | 200 | 2026-11-01T04:43:13Z | 21f9e5727164 | https://arxiv.org/abs/2008.07519 |
| S17-where2comm | OK | 200 | 2026-11-01T04:43:13Z | 27dbc68a071f | https://arxiv.org/abs/2209.12836 |
| S18-v2xvit | OK | 200 | 2026-11-01T04:43:13Z | 05dfebe00c55 | https://arxiv.org/abs/2203.10638 |
| S19-cobevt | OK | 200 | 2026-11-01T04:43:13Z | 99b71a228459 | https://arxiv.org/abs/2207.02202 |
| S01-etsi-cpm-forge | OK | 200 | 2026-11-01T04:43:13Z | cfa1394d2441 | https://forge.etsi.org/rep/ITS/asn1/cpm_ts103324 |
| S01b-etsi-cpm-pdf | OK | 200 | 2026-11-01T04:43:16Z | baba360d5311 | https://www.etsi.org/deliver/etsi_ts/103300_103399/103324/02.01.01_60/ts_103324v020101p.pdf |
| S02-sae-j3224 | OK | 200 | 2026-11-01T04:43:17Z | a069d6562d91 | https://saemobilus.sae.org/content/J3224_202208 |
| S14-usdot-cda | OK | 200 | 2026-11-01T04:43:18Z | 9d7299b15453 | https://rosap.ntl.bts.gov/view/dot/88873/dot_88873_DS1.pdf |
| S08-hanoi | OK | 200 | 2026-11-01T04:43:19Z | ac23fef63d56 | https://news.tuoitre.vn/hanoi-allows-24-month-trial-of-autonomous-buses-robotaxis-103260827192510373.htm |
| S09-hcmc | OK | 200 | 2026-11-01T04:43:21Z | 67209dacdd5a | https://news.tuoitre.vn/ho-chi-minh-city-to-pilot-level-4-self-driving-vehicles-in-real-world-conditions-103260702161609814.htm |
| S10a-vinfast-tuoitre | OK | 200 | 2026-11-01T04:43:22Z | 0e4108e781fc | https://tuoitre.vn/vinfast-lam-xe-tu-lai-giai-quyet-van-de-giao-thong-2026060208492671.htm |
| S10b-oecd | OK | 200 | 2026-11-01T04:43:24Z | fa6bddfd6bb7 | https://oecd.ai/en/incidents/2026-05-31-4680 |
| S11-grandpark | OK | 200 | 2026-11-01T04:43:25Z | ce6c5ed0cf10 | https://vneconomy.vn/chinh-thuc-ra-mat-du-an-vinhomes-grand-park.htm |
| L01-luat-ttatgt-chinhphu | OK | 200 | 2026-11-01T04:44:07Z | 9a20c8e616d4 | https://datafiles.chinhphu.vn/cpp/files/vbpq/2026/3/55-vbhn-vpqh.pdf |
| L02-luat-bvdlcn-en | BLOCKED_OR_FAILED | 403 | 2026-11-01T04:44:10Z |  | https://thuvienphapluat.vn/van-ban/EN/Bo-may-hanh-chinh/Law-91-2025-QH15-Personal-Data-Protection/665440/tieng-anh.aspx |
| L03-nd356 | BLOCKED_OR_FAILED | 403 | 2026-11-01T04:44:11Z |  | https://thuvienphapluat.vn/van-ban/Quyen-dan-su/Nghi-dinh-356-2025-ND-CP-huong-dan-Luat-Bao-ve-du-lieu-ca-nhan-687428.aspx |
| L04-bvdlcn-hatinh | OK | 200 | 2026-11-01T04:44:11Z | 573396e31d01 | https://hatinh.gov.vn/vi/bai-viet/quy-dinh-bao-ve-du-lieu-ca-nhan-thu-duoc-tu-hoat-dong-ghi-am-ghi-hinh-tai-noi-cong-cong |
| L05-pwc-nd356 | BLOCKED_OR_FAILED | 403 | 2026-11-01T04:44:13Z |  | https://www.pwc.com/vn/vn/publications/2026/20260128-new-rules-personal-data-protection.pdf |
| L06-hanoi-sandbox | OK | 200 | 2026-11-01T04:44:13Z | 11e667df4928 | https://thoibaotaichinhvietnam.vn/ha-noi-trao-quyet-dinh-thu-nghiem-sandbox-xe-tu-hanh-va-dat-hiem-cho-hai-doanh-nghiep-203609.html |
| L07-baovanhoa-sandbox | OK | 200 | 2026-11-01T04:44:15Z | 685b5add2bd4 | https://baovanhoa.vn/xe/chinh-thuc-thu-nghiem-co-kiem-soat-xe-tu-hanh-264052.html |
| L08-tt52-luatvietnam | OK | 200 | 2026-11-01T04:44:17Z | f3660c1ef3d7 | https://luatvietnam.vn/tin-van-bang-moi/tong-hop-van-ban-huong-dan-luat-trat-tu-an-toan-giao-thong-duong-bo-2024-186-100121-article.html |
| V01-vinhomes-security | OK | 200 | 2026-11-01T04:44:56Z | d873f87fe28a | https://baodauthau.vn/vinhomes-trien-khai-he-thong-an-ninh-da-lop-thong-minh-tai-cac-dai-do-thi-post130552.html |
| V02-vinai-guardpro | BLOCKED_OR_FAILED | 403 | 2026-11-01T04:44:19Z |  | https://vingroup.net/en/news/detail/2801/vinai-hop-tac-qualcomm-ra-mat-guardpro-giai-phap-an-ninh-cho-do-thi-thong-minh |
| V03-vizone | OK | 200 | 2026-11-01T04:44:19Z | 78cefd4dafac | https://doanhnhan.baophapluat.vn/vinbigdata-ra-mat-bo-giai-phap-phan-tich-hinh-anh-thong-minh-vizone-64232.html |
| V04-vinbus-advantech | OK | 200 | 2026-11-01T04:44:21Z | 4520b2eddd79 | https://vnbusiness.vn/vinbus-va-advantech-hop-tac-chien-luoc-phat-trien-he-thong-thong-minh-cho-xe-buyt-dien.html |
| V05-oceancity-tech | OK | 200 | 2026-11-01T04:44:23Z | 1fd90a584b4c | https://doanhnhan.baophapluat.vn/dieu-it-biet-ve-bo-ba-tru-cot-cong-nghe-thong-minh-tai-ocean-city-76129.html |
| V02-vinai-guardpro-alt | OK | 200 | 2026-11-01T04:44:57Z | 81150e5258bc | https://www.vinai.io/?p=3730 |
| S20-opencda | OK | 200 | 2026-11-01T04:45:54Z | 2c8f638be331 | https://arxiv.org/abs/2107.06260 |
| S21-coalign | OK | 200 | 2026-11-01T04:45:54Z | a793f4b0f05d | https://arxiv.org/abs/2211.07214 |
| S22-iso21448 | BLOCKED_OR_FAILED | 403 | 2026-11-01T04:45:54Z |  | https://www.iso.org/standard/77490.html |
| S23-ieee1609-2 | OK | 200 | 2026-11-01T04:45:54Z | b51e9f785051 | https://standards.ieee.org/ieee/1609.2/6985/ |
| S24-3gpp-v2x | OK | 200 | 2026-11-01T04:45:59Z | 7a2d34047ae6 | https://www.3gpp.org/technologies/v2x |
| L09-nd356-vbpl | OK | 200 | 2026-11-01T04:46:02Z | 04b6d5f36ea9 | https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=177000 |
| L10-ey-nd356 | OK | 200 | 2026-11-01T04:46:17Z | 237ae9286a77 | https://www.ey.com/vi_vn/technical/tax/tax-and-law-updates/nghi-dinh-so-356-2025-nd-cp-quy-dinh-chi-tiet-mot-so-dieu-va-bien-phap-thi-hanh-luat-bao-ve-du-lieu-ca-nhan |
| L11-luatvietnam-nd356 | OK | 200 | 2026-11-01T04:46:18Z | 3b041ba5b4ab | https://luatvietnam.vn/dan-su/nghi-dinh-356-2025-nd-cp-quy-dinh-chi-tiet-luat-bao-ve-du-lieu-ca-nhan-422896-d1.html |

## Không lấy được / không dùng
- L02 Luật 91/2025 (EN) và L03 NĐ 356 trên thuvienphapluat.vn, L05 PwC PDF, S22 ISO 21448: HTTP 403 (chặn bot) → NOT_VERIFIED từ nguồn gốc.
- L09 vbpl.vn: trả 83 byte (không có nội dung).
- S23 IEEE 1609.2: trang trả "removed or temporarily unavailable" → snapshot đã xoá, không dùng.
- S24 3GPP V2X: tải được nhưng chỉ là trang index, không có claim.
- V02 GuardPro (VinAI): vingroup.net 403; vinai.io trả trang không có số liệu → các số "9.000 luồng camera / 150 luồng per accelerator" từ WebSearch **chưa kiểm, không đưa vào claims**.

## Null có chủ đích (không có nguồn → không điền)
- Điều khoản riêng về xe tự lái trong Luật 36/2024/QH15: quét văn bản hợp nhất (L01) bằng regex `tự lái|tự hành|không người lái|tự động hóa` → 1 hit, là "tàu bay không người lái" (UAV), không phải xe. Kết luận hẹp: *trong văn bản hợp nhất này không thấy điều khoản riêng về xe tự lái*. Không suy rộng ra "pháp luật VN chưa có quy định".
- Nghị định 353/2025/NĐ-CP (sandbox), Nghị quyết 26/2026/NQ-HĐND Hà Nội: chỉ xuất hiện trong tóm tắt WebSearch → NOT_FETCHED.
- Kết nối Vinhomes Grand Park ↔ pilot xe tự hành: không có nguồn → null.
- Số lượng camera/khuôn mặt thực tế tại Vinhomes: null.
