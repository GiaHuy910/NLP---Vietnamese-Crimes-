"""Evaluate Part 2: Trigger F1, Argument F1, Relation F1, and Event Exact Match.

Run from the server/ directory:

    # Evaluate the rule baseline on test (entities are taken from gold).
    python -m src.event_pipeline.evaluate --gold datasets/test.jsonl --baseline

    # Evaluate a model prediction file (same JSONL format, including ann_id).
    python -m src.event_pipeline.evaluate --gold datasets/test.jsonl --pred datasets/processed/test_pred.jsonl

Use --errors 30 to print the first 30 trigger errors and --save-json to save results.
"""
import argparse
import json
from pathlib import Path

from .baseline import predict_row
from .data import load_jsonl, save_jsonl, validate
from .metrics import error_examples, evaluate, format_report


def main(argv=None):
    ap = argparse.ArgumentParser(description="Đánh giá trích xuất sự kiện (luồng 2)")
    ap.add_argument("--gold", required=True, help="file gold .jsonl (vd datasets/test.jsonl)")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--pred", help="file dự đoán .jsonl")
    src.add_argument("--baseline", action="store_true", help="tự chạy baseline luật rồi chấm")
    ap.add_argument("--save-pred", help="lưu dự đoán của baseline ra file .jsonl")
    ap.add_argument("--save-json", help="lưu kết quả đánh giá ra file .json")
    ap.add_argument("--errors", type=int, default=0, help="in N lỗi trigger đầu tiên")
    args = ap.parse_args(argv)

    gold = load_jsonl(args.gold)
    problems = validate(gold, "gold")
    if problems:
        print(f"Cảnh báo: {len(problems)} lỗi trong file gold, ví dụ:")
        print("\n".join("  " + p for p in problems[:10]))

    if args.baseline:
        pred = [predict_row(r) for r in gold]
        title = f"BASELINE LUẬT - {Path(args.gold).name}"
        if args.save_pred:
            save_jsonl(pred, args.save_pred)
    else:
        pred = load_jsonl(args.pred)
        problems = validate(pred, "pred")
        if problems:
            print(f"Cảnh báo: {len(problems)} lỗi trong file dự đoán, ví dụ:")
            print("\n".join("  " + p for p in problems[:10]))
        title = f"{Path(args.pred).name} vs {Path(args.gold).name}"

    res = evaluate(gold, pred)
    print(format_report(res, title))

    if args.errors:
        counts, examples = error_examples(gold, pred, args.errors)
        print(f"\nLỗi trigger: {dict(counts)}")
        for aid, kind, text, lab, sent in examples:
            print(f"  [{aid}] {kind:16s} '{text}' ({lab}) | {sent[:110]}")

    if args.save_json:
        Path(args.save_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.save_json).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nĐã lưu {args.save_json}")


if __name__ == "__main__":
    main()
