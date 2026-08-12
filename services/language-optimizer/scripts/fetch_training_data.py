"""
scripts/fetch_training_data.py

Fetches Java (and multi-language) code examples from two open-source sources:

  1. greensoftwarelab/Energy-Languages (GitHub)
     The actual SLE'17 benchmark programs — pre-labeled by benchmark name.

  2. Rosetta Code (MediaWiki API)
     Algorithm implementations categorized by task name.

Outputs formatted EXTRA_TRAINING_EXAMPLES entries to stdout.
Review the output, then append the entries to analyzer/training_data.py.

Usage:
    pip install requests
    python scripts/fetch_training_data.py > new_examples.py
    # Review new_examples.py, then paste into analyzer/training_data.py

Optional — set GITHUB_TOKEN env var to raise GitHub API rate limit (60 → 5000/hr):
    set GITHUB_TOKEN=ghp_...
    python scripts/fetch_training_data.py > new_examples.py
"""

import os, re, sys, time, textwrap, logging
from pathlib import Path
import requests

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
log = logging.getLogger(__name__)

# ── Category/target/saving tables ────────────────────────────────────────────

CATEGORY_TO_TARGET = {
    "sorting":        "C",
    "monte_carlo":    "C",
    "amortization":   "C",
    "combinatorial":  "C",
    "recursion_deep": "C++",
    "matrix":         "C",
    "hash_set":       "Rust",
    "nbody":          "C",
    "io":             "keep",
    "orchestration":  "keep",
    "trivial":        "keep",
    "fasta":          "C",
}

CATEGORY_SAVINGS = {
    "sorting":        52,
    "monte_carlo":    56,
    "amortization":   52,
    "combinatorial":  58,
    "recursion_deep": 40,
    "matrix":         56,
    "hash_set":       58,
    "nbody":          56,
    "io":             0,
    "orchestration":  0,
    "trivial":        0,
    "fasta":          55,
}

# ── Source 1: greensoftwarelab/Energy-Languages ───────────────────────────────
# Maps benchmark directory names → SLE'17 categories
ENERGY_LANGUAGES_MAP = {
    "binary-trees":       "recursion_deep",
    "fasta":              "fasta",
    "k-nucleotide":       "hash_set",
    "mandelbrot":         "matrix",
    "n-body":             "nbody",
    "spectral-norm":      "matrix",
    "fannkuch-redux":     "combinatorial",
    "regex-redux":        "io",
    "pidigits":           "combinatorial",
    "reverse-complement": "hash_set",
}

ENERGY_LANGUAGES_REPO = "greensoftwarelab/Energy-Languages"
ENERGY_LANGUAGES_JAVA_PATH = "Java"


# ── Source 2: Rosetta Code ────────────────────────────────────────────────────
# Maps category → list of Rosetta Code task page titles
ROSETTA_TASKS = {
    "sorting": [
        "Sorting algorithms/Bubble sort",
        "Sorting algorithms/Merge sort",
        "Sorting algorithms/Quicksort",
        "Sorting algorithms/Heapsort",
        "Sorting algorithms/Insertion sort",
        "Sorting algorithms/Shell sort",
        "Sorting algorithms/Radix sort",
        "Sorting algorithms/Cocktail sort",
    ],
    "monte_carlo": [
        "Monty Hall problem",
        "Pi Monte Carlo method",
        "Statistics/Normal distribution",
    ],
    "recursion_deep": [
        "Fibonacci sequence",
        "Towers of Hanoi",
        "Ackermann function",
        "Tree traversal",
        "Binary search",
        "Depth-first search",
    ],
    "hash_set": [
        "Word frequency",
        "Letter frequency",
        "Count occurrences of a substring",
        "Determine if a string has all unique characters",
    ],
    "matrix": [
        "Matrix multiplication",
        "Matrix transposition",
        "Gaussian elimination",
        "LU decomposition",
    ],
    "combinatorial": [
        "Knapsack problem/0-1",
        "Levenshtein distance",
        "Combinations",
        "Permutations",
        "Longest common subsequence",
    ],
    "nbody": [
        "N-body problem",
    ],
    "fasta": [
        "FASTA format",
        "Bioinformatics/base count",
    ],
}

ROSETTA_API = "https://rosettacode.org/w/api.php"


# ── GitHub helpers ────────────────────────────────────────────────────────────

def _gh_headers():
    token = os.environ.get("GITHUB_TOKEN", "")
    h = {"Accept": "application/vnd.github.v3+json"}
    if token:
        h["Authorization"] = f"token {token}"
    return h


def _gh_get(url):
    r = requests.get(url, headers=_gh_headers(), timeout=15)
    if r.status_code == 403:
        log.warning("GitHub rate limited — set GITHUB_TOKEN env var to increase limit")
        return None
    r.raise_for_status()
    return r.json()


def fetch_energy_languages():
    """
    Fetch Java source files from greensoftwarelab/Energy-Languages.
    Returns list of (code, category) tuples.
    """
    log.info("\n-- greensoftwarelab/Energy-Languages ----------------------------")
    base = f"https://api.github.com/repos/{ENERGY_LANGUAGES_REPO}/contents/{ENERGY_LANGUAGES_JAVA_PATH}"
    entries = _gh_get(base)
    if entries is None:
        return []

    results = []
    for entry in entries:
        if entry["type"] != "dir":
            continue
        benchmark = entry["name"]
        category = ENERGY_LANGUAGES_MAP.get(benchmark)
        if category is None:
            log.info(f"  skip {benchmark} (no category mapping)")
            continue

        log.info(f"  {benchmark} → {category}")
        files = _gh_get(entry["url"])
        if not files:
            continue

        for f in files:
            if not f["name"].endswith(".java"):
                continue
            try:
                raw = requests.get(f["download_url"], timeout=15).text
                methods = extract_java_methods(raw)
                if methods:
                    for m in methods:
                        results.append((m, category))
                    log.info(f"    {f['name']}: {len(methods)} method(s)")
                else:
                    # Fall back to full file if no methods extracted
                    results.append((raw[:3000], category))
                    log.info(f"    {f['name']}: full file (no methods parsed)")
            except Exception as e:
                log.warning(f"    {f['name']}: {e}")
            time.sleep(0.2)

    return results


# ── Rosetta Code helpers ──────────────────────────────────────────────────────

def fetch_rosetta_java(task_title):
    """
    Fetch the Java code block(s) from a Rosetta Code task page.
    Returns list of Java code strings.
    """
    r = requests.get(ROSETTA_API, params={
        "action": "parse",
        "page":   task_title,
        "prop":   "wikitext",
        "format": "json",
    }, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    if r.status_code != 200:
        return []
    data = r.json()
    if "parse" not in data:
        return []

    wikitext = data["parse"]["wikitext"]["*"]

    # Extract Java sections — Rosetta Code uses:
    #   <syntaxhighlight lang="java">  or  lang="java5"  or  <lang java>
    blocks = re.findall(
        r'<syntaxhighlight[^>]+lang=["\']?java\w*["\']?[^>]*>(.*?)</syntaxhighlight>',
        wikitext, re.DOTALL | re.IGNORECASE,
    )
    blocks += re.findall(
        r'<lang\s+java\w*>(.*?)</lang>',
        wikitext, re.DOTALL | re.IGNORECASE,
    )

    # Clean and filter — skip trivial one-liners
    cleaned = []
    for b in blocks:
        b = b.strip()
        if len(b) > 100:
            cleaned.append(b)
    return cleaned


def fetch_rosetta():
    """
    Fetch Java implementations from Rosetta Code for all mapped tasks.
    Returns list of (code, category) tuples.
    """
    log.info("\n-- Rosetta Code -------------------------------------------------")
    results = []
    for category, tasks in ROSETTA_TASKS.items():
        for task in tasks:
            log.info(f"  {task} → {category}")
            try:
                blocks = fetch_rosetta_java(task)
                for b in blocks:
                    methods = extract_java_methods(b)
                    if methods:
                        for m in methods:
                            results.append((m, category))
                    else:
                        results.append((b[:3000], category))
                log.info(f"    {len(blocks)} block(s)")
            except Exception as e:
                log.warning(f"    {task}: {e}")
            time.sleep(0.5)   # be polite to Rosetta Code

    return results


# ── Java method extractor ─────────────────────────────────────────────────────

def extract_java_methods(source: str) -> list:
    """
    Extract individual public/private/protected Java method bodies from source.
    Uses brace-counting to find complete method boundaries.
    Returns list of method strings (~10-60 lines each).
    """
    methods = []
    # Match method signatures: optional annotations + modifiers + return type + name + params
    sig_pattern = re.compile(
        r'(?:@\w+\s*)*'                          # optional annotations
        r'(?:public|private|protected|static|\s)+'
        r'[\w<>\[\],\s]+'                         # return type
        r'\w+\s*\([^)]*\)\s*'                     # method name + params
        r'(?:throws\s+[\w,\s]+)?\s*\{',           # optional throws + opening brace
    )

    for match in sig_pattern.finditer(source):
        start = match.start()
        brace_pos = match.end() - 1   # position of opening {
        depth = 1
        i = brace_pos + 1
        while i < len(source) and depth > 0:
            if source[i] == '{':
                depth += 1
            elif source[i] == '}':
                depth -= 1
            i += 1
        body = source[start:i].strip()
        lines = body.count('\n') + 1
        # Keep methods between 5 and 80 lines
        if 5 <= lines <= 80:
            methods.append(body)

    return methods


# ── Output formatter ──────────────────────────────────────────────────────────

def format_entries(examples: list) -> str:
    """Format (code, category) pairs as training_data.py entries."""
    lines = []
    last_cat = None
    for code, category in examples:
        target  = CATEGORY_TO_TARGET[category]
        saving  = CATEGORY_SAVINGS[category]
        if category != last_cat:
            lines.append(f"\n    # -- {category.upper()} (fetched) --")
            last_cat = category
        # Escape backslashes and triple-quotes in code
        safe = code.replace("\\", "\\\\").replace('"""', r'\"\"\"')
        lines.append(f'    (\n"""{safe}\n""", "{category}", "{target}", {saving}),\n')
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

OUTPUT_FILE = "new_examples.py"


def main():
    all_examples = []

    energy_examples = fetch_energy_languages()
    log.info(f"\nEnergy-Languages: {len(energy_examples)} examples")
    all_examples.extend(energy_examples)

    rosetta_examples = fetch_rosetta()
    log.info(f"Rosetta Code: {len(rosetta_examples)} examples")
    all_examples.extend(rosetta_examples)

    if not all_examples:
        log.error("No examples fetched -- check network access and API rate limits")
        sys.exit(1)

    # Group by category for a summary
    from collections import Counter
    counts = Counter(cat for _, cat in all_examples)
    log.info("\n-- Summary ------------------------------------------------------")
    for cat in sorted(counts):
        log.info(f"  {cat:20s}: {counts[cat]} new examples")
    log.info(f"\nTotal: {len(all_examples)} new examples")

    # Write output file directly (avoids shell redirect encoding issues)
    out_path = Path(OUTPUT_FILE)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# -- AUTO-FETCHED TRAINING EXAMPLES -------------------------------------\n")
        f.write("# Generated by scripts/fetch_training_data.py\n")
        f.write("# Review before adding to EXTRA_TRAINING_EXAMPLES in analyzer/training_data.py\n\n")
        f.write(format_entries(all_examples))
        f.write("\n")

    log.info(f"\nWritten to: {out_path.resolve()}")


if __name__ == "__main__":
    main()
