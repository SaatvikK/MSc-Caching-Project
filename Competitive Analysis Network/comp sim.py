# sim.py
from dataclasses import dataclass
from typing import Tuple, FrozenSet, TypeVar
from clock import V, I, T, Clock
from sequence import Sequence as Seq
from sequence import Request as Req
from backingstore import BackingStore as BStore
from cache import CacheState 
from policies import *
from network import CacheNetwork as CN
import csv


########## DEFINE SIM PARAMETERS ##########
MAX_TIME = 100000 # t_max >= N + 2Z_B + 2
NUM_REQUESTS = 20 # N
NUM_ITEMS = 6 # n
R = 1 # R
k = 2 # k
V = [0, 1] # vertices
E = [(0, 1)] # edges
leaf = 0
policyName = "TTL"
Z_A = 2 # delay parameter per hop
Z_B = len(V)*Z_A # delay parameter from root to backing store
k_T = len(V)*k
TTL = 6 # TTL granted to an item on admission/renewal
W = 3 # the first 3 items of I
###########################################
t = T(time = 0)
tmax = T(time = MAX_TIME)

clk = Clock(t, tmax)

def createSequence():
  """
  N : total number of requests
  n : number of distinct items (universe size)
  R : constant inter-request arrival time (in timesteps)
  """

  seq = Seq((), tmax = tmax, t = t)
  stop = False
  # First Z_B-1 pure requests
  # network is initialised with the first k_T items.
  # So we request any item > k_T
  item = k_T + 1
  tt = 0
  while not stop:
    rt = T(time = 1 + tt)
    seq = seq.add(item, rt)
    if tt == Z_B - 1: stop = True; break
    tt += 1

  # Then one pure request for an item in the |V|-1th cache.
  # By this point no items have been admitted.
  # So the cache is still in its initial state in terms of which items
  # are stored. Meaning, we just request the k_Tth item.
  rt = T(time = 1 + tt + 1)
  seq = seq.add(k_T, rt)

  # Then, we make |W|-1 bursty requests, each being for whichever
  # Item is in the network but not in W.
  # However, this cannot be pre-generated easily, so it will be
  # co-generated during simulation.

  return seq

def burstyRequestBuilder(item: I, seq: Seq, ct: T):
  # Nones:
  for i in range(Z_B):
    ct = T(time=ct.time + 1)
  
  # Item:
  for i in range(Z_B):
    ct = T(time=ct.time + 1)
    seq = seq.add(item, ct)
  
  # Nones:
  for i in range(Z_B):
    ct = T(time=ct.time + 1)
  
  return seq, ct

seq = createSequence()

print("SEQUENCE:")
for idx, req in enumerate(seq.S):
  print(f"  r_{idx+1}: item {req.i.item} at t={req.t.time}")
print()

#### COUNTERS
dHits = 0
hits = 0
misses = 0

V = [0, 1]
E = [(0, 1)]
leaf = 0
policyName = "TTL"

B = BStore(I, t, Z_B)

net = CN(
  (V, E), {}, T(time=0), T(time=MAX_TIME),
  clk=clk, Z_A=Z_A, B=B, dhCount=0,
  QFetch={}, QResolve={}, ttl=TTL
)
net.buildMap(t, k)

# Total Z from leaf to backing store
Z_B = net.computeZ(leaf)
print("NETWORK:")
print(f"  Topology: {V}")
print(f"  Edges: {E}")
print(f"  Path from leaf {leaf} to backing store: {net.pathTo(leaf)}")
print(f"  Z_A={Z_A}, Z_B={Z_B}")
print()

print("=" * 60)
print(f"  SIMULATION CONFIG")
print(f"  N={NUM_REQUESTS}, |I|={NUM_ITEMS}, R={R}")
print(f"  Z_A={Z_A}, Z_B={Z_B}, k={k}")
print(f"  tmax={tmax.time}")
print(f"  policy={policyName}")
print("=" * 60)

trace = []

Qreq = []      # forward path: [req, current_v, origin_leaf, t_arrived]

# --- Adversarial burst scheduling state ---
Witems = list(range(W))       # candidate item pool: {0, ..., W-1}
usedItems = set()             # members of W already bursted — never repeat one
burstsDone = 0
maxBursts = W                 # step 3 + |W|-1 repeats = |W| total bursts
burstCursor = T(time=seq.S[-1].t.time)  # next free tick, right after createSequence()'s last request

while clk.t.time < tmax.time:
  # Decide the next bursty phase now, before the clock advances, so it's
  # based on the network state as of the end of the previous tick's
  # rearrangement (i.e. after any LCE admission that just happened).
  if burstsDone < maxBursts and clk.t.time >= burstCursor.time:
    present = {i.item for v in V for (i, _) in net.M[v].C}
    candidates = [w for w in Witems if w not in present and w not in usedItems]
    assert candidates, f"no unused item in W={Witems} absent from network at t={clk.t.time}; adversarial construction assumption violated"
    item = candidates[0]
    usedItems.add(item)
    seq, burstCursor = burstyRequestBuilder(item, seq, burstCursor)
    burstsDone += 1
    print(f"  [burst {burstsDone}/{maxBursts}] scheduled item {item}, next cursor t={burstCursor.time}")

  clk.step()
  print(f"\n--- t = {clk.t.time} ---")

  # 1. Input new request from sequence
  req = seq.sendReq()
  if req is not None:
    Qreq.append([req, leaf, leaf, clk.t.time])
    print(f"  NEW REQUEST: item {req.i.item}")
    trace.append([clk.t.time, "NEW_REQ", req.i.item, f"leaf={leaf}"])

  # 2. Advance in-flight requests through the network
  to_remove = []
  for i in range(len(Qreq)):
    reqT = Qreq[i]
    # Check if Z_A time has elapsed since arriving at current node
    if reqT[1] != reqT[2] and clk.t.time - reqT[3] < Z_A:
      continue

    _, stat, vNext = net.forward(reqT[0], reqT[1])

    if stat == 2:  # hit at current node
      hits += 1
      print(f"  HIT: item {reqT[0].i.item} at node {reqT[1]}")
      trace.append([clk.t.time, "HIT", reqT[0].i.item, f"node={reqT[1]}"])
      #net.returnPath(reqT[0].i, reqT[2], policyName)
      to_remove.append(i)

    elif stat == 1:  # delayed hit — fetch already in flight at this node
      print(f"  DELAYED HIT: item {reqT[0].i.item} at node {reqT[1]}")
      trace.append([clk.t.time, "DELAYED_HIT", reqT[0].i.item, f"node={reqT[1]}"])
      to_remove.append(i)

    elif stat == "b":  # reached backing store
      misses += 1
      print(f"  MISS (all caches): item {reqT[0].i.item} -> backing store")
      trace.append([clk.t.time, "MISS_TO_BS", reqT[0].i.item, ""])

      # Fetch resolves now: Z_B ticks have already elapsed via the
      # per-hop Z_A stepping above, so admission/DH-resolution happen
      # on this same tick rather than via an extra artificial delay.
      net.cpp(reqT[0].i, reqT[2], policyName)
      print(f"  FETCH RETURN: item {reqT[0].i.item} (resolved at t={clk.t.time})")
      trace.append([clk.t.time, "FETCH_RETURN", reqT[0].i.item, f"resolved_at={clk.t.time}"])

      if net.dhCount > dHits:
        resolved = net.dhCount - dHits
        print(f"  RESOLVED: {resolved} delayed hit(s) for item {reqT[0].i.item}")
        trace.append([clk.t.time, "DH_RESOLVE", reqT[0].i.item, f"count={resolved}"])
        dHits = net.dhCount

      to_remove.append(i)

    elif stat == 0:  # miss at current node, advance to next hop
      print(f"  MISS: item {reqT[0].i.item} at node {reqT[1]} -> forwarding to {vNext}")
      trace.append([clk.t.time, "MISS", reqT[0].i.item, f"node={reqT[1]},next={vNext}"])
      Qreq[i][1] = vNext
      Qreq[i][3] = clk.t.time

  for i in reversed(to_remove):
    Qreq.pop(i)

  # 3. Print state
  for v in V:
    cache = net.M[v]
    items = [f"{i.item}" for (i, _) in cache.C]
    print(f"  Cache[{v}]: {{{', '.join(items) if items else 'empty'}}}")
  inflight_fwd = [f"{r[0].i.item}@{r[1]}" for r in Qreq]
  print(f"  Qreq(fwd): [{', '.join(inflight_fwd)}]")

  # Early termination — only once nothing is in flight, nothing already
  # queued in seq remains undelivered, and no future burst will add more.
  if req is None and not Qreq and seq.nextReq >= len(seq.S) and burstsDone >= maxBursts:
    print("\n  (no more activity — terminating early)")
    break

dHits = net.dhCount

print("\n" + "=" * 60)
print(f"  RESULTS")
print(f"  Hits:         {hits}")
print(f"  Misses:       {misses}")
print(f"  Delayed Hits: {dHits}")
print(f"  Total:        {hits + misses + dHits}")
if (hits + misses + dHits) > 0:
  total = hits + misses + dHits
  print(f"  Hit Rate:     {hits/total:.2%}")
  print(f"  Miss Rate:    {misses/total:.2%}")
  print(f"  DH Rate:      {dHits/total:.2%}")
print("=" * 60)


############## SAVE TO CSV
with open("trace.csv", "w", newline="") as f:
  writer = csv.writer(f)
  writer.writerow(["tick", "event", "item", "detail"])
  for row in trace:
    writer.writerow(row)

with open("metrics.csv", "w", newline="") as f:
  writer = csv.writer(f)
  writer.writerow(["metric", "value"])
  writer.writerow(["N", NUM_REQUESTS])
  writer.writerow(["n", NUM_ITEMS])
  writer.writerow(["R", R])
  writer.writerow(["Z_A", Z_A])
  writer.writerow(["Z_B", Z_B])
  writer.writerow(["k", k])
  writer.writerow(["tmax", tmax.time])
  writer.writerow(["policy", policyName])
  writer.writerow(["hits", hits])
  writer.writerow(["misses", misses])
  writer.writerow(["delayed_hits", dHits])
  writer.writerow(["total_requests", hits + misses + dHits])
  if (hits + misses + dHits) > 0:
    total = hits + misses + dHits
    writer.writerow(["hit_rate", f"{hits/total:.4f}"])
    writer.writerow(["miss_rate", f"{misses/total:.4f}"])
    writer.writerow(["dh_rate", f"{dHits/total:.4f}"])

print("\nCSV files written: trace.csv, metrics.csv")