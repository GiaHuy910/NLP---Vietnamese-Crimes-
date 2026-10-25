# Quick Start Guide

The commands below use PowerShell on Windows. Expected results are listed at the end of each step
for comparison (see `RESULTS.md` for the full results).

## 1. Get the code

For a fresh clone:

```powershell
git clone https://github.com/GiaHuy910/NLP---Vietnamese-Crimes-.git vietnamese-crimes
cd vietnamese-crimes
git checkout ninh
```

If you already have the repository, update it:

```powershell
git fetch origin
git checkout ninh
git pull origin ninh
```

## 2. Set up the environment

Run these commands from `server/`. Python 3.10 or later is required.

```powershell
cd server
python -m venv .venv
.venv\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-ner.txt
```

If PowerShell blocks the activation script, run this first:
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`

From this point on, run commands from `server/` with the virtual environment activated
(the prompt should begin with `(.venv)`).

## 3. Install the models

Model nặng khoảng 500 MB mỗi cái nên không có trong git. Model được đính kèm ở mục **Releases** của
repo GitHub (cột bên phải trang repo, mục Releases, bản `models-v1`):

- `ner_model.zip`: model NER của luồng 1
- `event_models.zip`: 2 model của luồng 2

Tải về rồi giải nén vào `server/models/` sao cho cấu trúc như sau:

```
server/
  models/
    config.json, model.safetensors, ...   (model NER của luồng 1, nằm trực tiếp trong models/)
    event_trigger/                        (model trigger của luồng 2)
    event_argument/                       (model vai trò của luồng 2)
```

Không cần model: các lệnh baseline ở bước 4 và 5, và bước 7 (kiểm tra bộ chấm).

## 4. Luồng 1: NER

```powershell
# Prepare splits from manually annotated data.
python -m src.ner_pipeline.cli prepare-splits --train train_ner.csv --validation val_ner.csv --test test_ner.csv

# Rule-based baseline (expected overall F1: 0.669).
python -m src.ner_pipeline.cli baseline

# PhoBERT (requires the NER model; expected overall F1: about 0.799).
python -m src.ner_pipeline.cli evaluate

# Analyze PhoBERT errors.
python -m src.ner_pipeline.cli analyze
```

## 5. Part 2: Trigger, Argument, and Relation

The rule-based baseline requires no model (expected test scores: Trigger F1 0.697,
Relation F1 0.589, Event EM 0.275):

```powershell
python -m src.event_pipeline.evaluate --gold datasets/test.jsonl --baseline
```

Primary system: rules detect triggers and PhoBERT classifies roles (expected test scores:
Relation F1 0.609, Event EM 0.367):

```powershell
python -m src.event_pipeline.model predict --split test --trigger-source rules
python -m src.event_pipeline.evaluate --gold datasets/test.jsonl --pred datasets/processed/test_event_pred_rules.jsonl
```

Run all three configurations (model, rules, gold) on a split. Change `test` to `val` to evaluate
the validation split:

```powershell
foreach ($src in "model","rules","gold") {
  $sfx = if ($src -eq "model") { "" } else { "_$src" }
  Write-Host "`n######## $src"
  python -m src.event_pipeline.model predict --split test --trigger-source $src
  python -m src.event_pipeline.evaluate --gold datasets/test.jsonl --pred datasets/processed/test_event_pred$sfx.jsonl
}
```

Meaning of `--trigger-source`:

- `model`: PhoBERT detects triggers and classifies roles.
- `rules`: rules detect triggers and PhoBERT classifies roles (the selected system).
- `gold`: use manually annotated triggers with PhoBERT role classification (an upper bound for analysis).

View examples of baseline trigger errors:

```powershell
python -m src.event_pipeline.evaluate --gold datasets/test.jsonl --baseline --errors 30
```

## 6. Retrain the Part 2 models (optional)

Run on a GPU if possible (for example, a Google Colab T4 runtime). CPU training will be very slow.

```powershell
python -m src.event_pipeline.model train --task trigger --epochs 30
python -m src.event_pipeline.model train --task argument --epochs 15
```

The new models overwrite `server/models/event_trigger` and `server/models/event_argument`.
Checkpoints are selected using validation data; test data is not used during training.

## 7. Test the metrics

```powershell
python -m unittest discover -s test -p "test_event_metrics.py"
```

Expected output: `Ran 4 tests ... OK`.

## Common issues

| Error | Fix |
| --- | --- |
| `No module named 'src'` | You are not in `server/`. Run all commands from that directory. |
| `No module named 'torch'` / `transformers` / `underthesea` | The virtual environment is not active or dependencies are missing; repeat step 2. |
| `unrecognized arguments: --trigger-source` | The code is outdated; run `git pull origin ninh`. |
| `models/event_trigger` or `config.json` not found | The models were not extracted to the expected location. See step 3; avoid an extra nested `models/models/` directory. |
| `FileNotFoundError ... test_event_pred_rules.jsonl` | Run `predict` before `evaluate`. |
| `git add` reports `pathspec ... did not match` | You are in `server/`; run Git commands that use `server/...` paths from the repository root. |
