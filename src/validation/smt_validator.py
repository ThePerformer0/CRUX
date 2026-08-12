"""Z3 SMT Path Feasibility Validator.

Translates path conditions collected along LLVM IR control flow branches into Z3 logic
expressions to verify whether candidate useless lock paths are satisfiable (SAT)
or dead paths (UNSAT), pruning false positives.
"""
