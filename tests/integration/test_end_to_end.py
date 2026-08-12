"""Integration end-to-end tests for CRUX analysis on synthetic LLVM IR benchmarks."""

import os
import json
import pytest
from crux import main
from src.frontend.call_graph import build_call_graph
from src.frontend.cfg_builder import build_cfgs
from src.analysis.alias_resolver import AliasResolver
from src.analysis.lockset_analyzer import LocksetAnalyzer
from src.analysis.site_extractor import SiteExtractor
from src.core.lsg import LockSiteGraph
from src.core.classifier import Classifier
from src.validation.smt_validator import SMTValidator
from src.output.reporter import generate_report

FIXTURES_DIR = os.path.dirname(__file__)


def run_crux_pipeline(ll_filename: str):
    ll_path = os.path.join(FIXTURES_DIR, ll_filename)
    with open(ll_path, "r", encoding="utf-8") as f:
        llvm_ir_text = f.read()

    call_graph = build_call_graph(llvm_ir_text)
    cfgs = build_cfgs(llvm_ir_text)
    alias_resolver = AliasResolver()
    alias_resolver.analyze_cfgs(cfgs)

    lockset_analyzer = LocksetAnalyzer(alias_resolver)
    site_extractor = SiteExtractor(alias_resolver, call_graph, lockset_analyzer)
    sites = site_extractor.extract_sites(cfgs)

    lsg = LockSiteGraph(call_graph)
    lsg.build_graph(sites)

    classifier = Classifier(lsg)
    classifier.classify_all()

    smt_validator = SMTValidator()
    smt_validator.validate_sites(sites)

    return generate_report(sites, lsg, ll_filename, 0.01)


def test_e2e_empty_cs():
    """Verify Crux detects EMPTY_CS useless lock site."""
    report = run_crux_pipeline("test_empty_cs.ll")
    assert report["summary"]["total_sites"] == 1
    assert report["summary"]["useless_sites"] == 1
    assert "EMPTY_CS" in report["useless_sites"][0]["reasons"]


def test_e2e_local_vars():
    """Verify Crux detects LOCAL_VARS useless lock site."""
    report = run_crux_pipeline("test_local_vars.ll")
    assert report["summary"]["total_sites"] == 1
    assert report["summary"]["useless_sites"] == 1
    assert "LOCAL_VARS" in report["useless_sites"][0]["reasons"]


def test_e2e_read_only():
    """Verify Crux detects READ_ONLY useless lock sites when no global write exists."""
    report = run_crux_pipeline("test_read_only.ll")
    assert report["summary"]["total_sites"] == 2
    assert report["summary"]["useless_sites"] == 2
    for useless in report["useless_sites"]:
        assert "READ_ONLY" in useless["reasons"]


def test_e2e_redundant():
    """Verify Crux detects REDUNDANT nested lock site."""
    report = run_crux_pipeline("test_redundant.ll")
    assert report["summary"]["total_sites"] == 2
    assert report["summary"]["useless_sites"] == 1
    assert "REDUNDANT" in report["useless_sites"][0]["reasons"]


def test_e2e_useful():
    """Verify Crux flags zero useless sites for useful locks protecting shared writes."""
    report = run_crux_pipeline("test_useful.ll")
    assert report["summary"]["total_sites"] == 2
    assert report["summary"]["useless_sites"] == 0
