from pathlib import Path

# Project directories
SERVER_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = SERVER_DIR.parent

# Dataset directories
DATASET_DIR = SERVER_DIR / "datasets"
RAW_DIR = DATASET_DIR / "raw"
GOLD_DIR = DATASET_DIR / "gold"
PROCESSED_DIR = DATASET_DIR / "processed"
PREDICT_DIR = DATASET_DIR / "predictions"

# Model directories
MODEL_DIR = SERVER_DIR / "models"
CHECKPOINT_DIR = MODEL_DIR / "checkpoints"

# Baseline rules
RULES_PATH = DATASET_DIR / "ner_rules.json"

# Create output directories only
for path in (PROCESSED_DIR, PREDICT_DIR, CHECKPOINT_DIR):
    path.mkdir(parents=True, exist_ok=True)