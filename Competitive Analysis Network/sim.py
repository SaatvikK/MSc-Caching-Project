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
MAX_TIME = 45 # t_max >= N + 2Z_B + 2
NUM_REQUESTS = 20 # N
NUM_ITEMS = 4 # n
R = 1 # R
CACHE_MAX_SIZE = 3 # k
V = [0, 1] # vertices
E = [(0, 1)] # edges
leaf = 0
policyName = "TTL"
Z_A = 5 # delay parameter per hop
Z_B = 10 # delay parameter from root to backing store
TTL = 15 # TTL granted to an item on admission/renewal
###########################################
t = T(time = 0)
tmax = T(time = MAX_TIME)

clk = Clock(t, tmax)

def createSequence(N: int, n: int, R: int = 1):
  """
  N : total number of requests
  n : number of distinct items (universe size)
  R : constant inter-request arrival time (in timesteps)
  """
  seq = Seq((), tmax=tmax, t=t)
  for j in range(N):
    rt = T(time=1 + j * R)
    seq = seq.add(j % n, rt)
  return seq, R

seq, _ = createSequence(N = NUM_REQUESTS, n = NUM_ITEMS, R = R)

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
net.buildMap(t, CACHE_MAX_SIZE)

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
print(f"  Z_A={Z_A}, Z_B={Z_B}, k={CACHE_MAX_SIZE}")
print(f"  tmax={tmax.time}")
print(f"  policy={policyName}")
print("=" * 60)

trace = []

Qreq = []      # forward path: [req, current_v, origin_leaf, t_arrived]
QReturn = []   # backing store returns: [req, origin_leaf, t_sent_to_bs]

while clk.t.time < tmax.time:
  clk.step()
  print(f"\n--- t = {clk.t.time} ---")

  # 1. Check for backing store returns
  for ret in list(QReturn):
    req, origin_leaf, t_sent = ret
    QReturn.remove(ret)
    print(f"  FETCH RETURN: item {req.i.item} (sent to BS at t={t_sent})")
    trace.append([clk.t.time, "FETCH_RETURN", req.i.item, f"sent_at={t_sent}"])

    # Return path: admit content, demote victims, resolve DHs
    #net.returnPath(req.i, origin_leaf, policyName)

    if net.dhCount > dHits:
      resolved = net.dhCount - dHits
      print(f"  RESOLVED: {resolved} delayed hit(s) for item {req.i.item}")
      trace.append([clk.t.time, "DH_RESOLVE", req.i.item, f"count={resolved}"])
      dHits = net.dhCount

  # 2. Input new request from sequence
  req = seq.sendReq()
  if req is not None:
    Qreq.append([req, leaf, leaf, clk.t.time])
    print(f"  NEW REQUEST: item {req.i.item}")
    trace.append([clk.t.time, "NEW_REQ", req.i.item, f"leaf={leaf}"])

  # 3. Advance in-flight requests through the network
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
      QReturn.append([reqT[0], reqT[2], clk.t.time])
      net.lce(reqT[0].i, reqT[2], policyName)
      to_remove.append(i)

    elif stat == 0:  # miss at current node, advance to next hop
      print(f"  MISS: item {reqT[0].i.item} at node {reqT[1]} -> forwarding to {vNext}")
      trace.append([clk.t.time, "MISS", reqT[0].i.item, f"node={reqT[1]},next={vNext}"])
      Qreq[i][1] = vNext
      Qreq[i][3] = clk.t.time

  for i in reversed(to_remove):
    Qreq.pop(i)

  # 4. Print state
  for v in V:
    cache = net.M[v]
    items = [f"{i.item}" for (i, _) in cache.C]
    print(f"  Cache[{v}]: {{{', '.join(items) if items else 'empty'}}}")
  inflight_fwd = [f"{r[0].i.item}@{r[1]}" for r in Qreq]
  inflight_ret = [f"{r[0].i.item}" for r in QReturn]
  print(f"  Qreq(fwd): [{', '.join(inflight_fwd)}]")
  print(f"  QReturn(bs): [{', '.join(inflight_ret)}]")

  # Early termination
  if req is None and not Qreq and not QReturn:
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
  writer.writerow(["k", CACHE_MAX_SIZE])
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