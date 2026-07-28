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
import pandas as pd

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


def makeSeq(path: str, tmax, t) -> Seq:
  df = pd.read_csv(path)
  df = df.head(n=100000)
  #tmax = df.time.max()
  seq = Seq((), tmax = tmax, t=t)
  for i in range(df.shape[0]):
    req = df.iloc[i]
    time = T(time = req.time)
    item = req.item
    seq = seq.add(item, time)
    print(f"[{i+1}/{df.shape[0]} ({((i+1)/df.shape[0])*100}%)] Added item {item} on request {i}")

  return seq

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

    print(f"Clk: {clk.t.time}/{clk.tmax.time} ({(clk.t.time/clk.tmax.time)*100}%)")

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

  netLCE = constructNet(Vn, Z_A, k, ttl, tmax_val)
  netOPT = constructNet(Vn, Z_A, k, ttl, tmax_val)
  seq = makeSeq("../dataset analysis/cache-u-00-cleaned.csv", netLCE.clk.tmax, netLCE.clk.t)
  #print("SEQUENCE MADE:", seq)
  print("========== BEGINNING LCE SIM ==========")
  latsLCE = simulate(netLCE, seq, "lce")
  print(latsLCE)
  # Sequence.sendReq() compares the current tick against seqFinal.t, which
  # is still aliased to net_lce's (now-finished) clock — rebind it to
  # net_opt's fresh clock before replaying, or every sendReq() check will
  # compare against a frozen, stale time and never match.
  #seqFinal.t = net_opt.clk.t

  #print("========== BEGINNING OPT SIM ==========")
  #latsOPT = simulate(netOPT, seq, cpp="opt", leaf=leaf, policyName=policyName)

  #return sum(latsLCE), sum(latsOPT), Z_B, k_T
  return sum(latsLCE), Z_B, k_T


if __name__ == "__main__":
  TTL_VAL = 6
  TMAX_VAL = pd.read_csv("../dataset analysis/cache-u-00-cleaned.csv").time.max()

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
        L_LCE, Z_B, k_T = runConfig(int(k), int(Vn), int(Z_A), TTL_VAL, TMAX_VAL)
        #CR = L_LCE / L_OPT if L_OPT else float("nan")
        #rows.append([k, Vn, Z_A, CR])
        exec_ = time.time()-start
        #print(f"[{currepoch} / {epochs}]{exec_:.2f} sec: k={k} Vn={Vn} Z_A={Z_A} Z_B={Z_B}  "
        #      f"L_LCE={L_LCE}  L_OPT={L_OPT}  CR={CR:.4f}")
        print(f"[{currepoch} / {epochs}]{exec_:.2f} sec: k={k} Vn={Vn} Z_A={Z_A} Z_B={Z_B}  "
              f"L_LCE={L_LCE}")
        currepoch += 1
  
  print(f"SIM EXEC TIME TOTAL: {time.time() - start:.2f} seconds")

  # with open("cr_sweep.csv", "w", newline="") as f:
  #   writer = csv.writer(f)
  #   writer.writerow(["k", "Vn", "Z_A", "CR"])
  #   writer.writerows(rows)

  # print("\nCSV written: cr_sweep.csv")
