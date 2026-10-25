import argparse
import json
import sys
from typing import Any
from pathlib import Path

from .baseline import RuleBasedNER
from .dataset import load_jsonl, prepare_dataset, prepare_predefined_splits
from .error_analysis import analyze_sentence, summarize
from .errors import NERPipelineError
from .metrics import score_spans, spans_from_record
from .paths import MODEL_DIR, PROCESSED_DIR, PREDICT_DIR
from .phobert import predict_records, predict_sentence, train


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Vietnamese crime NER pipeline"
    )

    commands = parser.add_subparsers(
        dest="command",
        required=True
    )

    prepare = commands.add_parser(
        "prepare",
        help="Validate, BIO-convert and split CSV.",
    )
    prepare.add_argument("--input", help="CSV nam trong server/datasets/.")
    prepare.add_argument("--seed", type=int, default=42)
    prepare.add_argument("--test-ratio", type=float, default=0.15)
    prepare.add_argument("--validation-ratio", type=float, default=0.15)
    prepare.add_argument(
        "--train-only",
        help="Optional CSV whose sentences must remain in train, never validation/test.",
    )

    prepare_splits = commands.add_parser(
        "prepare-splits",
        help="Validate pre-split train/validation/test CSV files without mixing them.",
    )
    prepare_splits.add_argument("--train", default="train.csv", help="Training CSV.")
    prepare_splits.add_argument(
        "--validation", default="valid.csv", help="Validation CSV."
    )
    prepare_splits.add_argument("--test", default="test.csv", help="Test CSV.")

    fitting = commands.add_parser(
        "train",
        help="Fine-tune PhoBERT token classifier.",
    )
    fitting.add_argument("--model-name", default="vinai/phobert-base-v2")
    fitting.add_argument("--epochs", type=int, default=3)
    fitting.add_argument("--batch-size", type=int, default=8)
    fitting.add_argument("--learning-rate", type=float, default=2e-5)
    fitting.add_argument("--max-length", type=int, default=256)
    fitting.add_argument("--seed", type=int, default=42)
    fitting.add_argument("--class-weight-power", type=float, default=0.5)
    fitting.add_argument(
        "--train-file",
        default="train.jsonl",
        help="File train trong server/datasets/processed/.",
    )
    fitting.add_argument(
        "--model-dir",
        default=str(MODEL_DIR),
        help="Thu muc luu checkpoint.",
    )
    
    baseline = commands.add_parser(
        "baseline",
        help="Evaluate rule-based NER without loading PhoBERT.",
    )

    evaluation = commands.add_parser(
        "evaluate",
        help="Evaluate baseline and PhoBERT on the same test split.",
    )
    evaluation.add_argument("--max-length", type=int, default=256)
    evaluation.add_argument(
        "--model-dir",
        default=str(MODEL_DIR),
        help="Thu muc checkpoint PhoBERT dung de danh gia.",
    )

    prediction = commands.add_parser(
        "predict",
        help="Predict entities in one sentence.",
    )
    prediction.add_argument(
        "--text",
        help="Input sentence; omitted for interactive input.",
    )
    prediction.add_argument("--max-length", type=int, default=256)

    # Add the batch-predict command.
    batch_prediction = commands.add_parser(
        "batch-predict",
        help="Du doan NER hang loat cho mot file JSONL va xuat Pseudo-label.",
    )
    batch_prediction.add_argument(
        "--input",
        required=True,
        help="Duong dan toi file JSONL chua du lieu tho (can truong 'sentence').",
    )
    batch_prediction.add_argument(
        "--output",
        default="pseudo_labels.jsonl",
        help="Ten file xuat ra (se duoc luu trong thu muc PREDICT_DIR).",
    )
    batch_prediction.add_argument("--max-length", type=int, default=256)
    batch_prediction.add_argument(
        "--model-dir",
        default=str(MODEL_DIR),
        help="Thu muc checkpoint PhoBERT dung de du doan.",
    )

    analysis = commands.add_parser(
        "analyze",
        help="Analyze PhoBERT errors on the held-out test split.",
    )
    analysis.add_argument("--max-length", type=int, default=256)
    analysis.add_argument(
        "--model-dir",
        default=str(MODEL_DIR),
        help="Thu muc checkpoint PhoBERT dung de phan tich loi.",
    )

    return parser


def _spans_for_baseline(
    records: list[dict[str, Any]],
    baseline: RuleBasedNER,
) -> list[list[tuple[int, int, str]]]:
    return [
        [
            (
                int(item["start"]),
                int(item["end"]),
                str(item["label"]),
            )
            for item in baseline.predict(str(record["sentence"]))
        ]
        for record in records
    ]


def _evaluation_payload(
    records: list[dict[str, Any]],
    predictions: list[list[tuple[int, int, str]]],
) -> dict[str, dict[str, float | int]]:
    gold = [spans_from_record(record) for record in records]
    return score_spans(gold, predictions)


def _run(args: argparse.Namespace) -> None:
    if args.command == "prepare":
        counts = prepare_dataset(
            args.input,
            seed=args.seed,
            test_ratio=args.test_ratio,
            validation_ratio=args.validation_ratio,
            train_only_path=args.train_only,
        )
        print(json.dumps(counts, ensure_ascii=False, indent=2))
        print(f"Da luu cac split trong: {PROCESSED_DIR}")
        return

    if args.command == "prepare-splits":
        counts = prepare_predefined_splits(
            args.train,
            args.validation,
            args.test,
        )
        print(json.dumps(counts, ensure_ascii=False, indent=2))
        print(f"Da luu cac split trong: {PROCESSED_DIR}")
        return

    if args.command == "train":
        train_records = load_jsonl(PROCESSED_DIR / args.train_file)
        validation_records = load_jsonl(PROCESSED_DIR / "validation.jsonl")
        model_path = train(
            train_records,
            validation_records,
            model_dir=Path(args.model_dir),
            model_name=args.model_name,
            epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.learning_rate,
            max_length=args.max_length,
            seed=args.seed,
            class_weight_power=args.class_weight_power,
        )
        print(f"Best checkpoint da luu tai: {model_path}")
        return

    if args.command == "baseline":
        records = load_jsonl(PROCESSED_DIR / "test.jsonl")
        baseline_spans = _spans_for_baseline(records, RuleBasedNER())

        print(
            json.dumps(
                {
                    "test_examples": len(records),
                    "baseline": _evaluation_payload(records, baseline_spans),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if args.command == "evaluate":
        records = load_jsonl(PROCESSED_DIR / "test.jsonl")
        baseline_spans = _spans_for_baseline(records, RuleBasedNER())
        phobert_spans = predict_records(
            records,
            model_dir=Path(args.model_dir),
            max_length=args.max_length,
        )

        print(
            json.dumps(
                {
                    "test_examples": len(records),
                    "baseline": _evaluation_payload(records, baseline_spans),
                    "phobert": _evaluation_payload(records, phobert_spans),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if args.command == "predict":
        sentence = (
            args.text
            if args.text is not None
            else input("Nhap cau: ")
        )

        if not sentence.strip():
            raise NERPipelineError("Cau dau vao khong duoc de trong.")

        print(
            json.dumps(
                predict_sentence(
                    sentence,
                    model_dir=Path(args.model_dir),
                    max_length=args.max_length,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if args.command == "batch-predict":
        input_path = Path(args.input)
        output_path = PREDICT_DIR / args.output

        if not input_path.is_file():
            raise NERPipelineError(f"Khong tim thay file input: {input_path}")
        
        # Load the unlabeled data.
        records = load_jsonl(input_path)
        print(f"Dang chay Batch Inference tren {len(records)} dong...")

        # Run batch predictions.
        predicted_spans_list = predict_records(
            records,
            model_dir=Path(args.model_dir),
            max_length=args.max_length,
        )

        # Format the output and mark pseudo-labels.
        output_records = []
        for record, spans in zip(records, predicted_spans_list):
            formatted_entities = [
                {
                    "text": record["sentence"][start:end],
                    "label": label,
                    "start": start,
                    "end": end
                }
                for start, end, label in spans
            ]
            
            output_records.append({
                "record_id": record.get("record_id", "unknown_id"),
                "sentence": record["sentence"],
                "entities": formatted_entities,
                "label_status": "PSEUDO_LABEL"
            })

        # Ghi ra file
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                for out_rec in output_records:
                    f.write(json.dumps(out_rec, ensure_ascii=False) + "\n")
        except OSError as exc:
            raise NERPipelineError(f"Khong the ghi output vao {output_path}: {exc}") from exc
            
        print(f"Hoan thanh! Ket qua pseudo-label luu an toan tai: {output_path}")
        return

    if args.command == "analyze":
        records = load_jsonl(PROCESSED_DIR / "test.jsonl")
        predicted = predict_records(
            records,
            model_dir=Path(args.model_dir),
            max_length=args.max_length,
        )

        analyses = [
            analyze_sentence(record, spans)
            for record, spans in zip(records, predicted)
        ]
        payload = summarize(analyses)
        output_path = PROCESSED_DIR / "error-analysis.json"

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            raise NERPipelineError(
                f"Khong the ghi error analysis vao {output_path}: {exc}"
            ) from exc

        print(
            json.dumps(
                payload["category_counts"],
                ensure_ascii=False,
                indent=2,
            )
        )
        print(f"Chi tiet error analysis da luu tai: {output_path}")
        return

    raise NERPipelineError(f"Lenh khong duoc ho tro: {args.command}")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="backslashreplace")

    parser = _parser()
    args = parser.parse_args()

    try:
        _run(args)
    except NERPipelineError as exc:
        print(f"Loi NER: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())