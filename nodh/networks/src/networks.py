from cache import CacheState
from dataclasses import dataclass
from typing import FrozenSet, Tuple, Optional, TypeVar, Generic
import random as rand

"""
graph of a network:
{
  root: Cache1
  cach1: [children_caches],
  cache2: [children],
  
}

eg, a line of 3 caches:
{
  root: Cache1
  Cache1: [Cache2],
  Cache2: [Cache3],
  Cache3: []
}

λ
μ
"""

CS = CacheState
I = int
T = int
ttl = 5

@dataclass(frozen=True)
class CacheNetwork:
  N: dict[str, list[str]]
  S: dict[str, CacheState]
  t: int

  def step(self, i: I):
    assert all(C.t == self.t for C in self.S.values())

    hit, newS = self.nodeReq(0, i, self.S)
    for k in range(len(newS)):
      cache = newS[k]
      if cache.t != self.t + 1:
        newS[k] = cache.stepTime(self.t + 1)

    return CacheNetwork(
      N=self.N,
      S=newS,
      t=self.t + 1
    ), hit


  def nodeReq(self, node: str, i: I, S):
    C_t = S[node]

    # local check
    old = C_t.get(i)
    if old is not None:
      hit, C_t1 = C_t.policy(C_t, i, self.t + 1)
      newS = {**S, node: C_t1}
      return True, newS

    # forward to children
    children = self.N[node]
    child = None
    if len(children) > 1:
      child = rand.randint(0, len(children))
    elif len(children) == 1:
      child = children[0]
    
    if child != None:
      hit, newS = self.nodeReq(child, i, S)
      if hit:
        # propagate upstream
        C_t = newS[node]
        hit2, C_t1 = C_t.policy(C_t, i, self.t + 1)
        newS = {**newS, node: C_t1}
        return True, newS
      S = newS

    # leaf miss: fetch from origin
    hit2, C_t1 = C_t.policy(C_t, i, self.t + 1)
    newS = {**S, node: C_t1}
    return False, newS
  
  def snapshot(self) -> str:
    """
    Returns a deterministic string describing node cache contents.
    """
    # Print nodes in sorted order (exclude "root" because it's a pointer)
    nodes = sorted([k for k in self.S.keys()])
    parts = []
    for u in nodes:
      C_u = self.S[u]
      parts.append(f"C{u}:{sorted(C_u.C)}")
    return " | ".join(parts)
  