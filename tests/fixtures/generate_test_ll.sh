#!/usr/bin/env bash
# Helper script to compile C source files to LLVM IR (.ll) with -O0 -g -S -emit-llvm
set -euo pipefail

CLANG="${CLANG:-clang}"

echo "Generating LLVM IR test fixtures..."
# Example: $CLANG -S -emit-llvm -O0 -g test_case.c -o test_case.ll
