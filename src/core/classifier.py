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

from typing import List, Set, Optional
from src.core.lock_site import LockSite
from src.core.lsg import LockSiteGraph
from src.analysis.alias_resolver import AliasResolver



# Standard C memory functions that always write to their first argument.
# If any of these appear in a CS, the lock cannot be EMPTY_CS.
_MEM_WRITE_FUNCS = frozenset({
    "memset", "bzero", "memcpy", "memmove", "memccpy",
    "strcpy", "strncpy", "strcat", "strncat", "sprintf", "snprintf",
    "bcopy",
})


def is_stack_local(var_name: str) -> bool:
    """Returns True if a variable identifier is a stack-local register (%var)."""
    clean = var_name.split("::")[-1].strip()
    return clean.startswith("%") and not clean.startswith("@")


class Classifier:

    """Classifies LockSite objects into anti-patterns based on LSG graph context."""

    def __init__(self, lsg: LockSiteGraph, alias_resolver: Optional[AliasResolver] = None) -> None:
        self.lsg = lsg
        self.alias_resolver = alias_resolver
        # Identify mutexes that have asymmetric/escaping acquisitions across the module (barrier/gate locks)
        self.escaping_mutexes: Set[str] = set()
        for s in self.lsg.sites_by_id.values():
            if not s.unlock_source_lines:
                self.escaping_mutexes.add(s.mutex_canonical_id)

    def _is_stack_local(self, var_name: str) -> bool:
        """Returns True only if var_name traces back to a true stack alloca."""
        clean = var_name.split("::")[-1].strip()
        if self.alias_resolver is not None:
            return self.alias_resolver.is_stack_alloca(clean)
        return is_stack_local(clean)

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

        # Check if any calls inside the CS are standard C memory-writing functions.
        # Those functions write to memory even if not captured as explicit LLVM stores.
        has_mem_write_call = any(c in _MEM_WRITE_FUNCS for c in site.calls)

        has_share_conflict = self.lsg.has_share_edge(site.site_id)
        effective_conflict = has_share_conflict and not self.lsg.all_share_edges_have_hb(site.site_id)

        # Pattern 1: EMPTY_CS
        # A CS is empty only if: no memory vars, no function calls, no indirect calls,
        # AND no calls to standard C memory-writing functions (memset, memcpy, etc.)
        # AND no detected LLVM memory intrinsics (even if variable extraction failed).
        if (not all_vars and not site.calls and not site.has_indirect_calls
                and not has_mem_write_call and not site.has_memory_intrinsic
                and not site.has_inline_asm):
            reasons.append("EMPTY_CS")

        # Pattern 2: LOCAL_VARS
        # Only flag if every accessed variable traces back to a true alloca (stack var).
        # GEP-derived pointers from parameters or globals are NOT local.
        elif (all_vars and all(self._is_stack_local(v) for v in all_vars) 
              and not site.has_indirect_calls and not effective_conflict
              and not site.has_inline_asm and not site.has_memory_intrinsic):
            reasons.append("LOCAL_VARS")

        # Pattern 3: READ_ONLY
        elif all_vars and not all_writes and not effective_conflict and not site.has_indirect_calls:
            reasons.append("READ_ONLY")

        # Pattern 4: THREAD_LOCAL
        # Only flag THREAD_LOCAL if the critical section has no writes (read-only unshared data)
        # and has no SHARE conflict edges in the LSG.
        # If the lock protects writes to non-stack memory, the lock is necessary.
        elif all_vars and not all_writes and not effective_conflict and not site.has_indirect_calls and "READ_ONLY" not in reasons:
            if not self.lsg.has_share_edge(site.site_id):
                reasons.append("THREAD_LOCAL")


        # Pattern 5: REDUNDANT (lock nesting)
        if self.lsg.has_nest_edge_in(site.site_id):
            parent = self.lsg.get_nest_parent(site.site_id)
            if parent:
                parent_coverage = parent.reads | parent.writes | parent.transitive_reads | parent.transitive_writes
                site_needs = all_vars
                # Soundness guard: only flag REDUNDANT if no other site has a SHARE
                # conflict with this site outside the parent-child nesting context.
                # If the site's variables are contested by external sites (not nested
                # under the same parent), then the inner lock is still necessary.
                has_external_share = self._has_external_share_conflict(site.site_id, parent.site_id)
                if site_needs.issubset(parent_coverage) and not has_external_share:
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

    def _has_external_share_conflict(self, child_site_id: str, parent_site_id: str) -> bool:
        """Returns True if the child site has SHARE edges to sites that are NOT
        themselves nested children of the same parent. This means the child lock's
        variables are contested from outside the parent's protection scope, making
        the child lock still necessary (not truly REDUNDANT).
        """
        share_neighbors = self.lsg.get_share_neighbors(child_site_id)
        if not share_neighbors:
            return False
        # Get all siblings nested under the same parent
        parent_children = self.lsg.get_nest_children(parent_site_id)
        for neighbor_id in share_neighbors:
            # If any SHARE partner is not a child of the same parent, it's external
            if neighbor_id != parent_site_id and neighbor_id not in parent_children:
                return True
        return False

    def _apply_safety_guards(self, site: LockSite, reasons: List[str]) -> List[str]:
        """Filters candidate reasons against safety constraints."""
        filtered = list(reasons)

        # Guard 1: Indirect calls present -> CS behaviour is opaque.
        # Unknown callback targets could perform non-trivial shared memory operations.
        # Only SINGLE_THREAD (temporal/structural ordering) is soundly safe.
        if site.has_indirect_calls:
            filtered = [r for r in filtered if r in ("SINGLE_THREAD",)]

        # Guard 2: Condition variable wait mutex -> discard EMPTY_CS, READ_ONLY, REDUNDANT
        if site.is_cond_wait_mutex:
            filtered = [r for r in filtered if r not in ("EMPTY_CS", "READ_ONLY", "REDUNDANT")]

        # Guard 3: Recursive mutex -> discard REDUNDANT
        if site.mutex_is_recursive:
            filtered = [r for r in filtered if r != "REDUNDANT"]

        # Guard 4: Escaping lock / wrapper function (no intra-procedural unlock found)
        # Without a visible unlock boundary, CS content cannot be soundly evaluated.
        if not site.unlock_source_lines:
            filtered = [r for r in filtered if r in ("SINGLE_THREAD",)]

        # Guard 5: Barrier / Gate mutex (mutex has escaping/unbalanced lock acquisition across functions)
        # Empty critical sections lock(M); unlock(M); are intentional barrier waits, not useless locks.
        if site.mutex_canonical_id in self.escaping_mutexes:
            filtered = [r for r in filtered if r not in ("EMPTY_CS",)]

        return filtered
