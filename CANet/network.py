# network.py
from dataclasses import dataclass, field
from typing import Tuple, List, Optional
from clock import V, I, T, Clock
from cache import CacheState
from sequence import Request
from backingstore import BackingStore
from policies import *
import numpy as np
import platform as plat

@dataclass
class CacheNetwork:
  G: Tuple[list, list]  # the topology, G = (V, E) where E is a list of (child, parent) directed edges
  M: dict               # mapping: vertex label -> CacheState
  tmax: T
  clk: Clock
  Z_A: int
  B: BackingStore
  dhCount: int
  QFetch: dict          # tracks in-flight fetches per node: vertex -> list of items being fetched
  QResolve: dict
  ttl: T
  dhLatencies: list = field(default_factory=list)  # latency of each resolved delayed hit
  # Each cache node is given a label that represents the vertex (eg v_1, v_2, etc.)
  # The mapping dict, M, maps each vertex to a CacheState object.
  # Then, in G, we only use the vertex labels.
  # In this way, we can avoid having to 'refresh' specific vertices in G whenever the CacheStates are updated
  # (because an update results in a new CacheState being outputed, they aren't updated in-place).

  # vertex 'b' is designated as the backing store
  # vertex 0 is always designated as the root


  def __post_init__(self):
    if not self.QFetch:
      self.QFetch = {v: [] for v in self.G[0]}
    if not self.QResolve:
      self.QResolve = {v: [] for v in self.G[0]}

  def getItems(self): # get all items stored in the network
    return {i for cache in self.M.values() for (i, _) in cache.C}


  def computeZ(self, src, dst = "b"):
    numCaches = len(self.pathTo(src, dst)) - 1
    return numCaches * self.Z_A # Z_C

  def resolve(self, item, v):
    matching = [req for req in self.QResolve[v] if req.i == item]
    self.QResolve[v] = [req for req in self.QResolve[v] if req.i != item]
    for req in matching:
      self.dhLatencies.append(self.clk.t.time - req.t.time)
    return self.QResolve, len(matching)

  def buildMap(self, t, k):  # t = time init at 0, k = max size of cache
    assert len(self.G[0]) > 0
    # Vertices
    V = self.G[0]
    # Now build the map
    for vi in V:
      # Initialise each cache into the first CacheState
      self.M[vi] = CacheState(t, frozenset(), k)
    return self.M

  def prefill(self, k_T: int):
    # Populate each cache, in vertex order, with a size-k block of the
    # first k_T items (cache index idx gets items [idx*k+1 .. idx*k+k]),
    # all admitted at the same initial ttl — matching the report's
    # worked (2,2) example, where every prefilled entry starts at the
    # same TTL (e.g. v0={(a,6),(b,6)}, v1={(c,6),(d,6)}). Ties among
    # equal-TTL entries are broken deterministically by ascending item
    # index (see policies.TTL), not left to frozenset iteration order.
    for idx, v in enumerate(self.G[0]):
      cache = self.M[v]
      size = cache.size
      lo = idx * size + 1
      entries = frozenset((I(item=it), self.ttl) for it in range(lo, lo + size))
      self.M[v] = CacheState(t=cache.t, C=entries, size=size)

  def nextHop(self, vCurr):
    # Follow the directed edge (child, parent) from vCurr.
    # In a tree, each node has exactly one parent.
    # The root has no parent, so next hop is the backing store.
    E = self.G[1]
    parents = [v for u, v in E if u == vCurr]
    if not parents:
      return "b"
    return parents[0]

  def children(self, vCurr):
    # Return all children of vCurr.
    # A child is any node u where (u, vCurr) is an edge.
    E = self.G[1]
    return [u for u, v in E if v == vCurr]

  def pathTo(self, src, dst="b"):
    # Return the full path from src to dst by following nextHop.
    p = [src]
    v = src
    while v != dst:
      vNext = self.nextHop(v)
      if vNext is None:
        break
      p.append(vNext)
      v = vNext
    return p

  ########## FORWARD PATH ##########
  # Request propagation: leaf -> ... -> root -> backing store
  # On a miss at node v, propagate upstream (toward backing store).
  # If a fetch is already in flight for this item at v, it's a delayed hit — don't propagate.

  def forward(self, req: Request, v):

    if v == "b":
      # Reached the backing store — send fetch
      self.B.recvFetch(req)
      return req, "b", None

    cache = self.M[v]

    # Check for hit
    if cache.get(req.i) is not None:
      # Hit — update recency, stop propagating
      old = cache.get(req.i)
      self.M[v] = cache.replace(rmv=old, add=(req.i, self.clk.t.time))
      return req, 2, None

    # Check if fetch already in flight at this node
    if req.i in self.QFetch[v]:
      # Delayed hit — don't send duplicate fetch
      self.QResolve[v].append(req)
      return req, 1, None

    # Miss — record and propagate upstream
    self.QFetch[v].append(req.i)
    return req, 0, self.nextHop(v)

  def cpp(self, item: I, leaf, policyName: str = "TTL", cpp: str = "lce"):
    if cpp == "opt": self.opt(item, leaf, policyName)
    elif cpp == "lce": self.lce(item, leaf, policyName)
    
# CPPs
  def opt(self, item: I, leaf, policyName: str = "TTL"):
    path = [n for n in self.pathTo(leaf, "b") if n != "b"]

    for node in path:
      if item in self.QFetch[node]:
        self.QFetch[node].remove(item)
        _, dhs = self.resolve(item, node)
        self.dhCount += dhs


  def lce(self, item: I, leaf, policyName: str = "TTL"):
    path = [n for n in self.pathTo(leaf, "b") if n != "b"]

    for node in path:
      # DH accounting: clear the in-flight fetch marker for this item at
      # this node (if any) and resolve any delayed hits registered against it.
      if item in self.QFetch[node]:
        self.QFetch[node].remove(item)
        _, dhs = self.resolve(item, node)
        self.dhCount += dhs

      # admit an item at this node
      cache = self.M[node]
      old = TTL(cache) # TTL(cache) returns the (item, TTL) tuple
      self.M[node] = cache.replace(rmv=old, add=(item, self.clk.t.time + self.ttl))
