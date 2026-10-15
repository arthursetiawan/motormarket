from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
DATA_RAW = DATA_DIR / "raw"
DATA_STAGING = DATA_DIR / "staging"
DATA_GOLD = DATA_DIR / "gold"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"
MODELS_DIR = ARTIFACTS_DIR / "models"
REPORTS_DIR = ARTIFACTS_DIR / "reports"

PRICE_MODEL_PATH = MODELS_DIR / "price_model.joblib"
FEATURE_SPEC_PATH = MODELS_DIR / "feature_spec.json"
METRICS_PATH = REPORTS_DIR / "metrics.json"
MODEL_CARD_PATH = REPORTS_DIR / "MODEL_CARD.md"
IMPORTANCE_PATH = REPORTS_DIR / "feature_importance.json"
DRIFT_PATH = REPORTS_DIR / "drift.json"


def ensure_dirs() -> None:
    for path in (DATA_RAW, DATA_STAGING, DATA_GOLD, MODELS_DIR, REPORTS_DIR):
        path.mkdir(parents=True, exist_ok=True)
