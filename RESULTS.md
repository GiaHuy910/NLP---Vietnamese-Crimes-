# Results Summary: Event and Relation Extraction from Vietnamese Crime News

This document consolidates the dataset, evaluation method, results for Part 1 (NER) and Part 2
(trigger, argument, and relation extraction), error analysis, and limitations. Reported scores were
obtained on the team's manually annotated data.

## 1. Data

### 1.1 Raw corpus

| Property | Value |
|---|---|
| Articles | 44,240 (pre-split into train / validation / test at 70 / 10 / 20) |
| Label distribution | About 83% are "violations", indicating substantial class imbalance |
| SubLabel distribution | Imbalanced; Traffic is about 3% |
| Label / SubLabel conflicts | 353 articles |
| Article length | Median about 460 words; 86% exceed PhoBERT's 256-token limit |
| Formatting issues | 46% contain spaces before punctuation; 11% contain photo captions; 6% are not NFC-normalized |
| Near duplicates across splits | 14 near-duplicate train/test pairs |

See `notebooks/eda_raw_corpus.ipynb` for details.

### 1.2 Processing pipeline

The 44,240 articles are cleaned to 43,170 articles, split into approximately 601,000 sentences, and
then 601 sentences are selected for manual annotation in Label Studio. Steps 1–7 are documented in
`data_pipeline/README.md`.

### 1.3 Manually annotated gold data

| Split | Sentences | Sampling method |
|---|---:|---|
| Train | 301 | 50% matched trigger-keyword regexes and 50% random; stratified by SubLabel; at most 2 per article |
| Validation | 150 | Random, stratified by SubLabel |
| Test | 150 | Random, stratified by SubLabel |

Training is keyword-enriched to provide enough trigger examples. Validation and test are random samples
intended to reflect the news distribution.

Schema: 8 entity labels (`PERSON`, `ORGANIZATION`, `LOCATION`, `TIME`, `MONEY`, `PRODUCT`, `DRUG`,
`CRIME`), 8 event types (`BAO_LUC`, `BAT_GIU`, `CUOP_TROM`, `KHOI_TO`, `LUA_DAO`, `MA_TUY`, `THU_GIU`,
`XET_XU`), and 10 roles (`DOI_TUONG`, `NAN_NHAN`, `CO_QUAN`, `DIA_DIEM`, `THOI_GIAN`, `TANG_VAT`,
`TAI_SAN`, `HUNG_KHI`, `TOI_DANH`, `MUC_AN`).

## 2. Evaluation method

All metrics use exact character-offset matching and micro-averaged Precision, Recall, and F1.

| Metric | A prediction is correct when |
|---|---|
| NER F1 | Both entity offsets and entity label match |
| Trigger F1 | Both trigger offsets and event type match |
| Argument F1 | The trigger and linked entity offsets match |
| Relation F1 | Argument match conditions hold and the role also matches |
| Event Exact Match | The trigger is correct and the complete set of arguments (offsets + roles) matches gold |

All decisions (rules, hyperparameters, checkpoints, and configurations) should be based only on train
and validation. Test is reserved for final reporting.

## 3. Part 1: Named Entity Recognition

Test results (150 sentences, 355 entities):

| Label | Support | Rule baseline F1 | PhoBERT F1 |
|---|---:|---:|---:|
| **Overall (micro)** | 355 | **0.669** (P 0.734, R 0.614) | **0.799** (P 0.749, R 0.856) |
| PERSON | 130 | 0.673 | 0.977 |
| ORGANIZATION | 88 | 0.484 | 0.747 |
| LOCATION | 60 | 0.691 | 0.773 |
| TIME | 25 | 0.824 | 0.679 |
| MONEY | 18 | 0.848 | 0.833 |
| PRODUCT | 15 | 0.889 | 0.426 (P 0.283) |
| DRUG | 16 | 0.813 | 0.686 |
| CRIME | 3 | 0.857 | 0.600 |

### Findings

- PhoBERT raises overall F1 from 0.669 to 0.799, mainly through higher recall (0.614 to 0.856). The
  largest gains are for PERSON and ORGANIZATION, labels with more examples that are difficult for rules.
- The baseline remains stronger on some recognizable patterns (TIME, MONEY, PRODUCT, DRUG). These
  labels have relatively few training examples, limiting what PhoBERT can learn. PRODUCT precision is
  only 0.283, indicating substantial overprediction.
- CRIME has only 3 test examples, so its score is not reliable.

PhoBERT error analysis: 48 false-positive entities, 35 missed entities, 23 boundary errors (correct
label but incorrect offsets), and 5 ORGANIZATION-to-LOCATION confusions.

A BIO-alignment bug was fixed during development: matching without word boundaries had created 44
spurious one-character PERSON entities. The reported test count of 355 is after that fix.

## 4. Part 2: Triggers, Arguments, and Relations

Gold entities are used to evaluate Part 2 independently of NER errors.

### 4.1 Systems

- **Rule baseline:** context-aware trigger keywords (for example, MA_TUY requires a nearby drug mention;
  triggers after unrealized-event cues such as "intention" or "request" are excluded). Roles are linked
  using position and entity labels.
- **PhoBERT trigger model:** BIO tagging over underthesea-segmented words for 8 event types. The `O`
  class weight is reduced to 0.3; learning rate is 5e-5; training runs for 30 epochs. The best
  validation checkpoint is epoch 15 (validation Trigger F1 0.727).
- **PhoBERT argument model:** for each trigger/entity pair, insert `<t> </t>` and `<e> </e>` markers
  and event/entity type tokens, then classify one of 10 roles or `NONE` (`NONE` weight 0.5). Only roles
  allowed for that entity type are considered. The checkpoint is selected by validation Relation F1
  using gold triggers.

### 4.2 Configuration selection on validation

| Configuration (trigger + argument) | Trigger F1 | Argument F1 | Relation F1 | Event EM |
|---|---:|---:|---:|---:|
| Rules + rules (baseline) | 0.756 | 0.621 | 0.594 | 0.347 |
| PhoBERT + PhoBERT | 0.727 | 0.630 | 0.624 | 0.439 |
| **Rules + PhoBERT** | **0.756** | **0.682** | **0.675** | **0.472** |
| Gold triggers + PhoBERT (upper bound) | 1.000 | 0.846 | 0.841 | 0.557 |

Rules for trigger detection plus PhoBERT role classification scored best across all validation metrics
and were selected as the primary system.

### 4.3 Test results

| Configuration | Trigger F1 | Argument F1 | Relation F1 | Event EM |
|---|---:|---:|---:|---:|
| Rules + rules (baseline) | 0.697 | 0.629 | 0.589 | 0.275 |
| PhoBERT + PhoBERT | 0.654 | 0.677 | 0.595 | 0.356 |
| **Rules + PhoBERT (selected system)** | **0.697** | **0.696** | **0.609** | **0.367** |
| Gold triggers + PhoBERT (upper bound) | 1.000 | 0.804 | 0.710 | 0.519 |

The test ranking matches validation, suggesting that the selected configuration is stable.

Selected system details on test:

| Event type | Trigger support | Trigger F1 |
|---|---:|---:|
| BAO_LUC | 14 | 0.720 |
| BAT_GIU | 10 | 0.857 |
| CUOP_TROM | 5 | 0.800 |
| KHOI_TO | 5 | 0.667 |
| LUA_DAO | 7 | 0.571 |
| MA_TUY | 7 | 0.429 |
| THU_GIU | 2 | 1.000 |
| XET_XU | 4 | 0.667 |

| Role | Relation support | Relation F1 |
|---|---:|---:|
| CO_QUAN | 10 | 0.783 |
| DIA_DIEM | 8 | 0.500 |
| DOI_TUONG | 33 | 0.658 |
| HUNG_KHI | 9 | 0.714 |
| MUC_AN | 2 | 0.500 |
| NAN_NHAN | 14 | 0.462 |
| TAI_SAN | 5 | 0.727 |
| TANG_VAT | 10 | 0.444 |
| THOI_GIAN | 4 | 0.750 |
| TOI_DANH | 2 | 0.400 |

### 4.4 Findings

1. **PhoBERT links roles better than rules.** With the same rule-based triggers, Relation F1 rises from
   0.594 to 0.675 on validation and from 0.589 to 0.609 on test. Test Event EM rises from 0.275 to 0.367.
2. **PhoBERT trigger detection does not outperform the rules.** It is weakest for LUA_DAO (recall 0.18
   on validation, 0.29 on test) and MA_TUY (recall 0.14 on test). These types have few training
   examples, and fraud triggers are diverse (`giả danh`, `tự xưng`, `chiếm đoạt`, etc.). Context-aware
   rules are more stable with limited data.
3. **Trigger errors are a major bottleneck.** With 100% correct triggers, Relation F1 rises to 0.841
   (validation) and 0.710 (test), a gain of roughly 0.10–0.17 points.
4. **Difficult roles:** NAN_NHAN is confused with DOI_TUONG because both target PERSON entities;
   DIA_DIEM is confused with hometown/residence locations; TANG_VAT has low precision due to extra links.
5. **Validation/test gap:** validation is a few points higher than test for all configurations. The
   rule baseline, like the models, was tuned only on train and validation.

## 5. Limitations

- The test set is small (54 triggers, 97 relations, 355 entities). Differences of 0.01–0.02 are not
  statistically meaningful; several labels and roles have only 2–5 examples.
- Evaluation is sentence-level; cross-sentence events and coreference are not handled.
- Part 2 uses gold entities. End-to-end scores will be lower when NER errors propagate.
- Some known annotation issues remain: spans with leading whitespace (`val_a0051`, `a0120`, `a0125`);
  `"Công an tỉnh Lai Châu"` (`val_a0048`); `"Bà Nga"` should be `"Nga"`; `"Bắc"` / `"Nam"` are not
  LOCATION; and `"400 triệu đồng"` (validation) and `"25 triệu đồng"` (test) should be MONEY.
- Trigger rules in branch `Tu` (commits `291d88f`, `23807f7`) were tuned directly on test (test 0.954,
  train 0.639, validation 0.562). This is data leakage, so those results are excluded from this report.

## 6. Reproduce the results

From `server/`, the event models must be available in `server/models/event_trigger` and
`server/models/event_argument`.

```powershell
# Part 1
python -m src.ner_pipeline.cli prepare-splits --train train_ner.csv --validation val_ner.csv --test test_ner.csv
python -m src.ner_pipeline.cli baseline

# Part 2: rule baseline
python -m src.event_pipeline.evaluate --gold datasets/test.jsonl --baseline

# Part 2: selected system (rules + PhoBERT)
python -m src.event_pipeline.model predict --split test --trigger-source rules
python -m src.event_pipeline.evaluate --gold datasets/test.jsonl --pred datasets/processed/test_event_pred_rules.jsonl
```

Set `--trigger-source` to `model` or `gold` for the other configurations. Change `test` to `val` to
inspect validation results.
