# Vietnamese NER pipeline

This folder implements **Part 1 — Named Entity Recognition** for Vietnamese legal-news
text. It does not implement event triggers, arguments, event structures, or relation
extraction.

Only `PERSON`, `ORGANIZATION`, and `LOCATION` are supported. The BIO vocabulary is
`O`, `B-PERSON`, `I-PERSON`, `B-ORGANIZATION`, `I-ORGANIZATION`, `B-LOCATION`,
`I-LOCATION`.

No dataset, annotation, evaluation result, or trained model is included. You supply
the data yourself; all raw and generated dataset files remain under `server/datasets/`.

## 1. Environment

- Python 3.10 or newer.
- PyTorch should be installed for the machine's CPU/CUDA configuration. Follow the
  [official PyTorch installation selector](https://pytorch.org/get-started/locally/)
  if the default package installation does not match your hardware.
- Fine-tuning downloads the pretrained `vinai/phobert-base-v2` model from Hugging Face
  unless a different `--model-name` is given. This is a pretrained model checkpoint,
  not an external replacement dataset.

## 2. Installation

From the repository root:

```powershell
cd server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-ner.txt
```

On macOS/Linux, activate with `source .venv/bin/activate`. Install a suitable PyTorch
build first if needed, then install the remaining packages from `requirements-ner.txt`.

## 3. Dataset location and format

Put one or more UTF-8 CSV files directly in `server/datasets/`. The CSV must contain
the columns `sentence` and `entities`; quote fields according to the CSV standard when
they contain commas. The `entities` cell is `NONE` for a sentence without target
entities, or semicolon-separated `TEXT|LABEL` items, where `LABEL` is one of the
three supported entity types. Do not add other entity types.

The pipeline does not download or generate example data automatically at runtime.
Existing non-CSV files are ignored. With exactly one CSV, `prepare` discovers it;
if there are multiple CSVs, pass `--input` with a filename or a `datasets/...` path
inside `server/`.

For a pipeline smoke test, the current `train.csv`, `valid.csv`, and `test.csv` each
contain 100 extra, template-generated synthetic rows, appended after the supplied
annotations. They are explicitly fictional and neutral, with one entity of each
supported type per row. These rows are not real news or human-verified annotations;
do not use metrics on this mixed test split as evidence of real-world model quality.
The original examples remain before the appended synthetic rows.

An optional user-maintained `server/datasets/ner_rules.json` can provide baseline
keywords, for example as a JSON object with `PERSON`, `ORGANIZATION`, and/or
`LOCATION` keys whose values are arrays of strings. No keyword list is pre-filled.

## 4. Preprocessing and annotation

Create the CSV annotation yourself using the format above. `prepare` validates the
schema and labels, aligns every annotated mention to the original sentence, performs
Vietnamese word segmentation with underthesea, and generates BIO labels. Alignment
is token-boundary based, whitespace tolerant, punctuation-aware, and marks every
matching occurrence of an annotated entity. It reports unmatched, overlapping, or
different-label overlapping annotations rather than silently assigning incorrect
labels. Same-label overlapping mentions keep the longest span, and the removal
count is reported for review.

When rebuilding splits from one full corpus after earlier experimental training,
use `--train-only` to keep the previously exposed sentences out of validation/test:

```powershell
python -m src.ner_pipeline.cli prepare `
  --input valid.csv --train-only annotation_clean.csv --seed 42
```

The training-only CSV must be a matching subset of the source corpus. Its examples
are forced into the new training split; it cannot contribute to validation or test.
Same-label overlapping annotations are reduced to the longest span, and the number
removed is reported. Different-label overlaps remain hard errors for manual review.

```powershell
python -m src.ner_pipeline.cli prepare
# Or select a file when there is more than one:
python -m src.ner_pipeline.cli prepare --input annotations.csv --seed 42
```

The deduplicated JSONL working files are written to `server/datasets/processed/`.
The standard annotation CSVs are also written to `server/datasets/train.csv`,
`server/datasets/valid.csv`, and `server/datasets/test.csv`. BIO token-level CSVs
(`train_bio.csv`, `valid_bio.csv`, and `test_bio.csv`) include sentence and token IDs,
token, BIO label, and source offsets. These six CSVs are generated outputs and replace
same-named files in `server/datasets/`; preserve any originals separately before
running `prepare` if you need them later.

Identical
sentences cannot cross splits; conflicting annotations for duplicate sentences stop
preprocessing and must be resolved. At least three unique sentences are required.
For small datasets each split contains at least one sentence, which leaves very little
training data; the CLI reports actual split sizes. No stratification is performed,
so check label coverage yourself before treating metrics as reliable.

If you already have separate annotated files, keep their intended roles and use:

```powershell
python -m src.ner_pipeline.cli prepare-splits `
  --train train.csv --validation valid.csv --test test.csv
```

This validates and BIO-converts each file independently; it never moves test rows
into training. It rejects duplicate sentences across the supplied splits, overlapping
entity spans, and token alignment errors. It writes the same processed JSONL files
only after all three inputs pass validation.

## 5. Train

```powershell
python -m src.ner_pipeline.cli train
```

Training reads only `train.jsonl`; the validation split selects the checkpoint by
exact-span F1. The held-out `test.jsonl` is not used in training or checkpoint
selection. The trained checkpoint and tokenizer are saved to
`server/models/phobert-ner/`. Training requires real annotated data and will fail
clearly if the data or dependencies are missing.
Class-weighted token loss is used by default to counter the predominance of `O`
labels; adjust it with `--class-weight-power` if validation indicates a different
balance is appropriate.

Optional controls include `--epochs`, `--batch-size`, `--learning-rate`,
`--max-length`, `--seed`, and `--model-name`. Sentences that exceed `--max-length`
are rejected rather than silently truncated. PhoBERT subword predictions are mapped back to word-level BIO labels using the
checkpoint tokenizer's word-piece encoding.

## 6. Evaluation

```powershell
python -m src.ner_pipeline.cli evaluate
```

Both the rule-based baseline and PhoBERT are evaluated against the same held-out
`test.jsonl`, with strict exact-span precision, recall, and F1 overall and for each
entity type. The baseline combines simple Vietnamese context cues with optional
user-supplied keywords; it is a transparent reference baseline, not a trained model.
No scores are printed unless the test split and trained model exist.
Because the current test split includes generated synthetic examples, its scores
are for pipeline validation only and must not be reported as evaluation on authentic
Vietnamese legal-news data.

## 7. Prediction

```powershell
python -m src.ner_pipeline.cli predict --text "Nhập câu tin tức cần nhận diện"
```

Omit `--text` to enter a sentence interactively. Results are JSON objects containing
the entity text and label. If no trained checkpoint exists, prediction reports that
the model must be trained; it does not substitute fabricated predictions.

## 8. Error analysis

```powershell
python -m src.ner_pipeline.cli analyze
```

The report is written to `server/datasets/processed/error-analysis.json` and counts
missing/extra entities, truncation, person misrecognition, location-as-person,
organization-as-location, multi-entity sentences, abbreviations, punctuation, and
repeated gold mentions where observable.

## 9. Project files and tests

- Pipeline code: `server/src/ner_pipeline/`
- Raw user dataset and generated splits/reports: `server/datasets/`
- Fine-tuned model: `server/models/phobert-ner/`
- Dependencies: `server/requirements-ner.txt`

Run unit tests from the repository root with:

```powershell
python -m unittest discover -s server/test -p "test_ner_pipeline.py"
```
