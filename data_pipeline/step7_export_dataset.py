import argparse
import json
import random

import pandas as pd

from config import PROJECT_DIR, SEED

OUT_DIR = PROJECT_DIR / "dataset"


def get_result(task):
    anns = [a for a in task.get("annotations", []) if not a.get("was_cancelled")]
    if anns:
        return anns[-1]["result"], "gold"
    preds = task.get("predictions", [])
    return (preds[-1]["result"], "silver") if preds else ([], "none")


def convert(task):
    s = task["data"]["sentence"]
    res, source = get_result(task)
    spans = {r["id"]: r for r in res if r["type"] == "labels"}
    item = lambda r: {"id": r["id"], "start": r["value"]["start"], "end": r["value"]["end"],
                      "text": s[r["value"]["start"]:r["value"]["end"]], "label": r["value"]["labels"][0]}
    ents = sorted((item(r) for r in spans.values() if r["from_name"] == "entity"), key=lambda x: x["start"])
    trigs = sorted((item(r) for r in spans.values() if r["from_name"] == "trigger"), key=lambda x: x["start"])
    rels = []
    for r in res:
        if r["type"] != "relation" or not r.get("labels"):
            continue
        a, b = spans.get(r["from_id"]), spans.get(r["to_id"])
        if not a or not b:
            continue
        if a["from_name"] != "trigger":          # nối ngược -> đảo lại cho đúng chiều trigger -> thực thể
            a, b = b, a
        if a["from_name"] == "trigger" and b["from_name"] == "entity":
            rels.append({"trigger_id": a["id"], "arg_id": b["id"], "role": r["labels"][0]})
    d = task["data"]
    return {"ann_id": d["ann_id"], "doc_id": d["doc_id"], "SubLabel": d["SubLabel"], "source": source,
            "sentence": s, "entities": ents, "triggers": trigs, "relations": rels}


def write(rows, name):
    with open(OUT_DIR / f"{name}.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    ner = pd.DataFrame({"sentence": [r["sentence"] for r in rows],
                        "entities": ["; ".join(f"{e['text']}|{e['label']}" for e in r["entities"]) for r in rows]})
    ner.to_csv(OUT_DIR / f"{name}_ner.csv", index=False, encoding="utf-8-sig")
    n = lambda k: sum(len(r[k]) for r in rows)
    src = pd.Series([r["source"] for r in rows]).value_counts().to_dict()
    print(f"{name:6s}: {len(rows)} câu {src} | {n('entities')} thực thể, {n('triggers')} trigger, "
          f"{n('relations')} quan hệ -> {name}.jsonl, {name}_ner.csv")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("name", help="train / test / ...")
    ap.add_argument("--val", type=int, default=0, help="số câu tách ra làm val (chia đều theo SubLabel)")
    ap.add_argument("--gold-only", action="store_true", help="chỉ lấy câu đã gán tay")
    args = ap.parse_args()

    OUT_DIR.mkdir(exist_ok=True)
    tasks = json.loads(open(args.file, encoding="utf-8").read())
    rows = [convert(t) for t in tasks]
    if args.gold_only:
        rows = [r for r in rows if r["source"] == "gold"]
    if args.val:
        by_group = {}
        for r in rows:
            by_group.setdefault(r["SubLabel"], []).append(r)
        rng = random.Random(SEED)
        val_ids = set()
        for g in by_group.values():
            val_ids |= {r["ann_id"] for r in rng.sample(g, min(len(g), args.val // len(by_group)))}
        write([r for r in rows if r["ann_id"] not in val_ids], args.name)
        write([r for r in rows if r["ann_id"] in val_ids], "val")
    else:
        write(rows, args.name)
