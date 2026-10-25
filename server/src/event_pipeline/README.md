# Luồng 2: Trigger, Argument, Relation

Thư mục này chứa phần đánh giá và baseline luật cho luồng 2, dùng schema 8 loại sự kiện và 10 vai trò
(xem `docs/annotation_guidelines.md`). Chỉ dùng thư viện chuẩn của Python, không cần cài thêm gì.

## File

- `schema.py`: 8 loại sự kiện, 10 vai trò và nhãn thực thể được phép cho từng vai trò.
- `data.py`: đọc/ghi `.jsonl`, kiểm tra offset và quan hệ, đổi câu thành danh sách sự kiện dạng span.
- `metrics.py`: các chỉ số đánh giá.
- `baseline.py`: baseline luật (từ khóa trigger + luật nối vai trò).
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

Thực thể lấy từ gold (đánh giá riêng luồng 2, không phụ thuộc lỗi của NER).

| Tập | Trigger F1 | Argument F1 | Relation F1 | Event Exact Match |
|---|---|---|---|---|
| val (150 câu) | 0.6290 | 0.4983 | 0.4913 | 0.2581 |
| test (150 câu) | 0.6226 | 0.5455 | 0.5051 | 0.2075 |

Luật chỉ được chỉnh dựa trên tập train, không nhìn val/test.

## Baseline làm gì

- Trigger: khớp từ khóa theo `TRIGGER_LEXICON` (cụm dài trước cụm ngắn); MA_TUY chỉ tính khi câu có nhắc
  ma túy. Bỏ các trường hợp quy ước không gán: cụm không phải trigger ("bắt đầu", "trại tạm giam",
  "kẻ trộm", "nhóm cướp"...), từ khóa đứng sau dấu hiệu chưa xảy ra ("ý định", "để", "sẽ", "không",
  "đề nghị"...), từ khóa nằm trong tên tội (sau "tội", "hành vi") hoặc trong tên đơn vị. "Khởi tố" nhắc lại
  nhiều lần chỉ giữ lần đầu.
- Vai trò, chỉ xét thực thể trong cùng mệnh đề với trigger:
  - CRIME là TOI_DANH; TIME là THOI_GIAN (MUC_AN nếu là mức án và trigger là XET_XU).
  - LOCATION là DIA_DIEM, trừ khi đứng sau "quê", "trú", "ngụ"...
  - ORGANIZATION gần nhất phía trước trigger tố tụng là CO_QUAN.
  - PERSON: với sự kiện tố tụng, người đứng sau trigger là DOI_TUONG; với sự kiện phạm tội, người đứng
    trước là DOI_TUONG, người đứng sau là NAN_NHAN.
  - DRUG / PRODUCT / MONEY nối theo loại sự kiện (TANG_VAT, TAI_SAN, HUNG_KHI).
