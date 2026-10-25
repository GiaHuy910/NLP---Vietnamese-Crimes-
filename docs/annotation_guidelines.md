# Annotation Guidelines

These guidelines apply to the 150-sentence gold test set. Annotate one sentence at a time and use
only information present in that sentence.

## A. Entities (8 labels)

| Label | Annotate | Do not annotate |
|---|---|---|
| `PERSON` | Proper names and abbreviated names (`T`, `L.T. V`, `Nguyễn Hùng M`) | Titles/ranks (`Thiếu tá`, `BS`, `nguyên Tổng giám đốc`); generic references (`bị cáo`, `nạn nhân`, `đối tượng`); nicknames (`đại ca`) |
| `ORGANIZATION` | Named institutions, including a location that is part of the name (`Công an huyện Kim Bình`, `TAND tỉnh Gia Lai`, `Bộ Công an`, `Quốc hội`, `phòng Cảnh sát hình sự`) | Generic terms alone (`công an`, `cảnh sát`, `cơ quan điều tra`, `HĐXX`, `Ban chuyên án`, `ngân hàng`); generic organization types (`công ty đại chúng`) |
| `LOCATION` | Place names, retaining an administrative prefix (`tỉnh Vân Nam`, `TP. Thủ Dầu Một`); named structures (`Trạm biến áp 110 Hưng Nguyên`, `cụm cảng Cái Mép`, `toà nhà Golden Palm`). Split comma-separated addresses into separate spans. | Broad regions (`Bắc`, `Nam`); nationalities (`người Lào`); `TP` by itself |
| `TIME` | Specific times, including parts of day (`rạng sáng 17/10`, `chiều ngày 12/6`, `mùng 2 Tết`); **prison terms/sentences** (`3 năm tù`, `tử hình`, `11 năm tù giam`) | Relative time (`khoảng một tuần sau`, `cách đây 15 năm`, `mới được 3 tháng`); birth years (`SN 1965`); document numbers (`kết luận số 10/2017`) |
| `MONEY` | Amounts with currency units (`1,3 tỉ đồng`, `200.000 đ`) | Percentages and shares (`18% cổ phần`); counting units such as `/lá` |
| `DRUG` | Every mention of a drug, including quantity (`4 gói heroin`, `1,5kg ma túy`, `ma túy đá`) | `ma túy` inside an organization name (`Cục Phòng, chống ma túy…`) |
| `PRODUCT` | Objects related to the case: evidence, stolen property, weapons (`1 khẩu súng`, `dao`, `xe tay ga hiệu Ari Blade`) | Ordinary goods unrelated to an event (`thịt heo`); containers (`túi ni lông`, `ba lô`) |
| `CRIME` | Specific crime names after `tội` or quoted after `hành vi` (`Cướp tài sản`, `giết người`, `trộm cắp tài sản`). Do **not** include the word `tội`. | Purpose descriptions (`chuyển tiền trái phép`); legal fields (`phòng chống tham nhũng`); allegations (`vi phạm bản quyền`) |

General rules:

- Annotate every occurrence of an entity in the sentence.
- Exclude punctuation at span boundaries (sentence-final periods, parentheses, commas).
- Entities must not overlap. For a combined name such as `công an hai huyện Tĩnh Gia và Như Thanh`,
  annotate the entire phrase as one `ORGANIZATION`.

## B. Event triggers (8 types)

1. **Annotate only events that have happened or are happening.** Do not annotate intentions, plans,
   hypotheticals, negations, questions, or speculation: `nảy sinh ý định lừa đảo`, `quyết tâm truy bắt`,
   `để tiến hành khởi tố`, `nếu bắn chết`, `có thể đã chiếm đoạt`, `nằm trong kế hoạch… bắt giữ`,
   `liên quan… hay không`.
2. **Use the main verb as the trigger.** Do not include modifiers or outcomes: annotate `đâm`, not
   `đâm liên tiếp nhiều nhát` or `đâm chết`; annotate `tàng trữ`, not `tàng trữ chất ma túy`.
   Include the full phrase for compound verbs: `giết hại`, `bắt quả tang`, `bắt tạm giam`,
   `khống chế bắt giữ`, `lừa đảo chiếm đoạt`.
3. **For a repeated mention of the same event in one sentence, annotate one trigger**, choosing the
   clearest assertion (`phát hiện bị lừa đảo`, `khởi tố vụ án, khởi tố bị can` → only the first
   `khởi tố`). Annotate distinct actions separately (`xét xử` and `tuyên phạt`; `hành hung` and `bắn`).
4. Nouns referring to people are not triggers: in `Trộm đột nhập…`, the trigger is `đột nhập`.
5. **Fraud tactics without the word `lừa`:** annotate the main verb for the tactic as `LUA_DAO`
   (`giả giọng`, `tự xưng`, texting to request money, `đưa ra` false information).
6. **`BAO_LUC`** covers physical harm: killing, stabbing, slashing, beating, shooting, throwing a
   grenade, armed fighting, resisting with a weapon, rape, or `tước đoạt / tước đi` tính mạng.
7. **Not triggers:** investigation, verification, pursuit, arrest warrants, reporting, accusations,
   confessions, generic offending/violations, threats, arguments, checks, generic raids, administrative
   fines/citations, asset freezes, bribery, forged signatures, document forgery when not used for fraud,
   civil lawsuits, drug addiction/positive drug tests, animal slaughter, or fishing.
8. **Commonly confused forms:** `bắt` in `bắt cóc` is not `BAT_GIU`; annotate the full kidnapping phrase
   as `BAO_LUC` when it describes an actual event. Do not annotate `bắt` in `đánh bắt` or `bắt đầu`.
   Annotate `truy bắt thành công` as `BAT_GIU`, but not `truy bắt` alone.

## C. Relations (roles)

1. Relations always point from a trigger to an entity. A sentence without a trigger has no relation.
2. Link only annotated entities. Do not link unnamed people such as `bị cáo`, `hai anh em`, or `mẹ`.
3. Link each role to the nearest matching entity in the same clause. Do not link a repeated name from a
   different clause.
4. **`DIA_DIEM`** is where the event occurred. Do not link a place introduced as a hometown/residence
   (`quê`, `ngụ`, `trú`, `ở`), or as a destination/purpose (`để tiêu thụ tại Việt Nam`).
5. **`THOI_GIAN`** is the time when the event occurred, not the reporting date (`Ngày 16-11, … cho biết`).
6. **`CO_QUAN`** is the institution directly carrying out a legal-proceeding action, not the suspect's
   employer.
7. **`TANG_VAT`** is seized evidence or an object in a drug case. **`HUNG_KHI`** is a weapon used to
   commit the crime. **`TAI_SAN`** is stolen property; an advertised sale price does not count.
8. Link **`MUC_AN`** from an `XET_XU` trigger to a sentence (`TIME`/`MONEY`); link **`TOI_DANH`** to a
   `CRIME` entity.

## D. Quality checks

- After each export, run `check_annotations.py`, inspect `*_issues.csv`, and fix confirmed errors such
  as reversed relations, invalid role/entity types, or punctuation included in a span.
- Final test review: 17 of 150 sentences had warnings. Manual review confirmed one actual error, which
  was corrected.
