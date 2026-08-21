"""Unit tests for Interprocedural Lockset Analysis & Function Summaries."""

import pytest
from src.frontend.cfg_builder import build_cfgs
from src.frontend.call_graph import build_call_graph
from src.analysis.alias_resolver import AliasResolver
from src.analysis.lockset_analyzer import LocksetAnalyzer
from src.analysis.site_extractor import SiteExtractor
from src.core.lsg import LockSiteGraph, EdgeKind
from src.core.classifier import Classifier


def test_interprocedural_function_summary_wrapper():
    """Verify function summaries capture net acquires and net releases across wrapper functions."""
    ir = """
    @g_lock = global i8 0

    define void @acquire_wrapper() {
    entry:
        call i32 @pthread_mutex_lock(i8* @g_lock)
        ret void
    }

    define void @release_wrapper() {
    entry:
        call i32 @pthread_mutex_unlock(i8* @g_lock)
        ret void
    }

    define void @caller() {
    entry:
        call void @acquire_wrapper()
        %x = alloca i32
        call void @release_wrapper()
        ret void
    }
    """
    cfgs = build_cfgs(ir)
    resolver = AliasResolver()
    resolver.analyze_cfgs(cfgs)

    analyzer = LocksetAnalyzer(resolver)
    summaries = analyzer.compute_all_summaries(cfgs)

    # acquire_wrapper has net_acquires = {@g_lock}
    assert "@g_lock" in summaries["acquire_wrapper"].net_acquires
    assert not summaries["acquire_wrapper"].is_balanced

    # release_wrapper has net_releases = {@g_lock}
    assert "@g_lock" in summaries["release_wrapper"].net_releases
    assert not summaries["release_wrapper"].is_balanced

    # When caller is analyzed with summaries, instruction after acquire_wrapper holds @g_lock
    states = analyzer.analyze_cfg(cfgs["caller"], function_summaries=summaries)
    # entry[0] is call acquire_wrapper (before call: empty)
    assert states["entry"][0].lockset == frozenset()
    # entry[1] is %x = alloca (after acquire_wrapper: holds @g_lock)
    assert "@g_lock" in states["entry"][1].lockset
    # entry[2] is call release_wrapper (before release: holds @g_lock)
    assert "@g_lock" in states["entry"][2].lockset
    # entry[3] is ret void (after release: empty)
    assert states["entry"][3].lockset == frozenset()


def test_interprocedural_nested_redundant_lock():
    """Verify that when outer function holds lock and calls inner function which acquires same lock,
    the inner lock is classified as REDUNDANT via interprocedural entry lockset propagation.
    """
    ir = """
    @shared_lock = global i8 0
    @shared_data = global i32 0

    define void @inner_helper() {
    entry:
        call i32 @pthread_mutex_lock(i8* @shared_lock)
        store i32 42, i32* @shared_data
        call i32 @pthread_mutex_unlock(i8* @shared_lock)
        ret void
    }

    define void @outer_caller() {
    entry:
        call i32 @pthread_mutex_lock(i8* @shared_lock)
        store i32 10, i32* @shared_data
        call void @inner_helper()
        call i32 @pthread_mutex_unlock(i8* @shared_lock)
        ret void
    }
    """
    cfgs = build_cfgs(ir)
    cg = build_call_graph(ir)
    resolver = AliasResolver()
    resolver.analyze_cfgs(cfgs)

    analyzer = LocksetAnalyzer(resolver)
    extractor = SiteExtractor(resolver, cg, analyzer)
    sites = extractor.extract_sites(cfgs)

    # 2 lock sites extracted: s1 in inner_helper, s2 in outer_caller (or vice versa)
    assert len(sites) == 2

    inner_site = next(s for s in sites if s.function == "inner_helper")
    outer_site = next(s for s in sites if s.function == "outer_caller")

    # The inner site must have inherited @shared_lock in its entry lockset!
    assert "@shared_lock" in inner_site.lockset_at_entry
    # The outer site starts with empty lockset
    assert len(outer_site.lockset_at_entry) == 0

    # Build LSG
    lsg = LockSiteGraph(cg)
    lsg.build_graph(sites)

    # Verify NEST edge from outer to inner
    assert lsg.graph.has_edge(outer_site.site_id, inner_site.site_id)
    edge_data = lsg.graph.get_edge_data(outer_site.site_id, inner_site.site_id)
    assert any(d.get("kind") == EdgeKind.NEST for d in edge_data.values())

    # Classify
    classifier = Classifier(lsg)
    classifier.classify_all()

    # Inner site must be marked as REDUNDANT!
    assert inner_site.is_useless
    assert "REDUNDANT" in inner_site.reasons

    # Outer site protects real shared writes and is NOT redundant
    assert not outer_site.is_useless


def test_interprocedural_multiple_callers_sound_intersection():
    """Verify conservative intersection: if a function is called from 2 callers,
    one holding the lock and one NOT holding it, the entry lockset is empty.
    """
    ir = """
    @m = global i8 0

    define void @callee() {
    entry:
        ret void
    }

    define void @caller_with_lock() {
    entry:
        call i32 @pthread_mutex_lock(i8* @m)
        call void @callee()
        call i32 @pthread_mutex_unlock(i8* @m)
        ret void
    }

    define void @caller_without_lock() {
    entry:
        call void @callee()
        ret void
    }
    """
    cfgs = build_cfgs(ir)
    resolver = AliasResolver()
    resolver.analyze_cfgs(cfgs)

    analyzer = LocksetAnalyzer(resolver)
    entry_locksets = analyzer.compute_interprocedural_entry_locksets(cfgs)

    # Intersection of {@m} and {} is empty frozenset() -> Sound!
    assert entry_locksets["callee"] == frozenset()
