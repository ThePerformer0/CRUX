"""Tests for alias resolution on global variables, SSA loads, and false positive guards."""

import pytest
from src.analysis.alias_resolver import AliasResolver
from src.core.lock_site import LockSite
from src.core.lsg import LockSiteGraph
from src.core.classifier import Classifier
from src.frontend.call_graph import CallGraph
from src.frontend.parser import parse_instruction


def test_alias_global_variables_and_repeated_loads():
    resolver = AliasResolver()
    
    # Simulate LLVM IR loading global variable @CommitTsSLRULock multiple times
    inst1 = parse_instruction("%25 = load ptr, ptr @CommitTsSLRULock, align 8")
    inst2 = parse_instruction("%28 = load ptr, ptr @CommitTsSLRULock, align 8")
    
    resolver._process_instruction(inst1)
    resolver._process_instruction(inst2)
    
    id1 = resolver.get_canonical_id("%25")
    id2 = resolver.get_canonical_id("%28")
    
    assert id1 == id2, f"Expected %25 and %28 to alias to same canonical ID, got {id1} vs {id2}"


def test_alias_global_stores_and_loads():
    resolver = AliasResolver()
    
    # Simulate store into global pointer, then load from it
    inst_store = parse_instruction("store ptr %my_mutex, ptr @GlobalMutexPtr")
    inst_load1 = parse_instruction("%regA = load ptr, ptr @GlobalMutexPtr")
    inst_load2 = parse_instruction("%regB = load ptr, ptr @GlobalMutexPtr")
    
    resolver._process_instruction(inst_store)
    resolver._process_instruction(inst_load1)
    resolver._process_instruction(inst_load2)
    
    canon_store = resolver.get_canonical_id("%my_mutex")
    canon_load1 = resolver.get_canonical_id("%regA")
    canon_load2 = resolver.get_canonical_id("%regB")
    
    assert canon_load1 == canon_load2
    assert canon_load1 == canon_store


def test_alias_gep_opaque_pointers_and_i64():
    """Simulate PostgreSQL MainLWLockArray GEP index calculation in 64-bit LLVM IR."""
    resolver = AliasResolver()
    
    # Load 1: acquire
    inst_load1 = parse_instruction("%24 = load ptr, ptr @MainLWLockArray, align 8")
    inst_gep1 = parse_instruction("%25 = getelementptr inbounds %struct.LWLockPadded, ptr %24, i64 12, i32 0")
    
    # Load 2: release
    inst_load2 = parse_instruction("%27 = load ptr, ptr @MainLWLockArray, align 8")
    inst_gep2 = parse_instruction("%28 = getelementptr inbounds %struct.LWLockPadded, ptr %27, i64 12, i32 0")
    
    resolver._process_instruction(inst_load1)
    resolver._process_instruction(inst_gep1)
    resolver._process_instruction(inst_load2)
    resolver._process_instruction(inst_gep2)
    
    canon1 = resolver.get_canonical_id("%25")
    canon2 = resolver.get_canonical_id("%28")
    
    assert canon1 == canon2
    assert "12" in canon1


def test_escaping_lock_wrapper_not_empty_cs():
    """LockBuffer pattern: lock is acquired and returned without unlock in same function."""
    lsg = LockSiteGraph()
    site = LockSite(
        site_id="s_buf",
        mutex_canonical_id="%buf_lock",
        mutex_name="%buf_lock",
        function="LockBuffer",
        lock_source_line=4728,
        unlock_source_lines=[],  # Escapes function
        reads=set(),
        writes=set(),
        calls=[],
    )
    lsg.add_site(site)
    
    classifier = Classifier(lsg)
    reasons = classifier.classify_site(site)
    
    # Must NOT be classified as EMPTY_CS because unlock_source_lines is empty (escaping lock)
    assert "EMPTY_CS" not in reasons
    assert "READ_ONLY" not in reasons
    assert not site.is_useless


def test_sequential_locks_no_nesting():
    """Two independent sequential locks in the same function."""
    call_graph = CallGraph()
    lsg = LockSiteGraph(call_graph)
    
    site1 = LockSite(
        site_id="s1",
        mutex_canonical_id="@Lock1",
        mutex_name="@Lock1",
        function="ActivateCommitTs",
        lock_source_line=682,
        unlock_source_lines=[684],
        reads={"@shared_var1"},
        writes={"@shared_var1"},
        lockset_at_entry=frozenset(),
    )
    
    site2 = LockSite(
        site_id="s2",
        mutex_canonical_id="@Lock2",
        mutex_name="@Lock2",
        function="ActivateCommitTs",
        lock_source_line=699,
        unlock_source_lines=[705],
        reads={"@shared_var2"},
        writes={"@shared_var2"},
        lockset_at_entry=frozenset(),  # Clean entry lockset since site1 unlocked at 684
    )

    other_worker = LockSite(
        site_id="s3",
        mutex_canonical_id="@Lock2",
        mutex_name="@Lock2",
        function="WorkerThread",
        lock_source_line=10,
        unlock_source_lines=[20],
        reads={"@shared_var2"},
        writes={"@shared_var2"},
    )
    
    lsg.build_graph([site1, site2, other_worker])
    
    assert not lsg.has_nest_edge_in("s2")
    
    classifier = Classifier(lsg)
    classifier.classify_all()
    
    assert "REDUNDANT" not in site2.reasons
    assert not site2.is_useless


def test_true_lock_nesting_is_detected():
    """True nested lock where inner lock accesses subset of outer lock variables."""
    call_graph = CallGraph()
    lsg = LockSiteGraph(call_graph)
    
    outer_site = LockSite(
        site_id="s_outer",
        mutex_canonical_id="@BigLock",
        mutex_name="@BigLock",
        function="do_work",
        lock_source_line=10,
        unlock_source_lines=[50],
        reads={"@shared_table", "@shared_counter"},
        writes={"@shared_table", "@shared_counter"},
        lockset_at_entry=frozenset(),
    )
    
    inner_site = LockSite(
        site_id="s_inner",
        mutex_canonical_id="@SmallLock",
        mutex_name="@SmallLock",
        function="do_work",
        lock_source_line=20,
        unlock_source_lines=[30],
        reads={"@shared_counter"},
        writes={"@shared_counter"},
        lockset_at_entry=frozenset(["@BigLock"]),  # Outer lock held
    )
    
    lsg.build_graph([outer_site, inner_site])
    
    assert lsg.has_nest_edge_in("s_inner")
    
    classifier = Classifier(lsg)
    classifier.classify_all()
    
    assert "REDUNDANT" in inner_site.reasons
    assert inner_site.is_useless
