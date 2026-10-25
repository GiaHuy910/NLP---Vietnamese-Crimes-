import random
import time
from collections import Counter

import pandas as pd
from underthesea import pos_tag

from config import DATA_DIR, NO_VIOLATION_SUBLABEL, PROJECT_DIR, SEED, read_csv
from step4_split_sentences import split_sentences

OUT_DIR = PROJECT_DIR / "analysis"
N_PER_GROUP = 5000      # ~2-3 phút cho 5 nhóm; tăng nếu muốn số liệu ổn định hơn
MIN_PCT = 0.3           # bỏ động từ xuất hiện < 0.3% số câu của nhóm
TOP_K = 40
N_EXAMPLES = 2
REF = "Tin thường (Khác)"


def reference_sentences(n, seed):
    """Câu từ tin KHÔNG vi phạm, làm nền so sánh."""
    arts = read_csv(DATA_DIR / "train.csv")
    arts = arts[arts["SubLabel"] == NO_VIOLATION_SUBLABEL].sample(frac=1, random_state=seed)
    sents = []
    for text in arts["Content"]:
        sents.extend(s for s in split_sentences(text) if 5 <= len(s.split()) <= 100)
        if len(sents) >= n * 2:
            break
    return random.Random(seed).sample(sents, min(n, len(sents)))


def verbs_of(sentence):
    return {w.lower() for w, tag in pos_tag(sentence) if tag == "V"}


if __name__ == "__main__":
    t0 = time.time()
    sents = read_csv(DATA_DIR / "train_sentences.csv")
    groups = {g: d["sentence"].sample(min(N_PER_GROUP, len(d)), random_state=SEED).tolist()
              for g, d in sents.groupby("SubLabel")}
    groups[REF] = reference_sentences(N_PER_GROUP, SEED)

    pct, examples = {}, {}
    for g, ss in groups.items():
        counter = Counter()
        for s in ss:
            for v in verbs_of(s):
                counter[v] += 1
                examples.setdefault((g, v), [])
                if len(examples[(g, v)]) < N_EXAMPLES:
                    examples[(g, v)].append(s)
        pct[g] = {v: c / len(ss) * 100 for v, c in counter.items()}
        print(f"{g}: {len(ss)} câu, {len(counter)} động từ ({time.time() - t0:.0f}s)", flush=True)

    table = pd.DataFrame(pct).fillna(0).round(2)
    crime_groups = [g for g in groups if g != REF]
    table["lift_max"] = (table[crime_groups].max(axis=1) / (table[REF] + 0.1)).round(1)

    OUT_DIR.mkdir(exist_ok=True)
    out_path = OUT_DIR / "trigger_candidates.xlsx"
    with pd.ExcelWriter(out_path) as xw:
        overall = table[table[crime_groups].max(axis=1) >= MIN_PCT].sort_values("lift_max", ascending=False)
        overall.head(150).to_excel(xw, sheet_name="tong_hop")
        for g in crime_groups:
            t = table[table[g] >= MIN_PCT].copy()
            t["lift"] = (t[g] / (t[REF] + 0.1)).round(1)
            t = t.sort_values("lift", ascending=False).head(TOP_K)
            t = t[[g, REF, "lift"]].rename(columns={g: "pct_nhom", REF: "pct_tin_thuong"})
            t["vi_du"] = [" || ".join(examples.get((g, v), [])) for v in t.index]
            t.to_excel(xw, sheet_name=g[:31].replace("/", "-"))

            print(f"\n=== {g}: top 15 (động từ | % câu trong nhóm | % tin thường | lift)")
            for v, r in t.head(15).iterrows():
                print(f"   {v:22s} {r['pct_nhom']:6.2f}%  {r['pct_tin_thuong']:6.2f}%  x{r['lift']}")

    print(f"\nĐã ghi {out_path}  ({time.time() - t0:.0f}s)")
