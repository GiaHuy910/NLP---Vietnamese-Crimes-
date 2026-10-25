"""Part 2 evaluation metrics (exact character-offset matching, micro-average).

1. Trigger Identification (Trigger-I): exact trigger offsets (start, end), ignoring event type.
2. Trigger Classification (Trigger-C): exact trigger offsets and event type; this is the main Trigger F1.
3. Argument Identification (Argument F1): exact trigger (offsets + type) and linked entity offsets,
   ignoring the role.
4. Relation / Argument Classification (Relation F1): the conditions in (3), including the role.
5. Event Exact Match: the trigger (offsets + type) and complete argument set (offsets + roles) match gold.

Each metric reports Precision, Recall, and F1. Trigger-C and Relation also report scores by type/role.
"""
from collections import Counter, defaultdict

from .data import events_of


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": p, "recall": r, "f1": f, "tp": tp, "fp": fp, "fn": fn, "support": tp + fn}


def _score(gold, pred):
    return prf(len(gold & pred), len(pred - gold), len(gold - pred))


def _by_key(gold, pred, key):
    keys = sorted({key(x) for x in gold | pred})
    return {k: _score({x for x in gold if key(x) == k}, {x for x in pred if key(x) == k}) for k in keys}


def collect(rows):
    """Convert sentence records into sets of tuples for exact matching."""
    sets = defaultdict(set)
    for r in rows:
        aid = r["ann_id"]
        for ev in events_of(r):
            ts, te, tt = ev["trigger"]
            sets["trig_i"].add((aid, ts, te))
            sets["trig_c"].add((aid, ts, te, tt))
            for as_, ae, role in ev["args"]:
                sets["arg_i"].add((aid, ts, te, tt, as_, ae))
                sets["rel"].add((aid, ts, te, tt, as_, ae, role))
            sets["event"].add((aid, ts, te, tt, frozenset(ev["args"])))
    return sets


def evaluate(gold_rows, pred_rows):
    gold_ids = {r["ann_id"] for r in gold_rows}
    pred_by_id = {r["ann_id"]: r for r in pred_rows}
    missing = gold_ids - set(pred_by_id)
    extra = set(pred_by_id) - gold_ids
    if missing:
        raise ValueError(f"Thiếu dự đoán cho {len(missing)} câu, ví dụ: {sorted(missing)[:5]}")
    pred_rows = [pred_by_id[r["ann_id"]] for r in gold_rows]     # Drop extra rows and preserve gold order.

    g, p = collect(gold_rows), collect(pred_rows)
    return {
        "n_sentences": len(gold_rows),
        "ignored_extra_predictions": len(extra),
        "trigger_identification": _score(g["trig_i"], p["trig_i"]),
        "trigger_classification": _score(g["trig_c"], p["trig_c"]),
        "argument_identification": _score(g["arg_i"], p["arg_i"]),
        "relation": _score(g["rel"], p["rel"]),
        "event_exact_match": _score(g["event"], p["event"]),
        "trigger_by_type": _by_key(g["trig_c"], p["trig_c"], key=lambda x: x[3]),
        "relation_by_role": _by_key(g["rel"], p["rel"], key=lambda x: x[6]),
    }


MAIN_METRICS = [
    ("trigger_identification", "Trigger Identification"),
    ("trigger_classification", "Trigger F1 (vị trí + loại)"),
    ("argument_identification", "Argument F1"),
    ("relation", "Relation F1 (+ vai trò)"),
    ("event_exact_match", "Event Exact Match"),
]


def format_report(res, title=""):
    lines = [f"===== {title} ({res['n_sentences']} câu) =====" if title else ""]
    lines.append(f"{'Chỉ số':30s} {'P':>7s} {'R':>7s} {'F1':>7s} {'TP':>5s} {'FP':>5s} {'FN':>5s}")
    for key, name in MAIN_METRICS:
        m = res[key]
        lines.append(f"{name:30s} {m['precision']:7.4f} {m['recall']:7.4f} {m['f1']:7.4f} "
                     f"{m['tp']:5d} {m['fp']:5d} {m['fn']:5d}")
    for block, label in (("trigger_by_type", "Trigger theo loại"), ("relation_by_role", "Relation theo vai trò")):
        lines.append(f"\n{label}:")
        for k, m in res[block].items():
            lines.append(f"  {k:28s} {m['precision']:7.4f} {m['recall']:7.4f} {m['f1']:7.4f}   gold={m['support']}")
    return "\n".join(lines)


def error_examples(gold_rows, pred_rows, limit=20):
    """List missed, extra, and misclassified triggers for error analysis."""
    pred_by_id = {r["ann_id"]: r for r in pred_rows}
    out = Counter()
    examples = []
    for gr in gold_rows:
        pr = pred_by_id.get(gr["ann_id"], {"triggers": []})
        s = gr["sentence"]
        gold = {(t["start"], t["end"]): t["label"] for t in gr["triggers"]}
        pred = {(t["start"], t["end"]): t["label"] for t in pr["triggers"]}
        for span, lab in gold.items():
            if span not in pred:
                kind = "bỏ sót"
            elif pred[span] != lab:
                kind = f"sai loại ({pred[span]})"
            else:
                continue
            out[kind.split(" (")[0]] += 1
            examples.append((gr["ann_id"], kind, s[span[0]:span[1]], lab, s))
        for span, lab in pred.items():
            if span not in gold:
                out["thừa"] += 1
                examples.append((gr["ann_id"], "thừa", s[span[0]:span[1]], lab, s))
    return out, examples[:limit]
