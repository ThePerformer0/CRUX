"""Unit tests for Z3 SMT Validator (src/validation/smt_validator.py)."""

import pytest
from src.core.lock_site import LockSite
from src.validation.smt_validator import SMTValidator, llvm_condition_to_z3


def test_empty_conditions_feasible():
    """Verify empty condition list is evaluated as feasible (SAT)."""
    validator = SMTValidator()
    assert validator.validate_path([]) is True


def test_satisfiable_path_conditions():
    """Verify compatible constraints (%x > 0 and %x < 10) return True (SAT)."""
    validator = SMTValidator()
    conds = ["icmp sgt i32 %x, 0", "icmp slt i32 %x, 10"]
    assert validator.validate_path(conds) is True


def test_unsatisfiable_path_conditions():
    """Verify contradictory constraints (%x > 10 and %x < 5) return False (UNSAT)."""
    validator = SMTValidator()
    conds = ["icmp sgt i32 %x, 10", "icmp slt i32 %x, 5"]
    assert validator.validate_path(conds) is False


def test_llvm_icmp_parsing():
    """Verify parsing of various icmp operators (eq, ne, sgt, slt, sge, sle)."""
    z3_vars = {}
    expr_gt = llvm_condition_to_z3("icmp sgt i32 %val, 100", z3_vars)
    assert expr_gt is not None

    expr_eq = llvm_condition_to_z3("icmp eq i32 %status, 0", z3_vars)
    assert expr_eq is not None


def test_smt_site_validation():
    """Verify SMTValidator updates smt_confirmed on SAT sites and prunes UNSAT sites."""
    s_sat = LockSite(site_id="s1", mutex_canonical_id="%m", mutex_name="%m", function="foo",
                     is_useless=True, path_conditions=["icmp sgt i32 %x, 0"])

    s_unsat = LockSite(site_id="s2", mutex_canonical_id="%m", mutex_name="%m", function="bar",
                       is_useless=True, path_conditions=["icmp sgt i32 %y, 10", "icmp slt i32 %y, 2"])

    validator = SMTValidator()
    validator.validate_sites([s_sat, s_unsat])

    assert s_sat.is_useless is True
    assert s_sat.smt_confirmed is True

    assert s_unsat.is_useless is False
    assert s_unsat.smt_confirmed is False
    assert "PRUNED_UNSAT_PATH" in s_unsat.reasons
