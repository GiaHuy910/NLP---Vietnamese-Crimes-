import json
import sys

import pandas as pd

from config import ANNOTATION_DIR, SPLITS
from rules import find_entities, find_triggers

MODEL_VERSION = "rules_v1"


def to_result(span, from_name, idx):
    return {"id": f"{from_name[0]}{idx}", "from_name": from_name, "to_name": "text", "type": "labels",
            "value": {"start": span["start"], "end": span["end"], "text": span["text"],
                      "labels": [span["label"]]}}


def make_task(row, prelabel):
    s = row["sentence"]
    task = {"data": {"ann_id": row["ann_id"], "doc_id": str(row["doc_id"]), "sent_id": int(row["sent_id"]),
                     "SubLabel": row["SubLabel"], "sentence": s,
                     "double_annotate": bool(row["double_annotate"])}}
    if prelabel:
        ents = find_entities(s)
        trigs = find_triggers(s, ents)
        for sp in ents + trigs:                           # kiểm tra vị trí khớp chữ
            assert s[sp["start"]:sp["end"]] == sp["text"], (row["ann_id"], sp)
        result = ([to_result(e, "entity", i) for i, e in enumerate(ents)]
                  + [to_result(t, "trigger", i) for i, t in enumerate(trigs)])
        task["predictions"] = [{"model_version": MODEL_VERSION, "result": result}]
    return task


if __name__ == "__main__":
    splits = sys.argv[1:] or SPLITS                       # vd: python step6_to_labelstudio.py train
    for sp in splits:
        df = pd.read_excel(ANNOTATION_DIR / f"{sp}_to_annotate.xlsx", keep_default_na=False)
        prelabel = sp == "train"
        tasks = []
        for i, row in df.iterrows():
            tasks.append(make_task(row, prelabel))
            if prelabel and (i + 1) % 100 == 0:
                print(f"  {sp}: {i + 1}/{len(df)}", flush=True)
        out = ANNOTATION_DIR / f"{sp}_tasks.json"
        out.write_text(json.dumps(tasks, ensure_ascii=False, indent=1), encoding="utf-8")

        msg = f"{sp}: {len(tasks)} câu -> {out.name}"
        if prelabel:
            res = [r for t in tasks for r in t["predictions"][0]["result"]]
            n_ent = sum(r["from_name"] == "entity" for r in res)
            n_trg = sum(r["from_name"] == "trigger" for r in res)
            n_sent_trg = sum(any(r["from_name"] == "trigger" for r in t["predictions"][0]["result"])
                             for t in tasks)
            msg += f" | gán sẵn {n_ent} thực thể, {n_trg} trigger ({n_sent_trg} câu có trigger)"
        print(msg)
