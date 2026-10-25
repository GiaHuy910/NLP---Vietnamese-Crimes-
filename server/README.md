# Vietnamese NLP Extraction Pipeline

The server provides two related components for Vietnamese legal-news text:

- **Part 1 — NER:** PhoBERT token classification for 8 entity types: `PERSON`, `ORGANIZATION`,
  `LOCATION`, `TIME`, `MONEY`, `PRODUCT`, `DRUG`, and `CRIME`.
- **Part 2 — Event extraction:** rule-based or PhoBERT trigger detection and role/argument extraction
  for 8 event types and 10 roles.

The Part 1 API is in `src/main.py`. The reusable NER inference code is in
`src/ner_pipeline/phobert.py`; trigger rules and event extraction are in
`src/ner_pipeline/event_module.py`. Part 2 training and evaluation commands are under
`src/event_pipeline/`.

## 1. Requirements and installation

- Python 3.10 or later.
- Install a PyTorch build appropriate for your CPU/CUDA environment.
- PhoBERT fine-tuning may download `vinai/phobert-base-v2` from Hugging Face unless a local model is
  supplied.

From the repository root:

```powershell
cd server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-ner.txt
```

On macOS/Linux, activate with `source .venv/bin/activate`.

## 2. Model files

Model files are not committed to Git. Place the Part 1 model directly under `server/models/`. Part 2
models, when used, belong in `server/models/event_trigger/` and `server/models/event_argument/`.
The model directories should contain their `config.json`, weights, and tokenizer files.

## 3. NER input data and preprocessing

Place UTF-8 CSV files under `server/datasets/`. They must contain `sentence` and `entities` columns.
Use `NONE` for a sentence without entities, or semicolon-separated `TEXT|LABEL` items. The accepted
labels are the eight entity types listed above.

Prepare separate, predefined splits without moving rows between them:

```powershell
python -m src.ner_pipeline.cli prepare-splits `
  --train train_ner.csv --validation val_ner.csv --test test_ner.csv
```

Processed JSONL and BIO files are written to `server/datasets/processed/`. Identical or near-duplicate
sentences across splits, conflicting annotations, overlapping spans, and alignment errors are checked
during preprocessing.

The local `train.csv`, `valid.csv`, and `test.csv` files may contain 100 template-generated synthetic
rows appended for smoke testing. These are fictional and not human-verified. Do not use metrics on
these mixed files as evidence of real-world quality. The separate annotated `*_ner.csv` files and
event JSONL data are distinct artifacts; check their provenance before reporting scores.

## 4. Train and evaluate NER

```powershell
python -m src.ner_pipeline.cli train
python -m src.ner_pipeline.cli baseline
python -m src.ner_pipeline.cli evaluate
python -m src.ner_pipeline.cli analyze
```

Training uses train data and selects checkpoints by exact-span F1 on validation. The held-out test
split is not used for training or checkpoint selection. The baseline and PhoBERT are evaluated with
exact-span Precision, Recall, and F1, overall and by entity label.

For a one-sentence prediction from Python:

```python
from src.ner_pipeline.phobert import predict_sentence

entities = predict_sentence("Ngày 15/8, Công an quận Đống Đa đã khởi tố Nguyễn Văn A.")
```

The result is a list of dictionaries with `text`, `label`, `start`, and `end`. Offsets refer to
characters in the normalized input sentence.

## 5. Run the API

Start from the `server/` directory:

```powershell
python -m src.main
```

The service listens at `http://127.0.0.1:3001`.

### NER endpoint

`POST /api/process` accepts a JSON body with a `text` field:

```powershell
$body = @{ text = "Ngày 15/8, Công an quận Đống Đa đã khởi tố Nguyễn Văn A." } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:3001/api/process -Method Post `
  -ContentType "application/json" -Body $body
```

The response includes `input_text` and `entities`. Empty input returns HTTP 400. A missing NER model
returns HTTP 503 with an actionable error message.

### Trigger-only endpoint

`POST /api/process/event-trigger` calls only `detect_triggers` from
`src/ner_pipeline/event_module.py`; it does not run NER or load a model:

```powershell
$body = @{ text = "Công an đã khởi tố Nguyễn Văn A." } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:3001/api/process/event-trigger -Method Post `
  -ContentType "application/json" -Body $body
```

The response includes `input_text` and a `triggers` list with event type and character offsets.

## 6. Part 2: Event training and evaluation

The event pipeline uses `datasets/train.jsonl`, `datasets/val.jsonl`, and `datasets/test.jsonl`.
For example:

```powershell
# Evaluate the rule-based baseline.
python -m src.event_pipeline.evaluate --gold datasets/test.jsonl --baseline

# Train both PhoBERT models (GPU recommended).
python -m src.event_pipeline.model train --task all --epochs 15

# Predict with rule-based triggers and PhoBERT role classification.
python -m src.event_pipeline.model predict --split test --trigger-source rules
python -m src.event_pipeline.evaluate --gold datasets/test.jsonl --pred datasets/processed/test_event_pred_rules.jsonl
```

Part 2 metrics use gold entities by default, so they isolate event extraction and do not measure
end-to-end NER error propagation. See `src/event_pipeline/README.md` for model details and metric
definitions.

## 7. Tests and error analysis

From the repository root:

```powershell
python -m unittest discover -s server/test -p "test_ner_pipeline.py"
python -m unittest discover -s server/test -p "test_event_metrics.py"
python -m unittest server.test.test_main_api
```

NER error analysis is written to `server/datasets/processed/error-analysis.json`.
