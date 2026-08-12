"""Unit tests for Lock Site Graph builder (src/core/lsg.py)."""

import pytest
from src.core.lock_site import LockSite
from src.core.lsg import LockSiteGraph, EdgeKind


def test_lsg_node_addition():
    """Verify LockSite nodes are added correctly to NetworkX graph."""
    site = LockSite(site_id="s1", mutex_canonical_id="%m", mutex_name="%m", function="foo")
    lsg = LockSiteGraph()
    lsg.add_site(site)

    assert "s1" in lsg.graph
    assert lsg.sites_by_id["s1"] == site


def test_share_edge_creation():
    """Verify SHARE edges are created when two sites access same variable with at least one write."""
    s1 = LockSite(site_id="s1", mutex_canonical_id="%m1", mutex_name="%m1", function="f1", writes={"@g_var"})
    s2 = LockSite(site_id="s2", mutex_canonical_id="%m2", mutex_name="%m2", function="f2", reads={"@g_var"})

    lsg = LockSiteGraph()
    lsg.build_graph([s1, s2])

    assert lsg.has_share_edge("s1") is True
    assert lsg.has_share_edge("s2") is True
    assert lsg.graph.has_edge("s1", "s2", key=EdgeKind.SHARE.value)
    assert lsg.graph.has_edge("s2", "s1", key=EdgeKind.SHARE.value)


def test_no_share_edge_on_read_only():
    """Verify no SHARE edge is created when both sites only read shared variables."""
    s1 = LockSite(site_id="s1", mutex_canonical_id="%m1", mutex_name="%m1", function="f1", reads={"@g_var"})
    s2 = LockSite(site_id="s2", mutex_canonical_id="%m2", mutex_name="%m2", function="f2", reads={"@g_var"})

    lsg = LockSiteGraph()
    lsg.build_graph([s1, s2])

    assert lsg.has_share_edge("s1") is False
    assert lsg.has_share_edge("s2") is False


def test_nest_edge_creation():
    """Verify NEST edge is created from parent lock to child nested lock site."""
    s1 = LockSite(site_id="s1", mutex_canonical_id="%m_parent", mutex_name="%m_parent", function="f1")
    s2 = LockSite(site_id="s2", mutex_canonical_id="%m_child", mutex_name="%m_child", function="f2",
                  lockset_at_entry=frozenset(["%m_parent"]))

    lsg = LockSiteGraph()
    lsg.build_graph([s1, s2])

    assert lsg.has_nest_edge_in("s2") is True
    assert lsg.get_nest_parent("s2") == s1
    assert lsg.graph.has_edge("s1", "s2", key=EdgeKind.NEST.value)


def test_hb_edge_creation():
    """Verify HB edge is created between single-threaded site and parallel site."""
    s1 = LockSite(site_id="s1", mutex_canonical_id="%m1", mutex_name="%m1", function="main", is_single_thread=True)
    s2 = LockSite(site_id="s2", mutex_canonical_id="%m2", mutex_name="%m2", function="worker", is_single_thread=False)

    lsg = LockSiteGraph()
    lsg.build_graph([s1, s2])

    assert lsg.graph.has_edge("s1", "s2", key=EdgeKind.HB.value)
