"""Lock Site Graph (LSG) Builder.

Builds a NetworkX directed multigraph G = (S, A) where nodes represent LockSite instances
and edges represent typed relationships:
- SHARE: data conflict on shared memory variables (read/write or write/write).
- NEST: lock nesting / parent-child redundancy.
- HB: happens-before temporal ordering between sites.
"""

from enum import Enum
from typing import Dict, List, Set, Optional, Tuple
import networkx as nx
from src.core.lock_site import LockSite
from src.frontend.call_graph import CallGraph


class EdgeKind(Enum):
    """Types of directed edges in the Lock Site Graph."""
    SHARE = "SHARE"
    NEST = "NEST"
    HB = "HB"


class LockSiteGraph:
    """Directed multigraph representation of lock sites and their relationships."""

    def __init__(self, call_graph: Optional[CallGraph] = None) -> None:
        self.graph = nx.MultiDiGraph()
        self.call_graph = call_graph or CallGraph()
        self.sites_by_id: Dict[str, LockSite] = {}
        self.sites_by_mutex: Dict[str, List[LockSite]] = {}

    def add_site(self, site: LockSite) -> None:
        """Adds a LockSite node to the graph."""
        self.graph.add_node(site.site_id, site=site)
        self.sites_by_id[site.site_id] = site

        if site.mutex_canonical_id not in self.sites_by_mutex:
            self.sites_by_mutex[site.mutex_canonical_id] = []
        self.sites_by_mutex[site.mutex_canonical_id].append(site)

    def build_graph(self, sites: List[LockSite]) -> None:
        """Populates nodes and constructs all SHARE, NEST, and HB edges.

        Args:
            sites: List of characterized LockSite objects.
        """
        for site in sites:
            self.add_site(site)

        self._build_share_edges()
        self._build_nest_edges()
        self._build_hb_edges()

    def _build_share_edges(self) -> None:
        """Constructs SHARE edges between sites accessing the same shared variable with at least one write using an inverted index."""
        sites_list = list(self.sites_by_id.values())
        var_to_sites: Dict[str, Set[str]] = {}

        for site in sites_list:
            all_vars = site.reads | site.writes | site.transitive_reads | site.transitive_writes
            for v in all_vars:
                if v not in var_to_sites:
                    var_to_sites[v] = set()
                var_to_sites[v].add(site.site_id)

        added_edges = set()
        for site in sites_list:
            writes = site.writes | site.transitive_writes
            if not writes:
                continue
            for w_var in writes:
                for other_site_id in var_to_sites.get(w_var, ()):
                    if other_site_id != site.site_id:
                        edge_key = (site.site_id, other_site_id)
                        if edge_key not in added_edges:
                            self.graph.add_edge(site.site_id, other_site_id, key=EdgeKind.SHARE.value, kind=EdgeKind.SHARE)
                            self.graph.add_edge(other_site_id, site.site_id, key=EdgeKind.SHARE.value, kind=EdgeKind.SHARE)
                            added_edges.add(edge_key)
                            added_edges.add((other_site_id, site.site_id))

    def _build_nest_edges(self) -> None:
        """Constructs NEST edges from parent lock site to nested child lock site."""
        for child_site in self.sites_by_id.values():
            for parent_mutex_id in child_site.lockset_at_entry:
                # Find parent sites holding parent_mutex_id when child_site is acquired
                if parent_mutex_id in self.sites_by_mutex:
                    for parent_site in self.sites_by_mutex[parent_mutex_id]:
                        if parent_site.site_id != child_site.site_id:
                            self.graph.add_edge(parent_site.site_id, child_site.site_id,
                                                key=EdgeKind.NEST.value, kind=EdgeKind.NEST)

    def _build_hb_edges(self) -> None:
        """Constructs HB (Happens-Before) edges for statically ordered execution phases."""
        sites_list = list(self.sites_by_id.values())
        for s1 in sites_list:
            for s2 in sites_list:
                if s1.site_id == s2.site_id:
                    continue
                # Statically ordered: single-threaded init phase (is_single_thread) before parallel phase
                if s1.is_single_thread and not s2.is_single_thread:
                    self.graph.add_edge(s1.site_id, s2.site_id, key=EdgeKind.HB.value, kind=EdgeKind.HB)

    def has_share_edge(self, site_id: str) -> bool:
        """Returns True if the site has any incident SHARE conflict edge."""
        if site_id not in self.graph:
            return False
        for _, _, data in self.graph.edges(site_id, data=True):
            if data.get("kind") == EdgeKind.SHARE:
                return True
        return False

    def has_nest_edge_in(self, site_id: str) -> bool:
        """Returns True if the site has an incoming NEST edge from an outer parent lock."""
        if site_id not in self.graph:
            return False
        for _, _, data in self.graph.in_edges(site_id, data=True):
            if data.get("kind") == EdgeKind.NEST:
                return True
        return False

    def get_nest_parent(self, site_id: str) -> Optional[LockSite]:
        """Returns the parent LockSite if an incoming NEST edge exists."""
        if site_id not in self.graph:
            return None
        for u, _, data in self.graph.in_edges(site_id, data=True):
            if data.get("kind") == EdgeKind.NEST:
                return self.sites_by_id.get(u)
        return None

    def all_share_edges_have_hb(self, site_id: str) -> bool:
        """Returns True if all SHARE edges connected to site_id are ordered by a HB edge."""
        if not self.has_share_edge(site_id):
            return False

        share_neighbors = set()
        for u, v, data in self.graph.edges(site_id, data=True):
            if data.get("kind") == EdgeKind.SHARE:
                share_neighbors.add(v)

        for neighbor in share_neighbors:
            has_hb = False
            for u, v, data in self.graph.edges(data=True):
                if data.get("kind") == EdgeKind.HB:
                    if (u == site_id and v == neighbor) or (u == neighbor and v == site_id):
                        has_hb = True
                        break
            if not has_hb:
                return False
        return True
