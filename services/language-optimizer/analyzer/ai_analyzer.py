"""
analyzer/ai_analyzer.py
Calls Claude API to:
1. Detect source language
2. Identify each function/method
3. Map each to the best language per SLE'17 paper
4. Generate the rewritten code in the target language
"""
import os, json, re, requests, logging
from dataclasses import dataclass, field
from typing import List, Optional
from analyzer.code_validator import validate_and_fix, ValidationResult
from analyzer.rule_engine import RuleEngine, RuleMatch, SLE17_ENERGY
from analyzer.local_classifier import get_classifier, LocalClassification

log = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-20250514"

SUPPORTED_LANGUAGES = {
    "python":     {"ext": ".py",   "runner": "graalpy",    "graal_id": "python"},
    "java":       {"ext": ".java", "runner": "java",       "graal_id": "java"},
    "javascript": {"ext": ".js",   "runner": "node",       "graal_id": "js"},
    "nodejs":     {"ext": ".js",   "runner": "node",       "graal_id": "js"},
    "ruby":       {"ext": ".rb",   "runner": "ruby",       "graal_id": "ruby"},
    "r":          {"ext": ".r",    "runner": "Rscript",    "graal_id": "R"},
}

TARGET_LANGUAGES = {
    "C":          {"ext": ".c",   "compile": "clang -O3 -emit-llvm -c {src} -o {out}",  "graal_id": "llvm"},
    "C++":        {"ext": ".cpp", "compile": "clang++ -O3 -emit-llvm -c {src} -o {out}", "graal_id": "llvm"},
    "Rust":       {"ext": ".rs",  "compile": "rustc --emit=llvm-bc -O --crate-type=cdylib {src} -o {out}", "graal_id": "llvm"},
    "JavaScript": {"ext": ".js",  "compile": None,                                        "graal_id": "js"},
}

DETECT_AND_ANALYZE_PROMPT = """You are an expert in programming language energy efficiency based on the SLE'17 paper "Energy Efficiency Across Programming Languages" (Pereira et al., 2017) and GraalVM polyglot architecture.

Analyze the following code and respond with ONLY a JSON object (no markdown, no explanation):

{
  "source_language": "python|java|javascript|ruby|r",
  "functions": [
    {
      "name": "functionName",
      "start_line": 10,
      "end_line": 20,
      "category": "fasta|binary_trees|sorting|recursion_deep|combinatorial|hash_set|numeric|io|orchestration|trivial",
      "recommended_language": "C|C++|Rust|JavaScript|keep",
      "energy_savings_percent": 45,
      "reason": "one sentence citing paper benchmark",
      "is_orchestrator": false,
      "dependencies": ["otherFunctionName"],
      "signature": "return_type function_name(param_type param_name, ...)",
      "rewritten_code": "complete rewritten function in recommended language, ready to compile"
    }
  ],
  "orchestrator_modifications": "description of what to inject into the original file to call GraalVM polyglot context",
  "graalvm_imports": "any imports needed at top of orchestrator file"
}

BENCHMARK DETECTION RULES (from SLE'17 paper):
- FASTA pattern (BlockingQueue/AtomicInteger/byte arrays/DNA): Rust wins (memory safe, 1.03x energy vs C)
- BINARY-TREES (recursive alloc/dealloc, tree traversal, graph): Rust wins - ownership model, 1.03x energy vs C
- K-NUCLEOTIDE (HashMap + string counting, string processing): Rust wins - safe hash maps
- MANDELBROT (complex number grid): C wins - SIMD
- SPECTRAL-NORM / N-BODY (matrix/physics math): C wins
- SORTING (merge/quick): C wins
- DEEP RECURSION (ackermann, fibonacci): C++ wins
- SIMPLE ITERATION / LOOPS: C wins (1.00x baseline)
- I/O HEAVY / STRING OPS: JavaScript wins (V8 engine, GraalJS)
- ORCHESTRATION / COORDINATION: keep in original language
- TRIVIAL (< 5 lines, print, simple math): keep in original language

GRAALVM POLYGLOT INTEROP RULES:
- For C/C++/Rust targets: compile to LLVM bitcode (.bc), load via polyglot.eval(language="llvm")
- For JavaScript targets: load via polyglot.eval(language="js")
- For Ruby targets: load via polyglot.eval(language="ruby")
- Functions marked "keep" stay in original language unchanged
- Orchestrator function (main/entry point) ALWAYS stays in original language
- The rewritten_code must be a COMPLETE, COMPILABLE function in the target language
- Include ALL necessary includes/imports in rewritten_code
- Use only simple types in function signatures (int, double, char*, long) for C/C++ FFI compatibility
- For C++: NEVER use <iostream>, <string>, <vector>, <map> or any STL — Sulong cannot resolve C++ stdlib symbols
- For array-returning functions: ALWAYS use explicit output buffer pattern: void fn(input_arr, int n, double* out, int out_n). Never sort/fill in-place — always write results to the out buffer.
- For functions returning any complex collection type (Map, List, Set, Collection, etc.) from any source
  language: use the flat array output buffer pattern so all logic runs natively with only 2 boundary crossings:
  * Map<String,Integer>: signature becomes (input_params..., char* keys_out, int key_stride, int* values_out, int max_entries) → returns int (actual entry count). Write each key null-padded to key_stride bytes.
  * Map<String,Double>: same but double* values_out
  * List<Double>/List<Float>: (input_params..., double* out, int max_entries) → returns int (count)
  * Set<String>: (input_params..., char* keys_out, int key_stride, int max_entries) → returns int (count)
  * For String input arrays: pass as (char* flat_buf, int n, int stride) — Java pre-flattens to stride-padded bytes

Code to analyze:
```
{code}
```"""

REWRITE_FUNCTION_PROMPT = """Rewrite the following {source_lang} function in {target_lang} for maximum energy efficiency.

Requirements:
- Complete, compilable {target_lang} code
- Include all necessary headers/imports at the top
- Use extern "C" linkage for C++ (for GraalVM LLVM interop)
- For C++: NEVER include <iostream>, <string>, <vector>, <map>, or any STL header — GraalVM Sulong
  cannot resolve C++ stdlib symbols (e.g. _ZNSt8ios_base4InitC1Ev). Use only C-compatible headers:
  <stdio.h>, <stdlib.h>, <math.h>, <string.h>, <stdint.h>. All output via return values or buffers.
- For Rust: use #[no_mangle] pub extern "C" fn for each exported function
- For Rust: use only primitive types in signatures (f64, i32, i64, *const f64, *mut f64 etc.)
- For Rust: add #![allow(non_snake_case, dead_code, unused_imports)] at top of file
- For functions that originally return Map/List/Set/Collection: use flat array output buffer pattern.
  All computation (hashing, counting, sorting, accumulating) stays in the native code — zero per-element
  boundary crossings. Java allocates output buffers before the call and reconstructs the collection after.
  * Map<String,Integer>: fn(inputs..., char* keys_out, int key_stride, int* values_out, int max_entries) → int
  * Map<String,Double>:  fn(inputs..., char* keys_out, int key_stride, double* values_out, int max_entries) → int
  * List<Double>:        fn(inputs..., double* out, int max_entries) → int
  * Set<String>:         fn(inputs..., char* keys_out, int key_stride, int max_entries) → int
  * String[] input args: flattened to (char* flat, int n, int stride) pairs — do NOT use char** pointers
- For Rust: use *const u8 / *mut u8 for string buffers, *mut i32/*mut f64 for value buffers
- For Rust: use unsafe pointer arithmetic to read/write flat buffers; no HashMap in the FFI signature
- For Rust: use std::collections::HashMap internally, then fill output buffers at the end
- For Rust: add #![allow(non_snake_case, dead_code, unused_imports)] at top of file
- Use only simple FFI-compatible types in the public signature (int, long, double, char*, void*)
- Add GraalVM polyglot export annotation if needed
- Optimize for energy efficiency per SLE'17 paper findings
- Function must have EXACTLY the same logical behavior as original

Original {source_lang} function:
```{source_lang}
{function_code}
```

Context (other functions this depends on):
```{source_lang}
{context_code}
```

Respond with ONLY the complete {target_lang} source code, no explanation, no markdown fences."""


@dataclass
class FunctionAnalysis:
    name: str
    start_line: int
    end_line: int
    category: str
    recommended_language: str
    energy_savings_percent: float
    reason: str
    is_orchestrator: bool
    dependencies: List[str]
    signature: str
    rewritten_code: str
    original_code: str = ""          # original source before rewrite (for re-generation)
    compile_validated: bool = False
    compile_attempts: int = 0
    compile_error: str = ""


@dataclass
class ValidationSummary:
    function_name: str
    language: str
    success: bool
    attempts: int
    error: str = ""
    bitcode_path: str = ""

@dataclass
class ProgramAnalysis:
    source_language: str
    functions: List[FunctionAnalysis]
    orchestrator_modifications: str
    graalvm_imports: str
    raw: dict = field(default_factory=dict)
    validation_results: List[ValidationSummary] = field(default_factory=list)


class AIAnalyzer:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-dangerous-direct-browser-access": "true",
        }
        self.rule_engine = RuleEngine()
        self.local_classifier = get_classifier()
        if self.local_classifier.available:
            log.info("[Analyzer] Tier 2 local classifier: ACTIVE")
        else:
            log.info("[Analyzer] Tier 2 local classifier: NOT AVAILABLE (Claude fallback only)")

    def _call_api(self, prompt: str, max_tokens: int = 4000) -> str:
        payload = {
            "model": MODEL,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}]
        }
        r = requests.post(ANTHROPIC_API_URL, headers=self.headers, json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise RuntimeError(f"API error: {data['error']['message']}")
        return data["content"][0]["text"]

    def analyze(self, code: str, source_language: str = None) -> ProgramAnalysis:
        """
        V1 hybrid pipeline:
        1. Rule engine handles known SLE'17 patterns instantly (no API call)
        2. Claude handles unrecognized patterns and generates all code
        """
        # ── Step 1: Detect language if not provided ───────────────────────────
        if not source_language:
            source_language = self._detect_language_fast(code)

        # ── Step 2: Run rule engine ───────────────────────────────────────────
        rule_result = self.rule_engine.analyze(code, source_language)
        log.info(f"Rule engine: {len(rule_result.matched)} matched, "
                 f"{len(rule_result.unmatched)} unmatched "
                 f"(coverage: {rule_result.coverage:.0%})")

        # ── Step 2b: Tier 2 — local CodeBERT classifier for unmatched functions ──
        local_matches = {}  # function_name -> LocalClassification
        if self.local_classifier.available and rule_result.unmatched:
            log.info(f"[Tier 2] Classifying {len(rule_result.unmatched)} unmatched functions...")
            for fn_name in rule_result.unmatched:
                # Extract function body from source code
                fn_code = self._extract_function(code, fn_name)
                if fn_code:
                    result = self.local_classifier.classify(fn_code)
                    if result:
                        local_matches[fn_name] = result
                        log.info(f"[Tier 2] {fn_name}: {result.category} → "
                                 f"{result.target_language} ({result.confidence:.0%})")
                    else:
                        log.info(f"[Tier 2] {fn_name}: low confidence → Claude fallback")

        still_unmatched = [f for f in rule_result.unmatched if f not in local_matches]
        log.info(f"[Tier 2] Handled {len(local_matches)} functions, "
                 f"{len(still_unmatched)} sent to Claude")

        # ── Step 3: Claude for full analysis (enriches rule matches + handles unknowns) ──
        hint = ""
        if rule_result.matched:
            hint += "\n\nRULE ENGINE PRE-ANALYSIS (high confidence, do not override unless clearly wrong):\n"
            for m in rule_result.matched:
                hint += (f"- {m.function_name}(): pattern={m.pattern_name}, "
                         f"target={m.target_lang}, confidence={m.confidence:.0%}, "
                         f"saving={m.energy_saving}%\n")

        if local_matches:
            hint += "\n\nLOCAL MODEL PRE-ANALYSIS (CodeBERT classifier, do not override unless clearly wrong):\n"
            for fn_name, lc in local_matches.items():
                hint += (f"- {fn_name}(): category={lc.category}, "
                         f"target={lc.target_language}, confidence={lc.confidence:.0%}, "
                         f"saving={lc.energy_saving}%\n")

        prompt = DETECT_AND_ANALYZE_PROMPT.replace("{code}", code) + hint
        raw_response = self._call_api(prompt, max_tokens=6000)

        json_match = re.search(r'\{[\s\S]*\}', raw_response)
        if not json_match:
            raise ValueError(f"No JSON in response: {raw_response[:200]}")

        data = json.loads(json_match.group(0))

        # ── Step 4: Merge rule engine + local classifier results into Claude's output ──
        rule_by_name  = {m.function_name: m for m in rule_result.matched}

        functions = []
        for f in data.get("functions", []):
            fn_name    = f.get("name", "unknown")
            rule_match = rule_by_name.get(fn_name)
            local_match = local_matches.get(fn_name)

            # Priority: rule engine (highest) → local model → Claude
            if rule_match and rule_match.confidence >= 0.85:
                recommended = rule_match.target_lang
                saving      = rule_match.energy_saving
                reason      = (f"{rule_match.description} "
                               f"[Rule engine: {rule_match.confidence:.0%} confidence, "
                               f"signals: {', '.join(rule_match.matched_signals[:3])}]")
                source_tag  = "rule_engine"
            elif local_match and local_match.confidence >= 0.75:
                recommended = local_match.target_language
                saving      = local_match.energy_saving
                reason      = (f"SLE'17 category '{local_match.category}' detected by "
                               f"CodeBERT classifier ({local_match.confidence:.0%} confidence)")
                source_tag  = "local_model"
            else:
                recommended = f.get("recommended_language", "keep")
                saving      = f.get("energy_savings_percent", 0)
                reason      = f.get("reason", "")
                source_tag  = "claude"

            functions.append(FunctionAnalysis(
                name=fn_name,
                start_line=f.get("start_line", 0),
                end_line=f.get("end_line", 0),
                category=f.get("category", rule_match.sle17_category if rule_match else "unknown"),
                recommended_language=recommended,
                energy_savings_percent=saving,
                reason=reason,
                is_orchestrator=f.get("is_orchestrator", False),
                dependencies=f.get("dependencies", []),
                signature=f.get("signature", ""),
                rewritten_code=f.get("rewritten_code", ""),
                original_code=self._extract_function(code, fn_name) or "",
            ))

        analysis = ProgramAnalysis(
            source_language=data.get("source_language", source_language),
            functions=functions,
            orchestrator_modifications=data.get("orchestrator_modifications", ""),
            graalvm_imports=data.get("graalvm_imports", ""),
            raw=data,
        )

        # Attach rule engine stats for transparency
        analysis.raw["rule_engine_coverage"] = rule_result.coverage
        analysis.raw["rule_engine_matched"]  = [m.function_name for m in rule_result.matched]
        analysis.raw["rule_engine_unmatched"]= rule_result.unmatched

        return analysis

    def _extract_function(self, code: str, fn_name: str) -> Optional[str]:
        """Extract a function's source code by name for local classifier input."""
        import re
        # Match Java/Python/JS function definitions
        patterns = [
            rf'(?:public|private|protected|static|\s)+[\w<>\[\]]+\s+{re.escape(fn_name)}\s*\([^{{]*\)\s*\{{',
            rf'def\s+{re.escape(fn_name)}\s*\([^:]*\):',
            rf'(?:function\s+{re.escape(fn_name)}|{re.escape(fn_name)}\s*=\s*(?:function|\())',
        ]
        for pattern in patterns:
            m = re.search(pattern, code)
            if m:
                start = m.start()
                # Return up to 1000 chars of context
                return code[start:start+1000]
        return None

    def _detect_language_fast(self, code: str) -> str:
        """Quick language detection without API call."""
        if "def " in code and "import " in code:     return "python"
        if "public class" in code or "void " in code: return "java"
        if "function " in code or "const " in code:   return "javascript"
        if "def " in code and "end" in code:           return "ruby"
        return "python"  # safe default

    @staticmethod
    def _detect_code_language(code: str) -> str:
        """Detect whether generated code is C, C++, or Rust by content."""
        if ('use std::' in code or '#[no_mangle]' in code
                or 'pub fn ' in code or 'pub extern' in code):
            return "Rust"
        if ('std::' in code or 'template<' in code
                or 'namespace ' in code or 'cout ' in code):
            return "C++"
        return "C"

    def validate_and_fix_functions(self, analysis: "ProgramAnalysis") -> "ProgramAnalysis":
        """
        For each function that was rewritten to C or C++,
        try to compile it and fix any errors using Claude.
        Updates analysis.functions in-place with fixed code.
        """
        for fn in analysis.functions:
            if fn.recommended_language not in ("C", "C++", "Rust") or fn.is_orchestrator:
                continue
            if not fn.rewritten_code:
                continue

            # Detect language mismatch: Claude wrote code in a different language
            # than what the rule engine / CodeBERT override selected.
            code_lang = self._detect_code_language(fn.rewritten_code)
            if code_lang != fn.recommended_language and fn.original_code:
                log.info(f"  Language mismatch for {fn.name}: "
                         f"code is {code_lang}, target is {fn.recommended_language} — regenerating")
                fn.rewritten_code = self.rewrite_function(
                    source_lang=analysis.source_language,
                    target_lang=fn.recommended_language,
                    function_code=fn.original_code,
                )

            log.info(f"Validating {fn.name} ({fn.recommended_language})...")
            result = validate_and_fix(
                code=fn.rewritten_code,
                lang=fn.recommended_language,
                func_name=fn.name,
                api_caller=self._call_api
            )

            fn.rewritten_code = result.code
            fn.compile_validated = result.success
            fn.compile_attempts  = result.attempts
            fn.compile_error     = result.error if not result.success else ""

            analysis.validation_results.append(ValidationSummary(
                function_name=fn.function_name if hasattr(fn, "function_name") else fn.name,
                language=fn.recommended_language,
                success=result.success,
                attempts=result.attempts,
                error=result.error,
                bitcode_path=result.bitcode_path,
            ))

        return analysis

    def rewrite_function(self, source_lang: str, target_lang: str,
                         function_code: str, context_code: str = "") -> str:
        prompt = (REWRITE_FUNCTION_PROMPT
                  .replace("{source_lang}", source_lang)
                  .replace("{target_lang}", target_lang)
                  .replace("{function_code}", function_code)
                  .replace("{context_code}", context_code))
        return self._call_api(prompt, max_tokens=3000)
