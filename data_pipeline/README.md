# Data pipeline: làm sạch, gán nhãn và xuất dữ liệu

Phần này chuẩn bị dữ liệu cho **cả 2 luồng** của đồ án (Đề tài 5, trích xuất sự kiện vi phạm pháp luật từ tin tức tiếng Việt):

- **Luồng 1 (NER)**: nhận diện 8 loại thực thể.
- **Luồng 2 (Event)**: Trigger → Argument → Relation.

Người phụ trách: Đỗ Đăng Ninh (tiền xử lý và gán nhãn dữ liệu cho cả 2 luồng).

---

## 1. Kết quả cuối

Nằm trong `data/dataset/`:

| Tập | Số câu | Nhãn | Thực thể | Trigger | Quan hệ | Dùng để |
|---|---|---|---|---|---|---|
| `train` | 301 | gán tay | 894 | 192 | 460 | train mô hình |
| `val` | 150 | gán tay | 408 | 70 | 165 | chọn epoch / dừng sớm |
| `test` | 150 | gán tay | 350 | 54 | 97 | **báo cáo kết quả cuối** |

Mỗi tập có 2 file:

- `{tập}.jsonl` cho **luồng 2**, mỗi dòng một câu (ví dụ minh họa, đã rút gọn):
  ```json
  {"ann_id": "test_a0003", "doc_id": "test_01234", "SubLabel": "Tội phạm Trật tự xã hội / Hình sự",
   "source": "gold", "sentence": "... Hùng dùng dao đâm ... anh Thuận ...",
   "entities": [{"id": "e1", "start": 52, "end": 56, "text": "Hùng", "label": "PERSON"}, ...],
   "triggers": [{"id": "t1", "start": 66, "end": 69, "text": "đâm", "label": "BAO_LUC"}],
   "relations": [{"trigger_id": "t1", "arg_id": "e1", "role": "DOI_TUONG"}, ...]}
  ```
  `start`, `end` là vị trí ký tự trong `sentence` (`sentence[start:end] == text`).
- `{tập}_ner.csv` cho **luồng 1**, gồm 2 cột `sentence, entities` với `entities` dạng `TEXT|LABEL; TEXT|LABEL`.

**Lưu ý:** chỉ báo cáo điểm trên `test`. Điểm trên `val` chỉ dùng để theo dõi lúc train.

---

## 2. Schema

**8 nhãn thực thể:** PERSON, ORGANIZATION, LOCATION, TIME, MONEY, DRUG, PRODUCT, CRIME

**8 loại sự kiện (trigger):**

| Nhóm | Loại | Ví dụ trigger |
|---|---|---|
| Phạm tội | LUA_DAO | lừa đảo chiếm đoạt, chiếm đoạt, giả danh |
| | MA_TUY | mua bán, tàng trữ, vận chuyển, sản xuất (khi có nhắc ma túy) |
| | BAO_LUC | giết, sát hại, đâm, chém, đánh, hành hung, hiếp dâm |
| | CUOP_TROM | cướp, cướp giật, trộm cắp, đột nhập |
| Tố tụng | BAT_GIU | bắt, bắt giữ, bắt quả tang, tạm giữ, tạm giam |
| | THU_GIU | thu giữ, tịch thu |
| | KHOI_TO | khởi tố, truy tố |
| | XET_XU | xét xử, tuyên phạt, tuyên án, kết án |

**10 vai trò (quan hệ luôn đi từ trigger tới thực thể):**

| Vai trò | Nối tới nhãn |
|---|---|
| DOI_TUONG, NAN_NHAN | PERSON, ORGANIZATION |
| CO_QUAN | ORGANIZATION |
| TAI_SAN | MONEY, PRODUCT |
| TANG_VAT | DRUG, PRODUCT |
| HUNG_KHI | PRODUCT |
| TOI_DANH | CRIME |
| MUC_AN | TIME, MONEY |
| THOI_GIAN | TIME |
| DIA_DIEM | LOCATION |

Quy ước gán nhãn chi tiết: [`docs/annotation_guidelines.md`](../docs/annotation_guidelines.md).

---

## 3. Cấu trúc thư mục

Thư mục `data_pipeline/` (script):

- `config.py`: đường dẫn, tham số, từ khóa trigger
- `rules.py`: luật nhận diện thực thể và trigger (gán sẵn, baseline)
- `step1_fix_encoding.py` ... `step7_export_dataset.py`: 7 bước xử lý
- `check_annotations.py`: kiểm tra lỗi nhãn tự động
- `explore_triggers.py`: tìm động từ đặc trưng (dùng để thiết kế schema)
- `labelstudio_config.xml`: giao diện gán nhãn Label Studio
- `requirements.txt`: thư viện cần cài

Thư mục khác:

- `docs/annotation_guidelines.md`: quy ước gán nhãn
- `data/corpus news/`: dữ liệu thô (không có trên git, xin trên Drive nhóm)
- `data/annotation/`: file gán nhãn và file export Label Studio
- `data/dataset/`: dữ liệu cuối cho 2 luồng

---

## 4. Chạy lại từ đầu

### Cài đặt

```bash
pip install -r data_pipeline/requirements.txt
```

Đặt 3 file gốc `train_cleaned_labeled.csv`, `val_cleaned_labeled.csv`, `test_cleaned_labeled.csv` vào `data/corpus news/`.

### Thứ tự chạy (trong thư mục `data_pipeline/`)

| Bước | Lệnh | Việc làm | Kết quả |
|---|---|---|---|
| 1 | `python step1_fix_encoding.py` | Sửa lỗi Unicode, ký tự ẩn | `*_clean.csv` |
| 2 | `python step2_clean_news.py` | Xóa chú thích ảnh/URL, sửa SubLabel, **chống rò rỉ** val/test | `train/val/test.csv` (30.907 / 4.420 / 8.844 bài) |
| 3 | `python step3_apply_scope.py --apply` | Bỏ nhóm "Vi phạm Giao thông" (~2%) | bỏ 684 / 126 / 191 bài |
| 4 | `python step4_split_sentences.py` | Tách câu (underthesea), lọc 5–100 chữ | `*_sentences.csv` (418.287 / 60.034 / 123.281 câu) |
| 5 | `python step5_sample_for_annotation.py` | Lấy mẫu chia đều theo SubLabel, tối đa 2 câu/bài | `annotation/*_to_annotate.xlsx` (600 / 150 / 150) |
| 6 | `python step6_to_labelstudio.py` | Tạo file import Label Studio (train có nhãn gán sẵn) | `annotation/*_tasks.json` |
| 7 | `python step7_export_dataset.py <file.json> <tên> [--gold-only]` | Chuyển JSON Label Studio sang dữ liệu 2 luồng | `dataset/*.jsonl`, `*_ner.csv` |

### Chi tiết từng bước

**Bước 1 - Sửa mã hóa ký tự** (`step1_fix_encoding.py`)
- Vào: `corpus news/{train,val,test}_cleaned_labeled.csv` (dữ liệu gốc). Ra: `corpus news/{split}_clean.csv`.
- Chuẩn hóa Unicode NFC (dấu tiếng Việt dạng rời thành ký tự dựng sẵn).
- Gắn lại dấu bị tách khỏi chữ bởi khoảng trắng ("Ky ̀" thành "Kỳ").
- Xóa ký tự ẩn (zero-width space, BOM lạc, soft hyphen); thay ký tự hỏng `\ufffd` bằng khoảng trắng; gộp khoảng trắng thừa.
- Hàm `clean_text` được dùng lại cho văn bản người dùng nhập ở API.

**Bước 2 - Xóa nhiễu, sửa nhãn, chống rò rỉ** (`step2_clean_news.py`)
- Vào: `{split}_clean.csv`. Ra: `{split}.csv` (thêm cột `doc_id`).
- Xóa chú thích ảnh ("- Ảnh : Đ . BÌNH ."), tiền tố "XEM CLIP:", URL.
- Sửa SubLabel mâu thuẫn với Label: Label = "Khác" thì SubLabel = "Khác (Không vi phạm)".
- Chống rò rỉ: test giữ nguyên; val bỏ bài trùng test; train bỏ bài trùng val/test. Hai bài được coi là trùng khi giống nội dung, hoặc giống 200 ký tự đầu, hoặc giống tiêu đề (bỏ qua hoa/thường và dấu câu).

**Bước 3 - Thu hẹp phạm vi** (`step3_apply_scope.py`)
- Vào/ra: `{split}.csv` (ghi đè cùng tên).
- Bỏ các nhóm trong `EXCLUDE_SUBLABELS` (config.py). "Vi phạm Giao thông" bị bỏ vì chỉ khoảng 2% số bài vi phạm, quá ít để huấn luyện và đánh giá tin cậy theo từng loại sự kiện.
- `python step3_apply_scope.py` chỉ xem trước; thêm `--apply` mới sửa file. Chạy `--apply` nhiều lần vẫn an toàn; muốn lấy lại bản đầy đủ thì chạy lại bước 2.

**Bước 4 - Tách câu** (`step4_split_sentences.py`)
- Vào: `{split}.csv` (1 dòng = 1 bài). Ra: `{split}_sentences.csv` (1 dòng = 1 câu).
- Chỉ lấy bài có Label "Vi phạm pháp luật", bỏ các nhóm trong `EXCLUDE_SUBLABELS`.
- Đưa 2 kiểu văn bản về một dạng ("23/3 , Cơ quan" thành "23/3, Cơ quan").
- Tách câu bằng underthesea, nối lại mảnh vỡ do cắt nhầm ở tên viết tắt ("bà L." | "(SN 1967...)").
- Bỏ câu đầu nếu trùng câu tóm tắt; bỏ câu dưới `MIN_WORDS` (5) hoặc trên `MAX_WORDS` (100) chữ.
- Hàm `split_sentences` được dùng lại cho bài báo người dùng nhập ở API.

**Bước 5 - Lấy mẫu câu để gán nhãn** (`step5_sample_for_annotation.py`)
- Vào: `{split}_sentences.csv`. Ra: `annotation/{split}_to_annotate.xlsx`.
- Chia đều theo SubLabel, mỗi bài tối đa `MAX_PER_DOC` (2) câu.
- Train: 50% câu có từ khóa trigger, phần còn lại ngẫu nhiên. Lý do: chỉ khoảng 25-30% câu có sự kiện, lấy ngẫu nhiên thì mô hình có quá ít ví dụ trigger để học.
- Val/test: 100% ngẫu nhiên. Nếu chỉ chọn câu có sẵn "bắt", "khởi tố"... thì baseline từ khóa được chấm trên đúng loại câu nó giỏi, điểm bị thổi phồng.
- `N_DOUBLE` câu train được đánh dấu `double_annotate` để gán lại sau, đo độ nhất quán (nếu thời gian cho phép).

**Bước 6 - Tạo file nhập Label Studio** (`step6_to_labelstudio.py`)
- Vào: `annotation/{split}_to_annotate.xlsx`. Ra: `annotation/{split}_tasks.json`.
- Train: kèm `predictions` là nhãn gán sẵn bằng luật (`rules.py`), trong Label Studio chỉ cần sửa. Gán sẵn chỉ có thực thể và trigger; quan hệ nối tay.
- Val/test: không gán sẵn, gán từ đầu, để nhãn không bị luật dẫn dắt và việc đánh giá baseline luật trên val/test được công bằng.
- Có thể chạy riêng một tập: `python step6_to_labelstudio.py train`.

**Bước 7 - Xuất dữ liệu cho 2 luồng** (`step7_export_dataset.py`)
- Vào: file JSON export từ Label Studio. Ra (trong `data/dataset/`): `{tên}.jsonl` cho luồng 2 và `{tên}_ner.csv` cho luồng 1.
- Câu có `annotations` (gán tay) được tính là gold; câu chỉ có `predictions` (luật gán sẵn) là silver.
- `--gold-only`: chỉ lấy câu đã gán tay (dùng cho train vì chưa gán tay hết 600 câu).
- Quan hệ nối ngược chiều (thực thể sang trigger) được tự đảo lại thành trigger sang thực thể.
- `--val N`: tách N câu làm val, chia đều theo SubLabel (không còn dùng vì đã có val gold riêng).

### Các file hỗ trợ

**`config.py` - Cấu hình chung**
- Đường dẫn: `data/corpus news/` (dữ liệu thô và file trung gian, không đưa lên git), `data/annotation/` (file gán nhãn), `data/dataset/` (dữ liệu cuối, bước 7 tạo), `data/analysis/` (kết quả khám phá trigger).
- Tham số: `SEED = 42`; `EXCLUDE_SUBLABELS` (nhóm bị bỏ); `MIN_WORDS, MAX_WORDS = 5, 100` (dưới 5 chữ thường là rác, trên 100 chữ dễ vượt giới hạn PhoBERT); `N_PER_SPLIT` (600 / 150 / 150 câu); `MAX_PER_DOC = 2`; `N_DOUBLE = 50`; `TRAIN_KEYWORD_SHARE = 0.5`.
- `TRIGGER_LEXICON`: từ khóa trigger theo 8 loại sự kiện, dùng chung cho lấy mẫu train, gán nhãn sẵn và baseline. Cụm dài đặt trước cụm ngắn ("bắt giữ" trước "bắt") để khớp cụm dài nhất.
- `DRUG_WORDS`: MA_TUY chỉ tính khi câu có nhắc tới ma túy. `TRIGGER_STOP`: cụm chứa từ khóa nhưng không phải trigger ("bắt đầu", "bắt tay", "đâm xe"...).
- `read_csv`, `write_csv`: đọc/ghi CSV bằng `utf-8-sig` (có BOM để Excel mở đúng tiếng Việt).

**`rules.py` - Luật nhận diện thực thể và trigger**
- Dùng cho 2 việc: gán nhãn sẵn cho tập train trong Label Studio (người gán chỉ sửa), và làm baseline regex/từ khóa cho luồng 2.
- Thực thể: TIME, MONEY, DRUG bằng regex; CRIME lấy cụm sau chữ "tội" hoặc trong ngoặc kép sau "hành vi"; ORGANIZATION bắt đầu từ các đầu tên đơn vị ("Công an", "TAND", "Cơ quan CSĐT"...) rồi nối các chữ tiếp theo; PERSON/LOCATION lấy từ `underthesea.ner`, bỏ danh xưng ở đầu và đổi thành PERSON nếu đứng sau "anh", "chị", "bị can"...
- Span chồng nhau thì giữ span ưu tiên cao hơn (CRIME > ORGANIZATION > MONEY/TIME/DRUG > NER), rồi span dài hơn.
- Trigger: khớp nguyên cụm theo `TRIGGER_LEXICON` (không khớp dính vào chữ khác), bỏ cụm trong `TRIGGER_STOP` và cụm nằm trong CRIME/ORGANIZATION.
- Mọi hàm trả về danh sách span `{start, end, text, label}` tính theo ký tự.

**`explore_triggers.py` - Khám phá ứng viên trigger** (dùng để soạn schema sự kiện)
- Vào: `train_sentences.csv` (câu tin vi phạm) và `train.csv` (lấy câu tin "Khác" làm nền so sánh). Ra: `data/analysis/trigger_candidates.xlsx`.
- Lấy mẫu 5.000 câu mỗi nhóm SubLabel và 5.000 câu tin không vi phạm; gán từ loại bằng `underthesea.pos_tag`, giữ các động từ.
- Với mỗi động từ: tính % số câu có chứa nó trong từng nhóm, và `lift = % trong nhóm vi phạm / % trong tin thường`. Lift cao là động từ đặc trưng cho tin vi phạm (ví dụ "bắt giữ"); lift gần 1 là động từ chung chung (ví dụ "cho biết").
- Chỉ dùng tập train để không "nhìn trộm" val/test khi thiết kế schema.

**`check_annotations.py` - Kiểm tra lỗi nhãn tự động**
- Chạy: `python check_annotations.py <file.json>`. Đọc được cả file task có `predictions` lẫn file export có `annotations`.
- Ra: `<file>_issues.csv`, mỗi dòng là một lỗi nghi ngờ (`so_task, ann_id, loai_loi, chi_tiet, cau`). Đây chỉ là cảnh báo theo luật cố định, người gán mở câu ra và tự quyết sửa hay không.
- Nhóm lỗi gần như chắc chắn sai (phải sửa): `QH_SAI_KIEU`, `QH_NGUOC_CHIEU`, `QH_CHUA_CHON_VAI_TRO`, `TRIGGER_BI_TACH`, `TIME_BI_TACH`, `SPAN_DAU_CHAM`, `PERSON_SAI`, `ORG_CHUNG_CHUNG`.
- Nhóm nghi vấn (xem lại, thường đúng theo quy ước): `PERSON_CHUA_NOI`, `ORG_CHUA_NOI_CO_QUAN`, `CO_THE_THIEU_TRIGGER`, `CO_THE_KHONG_PHAI_SU_KIEN`, `TRIGGER_CHUA_NOI`, `CO_THE_THIEU_CO_QUAN`, `DIA_DIEM_LA_QUE_NOI_O`.

Bước 3 chạy không có `--apply` thì chỉ xem trước, không ghi file.

Lệnh bước 7 đã dùng:

```bash
python step7_export_dataset.py ../data/annotation/train.json train --gold-only
python step7_export_dataset.py ../data/annotation/val.json val
python step7_export_dataset.py ../data/annotation/test.json test
```

Kiểm tra lỗi nhãn sau mỗi lần export:

```bash
python check_annotations.py ../data/annotation/train.json   # ra train_issues.csv (không đưa lên git)
```

---

## 5. Các quyết định quan trọng

- **Chống rò rỉ dữ liệu:** test giữ nguyên; val bỏ bài trùng test; train bỏ bài trùng val/test. So trùng theo nội dung, 200 ký tự đầu và tiêu đề.
- **Phạm vi:** bỏ "Vi phạm Giao thông" vì quá ít (~2%) để train và đánh giá theo loại.
- **Lấy mẫu:** train lấy 50% câu có từ khóa trigger (chỉ ~25–30% câu có sự kiện). Val/test lấy **ngẫu nhiên hoàn toàn**, để không thổi phồng điểm baseline từ khóa.
- **Nhãn gold cho cả 3 tập:** gán tay trong Label Studio theo `docs/annotation_guidelines.md`. Train có nhãn gán sẵn bằng luật (`rules.py`) để gán nhanh hơn, sau đó sửa tay từng câu; chỉ lấy câu đã gán tay (`--gold-only`).
- **Val/test không có nhãn gán sẵn**, gán tay từ đầu để tránh việc gán tự động bị sai lệch do máy không hiểu ý nghĩa.
- **Nhiễu sẵn có:** một số câu mang SubLabel vi phạm nhưng nội dung không liên quan (tin giải trí, thống kê). Nhãn SubLabel gốc ở mức bài báo, không ở mức câu.

## 6. Lưu ý

- **Không mở rồi lưu CSV bằng Excel** vì sẽ hỏng mã hóa tiếng Việt. Script ghi `utf-8-sig` nên Excel *đọc* được bình thường.
- Đóng file Excel trước khi chạy script, nếu không sẽ gặp `PermissionError`.
- Label Studio nên cài trong venv riêng (`.venv-ls`). Chạy script pipeline bằng Python thường (`deactivate` trước).
