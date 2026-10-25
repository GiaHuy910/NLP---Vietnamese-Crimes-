# Luồng 2: Trigger, Argument, Relation

Thư mục này chứa bộ chấm, baseline luật và mô hình PhoBERT cho luồng 2, dùng schema 8 loại sự kiện và
10 vai trò (xem `docs/annotation_guidelines.md`). Bộ chấm và baseline chỉ dùng thư viện chuẩn của Python;
mô hình cần `torch`, `transformers`, `underthesea` (đã có trong `requirements-ner.txt`).

## File

- `schema.py`: 8 loại sự kiện, 10 vai trò và nhãn thực thể được phép cho từng vai trò.
- `data.py`: đọc/ghi `.jsonl`, kiểm tra offset và quan hệ, đổi câu thành danh sách sự kiện dạng span.
- `metrics.py`: các chỉ số đánh giá.
- `baseline.py`: baseline luật (từ khóa trigger + luật nối vai trò).
- `model.py`: mô hình PhoBERT (trigger BIO + phân loại vai trò cho từng cặp trigger–thực thể).
- `evaluate.py`: lệnh chạy đánh giá.

## Dữ liệu

Dùng 3 file gold `datasets/train.jsonl`, `val.jsonl`, `test.jsonl` (do `data_pipeline/step7_export_dataset.py`
tạo). File dự đoán của bất kỳ mô hình nào cũng phải cùng định dạng: mỗi dòng một câu, có `ann_id`,
`sentence`, `entities`, `triggers`, `relations`. Id của span không cần trùng với gold, vì việc chấm dựa
trên vị trí ký tự.

## Chỉ số

Tất cả là so khớp chính xác theo vị trí ký tự, micro-average, có Precision / Recall / F1.

| Chỉ số | Một dự đoán được tính đúng khi |
|---|---|
| Trigger Identification | đúng vị trí trigger |
| **Trigger F1** | đúng vị trí và đúng loại sự kiện |
| **Argument F1** | đúng trigger (vị trí + loại) và đúng vị trí thực thể được nối |
| **Relation F1** | như Argument F1 và đúng cả vai trò |
| **Event Exact Match** | trigger đúng và toàn bộ argument (vị trí + vai trò) khớp hoàn toàn với gold |

Báo cáo in thêm Trigger F1 theo từng loại sự kiện và Relation F1 theo từng vai trò.

## Chạy (trong thư mục `server/`)

```powershell
# Baseline luật trên test
python -m src.event_pipeline.evaluate --gold datasets/test.jsonl --baseline --errors 30

# Lưu dự đoán và kết quả
python -m src.event_pipeline.evaluate --gold datasets/test.jsonl --baseline `
  --save-pred datasets/processed/test_baseline_pred.jsonl `
  --save-json datasets/processed/test_baseline_eval.json

# Chấm file dự đoán của mô hình
python -m src.event_pipeline.evaluate --gold datasets/test.jsonl --pred datasets/processed/test_pred.jsonl

# Kiểm tra bộ chấm
python -m unittest discover -s test -p "test_event_metrics.py"
```

## Kết quả baseline luật

Thực thể lấy từ gold (đánh giá riêng luồng 2, không phụ thuộc lỗi của NER). Luật chỉ được chỉnh dựa
trên train và val; test chỉ chạy một lần để báo cáo.

| Tập | Trigger F1 | Argument F1 | Relation F1 | Event Exact Match |
|---|---|---|---|---|
| train (301 câu) | 0.877 | 0.711 | 0.696 | 0.332 |
| val (150 câu) | 0.756 | 0.621 | 0.594 | 0.347 |
| **test (150 câu)** | **0.697** | **0.629** | **0.589** | **0.275** |

Điểm giữa val và test gần nhau, cho thấy luật không bị khớp riêng vào tập test.

## Mô hình PhoBERT

1. **Trigger**: gán nhãn BIO trên từ (tách từ bằng underthesea) với 8 loại sự kiện. Nhãn O được giảm
   trọng số (`--o-weight 0.3`) vì chiếm đa số.
2. **Argument**: với mỗi cặp (trigger, thực thể) trong câu, chèn dấu `<t> </t>` quanh trigger,
   `<e> </e>` quanh thực thể và token loại sự kiện, loại thực thể ở đầu câu, rồi phân loại vào 10 vai
   trò hoặc NONE. Lúc dự đoán chỉ cho phép vai trò hợp lệ với nhãn thực thể (bảng ROLE_TYPES).
3. Chọn checkpoint theo F1 trên val: trigger theo Trigger F1, argument theo Relation F1 khi dùng trigger gold.
   Test không dùng trong lúc train.

```powershell
# Train cả 2 mô hình (nên chạy trên GPU, ví dụ Colab T4; khoảng 10-15 phút)
python -m src.event_pipeline.model train --task all --epochs 15

# Dự đoán trên test (thực thể gold) rồi chấm
python -m src.event_pipeline.model predict --split test
python -m src.event_pipeline.evaluate --gold datasets/test.jsonl --pred datasets/processed/test_event_pred.jsonl
```

Mô hình lưu ở `server/models/event_trigger/` và `server/models/event_argument/` (không đưa lên git).
Lịch sử train (loss, val F1 theo epoch) nằm trong `train_history.json` của mỗi thư mục.

## Baseline làm gì

- Trigger: khớp từ khóa theo `TRIGGER_LEXICON` (cụm dài trước cụm ngắn). MA_TUY chỉ tính khi chất ma túy
  nằm gần động từ (động từ "yếu" như giao, giấu, cất chỉ tính khi chất ma túy đứng ngay sau). "Khống chế,
  bắt giữ" và chuỗi thủ đoạn lừa ("giả giọng…, tự xưng…") được tính là một sự kiện. Bỏ các trường hợp quy ước không gán: cụm không phải trigger ("bắt đầu", "trại tạm giam",
  "kẻ trộm", "nhóm cướp"...), từ khóa đứng sau dấu hiệu chưa xảy ra ("ý định", "để", "sẽ", "không",
  "đề nghị"...), từ khóa nằm trong tên tội (sau "tội", "hành vi") hoặc trong tên đơn vị. "Khởi tố" nhắc lại
  nhiều lần chỉ giữ lần đầu.
- Vai trò, chỉ xét thực thể trong cùng mệnh đề với trigger:
  - CRIME là TOI_DANH; TIME là THOI_GIAN (MUC_AN nếu là mức án và trigger là XET_XU).
  - LOCATION là DIA_DIEM, trừ khi là quê / nơi ở ("quê", "trú", "ngụ", "SN 1990, ở..."), kể cả chuỗi
    địa chỉ nhiều cấp trong ngoặc.
  - TIME đứng trước "cho biết", "thông tin" (ngày đưa tin) thì không nối.
  - ORGANIZATION gần nhất phía trước trigger tố tụng là CO_QUAN.
  - PERSON: với sự kiện tố tụng, người đứng sau trigger là DOI_TUONG; với sự kiện phạm tội, người đứng
    trước là DOI_TUONG, người đứng sau là NAN_NHAN.
  - DRUG / PRODUCT / MONEY nối theo loại sự kiện (TANG_VAT, TAI_SAN, HUNG_KHI).
