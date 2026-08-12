"""Unit tests for Lockset Analyzer (src/analysis/lockset_analyzer.py)."""

import pytest
from src.frontend.cfg_builder import build_cfgs
from src.analysis.alias_resolver import AliasResolver
from src.analysis.lockset_analyzer import LocksetAnalyzer


def test_lock_acquisition():
    """Verify lockset contains canonical ID of mutex after pthread_mutex_lock."""
    ir = """
    define void @foo(i8* %m) {
    entry:
        call i32 @pthread_mutex_lock(i8* %m)
        %x = alloca i32
        ret void
    }
    """
    cfgs = build_cfgs(ir)
    resolver = AliasResolver()
    resolver.analyze_cfgs(cfgs)

    analyzer = LocksetAnalyzer(resolver)
    states = analyzer.analyze_cfg(cfgs["foo"])

    # First instruction (call lock): lockset entry state is empty
    assert states["entry"][0].lockset == frozenset()
    # Second instruction (%x = alloca): lockset entry state contains %m
    assert states["entry"][1].lockset == frozenset(["%m"])


def test_unlock_release():
    """Verify lockset no longer contains mutex after pthread_mutex_unlock."""
    ir = """
    define void @foo(i8* %m) {
    entry:
        call i32 @pthread_mutex_lock(i8* %m)
        call i32 @pthread_mutex_unlock(i8* %m)
        ret void
    }
    """
    cfgs = build_cfgs(ir)
    resolver = AliasResolver()
    resolver.analyze_cfgs(cfgs)

    analyzer = LocksetAnalyzer(resolver)
    states = analyzer.analyze_cfg(cfgs["foo"])

    # Instruction 0 (lock): empty
    # Instruction 1 (unlock): holds %m
    assert states["entry"][1].lockset == frozenset(["%m"])
    # Instruction 2 (ret): empty
    assert states["entry"][2].lockset == frozenset()


def test_cfg_branch_intersection():
    """Verify conservative intersection join at CFG convergence (lock acquired on 1 branch only)."""
    ir = """
    define void @foo(i8* %m, i1 %c) {
    entry:
        br i1 %c, label %b1, label %b2
    b1:
        call i32 @pthread_mutex_lock(i8* %m)
        br label %merge
    b2:
        br label %merge
    merge:
        ret void
    }
    """
    cfgs = build_cfgs(ir)
    resolver = AliasResolver()
    resolver.analyze_cfgs(cfgs)

    analyzer = LocksetAnalyzer(resolver)
    states = analyzer.analyze_cfg(cfgs["foo"])

    # At entry of merge block, lockset is intersection (frozenset() & frozenset([%m])) -> empty
    assert states["merge"][0].lockset == frozenset()


def test_cond_wait_net_effect_zero():
    """Verify pthread_cond_wait leaves lockset unchanged (net effect = 0)."""
    ir = """
    define void @foo(i8* %m, i8* %cond) {
    entry:
        call i32 @pthread_mutex_lock(i8* %m)
        call i32 @pthread_cond_wait(i8* %cond, i8* %m)
        ret void
    }
    """
    cfgs = build_cfgs(ir)
    resolver = AliasResolver()
    resolver.analyze_cfgs(cfgs)

    analyzer = LocksetAnalyzer(resolver)
    states = analyzer.analyze_cfg(cfgs["foo"])

    # Instruction 2 (ret): after cond_wait, mutex %m is still held
    assert states["entry"][2].lockset == frozenset(["%m"])


def test_custom_lock_functions():
    """Verify custom lock and unlock functions are recognized."""
    ir = """
    define void @foo(i8* %lock_obj) {
    entry:
        call void @my_custom_lock(i8* %lock_obj)
        call void @my_custom_unlock(i8* %lock_obj)
        ret void
    }
    """
    cfgs = build_cfgs(ir)
    resolver = AliasResolver()
    resolver.analyze_cfgs(cfgs)

    analyzer = LocksetAnalyzer(resolver, custom_locks={"my_custom_lock"}, custom_unlocks={"my_custom_unlock"})
    states = analyzer.analyze_cfg(cfgs["foo"])

    assert states["entry"][1].lockset == frozenset(["%lock_obj"])
    assert states["entry"][2].lockset == frozenset()


def test_path_conditions_accumulation():
    """Verify conditional branch conditions are collected in path_conditions tuple."""
    ir = """
    define void @foo(i1 %c) {
    entry:
        br i1 %c, label %then, label %else
    then:
        ret void
    else:
        ret void
    }
    """
    cfgs = build_cfgs(ir)
    resolver = AliasResolver()
    resolver.analyze_cfgs(cfgs)

    analyzer = LocksetAnalyzer(resolver)
    states = analyzer.analyze_cfg(cfgs["foo"])

    assert "%c" in states["then"][0].path_conditions
