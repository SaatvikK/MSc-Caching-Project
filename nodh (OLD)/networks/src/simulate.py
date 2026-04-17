# simulate.py
from dataclasses import dataclass
from typing import Callable, Tuple, TypeVar, Generic
from sequence import Sequence, Request, I, T
from cache import CacheNode
from networks import CacheNetwork

V = TypeVar("V")

PolicyLRU = Callable[[CacheNode[T], I, T], Tuple[bool, CacheNode[T]]]
PolicyTTL = Callable[[CacheNode[T], I, T, T], Tuple[bool, CacheNode[T]]]

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


def run_LRU(seq: Sequence, net: CacheNetwork, verbose: bool = True) -> Stats:
  if verbose: print("====== Beginning Caching Process: LRU ======")

  h, m = 0, 0

  for r in seq.S:
    net, hit = net.step(r.i)
    if hit:
      h += 1
      if verbose:
        print("Request", r, "at time", r.t, ": Item is in cache. Hit.")
        print("-----> Cache time-stamp (t =", net.t, ") is updated:", net.snapshot())
    else:
      m += 1
      if verbose:
        print("Request", r, "at time", r.t, ": Item is not in cache. Miss.")
        print("-----> Cache after policy(t =", net.t, "):", net.snapshot())

    if verbose:
      print(" ")

  if verbose:
    print("hits:", h, "misses:", m)
    print("hit ratio:", round(h / (h + m), 2) if (h + m) > 0 else 0.0)

  return Stats(hits=h, misses=m)


def run_R_TTL(seq: Sequence, net: CacheNetwork, verbose: bool = True) -> Stats:
  if verbose:
    print("====== Beginning Caching Process: R-Policy TTL ======")

  h, m = 0, 0

  for r in seq.S:
    net, hit = net.step(r.i)
    if hit:
      h += 1
      if verbose:
        print("Request", r, "at time", r.t, ": Item is in cache. Hit.")
        print("-----> Cache TTL is reset:", net.snapshot())
    else:
      m += 1
      if verbose:
        print("Request", r, "at time", r.t, ": Item is not in cache. Miss.")
        print("-----> Cache after policy:", net.snapshot())

    if verbose:
      print(" ")

  if verbose:
    print("hits:", h, "misses:", m)
    print("hit ratio:", round(h / (h + m), 2) if (h + m) > 0 else 0.0)

  return Stats(hits=h, misses=m)
