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
import sys
import time
import numpy as np
import sequenceBuild as sb
import opts

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


def runConfig(k, Vn, Z_A, ttl, tmax_val, Nmu, UniSize = 6, seqType = "A"):
  """Runs one (k, Vn, Z_A) sweep point end to end: builds the adversarial
  sequence against a fresh LCE network, then replays the finalised
  sequence against a fresh, independently-prefilled OPT network. Returns
  (L_LCE, L_OPT, Z_B, k_T)."""
  k_T = Vn * k
  Z_B = Vn * Z_A
  W_items = list(range(1, k + 2))  # |W| = k+1 items, subset of the initially resident set

  net_lce = constructNet(Vn, Z_A, k, ttl, tmax_val)
  seqFinal, latsLCE = None, None
  if seqType == "A":
    seq0 = createSequenceSkeleton(k_T, Z_B, net_lce.clk.tmax, net_lce.clk.t)
    latsLCE, seqFinal = sb.simulateAdversarial(net_lce, seq0, W_items, Z_B, leaf, policyName)
  elif seqType == "MW":
    latsLCE, seqFinal = sb.simulateManoharWilliams(net_lce, UniSize, Z_B, k, leaf, policyName)

  elif seqType == "n":
    latsLCE, seqFinal = sb.simulateRhon(net_lce, Nmu, UniSize, Z_B, k, leaf, policyName)

  net_opt = constructNet(Vn, Z_A, k, ttl, tmax_val)
  seqFinal.nextReq = 0
  # Sequence.sendReq() compares the current tick against seqFinal.t, which
  # is still aliased to net_lce's (now-finished) clock — rebind it to
  # net_opt's fresh clock before replaying, or every sendReq() check will
  # compare against a frozen, stale time and never match.
  seqFinal.t = net_opt.clk.t

  if seqType == "A":
    latsOPT = opts.aOptSimulate(net_opt, seqFinal, cpp="aOPT", leaf=leaf, policyName=policyName)
  elif seqType == "MW":
    latsOPT = opts.mwOptSimulate(net_opt, seqFinal, cpp="mwOPT", leaf=leaf, policyName=policyName, UNIVERSE_SIZE = 6)
  elif seqType == "n":
    latsOPT = opts.nOptSimulate(net_opt, seqFinal, cpp="nOPT", leaf=leaf, policyName=policyName)

  return sum(latsLCE), sum(latsOPT), Z_B, k_T


if __name__ == "__main__":
  TTL_VAL = 6
  TMAX_VAL = np.inf
  # usage: python "comp sim.py" [A|MW|n]
  TYPE = sys.argv[1] if len(sys.argv) > 1 else "MW" # A = rho_A, MW = rho_MW, n = rho_n

  # Geometric sweeps: log-spaced points span orders of magnitude with far
  # fewer configs than a linear range, which is what the asymptotic growth
  # in k and |V| needs. Widen by bumping the arange bounds; cost per config
  # grows like Vn*Z_A*(k+3), so the top corner dominates the total runtime.
  krange = 2 ** np.arange(8)          # 1,2,4,8,16,32,64,128
  Vrange = 2 ** np.arange(1, 8)       # 2,4,8,16,32,64,128
  Z_Arange = 2 ** np.arange(6)        # 1,2,4,8,16,32
  Nmurange = np.array([1])            # only rho_n has a mu phase

  if TYPE == "n":
    # rho_n's family index is N_mu, not the network: Corollary 5.5.1 asks for
    # CR -> infinity with x_0 = (k, |V|, Z_A) fixed. Empirically
    # CR = C * N_mu / (k|V|), with C an O(1) constant (0.7 to 1.9 across this
    # grid), so N_mu has to outgrow k|V| for the ratio to diverge -- hence a
    # far longer N_mu range than network range, and no k = |V| > 16 (k|V| =
    # 1024 would put the smallest-N_mu corner at CR ~ 1.5). Vn is tied to k
    # because phi can only walk g down the line while k >= |V|.
    krange = np.array([2, 3, 4, 6, 8, 12, 16])       # Vn = k
    Z_Arange = np.array([1, 2, 4, 8, 12, 16, 24, 32])
    # Half-octave steps over the same 1024..131072 interval: 15 points
    # instead of 8, so the linear growth in N_mu is sampled densely enough
    # to read the trend off the panel rather than infer it from 8 crosses.
    Nmurange = np.unique(np.round(2 ** np.arange(10, 17.5, 0.5)).astype(int))
    configs = [(Nmu, k, k, Z_A) for Nmu in Nmurange
               for k in krange for Z_A in Z_Arange]
  else:
    configs = [(Nmu, k, Vn, Z_A) for Nmu in Nmurange for k in krange
               for Vn in Vrange for Z_A in Z_Arange]

  rows = []
  epochs = len(configs)
  currepoch = 0
  start = time.time()
  # Rows are written as they are computed. The expensive corners come last in
  # the loop order, so a run that is cut short still leaves every cheaper
  # config on disk and plottable, rather than losing the lot.
  csvfile = open(f"{TYPE}_lowerbound_sweep.csv", "w", newline="")
  writer = csv.writer(csvfile)
  writer.writerow(["N_mu", "k", "Vn", "Z_A", "CR"])
  for Nmu, k, Vn, Z_A in configs:
    # |I| = k_T + 1 (report Sec 5.2): exactly one item sits outside the
    # network at all times, so the adversary always has a target. Same
    # formula for every sequence type and every sweep point.
    UNIVERSE_SIZE = int(Vn) * int(k) + 1
    L_LCE, L_OPT, Z_B, k_T = runConfig(int(k), int(Vn), int(Z_A), TTL_VAL, TMAX_VAL,
                                       int(Nmu), UNIVERSE_SIZE, seqType=TYPE)
    CR = L_LCE / L_OPT if L_OPT else float("nan")
    rows.append([Nmu, k, Vn, Z_A, CR])
    writer.writerow([Nmu, k, Vn, Z_A, CR]); csvfile.flush()
    exec_ = time.time()-start
    print(f"[{currepoch} / {epochs}]{exec_:.2f} sec: Nmu={Nmu} k={k} Vn={Vn} Z_A={Z_A} Z_B={Z_B}  "
          f"L_LCE={L_LCE}  L_OPT={L_OPT}  CR={CR:.4f}")
    currepoch += 1
  
  print(f"SIM EXEC TIME TOTAL: {time.time() - start:.2f} seconds")

  csvfile.close()

  print(f"\nCSV written: {TYPE}_lowerbound_sweep.csv")



"""
for A and mw:
  krange = 2 ** np.arange(8)          # 1,2,4,8,16,32,64,128
  Vrange = 2 ** np.arange(1, 8)       # 2,4,8,16,32,64,128
  Z_Arange = 2 ** np.arange(6)        # 1,2,4,8,16,32
  Nmurange = 1 # set to 1 unless you're testing uncompetitiveness

"""