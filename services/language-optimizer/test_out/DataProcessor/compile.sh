#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$DIR/out"
mkdir -p "$DIR/out/com/example"
cp "$DIR/DataProcessor.java" "$DIR/out/com/example/"
javac -encoding UTF-8 -d "$DIR/out" "$DIR/out/com/example/DataProcessor.java" "$DIR/Main.java"
echo "✅ Compiled to out/"
