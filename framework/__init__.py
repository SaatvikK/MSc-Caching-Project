"""The DH-aware cache network framework.

The formal objects of Chapter 4, one module each:

  clock         T, I, Clock          -- time, items, the single master clock
  sequence      Request, Sequence    -- r_j = (i,t) and rho = (r_j)
  cache         CacheState           -- C_t, the frozen (i, tau) set of Def 4.1.2
  policies      TTL, policy          -- the eviction rule, selected by name
  backingstore  BackingStore         -- B, addressed as vertex 'b'
  network       CacheNetwork         -- N = (V,E), plus the CPPs

Re-exported here so callers can write

    from framework import CacheNetwork, CacheState, Clock

rather than reaching into each module. Import order below follows the
dependency chain (clock -> sequence -> cache -> policies -> backingstore ->
network); it is not alphabetical, and reordering it will break the imports.
"""

from framework.clock import V, I, T, Clock
from framework.sequence import Request, Sequence
from framework.cache import CacheState
from framework.policies import TTL, policy
from framework.backingstore import BackingStore
from framework.network import CacheNetwork

__all__ = [
  "V", "I", "T", "Clock",
  "Request", "Sequence",
  "CacheState",
  "TTL", "policy",
  "BackingStore",
  "CacheNetwork",
]
