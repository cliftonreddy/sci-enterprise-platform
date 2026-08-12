#!/bin/bash
# Auto-generated run script -- GraalVM Optimizer
# Usage: ./run.sh [args...]  (same as original: java DataProcessor.java [args...])

DIR="$(cd "$(dirname "$0")" && pwd)"
NATIVE_DIR="$DIR/native"

# Bitcode files are baked into the Docker image during build.
# If missing, the app runs with Java fallback automatically.
if ! ls "$NATIVE_DIR"/*.bc 2>/dev/null | grep -q .; then
    echo "WARNING: No bitcode files in $NATIVE_DIR -- running with Java fallback"
fi

# Java — compile then run with GraalVM
if command -v java &> /dev/null; then
    echo "⚡ Compiling Java..."
    bash "$DIR/compile.sh"
    echo "⚡ Running with GraalVM java"
    java \
        -cp "$DIR/out" \
        -Dpolyglot.engine.WarnInterpreterOnly=false \
        -Dpolyglot.llvm.verifyBitcode=false \
        -Dnative.dir="$NATIVE_DIR" \
        Main "$@"
else
    echo '✗ java not found — is GraalVM installed?'
    exit 1
fi