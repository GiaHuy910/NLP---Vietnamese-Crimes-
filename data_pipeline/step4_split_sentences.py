import re
import time

import pandas as pd
from underthesea import sent_tokenize

from config import (DATA_DIR, EXCLUDE_SUBLABELS, MAX_WORDS, MIN_WORDS, SPLITS,
                    VIOLATION_LABEL, read_csv, write_csv)

SPACE_BEFORE = re.compile(r"\s+([,.;:!?…)\]”’%])")   # "23/3 ," -> "23/3,"
SPACE_AFTER = re.compile(r"([(\[“‘])\s+")             # "( SN"  -> "(SN"


def detokenize(text):
    return SPACE_AFTER.sub(r"\1", SPACE_BEFORE.sub(r"\1", text))


def norm_key(s):
    return re.sub(r"\W+", " ", s.lower()).strip()


def split_sentences(text):
    """Bài báo (đã làm sạch) -> danh sách câu."""
    merged = []
    for s in (x.strip() for x in sent_tokenize(detokenize(text))):
        if not s:
            continue
        # Mảnh vỡ ("bà L." | "(SN 1967...)", "”.") -> nối vào câu trước
        is_fragment = len(s.split()) < 3 or s[0] in "(,;:)”’" or s[0].islower()
        if merged and is_fragment:
            merged[-1] = f"{merged[-1]} {s}"
        else:
            merged.append(s)
    return merged


def article_to_rows(row):
    sents = split_sentences(row["Content"])
    if sents and norm_key(sents[0]) == norm_key(detokenize(row["Summarize"])):
        sents = sents[1:]                       # câu đầu = câu tóm tắt -> bỏ
    return [{"doc_id": row["doc_id"], "sent_id": i, "sentence": s,
             "n_words": len(s.split()), "SubLabel": row["SubLabel"]}
            for i, s in enumerate(sents)]


if __name__ == "__main__":
    report = {}
    for sp in SPLITS:
        t0 = time.time()
        df = read_csv(DATA_DIR / f"{sp}.csv")
        df = df[(df["Label"] == VIOLATION_LABEL) & ~df["SubLabel"].isin(EXCLUDE_SUBLABELS)]

        out = pd.DataFrame([r for _, art in df.iterrows() for r in article_to_rows(art)])
        too_short = out["n_words"] < MIN_WORDS
        too_long = out["n_words"] > MAX_WORDS
        kept = out[~too_short & ~too_long].reset_index(drop=True)
        write_csv(kept, DATA_DIR / f"{sp}_sentences.csv")

        report[sp] = {"articles": len(df), "sentences": len(out),
                      "dropped_short": int(too_short.sum()), "dropped_long": int(too_long.sum()),
                      "kept": len(kept), "median_words": int(kept["n_words"].median()),
                      "seconds": int(time.time() - t0)}
        print(sp, report[sp], flush=True)

    print("\n" + pd.DataFrame(report).T.to_string())
