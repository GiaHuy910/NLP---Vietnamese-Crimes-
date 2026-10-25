import re
import unicodedata

import pandas as pd

from config import DATA_DIR, SPLITS, TEXT_COLS, write_csv

INVISIBLE = re.compile("[\u200b\ufeff\u00ad]")
SPACE_BEFORE_MARK = re.compile("\\s+(?=[\u0300-\u036f])")
COMBINING = re.compile("[\u0300-\u036f]")


def clean_text(s):
    if not isinstance(s, str):          # ô trống -> NaN
        return ""
    s = SPACE_BEFORE_MARK.sub("", s)    # gắn dấu về lại chữ đứng trước
    s = unicodedata.normalize("NFC", s) # chữ + dấu rời -> 1 ký tự dựng sẵn
    s = INVISIBLE.sub("", s)
    s = s.replace("\ufffd", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def count_issues(series):
    text = "".join(series.astype(str))
    return {"dau_roi": len(COMBINING.findall(text)),
            "ky_tu_an": len(INVISIBLE.findall(text)),
            "ky_tu_hong": text.count("\ufffd")}


if __name__ == "__main__":
    for sp in SPLITS:
        df = pd.read_csv(DATA_DIR / f"{sp}_cleaned_labeled.csv", encoding="utf-8")
        before = {col: count_issues(df[col]) for col in TEXT_COLS}
        for col in TEXT_COLS:
            df[col] = df[col].map(clean_text)
        after = {col: count_issues(df[col]) for col in TEXT_COLS}

        write_csv(df, DATA_DIR / f"{sp}_clean.csv")
        print(f"== {sp}: {len(df)} dòng")
        for col in TEXT_COLS:
            print(f"   {col:10s} trước: {before[col]}")
            print(f"   {col:10s} sau  : {after[col]}")
