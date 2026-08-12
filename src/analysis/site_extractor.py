"""Lock Site Characterizer.

Identifies lock acquisition calls, traces critical sections to their matching unlock calls,
and computes direct/transitive memory reads, writes, indirect call flags, path conditions,
and entry locksets for each LockSite object.
"""
