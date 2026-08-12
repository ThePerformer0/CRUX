"""Z3 SMT Path Feasibility Validator.

Translates path conditions collected along LLVM IR control flow branches into Z3 logic
expressions to verify whether candidate useless lock paths are satisfiable (SAT)
or dead paths (UNSAT), pruning false positives.
"""

import re
from typing import Dict, List, Optional
import z3
from src.core.lock_site import LockSite

ICMP_PATTERN = re.compile(
    r"(?:icmp\s+)?(eq|ne|slt|sle|sgt|sge|ult|ule|ugt|uge)\s+(?:[a-zA-Z0-9_$.]+\s+)?(%[a-zA-Z0-9_$.]+|-?\d+)\s*,\s*(%[a-zA-Z0-9_$.]+|-?\d+)"
)


def llvm_condition_to_z3(cond_str: str, z3_vars: Dict[str, z3.ArithRef]) -> Optional[z3.BoolRef]:
    """Parses an LLVM IR condition string and translates it to a Z3 boolean expression.

    Args:
        cond_str: LLVM IR comparison string (e.g. "icmp sgt i32 %x, 0").
        z3_vars: Cache of variable names -> z3.Int instances.

    Returns:
        Z3 BoolRef expression or None if parsing fails.
    """
    clean_cond = cond_str.strip()
    match = ICMP_PATTERN.search(clean_cond)
    if not match:
        return None

    op, left_raw, right_raw = match.group(1), match.group(2), match.group(3)

    def resolve_operand(token: str) -> z3.ArithRef:
        if token.startswith("%") or token.startswith("@"):
            if token not in z3_vars:
                z3_vars[token] = z3.Int(token)
            return z3_vars[token]
        try:
            return z3.IntVal(int(token))
        except ValueError:
            if token not in z3_vars:
                z3_vars[token] = z3.Int(token)
            return z3_vars[token]

    left_expr = resolve_operand(left_raw)
    right_expr = resolve_operand(right_raw)

    if op in ("eq",):
        return left_expr == right_expr
    elif op in ("ne",):
        return left_expr != right_expr
    elif op in ("slt", "ult"):
        return left_expr < right_expr
    elif op in ("sle", "ule"):
        return left_expr <= right_expr
    elif op in ("sgt", "ugt"):
        return left_expr > right_expr
    elif op in ("sge", "uge"):
        return left_expr >= right_expr

    return None


class SMTValidator:
    """Validates path conditions of candidate useless lock sites using Z3."""

    def validate_path(self, conditions: List[str]) -> bool:
        """Returns True if the path conditions are satisfiable (SAT / feasible path).

        Returns False if path is provably dead (UNSAT).
        """
        if not conditions:
            return True  # No conditions = path is always feasible

        solver = z3.Solver()
        z3_vars: Dict[str, z3.ArithRef] = {}
        added_any = False

        for cond in conditions:
            expr = llvm_condition_to_z3(cond, z3_vars)
            if expr is not None:
                solver.add(expr)
                added_any = True

        if not added_any:
            return True  # Unsupported conditions are conservatively assumed feasible

        result = solver.check()
        return result != z3.unsat

    def validate_sites(self, sites: List[LockSite]) -> List[LockSite]:
        """Validates all candidate useless sites and updates their SMT confirmation status."""
        for site in sites:
            if site.is_useless:
                is_feasible = self.validate_path(site.path_conditions)
                if is_feasible:
                    site.smt_confirmed = True
                else:
                    # Path is dead (UNSAT) -> prune false positive candidate
                    site.is_useless = False
                    site.smt_confirmed = False
                    site.reasons.append("PRUNED_UNSAT_PATH")
        return sites
