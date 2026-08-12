"""
analyzer/local_classifier.py

Tier 2 classifier using CodeBERT embeddings + sklearn SVM.
Generates 768-dim CLS embeddings via microsoft/codebert-base, then
classifies into SLE'17 categories using a trained RBF-SVM.

Model weights are loaded from CODEBERT_DIR (volume-mounted in Docker).
The SVM pickle is produced by scripts/train_classifier.py.
"""
import os, logging, pickle
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import numpy as np

log = logging.getLogger(__name__)

def _resolve_model_dir() -> str:
    if "CODEBERT_DIR" in os.environ:
        return os.environ["CODEBERT_DIR"]
    local = Path(r"C:\GreenSoftware\models\codebert")
    if local.exists():
        return str(local)
    return "/app/models/codebert"

MODEL_DIR       = _resolve_model_dir()
CLASSIFIER_PATH = Path(MODEL_DIR) / "sle17_classifier.pkl"


@dataclass
class LocalClassification:
    category: str
    target_language: str
    energy_saving: int
    confidence: float
    source: str = "local_model"


# ── Lazy-loaded CodeBERT globals ─────────────────────────────────────────────
_tokenizer  = None
_model      = None
_codebert_ok = False


def _ensure_codebert() -> bool:
    """Load CodeBERT tokenizer + model once; return True if ready."""
    global _tokenizer, _model, _codebert_ok
    if _codebert_ok:
        return True
    try:
        import torch
        from transformers import AutoTokenizer, AutoModel
        log.info("[CodeBERT] Loading from %s ...", MODEL_DIR)
        _tokenizer   = AutoTokenizer.from_pretrained(
            "microsoft/codebert-base", cache_dir=MODEL_DIR)
        _model       = AutoModel.from_pretrained(
            "microsoft/codebert-base", cache_dir=MODEL_DIR)
        _model.eval()
        _codebert_ok = True
        log.info("[CodeBERT] Ready")
        return True
    except Exception as e:
        log.warning("[CodeBERT] Load failed: %s", e)
        return False


def extract_features(code: str) -> np.ndarray:
    """
    Return a 768-dim CodeBERT CLS embedding for the given code snippet.
    Used by both the SVM trainer and the runtime classifier.
    Falls back to a zero vector if CodeBERT is unavailable.
    """
    if not _ensure_codebert():
        return np.zeros(768, dtype=np.float32)
    import torch
    inputs = _tokenizer(
        code, return_tensors="pt", truncation=True,
        max_length=512, padding=True,
    )
    with torch.no_grad():
        outputs = _model(**inputs)
    return outputs.last_hidden_state[:, 0, :].squeeze().numpy().astype(np.float32)


class LocalClassifier:
    def __init__(self):
        self._clf       = None
        self._available = False
        self._load()

    def _load(self):
        try:
            import sklearn
            if CLASSIFIER_PATH.exists():
                log.info("[LocalClassifier] Loading SLE17 classifier...")
                with open(CLASSIFIER_PATH, "rb") as f:
                    self._clf = pickle.load(f)
                codebert_ready  = _ensure_codebert()
                self._available = codebert_ready
                if codebert_ready:
                    log.info("[LocalClassifier] Ready (CodeBERT + SVM)")
                else:
                    log.warning("[LocalClassifier] SVM loaded but CodeBERT unavailable — tier 2 disabled")
            else:
                log.warning(f"[LocalClassifier] Not found: {CLASSIFIER_PATH} -- "
                            "Run scripts/train_classifier.py")
        except ImportError:
            log.warning("[LocalClassifier] scikit-learn not installed")
        except Exception as e:
            log.warning(f"[LocalClassifier] Load error: {e}")

    @property
    def available(self) -> bool:
        return self._available

    def classify(self, code: str, confidence_threshold: float = 0.65) -> Optional[LocalClassification]:
        if not self._available:
            return None
        try:
            from analyzer.training_data import CATEGORY_TO_TARGET, CATEGORY_SAVINGS
            features   = extract_features(code)
            proba      = self._clf.predict_proba([features])[0]
            best_idx   = proba.argmax()
            confidence = float(proba[best_idx])
            category   = self._clf.classes_[best_idx]

            if confidence < confidence_threshold:
                log.debug(f"[LocalClassifier] Low confidence {confidence:.0%} -> Claude")
                return None

            target = CATEGORY_TO_TARGET.get(category, "keep")
            saving = CATEGORY_SAVINGS.get(category, 0)
            log.info(f"[LocalClassifier] {category} -> {target} ({confidence:.0%})")

            return LocalClassification(
                category=category,
                target_language=target,
                energy_saving=saving,
                confidence=confidence,
                source="local_model"
            )
        except Exception as e:
            log.warning(f"[LocalClassifier] Error: {e}")
            return None

    def status(self) -> dict:
        return {
            "available": self._available,
            "model_dir": MODEL_DIR,
            "classifier_path": str(CLASSIFIER_PATH),
            "classifier_trained": CLASSIFIER_PATH.exists(),
            "codebert_loaded": _codebert_ok,
        }


_instance: Optional[LocalClassifier] = None

def get_classifier() -> LocalClassifier:
    global _instance
    if _instance is None:
        _instance = LocalClassifier()
    return _instance
