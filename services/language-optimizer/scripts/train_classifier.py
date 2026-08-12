"""
scripts/train_classifier.py

Train the SLE'17 classifier using CodeBERT embeddings + sklearn SVM.
Generates 768-dim CLS embeddings for each training example, then fits
an RBF-SVM. Produces sle17_classifier.pkl for use in Docker at runtime.

Usage:
    pip install scikit-learn numpy torch transformers sentencepiece tokenizers
    python scripts/train_classifier.py
"""
import os, sys, pickle, logging
from pathlib import Path
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)
sys.path.insert(0, str(Path(__file__).parent.parent))

MODEL_DIR       = os.environ.get("CODEBERT_DIR", "C:/GreenSoftware/models/codebert")
CLASSIFIER_PATH = Path(MODEL_DIR) / "sle17_classifier.pkl"


def main():
    log.info("=" * 60)
    log.info("GraalVM Optimizer -- SLE17 Classifier Training")
    log.info("=" * 60)

    try:
        import sklearn, numpy as np
    except ImportError as e:
        log.error(f"Missing: {e}. Run: pip install scikit-learn numpy")
        sys.exit(1)

    try:
        import torch
        from transformers import AutoTokenizer, AutoModel  # noqa: F401
    except ImportError as e:
        log.error(f"Missing: {e}. Run: pip install torch transformers sentencepiece tokenizers")
        sys.exit(1)

    from analyzer.training_data import TRAINING_EXAMPLES, ALL_CATEGORIES
    from analyzer.local_classifier import extract_features, _ensure_codebert

    if not _ensure_codebert():
        log.error("CodeBERT failed to load — cannot extract embeddings. Check CODEBERT_DIR.")
        sys.exit(1)

    log.info(f"Training examples: {len(TRAINING_EXAMPLES)}")
    log.info(f"Categories: {ALL_CATEGORIES}")
    log.info("\nExtracting features...")

    X, y = [], []
    for i, (code, category, target, saving) in enumerate(TRAINING_EXAMPLES):
        X.append(extract_features(code))
        y.append(category)
        log.info(f"  [{i+1}/{len(TRAINING_EXAMPLES)}] {category}")

    X = np.array(X)
    log.info(f"\nFeature matrix: {X.shape[0]} x {X.shape[1]}")

    from sklearn.svm import SVC
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline
    from sklearn.model_selection import cross_val_score, StratifiedKFold

    clf = Pipeline([
        ("scaler", StandardScaler()),
        ("svm", SVC(kernel="rbf", C=2.0, gamma="scale",
                    probability=True, class_weight="balanced", random_state=42))
    ])

    log.info("\nCross-validation...")
    try:
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        scores = cross_val_score(clf, X, y, cv=cv, scoring="accuracy")
        log.info(f"CV accuracy: {scores.mean():.1%} +/- {scores.std():.1%}")
    except Exception as e:
        log.info(f"CV skipped: {e}")

    clf.fit(X, y)

    log.info("\nPer-category training accuracy:")
    y_pred = clf.predict(X)
    cat_c, cat_t = defaultdict(int), defaultdict(int)
    for true, pred in zip(y, y_pred):
        cat_t[true] += 1
        if true == pred: cat_c[true] += 1
    for cat in sorted(set(y)):
        log.info(f"  {cat:20s}: {cat_c[cat]/cat_t[cat]:.0%} ({cat_c[cat]}/{cat_t[cat]})")

    Path(MODEL_DIR).mkdir(parents=True, exist_ok=True)
    with open(CLASSIFIER_PATH, "wb") as f:
        pickle.dump(clf, f)
    log.info(f"\nSaved: {CLASSIFIER_PATH}")

    log.info("\nQuick tests:")
    tests = [
        ("""
public double[] sortTransactionAmounts(double[] amounts) {
    double[] result = amounts.clone();
    int n = result.length;
    for (int i = 0; i < n-1; i++)
        for (int j = 0; j < n-i-1; j++)
            if (result[j] > result[j+1]) {
                double t = result[j]; result[j] = result[j+1]; result[j+1] = t;
            }
    return result;
}""", "sorting"),
        ("""
public double runSimulation(double portfolioValue, double vol, int simulations) {
    Random rng = new Random();
    double[] results = new double[simulations];
    for (int s = 0; s < simulations; s++) {
        double value = portfolioValue;
        for (int d = 0; d < 252; d++)
            value *= Math.exp(-0.5*vol*vol/252 + vol/Math.sqrt(252)*rng.nextGaussian());
        results[s] = value;
    }
    Arrays.sort(results);
    return results[(int)(simulations * 0.05)];
}""", "monte_carlo"),
        ("""
public double computeRiskScore(double[] factors, double[] weights, int depth) {
    if (depth == 0) {
        double sum = 0;
        for (int i = 0; i < factors.length; i++) sum += factors[i] * weights[i];
        return sum;
    }
    int mid = factors.length / 2;
    return (computeRiskScore(Arrays.copyOfRange(factors,0,mid),
                             Arrays.copyOfRange(weights,0,mid), depth-1) +
            computeRiskScore(Arrays.copyOfRange(factors,mid,factors.length),
                             Arrays.copyOfRange(weights,mid,weights.length), depth-1)) / 2;
}""", "recursion_deep"),
        ("public String getAccountNumber() { return this.accountNumber; }", "trivial"),
        ("""
public List<AmortizationRow> computeSchedule(double principal, double rate, int months) {
    double r = rate / 12 / 100;
    double payment = principal * r / (1 - Math.pow(1+r, -months));
    List<AmortizationRow> schedule = new ArrayList<>();
    double balance = principal;
    for (int m = 1; m <= months; m++) {
        double interest = balance * r;
        balance -= payment - interest;
        schedule.add(new AmortizationRow(m, payment, interest, balance));
    }
    return schedule;
}""", "amortization"),
    ]
    for code, expected in tests:
        feat = extract_features(code)
        pred = clf.predict([feat])[0]
        prob = clf.predict_proba([feat])[0].max()
        ok   = "OK  " if pred == expected else "MISS"
        log.info(f"  [{ok}] expected={expected:15s} got={pred:15s} ({prob:.0%})")

    log.info("\nDone! Restart optimizer to activate tier 2.")


if __name__ == "__main__":
    main()
