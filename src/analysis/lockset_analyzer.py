"""BFS Control-Flow Lockset Analyzer.

Performs BFS dataflow analysis on function CFGs to track the set of held locks
(lockset) at every instruction point. Features conservative intersection join operations,
`pthread_cond_wait` handling (net effect 0), and path condition collection.
"""
