from pathlib import Path


SERVER_DIR = Path(__file__).resolve().parents[2]
DATASET_DIR = SERVER_DIR / "datasets"
PROCESSED_DIR = DATASET_DIR / "processed"
MODEL_DIR = SERVER_DIR / "models" / "phobert-ner"
RULES_PATH = DATASET_DIR / "ner_rules.json"

