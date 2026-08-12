"""
api/server.py — FastAPI backend for GraalVM Optimizer
"""
import os, sys, json, tempfile, shutil, zipfile, subprocess, logging
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
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
from analyzer.ai_analyzer import AIAnalyzer
from analyzer.ai_provider import AIProvider, AnthropicProvider, OpenAIProvider, OllamaProvider
from generator.code_generator import PackageGenerator

app = FastAPI(title="GraalVM Auto-Optimizer API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UI_BUILD = Path(__file__).parent.parent / "ui" / "build"


class AnalyzeRequest(BaseModel):
    code: str
    filename: str = "program.py"
    api_key: Optional[str] = None
    validate: bool = True    # compile-validate generated C/C++ code


class GenerateRequest(BaseModel):
    code: str
    filename: str = "program.py"
    api_key: Optional[str] = None


def _get_provider(req_key: Optional[str] = None) -> AIProvider:
    """Select AI provider from AI_PROVIDER env var; default is Anthropic."""
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
    # default: anthropic — req_key allows per-request override from UI
    return AnthropicProvider(req_key or os.environ.get("ANTHROPIC_API_KEY", ""))


@app.get("/health")
def health():
    from analyzer.local_classifier import get_classifier
    clf = get_classifier()
    return {
        "status": "ok",
        "classifier": clf.status()
    }


@app.get("/config.json")
def config():
    provider = _get_provider()
    return {
        "anthropicApiKey": os.environ.get("ANTHROPIC_API_KEY", ""),
        "aiProvider": os.environ.get("AI_PROVIDER", "anthropic"),
        "aiProviderAvailable": provider.available,
    }


@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    try:
        analyzer = AIAnalyzer(_get_provider(req.api_key))
        analysis = analyzer.analyze(req.code)

        # Validate and fix generated C/C++ code — compile with clang, retry on error
        validate = req.validate if hasattr(req, "validate") else True
        if validate:
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


@app.post("/api/generate")
async def generate(req: GenerateRequest):
    tmp = Path(tempfile.mkdtemp())
    try:
        analyzer = AIAnalyzer(_get_provider(req.api_key))
        analysis = analyzer.analyze(req.code)
        out_dir = tmp / "optimized"
        gen = PackageGenerator(analysis, req.code, req.filename, str(out_dir))
        gen.generate()

        zip_path = tmp / "polyglot_package.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in out_dir.rglob("*"):
                if f.is_file():
                    zf.write(f, f.relative_to(out_dir))

        return FileResponse(
            str(zip_path),
            media_type="application/zip",
            filename=f"polyglot_{Path(req.filename).stem}.zip",
        )
    except Exception as e:
        shutil.rmtree(tmp, ignore_errors=True)
        raise HTTPException(500, str(e))


class BenchmarkRequest(BaseModel):
    code: str
    filename: str = "program.java"
    api_key: Optional[str] = None


@app.post("/api/benchmark")
async def benchmark(req: BenchmarkRequest):
    """
    Analyze + generate the polyglot package, build the Docker image (which runs
    TestSuite to prove correctness), then run benchmark.sh twice (Java path and
    native path) and return combined JSON results with energy comparisons.
    """
    tmp = Path(tempfile.mkdtemp())
    try:
        # 1. Analyze and generate package
        analyzer = AIAnalyzer(_get_provider(req.api_key))
        analysis = analyzer.analyze(req.code)
        out_dir = tmp / "optimized"
        gen = PackageGenerator(analysis, req.code, req.filename, str(out_dir))
        gen.generate()

        if not (out_dir / "BenchmarkSuite.java").exists():
            raise HTTPException(400, "No benchmarkable functions found in this file.")

        # 2. Build Docker image (runs TestSuite — fails fast if native code is broken)
        image_tag = f"graal-bench-{tmp.name}"
        build_result = subprocess.run(
            ["docker", "build", "-t", image_tag, "."],
            cwd=str(out_dir),
            capture_output=True, text=True, timeout=600
        )
        if build_result.returncode != 0:
            # Docker build log (layer output) goes to stdout; metadata/errors to stderr
            build_log = (build_result.stdout or "") + "\n" + (build_result.stderr or "")
            raise HTTPException(500, f"Docker build failed:\n{build_log[-4000:]}")

        # Run benchmark.sh once — it emits both Java and native passes with markers
        bench_result = subprocess.run(
            ["docker", "run", "--rm", "--entrypoint", "bash", image_tag, "/app/benchmark.sh"],
            capture_output=True, text=True, timeout=600
        )
        output = bench_result.stdout + bench_result.stderr

        def _parse_pass(output: str, mode: str) -> list:
            if mode == "java":
                start_marker, end_marker = "===JAVA_PASS===", "===NATIVE_PASS==="
            else:
                start_marker, end_marker = "===NATIVE_PASS===", "===DONE==="
            start = output.find(start_marker)
            end   = output.find(end_marker)
            if start == -1 or end == -1:
                return []
            segment = output[start + len(start_marker):end].strip()
            try:
                return json.loads(segment)
            except Exception:
                return []

        java_results   = _parse_pass(output, "java")
        native_results = _parse_pass(output, "native")

        # 3. Merge and compute energy savings
        POWER_C    = 1.00
        POWER_JAVA = 2.98
        # Minimum speedup to include in results.
        # Functions below this threshold are interop-overhead-dominated:
        # the GraalVM boundary crossing cost exceeds any compute savings.
        MIN_SPEEDUP = 1.20
        merged = []
        skipped = []
        java_by_fn = {r["function"]: r for r in java_results}
        for nr in native_results:
            fn   = nr["function"]
            jr   = java_by_fn.get(fn)
            if not jr:
                continue
            java_mean   = jr["meanMs"]
            native_mean = nr["meanMs"]
            speedup      = java_mean / native_mean if native_mean > 0 else 0
            energy_saving = 1.0 - (native_mean * POWER_C) / (java_mean * POWER_JAVA) if java_mean > 0 else 0

            if speedup < MIN_SPEEDUP:
                skipped.append({
                    "function":   fn,
                    "reason":     "interop-overhead-dominated",
                    "speedup":    round(speedup, 2),
                    "javaMeanMs": round(java_mean, 4),
                    "nativeMeanMs": round(native_mean, 4),
                })
                continue

            merged.append({
                "function":        fn,
                "targetLanguage":  nr.get("targetLanguage", ""),
                "javaMeanMs":      round(java_mean,   4),
                "nativeMeanMs":    round(native_mean, 4),
                "speedup":         round(speedup,     2),
                "energySavingPct": round(energy_saving * 100, 1),
            })

        # Extract BenchmarkSuite diagnostics from stderr for debugging
        diag_lines = [l for l in bench_result.stderr.splitlines() if "[BenchmarkSuite]" in l]

        return {"results": merged, "skipped": skipped, "imageTag": image_tag,
                "diagnostics": diag_lines}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


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


# ── Folder generate endpoint ──────────────────────────────────────────────────

class FolderFile(BaseModel):
    path: str
    code: str

class GenerateFolderRequest(BaseModel):
    files: list[FolderFile]
    api_key: Optional[str] = None


@app.post("/api/generate-folder")
async def generate_folder(req: GenerateFolderRequest):
    """Analyze all files and produce one unified polyglot package zip."""
    tmp = Path(tempfile.mkdtemp())
    out_dir = tmp / "polyglot_package"
    out_dir.mkdir()

    try:
        analyzer = AIAnalyzer(_get_provider(req.api_key))

        for f in req.files:
            file_path = Path(f.path)
            analysis = analyzer.analyze(f.code)
            file_out = out_dir / file_path.parent
            file_out.mkdir(parents=True, exist_ok=True)
            gen = PackageGenerator(analysis, f.code, file_path.name, str(file_out))
            gen.generate()

        # Single build.sh that calls all sub build scripts
        sub_builds = list(out_dir.rglob("build.sh"))
        master_build = ["#!/bin/bash", "set -e", "DIR=$(dirname \"$0\")", ""]
        for sb in sub_builds:
            rel = sb.relative_to(out_dir)
            master_build.append(f'bash "$DIR/{rel}"')
        master_build.append('\necho "✅ All modules built"')
        (out_dir / "build.sh").write_text("\n".join(master_build))
        (out_dir / "build.sh").chmod(0o755)

        zip_path = tmp / "polyglot_package.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in out_dir.rglob("*"):
                if f.is_file():
                    zf.write(f, f.relative_to(out_dir))

        return FileResponse(
            str(zip_path),
            media_type="application/zip",
            filename="polyglot_package.zip",
        )
    except Exception as e:
        shutil.rmtree(tmp, ignore_errors=True)
        raise HTTPException(500, str(e))
