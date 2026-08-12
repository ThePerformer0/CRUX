"""LockSite Dataclass.

Represents a single synchronization lock acquisition site in the LLVM IR, storing
metadata, direct and transitive memory access sets, path conditions, entry lockset,
classification results, and SMT validation status.
"""

from dataclasses import dataclass, field
from typing import List, Set, FrozenSet


@dataclass
class LockSite:
    """Represents a lock site and its characterized critical section."""

    # Identification
    site_id: str
    mutex_canonical_id: str
    mutex_name: str
    function: str
    source_file: str = "unknown.c"
    lock_source_line: int = 0
    unlock_source_lines: List[int] = field(default_factory=list)

    # Critical Section Content (canonical IDs)
    reads: Set[str] = field(default_factory=set)
    writes: Set[str] = field(default_factory=set)
    calls: List[str] = field(default_factory=list)

    # Interprocedural Analysis
    transitive_reads: Set[str] = field(default_factory=set)
    transitive_writes: Set[str] = field(default_factory=set)
    has_indirect_calls: bool = False

    # SMT Validation
    path_conditions: List[str] = field(default_factory=list)

    # Concurrency Context
    lockset_at_entry: FrozenSet[str] = field(default_factory=frozenset)
    is_single_thread: bool = False
    is_cond_wait_mutex: bool = False
    mutex_is_recursive: bool = False

    # Classification & Verdict
    is_useless: bool = False
    reasons: List[str] = field(default_factory=list)
    confidence_score: float = 1.0
    suggested_fix: str = ""
    smt_confirmed: bool = False
