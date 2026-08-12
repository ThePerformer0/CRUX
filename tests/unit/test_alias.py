"""Unit tests for Field-Based Alias Analyzer (src/analysis/alias_resolver.py)."""

import pytest
from src.analysis.alias_resolver import AliasResolver


def test_identity_canonical_id():
    """Verify an independent register retains its own name as canonical ID."""
    resolver = AliasResolver()
    assert resolver.get_canonical_id("%x") == "%x"
    assert resolver.get_canonical_id("@global_var") == "@global_var"


def test_bitcast_aliasing():
    """Verify bitcast merges source and destination registers into same canonical ID."""
    ir = """
    define void @foo(i8* %m) {
    entry:
        %p = bitcast i8* %m to i32*
        ret void
    }
    """
    resolver = AliasResolver()
    resolver.analyze_ir(ir)
    assert resolver.get_canonical_id("%p") == resolver.get_canonical_id("%m")


def test_gep_same_field_aliasing():
    """Verify two GEP instructions on same base struct and field index share canonical ID."""
    ir = """
    define void @foo(%struct.Pool* %p) {
    entry:
        %11 = getelementptr inbounds %struct.Pool, %struct.Pool* %p, i32 0, i32 1
        %23 = getelementptr inbounds %struct.Pool, %struct.Pool* %p, i32 0, i32 1
        ret void
    }
    """
    resolver = AliasResolver()
    resolver.analyze_ir(ir)
    canon_11 = resolver.get_canonical_id("%11")
    canon_23 = resolver.get_canonical_id("%23")
    assert canon_11 == canon_23
    assert canon_11 == "%p.1"


def test_gep_different_fields_distinct():
    """Verify GEP instructions accessing different field indices have distinct canonical IDs."""
    ir = """
    define void @foo(%struct.Pool* %p) {
    entry:
        %m1 = getelementptr inbounds %struct.Pool, %struct.Pool* %p, i32 0, i32 1
        %m2 = getelementptr inbounds %struct.Pool, %struct.Pool* %p, i32 0, i32 2
        ret void
    }
    """
    resolver = AliasResolver()
    resolver.analyze_ir(ir)
    canon_m1 = resolver.get_canonical_id("%m1")
    canon_m2 = resolver.get_canonical_id("%m2")
    assert canon_m1 != canon_m2
    assert canon_m1 == "%p.1"
    assert canon_m2 == "%p.2"


def test_phi_aliasing():
    """Verify phi instruction merges destination register with all incoming values."""
    ir = """
    define void @foo(i8* %p1, i8* %p2, i1 %c) {
    entry:
        br i1 %c, label %b1, label %b2
    b1:
        br label %merge
    b2:
        br label %merge
    merge:
        %res = phi i8* [ %p1, %b1 ], [ %p2, %b2 ]
        ret void
    }
    """
    resolver = AliasResolver()
    resolver.analyze_ir(ir)
    canon_res = resolver.get_canonical_id("%res")
    assert canon_res == resolver.get_canonical_id("%p1")
    assert canon_res == resolver.get_canonical_id("%p2")


def test_store_load_pointer_aliasing():
    """Verify store and load of a pointer value links stored and loaded registers."""
    ir = """
    define void @foo(i8* %src, i8** %slot) {
    entry:
        store i8* %src, i8** %slot
        %dst = load i8*, i8** %slot
        ret void
    }
    """
    resolver = AliasResolver()
    resolver.analyze_ir(ir)
    assert resolver.get_canonical_id("%dst") == resolver.get_canonical_id("%src")
