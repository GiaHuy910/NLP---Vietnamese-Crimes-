from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent / "data"   # <repo>/data
DATA_DIR = PROJECT_DIR / "corpus news"
ANNOTATION_DIR = PROJECT_DIR / "annotation"

SPLITS = ["train", "val", "test"]
SEED = 42

TEXT_COLS = ["Summarize", "Content"]
VIOLATION_LABEL = "Vi phạm pháp luật"
NO_VIOLATION_SUBLABEL = "Khác (Không vi phạm)"

# Phạm vi đề tài: bỏ nhóm chỉ chiếm ~2% số bài vi phạm (quá ít để train và đánh giá theo loại)
EXCLUDE_SUBLABELS = {"Vi phạm Giao thông"}

# Tách câu
MIN_WORDS, MAX_WORDS = 5, 100   # < 5 chữ thường là rác; > 100 chữ dễ vượt giới hạn PhoBERT

# Lấy mẫu gán nhãn
N_PER_SPLIT = {"train": 600, "val": 150, "test": 150}
MAX_PER_DOC = 2      # mỗi bài tối đa 2 câu
N_DOUBLE = 50        # số câu train cho 2 người cùng gán (đo độ đồng thuận)


def read_csv(path, **kw):
    import pandas as pd
    return pd.read_csv(path, encoding="utf-8-sig", keep_default_na=False, **kw)


def write_csv(df, path):
    df.to_csv(path, index=False, encoding="utf-8-sig")   # có BOM -> Excel mở đúng tiếng Việt


# Từ khóa trigger (dùng chung: lấy mẫu train, gán nhãn sẵn, baseline)
# Cụm dài đặt trước cụm ngắn ("bắt giữ" trước "bắt") để khớp cụm dài nhất.
TRIGGER_LEXICON = {
    "LUA_DAO":   ["lừa đảo", "chiếm đoạt", "lừa"],
    "MA_TUY":    ["mua bán", "buôn bán", "tàng trữ", "vận chuyển", "sử dụng trái phép"],
    "BAO_LUC":   ["sát hại", "giết", "đâm", "chém", "đánh đập", "hành hung"],
    "CUOP_TROM": ["cướp giật", "cướp", "trộm cắp", "trộm", "đột nhập"],
    "BAT_GIU":   ["bắt quả tang", "bắt khẩn cấp", "bắt giữ", "bắt tạm giam", "tạm giữ", "tạm giam",
                  "khống chế", "bắt"],
    "THU_GIU":   ["thu giữ", "tịch thu"],
    "KHOI_TO":   ["khởi tố", "truy tố"],
    "XET_XU":    ["xét xử", "tuyên phạt", "tuyên án", "kết án"],
}
# MA_TUY chỉ tính khi câu có nhắc tới ma túy
DRUG_WORDS = ["ma túy", "ma tuý", "heroin", "ketamin", "thuốc lắc", "cần sa", "methamphetamine", "mdma"]
# Không phải trigger dù chứa từ khóa
TRIGGER_STOP = ["bắt đầu", "bắt buộc", "bắt tay", "bắt gặp", "bắt kịp", "bắt nguồn", "bắt chước",
                "đâm vào", "đâm sầm", "đâm xe"]

TRAIN_KEYWORD_SHARE = 0.5   # train: 50% câu có từ khóa trigger, 50% ngẫu nhiên (val/test: 100% ngẫu nhiên)
