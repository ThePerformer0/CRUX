"""Unit tests for LocksetAnalyzer BFS convergence and correctness.

These tests specifically validate the two fixes applied to lockset_analyzer.py:

Fix 1 - Fixpoint on lockset only (not path_conditions):
    Before the fix, BFS would loop indefinitely on functions containing loops
    because path_conditions grew unboundedly at each back-edge visit.
    After the fix, convergence is guaranteed for any finite CFG.

Fix 2 - deque instead of queue.Queue:
    Before the fix, every worklist operation acquired a threading lock,
    adding ~22s of overhead on HAProxy alone. The deque is lock-free.
"""

import time
import pytest
from src.frontend.cfg_builder import build_cfgs
from src.analysis.alias_resolver import AliasResolver
from src.analysis.lockset_analyzer import LocksetAnalyzer, MAX_PATH_CONDITIONS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_analyzer(ir, custom_locks=None, custom_unlocks=None):
    cfgs = build_cfgs(ir)
    resolver = AliasResolver()
    resolver.analyze_cfgs(cfgs)
    return cfgs, LocksetAnalyzer(resolver,
                                 custom_locks=custom_locks,
                                 custom_unlocks=custom_unlocks)


# ---------------------------------------------------------------------------
# Fix 1a — convergence on loops (root cause of non-termination)
# ---------------------------------------------------------------------------

SIMPLE_LOOP_IR = """
define void @loop_func(i8* %m, i32 %n) {
entry:
    call i32 @pthread_mutex_lock(i8* %m)
    br label %loop_header
loop_header:
    %i = phi i32 [ 0, %entry ], [ %i_next, %loop_body ]
    %cond = icmp slt i32 %i, %n
    br i1 %cond, label %loop_body, label %loop_exit
loop_body:
    %i_next = add i32 %i, 1
    br label %loop_header
loop_exit:
    call i32 @pthread_mutex_unlock(i8* %m)
    ret void
}
"""

NESTED_LOOP_IR = """
define void @nested_loops(i8* %m, i32 %n) {
entry:
    call i32 @pthread_mutex_lock(i8* %m)
    br label %outer_header
outer_header:
    %i = phi i32 [ 0, %entry ], [ %i_next, %outer_latch ]
    %outer_cond = icmp slt i32 %i, %n
    br i1 %outer_cond, label %inner_header, label %exit
inner_header:
    %j = phi i32 [ 0, %outer_header ], [ %j_next, %inner_body ]
    %inner_cond = icmp slt i32 %j, %n
    br i1 %inner_cond, label %inner_body, label %outer_latch
inner_body:
    %j_next = add i32 %j, 1
    br label %inner_header
outer_latch:
    %i_next = add i32 %i, 1
    br label %outer_header
exit:
    call i32 @pthread_mutex_unlock(i8* %m)
    ret void
}
"""


def test_loop_convergence_terminates():
    """BFS must terminate quickly on a simple loop (was infinite before fix)."""
    cfgs, analyzer = _make_analyzer(SIMPLE_LOOP_IR)
    start = time.time()
    states = analyzer.analyze_cfg(cfgs["loop_func"])
    elapsed = time.time() - start
    assert elapsed < 1.0, (
        f"analyze_cfg took {elapsed:.2f}s on a trivial loop — BFS did not converge"
    )
    # Lock must be tracked inside the loop
    assert "%m" in states["loop_header"][0].lockset


def test_nested_loop_convergence_terminates():
    """BFS must terminate on nested loops (two back-edges)."""
    cfgs, analyzer = _make_analyzer(NESTED_LOOP_IR)
    start = time.time()
    analyzer.analyze_cfg(cfgs["nested_loops"])
    elapsed = time.time() - start
    assert elapsed < 2.0, f"Nested loop took {elapsed:.2f}s — convergence issue"


# ---------------------------------------------------------------------------
# Fix 1b — lockset correctness is preserved after the convergence fix
# ---------------------------------------------------------------------------

def test_lockset_correct_through_loop():
    """Lockset acquired before a loop must be tracked inside and after the loop."""
    ir = """
define void @lock_through_loop(i8* %m, i32 %n) {
entry:
    call i32 @pthread_mutex_lock(i8* %m)
    br label %header
header:
    %i = phi i32 [ 0, %entry ], [ %i_next, %body ]
    %cond = icmp slt i32 %i, %n
    br i1 %cond, label %body, label %exit
body:
    %i_next = add i32 %i, 1
    br label %header
exit:
    call i32 @pthread_mutex_unlock(i8* %m)
    ret void
}
"""
    cfgs, analyzer = _make_analyzer(ir)
    states = analyzer.analyze_cfg(cfgs["lock_through_loop"])
    # Lock held at loop header and in body
    assert "%m" in states["header"][0].lockset
    assert "%m" in states["body"][0].lockset
    # Lock released at exit: state at ret instruction (index 1, after unlock)
    assert states["exit"][1].lockset == frozenset()


def test_lock_only_in_one_branch_not_at_merge():
    """Lock acquired only on one branch -> lockset empty at merge (intersection)."""
    ir = """
define void @branch_lock(i8* %m, i1 %c) {
entry:
    br i1 %c, label %locked_branch, label %unlocked_branch
locked_branch:
    call i32 @pthread_mutex_lock(i8* %m)
    br label %merge
unlocked_branch:
    br label %merge
merge:
    ret void
}
"""
    cfgs, analyzer = _make_analyzer(ir)
    states = analyzer.analyze_cfg(cfgs["branch_lock"])
    # intersection({%m}, {}) = {}  — conservative: lock NOT considered held
    assert states["merge"][0].lockset == frozenset()


def test_lock_in_both_branches_held_at_merge():
    """Lock acquired on BOTH branches -> still held at merge."""
    ir = """
define void @both_branch_lock(i8* %m, i1 %c) {
entry:
    br i1 %c, label %b1, label %b2
b1:
    call i32 @pthread_mutex_lock(i8* %m)
    br label %merge
b2:
    call i32 @pthread_mutex_lock(i8* %m)
    br label %merge
merge:
    call i32 @pthread_mutex_unlock(i8* %m)
    ret void
}
"""
    cfgs, analyzer = _make_analyzer(ir)
    states = analyzer.analyze_cfg(cfgs["both_branch_lock"])
    # intersection({%m}, {%m}) = {%m}
    assert "%m" in states["merge"][0].lockset


def test_two_independent_mutexes_tracked():
    """Two mutexes acquired sequentially must both appear in the lockset."""
    ir = """
define void @two_locks(i8* %m1, i8* %m2) {
entry:
    call i32 @pthread_mutex_lock(i8* %m1)
    call i32 @pthread_mutex_lock(i8* %m2)
    call i32 @pthread_mutex_unlock(i8* %m2)
    call i32 @pthread_mutex_unlock(i8* %m1)
    ret void
}
"""
    cfgs, analyzer = _make_analyzer(ir)
    states = analyzer.analyze_cfg(cfgs["two_locks"])
    # After locking both: both held
    assert "%m1" in states["entry"][2].lockset
    assert "%m2" in states["entry"][2].lockset
    # After unlocking m2: only m1
    assert "%m1" in states["entry"][3].lockset
    assert "%m2" not in states["entry"][3].lockset
    # After unlocking m1: empty
    assert states["entry"][4].lockset == frozenset()


# ---------------------------------------------------------------------------
# Path conditions — still collected, never block convergence
# ---------------------------------------------------------------------------

def test_path_conditions_collected_on_simple_branch():
    """Path conditions must still be collected even though they don't drive fixpoint."""
    ir = """
define void @cond_collect(i1 %flag) {
entry:
    br i1 %flag, label %then, label %else
then:
    ret void
else:
    ret void
}
"""
    cfgs, analyzer = _make_analyzer(ir)
    states = analyzer.analyze_cfg(cfgs["cond_collect"])
    assert "%flag" in states["then"][0].path_conditions


def test_path_conditions_do_not_block_loop_convergence():
    """Path conditions accumulated in a loop must not re-trigger BFS propagation."""
    cfgs, analyzer = _make_analyzer(SIMPLE_LOOP_IR)
    # If path_conditions were in the fixpoint criterion this would hang.
    # Simply completing in time proves they are not.
    start = time.time()
    analyzer.analyze_cfg(cfgs["loop_func"])
    assert time.time() - start < 1.0


# ---------------------------------------------------------------------------
# Fix 2 — structural: deque replaces threading Queue
# ---------------------------------------------------------------------------

def test_deque_replaces_queue():
    """Confirm queue.Queue was replaced by collections.deque in the source."""
    import inspect
    import src.analysis.lockset_analyzer as mod
    src_text = inspect.getsource(mod)
    assert "from queue import Queue" not in src_text, (
        "queue.Queue is still imported — threading overhead not removed"
    )
    assert "from collections import deque" in src_text, (
        "collections.deque not found — fix not applied"
    )


def test_max_path_conditions_constant_exists():
    """MAX_PATH_CONDITIONS must be exported and be a positive integer."""
    assert isinstance(MAX_PATH_CONDITIONS, int)
    assert MAX_PATH_CONDITIONS > 0
