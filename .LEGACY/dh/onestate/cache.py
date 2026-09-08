# cache.py
from dataclasses import dataclass
from typing import FrozenSet, Tuple, Optional, TypeVar, Generic
from LEGACY.dh.onestate.clock import V, I, T
from LEGACY.dh.onestate.sequence import Request

@dataclass(frozen=True)
class CacheState(Generic[V]):
  """
  Cache state at time t:

    C_t = (t, C, k)
    where C is a frozenset of (i, v) entries, |C| <= k.

  Invariant (uniqueness):
    ∀ i : there is at most one (i, v) in C.
  """
  t: T
  C: FrozenSet[Tuple[I, V]]
  size: int

  def __post_init__(self):
    assert self.size > 0
    assert len(self.C) <= self.size
    # uniqueness invariant
    ids = [i for (i, _) in self.C]
    assert len(ids) == len(set(ids)), "Duplicate object ids in cache state"

  def get(self, i: I) -> Optional[Tuple[I, V]]:
    return next(((j, v) for (j, v) in self.C if j == i), None)

  def arrival(self, r_j: Request):
    if self.get(r_j.i) is not None:
      return 1 # hit
    return 0 # miss

  def replace(self, rmv=None, add=None) -> "CacheState[V]":
    C1 = self.C if rmv is None else (self.C - {rmv})
    C2 = C1 if add is None else (C1 | {add})
    assert len(C2) <= self.size, "Cache overflow: must evict before admitting"
    return CacheState(t=self.t, C=C2, size=self.size)
