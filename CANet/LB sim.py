# comp sim.py
#
# Iterates over (k, |V|, Z_A) and, for each configuration, builds the
# adversarial sequence from report Section 5.4, runs it against LCE
# (dynamically, since the burst schedule depends on live LCE eviction
# behaviour), then replays the exact same finalised sequence against OPT
# (a pre-seeded network that never needs to rearrange), and records the
# empirical competitive ratio CR = L(LCE, rho_A) / L(OPT, rho_A).

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
import time
import numpy as np

leaf = 0
policyName = "TTL"


def constructNet(Vn, Z_A, k, ttl, tmax_val):
  """Vn = |V| = number of caches (each capacity k), in a line ending at
  the backing store. Builds a brand-new T/Clock/CacheNetwork on every
  call — nothing is shared across calls, so independent sweep points
  (and the paired LCE/OPT runs within one sweep point) never leak clock
  or cache state into each other."""
  t = T(time=0)
  tmax = T(time=tmax_val)
  clk = Clock(t, tmax)

  vertices = list(range(Vn))
  edges = [(i, i + 1) for i in range(Vn - 1)]
  B = BStore(I, t, Vn * Z_A)

  net = CN(
    (vertices, edges), {}, tmax,
    clk=clk, Z_A=Z_A, B=B, dhCount=0,
    QFetch={}, QResolve={}, ttl=ttl
  )
  net.buildMap(t, k)
  net.prefill(Vn * k)
  return net


def createSequenceSkeleton(k_T, Z_B, tmax, t):
  """The fixed prefix of rho_A (report Sec 5.4, generalised):
    1. Z_B - 1 pure requests, at t=1..Z_B-1, for item k_T+1 (not resident).
    2. One pure request, at t=Z_B, for item k_T (resident, in the last cache).
  The bursty phase is appended dynamically during simulation, since which
  item each burst targets depends on live eviction state."""
  seq = Seq((), tmax=tmax, t=t)
  freshItem = k_T + 1
  seq = seq.add(freshItem, T(time=1))
  # for tt in range(1, Z_B):
  #   seq = seq.add(freshItem, T(time=tt))
  # seq = seq.add(k_T, T(time=Z_B))
  return seq


def appendBurst(seq, item, startTime, Z_B):
  """Append Z_B consecutive per-tick requests for `item`, starting at
  startTime, with no gap before or after (the next burst, if any, starts
  immediately at startTime + Z_B)."""
  for j in range(Z_B):
    seq = seq.add(item, T(time=startTime + j))
  return seq, startTime + Z_B


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
  burstCursor = Z_B + 1  # first burst starts right after the initial fetch resolves

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


def simulate(net, seq, cpp, leaf=0, policyName="TTL"):
  """Pure replay of an ALREADY-FINALISED sequence (no live decisions)
  through `net` using the given cpp ('lce' or 'opt'). Caller must reset
  seq.nextReq = 0 before calling this a second time on the same Sequence
  object."""
  latencies = []
  Qreq = []
  clk = net.clk

  while clk.t.time < clk.tmax.time:
    clk.step()

    req = seq.sendReq()
    if req is not None:
      Qreq.append([req, leaf, leaf, clk.t.time, 0])

    to_remove = []
    for i in range(len(Qreq)):
      reqT = Qreq[i]
      if reqT[1] != reqT[2] and clk.t.time - reqT[3] < net.Z_A:
        continue

      _, stat, vNext = net.forward(reqT[0], reqT[1])

      if stat == 2: #hit
        latencies.append(reqT[4])
        to_remove.append(i)


        path = [n for n in net.pathTo(reqT[2], "b") if n != "b"]
        item = reqT[0].i
        for node in path:
          if item in net.QFetch[node]:
            net.QFetch[node].remove(item)
            _, dhs = net.resolve(item, node)
            net.dhCount += dhs
            
      elif stat == 1: # DH
        to_remove.append(i)
      elif stat == "b":
        net.cpp(reqT[0].i, reqT[2], policyName, cpp=cpp)
        latencies.append(reqT[4])
        to_remove.append(i)
      elif stat == 0: # node miss
        Qreq[i][1] = vNext
        Qreq[i][3] = clk.t.time
        Qreq[i][4] += net.Z_A

    for i in reversed(to_remove):
      Qreq.pop(i)

    if req is None and not Qreq and seq.nextReq >= len(seq.S):
      break

  return latencies + net.dhLatencies


def runConfig(k, Vn, Z_A, ttl, tmax_val):
  """Runs one (k, Vn, Z_A) sweep point end to end: builds the adversarial
  sequence against a fresh LCE network, then replays the finalised
  sequence against a fresh, independently-prefilled OPT network. Returns
  (L_LCE, L_OPT, Z_B, k_T)."""
  k_T = Vn * k
  Z_B = Vn * Z_A
  W_items = list(range(1, k + 2))  # |W| = k+1 items, subset of the initially resident set

  net_lce = constructNet(Vn, Z_A, k, ttl, tmax_val)
  seq0 = createSequenceSkeleton(k_T, Z_B, net_lce.clk.tmax, net_lce.clk.t)
  latsLCE, seqFinal = simulateAdversarial(net_lce, seq0, W_items, Z_B, leaf, policyName)

  net_opt = constructNet(Vn, Z_A, k, ttl, tmax_val)
  seqFinal.nextReq = 0
  # Sequence.sendReq() compares the current tick against seqFinal.t, which
  # is still aliased to net_lce's (now-finished) clock — rebind it to
  # net_opt's fresh clock before replaying, or every sendReq() check will
  # compare against a frozen, stale time and never match.
  seqFinal.t = net_opt.clk.t
  latsOPT = simulate(net_opt, seqFinal, cpp="opt", leaf=leaf, policyName=policyName)

  return sum(latsLCE), sum(latsOPT), Z_B, k_T


if __name__ == "__main__":
  TTL_VAL = 6
  TMAX_VAL = np.inf

  # Geometric sweeps: log-spaced points span orders of magnitude with far
  # fewer configs than a linear range, which is what the asymptotic growth
  # in k and |V| needs. Widen by bumping the arange bounds; cost per config
  # grows like Vn*Z_A*(k+3), so the top corner dominates the total runtime.
  krange = 2 ** np.arange(16)          # 1,2,4,8,16,32
  Vrange = 2 ** np.arange(1, 16)       # 2,4,8,16,32
  Z_Arange = 2 ** np.arange(3)        # 1,2,4,8,16

  rows = []
  epochs = len(krange) * len(Vrange) * len(Z_Arange)
  currepoch = 0
  start = time.time()
  for k in krange:
    for Vn in Vrange:
      for Z_A in Z_Arange:
        L_LCE, L_OPT, Z_B, k_T = runConfig(int(k), int(Vn), int(Z_A), TTL_VAL, TMAX_VAL)
        CR = L_LCE / L_OPT if L_OPT else float("nan")
        rows.append([k, Vn, Z_A, CR])
        exec_ = time.time()-start
        print(f"[{currepoch} / {epochs}]{exec_:.2f} sec: k={k} Vn={Vn} Z_A={Z_A} Z_B={Z_B}  "
              f"L_LCE={L_LCE}  L_OPT={L_OPT}  CR={CR:.4f}")
        currepoch += 1
  
  print(f"SIM EXEC TIME TOTAL: {time.time() - start:.2f} seconds")

  with open("cr_sweep.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["k", "Vn", "Z_A", "CR"])
    writer.writerows(rows)

  print("\nCSV written: cr_sweep.csv")
