# network.py
from dataclasses import dataclass, field
from typing import Tuple, List, Optional
from framework.clock import V, I, T, Clock
from framework.cache import CacheState
from framework.sequence import Request, Sequence
from framework.backingstore import BackingStore
from framework.policies import *
import numpy as np
import platform as plat
import random as rand

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
  arranged: bool = False  # has OPT already spent its single rearrangement? 
  # Each cache node is given a label that represents the vertex (eg v_1, v_2, etc.)
  # The mapping dict, M, maps each vertex to a CacheState object.
  # Then, in G, we only use the vertex labels.
  # In this way, we can avoid having to 'refresh' specific vertices in G whenever the CacheStates are updated
  # (because an update results in a new CacheState being outputed, they aren't updated in-place).

  # vertex 'b' is designated as the backing store
  # vertex 0 is always designated as the root


  # after initialisation, make sure that QFetch has a key-value per vertex in the network representing what fetch requests originated from
  # what cache. 
  # Same for resolve (the waiting queue).
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

  # after a fetch request resolve any delayed hits
  def resolve(self, item, v):
    matching = [req for req in self.QResolve[v] if req.i == item]
    self.QResolve[v] = [req for req in self.QResolve[v] if req.i != item]
    for req in matching:
      self.dhLatencies.append(self.clk.t.time - req.t.time)
    return self.QResolve, len(matching)

  # building the map that maps each vertex to a unique cache object.
  def buildMap(self, t, k):  # t = time init at 0, k = max size of cache
    assert len(self.G[0]) > 0
    # Vertices
    V = self.G[0]
    # Now build the map
    for vi in V:
      # Initialise each cache into the first CacheState
      self.M[vi] = CacheState(t, frozenset(), k)
    return self.M


  # Populate the cache, in vertex order, with k-sized blocks.
  # This results in the first k_T items in the universe being in the cache.
  # That is: [idx*k+1 .. idx*k+k]
  def prefill(self, k_T: int):
    for idx, v in enumerate(self.G[0]):
      cache = self.M[v]
      size = cache.size
      lo = idx * size + 1
      entries = frozenset((I(item=it), self.clk.t.time) for it in range(lo, lo + size))
      self.M[v] = CacheState(t=cache.t, C=entries, size=size)

  # Dynamically find the next cache to forward the request to. If there's more than one option, just go
  # for the first one in the list.
  def nextHop(self, vCurr):
    E = self.G[1]
    parents = [v for u, v in E if u == vCurr]
    # If no parents, then we're at root so just send to backing store.
    if not parents:
      return "b"
    return parents[0]

  # Return all children of vCurr.
  # A child is any node u where (u, vCurr) is an edge.
  def children(self, vCurr):
    E = self.G[1]
    return [u for u, v in E if v == vCurr]

  # Return the full path from src to dst by following nextHop.
  def pathTo(self, src, dst="b"):
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

  # Tracks a request.
  def forward(self, req: Request, v):

    # If req is at v==b (backing store)...
    if v == "b":
      # Reached the backing store — send fetch
      self.B.recvFetch(req)
      return req, "b", None

    # else, get the cache that v represents.
    cache = self.M[v]

    # Check for hit
    if cache.get(req.i) is not None:
      # Hit. update recency, stop propagating
      old = cache.get(req.i)
      self.M[v] = cache.replace(rmv=old, add=(req.i, self.clk.t.time))
      return req, 2, None

    # Check if fetch already in flight at this node
    if req.i in self.QFetch[v]:
      # Delayed hit. don't send duplicate fetch
      self.QResolve[v].append(req)
      return req, 1, None

    # Miss. record and propagate upstream
    self.QFetch[v].append(req.i)
    return req, 0, self.nextHop(v)

  # CHOOSE A CRPP BASED ON THE CPP SUPPLIED AT THE BEGINNING OF THE SIMULATION
  def cpp(self, item: I, leaf, policyName: str = "TTL", cpp: str = "lce", seq: Sequence = None):
    """`seq` is only consulted by mwOPT and nOPT, which need the *finalised*
    request sequence to work out which item is never requested again (mwOPT)
    and which item the whole sequence is built around (nOPT)."""
    if cpp == "lce": self.lce(item, leaf, policyName)
    elif cpp == "aOPT": self.aOPT(item, leaf, policyName)
    elif cpp == "mwOPT":
      assert seq is not None, "mwOPT needs the finalised sequence to locate j"
      self.mwOPT(item, seq, leaf, policyName)
    elif cpp == "nOPT":
      assert seq is not None, "nOPT needs the finalised sequence to locate g"
      self.nOPT(item, seq, leaf, policyName)
    else: raise ValueError(f"unknown CPP '{cpp}' (have: lce, aOPT, mwOPT, nOPT)")


# CPPs ---------------------------------------------------------------------------------------------
  # rho_A's OPT instance
  # Never rearranges the network.
  def aOPT(self, item: I, leaf, policyName: str = "TTL"):
    path = [n for n in self.pathTo(leaf, "b") if n != "b"]

    for node in path:
      # DH accounting: clear the in-flight fetch marker for this item at
      # this node (if any) and resolve any delayed hits registered against it.
      if item in self.QFetch[node]:
        self.QFetch[node].remove(item)
        _, dhs = self.resolve(item, node)
        self.dhCount += dhs

  # The LCE CPP.
  # Leave a copy of the item at every node in the request's path.
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
      self.M[node] = cache.replace(rmv=old, add=(item, self.clk.t.time))

  # rho_MW's OPT instance.
  # This evicts a single unmarked item `j` at the return of the first fetch request.
  # OPT never rearranges again as every other item other than j gets requested at least once.
  def mwOPT(self, item: I, seq: Sequence, leaf, policyName: str = "TTL"):
    path = [n for n in self.pathTo(leaf, "b") if n != "b"]

    for node in path:
      # DH accounting: clear the in-flight fetch marker for this item at
      # this node (if any) and resolve any delayed hits registered against it.
      if item in self.QFetch[node]:
        self.QFetch[node].remove(item)
        _, dhs = self.resolve(item, node)
        self.dhCount += dhs

    if self.arranged:
      return
    self.arranged = True

    # Make the marked set M. We do [1:] because S[0] is the initial pure request which
    # isn't counted towards marking.
    M = {r.i for r in seq.S[1:]}

    # j is the unmarked item: it is never requested again, so its slot is the
    # one O can afford to give up. If the fetched item is itself unmarked then
    # j = item and O declines placement outright (Sec 5.1) — this is the MW
    # case where OPT simply does not cache k_T+1.

    # `j` is the one unmarked item. Check if it's the one that was pure-requested. If so just return without doing anythig.
    # It will implicitly be rejected.
    # Else, continue.
    if item not in M:
      return

    # We now know that `j` is in the network somewhere, so simply iterate through until we find it.
    # Intuitively, we aim to find the shallowest `j` in the network.
    vj, j = None, None
    for node in path:
      unmarked = sorted((i for (i, _) in self.M[node].C if i not in M),
                        key=lambda i: i.item)
      if unmarked:
        vj, j = node, unmarked[0]
        break

    # Make sure `j` actually exists -- if it's None that means the simulation has broken as 
    # MW proved that j does indeed exist.
    assert j is not None, (
      f"every resident item is marked at t={self.clk.t.time}; rho_MW should "
      f"always leave at least one unmarked item in {{1,...,k_T+1}}"
    )

    # Then, because OPT has no control over what item is evicted, it has to keep evicting items
    # until the evicted item is j.
    # The initial eviction is done in order to admit the fetched item `item`.
    cache = self.M[vj]
    victim = TTL(cache)  # None iff this cache has a free slot, so nothing need be evicted
    rotations = 0
    while victim is not None and victim[0] != j and rotations < cache.size:
      cache = cache.replace(rmv=victim, add=(victim[0], self.clk.t.time))
      victim = TTL(cache)
      rotations += 1

    assert victim is None or victim[0] == j, (
      f"TTL never surfaced j={j} at v{vj} after {rotations} rotations"
    )
    self.M[vj] = cache.replace(rmv=victim, add=(item, self.clk.t.time))


  # Place `g` at the shallowest cache, incurring zero latency for all \mu requests.
  # Incur the same amount of latency for \phi as LCE, if not less.
  # The rearrangement happens at the first opportunity.
  def nOPT(self, item: I, seq: Sequence, leaf, policyName: str = "TTL"):
    path = [n for n in self.pathTo(leaf, "b") if n != "b"]

    for node in path:
      # DH accounting: clear the in-flight fetch marker for this item at
      # this node (if any) and resolve any delayed hits registered against it.
      if item in self.QFetch[node]:
        self.QFetch[node].remove(item)
        _, dhs = self.resolve(item, node)
        self.dhCount += dhs

    # Only g earns the single rearrangement; every other fetch — phi's bait
    # items, which full-miss here because O's caches never move — is
    # DH-accounted only.
    g = seq.S[0].i
    if self.arranged or item != g:
      return
    self.arranged = True

    v0 = path[0]
    cache = self.M[v0]
    self.M[v0] = cache.replace(rmv=TTL(cache), add=(g, self.clk.t.time))


    
