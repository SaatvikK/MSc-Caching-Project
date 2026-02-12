# cache.py
from dataclasses import dataclass
from typing import FrozenSet, Tuple, Optional, TypeVar, Generic

I = int
T = int
V = TypeVar("V")  # value (timestamp, ttl, etc.)

@dataclass(frozen=True)
class CacheState(Generic[V]):
  """
  Cache state at time t:

    C_t = (t, C, k)
    where C is a frozenset of (i, v) entries, |C| <= k.

  Invariant (uniqueness):
    ∀ i : there is at most one (i, v) in C.
  """
  t: T # type: ignore
  C: FrozenSet[Tuple[I, V]] # type: ignore
  size: int
  policy: int
  polName: str

  def __post_init__(self):
    assert self.size > 0
    assert len(self.C) <= self.size
    # uniqueness invariant
    ids = [i for (i, _) in self.C]
    assert len(ids) == len(set(ids)), "Duplicate object ids in cache state"

  def get(self, i: I) -> Optional[Tuple[I, V]]:
    return next(((j, v) for (j, v) in self.C if j == i), None)

  def stepTime(self, t1: T) -> "CacheState[V]":
    """
    Move time forward without changing contents.
    """
    assert t1 == self.t + 1
    return CacheState(t=t1, C=self.C, size=self.size, policy = self.policy, polName = self.polName)

  def replace(self, rmv: Optional[Tuple[I, V]], add: Optional[Tuple[I, V]]) -> "CacheState[V]":
    """
    Pure set-update operator, with time increment baked in.

    Pre-state:  C_t = (t, C, k)
    Post-state: C_{t+1} = (t+1, C', k)

    where:
      if rmv is None: C1 = C
      else:           C1 = C \ {rmv}

      if add is None: C' = C1
      else:           C' = C1 ∪ {add}

    (and still |C'| <= k and uniqueness holds).
    """
    t1 = self.t + 1

    C1 = self.C if rmv is None else (self.C - {rmv})
    C2 = C1 if add is None else (C1 | {add})

    return CacheState(t=t1, C=C2, size=self.size, policy = self.policy, polName = self.polName)
