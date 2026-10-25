"""Evaluate triggers (kept for the legacy command; now shares the Part 2 evaluator).

Run from server/:
    python -m src.ner_pipeline.evaluate_trigger                       # baseline trên datasets/test.jsonl
    python -m src.ner_pipeline.evaluate_trigger --data datasets/val.jsonl
    python -m src.ner_pipeline.evaluate_trigger --pred datasets/processed/test_pred.jsonl

Data is a gold .jsonl file created by data_pipeline/step7_export_dataset.py; trigger_test.csv
is no longer used. Results include Trigger F1, Argument F1, Relation F1, and Event Exact Match.
"""
import argparse

from ..event_pipeline.evaluate import main as evaluate_main


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="datasets/test.jsonl", help="file gold .jsonl")
    ap.add_argument("--pred", help="file dự đoán .jsonl; bỏ trống thì chấm baseline luật")
    ap.add_argument("--errors", type=int, default=20, help="in N lỗi trigger đầu tiên")
    args = ap.parse_args()
    argv = ["--gold", args.data, "--errors", str(args.errors)]
    argv += ["--pred", args.pred] if args.pred else ["--baseline"]
    evaluate_main(argv)


if __name__ == "__main__":
    main()
