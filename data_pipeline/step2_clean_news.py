import re

import pandas as pd

from config import DATA_DIR, NO_VIOLATION_SUBLABEL, SPLITS, read_csv, write_csv


def norm_key(s):
    """Chữ thường, bỏ dấu câu -> so trùng không bị lệch do ' , ' hay ', '."""
    return re.sub(r"\W+", " ", s.lower()).strip()


# Nhiễu
UPPER = "A-Z" + "".join(chr(i) for i in range(0xC0, 0x1EFA) if chr(i).isupper())
NAME_TOKEN = rf"[{UPPER}][{UPPER}.]*"                                # QUANG, Đ, N.ẨN, V.CƯỜNG
CAPTION = re.compile(
    rf"[-–]?\s*(?:Ảnh|Đồ hoạ|Đồ họa)\s*:\s*(?:{NAME_TOKEN}\s*\.?\s*){{1,4}}(?=\s|$)")   # "- Ảnh : Đ . BÌNH ."
CAPTION_SOURCE = re.compile(r"[-–]\s*Ảnh\s*:\s*[^.]{1,50}?\s\.(?=\s|$)")              # "- Ảnh : Công an cung cấp ."
CAPTION_PAREN = re.compile(r"\(\s*(?:Ảnh|Nguồn)\s*:[^()]{0,60}\)")                    # "( Ảnh : Báo Người lao động )"
CLIP = re.compile(r"(?:XEM CLIP|Xem [Cc]lip|Clip)\s*:\s*")
URL = re.compile(r"https?://\S+|www\.\S+")


def remove_noise(s):
    s = CAPTION_PAREN.sub(" ", s)
    s = CAPTION.sub(" . ", s)           # giữ ranh giới câu, nếu không câu chú thích dính vào câu sau
    s = CAPTION_SOURCE.sub(" . ", s)
    s = CLIP.sub("", s)
    s = URL.sub(" ", s)
    s = re.sub(r"\.(\s+\.)+", ".", s)   # ". ." -> "."
    s = re.sub(r"^\s*\.\s*", "", s)     # dấu chấm thừa ở đầu
    return re.sub(r"\s+", " ", s).strip()


# Chống rò rỉ
def keys(df):
    content = df["Content"].map(norm_key)
    return content, content.str[:200], df["Summarize"].map(norm_key)


def drop_overlap(df, held_dfs):
    """Bỏ khỏi df các bài trùng với held_dfs, và các bài trùng ngay trong df."""
    held_full, held_head, held_sum = set(), set(), set()
    for h in held_dfs:
        c, hd, sm = keys(h)
        held_full |= set(c); held_head |= set(hd); held_sum |= set(sm)
    c, hd, sm = keys(df)
    leak = c.isin(held_full) | hd.isin(held_head) | sm.isin(held_sum)
    dup = hd.duplicated() | sm.duplicated()
    return df[~(leak | dup)].reset_index(drop=True), int(leak.sum()), int((dup & ~leak).sum())


if __name__ == "__main__":
    dfs = {sp: read_csv(DATA_DIR / f"{sp}_clean.csv") for sp in SPLITS}
    report = {sp: {"rows_in": len(df)} for sp, df in dfs.items()}

    for sp, df in dfs.items():
        before = df["Content"].copy()
        df["Content"] = df["Content"].map(remove_noise)
        df["Summarize"] = df["Summarize"].map(remove_noise)
        report[sp]["noise_docs_changed"] = int((before != df["Content"]).sum())

        bad = (df["Label"] == "Khác") & (df["SubLabel"] != NO_VIOLATION_SUBLABEL)
        df.loc[bad, "SubLabel"] = NO_VIOLATION_SUBLABEL
        report[sp]["sublabel_fixed"] = int(bad.sum())

    dfs["test"], _, report["test"]["dup_removed"] = drop_overlap(dfs["test"], [])
    dfs["val"], report["val"]["leak_removed"], report["val"]["dup_removed"] = drop_overlap(
        dfs["val"], [dfs["test"]])
    dfs["train"], report["train"]["leak_removed"], report["train"]["dup_removed"] = drop_overlap(
        dfs["train"], [dfs["val"], dfs["test"]])

    for sp, df in dfs.items():
        df.insert(0, "doc_id", [f"{sp}_{i:05d}" for i in range(len(df))])
        write_csv(df, DATA_DIR / f"{sp}.csv")
        report[sp]["rows_out"] = len(df)

    cols = ["rows_in", "noise_docs_changed", "sublabel_fixed", "leak_removed", "dup_removed", "rows_out"]
    print(pd.DataFrame(report).T.reindex(columns=cols).fillna(0).astype(int).to_string())
