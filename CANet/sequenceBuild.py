from clock import V, I, T, Clock
from network import CacheNetwork
import random as rand 
from sequence import Sequence as Seq
from policies import TTL

def appendBurst(seq, item, startTime, Z_B):
  """Append a bursty request (null^Z_B, item^Z_B, null^Z_B)"""
  startTime += Z_B ## add the initial Z_B of no requests
  for j in range(Z_B):
    seq = seq.add(item, T(time=startTime + j))
  
  startTime += Z_B*2 # then increase the time once, to account for the Z_B items
  # and then again, to account for the final Z_B wait of no requests.
  return seq, startTime

def appendPure(seq, item, startTime, Z_B):
  """Append a bursty request (null^Z_B, item, null^Z_B)"""
  startTime += Z_B ## add the initial Z_B of no requests
  seq = seq.add(item, T(time=startTime))
  
  startTime += Z_B + 1 # then increase the time once, to account for the Z_B items
  # and then again, to account for the final Z_B wait of no requests.
  return seq, startTime


def simulateAdversarial(net, seq, W_items, Z_B, leaf=0, policyName="TTL"):
  """Drives `net` (under LCE) through the fixed-prefix sequence, then
  dynamically appends len(W_items) bursts as the clock reaches each
  burst's start tick, each targeting whichever W-item is currently both
  absent from the network and not yet used. Returns (latencies, seq) —
  seq is now fully concrete and can be replayed verbatim against another
  (e.g. OPT) network."""
  latencies = []
  Qreq = []  # [req, current_v, origin_leaf, t_arrived, latency]
  clk = net.clk

  usedItems = set()
  burstsDone = 0
  maxBursts = len(W_items)
  burstCursor = 2 # first burst starts right after the initial fetch resolves

  while clk.t.time < clk.tmax.time:
    clk.step()

    # Scheduling must happen AFTER clk.step() (i.e. using the tick that
    # sendReq() is about to check against), not before.
    if burstsDone < maxBursts and clk.t.time >= burstCursor:
      present = net.getItems()
      candidates = [w for w in W_items if w not in present and w not in usedItems]
      assert candidates, (
        f"no unused item in W={W_items} absent from network at "
        f"t={clk.t.time}; adversarial construction assumption violated"
      )
      item = candidates[0]
      usedItems.add(item)
      seq, burstCursor = appendBurst(seq, item, burstCursor, Z_B)
      burstsDone += 1

    req = seq.sendReq()
    if req is not None:
      Qreq.append([req, leaf, leaf, clk.t.time, 0])

    to_remove = []
    for i in range(len(Qreq)):
      reqT = Qreq[i]
      if reqT[1] != reqT[2] and clk.t.time - reqT[3] < net.Z_A:
        continue

      _, stat, vNext = net.forward(reqT[0], reqT[1])

      if stat == 2: # hit
        latencies.append(reqT[4])
        to_remove.append(i)


        path = [n for n in net.pathTo(reqT[2], "b") if n != "b"]
        item = reqT[0].i
        for node in path:
          if item in net.QFetch[node]:
            net.QFetch[node].remove(item)
            _, dhs = net.resolve(item, node)
            net.dhCount += dhs
            
      elif stat == 1:  # delayed hit — its latency is recorded later, via
        to_remove.append(i)  # net.dhLatencies, once the underlying fetch resolves
      elif stat == "b":  # reached backing store — fetch resolves now
        net.cpp(reqT[0].i, reqT[2], policyName, cpp="lce")
        latencies.append(reqT[4])
        to_remove.append(i)
      elif stat == 0:  # miss, advance to next hop
        Qreq[i][1] = vNext
        Qreq[i][3] = clk.t.time
        Qreq[i][4] += net.Z_A

    for i in reversed(to_remove):
      Qreq.pop(i)

    if (req is None and not Qreq and seq.nextReq >= len(seq.S)
        and burstsDone >= maxBursts):
      break

  return latencies + net.dhLatencies, seq


def simulateManoharWilliams(net, ISize, Z_B, k, leaf=0, policyName="TTL"):
  """Drives `net` (under LCE) through the manohar-williams sequence, then
  dynamically appends len(W_items) bursts as the clock reaches each
  burst's start tick, each targeting whichever W-item is currently both
  absent from the network and not yet used. Returns (latencies, seq) —
  seq is now fully concrete and can be replayed verbatim against another
  (e.g. OPT) network."""
  latencies = []
  Qreq = []  # [req, current_v, origin_leaf, t_arrived, latency]
  clk = net.clk

  burstsDone = 0
  burstCursor = 2*Z_B+1  # first burst starts right after the initial fetch resolves

  # add initial pure request: (0^Z_B, i, 0^Z_B)
  N_0 = {i.item for i in net.getItems()}
  universe = { i for i in range(ISize + 1)} 
  notin = universe - N_0
  initItem = rand.sample(sorted(notin), 1)[0]  # 3.11+ removed sampling from a set
  seq = Seq((), tmax=clk.tmax, t=clk.t)
  seq = seq.add(initItem, T(time = Z_B))

  while clk.t.time < clk.tmax.time:
    clk.step()

    # Scheduling must happen AFTER clk.step() (i.e. using the tick that
    # sendReq() is about to check against), not before.
    if burstsDone < k and clk.t.time >= burstCursor:
      present = {i.item for i in net.getItems()}
      notin = universe - present

      assert notin, (  # not `assert candidate`: item 0 is valid but falsy
        f"no unused item in I absent from network at "
        f"t={clk.t.time}; adversarial construction assumption violated"
      )
      candidate = rand.sample(sorted(notin), 1)[0]

      seq, burstCursor = appendBurst(seq, candidate, burstCursor, Z_B)
      burstsDone += 1

    req = seq.sendReq()
    if req is not None:
      Qreq.append([req, leaf, leaf, clk.t.time, 0])

    to_remove = []
    for i in range(len(Qreq)):
      reqT = Qreq[i]
      if reqT[1] != reqT[2] and clk.t.time - reqT[3] < net.Z_A:
        continue

      _, stat, vNext = net.forward(reqT[0], reqT[1])

      if stat == 2: # hit
        latencies.append(reqT[4])
        to_remove.append(i)


        path = [n for n in net.pathTo(reqT[2], "b") if n != "b"]
        item = reqT[0].i
        for node in path:
          if item in net.QFetch[node]:
            net.QFetch[node].remove(item)
            _, dhs = net.resolve(item, node)
            net.dhCount += dhs
            
      elif stat == 1:  # delayed hit — its latency is recorded later, via
        to_remove.append(i)  # net.dhLatencies, once the underlying fetch resolves
      elif stat == "b":  # reached backing store — fetch resolves now
        net.cpp(reqT[0].i, reqT[2], policyName, cpp="lce")
        latencies.append(reqT[4])
        to_remove.append(i)
      elif stat == 0:  # miss, advance to next hop
        Qreq[i][1] = vNext
        Qreq[i][3] = clk.t.time
        Qreq[i][4] += net.Z_A

    for i in reversed(to_remove):
      Qreq.pop(i)

    if (req is None and not Qreq and seq.nextReq >= len(seq.S)
        and burstsDone >= k):
      break

  return latencies + net.dhLatencies, seq



def simulateRhon(net, Nmu, ISize, Z_B, k, leaf=0, policyName="TTL"):
  """Drives `net` (under LCE) through rho_n = phi + mu (report Sec 5.5.1),
  building both subsequences live, since each depends on the eviction state
  the previous requests produced. phi walks the target g from the leaf down
  to the last cache: at each cache it refreshes every resident entry except
  g until TTL surfaces g, then evicts it with a bait item fetched from the
  backing store. mu then requests g Nmu times, each a hit at depth d costing
  d * Z_A. Returns (latencies, seq) — seq is now fully concrete and can be
  replayed verbatim against another (e.g. OPT) network."""
  latencies = []
  Qreq = []  # [req, current_v, origin_leaf, t_arrived, latency]
  clk = net.clk

  def getItemNotIn():
    N_0 = {i.item for i in net.getItems()}
    universe = {i for i in range(ISize + 1)}
    notin = universe - N_0
    assert notin, f"no item of I outside the network at t={clk.t.time}"
    return rand.sample(sorted(notin), 1)[0]  # 3.11+ removed sampling from a set

  # the opening pure request (0^Z_B, g, 0^Z_B) leaves g in every cache
  target = getItemNotIn()
  seq = Seq((), tmax=clk.tmax, t=clk.t)
  seq, cursor = appendPure(seq, target, clk.t.time, Z_B)

  vi = 0                          # cache phi is currently evicting g from
  lastCache = len(net.G[0]) - 1   # g is left here, so mu's hits cost d * Z_A
  muReqsDone = 0

  while clk.t.time < clk.tmax.time:
    clk.step()

    # Scheduling must happen AFTER clk.step() (i.e. using the tick that
    # sendReq() is about to check against), not before.
    if clk.t.time >= cursor:
      if vi < lastCache:
        cache = net.M[vi]
        victim = TTL(cache)
        if victim is not None and victim[0].item == target:
          seq, cursor = appendPure(seq, getItemNotIn(), cursor, Z_B)
          vi += 1
        else:
          # only items absent from every shallower cache actually reach vi
          shallower = {i.item for n in range(vi) for (i, _) in net.M[n].C}
          items = sorted(i.item for i in cache.getall()
                         if i.item != target and i.item not in shallower)
          assert items, (
            f"nothing at v{vi} can be refreshed at t={clk.t.time}: every "
            f"entry besides {target} is shadowed by a shallower cache"
          )
          seq, cursor = appendPure(seq, rand.choice(items), cursor, Z_B)
      elif muReqsDone < Nmu:
        seq = seq.add(target, T(time=clk.t.time))
        cursor = clk.t.time + 1
        muReqsDone += 1

    req = seq.sendReq()
    if req is not None:
      Qreq.append([req, leaf, leaf, clk.t.time, 0])

    to_remove = []
    for i in range(len(Qreq)):
      reqT = Qreq[i]
      if reqT[1] != reqT[2] and clk.t.time - reqT[3] < net.Z_A:
        continue

      _, stat, vNext = net.forward(reqT[0], reqT[1])

      if stat == 2: # hit
        latencies.append(reqT[4])
        to_remove.append(i)


        path = [n for n in net.pathTo(reqT[2], "b") if n != "b"]
        item = reqT[0].i
        for node in path:
          if item in net.QFetch[node]:
            net.QFetch[node].remove(item)
            _, dhs = net.resolve(item, node)
            net.dhCount += dhs

      elif stat == 1:  # delayed hit — its latency is recorded later, via
        to_remove.append(i)  # net.dhLatencies, once the underlying fetch resolves
      elif stat == "b":  # reached backing store — fetch resolves now
        net.cpp(reqT[0].i, reqT[2], policyName, cpp="lce")
        latencies.append(reqT[4])
        to_remove.append(i)
      elif stat == 0:  # miss, advance to next hop
        Qreq[i][1] = vNext
        Qreq[i][3] = clk.t.time
        Qreq[i][4] += net.Z_A

    for i in reversed(to_remove):
      Qreq.pop(i)

    if (req is None and not Qreq and seq.nextReq >= len(seq.S)
        and vi >= lastCache and muReqsDone >= Nmu):
      break

  return latencies + net.dhLatencies, seq
