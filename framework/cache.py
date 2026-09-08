# cache.py
from dataclasses import dataclass
from typing import FrozenSet, Tuple, Optional, TypeVar, Generic
from framework.clock import V, I, T
from framework.sequence import Request

@dataclass(frozen=True)
class CacheState(Generic[V]):
  """
  Cache state at time t:

    C_t = (t, C, k)
    where C is a frozenset of (i, v) entries, |C| <= k.

  Invariant (uniqueness):
    ∀ i : there is at most one (i, v) in C.
  """
  t: T # current time (interneal time)
  C: FrozenSet[Tuple[I, V]] # the cache set itself
  size: int # total capacity of the cache

  def __post_init__(self):
    """
    After initialisation, check all the assertions. Is the size greater than zero, id the current length of the set less than the capacity, etc.
    """
    assert self.size > 0
    assert len(self.C) <= self.size
    # uniqueness invariant
    ids = [i for (i, _) in self.C]
    assert len(ids) == len(set(ids)), "Duplicate object ids in cache state"

  def get(self, i: I) -> Optional[Tuple[I, V]]:
    """
    See if a given item `i` is in the cache. If it is, then return the (i, \tau) pair.
    """
    return next(((j, v) for (j, v) in self.C if j == i), None)

  def getall(self) -> frozenset[I]:
    """
    Get every item in the cache as a set -- so without the associated time-values.
    """
    return frozenset([i[0] for i in self.C])

  def arrival(self, r_j: Request) -> bool:
    """
    The hit-indicator function. h(i) = 1 (hit) if i : C, h(i) = 0 (miss) if i /: C
    """
    if self.get(r_j.i) is not None:
      return 1 # hit
    return 0 # miss

  def replace(self, rmv=None, add=None) -> "CacheState[V]":
    """
    Replacement function used during evictions.
    rmv and add are *items*, not the requests themselves.
    """
    C1 = self.C if rmv is None else (self.C - {rmv})
    C2 = C1 if add is None else (C1 | {add})
    assert len(C2) <= self.size, "Cache overflow: must evict before admitting"
    return CacheState(t=self.t, C=C2, size=self.size)
