#!/bin/sh
set -e

echo "╔══════════════════════════════════════════════════════╗"
echo "║       GraalVM Auto-Optimizer                         ║"
echo "╚══════════════════════════════════════════════════════╝"

# Write API key to config.json for the UI
python3 -c "
import os, json
key = os.environ.get('ANTHROPIC_API_KEY', '')
with open('/app/ui/build/config.json', 'w') as f:
    json.dump({'anthropicApiKey': key}, f)
print('Config written, key length:', len(key))
"

echo "🐍 Python: $(python3 --version)"
echo "🟨 Node:   $(node --version 2>/dev/null || echo 'not found')"
echo ""
echo "🌐 Web UI:  http://localhost:8000/app"
echo "📡 API:     http://localhost:8000/api"
echo "📖 Docs:    http://localhost:8000/docs"
echo ""

# Auto-train CodeBERT classifier on first run if model is missing
# Set ENABLE_TIER2=false to skip training and run Tier 1 + Tier 3 only.
export CODEBERT_DIR="${CODEBERT_DIR:-/app/models/codebert}"
CLASSIFIER_PATH="$CODEBERT_DIR/sle17_classifier.pkl"
ENABLE_TIER2="${ENABLE_TIER2:-true}"

if [ "$ENABLE_TIER2" = "false" ]; then
    echo "Tier 2 (CodeBERT) disabled via ENABLE_TIER2=false — skipping training."
elif [ ! -f "$CLASSIFIER_PATH" ]; then
    echo "CodeBERT classifier not found — training now (first-run only, ~15 min)..."
    CODEBERT_DIR="$CODEBERT_DIR" TRANSFORMERS_OFFLINE=0 HF_DATASETS_OFFLINE=0 python3 scripts/train_classifier.py
    echo "Training complete. Subsequent starts will be instant."
else
    echo "CodeBERT classifier found — skipping training."
fi
echo ""

exec python3 -m uvicorn api.server:app --host 0.0.0.0 --port 8000
