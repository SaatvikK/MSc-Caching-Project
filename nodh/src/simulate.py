# simulate.py
from dataclasses import dataclass
from typing import Callable, Tuple, TypeVar, Generic
from sequence import Sequence, Request, I, T
from cache import CacheState
from policies import policy_R_TTL, policy_LRU

V = TypeVar("V")

PolicyLRU = Callable[[CacheState[T], I, T], Tuple[bool, CacheState[T]]]
PolicyTTL = Callable[[CacheState[T], I, T, T], Tuple[bool, CacheState[T]]]

@dataclass(frozen=True)
class Stats:
  hits: int
  misses: int

  @property
  def total(self) -> int:
    return self.hits + self.misses

  @property
  def hit_ratio(self) -> float:
    return 0.0 if self.total == 0 else self.hits / self.total


def run_LRU(seq: Sequence, cache_size: int, verbose: bool = True) -> Stats:
  if verbose:
    print("====== Beginning Caching Process: LRU ======")

  C_t = CacheState[T](t=0, C=frozenset(), size=cache_size)
  h, m = 0, 0

  for r in seq.S:
    hit, C_t1 = policy_LRU(C_t, r.i, r.t)

    if hit:
      h += 1
      if verbose:
        print("Request", r, "at time", r.t, ": Item is in cache. Hit.")
        print("-----> Cache time-stamp is updated:", C_t1.C)
    else:
      m += 1
      if verbose:
        print("Request", r, "at time", r.t, ": Item is not in cache. Miss.")
        print("-----> Cache after policy:", C_t1.C)

    if verbose:
      print(" ")

    C_t = C_t1

  if verbose:
    print("hits:", h, "misses:", m)
    print("hit ratio:", round(h / (h + m), 2) if (h + m) > 0 else 0.0)

  return Stats(hits=h, misses=m)


def run_R_TTL(seq: Sequence, cache_size: int, ttl: int, verbose: bool = True) -> Stats:
  if verbose:
    print("====== Beginning Caching Process: R-Policy TTL ======")

  C_t = CacheState[T](t=0, C=frozenset(), size=cache_size)
  h, m = 0, 0


  for r in seq.S:
    hit, C_t1 = policy_R_TTL(C_t, r.i, r.t, ttl)

    if hit:
      h += 1
      if verbose:
        print("Request", r, "at time", r.t, ": Item is in cache. Hit.")
        print("-----> Cache TTL is reset:", C_t1.C)
    else:
      m += 1
      if verbose:
        print("Request", r, "at time", r.t, ": Item is not in cache. Miss.")
        print("-----> Cache after policy:", C_t1.C)

    if verbose:
      print(" ")

    C_t = C_t1

  if verbose:
    print("hits:", h, "misses:", m)
    print("hit ratio:", round(h / (h + m), 2) if (h + m) > 0 else 0.0)

  return Stats(hits=h, misses=m)
