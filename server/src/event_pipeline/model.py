"""PhoBERT models for Part 2: Trigger -> Argument -> Relation.

Two separately trained models:
1. Trigger: BIO-tag underthesea-segmented words for 8 event types.
2. Argument: classify each trigger/entity pair in a sentence into one of 10 roles or NONE.
   The input marks the trigger with <t> </t>, the entity with <e> </e>, and prepends event/entity
   type tokens. At inference, only roles allowed for the entity label (ROLE_TYPES) are considered.

Entities come from the input file: by default, gold entities are used to evaluate Part 2 in isolation.
Pass --entities to use entities predicted by the Part 1 NER model for a combined evaluation.

Run from server/ (a GPU is recommended, e.g. a Colab T4):
    python -m src.event_pipeline.model train --task all --epochs 15
    python -m src.event_pipeline.model predict --split test
    python -m src.event_pipeline.evaluate --gold datasets/test.jsonl --pred datasets/processed/test_event_pred.jsonl
"""
import argparse
import json
import random
import re
from pathlib import Path

from .data import load_jsonl, save_jsonl
from .metrics import evaluate
from .schema import EVENT_TYPES, ROLE_TYPES, ROLES, ENTITY_TYPES

SERVER_DIR = Path(__file__).resolve().parents[2]
DATASET_DIR = SERVER_DIR / "datasets"
MODEL_ROOT = SERVER_DIR / "models"
TRIGGER_DIR = MODEL_ROOT / "event_trigger"
ARGUMENT_DIR = MODEL_ROOT / "event_argument"

TRIGGER_LABELS = ["O"] + [f"{p}-{t}" for t in EVENT_TYPES for p in ("B", "I")]
ARG_LABELS = ["NONE"] + list(ROLES)
MARKERS = ["<t>", "</t>", "<e>", "</e>"]
TYPE_TOKENS = [f"<{x}>" for x in EVENT_TYPES + ENTITY_TYPES]


# ---------------------------------------------------------------- word segmentation
_SYL = re.compile(r"\w+|[^\w\s]")


def _syllables(sentence):
    return [(m.start(), m.end()) for m in _SYL.finditer(sentence)]


def segment(sentence):
    """Return word (start, end) spans; use underthesea or fall back to syllable segmentation."""
    syl = _syllables(sentence)
    try:
        from underthesea import word_tokenize
        words = word_tokenize(sentence)
    except Exception:
        return syl
    spans, i = [], 0
    for w in words:
        n = len(_SYL.findall(w))
        if n == 0:
            continue
        if i + n > len(syl):                         # On mismatch, fall back to syllables.
            return syl
        spans.append((syl[i][0], syl[i + n - 1][1]))
        i += n
    return spans + syl[i:]


def split_at(spans, cuts):
    """Split words at boundaries so trigger/entity spans align with word boundaries."""
    cuts = sorted(set(cuts))
    out = []
    for a, b in spans:
        pos = [a] + [c for c in cuts if a < c < b] + [b]
        for x, y in zip(pos, pos[1:]):
            out.append((x, y))
    return out


def word_text(sentence, span):
    return sentence[span[0]:span[1]].strip().replace(" ", "_") or "_"


# ---------------------------------------------------------------- encoding
def encode_words(tokenizer, words, max_length=256):
    """Convert words to input_ids and word_ids (word index per subword, None for special tokens)."""
    ids, wids = [], []
    for i, w in enumerate(words):
        pieces = tokenizer.convert_tokens_to_ids(tokenizer.tokenize(w)) or [tokenizer.unk_token_id]
        ids.extend(pieces)
        wids.extend([i] * len(pieces))
    ids, wids = ids[:max_length - 2], wids[:max_length - 2]
    return [tokenizer.cls_token_id] + ids + [tokenizer.sep_token_id], [None] + wids + [None]


def _batches(items, size, shuffle, seed=0):
    idx = list(range(len(items)))
    if shuffle:
        random.Random(seed).shuffle(idx)
    for i in range(0, len(idx), size):
        yield [items[j] for j in idx[i:i + size]]


def _pad(torch, seqs, value):
    n = max(len(s) for s in seqs)
    return torch.tensor([s + [value] * (n - len(s)) for s in seqs])


def _deps():
    try:
        import torch
        import transformers  # noqa: F401
    except ImportError as exc:
        raise SystemExit("Thiếu torch/transformers: pip install -r requirements-ner.txt") from exc
    return torch


# ---------------------------------------------------------------- trigger
def trigger_examples(rows):
    """Convert a gold sentence to words, word-level BIO labels, and word spans."""
    out = []
    for r in rows:
        s = r["sentence"]
        trigs = r.get("triggers", [])
        spans = split_at(segment(s), [p for t in trigs for p in (t["start"], t["end"])])
        labels = ["O"] * len(spans)
        for t in trigs:
            inside = [i for i, (a, b) in enumerate(spans) if a >= t["start"] and b <= t["end"]]
            for k, i in enumerate(inside):
                labels[i] = ("B-" if k == 0 else "I-") + t["label"]
        out.append({"words": [word_text(s, sp) for sp in spans], "labels": labels, "spans": spans})
    return out


def decode_bio(sentence, spans, labels):
    trigs, cur = [], None
    for (a, b), lab in zip(spans, labels):
        if lab == "O":
            cur = None
            continue
        pref, typ = lab.split("-", 1)
        if pref == "I" and cur is not None and cur["label"] == typ:
            cur["end"] = b
        else:
            cur = {"start": a, "end": b, "label": typ}
            trigs.append(cur)
    return [dict(t, id=f"t{i}", text=sentence[t["start"]:t["end"]]) for i, t in enumerate(trigs)]


def predict_triggers(model, tokenizer, rows, device, max_length=256, batch_size=16):
    torch = _deps()
    model.eval()
    results = []
    for batch in _batches(rows, batch_size, shuffle=False):
        segs = [segment(r["sentence"]) for r in batch]
        enc = [encode_words(tokenizer, [word_text(r["sentence"], sp) for sp in sg], max_length)
               for r, sg in zip(batch, segs)]
        ids = _pad(torch, [e[0] for e in enc], tokenizer.pad_token_id).to(device)
        mask = (ids != tokenizer.pad_token_id).long()
        with torch.no_grad():
            logits = model(input_ids=ids, attention_mask=mask).logits.argmax(-1).tolist()
        for r, sg, (_, wids), pred in zip(batch, segs, enc, logits):
            labels = ["O"] * len(sg)
            seen = set()
            for pos, w in enumerate(wids):
                if w is not None and w not in seen:
                    seen.add(w)
                    labels[w] = TRIGGER_LABELS[pred[pos]]
            results.append(decode_bio(r["sentence"], sg, labels))
    return results


def train_trigger(train_rows, val_rows, args):
    torch = _deps()
    from transformers import AutoModelForTokenClassification, AutoTokenizer
    torch.manual_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tok = AutoTokenizer.from_pretrained(args.model_name)
    model = AutoModelForTokenClassification.from_pretrained(
        args.model_name, num_labels=len(TRIGGER_LABELS),
        id2label=dict(enumerate(TRIGGER_LABELS)), label2id={l: i for i, l in enumerate(TRIGGER_LABELS)},
    ).to(device)
    lab2id = {l: i for i, l in enumerate(TRIGGER_LABELS)}
    data = []
    for ex in trigger_examples(train_rows):
        ids, wids = encode_words(tok, ex["words"], args.max_length)
        y, seen = [], set()
        for w in wids:
            if w is None or w in seen:
                y.append(-100)
            else:
                seen.add(w)
                y.append(lab2id[ex["labels"][w]])
        data.append((ids, y))
    # Reduce the influence of O, the majority class.
    weights = torch.ones(len(TRIGGER_LABELS))
    weights[0] = args.o_weight
    loss_fn = torch.nn.CrossEntropyLoss(weight=weights.to(device), ignore_index=-100)
    return _fit(model, tok, data, loss_fn, args, device, TRIGGER_DIR,
                score_fn=lambda: _trigger_val_f1(model, tok, val_rows, device, args), token_level=True)


def _trigger_val_f1(model, tok, rows, device, args):
    preds = predict_triggers(model, tok, rows, device, args.max_length)
    pred_rows = [dict(ann_id=r["ann_id"], sentence=r["sentence"], entities=[], triggers=t, relations=[])
                 for r, t in zip(rows, preds)]
    return evaluate(rows, pred_rows)["trigger_classification"]["f1"]


# ---------------------------------------------------------------- argument
def pair_words(sentence, base_spans, trigger, entity):
    """Build marked input words for one sentence and trigger/entity pair."""
    spans = split_at(base_spans, [trigger["start"], trigger["end"], entity["start"], entity["end"]])
    words = [f"<{trigger['label']}>", f"<{entity['label']}>"]
    for a, b in spans:
        if a == trigger["start"]:
            words.append("<t>")
        if a == entity["start"]:
            words.append("<e>")
        words.append(word_text(sentence, (a, b)))
        if b == entity["end"]:
            words.append("</e>")
        if b == trigger["end"]:
            words.append("</t>")
    return words


def argument_pairs(rows, use_gold_relations=True):
    """Return all trigger/entity pairs with gold roles (NONE when unlinked)."""
    out = []
    for r in rows:
        s = r["sentence"]
        base = segment(s)
        gold = {(x["trigger_id"], x["arg_id"]): x["role"] for x in r.get("relations", [])} if use_gold_relations else {}
        for t in r.get("triggers", []):
            for e in r.get("entities", []):
                if not (e["end"] <= t["start"] or e["start"] >= t["end"]):
                    continue                             # Exclude entities that overlap the trigger.
                out.append({"row": r["ann_id"], "trigger": t, "entity": e,
                            "words": pair_words(s, base, t, e),
                            "role": gold.get((t["id"], e["id"]), "NONE")})
    return out


def _role_mask(torch, entity_label):
    return torch.tensor([0.0] + [0.0 if entity_label in ROLE_TYPES[r] else float("-inf") for r in ROLES])


def classify_pairs(model, tok, pairs, device, max_length=256, batch_size=32):
    torch = _deps()
    model.eval()
    out = []
    for batch in _batches(pairs, batch_size, shuffle=False):
        enc = [encode_words(tok, p["words"], max_length)[0] for p in batch]
        ids = _pad(torch, enc, tok.pad_token_id).to(device)
        mask = (ids != tok.pad_token_id).long()
        with torch.no_grad():
            logits = model(input_ids=ids, attention_mask=mask).logits.cpu()
        for p, lg in zip(batch, logits):
            out.append(ARG_LABELS[int((lg + _role_mask(torch, p["entity"]["label"])).argmax())])
    return out


def train_argument(train_rows, val_rows, args):
    torch = _deps()
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    torch.manual_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tok = AutoTokenizer.from_pretrained(args.model_name)
    tok.add_special_tokens({"additional_special_tokens": MARKERS + TYPE_TOKENS})
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model_name, num_labels=len(ARG_LABELS),
        id2label=dict(enumerate(ARG_LABELS)), label2id={l: i for i, l in enumerate(ARG_LABELS)},
    )
    model.resize_token_embeddings(len(tok))
    model.to(device)
    lab2id = {l: i for i, l in enumerate(ARG_LABELS)}
    data = [(encode_words(tok, p["words"], args.max_length)[0], lab2id[p["role"]])
            for p in argument_pairs(train_rows)]
    weights = torch.ones(len(ARG_LABELS))
    weights[0] = args.none_weight
    loss_fn = torch.nn.CrossEntropyLoss(weight=weights.to(device))
    val_pairs = argument_pairs(val_rows)
    return _fit(model, tok, data, loss_fn, args, device, ARGUMENT_DIR,
                score_fn=lambda: _argument_val_f1(model, tok, val_rows, val_pairs, device, args),
                token_level=False)


def _relations_from(pairs, roles):
    by_row = {}
    for p, role in zip(pairs, roles):
        if role != "NONE":
            by_row.setdefault(p["row"], []).append(
                {"trigger_id": p["trigger"]["id"], "arg_id": p["entity"]["id"], "role": role})
    return by_row


def _argument_val_f1(model, tok, rows, pairs, device, args):
    """Compute validation Relation F1 with gold triggers to isolate role-linking performance."""
    rel = _relations_from(pairs, classify_pairs(model, tok, pairs, device, args.max_length))
    pred = [dict(r, relations=rel.get(r["ann_id"], [])) for r in rows]
    return evaluate(rows, pred)["relation"]["f1"]


# ---------------------------------------------------------------- shared training loop
def _fit(model, tok, data, loss_fn, args, device, out_dir, score_fn, token_level):
    torch = _deps()
    from transformers import get_linear_schedule_with_warmup
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    steps = max(1, (len(data) + args.batch_size - 1) // args.batch_size) * args.epochs
    sched = get_linear_schedule_with_warmup(opt, int(0.1 * steps), steps)
    best, history = -1.0, []
    for epoch in range(1, args.epochs + 1):
        model.train()
        total = 0.0
        for batch in _batches(data, args.batch_size, shuffle=True, seed=args.seed + epoch):
            ids = _pad(torch, [b[0] for b in batch], tok.pad_token_id).to(device)
            mask = (ids != tok.pad_token_id).long()
            logits = model(input_ids=ids, attention_mask=mask).logits
            if token_level:
                y = _pad(torch, [b[1] for b in batch], -100).to(device)
                loss = loss_fn(logits.reshape(-1, logits.size(-1)), y.reshape(-1))
            else:
                y = torch.tensor([b[1] for b in batch], device=device)
                loss = loss_fn(logits, y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            opt.zero_grad()
            total += loss.item() * len(batch)
        score = score_fn()
        history.append({"epoch": epoch, "train_loss": total / len(data), "val_f1": score})
        print(f"[{out_dir.name}] epoch {epoch}/{args.epochs} loss={total / len(data):.4f} val_f1={score:.4f}",
              flush=True)
        if score > best:
            best = score
            out_dir.mkdir(parents=True, exist_ok=True)
            model.save_pretrained(out_dir)
            tok.save_pretrained(out_dir)
    (out_dir / "train_history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
    print(f"[{out_dir.name}] best val_f1={best:.4f} -> {out_dir}")
    return best


# ---------------------------------------------------------------- full prediction
def predict(rows, entity_rows=None, max_length=256, trigger_dir=TRIGGER_DIR, argument_dir=ARGUMENT_DIR,
            trigger_source="model"):
    """Predict triggers and roles for Part 2 and return records in the same JSONL format.

    trigger_source: "model" (PhoBERT trigger model), "rules" (rule triggers with model role linking),
    or "gold" (gold triggers to evaluate role-linking performance in isolation).
    """
    torch = _deps()
    from transformers import AutoModelForSequenceClassification, AutoModelForTokenClassification, AutoTokenizer
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    atok = AutoTokenizer.from_pretrained(argument_dir)
    amodel = AutoModelForSequenceClassification.from_pretrained(argument_dir).to(device)
    ents_by_id = {r["ann_id"]: r.get("entities", []) for r in (entity_rows or rows)}

    if trigger_source == "model":
        ttok = AutoTokenizer.from_pretrained(trigger_dir)
        tmodel = AutoModelForTokenClassification.from_pretrained(trigger_dir).to(device)
        trig_preds = predict_triggers(tmodel, ttok, rows, device, max_length)
    elif trigger_source == "rules":
        from .baseline import find_triggers
        trig_preds = [find_triggers(r["sentence"], ents_by_id.get(r["ann_id"], [])) for r in rows]
    else:
        trig_preds = [[dict(t) for t in r.get("triggers", [])] for r in rows]
    out = [{"ann_id": r["ann_id"], "sentence": r["sentence"], "entities": ents_by_id.get(r["ann_id"], []),
            "triggers": t, "relations": []} for r, t in zip(rows, trig_preds)]
    pairs = argument_pairs(out, use_gold_relations=False)
    rel = _relations_from(pairs, classify_pairs(amodel, atok, pairs, device, max_length))
    for r in out:
        r["relations"] = rel.get(r["ann_id"], [])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="PhoBERT cho trigger và argument (luồng 2)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("train")
    t.add_argument("--task", choices=["trigger", "argument", "all"], default="all")
    t.add_argument("--model-name", default="vinai/phobert-base-v2")
    t.add_argument("--epochs", type=int, default=15)
    t.add_argument("--batch-size", type=int, default=16)
    t.add_argument("--lr", type=float, default=5e-5)
    t.add_argument("--max-length", type=int, default=256)
    t.add_argument("--o-weight", type=float, default=0.3, help="trọng số nhãn O khi train trigger")
    t.add_argument("--none-weight", type=float, default=0.5, help="trọng số nhãn NONE khi train argument")
    t.add_argument("--seed", type=int, default=42)
    p = sub.add_parser("predict")
    p.add_argument("--split", default="test", help="train / val / test (đọc datasets/{split}.jsonl)")
    p.add_argument("--entities", help="file jsonl thực thể dự đoán của luồng 1 (mặc định: thực thể gold)")
    p.add_argument("--out", help="mặc định datasets/processed/{split}_event_pred.jsonl")
    p.add_argument("--max-length", type=int, default=256)
    p.add_argument("--trigger-source", choices=["model", "rules", "gold"], default="model",
                   help="nguồn trigger: mô hình PhoBERT, baseline luật, hoặc gold")
    args = ap.parse_args(argv)

    if args.cmd == "train":
        train_rows = load_jsonl(DATASET_DIR / "train.jsonl")
        val_rows = load_jsonl(DATASET_DIR / "val.jsonl")
        if args.task in ("trigger", "all"):
            train_trigger(train_rows, val_rows, args)
        if args.task in ("argument", "all"):
            train_argument(train_rows, val_rows, args)
        return

    rows = load_jsonl(DATASET_DIR / f"{args.split}.jsonl")
    ent_rows = load_jsonl(args.entities) if args.entities else None
    pred = predict(rows, ent_rows, args.max_length, trigger_source=args.trigger_source)
    suffix = "" if args.trigger_source == "model" else f"_{args.trigger_source}"
    out = Path(args.out) if args.out else DATASET_DIR / "processed" / f"{args.split}_event_pred{suffix}.jsonl"
    save_jsonl(pred, out)
    print(f"Đã lưu {len(pred)} câu dự đoán -> {out}")


if __name__ == "__main__":
    main()
