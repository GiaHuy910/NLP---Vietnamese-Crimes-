"""Bước 3 - Thu hẹp phạm vi: bỏ các nhóm trong EXCLUDE_SUBLABELS (config.py).

Đầu vào/ra: corpus news/{train,val,test}.csv   (GHI ĐÈ cùng tên)

Lý do bỏ "Vi phạm Giao thông": chỉ ~2% số bài vi phạm, quá ít để huấn luyện
và đánh giá tin cậy theo từng loại sự kiện.

Cách dùng:
    python step3_apply_scope.py            # CHỈ XEM TRƯỚC, không sửa file nào
    python step3_apply_scope.py --apply    # THỰC HIỆN
Chạy --apply nhiều lần vẫn an toàn. Muốn lấy lại bản đầy đủ: chạy lại bước 2.
"""
import sys

import pandas as pd

from config import DATA_DIR, EXCLUDE_SUBLABELS, SPLITS, read_csv, write_csv

N_EXAMPLES = 3

if __name__ == "__main__":
    apply = "--apply" in sys.argv
    report = {}
    for sp in SPLITS:
        path = DATA_DIR / f"{sp}.csv"
        df = read_csv(path)
        drop = df["SubLabel"].isin(EXCLUDE_SUBLABELS)
        report[sp] = {"articles": len(df), "remove": int(drop.sum()), "keep": int((~drop).sum())}

        print(f"\n== {sp}: {'đã bỏ' if apply else 'sẽ bỏ'} {int(drop.sum())} / {len(df)} bài")
        for _, r in df[drop].head(N_EXAMPLES).iterrows():
            print(f"   - {r['doc_id']}: {r['Summarize'][:90]}")
        if apply:
            write_csv(df[~drop], path)

    print("\n" + pd.DataFrame(report).T.to_string())
    if not apply:
        print("\nChưa sửa file nào. Chạy lại với --apply để thực hiện.")
