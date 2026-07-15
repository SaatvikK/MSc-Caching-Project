# network.py
from dataclasses import dataclass
from typing import Tuple, List, Optional
from clock import V, I, T, Clock
from cache import CacheState
from sequence import Request
from backingstore import BackingStore
from policies import *
import numpy as np

@dataclass
class CacheNetwork:
  G: Tuple[list, list]  # the topology, G = (V, E) where E is a list of (child, parent) directed edges
  M: dict               # mapping: vertex label -> CacheState
  t: T
  tmax: T
  clk: Clock
  Z_A: int
  B: BackingStore
  dhCount: int
  QFetch: dict          # tracks in-flight fetches per node: vertex -> list of items being fetched
  QResolve: dict
  ttl: T
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
    
    clk = Clock(t = self.t, tmax = self.tmax)

  def getItems(self): # get all items stored in the network
    return {i for cache in self.M.values() for (i, _) in cache.C}


  def computeZ(self, src, dst = "b"):
    numCaches = len(self.pathTo(src, dst)) - 1
    return numCaches * self.Z_A # Z_C

  def resolve(self, item, v):
    dh = sum(1 for req in self.QResolve[v] if req.i == item)
    self.QResolve[v] = [req for req in self.QResolve[v] if req.i != item]
    return self.QResolve, dh

  def buildMap(self, t, k):  # t = time init at 0, k = max size of cache
    assert len(self.G[0]) > 0
    # Vertices
    V = self.G[0]
    # Now build the map
    for vi in V:
      # Initialise each cache into the first CacheState
      self.M[vi] = CacheState(t, frozenset(), k)
    return self.M

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
      self.M[v] = cache.replace(rmv=old, add=(req.i, self.t.time))
      return req, 2, None

    # Check if fetch already in flight at this node
    if req.i in self.QFetch[v]:
      # Delayed hit — don't send duplicate fetch
      self.QResolve[v].append(req)
      return req, 1, None

    # Miss — record and propagate upstream
    self.QFetch[v].append(req.i)
    return req, 0, self.nextHop(v)

  # ########## RETURN PATH ##########
  # # Content flows back downstream: backing store -> ... -> leaf
  # # On return, each node admits the item and may evict a victim.
  # # The return path follows the forward path in reverse.

  # def returnPath(self, item: I, leaf, policyName: str = "LRU", bflag = False):
  #   """
  #   Leave-Copy-at-Leaf (LCL) return semantics.

  #   On return of `item` to the origin `leaf`:
  #     1. Sweep the forward path pi(leaf, b) and, at every node that was
  #        carrying an in-flight fetch marker for `item`, clear QFetch and
  #        resolve any registered delayed hits (QResolve). This is the
  #        DH-accounting pass; it is orthogonal to admission.
  #     2. Admit `item` ONLY at the origin leaf. No intermediate caches
  #        receive a copy — this is the key departure from LCE.
  #     3. If the leaf admission evicts a victim x, forward x one hop
  #        upstream via `demote`, which itself may trigger a further
  #        eviction, yielding a cascade. The cascade terminates at the
  #        root r: next(r) = b, so the root's evicted victim is simply
  #        discarded (i.e. the chain has length <= depth(leaf, root)).
  #   """
  #   fwd = self.pathTo(leaf, "b")
  #   ret = [v for v in reversed(fwd) if v != "b"]

  #   # (1) DH accounting: clear in-flight markers & resolve delayed hits
  #   # at every node on the forward path. This must sweep all nodes, not
  #   # just the leaf, since delayed hits may have been registered at
  #   # intermediate nodes while the fetch was in transit.
  #   for v in ret:
  #     if item in self.QFetch[v]:
  #       self.QFetch[v].remove(item)
  #       _, dhs = self.resolve(item, v)
  #       self.dhCount += dhs

  #   # (2) Admit only at the origin leaf only if the item was sent from the backing store
  #   if bflag == True:
  #     leafCache = self.M[leaf]

  #   # Idempotency edge case: if the leaf already holds the item (e.g. a
  #   # hit-at-leaf invocation routed through returnPath), just refresh
  #   # recency and stop — no eviction, no cascade.
  #   if leafCache.get(item) is not None:
  #     old = leafCache.get(item)
  #     self.M[leaf] = leafCache.replace(rmv=old, add=(item, self.t.time))
  #     return

  #   victim = policy(policyName, leafCache)
  #   self.M[leaf] = leafCache.replace(rmv=victim, add=(item, self.t.time))

  #   # (3) Cascade the leaf's eviction upstream. The recursion in
  #   # `demote` carries the chain through intermediate caches until it
  #   # either (a) finds a non-full cache (victim = None, terminating),
  #   # (b) finds the demoted item already present (recency refresh,
  #   # terminating), or (c) reaches the root, whose upstream is the
  #   # backing store and whose final victim is dropped.
  #   if victim is not None:
  #     vUp = self.nextHop(leaf)
  #     if vUp is not None and vUp != "b":
  #       self.demote(victim[0], vUp, policyName)



##################################
  def cpp(self, item: I, leaf, policyName: str = "TTL", cpp: str = "lce"):
    match(cpp):
      case "opt": self.opt(item, leaf, policyName)
      case "lce": self.lce(item, leaf, policyName)
    
# CPPs
  def opt(self, item: I, leaf, policyName: str = "TTL"):
    # OPT does not need to re-arrange for the advesarial sequence.
    pass


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
      self.M[node] = cache.replace(rmv=old, add=(item, self.t.time + self.ttl))
     
  def demote(self, item: I, v, policyName: str = "LRU"):
    # Push an evicted item one hop upstream (toward backing store).
    if v == "b":
      return

    cache = self.M[v]

    # If item already in cache at this node, just update recency
    if cache.get(item) is not None:
      old = cache.get(item)
      self.M[v] = cache.replace(rmv=old, add=(item, self.t.time))
      return

    # Admit the demoted item, possibly evicting another victim
    victim = policy(policyName, cache)
    self.M[v] = cache.replace(rmv=victim, add=(item, self.t.time))

    # Cascade: if this eviction also produces a victim, demote it further upstream
    if victim is not None:
      vUp = self.nextHop(v)
      if vUp is not None and vUp != "b":
        self.demote(victim[0], vUp, policyName)