"""Unit tests for Crux Classifier (src/core/classifier.py)."""

import pytest
from src.core.lock_site import LockSite
from src.core.lsg import LockSiteGraph
from src.core.classifier import Classifier


def test_classify_empty_cs():
    """Verify lock site with empty critical section is classified as EMPTY_CS."""
    site = LockSite(site_id="s1", mutex_canonical_id="%m", mutex_name="%m", function="foo", unlock_source_lines=[10])
    lsg = LockSiteGraph()
    lsg.build_graph([site])

    classifier = Classifier(lsg)
    reasons = classifier.classify_site(site)

    assert "EMPTY_CS" in reasons
    assert site.is_useless is True


def test_classify_local_vars():
    """Verify lock site accessing only stack-local %alloca variables is classified as LOCAL_VARS."""
    site = LockSite(site_id="s1", mutex_canonical_id="%m", mutex_name="%m", function="foo",
                    reads={"%local_x"}, writes={"%local_y"}, unlock_source_lines=[10])
    lsg = LockSiteGraph()
    lsg.build_graph([site])

    classifier = Classifier(lsg)
    reasons = classifier.classify_site(site)

    assert "LOCAL_VARS" in reasons
    assert site.is_useless is True


def test_classify_read_only():
    """Verify lock site performing only reads on global variables without writes is classified as READ_ONLY."""
    site1 = LockSite(site_id="s1", mutex_canonical_id="%m1", mutex_name="%m1", function="f1", reads={"@global_var"}, unlock_source_lines=[10])
    site2 = LockSite(site_id="s2", mutex_canonical_id="%m2", mutex_name="%m2", function="f2", reads={"@global_var"}, unlock_source_lines=[20])

    lsg = LockSiteGraph()
    lsg.build_graph([site1, site2])

    classifier = Classifier(lsg)
    reasons1 = classifier.classify_site(site1)
    reasons2 = classifier.classify_site(site2)

    assert "READ_ONLY" in reasons1
    assert "READ_ONLY" in reasons2


def test_classify_redundant():
    """Verify nested child lock site covered by parent lock is classified as REDUNDANT."""
    s1 = LockSite(site_id="s1", mutex_canonical_id="%m_parent", mutex_name="%m_parent", function="f1",
                  writes={"@global_var"}, lock_source_line=10, unlock_source_lines=[50])
    s2 = LockSite(site_id="s2", mutex_canonical_id="%m_child", mutex_name="%m_child", function="f1",
                  writes={"@global_var"}, lock_source_line=20, unlock_source_lines=[30],
                  lockset_at_entry=frozenset(["%m_parent"]))

    lsg = LockSiteGraph()
    lsg.build_graph([s1, s2])

    classifier = Classifier(lsg)
    reasons_s2 = classifier.classify_site(s2)

    assert "REDUNDANT" in reasons_s2
    assert s2.is_useless is True


def test_useful_lock_not_flagged():
    """Verify a lock site protecting a shared write against conflicting accesses is NOT flagged as useless."""
    s1 = LockSite(site_id="s1", mutex_canonical_id="%m1", mutex_name="%m1", function="writer", writes={"@shared_counter"})
    s2 = LockSite(site_id="s2", mutex_canonical_id="%m2", mutex_name="%m2", function="reader", reads={"@shared_counter"})

    lsg = LockSiteGraph()
    lsg.build_graph([s1, s2])

    classifier = Classifier(lsg)
    reasons_s1 = classifier.classify_site(s1)
    reasons_s2 = classifier.classify_site(s2)

    assert reasons_s1 == []
    assert s1.is_useless is False
    assert reasons_s2 == []
    assert s2.is_useless is False


def test_safety_guard_indirect_calls():
    """Verify indirect calls guard discards EMPTY_CS and READ_ONLY reasons."""
    site = LockSite(site_id="s1", mutex_canonical_id="%m", mutex_name="%m", function="foo",
                    has_indirect_calls=True)
    lsg = LockSiteGraph()
    lsg.build_graph([site])

    classifier = Classifier(lsg)
    reasons = classifier.classify_site(site)

    assert "EMPTY_CS" not in reasons
    assert site.is_useless is False


def test_safety_guard_cond_wait():
    """Verify condition wait guard discards EMPTY_CS, READ_ONLY, and REDUNDANT reasons."""
    site = LockSite(site_id="s1", mutex_canonical_id="%m", mutex_name="%m", function="foo",
                    is_cond_wait_mutex=True)
    lsg = LockSiteGraph()
    lsg.build_graph([site])

    classifier = Classifier(lsg)
    reasons = classifier.classify_site(site)

    assert "EMPTY_CS" not in reasons
    assert "READ_ONLY" not in reasons
    assert site.is_useless is False


def test_classifier_guards_inline_asm():
    """Verify inline assembly or memory intrinsic guards discard EMPTY_CS and LOCAL_VARS reasons."""
    # Site 1: Looks empty but has inline asm
    site_asm = LockSite(site_id="s1", mutex_canonical_id="%m", mutex_name="%m", function="foo",
                        has_inline_asm=True)
    
    # Site 2: Looks like LOCAL_VARS but has a memory fence
    site_fence = LockSite(site_id="s2", mutex_canonical_id="%m", mutex_name="%m", function="bar",
                          reads={"%local_x"}, writes={"%local_y"}, has_memory_intrinsic=True)
    
    lsg = LockSiteGraph()
    lsg.build_graph([site_asm, site_fence])

    classifier = Classifier(lsg)
    
    # Simulate stack-local validation for site_fence
    classifier.alias_resolver = type('MockResolver', (), {'is_stack_alloca': lambda self, v: True})()

    reasons_asm = classifier.classify_site(site_asm)
    reasons_fence = classifier.classify_site(site_fence)

    assert "EMPTY_CS" not in reasons_asm
    assert site_asm.is_useless is False
    
    assert "LOCAL_VARS" not in reasons_fence
    assert site_fence.is_useless is False
