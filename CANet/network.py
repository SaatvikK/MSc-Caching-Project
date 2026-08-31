# network.py
from dataclasses import dataclass, field
from typing import Tuple, List, Optional
from clock import V, I, T, Clock
from cache import CacheState
from sequence import Request, Sequence
from backingstore import BackingStore
from policies import *
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
  arranged: bool = False  # has OPT already spent its single rearrangement? (report Lemma 5.2)
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
    # every entry stamped with the current clock reading — matching the
    # report's worked (2,2) example, where every prefilled entry starts
    # on the same footing (e.g. v0={(a,0),(b,0)}, v1={(c,0),(d,0)}), so
    # the whole prefilled block is uniformly the oldest thing resident.
    # Ties among equal-stamp entries are broken deterministically by
    # ascending item index (see policies.TTL), not left to frozenset
    # iteration order.
    for idx, v in enumerate(self.G[0]):
      cache = self.M[v]
      size = cache.size
      lo = idx * size + 1
      entries = frozenset((I(item=it), self.clk.t.time) for it in range(lo, lo + size))
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


# CPPs
  def aOPT(self, item: I, leaf, policyName: str = "TTL"):
    path = [n for n in self.pathTo(leaf, "b") if n != "b"]

    for node in path:
      # DH accounting: clear the in-flight fetch marker for this item at
      # this node (if any) and resolve any delayed hits registered against it.
      if item in self.QFetch[node]:
        self.QFetch[node].remove(item)
        _, dhs = self.resolve(item, node)
        self.dhCount += dhs

    # rho_A's OPT does not rearrange.


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

  def mwOPT(self, item: I, seq: Sequence, leaf, policyName: str = "TTL"):
    """OPT for rho_MW (report Lemmas 5.2 and 5.3).

    Manohar & Williams' OPT evicts the single unmarked item j at the return of
    the opening pure request, and never touches the cache again. Here O is a
    *placement* policy (report Sec 5.1): it cannot name an eviction victim,
    because that is TTL's decision. So it cannot evict j directly — it has to
    *induce* the eviction by repeatedly placing items into the cache holding j
    until TTL itself picks j. Each such placement re-admits the item TTL has
    just evicted (Sec 5.1 explicitly grants O the right to place "any item
    evicted by any cache"), which refreshes that item's TTL and rotates it to
    the back of the eviction order. j is the only entry never refreshed, so it
    becomes the TTL minimum within at most k - 1 rotations, at which point O
    admits the fetched item into the slot j vacates.

    O gets exactly one such rearrangement; every later fetch is DH-accounted
    only, per Lemma 5.2 ("never rearranges again")."""
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

    # The marked set M. seq.S[0] is the opening pure request (see
    # sequenceBuild.simulateManoharWilliams); everything after it is bursty,
    # and only bursty requests mark — exactly as in Manohar & Williams, where
    # the pure request for k_T+1 does not mark it.
    M = {r.i for r in seq.S[1:]}

    # j is the unmarked item: it is never requested again, so its slot is the
    # one O can afford to give up. If the fetched item is itself unmarked then
    # j = item and O declines placement outright (Sec 5.1) — this is the MW
    # case where OPT simply does not cache k_T+1.
    if item not in M:
      return

    # Otherwise j is resident. Prefer the shallowest candidate: swapping the
    # fetched item into a cache nearer the leaf makes its later hits cheaper
    # (a hit at depth d costs d * Z_A, Definition 4.8), and swapping in place
    # leaves k items at every depth, which is what Lemma 5.3's latency
    # accounting assumes.
    vj, j = None, None
    for node in path:
      unmarked = sorted((i for (i, _) in self.M[node].C if i not in M),
                        key=lambda i: i.item)
      if unmarked:
        vj, j = node, unmarked[0]
        break

    assert j is not None, (
      f"every resident item is marked at t={self.clk.t.time}; rho_MW should "
      f"always leave at least one unmarked item in {{1,...,k_T+1}}"
    )

    # Induce the eviction of j, then take the slot it vacates.
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

  def nOPT(self, item: I, seq: Sequence, leaf, policyName: str = "TTL"):
    """OPT for rho_n (report Theorem 5.5.1).

    O's whole strategy is one move: at the return of the opening pure request
    it places g — seq.S[0], the item phi spends the rest of the sequence
    pushing to the back of LCE's network — into the leaf cache, and never
    rearranges again. Every mu request is then a depth-0 hit costing nothing,
    while LCE pays d * Z_A for each, so L(O, rho_n) stays constant in N_mu.

    Simpler than mwOPT in two ways: there is no marked set, since nothing but
    g is requested after phi, and no rotation is needed to name a victim,
    since whichever entry TTL surfaces at v0 is expendable."""
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


    

