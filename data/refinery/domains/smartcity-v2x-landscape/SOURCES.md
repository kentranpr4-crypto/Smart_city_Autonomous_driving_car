# Seed list nguồn (ứng viên cần cào)

Trạng thái: **NOT_FETCHED** — sandbox chặn host (egress policy) nên chưa có snapshot, chưa có claim.
Mục dưới chỉ là *kết quả WebSearch* (tóm tắt của công cụ tìm kiếm, chưa phải nguyên văn nguồn). Không được dùng làm evidence.

| ID | Thực thể | Loại | URL ứng viên | Host cần allow | Tier dự kiến | Việc cần trích |
|---|---|---|---|---|---|---|
| S01 | ETSI TS 103 324 (CPM) | standard | https://forge.etsi.org/rep/ITS/asn1/cpm_ts103324 | forge.etsi.org, www.etsi.org | A | version, ngày, scope |
| S02 | SAE J3224 (SDSM) | standard | https://saemobilus.sae.org/content/J3224_202208 | saemobilus.sae.org | A | version, ngày, scope |
| S03 | V2V4Real | dataset | https://arxiv.org/abs/2303.07601 | arxiv.org | A | số frame/box/class (nguồn mâu thuẫn: 2022 vs CVPR 2023) |
| S04 | OPV2V | dataset | https://arxiv.org/abs/2109.07644 | arxiv.org | A | số frame/box |
| S05 | DAIR-V2X | dataset | https://arxiv.org/abs/2204.05575 | arxiv.org | A | số frame/class (bảng khác nhau báo 39K) |
| S06 | Collaborative Perception survey | survey | https://arxiv.org/abs/2301.06262 | arxiv.org | B | phân loại early/intermediate/late |
| S07 | VoI redundancy mitigation review | survey | https://arxiv.org/abs/2501.01200 | arxiv.org | B | quy tắc chọn object gửi CPM |
| S08 | Hà Nội thử nghiệm 24 tháng (Phenikaa-X) | pilot/regulation | https://news.tuoitre.vn/hanoi-allows-24-month-trial-of-autonomous-buses-robotaxis-103260827192510373.htm | news.tuoitre.vn | B | giới hạn tốc độ, thời tiết, tuyến, ngày |
| S09 | TP.HCM pilot Level 4 (07–09/2026) | pilot | https://news.tuoitre.vn/ho-chi-minh-city-to-pilot-level-4-self-driving-vehicles-in-real-world-conditions-103260702161609814.htm | news.tuoitre.vn | B | đơn vị vận hành, tuyến, nền tảng dữ liệu |
| S10 | VinFast–NVIDIA–Autobrains robotaxi L4 | deployment | https://oecd.ai/en/incidents/2026-05-31-4680 ; https://tuoitre.vn/vinfast-lam-xe-tu-lai-giai-quyet-van-de-giao-thong-2026060208492671.htm | oecd.ai, tuoitre.vn | B | phạm vi, mốc thời gian |
| S11 | Vinhomes Grand Park (thành phố thông minh, VinBus) | deployment | https://vneconomy.vn/chinh-thuc-ra-mat-du-an-vinhomes-grand-park.htm | vneconomy.vn | B | hạ tầng thông minh thực tế đã công bố |
| S12 | Luật Trật tự, an toàn giao thông đường bộ 2024 (điều khoản xe tự lái) | regulation | CHƯA TÌM ĐƯỢC nguồn chính thức | thuvienphapluat.vn / vbpl.vn | A | điều khoản xe tự hành — **null** cho đến khi có nguồn |
| S13 | Nghị định 13/2023/NĐ-CP (dữ liệu cá nhân) + Luật BVDLCN | regulation | CHƯA TÌM ĐƯỢC nguồn chính thức | như trên | A | quy định camera/ảnh khuôn mặt/biển số — **null** |
| S14 | MCity SDSM RSU (U-Mich) + FHWA/USDOT CDA perception sharing | deployment | https://rosap.ntl.bts.gov/view/dot/88873/dot_88873_DS1.pdf | rosap.ntl.bts.gov | A | kịch bản VRU qua RSU |

## Thông tin đã thấy nhưng chưa kiểm (từ tóm tắt tìm kiếm)
- Một nguồn quảng bá (LinkedIn Phenikaa-X) nói VF8 là xe tự lái đầu tiên thử trên đường công cộng VN → **claim chưa kiểm, tier C**.
- Không tìm thấy nguồn nào nối trực tiếp Vinhomes Grand Park với pilot xe tự hành → để **null**, không suy diễn.
