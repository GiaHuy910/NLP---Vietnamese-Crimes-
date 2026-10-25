# Hướng dẫn chạy thử

Các lệnh dưới đây dùng PowerShell trên Windows. Kết quả mong đợi ghi ở cuối mỗi bước để đối chiếu
(số liệu đầy đủ xem `RESULTS.md`).

## 1. Lấy code

Lần đầu:

```powershell
git clone https://github.com/GiaHuy910/NLP---Vietnamese-Crimes-.git vietnamese-crimes
cd vietnamese-crimes
git checkout ninh
```

Đã có repo thì chỉ cần cập nhật:

```powershell
git fetch origin
git checkout ninh
git pull origin ninh
```

## 2. Cài môi trường

Chạy trong thư mục `server/`, cần Python 3.10 trở lên.

```powershell
cd server
python -m venv .venv
.venv\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-ner.txt
```

Nếu PowerShell báo không cho chạy script khi activate, chạy trước lệnh:
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`

Từ đây trở đi, mọi lệnh đều chạy trong `server/` với venv đã bật (đầu dòng có `(.venv)`).

## 3. Đặt model

Model nặng khoảng 500 MB mỗi cái nên không có trên git; lấy file zip trên Drive của nhóm rồi giải nén
vào `server/models/` sao cho cấu trúc như sau:

```
server/
  models/
    config.json, model.safetensors, ...   (model NER của luồng 1, nằm trực tiếp trong models/)
    event_trigger/                        (model trigger của luồng 2)
    event_argument/                       (model vai trò của luồng 2)
```

Các bước 4, 6 và 7 (baseline, kiểm tra bộ chấm) không cần model, có thể chạy trước.

## 4. Luồng 1: NER

### Chạy API nhận diện thực thể

Đảm bảo model NER đã được đặt trong `server/models/`, sau đó chạy từ thư mục `server/`:

```powershell
python -m src.main
```

Gửi câu cần nhận diện tới `POST /api/process`:

```powershell
$body = @{ text = "Ngày 15/8, Công an quận Đống Đa đã khởi tố Nguyễn Văn A." } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:3001/api/process -Method Post `
  -ContentType "application/json" -Body $body
```

API trả về `input_text` và danh sách `entities`, mỗi thực thể có `text`, `label`, `start`, `end`.
Nếu model chưa được cài hoặc chưa tồn tại, API trả HTTP 503 cùng thông báo lỗi.

Endpoint chỉ nhận diện trigger, không cần model:

```powershell
$body = @{ text = "Công an đã khởi tố Nguyễn Văn A." } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:3001/api/process/event-trigger -Method Post `
  -ContentType "application/json" -Body $body
```

Endpoint trả về `input_text` và danh sách `triggers` từ hàm `detect_triggers`.

### Đánh giá NER từ dòng lệnh

```powershell
# Tạo split từ dữ liệu gán tay
python -m src.ner_pipeline.cli prepare-splits --train train_ner.csv --validation val_ner.csv --test test_ner.csv

# Baseline luật  (mong đợi: overall f1 0.669)
python -m src.ner_pipeline.cli baseline

# PhoBERT  (cần model NER; mong đợi: overall f1 khoảng 0.799)
python -m src.ner_pipeline.cli evaluate

# Phân tích lỗi PhoBERT
python -m src.ner_pipeline.cli analyze
```

## 5. Luồng 2: Trigger, Argument, Relation

Baseline luật, không cần model (mong đợi trên test: Trigger F1 0.697, Relation F1 0.589, Event EM 0.275):

```powershell
python -m src.event_pipeline.evaluate --gold datasets/test.jsonl --baseline
```

Hệ thống chính: luật tìm trigger, PhoBERT nối vai trò (mong đợi trên test: Relation F1 0.609, Event EM 0.367):

```powershell
python -m src.event_pipeline.model predict --split test --trigger-source rules
python -m src.event_pipeline.evaluate --gold datasets/test.jsonl --pred datasets/processed/test_event_pred_rules.jsonl
```

Chạy cả 3 cấu hình (model, rules, gold) trên một tập, đổi `test` thành `val` nếu muốn xem val:

```powershell
foreach ($src in "model","rules","gold") {
  $sfx = if ($src -eq "model") { "" } else { "_$src" }
  Write-Host "`n######## $src"
  python -m src.event_pipeline.model predict --split test --trigger-source $src
  python -m src.event_pipeline.evaluate --gold datasets/test.jsonl --pred datasets/processed/test_event_pred$sfx.jsonl
}
```

Ý nghĩa `--trigger-source`:
- `model`: PhoBERT tìm trigger, PhoBERT nối vai trò.
- `rules`: luật tìm trigger, PhoBERT nối vai trò (hệ thống chọn).
- `gold`: dùng trigger gán tay, PhoBERT nối vai trò (trần trên, để phân tích).

Xem các câu bị đoán sai của baseline:

```powershell
python -m src.event_pipeline.evaluate --gold datasets/test.jsonl --baseline --errors 30
```

## 6. Train lại model luồng 2 (không bắt buộc)

Nên chạy trên GPU (Google Colab, Runtime T4). Trên CPU sẽ rất lâu.

```powershell
python -m src.event_pipeline.model train --task trigger --epochs 30
python -m src.event_pipeline.model train --task argument --epochs 15
```

Model mới ghi đè vào `server/models/event_trigger` và `server/models/event_argument`. Checkpoint được chọn
theo val, test không dùng trong lúc train.

## 7. Kiểm tra bộ chấm

```powershell
python -m unittest discover -s test -p "test_event_metrics.py"
```

Mong đợi: `Ran 4 tests ... OK`.

## Lỗi thường gặp

| Lỗi | Cách sửa |
|---|---|
| `No module named 'src'` | Chưa `cd server`. Mọi lệnh phải chạy trong thư mục `server/`. |
| `No module named 'torch'` / `transformers` / `underthesea` | Chưa bật venv hoặc chưa cài, làm lại bước 2. |
| `unrecognized arguments: --trigger-source` | Code cũ, chạy `git pull origin ninh`. |
| Không tìm thấy `models/event_trigger` hoặc file `config.json` | Chưa giải nén model đúng chỗ, xem bước 3 (hay gặp lỗi lồng 2 lớp `models/models/`). |
| `FileNotFoundError ... test_event_pred_rules.jsonl` | Chưa chạy lệnh `predict` trước lệnh `evaluate`. |
| `git add` báo `pathspec ... did not match` | Đang đứng trong `server/`; lệnh git với đường dẫn `server/...` phải chạy ở thư mục gốc repo. |
