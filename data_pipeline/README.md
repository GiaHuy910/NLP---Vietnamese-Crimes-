# Data Pipeline: Cleaning, Annotation, and Export

This pipeline prepares data for both parts of the project: extracting legal-violation events from
Vietnamese news.

- **Part 1 (NER):** recognize 8 entity types.
- **Part 2 (event extraction):** extract Trigger → Argument → Relation.

Data preprocessing and annotation: Đỗ Đăng Ninh.

## 1. Final dataset

Generated files are stored in `data/dataset/`.

| Split | Sentences | Source | Entities | Triggers | Relations | Purpose |
|---|---:|---|---:|---:|---:|---|
| `train` | 301 | Manually annotated | 894 | 192 | 460 | Model training |
| `val` | 150 | Manually annotated | 408 | 70 | Checkpoint/early-stop selection |
| `test` | 150 | Manually annotated | 350 | 54 | **Final results only** |

Each split has two files:

- `{split}.jsonl` for **Part 2**, one sentence per line. Each record contains `ann_id`, `doc_id`,
  `SubLabel`, `source`, `sentence`, `entities`, `triggers`, and `relations`. Span offsets are character
  offsets into `sentence`, so `sentence[start:end] == text`.
- `{split}_ner.csv` for **Part 1**, with `sentence` and `entities` columns. The `entities` field uses
  `TEXT|LABEL` items separated by semicolons.

Report final scores on `test` only. Use `val` for model and configuration selection.

## 2. Schema

**Eight entity labels:** `PERSON`, `ORGANIZATION`, `LOCATION`, `TIME`, `MONEY`, `DRUG`, `PRODUCT`,
`CRIME`.

**Eight event types:**

| Group | Type | Trigger examples |
|---|---|---|
| Crime | `LUA_DAO` | lừa đảo chiếm đoạt, chiếm đoạt, giả danh |
| Crime | `MA_TUY` | mua bán, tàng trữ, vận chuyển, sản xuất (when a drug is mentioned) |
| Crime | `BAO_LUC` | giết, sát hại, đâm, chém, đánh, hành hung, hiếp dâm |
| Crime | `CUOP_TROM` | cướp, cướp giật, trộm cắp, đột nhập |
| Procedure | `BAT_GIU` | bắt, bắt giữ, bắt quả tang, tạm giữ, tạm giam |
| Procedure | `THU_GIU` | thu giữ, tịch thu |
| Procedure | `KHOI_TO` | khởi tố, truy tố |
| Procedure | `XET_XU` | xét xử, tuyên phạt, tuyên án, kết án |

**Ten roles** (relations always point from a trigger to an entity):

| Role | Allowed entity labels |
|---|---|
| `DOI_TUONG`, `NAN_NHAN` | `PERSON`, `ORGANIZATION` |
| `CO_QUAN` | `ORGANIZATION` |
| `TAI_SAN` | `MONEY`, `PRODUCT` |
| `TANG_VAT` | `DRUG`, `PRODUCT` |
| `HUNG_KHI` | `PRODUCT` |
| `TOI_DANH` | `CRIME` |
| `MUC_AN` | `TIME`, `MONEY` |
| `THOI_GIAN` | `TIME` |
| `DIA_DIEM` | `LOCATION` |

See [`docs/annotation_guidelines.md`](../docs/annotation_guidelines.md) for the full annotation policy.

## 3. Directory structure

Scripts in `data_pipeline/`:

- `config.py`: paths, parameters, trigger lexicon.
- `rules.py`: entity and trigger rules for pre-annotation and the baseline.
- `step1_fix_encoding.py` through `step7_export_dataset.py`: the seven processing stages.
- `check_annotations.py`: automatic annotation checks.
- `explore_triggers.py`: trigger-candidate analysis used to design the schema.
- `labelstudio_config.xml`: Label Studio interface.
- `requirements.txt`: pipeline dependencies.

Other data locations:

- `data/corpus news/`: raw and intermediate corpus files (not committed; obtain from the team Drive).
- `data/annotation/`: annotation spreadsheets and Label Studio exports.
- `data/dataset/`: final datasets for both parts.

## 4. Rebuild the data

Install dependencies:

```powershell
pip install -r data_pipeline/requirements.txt
```

Place `train_cleaned_labeled.csv`, `val_cleaned_labeled.csv`, and `test_cleaned_labeled.csv` in
`data/corpus news/`. Run the following scripts from `data_pipeline/`:

| Step | Command | Operation | Output |
|---|---|---|---|
| 1 | `python step1_fix_encoding.py` | Repair Unicode and remove hidden characters | `*_clean.csv` |
| 2 | `python step2_clean_news.py` | Remove captions/URLs, fix SubLabel, prevent train/val/test leakage | `train/val/test.csv` |
| 3 | `python step3_apply_scope.py --apply` | Exclude the small Traffic Violations category (~2%) | Updated split CSVs |
| 4 | `python step4_split_sentences.py` | Split articles; retain sentences with 5–100 words | `*_sentences.csv` |
| 5 | `python step5_sample_for_annotation.py` | Stratify by SubLabel; keep at most 2 sentences per article | `annotation/*_to_annotate.xlsx` |
| 6 | `python step6_to_labelstudio.py` | Create Label Studio tasks (train includes rule pre-labels) | `annotation/*_tasks.json` |
| 7 | `python step7_export_dataset.py <file.json> <name> [--gold-only]` | Export both task formats | `dataset/*.jsonl`, `*_ner.csv` |

### Processing details

1. **Encoding cleanup** (`step1_fix_encoding.py`): normalize Unicode to NFC; repair separated
   Vietnamese diacritics; remove zero-width spaces, stray BOMs, and soft hyphens; replace the
   replacement character with a space; and collapse repeated whitespace. `clean_text` is also used
   for text submitted to the API.
2. **Noise removal and leakage prevention** (`step2_clean_news.py`): remove photo captions, `XEM CLIP:`
   prefixes, and URLs; reconcile inconsistent Label/SubLabel values; keep test fixed, remove test
   duplicates from validation, and remove validation/test duplicates from training. Documents are
   considered duplicates when full content, the first 200 characters, or normalized titles match.
3. **Scope filtering** (`step3_apply_scope.py`): exclude the categories listed in `EXCLUDE_SUBLABELS`.
   Without `--apply`, the script only previews the removals. Re-running with `--apply` is safe; rerun
   step 2 to restore the unfiltered data.
4. **Sentence splitting** (`step4_split_sentences.py`): use underthesea, normalize punctuation spacing,
   join fragments created by abbreviation splitting, remove a duplicated summary sentence, and retain
   sentences between `MIN_WORDS` (5) and `MAX_WORDS` (100). The sentence-splitting helper is also used
   for articles submitted through the API.
5. **Sampling** (`step5_sample_for_annotation.py`): sample evenly by SubLabel and select at most two
   sentences per article. Half of the training sample is drawn from sentences matching trigger keywords;
   the rest is random. Validation and test are randomly sampled so keyword rules are not favored.
   `N_DOUBLE` training sentences are flagged for optional duplicate annotation.
6. **Label Studio tasks** (`step6_to_labelstudio.py`): training tasks include rule-based entity and
   trigger suggestions that annotators correct; relations are annotated manually. Validation and test
   tasks have no pre-labels. A single split can be generated with, for example,
   `python step6_to_labelstudio.py train`.
7. **Export** (`step7_export_dataset.py`): manually annotated `annotations` are gold; records with only
   rule-generated `predictions` are silver. Use `--gold-only` to export only manually annotated
   records. Reversed entity-to-trigger relations are corrected to trigger-to-entity direction.
   `--val N` can split a validation subset by SubLabel but is not used when a separate gold validation
   set already exists.

Example exports:

```powershell
python step7_export_dataset.py ../data/annotation/train.json train --gold-only
python step7_export_dataset.py ../data/annotation/val.json val
python step7_export_dataset.py ../data/annotation/test.json test
```

Run the annotation checker after each export:

```powershell
python check_annotations.py ../data/annotation/train.json
```

It writes `<input>_issues.csv`. Warnings are rule-based suggestions for human review, not automatic
corrections. Definite structural issues include invalid role/entity types, reversed relations, missing
roles, split triggers/times, punctuation attached to spans, and generic PERSON/ORGANIZATION labels.

## 5. Important decisions and limitations

- **Leakage prevention:** preserve test; remove test duplicates from validation; remove validation and
  test duplicates from training. Compare full content, the first 200 characters, and titles.
- **Scope:** exclude Traffic Violations because it represents only about 2% of violation articles.
- **Sampling:** half of training is keyword-enriched because only about 25–30% of candidate sentences
  contain an event. Validation and test are sampled randomly to avoid inflating keyword-baseline scores.
- **Gold labels:** all three splits are annotated manually using `docs/annotation_guidelines.md`.
  Training suggestions are corrected by annotators; only manually annotated training examples are
  exported with `--gold-only`.
- **Residual noise:** some article-level violation SubLabels are attached to sentences that are not
  themselves about a crime (e.g. entertainment or statistics). SubLabel is assigned at article level.
- **Annotation review:** the final test checker produced warnings for 17 of 150 sentences; manual
  review confirmed one actual error, which was fixed.

## 6. Notes

- Do not open and resave CSVs in Excel; this can damage Vietnamese encoding. Scripts use `utf-8-sig`,
  which Excel can read.
- Close spreadsheets before running scripts to avoid `PermissionError`.
- Install Label Studio in a separate virtual environment (for example, `.venv-ls`). Deactivate it
  before running the data pipeline with the project Python environment.
