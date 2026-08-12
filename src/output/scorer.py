"""Confidence Scorer and Fix Suggester.

Calculates a confidence score in range [0.0, 1.0] for each flagged useless lock site based on
heuristics (indirect calls, call depth, caller fan-in, path complexity, SMT confirmation, global mutexes)
and generates human-readable refactoring suggestions.
"""
