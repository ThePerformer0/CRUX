"""Lock Site Graph (LSG) Builder.

Builds a NetworkX directed multigraph G = (S, A) where nodes represent LockSite instances
and edges represent typed relationships:
- SHARE: data conflict on shared memory variables (read/write or write/write).
- NEST: lock nesting / parent-child redundancy.
- HB: happens-before temporal ordering between sites.
"""
