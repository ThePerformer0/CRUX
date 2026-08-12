"""Interprocedural Call Graph Builder.

Analyzes function call instructions across the LLVM IR module.
Constructs caller-callee mappings for direct calls and uses Class Hierarchy
Analysis (CHA) to resolve indirect calls conservatively. Supports transitive
callee extraction and recursion handling.
"""
