"""Unit tests for Interprocedural Call Graph Builder (src/frontend/call_graph.py)."""

import pytest
from src.frontend.call_graph import build_call_graph, CallGraph


def test_direct_call_extraction():
    """Verify direct calls (call @bar) are extracted into calls and callers."""
    ir = """
    define void @bar() {
        ret void
    }

    define void @foo() {
        call void @bar()
        ret void
    }
    """
    cg = build_call_graph(ir)
    assert "bar" in cg.get_callees("foo")
    assert "foo" in cg.get_callers("bar")
    assert cg.call_counts[("foo", "bar")] == 1


def test_invoke_instruction_handled():
    """Verify invoke instructions (C++ exceptions) are recognized as calls."""
    ir = """
    define void @throw_func() {
        ret void
    }

    define void @caller_func() {
        invoke void @throw_func() to label %normal unwind label %catch
    normal:
        ret void
    catch:
        ret void
    }
    """
    cg = build_call_graph(ir)
    assert "throw_func" in cg.get_callees("caller_func")
    assert "caller_func" in cg.get_callers("throw_func")


def test_transitive_callees():
    """Verify transitive callee resolution across multi-level call chains."""
    ir = """
    define void @baz() { ret void }
    define void @bar() { call void @baz(); ret void }
    define void @foo() { call void @bar(); ret void }
    define void @main() { call void @foo(); ret void }
    """
    cg = build_call_graph(ir)
    transitive = cg.get_transitive_callees("main")
    assert transitive == {"foo", "bar", "baz"}


def test_recursion_handling():
    """Verify cyclic call graphs (direct and indirect recursion) do not loop infinitely."""
    ir = """
    define void @func_a() {
        call void @func_b()
        ret void
    }

    define void @func_b() {
        call void @func_a()
        ret void
    }
    """
    cg = build_call_graph(ir)
    assert cg.get_transitive_callees("func_a") == {"func_a", "func_b"}
    assert cg.get_transitive_callees("func_b") == {"func_a", "func_b"}


def test_llvm_intrinsics_ignored():
    """Verify calls to @llvm.* intrinsic functions are excluded from CallGraph edges."""
    ir = """
    define void @foo(i8* %ptr) {
        call void @llvm.lifetime.start.p0i8(i64 4, i8* %ptr)
        call void @llvm.memcpy.p0i8.p0i8.i64(i8* %ptr, i8* %ptr, i64 4, i1 false)
        ret void
    }
    """
    cg = build_call_graph(ir)
    assert cg.get_callees("foo") == []


def test_indirect_call_cha():
    """Verify indirect calls via function pointers use CHA to match defined functions."""
    ir = """
    define void @target1() { ret void }
    define void @target2() { ret void }

    define void @caller(void ()* %fn_ptr) {
        call void %fn_ptr()
        ret void
    }
    """
    cg = build_call_graph(ir)
    callees = cg.get_callees("caller")
    assert "target1" in callees
    assert "target2" in callees


def test_multiple_call_sites():
    """Verify multiple calls from same caller to same callee update call counts."""
    ir = """
    define void @worker() { ret void }
    define void @manager() {
        call void @worker()
        call void @worker()
        call void @worker()
        ret void
    }
    """
    cg = build_call_graph(ir)
    assert cg.call_counts[("manager", "worker")] == 3
