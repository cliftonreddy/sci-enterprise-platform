"""
analyzer/rule_engine.py — V1 Rule Engine

Pure pattern matching on code structure.
No ML, no API calls, instant results.
Covers the 10 SLE'17 benchmark categories with high confidence.

Returns RuleMatch objects that feed directly into the analysis pipeline.
Claude is only called for functions the rule engine can't classify confidently.
"""
import re
import ast
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple

# ── SLE'17 energy table (normalized, C=1.00) ─────────────────────────────────
SLE17_ENERGY = {
    "C":          1.00,
    "Rust":       1.03,
    "C++":        1.34,
    "Ada":        1.70,
    "Java":       1.98,
    "Go":         3.23,
    "JavaScript": 4.45,
    "TypeScript": 4.69,
    "Python":     75.88,
    "Ruby":       15.83,
    "Perl":       79.58,
}

# ── Pattern definitions ───────────────────────────────────────────────────────
# Each pattern: (name, target_lang, energy_saving_vs_java_pct, sle17_category, description)

@dataclass
class Pattern:
    name:           str
    target_lang:    str
    energy_saving:  float        # % saving vs Java baseline
    sle17_category: str
    description:    str
    signals:        List[str]    # code signals that trigger this pattern
    confidence:     float = 0.90

PATTERNS: List[Pattern] = [

    # ── Sorting ───────────────────────────────────────────────────────────────
    Pattern(
        name="merge_sort",
        target_lang="C",
        energy_saving=52.0,
        sle17_category="sorting",
        description="Merge sort implementation — SLE'17: sorting → C saves 52% over Java",
        signals=["merge", "mergesort", "merge_sort"],
        confidence=0.95,
    ),
    Pattern(
        name="quick_sort",
        target_lang="C",
        energy_saving=52.0,
        sle17_category="sorting",
        description="Quick sort implementation — SLE'17: sorting → C saves 52% over Java",
        signals=["quicksort", "quick_sort", "partition"],
        confidence=0.95,
    ),
    Pattern(
        name="general_sort",
        target_lang="C",
        energy_saving=52.0,
        sle17_category="sorting",
        description="Sorting algorithm — SLE'17: sorting → C saves 52% over Java",
        signals=["sort", "bubble_sort", "insertion_sort", "heap_sort", "radix_sort"],
        confidence=0.85,
    ),

    # ── Numeric / tight loops ─────────────────────────────────────────────────
    Pattern(
        name="monte_carlo",
        target_lang="C",
        energy_saving=56.0,
        sle17_category="spectral_norm",
        description="Monte Carlo simulation — tight numeric loop → C saves 56% over Java",
        signals=["monte_carlo", "montecarlo", "simulation", "random", "gaussian",
                 "normal_dist", "num_simulations", "num_sims"],
        confidence=0.90,
    ),
    Pattern(
        name="matrix_multiply",
        target_lang="C",
        energy_saving=56.0,
        sle17_category="spectral_norm",
        description="Matrix multiplication — SLE'17: spectral-norm/n-body → C saves 56%",
        signals=["matrix_mult", "matmul", "dot_product", "matrix_multiply"],
        confidence=0.92,
    ),
    Pattern(
        name="nbody",
        target_lang="C",
        energy_saving=56.0,
        sle17_category="n_body",
        description="N-body physics simulation — SLE'17: n-body → C saves 56% over Java",
        signals=["nbody", "n_body", "gravity", "velocity", "position", "planet", "body"],
        confidence=0.88,
    ),
    Pattern(
        name="mandelbrot",
        target_lang="C",
        energy_saving=56.0,
        sle17_category="mandelbrot",
        description="Mandelbrot set computation — SLE'17: mandelbrot → C saves 56%",
        signals=["mandelbrot", "complex", "fractal", "escape", "iteration"],
        confidence=0.92,
    ),
    Pattern(
        name="amortization",
        target_lang="C",
        energy_saving=52.0,
        sle17_category="numeric",
        description="Iterative financial math — tight numeric loop → C saves 52% over Java",
        signals=["amortiz", "mortgage", "loan", "principal", "interest", "monthly_rate",
                 "payment", "balance"],
        confidence=0.88,
    ),

    # ── Recursion ─────────────────────────────────────────────────────────────
    Pattern(
        name="binary_trees",
        target_lang="Rust",
        energy_saving=40.0,
        sle17_category="binary_trees",
        description="Binary tree recursion — SLE'17: binary-trees → C++ saves 40% over Java",
        signals=["binary_tree", "binarytree", "btree", "tree_node", "left_child",
                 "right_child", "inorder", "preorder", "postorder"],
        confidence=0.93,
    ),
    Pattern(
        name="deep_recursion",
        target_lang="C++",
        energy_saving=40.0,
        sle17_category="recursion",
        description="Deep recursive algorithm — SLE'17: deep recursion → C++ saves 40%",
        signals=["ackermann", "fibonacci", "fib", "factorial", "recursive", "recurse"],
        confidence=0.85,
    ),
    Pattern(
        name="risk_score_recursive",
        target_lang="C++",
        energy_saving=40.0,
        sle17_category="recursion",
        description="Recursive weighted scoring — deep recursion → C++ saves 40% over Java",
        signals=["risk_score", "riskscore", "compute_risk", "credit_score", "weighted_score"],
        confidence=0.88,
    ),

    # ── Combinatorial / search ────────────────────────────────────────────────
    Pattern(
        name="combinatorial_search",
        target_lang="C",
        energy_saving=58.0,
        sle17_category="k_nucleotide",
        description="Combinatorial window search — SLE'17: k-nucleotide → C saves 58%",
        signals=["fraud", "anomaly", "pattern_detect", "window", "velocity",
                 "combinatorial", "knucleotide", "k_nucleotide"],
        confidence=0.88,
    ),
    Pattern(
        name="hash_map_counting",
        target_lang="Rust",
        energy_saving=58.0,
        sle17_category="k_nucleotide",
        description="Hash map frequency counting — SLE'17: k-nucleotide → Rust saves 58%",
        signals=["frequency", "count", "histogram", "word_count", "char_count",
                 "kmer", "k_mer", "nucleotide", "HashMap", "merge"],
        confidence=0.90,
    ),

    # ── String / regex ────────────────────────────────────────────────────────
    Pattern(
        name="regex_matching",
        target_lang="C",
        energy_saving=52.0,
        sle17_category="regex_redux",
        description="Regex pattern matching — SLE'17: regex-redux → C saves 52%",
        signals=["regex", "regexp", "pattern_match", "re.match", "re.search",
                 "re.compile", "re.findall"],
        confidence=0.88,
    ),

    # ── DNA / FASTA ───────────────────────────────────────────────────────────
    Pattern(
        name="fasta_dna",
        target_lang="C",
        energy_saving=55.0,
        sle17_category="fasta",
        description="DNA/FASTA sequence processing — SLE'17: fasta → C saves 55%",
        signals=["fasta", "dna", "nucleotide", "sequence", "codon", "genome",
                 "adenine", "thymine", "guanine", "cytosine"],
        confidence=0.95,
    ),

    # ── I/O heavy → keep or JavaScript ───────────────────────────────────────
    Pattern(
        name="io_heavy",
        target_lang="keep",
        energy_saving=0.0,
        sle17_category="io",
        description="I/O-heavy function — network/file I/O not energy-bottlenecked by language",
        signals=["read_file", "write_file", "open(", "http", "request", "response",
                 "socket", "network", "fetch", "download", "upload"],
        confidence=0.88,
    ),
    Pattern(
        name="string_formatting",
        target_lang="JavaScript",
        energy_saving=15.0,
        sle17_category="io",
        description="String formatting/templating — GraalJS V8 engine optimizes string ops",
        signals=["format", "template", "render", "stringify", "serialize", "json",
                 "html", "xml", "csv"],
        confidence=0.75,
    ),

    # ── Orchestration → always keep ───────────────────────────────────────────
    Pattern(
        name="orchestration",
        target_lang="keep",
        energy_saving=0.0,
        sle17_category="orchestration",
        description="Orchestration/coordination — keep in original language",
        signals=["main", "__init__", "setup", "teardown", "configure", "init",
                 "start", "stop", "run", "execute", "dispatch", "router", "controller",
                 "process", "processData", "pipeline", "workflow", "orchestrat",
                 "System.out", "println", "print(", "log."],
        confidence=0.93,
    ),
]

# ── Build signal → pattern index for fast lookup ──────────────────────────────
_SIGNAL_INDEX: Dict[str, List[Pattern]] = {}
for _p in PATTERNS:
    for _s in _p.signals:
        _SIGNAL_INDEX.setdefault(_s.lower(), []).append(_p)


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class RuleMatch:
    function_name:  str
    pattern_name:   str
    target_lang:    str
    energy_saving:  float
    sle17_category: str
    description:    str
    confidence:     float
    matched_signals: List[str] = field(default_factory=list)

@dataclass
class RuleMiss:
    function_name:    str
    reason:           str   # "no_signals_matched" | "low_confidence"
    best_pattern:     str = ""
    best_confidence:  float = 0.0
    matched_signals:  List[str] = field(default_factory=list)

@dataclass
class RuleEngineResult:
    matched:     List[RuleMatch]    # functions the rule engine handled
    unmatched:   List[str]          # function names to send to Tier 2/3
    near_misses: List[RuleMiss]     # why each unmatched function was dropped
    coverage:    float              # % of functions handled by rules


# ── Rule Engine ───────────────────────────────────────────────────────────────

class RuleEngine:
    """
    V1: pure signal matching on function names, parameter names, and body keywords.
    Fast, deterministic, zero API calls.
    """

    CONFIDENCE_THRESHOLD = 0.85

    def analyze(self, code: str, source_language: str) -> RuleEngineResult:
        """
        Parse code, extract functions, match against SLE'17 patterns.
        Returns matched functions and list of unmatched names for Claude.
        """
        functions   = self._extract_functions(code, source_language)
        matched     = []
        unmatched   = []
        near_misses = []

        for fn_name, fn_body, fn_params in functions:
            match = self._match_function(fn_name, fn_body, fn_params)
            if match and match.confidence >= self.CONFIDENCE_THRESHOLD:
                match.function_name = fn_name
                matched.append(match)
            else:
                unmatched.append(fn_name)
                if match:
                    near_misses.append(RuleMiss(
                        function_name=fn_name,
                        reason="low_confidence",
                        best_pattern=match.pattern_name,
                        best_confidence=match.confidence,
                        matched_signals=match.matched_signals,
                    ))
                else:
                    near_misses.append(RuleMiss(
                        function_name=fn_name,
                        reason="no_signals_matched",
                    ))

        total    = len(functions)
        coverage = len(matched) / total if total > 0 else 0.0

        return RuleEngineResult(
            matched=matched,
            unmatched=unmatched,
            near_misses=near_misses,
            coverage=coverage,
        )

    # GraalVM Sulong interop overhead per call (empirically ~0.05ms on GraalVM 22.3)
    # A function must have compute time > 10× this to benefit from native offload.
    # We estimate compute time from code complexity — if a function has no loops and
    # no array parameters, it almost certainly runs in < 0.05ms and is interop-dominated.
    INTEROP_OVERHEAD_MS = 0.05

    def _is_interop_dominated(self, name: str, body: str, params: List[str]) -> bool:
        """
        Return True if the function is too fast to benefit from native offload.
        Heuristic: functions with no loops AND no array/collection parameters
        complete in microseconds — the boundary crossing cost will dominate.
        """
        body_lower = body.lower()

        # Check for loops — any loop means meaningful iteration
        has_loop = bool(re.search(r'\b(for|while)\b', body_lower))

        # Check for array/collection parameters (bulk data = worthwhile to offload)
        has_array_param = any(
            re.search(r'(\[\]|List|Array|Collection|Map|Set)\s+' + re.escape(p), body)
            for p in params if p
        ) or '[]' in body[:body.find('{')+1 if '{' in body else 100]

        # Count non-empty, non-comment lines in body as a proxy for complexity
        code_lines = [
            l for l in body.splitlines()
            if l.strip() and not l.strip().startswith('//') and not l.strip().startswith('*')
        ]
        is_short = len(code_lines) < 8

        # Interop-dominated: no loops, no bulk data, trivially short
        return is_short and not has_loop and not has_array_param

    def _match_function(self, name: str, body: str, params: List[str]) -> Optional[RuleMatch]:
        """Score all patterns against this function, return best match."""
        combined = (name + " " + body + " " + " ".join(params)).lower()
        scores: Dict[str, Tuple[Pattern, float, List[str]]] = {}

        for signal, patterns in _SIGNAL_INDEX.items():
            if signal in combined:
                for p in patterns:
                    prev = scores.get(p.name, (p, 0.0, []))
                    hit_signals = prev[2] + [signal]
                    # More signals → higher confidence (up to pattern's max)
                    boosted = min(p.confidence, 0.70 + len(hit_signals) * 0.08)
                    scores[p.name] = (p, boosted, hit_signals)

        if not scores:
            return None

        best_name = max(scores, key=lambda k: scores[k][1])
        pattern, confidence, signals = scores[best_name]

        # If already marked keep, return as-is
        if pattern.target_lang == "keep":
            return RuleMatch(
                function_name=name,
                pattern_name=pattern.name,
                target_lang="keep",
                energy_saving=0.0,
                sle17_category=pattern.sle17_category,
                description=pattern.description,
                confidence=confidence,
                matched_signals=signals,
            )

        # Interop-dominated check — override to keep if computation is too trivial
        if self._is_interop_dominated(name, body, params):
            return RuleMatch(
                function_name=name,
                pattern_name="interop_dominated",
                target_lang="keep",
                energy_saving=0.0,
                sle17_category=pattern.sle17_category,
                description=(
                    f"INTEROP_DOMINATED — computation too fast for polyglot overhead to amortize. "
                    f"GraalVM boundary crossing ≈{self.INTEROP_OVERHEAD_MS}ms; "
                    f"function has no loops and no bulk array data. Keep in Java."
                ),
                confidence=0.95,
                matched_signals=signals,
            )

        return RuleMatch(
            function_name=name,
            pattern_name=pattern.name,
            target_lang=pattern.target_lang,
            energy_saving=pattern.energy_saving,
            sle17_category=pattern.sle17_category,
            description=pattern.description,
            confidence=confidence,
            matched_signals=signals,
        )

    def _extract_functions(self, code: str, language: str) -> List[Tuple[str, str, List[str]]]:
        """
        Extract (name, body, params) tuples from code.
        Uses Python AST for Python, regex heuristics for Java/JS/others.
        """
        if language == "python":
            return self._extract_python(code)
        elif language in ("java", "javascript", "ruby"):
            return self._extract_generic(code, language)
        else:
            return self._extract_generic(code, language)

    def _extract_python(self, code: str) -> List[Tuple[str, str, List[str]]]:
        """Use Python's AST for accurate function extraction."""
        results = []
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    name   = node.name
                    params = [a.arg for a in node.args.args]
                    body   = ast.unparse(node) if hasattr(ast, 'unparse') else ""
                    results.append((name, body, params))
        except SyntaxError:
            results = self._extract_generic(code, "python")
        return results

    def _extract_generic(self, code: str, language: str) -> List[Tuple[str, str, List[str]]]:
        """
        Regex-based extraction for Java, JavaScript, Ruby, etc.
        Less precise than AST but works cross-language.
        """
        results = []

        # Match: [modifiers] returnType functionName(params) { body }
        # Covers Java, JS, C-like syntax
        patterns = [
            # Java/C style: public static double myFunc(int x, double y) {
            r'(?:public|private|protected|static|final|async|def)?\s*'
            r'(?:\w+\s+)?(\w+)\s*\(([^)]*)\)\s*(?:throws\s+\w+\s*)?\{',
            # Python style: def my_func(x, y):
            r'def\s+(\w+)\s*\(([^)]*)\)\s*:',
            # JS arrow: const myFunc = (x, y) =>
            r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>',
        ]

        for pattern in patterns:
            for m in re.finditer(pattern, code):
                name   = m.group(1)
                params_str = m.group(2) if m.lastindex >= 2 else ""
                params = [p.strip().split()[-1] if p.strip() else ""
                          for p in params_str.split(",") if p.strip()]
                # Extract body heuristically — 500 chars after match
                start = m.start()
                body  = code[start:start+500]
                results.append((name, body, params))

        # Deduplicate by name and filter language keywords
        _KEYWORDS = {
            "for", "while", "if", "else", "switch", "try", "catch", "finally",
            "new", "return", "throw", "throws", "import", "package", "class",
            "interface", "enum", "extends", "implements", "do", "break",
            "continue", "case", "default", "instanceof", "super", "this",
            "function", "var", "let", "const", "async", "await",
        }
        seen = set()
        unique = []
        for item in results:
            if item[0] not in seen and item[0] not in _KEYWORDS:
                seen.add(item[0])
                unique.append(item)

        return unique

    def energy_saving_vs_source(self, target_lang: str, source_lang: str) -> float:
        """Calculate % energy saving of target vs source language per SLE'17."""
        source_energy = SLE17_ENERGY.get(source_lang.capitalize(), SLE17_ENERGY["Java"])
        target_energy = SLE17_ENERGY.get(target_lang, SLE17_ENERGY["C"])
        if source_energy <= 0:
            return 0.0
        return round((1 - target_energy / source_energy) * 100, 1)
