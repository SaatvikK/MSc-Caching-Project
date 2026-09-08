from dataclasses import dataclass
from typing import Tuple, FrozenSet, TypeVar
from LEGACY.dh.onestate.clock import V, I, T, Clock
from LEGACY.dh.onestate.sequence import Sequence as Seq
from LEGACY.dh.onestate.sequence import Request as Req
from LEGACY.dh.onestate.backingstore import BackingStore as BStore
from LEGACY.dh.onestate.cache import CacheState 
from LEGACY.dh.onestate.policies import policy
import csv


########## DEFINE SIM PARAMETERS ##########
MAX_TIME = 50 # t_max
NUM_REQUESTS = 20 # N
NUM_ITEMS = 5 # n
R = 1 # R
CACHE_MAX_SIZE = 3 # k
FETCH_TIME = 5 # F
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


# fetch time
# Literature states that F > 1 results in an environment where delayed hits becomes *physically possible*.
# However, for this simulation, we'd like to be able to deterministically guarantee whether or not delayed hits occur.
# Thus, in order to create a DH environment we must set F such that F > nR.
F = FETCH_TIME # F = 1 with n = 4 and R = 1 means no delayed hits. 1 < 4.


Z = F/R # computing Z is trivial in discrete time models as R = 1, but for completion purposes we do it here.
QResolve = [] # the queue of requests for an item where a fetch request has all ready been sent. I.e. those requests waiting to be resolved
QFetch = [] # the queue of requests for an item that triggered a miss, tracks which items the backing store needs to fetch.
prevReqs = [] # queue of all previous requests sent. Format: (req, x), where x : {0,1,2} 0 = miss, 1 = DH, 2 = hit
latencies = []

#### COUNTERS
dHits = 0
hits = 0
misses = 0
totalLatency = 0

B = BStore(I, t, Z)

def resolve(item, QResolve):
  dh = sum(1 for req in QResolve if req.i == item)
  QResolve = [req for req in QResolve if req.i != item]
  return QResolve, dh

# latency function
def p_t(item: I, time: int, prevReqs: list):
  for req, fired in prevReqs:
    if req.i == item and fired == 0: # if the requests item is the same as the one we're looking for AND if the result was a miss
      return req.t.time
  return time  

def latency(Z: int, item: I, prevReqs: list, time: int):
  return Z - ( time - p_t(item, time, prevReqs) )


cache = CacheState(t, frozenset(), size=CACHE_MAX_SIZE)

print("=" * 60)
print(f"  SIMULATION CONFIG")
print(f"  N={NUM_REQUESTS}, n={NUM_ITEMS}, R={R}, F={F}, Z={Z}, k={cache.size}")
print(f"  tmax={tmax.time}")
print("=" * 60)

trace = []

while clk.t.time < tmax.time:
  # 1. step the clock
  clk.step()
  print(f"\n--- t = {clk.t.time} ---")

  # 2. Query the backing store to see if any fetch requests are ready to be resolved
  for req in list(QFetch):
    res = B.recvFetch(req)

    # Resolve the request if possible
    if res is not None:
      QFetch.remove(req)
      trace.append([clk.t.time, "FETCH_RETURN", res.item, f"sent_at={req.t.time}"])
      print(f"  FETCH RETURN: item {res.item} (sent at t={req.t.time})")

      QResolve, dh = resolve(res, QResolve)
      dHits += dh
      if dh > 0:
        trace.append([clk.t.time, "DH_RESOLVE", res.item, f"count={dh}"])
        print(f"  RESOLVED: {dh} delayed hit(s) for item {res.item} with latencies {[ latencies[i] for i in range(len(prevReqs)) if prevReqs[i][0].i == res ]}")

      victim = policy("LRU", cache)
      if victim is not None:
        trace.append([clk.t.time, "EVICT", victim[0].item, f"last_access={victim[1]}"])
        print(f"  EVICT: item {victim[0].item} (last accessed t={victim[1]})")
      cache = cache.replace(rmv=victim, add=(res, clk.t.time))
      trace.append([clk.t.time, "ADMIT", res.item, ""])
      print(f"  ADMIT: item {res.item}")

  req = seq.sendReq()
  
  if req is not None:
    print(f"  REQUEST: item {req.i.item}")
    hitmiss = cache.arrival(req)
    if hitmiss == 1:
      hits += 1
      trace.append([clk.t.time, "HIT", req.i.item, ""])
      print(f"    -> HIT")
      old = cache.get(req.i)
      cache = cache.replace(rmv=old, add=(req.i, clk.t.time))
      prevReqs.append((req, 2))

    elif req.i in [r.i for r in QFetch]:
      QResolve.append(req)
      trace.append([clk.t.time, "DELAYED_HIT", req.i.item, "fetch_in_flight"])
      print(f"    -> DELAYED HIT (fetch in flight)")

      prevReqs.append((req, 1))

      lat = latency(Z, req.i, prevReqs, req.t.time)
      latencies.append(lat)

    else:
      QFetch.append(req)
      misses += 1
      trace.append([clk.t.time, "MISS", req.i.item, "fetch_sent"])
      print(f"    -> MISS (fetch sent)")
      prevReqs.append((req, 0))
      lat = latency(Z, req.i, prevReqs, req.t.time)
      latencies.append(lat)

  else:
      trace.append([clk.t.time, "NO_REQ", "", ""])
      print(f"  (no request this tick)")

  cache_items = [f"{i.item}" for (i, _) in cache.C]
  print(f"  CACHE: {{{', '.join(cache_items) if cache_items else 'empty'}}}")
  print(f"  QFetch: [{', '.join(str(r.i.item) for r in QFetch)}]")
  print(f"  QResolve: [{', '.join(str(r.i.item) for r in QResolve)}]")

print("\n" + "=" * 60)
print(f"  RESULTS")
print(f"  Hits:         {hits}")
print(f"  Misses:       {misses}")
print(f"  Delayed Hits: {dHits}")
print(f"  Total:        {hits + misses + dHits}")
print("=" * 60)




############## SAVE TO CSV
with open("trace.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["tick", "event", "item", "detail"])
    for row in trace:
        writer.writerow(row)

# Summary metrics
with open("metrics.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["metric", "value"])
    writer.writerow(["N", NUM_REQUESTS])
    writer.writerow(["n", NUM_ITEMS])
    writer.writerow(["R", R])
    writer.writerow(["F", F])
    writer.writerow(["Z", Z])
    writer.writerow(["k", cache.size])
    writer.writerow(["tmax", tmax.time])
    writer.writerow(["hits", hits])
    writer.writerow(["misses", misses])
    writer.writerow(["delayed_hits", dHits])
    writer.writerow(["total_requests", hits + misses + dHits])
    writer.writerow(["hit_rate", hits / (hits + misses + dHits) if (hits + misses + dHits) > 0 else 0])
    writer.writerow(["miss_rate", misses / (hits + misses + dHits) if (hits + misses + dHits) > 0 else 0])
    writer.writerow(["dh_rate", dHits / (hits + misses + dHits) if (hits + misses + dHits) > 0 else 0])

print("\nCSV files written: trace.csv, metrics.csv")