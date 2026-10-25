"""Đánh giá trigger (giữ lại cho lệnh cũ, nay dùng chung bộ chấm của luồng 2).

Chạy trong server/:
    python -m src.ner_pipeline.evaluate_trigger                       # baseline trên datasets/test.jsonl
    python -m src.ner_pipeline.evaluate_trigger --data datasets/val.jsonl
    python -m src.ner_pipeline.evaluate_trigger --pred datasets/processed/test_pred.jsonl

Dữ liệu là file .jsonl gold (do data_pipeline/step7_export_dataset.py tạo), không còn dùng
trigger_test.csv. Kết quả gồm Trigger F1 và cả Argument F1, Relation F1, Event Exact Match.
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
