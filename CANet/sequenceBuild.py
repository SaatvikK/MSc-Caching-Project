from clock import V, I, T, Clock
from network import CacheNetwork
import random as rand 
from sequence import Sequence as Seq

def appendBurst(seq, item, startTime, Z_B):
  """Append a bursty request (null^Z_B, item^Z_B, null^Z_B)"""
  startTime += Z_B ## add the initial Z_B of no requests
  for j in range(Z_B):
    seq = seq.add(item, T(time=startTime + j))
  
  startTime += Z_B*2 # then increase the time once, to account for the Z_B items
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


def simulateManoharWilliams(net, ISize, Z_B, k, tmax, leaf=0, policyName="TTL"):
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
  initItem = rand.sample(notin, 1)[0]
  seq = Seq((), tmax=tmax, t=clk.t)
  seq = seq.add(initItem, T(time = Z_B))

  while clk.t.time < clk.tmax.time:
    clk.step()

    # Scheduling must happen AFTER clk.step() (i.e. using the tick that
    # sendReq() is about to check against), not before.
    if burstsDone < k and clk.t.time >= burstCursor:
      present = {i.item for i in net.getItems()}
      notin = universe - present
      candidate = rand.sample(notin, 1)[0]

      assert candidate, (
        f"no unused item in I absent from network at "
        f"t={clk.t.time}; adversarial construction assumption violated"
      )

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
