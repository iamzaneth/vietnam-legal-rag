# VBPL 50-document Extract validation

Run: 2026-10-06T17:50:47.575095+00:00 → 2026-10-08T03:34:28.969025+00:00 (UTC). Schema/parser: 2.3.2 / 2.3.2.

Exactly 50 new documents were captured and processed in five waves, alternating Central and Local throughout. The original golden is additional to the sample.

Final Extract: 41 success, 9 success_with_warnings, 0 failed. All outputs were regenerated and independently revalidated after the last parser change.

| Quality | Count | Rate |
|---|---:|---:|
| schema_valid | 50/50 | 100% |
| deterministic | 50/50 | 100% |
| meaningful_text_preserved | 50/50 | 100% |
| semantic_complete | 41/50 | 82% |

Diagnostics: {'info': 50, 'warning': 28, 'error': 0, 'fatal': 0}. Structure checks: {'numbered_candidates': 0, 'orphan_nodes': 0, 'ambiguous_tables': 1, 'structured_paragraph_list_issues': 0, 'form_validation_issues': 0, 'relation_count_mismatches': 0}.

Crawl accounting: {'selected': 50, 'successfully_crawled_sample': 50, 'central': 25, 'local': 25, 'candidate_attempts': 181, 'successful_captures_including_scope_mismatches': 157, 'replaced_due_to_crawl_source_failure': 24, 'replaced_due_to_scope_hint_mismatch': 107}. RAW failures and scope mismatches were recorded and replaced; immutable extra captures remain outside the fixed sample.

Actual source document types: {'Thông tư': 6, 'Quyết định': 6, 'Bản dịch văn bản': 7, 'Nghị quyết': 7, 'Chỉ thị': 9, 'Văn bản hành chính liên quan': 1, 'Luật': 4, 'Văn bản hợp nhất': 6, 'Văn bản liên quan': 2, 'Pháp lệnh': 1, 'Nghị định': 1}.

Repaired 36 generic parser defects (35 exposed by sampled source patterns and 1 during regression expansion); schema gaps and RAW capture code defects: 0. No schema bump, manual generated-JSON edits, or weakened validator assertions.

## Final document inventory

| # / wave | Document ID and source URL | Scope | Source type / number | Crawl | Extract | W/E/F |
|---|---|---|---|---|---|---|
| 1 / 1 | [vbpl:152955](https://vbpl.vn/van-ban/chi-tiet/thong-tu-so-23-2021-tt-byt-sua-doi-bo-sung-mot-so-van-ban-quy-pham-phap-luat-do-bo-truong-bo-y-te-ban-hanh--152955) | Central | Thông tư / 23/2021/TT-BYT | complete | success | 0/0/0 |
| 2 / 1 | [vbpl:116962](https://vbpl.vn/van-ban/chi-tiet/quyet-dinh-so-26-2016-qd-ubnd-ban-hanh-quy-che-lam-viec-cua-uy-ban-nhan-dan-tinh-lai-chau-nhiem-ky-2016-2021--116962) | Local | Quyết định / 26/2016/QĐ-UBND | complete | success | 0/0/0 |
| 3 / 1 | [vbpl:00027f33df7ab52e31a577d0d52a099c](https://vbpl.vn/van-ban/chi-tiet/directive-08-2006-ct-ttg--vbpqta_5877) | Central | Bản dịch văn bản / 08/2006/CT-TTg | complete | success | 0/0/0 |
| 4 / 1 | [vbpl:159581](https://vbpl.vn/van-ban/chi-tiet/nghi-quyet-so-31-2021-nq-hdnd-ban-hanh-quy-dinh-ve-che-do-chinh-sach-va-cac-dieu-kien-bao-dam-hoat-dong-cua-dai-bieu-hoi-dong-nhan-dan-cac-cap-tai-thanh-pho-ho-chi-minh-nhiem-ky-2021-2026--159581) | Local | Nghị quyết / 31/2021/NQ-HĐND | complete | success | 0/0/0 |
| 5 / 1 | [vbpl:32026](https://vbpl.vn/van-ban/chi-tiet/quyet-dinh-so-295-qd-bxd-ve-viec-cong-bo-tap-suat-von-dau-tu-xay-dung-cong-trinh-nam-2010--32026) | Central | Quyết định / 295/QĐ-BXD | complete | success | 0/0/0 |
| 6 / 1 | [vbpl:54406](https://vbpl.vn/van-ban/chi-tiet/chi-thi-so-20-2007-ct-ubnd-ve-viec-tang-cuong-cong-tac-quan-ly-chat-thai-ran-tren-dia-ban-tinh-binh-duong--54406) | Local | Chỉ thị / 20/2007/CT-UBND | complete | success | 0/0/0 |
| 7 / 1 | [vbpl:0019dd16cfe06add842b1031300f9fe3](https://vbpl.vn/van-ban/chi-tiet/nghi-dinh-57-1999-nd-cp--vbpqta_895) | Central | Bản dịch văn bản / 57/1999/NĐ-CP | complete | success | 0/0/0 |
| 8 / 1 | [vbpl:0a37926080b6ffa67a58ba410db7939b](https://vbpl.vn/van-ban/chi-tiet/408-ubnd-tn--vbpqdinhchinh_105) | Local | Văn bản hành chính liên quan / 408/UBND-TN | complete | success | 0/0/0 |
| 9 / 1 | [vbpl:8760](https://vbpl.vn/van-ban/chi-tiet/chi-thi-so-39-ttg-ve-viec-bao-dam-an-toan-cho-nguoi-va-phuong-tien-nghe-ca-hoat-dong-tren-bien--8760) | Central | Chỉ thị / 39/TTg | complete | success | 0/0/0 |
| 10 / 1 | [vbpl:3322](https://vbpl.vn/van-ban/chi-tiet/thong-tu-so-165-hdbt-huong-dan-cuoc-bau-cu-dai-bieu-hdnd-va-ubnd-tinh-thanh-pho-va-dac-khu-truc-thuoc-trung-uong-nhiem-ky-1985-1989--3322) | Local | Thông tư / 165-HĐBT | complete | success | 0/0/0 |
| 11 / 2 | [vbpl:1005](https://vbpl.vn/van-ban/chi-tiet/luat-cong-doan-1957-so-108-sl-l10--1005) | Central | Luật / 108-SL/L10 | complete | success_with_warnings | 2/0/0 |
| 12 / 2 | [vbpl:b3abef60-bb0b-11f1-b268-c159cf8a37b0](https://vbpl.vn/van-ban/chi-tiet/van-ban-hop-nhat-so-4308-vbhn-qd-ubnd-ve-viec-ban-hanh-he-so-dieu-chinh-gia-dat-nam-2026-tren-dia-ban-tinh-lam-dong--b3abef60-bb0b-11f1-b268-c159cf8a37b0) | Local | Văn bản hợp nhất / 4308/VBHN-QĐ-UBND | complete | success | 0/0/0 |
| 13 / 2 | [vbpl:107957](https://vbpl.vn/van-ban/chi-tiet/quyet-dinh-so-1988-qd-btc-quy-dinh-chuc-nang-nhiem-vu-quyen-han-va-co-cau-to-chuc-cua-vu-to-chuc-can-bo--107957) | Central | Quyết định / 1988/QĐ - BTC | complete | success | 0/0/0 |
| 14 / 2 | [vbpl:86463](https://vbpl.vn/van-ban/chi-tiet/nghi-quyet-so-03-1999-nq-hdnd-ve-viec-xac-nhan-ket-qua-bau-cu-thanh-vien-uy-ban-nhan-dan-tinh-son-la-khoa-xi-nhiem-ky-1999-2004--86463) | Local | Nghị quyết / 03/1999/NQ-HĐND | complete | success_with_warnings | 2/0/0 |
| 15 / 2 | [vbpl:78081](https://vbpl.vn/van-ban/chi-tiet/thong-tu-so-07-tc-gttl-huong-dan-them-mot-so-diem-ve-nhuong-ban-tai-san-co-dinh-qui-dinh-trong-thong-tu-260-ttg-ngay-20-6-1977-cua-thu-tuong-chinh-phu--78081) | Central | Thông tư / 07-TC/GTTL | complete | success | 0/0/0 |
| 16 / 2 | [vbpl:53597](https://vbpl.vn/van-ban/chi-tiet/chi-thi-so-14-2011-ct-ubnd-ve-tang-cuong-cong-tac-tham-muu-de-xuat-xu-ly-cong-viec-trong-cong-tac-quan-ly-chi-dao-dieu-hanh-thuc-hien-nhiem-vu-phat-trien-kinh-te-xa-hoi-quoc-phong-an-ninh-xay-dung-he-thong-chinh-quyen-tren-dia-ban-tinh-hau-giang--53597) | Local | Chỉ thị / 14/2011/CT-UBND | complete | success | 0/0/0 |
| 17 / 2 | [vbpl:16151b5ba377472bb544046dad620ea1](https://vbpl.vn/van-ban/chi-tiet/decision-1944-2003-qd-bgtvt--vbpqta_8619) | Central | Bản dịch văn bản / 1944/2003/QD-BGTVT | complete | success | 0/0/0 |
| 18 / 2 | [vbpl:6e60a930-bb12-11f1-8bac-5301206c636f](https://vbpl.vn/van-ban/chi-tiet/van-ban-hop-nhat-so-4096-vbhn-qd-ubnd-ve-boi-thuong-ho-tro-tai-dinh-cu-khi-nha-nuoc-thu-hoi-dat-tren-dia-ban-tinh-lam-dong--6e60a930-bb12-11f1-8bac-5301206c636f) | Local | Văn bản hợp nhất / 4096/VBHN-QĐ-UBND | complete | success | 0/0/0 |
| 19 / 2 | [vbpl:0b2087e0-83fa-11f1-8c48-c5a5aa8ebc17](https://vbpl.vn/van-ban/chi-tiet/van-ban-hop-nhat-so-31-vbhn-bct-thong-tu-quy-dinh-ve-phuong-phap-xac-dinh-va-nguyen-tac-ap-dung-bieu-gia-chi-phi-tranh-duoc-cho-cac-nha-may-dien-nang-luong-tai-tao-nho-noi-dung-chinh-cua-hop-dong-mua-ban-dien--0b2087e0-83fa-11f1-8c48-c5a5aa8ebc17) | Central | Văn bản hợp nhất / 31/VBHN-BCT | complete | success_with_warnings | 3/0/0 |
| 20 / 2 | [vbpl:119747](https://vbpl.vn/van-ban/chi-tiet/quyet-dinh-so-2073-2004-qd-ubnd-ve-viec-quy-dinh-cam-mot-so-phuong-tien-xe-co-goi-di-vao-cac-tuyen-duong-chinh-tren-dia-ban-thanh-pho-thai-nguyen-va-bo-sung-bien-phap-tam-giu-phuong-tien-vi-pham-luat-giao-thong-duong-bo-tren-dia-ban-tinh-thai-nguyen--119747) | Local | Quyết định / 2073/2004/QĐ-UBND. | complete | success | 0/0/0 |
| 21 / 3 | [vbpl:2067](https://vbpl.vn/van-ban/chi-tiet/luat-sua-doi-bo-sung-mot-so-dieu-cua-luat-dau-tu-nuoc-ngoai-tai-viet-nam-so-41-lct-hdnn8--2067) | Central | Luật / 41-LCT/HĐNN8 | complete | success_with_warnings | 8/0/0 |
| 22 / 3 | [vbpl:68094](https://vbpl.vn/van-ban/chi-tiet/nghi-quyet-so-24-11-1979-a-ve-viec-ban-hanh-dieu-le-tam-thoi-ve-hoat-dong-cua-hdnd-va-dai-bieu-hdnd-cac-cap-trong-thanh-pho--68094) | Local | Nghị quyết / 24/11/1979-A | complete | success | 0/0/0 |
| 23 / 3 | [vbpl:3e34bb0aa4d294fc82c53d03d4d543d3](https://vbpl.vn/van-ban/chi-tiet/directive-726-ttg--vbpqta_1930) | Central | Bản dịch văn bản / 726/TTg | complete | success | 0/0/0 |
| 24 / 3 | [vbpl:95214](https://vbpl.vn/van-ban/chi-tiet/chi-thi-so-01-2007-ct-ubnd-ve-viec-tang-cuong-cong-tac-chi-dao-thu-thue-nam-2007--95214) | Local | Chỉ thị / 01/2007/CT-UBND | complete | success | 0/0/0 |
| 25 / 3 | [vbpl:26741](https://vbpl.vn/van-ban/chi-tiet/luat-phong-chong-mua-ban-nguoi-so-66-2011-qh12--26741) | Central | Luật / 66/2011/QH12 | complete | success_with_warnings | 3/0/0 |
| 26 / 3 | [vbpl:8685](https://vbpl.vn/van-ban/chi-tiet/thong-tu-so-34-tt-ub-trien-khai-thuc-hien-chi-thi-09-ct-tw-cua-bo-chinh-tri-qd-56-ttg-qd-57-ttg-cua-thu-tuong-chinh-phu-ve-viec-ky-niem-50-ngay-thuong-binh-liet-si-27-7-1947-27-7-1997--8685) | Local | Thông tư / 34/TT-UB | complete | success | 0/0/0 |
| 27 / 3 | [vbpl:10423](https://vbpl.vn/van-ban/chi-tiet/luat-sua-doi-mot-so-dieu-cua-luat-doanh-nghiep-tu-nhan-so-khong-so--10423) | Central | Luật / Không số | complete | success_with_warnings | 5/0/0 |
| 28 / 3 | [vbpl:bb8b7c30-9f65-11f1-ab9a-39774c38cd0e](https://vbpl.vn/van-ban/chi-tiet/van-ban-hop-nhat-so-88-2026-vbhn-qd-ubnd-ban-hanh-quy-che-phoi-hop-giua-cac-co-quan-quan-ly-nha-nuoc-trong-cong-tac-quan-ly-nha-nuoc-doi-voi-doanh-nghiep-va-ho-kinh-doanh-sau-dang-ky-thanh-lap-tren-dia-ban-tinh-vinh-long--bb8b7c30-9f65-11f1-ab9a-39774c38cd0e) | Local | Văn bản hợp nhất / 88/2026/VBHN-QĐ-UBND | complete | success | 0/0/0 |
| 29 / 3 | [vbpl:d4ba5790-8010-11f1-93ea-dd502af5ba0e](https://vbpl.vn/van-ban/chi-tiet/van-ban-hop-nhat-so-68-2026-vbhn-nd-bct-nghi-dinh-quy-dinh-ve-co-che-thoi-gian-dieu-chinh-gia-ban-le-dien-binh-quan--d4ba5790-8010-11f1-93ea-dd502af5ba0e) | Central | Văn bản hợp nhất / 68/2026/VBHN-NĐ-BCT | complete | success_with_warnings | 2/0/0 |
| 30 / 3 | [vbpl:49202](https://vbpl.vn/van-ban/chi-tiet/quyet-dinh-so-1966-2011-qd-ubnd-ve-viec-ban-hanh-quy-dinh-ve-danh-so-va-gan-bien-so-nha-tren-dia-ban-tinh-phu-yen--49202) | Local | Quyết định / 1966/2011/QĐ-UBND | complete | success | 0/0/0 |
| 31 / 4 | [vbpl:0781f27b881b5bf75a3c3b265534be25](https://vbpl.vn/van-ban/chi-tiet/luat-13-1999-qh10--vbpqta_929) | Central | Bản dịch văn bản / 13/1999/QH10 | complete | success | 0/0/0 |
| 32 / 4 | [vbpl:1507](https://vbpl.vn/van-ban/chi-tiet/thong-tu-so-3-cb-ub-huong-dan-thi-hanh-quyet-dinh-so-304-cp-ngay-29-8-1979-ve-to-chuc-bo-may-bien-che-cua-nha-tre-thuoc-khu-vuc-nha-nuoc--1507) | Local | Thông tư / 3/CB-UB | complete | success | 0/0/0 |
| 33 / 4 | [vbpl:54805](https://vbpl.vn/van-ban/chi-tiet/chi-thi-so-1973-ct-ttg-ve-viec-tiep-tuc-day-manh-viec-hoc-tap-va-lam-theo-tam-guong-dao-duc-ho-chi-minh--54805) | Central | Chỉ thị / 1973/CT-TTg | complete | success | 0/0/0 |
| 34 / 4 | [vbpl:29189](https://vbpl.vn/van-ban/chi-tiet/van-ban-lien-quan-09-2006-qd-ubnd--29189) | Local | Văn bản liên quan / 09/2006/QĐ-UBND | complete | success | 0/0/0 |
| 35 / 4 | [vbpl:182596](https://vbpl.vn/van-ban/chi-tiet/phap-lenh-so-05-2024-ubtvqh15-chi-phi-to-tung--182596) | Central | Pháp lệnh / 05/2024/UBTVQH15 | complete | success | 0/0/0 |
| 36 / 4 | [vbpl:103901](https://vbpl.vn/van-ban/chi-tiet/chi-thi-so-08-ub-ct-v-v-tang-cuong-cong-tac-phong-chay-chua-chay-va-chuan-bi-tong-ket-30-nam-thi-hanh-phap-lenh-phong-chay-chua-chay-04-10-1961-04-10-1991--103901) | Local | Chỉ thị / 08/UB-CT | complete | success | 0/0/0 |
| 37 / 4 | [vbpl:832](https://vbpl.vn/van-ban/chi-tiet/nghi-dinh-so-12-ld-nd-bo-khuyet-bang-tieu-chuan-nghe-nghiep-kem-theo-sac-lenh-so-77-sl-ngay-22-thang-5-nam-1950--832) | Central | Nghị định / 12/LĐ-NĐ | complete | success | 0/0/0 |
| 38 / 4 | [vbpl:112825](https://vbpl.vn/van-ban/chi-tiet/nghi-quyet-so-16-2016-nq-hdnd-quy-dinh-cac-khoan-dong-gop-va-che-do-mien-giam-doi-voi-nguoi-tu-nguyen-chua-tri-cai-nghien-ma-tuy-tai-co-so-dieu-tri-nghien-nguoi-cai-nghien-ma-tuy-bat-buoc-tu-nguyen-tai-cong-dong-tren-dia-ban-tinh-bac-giang--112825) | Local | Nghị quyết / 16/2016/NQ-HĐND | complete | success | 0/0/0 |
| 39 / 4 | [vbpl:e7f747c5f1112006a13c6812c061841d](https://vbpl.vn/van-ban/chi-tiet/luat-02-1997-qh10--vbpqta_1788) | Central | Bản dịch văn bản / 02/1997/QH10 | complete | success_with_warnings | 2/0/0 |
| 40 / 4 | [vbpl:599bc3d0-9f70-11f1-804c-871db2d0ec68](https://vbpl.vn/van-ban/chi-tiet/van-ban-hop-nhat-so-02-2026-vbhn-qd-ubnd-ve-day-them-hoc-them-tren-dia-ban-tinh-quang-tri--599bc3d0-9f70-11f1-804c-871db2d0ec68) | Local | Văn bản hợp nhất / 02/2026/VBHN-QĐ-UBND | complete | success | 0/0/0 |
| 41 / 5 | [vbpl:8050](https://vbpl.vn/van-ban/chi-tiet/nghi-quyet-so-05-nq-1997-qh10-ve-tieu-chuan-cac-cong-trinh-quan-trong-quoc-gia-trinh-quoc-hoi-xem-xet-quyet-dinh-chu-truong-dau-tu--8050) | Central | Nghị quyết / 05/NQ-1997-QH10 | complete | success | 0/0/0 |
| 42 / 5 | [vbpl:50591](https://vbpl.vn/van-ban/chi-tiet/quyet-dinh-so-1902-2009-qd-ubnd-quy-dinh-mot-so-co-che-giai-phap-dieu-hanh-va-ke-hoach-trien-khai-doi-voi-cac-du-an-cap-bach-quan-trong-tren-dia-ban-tinh-phu-yen--50591) | Local | Quyết định / 1902/2009/QĐ-UBND | complete | success | 0/0/0 |
| 43 / 5 | [vbpl:24647](https://vbpl.vn/van-ban/chi-tiet/chi-thi-so-1940-ct-ttg-ve-nha-dat-lien-quan-den-ton-giao--24647) | Central | Chỉ thị / 1940/CT-TTg | complete | success | 0/0/0 |
| 44 / 5 | [vbpl:10129](https://vbpl.vn/van-ban/chi-tiet/thong-tu-so-333-ub-ltx-huong-dan-thi-hanh-quy-che-dau-tu-theo-hinh-thuc-hop-dong-xay-dung-kinh-doanh-chuyen-giao-bot--10129) | Local | Thông tư / 333/UB-LTX | complete | success | 0/0/0 |
| 45 / 5 | [vbpl:01308b41e5d32d9b48780b7631d358ce](https://vbpl.vn/van-ban/chi-tiet/luat-20-2012-qh13--vbpqta_11015) | Central | Bản dịch văn bản / 20/2012/QH13 | complete | success_with_warnings | 1/0/0 |
| 46 / 5 | [vbpl:28964](https://vbpl.vn/van-ban/chi-tiet/van-ban-lien-quan-13-2006-qd-ubnd--28964) | Local | Văn bản liên quan / 13/2006/QĐ-UBND | complete | success | 0/0/0 |
| 47 / 5 | [vbpl:3919](https://vbpl.vn/van-ban/chi-tiet/chi-thi-so-21-ttg-ve-viec-nang-bac-luong-nam-1981-cho-cong-nhan-can-bo-nhan-vien-nha-nuoc--3919) | Central | Chỉ thị / 21-TTg | complete | success | 0/0/0 |
| 48 / 5 | [vbpl:118286](https://vbpl.vn/van-ban/chi-tiet/nghi-quyet-so-21-2016-nq-hdnd-ve-viec-thong-qua-dinh-muc-phan-bo-du-toan-chi-thuong-xuyen-ngan-sach-tinh-hau-giang-giai-doan-2017-2020--118286) | Local | Nghị quyết / 21/2016/NQ-HĐND | complete | success | 0/0/0 |
| 49 / 5 | [vbpl:7130](https://vbpl.vn/van-ban/chi-tiet/nghi-quyet-so-07-1999-nq-cp-phien-hop-chinh-phu-thuong-ky-thang-6-nam-1999--7130) | Central | Nghị quyết / 07/1999/NQ-CP | complete | success | 0/0/0 |
| 50 / 5 | [vbpl:105730](https://vbpl.vn/van-ban/chi-tiet/chi-thi-so-22-ct-ub-ve-viec-tang-cuong-quan-ly-chi-dao-to-chuc-thuc-hien-chuong-trinh-135--105730) | Local | Chỉ thị / 22/CT-UB | complete | success | 0/0/0 |

## Source ambiguities retained

These warnings are source-backed exceptions, not repaired parser defects. Generated semantic_complete flags remain false where required. Exact source anchors and excerpts are in the JSON companion.

- vbpl:1005: {'unresolved_document_reference': 2}. Reviewed direct article-local alphabetic lists and source relations with no numbered identifier/link.
- vbpl:86463: {'table_semantics_unresolved': 1, 'unresolved_document_reference': 1}. Reviewed headerless person/position table; neither header axis nor missing law identifier can be safely inferred.
- vbpl:0b2087e0-83fa-11f1-8c48-c5a5aa8ebc17: {'non_text_content': 2, 'possible_page_number': 1}. Reviewed contract form, contents, lettered appendices and merged header bands. Annex II a through i now form one continuous sequence with dash lists nested under f and h. Formula media and bare 11 remain warned.
- vbpl:2067: {'unresolved_document_reference': 8}. Reviewed ten actual hyphen clauses, preamble and unresolved source relations; corrected the previous zero-clause pinned expectation from RAW evidence.
- vbpl:26741: {'unresolved_document_reference': 3}. Reviewed 58 articles, chapter/section hierarchy and Constitution references lacking identifiers/links.
- vbpl:10423: {'unresolved_document_reference': 5}. Leading Điều ... được sửa đổi phrases are prose amendment lead-ins; quoted content stays local. Missing relation identifiers remain unresolved.
- vbpl:d4ba5790-8010-11f1-93ea-dd502af5ba0e: {'non_text_content': 1, 'possible_page_number': 1}. Reviewed consolidated hierarchy; encoded formula media and isolated bare 11 remain source-faithful warnings.
- vbpl:e7f747c5f1112006a13c6812c061841d: {'duplicate_legal_number': 2}. Inspected translation with 131 articles and numeric/slash counters. RAW repeats Article 38 at orders 615/633 and clause 2 at 1938/1941; no renumbering is permitted.
- vbpl:01308b41e5d32d9b48780b7631d358ce: {'incomplete_source_quotation': 1}. Reviewed 37 outer amendments plus two implementation clauses. RAW omits the closing quote before amendment 32; quoted counters are local and an incomplete_source_quotation diagnostic remains.

## Generic parser repairs

- **ui_artifacts** (vbpl:152955, vbpl:1005): Browser title metadata, amendment controls and empty-state graphics were parsed as legal text/media. Audit and exclude only source-backed interface artifacts; retain ordinary buttons and source media.
- **replacement_quotation_scope** (vbpl:152955, vbpl:0a37926080b6ffa67a58ba410db7939b): Replacement counters inside multiline quotations leaked into the enclosing legal hierarchy. Balance explicit source quotation boundaries and represent their independent counters as local lists.
- **sparse_body_boundary** (vbpl:00027f33df7ab52e31a577d0d52a099c, vbpl:54406, vbpl:0a37926080b6ffa67a58ba410db7939b): Article-free directives and correction letters remained in header/title sections. Use source heading, alignment and substantive narrative boundaries to enter the body.
- **header_authority** (vbpl:116962, vbpl:8760): An authority displayed in a letterhead table could trigger the closing signature phase. Preserve issuing-authority role in the initial header context.
- **article_free_alpha** (vbpl:3322): Alphabetic counters in an article-free body became orphan legal points. Retain source-backed numbered paragraphs without inventing articles or clauses.
- **counter_restart** (vbpl:159581): A bounded counter restart below a colon lead-in duplicated legal clause numbers. Keep the complete restarted sequence in its own evidenced enumeration scope.
- **signature_table_scope** (vbpl:116962, vbpl:8760, vbpl:95214): Small signature tables without axis headers were ambiguous or prematurely ended an attached legal act. Recognize explicit signing markers/delegation and keep local semantic signature blocks.
- **addressee_scope** (vbpl:0a37926080b6ffa67a58ba410db7939b, vbpl:78081): Legacy Kính gửi blocks and dash recipients were left as generic paragraphs. Recognize the source addressee heading and preserve recipient/list context.
- **legacy_reference_numbers** (vbpl:8760, vbpl:2067): Hyphenated, suffix-letter and multiple-slash document numbers were omitted from relations/history. Expand source-slice recognition while keeping primary citations and mentions separate.
- **article_local_alpha** (vbpl:1005): Alphabetic sequences directly below an article colon lead-in became orphan points. Represent consecutive local lists without synthesizing an absent legal clause.
- **roman_decimal_outline** (vbpl:119747): Roman subdivisions and decimal items within an article were confused with clauses and orphan points. Scope explicitly emphasized Roman outlines and their nested counters as local ordered lists.
- **article_footnote_marker** (vbpl:6e60a930-bb12-11f1-8bac-5301206c636f): A footnote immediately after an article number prevented article recognition. Allow source footnote notation at the label boundary and preserve its text/annotation.
- **td_header_markup** (vbpl:b3abef60-bb0b-11f1-b268-c159cf8a37b0, vbpl:0b2087e0-83fa-11f1-8c48-c5a5aa8ebc17): Bold or shaded td header bands lacked column associations. Recognize explicit typography and reusable column labels; preserve physical cells, spans and conservative ambiguous axes.
- **layout_colgroup** (vbpl:107957, vbpl:86463, vbpl:78081): Non-text colgroup/col layout declarations emitted unknown-element warnings. Keep these declarations as table geometry metadata instead of legal-content units.
- **symbol_definition_table** (vbpl:0b2087e0-83fa-11f1-8c48-c5a5aa8ebc17): Repeated symbol/separator/definition rows were treated as ambiguous axis tables. Keep their full physical geometry as key/value definition tables with no irrelevant role/confidence metadata.
- **blank_letterhead_rows** (vbpl:0b2087e0-83fa-11f1-8c48-c5a5aa8ebc17): A national heading/motto table with blank rows was mistaken for a data table. Use meaningful rows and exact letterhead roles, retaining layout provenance.
- **interleaved_closing_columns** (vbpl:107957): Signing columns interrupted recipient groups; regrouping across rows could cross source order. Keep explicit recipient continuation groups in source order and preserve individual layout-cell boundaries.
- **annex_alpha_continuations** (vbpl:0b2087e0-83fa-11f1-8c48-c5a5aa8ebc17): Alphabetic annex lists separated by formulas or explanatory paragraphs remained generic. Build bounded consecutive annex lists with source-backed continuation blocks.
- **css_heading_emphasis** (vbpl:0b2087e0-83fa-11f1-8c48-c5a5aa8ebc17): Whole-unit CSS font-weight evidence was ignored. Recognize bold CSS as the same source heading evidence as bold/strong tags.
- **contract_template_scope** (vbpl:0b2087e0-83fa-11f1-8c48-c5a5aa8ebc17): Contents entries became annex boundaries, and contract article/lettered appendix headings remained generic. Scope explicit contents as source lists; recognize the contract form and retain local article/appendix headings and counters.
- **directive_decimal_prefix** (vbpl:95214): Decimal subdivisions in an article-free directive remained generic and lost their source prefix parent. Attach explicitly punctuated decimal counters to their actual existing prefix; diagnose missing prefixes rather than inventing parents.
- **attached_legal_act_boundary** (vbpl:bb8b7c30-9f65-11f1-ab9a-39774c38cd0e): A signature and second letterhead locked an attached act into the closing phase. Preserve intermediate closing/header roles as local layout blocks and restart legal counters in the canonical body.
- **unconsumed_split_heading** (vbpl:bb8b7c30-9f65-11f1-ab9a-39774c38cd0e): Speculative heading coalescence could discard the title of a generic footer unit. Restore the source title child whenever no legal node consumed the coalesced title.
- **footnote_provision_excerpt** (vbpl:bb8b7c30-9f65-11f1-ab9a-39774c38cd0e): An amended provision inside a source footer retained a clause marker as a generic paragraph. Represent explicit article/clause excerpts as local counter lists inside their actual footnote.
- **english_legal_labels** (vbpl:0781f27b881b5bf75a3c3b265534be25): English Article/Chapter/Section headings remained generic despite valid JSON. Recognize source English legal labels and document headings, preserve separator punctuation, reject leading prose citations.
- **legacy_counter_separators** (vbpl:2067, vbpl:0781f27b881b5bf75a3c3b265534be25, vbpl:e7f747c5f1112006a13c6812c061841d): Hyphen clause counters and slash point counters were left as generic paragraphs. Recognize spaced hyphen/slash numeric counters and slash alphabetic counters in legal and local list scopes; retain numeric ranges, fractions and inline ratios as ordinary text.
- **preamble_boundary_before_sparse_body** (vbpl:2067, vbpl:68094, vbpl:0781f27b881b5bf75a3c3b265534be25): Unlabelled motivation paragraphs entered the body before an explicit source basis; a bare enacting formula could become a title. Use the explicit following basis/formula before the first legal heading to preserve preamble scope; recognize unambiguous bare enacting formula labels.
- **roman_article_free_outline** (vbpl:1507): Only the first Roman heading in an article-free circular was recognized; later emphasized siblings stayed generic. Represent repeated emphasized Roman headings and their subordinate numeric/alpha counters as a local body outline, bounded by source legal/annex/closing labels.
- **incomplete_amendment_quotation** (vbpl:01308b41e5d32d9b48780b7631d358ce): A source quotation missing its closing mark let replacement clauses leak into the outer act. Bound its local counters at the next explicit sequential amendment lead-in; preserve every character and emit a source-incomplete-quotation warning.
- **point_evidence_across_child_tables** (vbpl:118286): Clause inference stopped at a child table, missing explicit later sibling point b and leaving four orphan points. Collect outer sibling point evidence across opaque child tables/lists; keep numeric-only sequence barriers and procedural-list contradictions unchanged.
- **qualified_column_labels** (vbpl:118286): A source td header with a parenthetical measurement unit was not recognized as a single named column label. Match reusable source column-label vocabulary plus its explicit unit qualifier and preserve the complete original header text.
- **spanned_formula_table** (vbpl:118286): An assignment formula rendered with rowspan and a two-row expression was treated as an unresolved data table. Use existing key/value table representation for an explicit single assignment spanning all source rows; retain all eight physical cells and grid geometry without invented axes.
- **annex_nested_list_continuation** (vbpl:0b2087e0-83fa-11f1-8c48-c5a5aa8ebc17): An annex alphabetic sequence stopped at a nested dash list, leaving its final consecutive item generic. Retain nested lists as opaque continuation children until the next source-backed alphabetic sibling or stronger boundary.
- **source_alpha_outline_heading** (vbpl:1507): Plain A/B subdivisions carried explicit VBPL provision-heading classes but no bold markup, leaving them generic. Use the source provision-heading class on uppercase headings and represent alphabetic subdivisions between Roman and numeric local-outline levels.
- **slash_signature_delegation** (vbpl:105730): A source KT/ delegation title stayed generic inside an otherwise recognized signing block. Recognize slash-delimited delegation abbreviations only when followed by an explicit authority; preserve the exact source spelling.
- **bare_annex_coalescence_boundary** (portable regression): A bare annex label after a bare article label could be consumed as the article title during speculative coalescence. Treat an actual annex candidate as a boundary in heading coalescence. Portable nested-annex-list regression exposed the boundary omission; no sampled capture required RAW changes.

## Regression and verification

248 unit tests passed. Added 38 portable parser-pattern tests, 3 sampler tests, and one capture-corpus test covering 25 promoted real documents. Existing assertions remain active; the ten-clause expectation correction for vbpl:2067 is backed by explicit RAW 1- through 10- markers.

Fixtures: `tests/fixtures/vbpl_batch_regressions.json`. Tests: `tests/unit/test_batch_source_patterns.py`, `test_batch_capture_regressions.py`, `test_validation_sampler.py`. The existing representative suite now pins its original five captures explicitly so corpus growth cannot change its membership.

Golden: all quality flags true, warnings/errors/fatals zero; 4 chapters, 15 articles, 36 clauses, 5 points; 4 annexes, 5 numbered sections, 26 numbered items; 16 forms, 80 fields, 14 subfields, 52 footnotes. Orphans, ambiguous tables and unresolved numbered candidates remain zero.

Offline revalidation: `.venv/bin/python scripts/run_extract_validation_50.py audit --regenerate`. Its nonzero exit status deliberately reflects retained source warnings; it does not hide them behind a green batch status.

Machine report: `reports/extract-validation-50.json`. Resumable evidence: state, repairs and reviews JSON files in `reports/`.

## Remaining limitations

- Manifest semantic_complete stays false for source warnings. The report never overrides generated flags to claim 50/50 semantic completeness.
- Missing relation numbers/links are retained as unresolved; no external lookup or invented link is used.
- Formula images remain media with original source URLs/data URLs; no OCR or invented mathematical expression is supplied.
- Isolated bare source numbers without page-transition evidence remain visible and warned.
- Headerless table axes and actual duplicated legal numbers retain their source ambiguity and diagnostics.
- A quotation missing its closing mark stays local to the next explicit amendment boundary and retains an incomplete_source_quotation warning; no missing punctuation is inserted.
- Central/Local follows the existing crawler’s VBPL breadcrumb contract. Some legacy national issuers appear in the Local source category; issuing-authority source values are reported separately.
- The existing crawler explicitly excludes Tải về and Văn bản gốc and captures rendered HTML tabs only. Attachments were not downloaded or validated; excluded tab metadata is preserved.
- Some English VBPL pages are summaries and some contain source encoding artifacts. Validation covers the actual captured HTML, not missing full text or attachment content.
- Real capture regressions reference immutable local RAW rather than copying large HTML into Git. Portable synthetic regressions run without those local captures.
