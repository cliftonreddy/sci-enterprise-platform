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

exec python3 -m uvicorn api.server:app --host 0.0.0.0 --port 8000
