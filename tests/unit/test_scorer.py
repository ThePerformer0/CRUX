"""Unit tests for Scorer & Reporter (src/output/scorer.py & reporter.py)."""

import pytest
from src.core.lock_site import LockSite
from src.core.lsg import LockSiteGraph
from src.output.scorer import compute_confidence_score, suggest_fix
from src.output.reporter import generate_report


def test_confidence_score_calculation():
    """Verify confidence score applies positive and negative factors correctly."""
    site = LockSite(site_id="s1", mutex_canonical_id="@global_mutex", mutex_name="@global_mutex",
                    function="foo", reasons=["EMPTY_CS"], smt_confirmed=True)
    lsg = LockSiteGraph()
    lsg.build_graph([site])

    score = compute_confidence_score(site, lsg)
    # Score has bonus from SMT (1.3), global mutex (1.1), EMPTY_CS (1.2) capped at 1.0
    assert score == 1.0


def test_suggested_fix_generation():
    """Verify fix recommendation messages for different anti-pattern reasons."""
    s_empty = LockSite(site_id="s1", mutex_canonical_id="%m", mutex_name="%m", function="f", reasons=["EMPTY_CS"])
    s_read = LockSite(site_id="s2", mutex_canonical_id="%m", mutex_name="%m", function="f", reasons=["READ_ONLY"])
    s_redundant = LockSite(site_id="s3", mutex_canonical_id="%m", mutex_name="%m", function="f", reasons=["REDUNDANT"])

    assert "vide" in suggest_fix(s_empty)
    assert "pthread_rwlock_rdlock" in suggest_fix(s_read)
    assert "parent" in suggest_fix(s_redundant)


def test_json_reporter_format():
    """Verify generate_report produces schema-compliant output."""
    site = LockSite(site_id="s1", mutex_canonical_id="%m", mutex_name="%m", function="foo",
                    is_useless=True, reasons=["EMPTY_CS"])
    lsg = LockSiteGraph()
    lsg.build_graph([site])

    report = generate_report([site], lsg, llvm_ir_file="test.ll", analysis_time=0.05)

    assert report["metadata"]["tool"] == "crux"
    assert report["summary"]["total_sites"] == 1
    assert report["summary"]["useless_sites"] == 1
    assert len(report["useless_sites"]) == 1
    assert report["useless_sites"][0]["id"] == "s1"
