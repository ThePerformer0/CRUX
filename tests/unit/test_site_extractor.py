"""Unit tests for Site Characterizer (src/analysis/site_extractor.py)."""

import pytest
from src.frontend.cfg_builder import build_cfgs
from src.frontend.call_graph import build_call_graph
from src.analysis.alias_resolver import AliasResolver
from src.analysis.lockset_analyzer import LocksetAnalyzer
from src.analysis.site_extractor import SiteExtractor


def test_lock_site_extraction_basic():
    """Verify basic lock site extraction and identification of lock/unlock lines."""
    ir = """
    define void @foo(i8* %m) {
    entry:
        call i32 @pthread_mutex_lock(i8* %m)
        call i32 @pthread_mutex_unlock(i8* %m)
        ret void
    }
    """
    cfgs = build_cfgs(ir)
    cg = build_call_graph(ir)
    resolver = AliasResolver()
    resolver.analyze_cfgs(cfgs)
    lockset_analyzer = LocksetAnalyzer(resolver)

    extractor = SiteExtractor(resolver, cg, lockset_analyzer)
    sites = extractor.extract_sites(cfgs)

    assert len(sites) == 1
    site = sites[0]
    assert site.site_id == "s1"
    assert site.function == "foo"
    assert site.mutex_canonical_id == "%m"


def test_direct_reads_and_writes():
    """Verify direct memory reads (load) and writes (store) in critical section are extracted."""
    ir = """
    @global_var = global i32 0, align 4

    define void @foo(i8* %m, i32* %ptr) {
    entry:
        call i32 @pthread_mutex_lock(i8* %m)
        %val = load i32, i32* @global_var
        store i32 42, i32* %ptr
        call i32 @pthread_mutex_unlock(i8* %m)
        ret void
    }
    """
    cfgs = build_cfgs(ir)
    cg = build_call_graph(ir)
    resolver = AliasResolver()
    resolver.analyze_cfgs(cfgs)
    lockset_analyzer = LocksetAnalyzer(resolver)

    extractor = SiteExtractor(resolver, cg, lockset_analyzer)
    sites = extractor.extract_sites(cfgs)

    assert len(sites) == 1
    site = sites[0]
    assert "@global_var" in site.reads
    assert "%ptr" in site.writes


def test_transitive_memory_effects():
    """Verify transitive reads and writes of called helper functions are aggregated."""
    ir = """
    @global_read = global i32 0, align 4
    @global_write = global i32 0, align 4

    define void @helper() {
    entry:
        %v = load i32, i32* @global_read
        store i32 %v, i32* @global_write
        ret void
    }

    define void @foo(i8* %m) {
    entry:
        call i32 @pthread_mutex_lock(i8* %m)
        call void @helper()
        call i32 @pthread_mutex_unlock(i8* %m)
        ret void
    }
    """
    cfgs = build_cfgs(ir)
    cg = build_call_graph(ir)
    resolver = AliasResolver()
    resolver.analyze_cfgs(cfgs)
    lockset_analyzer = LocksetAnalyzer(resolver)

    extractor = SiteExtractor(resolver, cg, lockset_analyzer)
    sites = extractor.extract_sites(cfgs)

    assert len(sites) == 1
    site = sites[0]
    assert "helper" in site.calls
    assert "@global_read" in site.transitive_reads
    assert "@global_write" in site.transitive_writes


def test_indirect_call_flag():
    """Verify calling a function pointer inside critical section sets has_indirect_calls = True."""
    ir = """
    define void @foo(i8* %m, void ()* %fn_ptr) {
    entry:
        call i32 @pthread_mutex_lock(i8* %m)
        call void %fn_ptr()
        call i32 @pthread_mutex_unlock(i8* %m)
        ret void
    }
    """
    cfgs = build_cfgs(ir)
    cg = build_call_graph(ir)
    resolver = AliasResolver()
    resolver.analyze_cfgs(cfgs)
    lockset_analyzer = LocksetAnalyzer(resolver)

    extractor = SiteExtractor(resolver, cg, lockset_analyzer)
    sites = extractor.extract_sites(cfgs)

    assert len(sites) == 1
    site = sites[0]
    assert site.has_indirect_calls is True


def test_lockset_at_entry_extraction():
    """Verify lockset_at_entry records outer parent locks already held."""
    ir = """
    define void @foo(i8* %m1, i8* %m2) {
    entry:
        call i32 @pthread_mutex_lock(i8* %m1)
        call i32 @pthread_mutex_lock(i8* %m2)
        call i32 @pthread_mutex_unlock(i8* %m2)
        call i32 @pthread_mutex_unlock(i8* %m1)
        ret void
    }
    """
    cfgs = build_cfgs(ir)
    cg = build_call_graph(ir)
    resolver = AliasResolver()
    resolver.analyze_cfgs(cfgs)
    lockset_analyzer = LocksetAnalyzer(resolver)

    extractor = SiteExtractor(resolver, cg, lockset_analyzer)
    sites = extractor.extract_sites(cfgs)

    assert len(sites) == 2
    site1, site2 = sites[0], sites[1]
    assert site1.mutex_canonical_id == "%m1"
    assert site1.lockset_at_entry == frozenset()
    assert site2.mutex_canonical_id == "%m2"
    assert site2.lockset_at_entry == frozenset(["%m1"])
