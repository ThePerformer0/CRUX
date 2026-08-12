"""Crux Anti-Pattern Classifier.

Evaluates LockSite nodes in the Lock Site Graph against the 6 anti-patterns:
- EMPTY_CS: critical section contains no memory operations.
- LOCAL_VARS: critical section operates strictly on stack-local variables (alloca).
- READ_ONLY: critical section only reads shared variables, with zero global writes in the program.
- REDUNDANT: lock is acquired under an enclosing parent lock covering the same variables.
- SINGLE_THREAD: lock is acquired in a single-threaded execution context.
- THREAD_LOCAL: variables are thread-local and unshared across threads.

Enforces strict safety guards (indirect calls, cond_wait, recursive mutexes).
"""

from typing import List, Set
from src.core.lock_site import LockSite
from src.core.lsg import LockSiteGraph


def is_stack_local(var_name: str) -> bool:
    """Returns True if a variable identifier is a stack-local register (%var)."""
    clean = var_name.strip()
    return clean.startswith("%") and not clean.startswith("@")


class Classifier:
    """Classifies LockSite objects into anti-patterns based on LSG graph context."""

    def __init__(self, lsg: LockSiteGraph) -> None:
        self.lsg = lsg

    def classify_site(self, site: LockSite) -> List[str]:
        """Evaluates a LockSite and returns a list of applicable anti-pattern reasons.

        Args:
            site: LockSite instance to evaluate.

        Returns:
            List of anti-pattern strings (e.g. ['EMPTY_CS'], ['READ_ONLY'], etc.).
        """
        reasons: List[str] = []

        all_vars = site.reads | site.writes | site.transitive_reads | site.transitive_writes
        all_writes = site.writes | site.transitive_writes

        has_share_conflict = self.lsg.has_share_edge(site.site_id)
        effective_conflict = has_share_conflict and not self.lsg.all_share_edges_have_hb(site.site_id)

        # Pattern 1: EMPTY_CS
        if not all_vars and not site.calls and not site.has_indirect_calls:
            reasons.append("EMPTY_CS")

        # Pattern 2: LOCAL_VARS
        elif all_vars and all(is_stack_local(v) for v in all_vars) and not site.has_indirect_calls and not effective_conflict:
            reasons.append("LOCAL_VARS")

        # Pattern 3: READ_ONLY
        elif all_vars and not all_writes and not effective_conflict and not site.has_indirect_calls:
            reasons.append("READ_ONLY")

        # Pattern 4: THREAD_LOCAL
        elif all_vars and not is_stack_local(next(iter(all_vars))) and not effective_conflict and not site.has_indirect_calls and "READ_ONLY" not in reasons:
            reasons.append("THREAD_LOCAL")

        # Pattern 5: REDUNDANT (lock nesting)
        if self.lsg.has_nest_edge_in(site.site_id):
            parent = self.lsg.get_nest_parent(site.site_id)
            if parent:
                parent_coverage = parent.reads | parent.writes | parent.transitive_reads | parent.transitive_writes
                site_needs = all_vars
                if site_needs.issubset(parent_coverage):
                    reasons.append("REDUNDANT")

        # Pattern 6: SINGLE_THREAD
        if site.is_single_thread:
            reasons.append("SINGLE_THREAD")

        # Apply Safety Guards
        reasons = self._apply_safety_guards(site, reasons)

        # Update LockSite verdict fields
        site.reasons = reasons
        site.is_useless = len(reasons) > 0

        return reasons

    def classify_all(self) -> List[LockSite]:
        """Classifies all sites in the LSG and returns the list of evaluated sites."""
        sites = list(self.lsg.sites_by_id.values())
        for site in sites:
            self.classify_site(site)
        return sites

    def _apply_safety_guards(self, site: LockSite, reasons: List[str]) -> List[str]:
        """Filters candidate reasons against safety constraints."""
        filtered = list(reasons)

        # Guard 1: Indirect calls present -> keep ONLY REDUNDANT and SINGLE_THREAD
        if site.has_indirect_calls:
            filtered = [r for r in filtered if r in ("REDUNDANT", "SINGLE_THREAD")]

        # Guard 2: Condition variable wait mutex -> discard EMPTY_CS, READ_ONLY, REDUNDANT
        if site.is_cond_wait_mutex:
            filtered = [r for r in filtered if r not in ("EMPTY_CS", "READ_ONLY", "REDUNDANT")]

        # Guard 3: Recursive mutex -> discard REDUNDANT
        if site.mutex_is_recursive:
            filtered = [r for r in filtered if r != "REDUNDANT"]

        return filtered
