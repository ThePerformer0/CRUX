"""Confidence Scorer and Fix Suggester.

Calculates a confidence score in range [0.0, 1.0] for each flagged useless lock site based on
heuristics (indirect calls, call depth, caller fan-in, path complexity, SMT confirmation, global mutexes)
and generates human-readable refactoring suggestions.
"""

from src.core.lock_site import LockSite
from src.core.lsg import LockSiteGraph


def compute_confidence_score(site: LockSite, lsg: LockSiteGraph) -> float:
    """Calculates confidence score in range [0.0, 1.0] for a characterized LockSite.

    Args:
        site: LockSite instance.
        lsg: LockSiteGraph graph context.

    Returns:
        Confidence score float between 0.0 and 1.0.
    """
    score = 1.0

    # Negative factors (reduce confidence)
    if site.has_indirect_calls:
        score *= 0.5

    n_calls = len(site.calls)
    if n_calls > 0:
        score *= (0.9 ** n_calls)

    n_callers = len(lsg.call_graph.get_callers(site.function))
    if n_callers > 20:
        score *= 0.8

    n_conditions = len(site.path_conditions)
    if n_conditions > 5:
        score *= 0.9

    # Positive factors (increase confidence)
    if site.smt_confirmed:
        score *= 1.3

    if site.mutex_canonical_id.startswith("@"):
        score *= 1.1

    if "EMPTY_CS" in site.reasons:
        score *= 1.2

    # Conservative weighting for THREAD_LOCAL (since C lacks managed escape analysis)
    if "THREAD_LOCAL" in site.reasons and len(site.reasons) == 1:
        score *= 0.75

    score = min(score, 1.0)
    score = max(score, 0.0)
    return round(score, 2)


def suggest_fix(site: LockSite) -> str:
    """Generates a human-readable refactoring recommendation for a useless lock site."""
    if "EMPTY_CS" in site.reasons:
        return "Supprimer le verrou : la section critique est vide."
    if "LOCAL_VARS" in site.reasons:
        return "Supprimer le verrou : toutes les variables sont locales."
    if "READ_ONLY" in site.reasons:
        return "Remplacer pthread_mutex_lock par pthread_rwlock_rdlock (lecture seule suffisante)."
    if "REDUNDANT" in site.reasons:
        return "Supprimer le verrou interne : le verrou parent couvre déjà cette section."
    if "SINGLE_THREAD" in site.reasons:
        return "Supprimer le verrou : ce code s'exécute avant toute création de thread."
    if "THREAD_LOCAL" in site.reasons:
        return "Vérifier l'absence de partage global (motif conservatif) : les variables manipulées n'ont aucun conflit concurrent observé."
    return ""

