# Tổng hợp kết quả: Trích xuất sự kiện và quan hệ từ tin tội phạm tiếng Việt

Tài liệu này gom toàn bộ số liệu để viết báo cáo: dữ liệu, cách đánh giá, kết quả luồng 1 (NER) và luồng 2
(trigger, argument, relation), phân tích lỗi và hạn chế. Mọi số liệu đều chạy trên dữ liệu gán tay của nhóm.

## 1. Dữ liệu

### 1.1 Corpus thô

| Thông tin | Giá trị |
|---|---|
| Số bài báo | 44,240 (chia sẵn train / val / test theo tỉ lệ 70 / 10 / 20) |
| Nhãn Label | khoảng 83% là "vi phạm", lệch lớp mạnh |
| Nhãn SubLabel | lệch lớp, nhóm Giao thông chỉ khoảng 3% |
| Mâu thuẫn Label / SubLabel | 353 bài |
| Độ dài bài | trung vị khoảng 460 từ; 86% bài dài hơn 256 từ (giới hạn của PhoBERT) |
| Lỗi định dạng | 46% bài có khoảng trắng trước dấu câu, 11% có chú thích ảnh, 6% chưa chuẩn hóa Unicode NFC |
| Trùng lặp gần giữa các tập | 14 cặp train và test gần trùng nhau |

Chi tiết trong `notebooks/eda_raw_corpus.ipynb`.

### 1.2 Pipeline xử lý

44,240 bài, sau khi làm sạch còn 43,170 bài, tách được khoảng 601 nghìn câu, chọn ra 601 câu để gán tay
trên Label Studio. Các bước 1 đến 7 mô tả trong `data_pipeline/README.md`.

### 1.3 Tập gán tay (gold)

| Tập | Số câu | Cách chọn câu |
|---|---|---|
| train | 301 | 50% câu khớp regex từ khóa trigger, 50% ngẫu nhiên; phân tầng theo SubLabel; tối đa 2 câu mỗi bài |
| val | 150 | ngẫu nhiên, phân tầng theo SubLabel |
| test | 150 | ngẫu nhiên, phân tầng theo SubLabel |

Train được "làm giàu" bằng regex để có đủ ví dụ trigger. Val và test lấy ngẫu nhiên để phản ánh phân bố
thật của tin tức.

Schema: 8 nhãn thực thể (PERSON, ORGANIZATION, LOCATION, TIME, MONEY, PRODUCT, DRUG, CRIME), 8 loại sự
kiện (BAO_LUC, BAT_GIU, CUOP_TROM, KHOI_TO, LUA_DAO, MA_TUY, THU_GIU, XET_XU) và 10 vai trò (DOI_TUONG,
NAN_NHAN, CO_QUAN, DIA_DIEM, THOI_GIAN, TANG_VAT, TAI_SAN, HUNG_KHI, TOI_DANH, MUC_AN).

## 2. Cách đánh giá

Tất cả chỉ số so khớp chính xác theo vị trí ký tự, micro-average, có Precision, Recall và F1.

| Chỉ số | Một dự đoán được tính đúng khi |
|---|---|
| NER F1 | đúng vị trí và đúng nhãn thực thể |
| Trigger F1 | đúng vị trí trigger và đúng loại sự kiện |
| Argument F1 | đúng trigger và đúng thực thể được nối vào |
| Relation F1 | như Argument F1 và đúng cả vai trò |
| Event Exact Match | trigger đúng và toàn bộ argument (vị trí + vai trò) khớp hoàn toàn với gold |

Nguyên tắc: mọi lựa chọn (luật, siêu tham số, checkpoint, cấu hình) chỉ dựa trên train và val. Test chỉ
dùng để báo cáo kết quả cuối.

## 3. Luồng 1: Nhận dạng thực thể (NER)

Kết quả trên test (150 câu, 355 thực thể):

| Nhãn | Số mẫu | Baseline F1 | PhoBERT F1 |
|---|---|---|---|
| **Tổng (micro)** | 355 | **0.669** (P 0.734, R 0.614) | **0.799** (P 0.749, R 0.856) |
| PERSON | 130 | 0.673 | 0.977 |
| ORGANIZATION | 88 | 0.484 | 0.747 |
| LOCATION | 60 | 0.691 | 0.773 |
| TIME | 25 | 0.824 | 0.679 |
| MONEY | 18 | 0.848 | 0.833 |
| PRODUCT | 15 | 0.889 | 0.426 (P 0.283) |
| DRUG | 16 | 0.813 | 0.686 |
| CRIME | 3 | 0.857 | 0.600 |

Nhận xét:

- PhoBERT tăng F1 tổng từ 0.669 lên 0.799, chủ yếu nhờ recall (0.614 lên 0.856). Tăng mạnh nhất ở PERSON
  và ORGANIZATION, hai nhãn nhiều mẫu và khó bắt bằng luật.
- Baseline vẫn tốt hơn ở các nhãn có mẫu hình rõ (TIME, MONEY, PRODUCT, DRUG). Các nhãn này ít mẫu train
  nên PhoBERT học chưa đủ. PRODUCT có precision chỉ 0.283, tức đoán thừa rất nhiều.
- CRIME chỉ có 3 mẫu test, số liệu không đủ tin cậy.

Phân tích lỗi PhoBERT: 48 thực thể đoán thừa, 35 bỏ sót, 23 sai biên (đúng nhãn nhưng lệch vị trí), 5 nhầm
ORGANIZATION thành LOCATION.

Sửa lỗi trong quá trình làm: hàm căn chỉnh BIO (`alignment.py`) ban đầu khớp chuỗi không theo ranh giới
từ, sinh ra 44 thực thể PERSON giả chỉ một chữ cái. Sau khi sửa, số thực thể test là 355.

## 4. Luồng 2: Trigger, Argument, Relation

Thực thể lấy từ gold để đánh giá riêng luồng 2, không bị ảnh hưởng bởi lỗi của NER.

### 4.1 Các hệ thống

- **Baseline luật**: trigger bằng từ khóa có ràng buộc ngữ cảnh (ví dụ MA_TUY phải có chất ma túy ở gần,
  bỏ trigger đứng sau dấu hiệu chưa xảy ra như "ý định", "đề nghị"); vai trò nối bằng luật vị trí và nhãn
  thực thể.
- **PhoBERT trigger**: gán nhãn BIO trên từ đã tách bằng underthesea, 8 loại sự kiện. Giảm trọng số nhãn O
  (0.3), learning rate 5e-5, 30 epoch, checkpoint tốt nhất theo val ở epoch 15 (val Trigger F1 0.727).
- **PhoBERT argument**: với mỗi cặp (trigger, thực thể), chèn dấu `<t> </t>`, `<e> </e>` và token loại
  sự kiện, loại thực thể, rồi phân loại vào 10 vai trò hoặc NONE (trọng số NONE 0.5). Chỉ cho phép vai trò
  hợp lệ với nhãn thực thể. Checkpoint chọn theo Relation F1 trên val khi dùng trigger gold.

### 4.2 Chọn cấu hình trên val

| Cấu hình (trigger + argument) | Trigger F1 | Argument F1 | Relation F1 | Event EM |
|---|---|---|---|---|
| Luật + luật (baseline) | 0.756 | 0.621 | 0.594 | 0.347 |
| PhoBERT + PhoBERT | 0.727 | 0.630 | 0.624 | 0.439 |
| **Luật + PhoBERT** | **0.756** | **0.682** | **0.675** | **0.472** |
| Trigger gold + PhoBERT (trần trên) | 1.000 | 0.846 | 0.841 | 0.557 |

Cấu hình **luật tìm trigger + PhoBERT nối vai trò** tốt nhất trên val ở mọi chỉ số, nên được chọn làm hệ
thống chính.

### 4.3 Kết quả trên test

| Cấu hình | Trigger F1 | Argument F1 | Relation F1 | Event EM |
|---|---|---|---|---|
| Luật + luật (baseline) | 0.697 | 0.629 | 0.589 | 0.275 |
| PhoBERT + PhoBERT | 0.654 | 0.677 | 0.595 | 0.356 |
| **Luật + PhoBERT (hệ thống chọn)** | **0.697** | **0.696** | **0.609** | **0.367** |
| Trigger gold + PhoBERT (trần trên) | 1.000 | 0.804 | 0.710 | 0.519 |

Thứ hạng trên test giống trên val, nên lựa chọn ổn định.

Hệ thống chọn, chi tiết trên test:

| Loại sự kiện | Số trigger | Trigger F1 |
|---|---|---|
| BAO_LUC | 14 | 0.720 |
| BAT_GIU | 10 | 0.857 |
| CUOP_TROM | 5 | 0.800 |
| KHOI_TO | 5 | 0.667 |
| LUA_DAO | 7 | 0.571 |
| MA_TUY | 7 | 0.429 |
| THU_GIU | 2 | 1.000 |
| XET_XU | 4 | 0.667 |

| Vai trò | Số quan hệ | Relation F1 |
|---|---|---|
| CO_QUAN | 10 | 0.783 |
| DIA_DIEM | 8 | 0.500 |
| DOI_TUONG | 33 | 0.658 |
| HUNG_KHI | 9 | 0.714 |
| MUC_AN | 2 | 0.500 |
| NAN_NHAN | 14 | 0.462 |
| TAI_SAN | 5 | 0.727 |
| TANG_VAT | 10 | 0.444 |
| THOI_GIAN | 4 | 0.750 |
| TOI_DANH | 2 | 0.400 |

### 4.4 Nhận xét

1. **PhoBERT nối vai trò tốt hơn luật.** Cùng trigger từ luật, Relation F1 tăng từ 0.594 lên 0.675 trên
   val và từ 0.589 lên 0.609 trên test; Event EM tăng từ 0.275 lên 0.367 trên test.
2. **PhoBERT tìm trigger chưa hơn luật.** Yếu nhất ở LUA_DAO (recall 0.18 trên val, 0.29 trên test) và
   MA_TUY (recall 0.14 trên test). Hai loại này ít ví dụ trong 301 câu train; trigger lừa đảo lại đa dạng
   ("giả danh", "tự xưng", "chiếm đoạt"...). Luật có ràng buộc ngữ cảnh nên ổn định hơn khi dữ liệu ít.
3. **Lỗi trigger là nút thắt chính.** Khi trigger đúng 100%, Relation F1 lên 0.841 (val) và 0.710 (test),
   tức khoảng 0.10 đến 0.17 điểm bị mất do trigger.
4. **Vai trò khó:** NAN_NHAN dễ nhầm với DOI_TUONG vì cùng là PERSON; DIA_DIEM dễ nhầm giữa nơi xảy ra và
   quê quán / nơi ở; TANG_VAT có precision thấp do nối thừa vật chứng.
5. **Khoảng cách val và test:** val cao hơn test vài điểm ở mọi cấu hình, phù hợp với việc chọn cấu hình
   và checkpoint trên val. Baseline luật cũng chỉ được chỉnh trên train và val.

## 5. Hạn chế

- Tập test nhỏ (54 trigger, 97 quan hệ, 355 thực thể). Chênh lệch 0.01 đến 0.02 điểm chưa có ý nghĩa
  thống kê; nhiều nhãn và vai trò chỉ có 2 đến 5 mẫu.
- Chỉ đánh giá trên câu đơn, chưa xử lý sự kiện trải qua nhiều câu hoặc đồng tham chiếu.
- Luồng 2 dùng thực thể gold. Khi nối với NER thật, điểm sẽ thấp hơn do lỗi NER lan sang.
- Còn một số lỗi nhãn đã phát hiện nhưng chưa sửa: vài span thừa khoảng trắng đầu (val_a0051, a0120,
  a0125), "Công an tỉnh Lai Châu" (val_a0048), "Bà Nga" nên là "Nga", "Bắc" / "Nam" không phải LOCATION,
  "400 triệu đồng" (val) và "25 triệu đồng" (test) nên là MONEY.
- Bộ luật trigger ở nhánh `Tu` (commit 291d88f, 23807f7) được chỉnh trực tiếp theo test (test 0.954 nhưng
  train 0.639, val 0.562), là rò rỉ dữ liệu nên không dùng trong báo cáo.

## 6. Chạy lại

Trong thư mục `server/`, cần model ở `server/models/event_trigger` và `server/models/event_argument`.

```powershell
# Luồng 1
python -m src.ner_pipeline.cli prepare-splits --train train_ner.csv --validation val_ner.csv --test test_ner.csv
python -m src.ner_pipeline.cli baseline

# Luồng 2: baseline luật
python -m src.event_pipeline.evaluate --gold datasets/test.jsonl --baseline

# Luồng 2: hệ thống chọn (luật + PhoBERT)
python -m src.event_pipeline.model predict --split test --trigger-source rules
python -m src.event_pipeline.evaluate --gold datasets/test.jsonl --pred datasets/processed/test_event_pred_rules.jsonl
```

Đổi `--trigger-source` thành `model` hoặc `gold` để chạy hai cấu hình còn lại; đổi `test` thành `val` để
xem kết quả trên val.
