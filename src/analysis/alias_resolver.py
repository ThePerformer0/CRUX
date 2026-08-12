"""Field-Based Alias Analyzer.

Uses a field-based equivalence framework (Union-Find) to assign a canonical ID
to memory objects and registers. Merges registers linked via bitcast,
getelementptr (struct field indexing), store/load pointer operations, and phi nodes.
"""
