import pandas as pd

from config import (ANNOTATION_DIR, DATA_DIR, MAX_PER_DOC, N_DOUBLE, N_PER_SPLIT, SEED,
                    TRAIN_KEYWORD_SHARE, read_csv)
from rules import has_trigger_keyword

ANNOTATION_COLS = ["entities", "triggers", "arguments", "note"]


def sample_split(df, n_total, seed):
    # 1. Mỗi bài giữ tối đa MAX_PER_DOC câu
    df = df.sample(frac=1, random_state=seed).groupby("doc_id").head(MAX_PER_DOC)
    # 2. Chia đều theo SubLabel
    groups = df.groupby("SubLabel")
    per_group = n_total // groups.ngroups
    out = pd.concat([g.sample(min(len(g), per_group), random_state=seed) for _, g in groups])
    # 3. Bù phần thiếu do chia không hết
    missing = n_total - len(out)
    if missing > 0:
        rest = df.drop(out.index)
        out = pd.concat([out, rest.sample(min(missing, len(rest)), random_state=seed)])
    return out


def sample_train(df, n_total, seed):
    print("  đang dò từ khóa trigger trên tập train (~1 phút)...", flush=True)
    df = df.copy()
    df["has_keyword"] = df["sentence"].map(has_trigger_keyword)
    n_kw = int(n_total * TRAIN_KEYWORD_SHARE)
    kw = sample_split(df[df["has_keyword"]], n_kw, seed)
    # nửa ngẫu nhiên: lấy từ các bài CHƯA được chọn để giữ giới hạn câu/bài
    rnd = sample_split(df[~df["doc_id"].isin(kw["doc_id"])], n_total - len(kw), seed)
    return pd.concat([kw, rnd])


if __name__ == "__main__":
    ANNOTATION_DIR.mkdir(exist_ok=True)
    summary = []
    for sp, n in N_PER_SPLIT.items():
        df = read_csv(DATA_DIR / f"{sp}_sentences.csv")
        s = sample_train(df, n, SEED) if sp == "train" else sample_split(df, n, SEED)
        s = s.sample(frac=1, random_state=SEED).reset_index(drop=True)
        s.insert(0, "ann_id", [f"{sp}_a{i:04d}" for i in range(len(s))])
        s["double_annotate"] = (sp == "train") & (s.index < N_DOUBLE)
        for col in ANNOTATION_COLS:
            s[col] = ""
        cols = ["ann_id", "doc_id", "sent_id", "SubLabel", "sentence", *ANNOTATION_COLS, "double_annotate"]
        s[cols].to_excel(ANNOTATION_DIR / f"{sp}_to_annotate.xlsx", index=False)
        row = {"split": sp, "sentences": len(s), "docs": s["doc_id"].nunique(),
               **s["SubLabel"].value_counts().to_dict()}
        if "has_keyword" in s:
            row["co_tu_khoa"] = int(s["has_keyword"].sum())
        summary.append(row)

    print(pd.DataFrame(summary).set_index("split").fillna(0).astype(int).T.to_string())
