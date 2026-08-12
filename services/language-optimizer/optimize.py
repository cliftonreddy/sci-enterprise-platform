#!/usr/bin/env python3
"""
optimize.py — GraalVM Auto-Optimizer CLI
─────────────────────────────────────────
Paste any program, get back a GraalVM polyglot package that runs
with the same command as the original.

Usage:
    python optimize.py <source_file> [--output <dir>] [--api-key <key>]

Examples:
    python optimize.py my_program.py
    python optimize.py BinaryTrees.java --output ./out
    python optimize.py server.js --api-key sk-ant-...
"""
import sys, os, json, argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from analyzer.ai_analyzer import AIAnalyzer
from generator.code_generator import PackageGenerator


def get_api_key(args_key: str = None) -> str:
    key = (args_key
           or os.environ.get("ANTHROPIC_API_KEY")
           or _read_env_file())
    if not key or not key.startswith("sk-"):
        print("❌ No valid Anthropic API key found.")
        print("   Set ANTHROPIC_API_KEY env var, or pass --api-key sk-ant-...")
        sys.exit(1)
    return key


def _read_env_file() -> str:
    for p in [Path(".env"), Path(__file__).parent / ".env"]:
        if p.exists():
            for line in p.read_text().splitlines():
                if line.startswith("ANTHROPIC_API_KEY="):
                    return line.split("=", 1)[1].strip()
    return ""


def main():
    parser = argparse.ArgumentParser(
        description="GraalVM Auto-Optimizer — splits any program into polyglot native components",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("source_file", help="Source file to optimize (any language)")
    parser.add_argument("--output", "-o", default=None,
                        help="Output directory (default: ./optimized/<program_name>)")
    parser.add_argument("--api-key", "-k", default=None,
                        help="Anthropic API key (or set ANTHROPIC_API_KEY env var)")
    parser.add_argument("--no-docker", action="store_true",
                        help="Skip Dockerfile generation")
    parser.add_argument("--report-only", action="store_true",
                        help="Show analysis report without generating files")
    args = parser.parse_args()

    source_path = Path(args.source_file)
    if not source_path.exists():
        print(f"❌ File not found: {source_path}")
        sys.exit(1)

    source_code = source_path.read_text()
    output_dir = Path(args.output) if args.output else Path("optimized") / source_path.stem
    api_key = get_api_key(args.api_key)

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║          GraalVM Auto-Optimizer                              ║
║  "Energy Efficiency Across Programming Languages" (SLE'17)   ║
╚══════════════════════════════════════════════════════════════╝

▶ Analyzing: {source_path.name}
▶ Output:    {output_dir}
""")

    # ── Step 1: AI Analysis ───────────────────────────────────────────────────
    print("🤖 Step 1/3 — AI analyzing code and mapping functions to optimal languages...")
    analyzer = AIAnalyzer(api_key)
    try:
        analysis = analyzer.analyze(source_code)
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        sys.exit(1)

    # Print analysis summary
    print(f"\n   Detected language: {analysis.source_language.upper()}")
    print(f"   Functions found:   {len(analysis.functions)}\n")
    print(f"   {'Function':<25} {'→ Target':<15} {'Saving':<10} Reason")
    print(f"   {'─'*25} {'─'*15} {'─'*10} {'─'*40}")
    for fn in analysis.functions:
        target = fn.recommended_language if not fn.is_orchestrator else "keep"
        saving = f"~{fn.energy_savings_percent:.0f}%" if fn.energy_savings_percent > 0 else "—"
        print(f"   {fn.name:<25} {target:<15} {saving:<10} {fn.reason[:45]}")

    if args.report_only:
        print("\n(--report-only mode: no files generated)")
        return

    # ── Step 2: Generate Package ──────────────────────────────────────────────
    print(f"\n⚙️  Step 2/3 — Generating polyglot package...")
    generator = PackageGenerator(analysis, source_code, str(source_path), str(output_dir))
    manifest = generator.generate()

    # ── Step 3: Summary ───────────────────────────────────────────────────────
    moved = [f for f in analysis.functions
             if f.recommended_language != "keep" and not f.is_orchestrator]
    avg_saving = sum(f.energy_savings_percent for f in moved) / len(moved) if moved else 0

    print(f"""
✅ Step 3/3 — Package ready!

   📁 Output directory:  {output_dir}/
   📄 Orchestrator:      {Path(manifest['orchestrator_file']).name}
   🔧 Native modules:    {len(manifest['native_files'])} file(s)
   📊 Report:            {output_dir}/REPORT.md
   🐳 Docker:            {output_dir}/Dockerfile
   ⚡ Avg energy saving: ~{avg_saving:.0f}%

╔══════════════════════════════════════════════════════════════╗
║  HOW TO RUN (same as original!)                              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Option 1 — Direct (GraalVM installed locally):             ║
║    cd {str(output_dir):<50}║
║    bash build.sh                                             ║
║    ./run.sh [your original arguments]                        ║
║                                                              ║
║  Option 2 — Docker (recommended, no install needed):        ║
║    cd {str(output_dir):<50}║
║    docker compose build                                      ║
║    docker compose run graalvm-optimizer [arguments]          ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")

    # Save manifest
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str)
    )


if __name__ == "__main__":
    main()
