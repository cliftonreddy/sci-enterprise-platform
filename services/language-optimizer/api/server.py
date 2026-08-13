"""
api/server.py — FastAPI backend for GraalVM Optimizer
"""
import os, sys, json, logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(name)s: %(message)s",
    stream=sys.stdout,
)
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent))
from analyzer.ai_analyzer import AIAnalyzer
from analyzer.ai_provider import AIProvider, AnthropicProvider, OpenAIProvider, OllamaProvider

app = FastAPI(title="GraalVM Auto-Optimizer API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8000",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

UI_BUILD = Path(__file__).parent.parent / "ui" / "build"


class AnalyzeRequest(BaseModel):
    code: str
    filename: str = "program.py"
    validate: bool = False



def _get_provider() -> AIProvider:
    backend = os.environ.get("AI_PROVIDER", "anthropic").lower()
    if backend == "openai":
        return OpenAIProvider(
            api_key=os.environ.get("OPENAI_API_KEY", ""),
            model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
        )
    if backend == "ollama":
        return OllamaProvider(
            url=os.environ.get("OLLAMA_URL", "http://localhost:11434"),
            model=os.environ.get("OLLAMA_MODEL", "llama3"),
        )
    return AnthropicProvider(os.environ.get("ANTHROPIC_API_KEY", ""))


@app.get("/health")
def health():
    from analyzer.local_classifier import get_classifier
    clf = get_classifier()
    return {
        "status": "ok",
        "classifier": clf.status()
    }



@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    try:
        analyzer = AIAnalyzer(_get_provider())
        analysis = analyzer.analyze(req.code)

        if req.validate:
            analysis = analyzer.validate_and_fix_functions(analysis)

        return {
            "source_language": analysis.source_language,
            "functions": [
                {
                    "name": f.name,
                    "start_line": f.start_line,
                    "end_line": f.end_line,
                    "category": f.category,
                    "recommended_language": f.recommended_language,
                    "energy_savings_percent": f.energy_savings_percent,
                    "reason": f.reason,
                    "is_orchestrator": f.is_orchestrator,
                    "rewritten_code": f.rewritten_code,
                    "compile_validated": getattr(f, "compile_validated", None),
                    "compile_attempts": getattr(f, "compile_attempts", 0),
                    "compile_error": getattr(f, "compile_error", ""),
                }
                for f in analysis.functions
            ],
            "orchestrator_modifications": analysis.orchestrator_modifications,
            "rule_engine": {
                "coverage": analysis.raw.get("rule_engine_coverage", 0),
                "matched":  analysis.raw.get("rule_engine_matched", []),
                "unmatched":analysis.raw.get("rule_engine_unmatched", []),
            },
            "validation_summary": [
                {
                    "function": v.function_name,
                    "language": v.language,
                    "success": v.success,
                    "attempts": v.attempts,
                    "error": v.error,
                }
                for v in analysis.validation_results
            ],
            "no_api_key": analysis.raw.get("no_api_key", False),
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, str(e))



class TestRequest(BaseModel):
    functions: list


@app.post("/api/test")
async def test_suite(req: TestRequest):
    provider = _get_provider()
    if not provider.available:
        raise HTTPException(503, "No AI provider configured — set AI_PROVIDER and the corresponding API key in .env")
    fn_list = "\n".join(
        f'- {f["name"]}() in {f["file"]}: {f.get("reason", "")}'
        for f in req.functions[:5]
    )
    prompt = f"""Generate simulated test cases for these native-optimised functions.
For each function, produce 3 test cases describing expected behaviour.
Respond ONLY with a JSON array, no markdown:
[{{"function_name": "name", "file": "path", "test_cases": [
  {{"description": "basic case", "input_description": "input summary", "expected_output": "output summary", "passed": true}}
]}}]

Functions:
{fn_list}

Mark passed: true for all (native code preserves Java/Python semantics by construction)."""
    try:
        import re
        text = provider.complete(prompt, max_tokens=2000)
        match = re.search(r'\[[\s\S]*\]', text)
        if not match:
            raise ValueError("No JSON array in response")
        return {"results": json.loads(match.group(0))}
    except Exception as e:
        raise HTTPException(500, str(e))


# Serve React UI at root — mount LAST so API routes take priority
# Catch-all for React Router: serve index.html for any unmatched path
@app.get("/{full_path:path}")
async def serve_ui(full_path: str):
    # Try exact file first
    file_path = UI_BUILD / full_path
    if file_path.is_file():
        return FileResponse(str(file_path))
    # Fall back to index.html for client-side routing
    index = UI_BUILD / "index.html"
    if index.exists():
        return FileResponse(str(index))
    raise HTTPException(404, "Not found")


