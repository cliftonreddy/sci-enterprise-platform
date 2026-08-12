#!/bin/bash
# Auto-generated build script — GraalVM Optimizer
# Compiles native modules for: DataProcessor.java

# Always work relative to this script's location
DIR="$(cd "$(dirname "$0")" && pwd)"
NATIVE_DIR="$DIR/native"

# Detect compilers
CLANG="${CLANG:-clang}"
CLANGPP="${CLANGPP:-clang++}"
RUSTC="${RUSTC:-rustc}"

echo 'Compiling Rust: native_rust.rs'
if "$RUSTC" --emit=llvm-bc -O --crate-type=cdylib "$NATIVE_DIR/native_rust.rs" -o "$NATIVE_DIR/native_rust.bc" 2>&1; then
    echo '  OK native_rust.bc'
else
    echo '  FAIL: native_rust.rs (is rustc installed?)'
fi

echo ""
echo '✅ Build complete'
echo "Bitcode files:"
ls -lh "$NATIVE_DIR"/*.bc 2>/dev/null || echo "  (none — check compiler errors above)"