# comp sim.py

from dataclasses import dataclass
from typing import Tuple, FrozenSet, TypeVar
from framework.clock import V, I, T, Clock
from framework.sequence import Sequence as Seq
from framework.sequence import Request as Req
from framework.backingstore import BackingStore as BStore
from framework.cache import CacheState
from framework.policies import *
from framework.network import CacheNetwork as CN
import csv
import random
import sys
import time
import numpy as np
from simulations import sequenceBuild as sb


leaf = 0
policyName = "TTL"


def constructNet(Vn, Z_A, k, ttl, tmax_val):
  """
  Vn (|V|) number of caches (each capacity k), in a line network. 
  Builds a new T/Clock/CacheNetwork on every call.
  """

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
  """
  The fixed prefix of rho_A is as follows:
  1. Z_B - 1 pure requests for item k_T + 1 (not in the network at t=0).
  2. One request, at t = Z_B, for item k_T (in the last cache in the network).

  The bursty part is not added here as it is constructed dynamically based on LCE's behaviour,
  so it is created and stored in realtime later.
  """
  seq = Seq((), tmax=tmax, t=t)
  freshItem = k_T + 1
  seq = seq.add(freshItem, T(time=1))
  return seq

def runConfig(k, Vn, Z_A, ttl, tmax_val, Nmu, UniSize = 6, seqType = "A"):
  """
  Runs one (k, Vn, Z_A) configuration: builds the adversarial
  sequence against the network running LCE, then replays the finalised
  sequence against a network running OPT. Returns
  (L_LCE, L_OPT, Z_B, k_T).
  """

  # Compute further parameters
  k_T = Vn * k
  Z_B = Vn * Z_A
  W_items = list(range(1, k + 2))  # |W| = k+1 items, used by rho_A.

  net_lce = constructNet(Vn, Z_A, k, ttl, tmax_val)
  seqFinal, latsLCE = None, None

  # depending on what type of simulation (sequence) we're running...
  # the sb.suimulateXYZ is the LCE simulation that dynamically constructs the sequence WHILE counting the latency that LCE incurs.
  if seqType == "A":
    seq0 = createSequenceSkeleton(k_T, Z_B, net_lce.clk.tmax, net_lce.clk.t)
    latsLCE, seqFinal = sb.simulateAdversarial(net_lce, seq0, W_items, Z_B, leaf, policyName)
  elif seqType == "MW":
    latsLCE, seqFinal = sb.simulateManoharWilliams(net_lce, UniSize, Z_B, k, leaf, policyName)

  elif seqType == "n":
    latsLCE, seqFinal = sb.simulateRhon(net_lce, Nmu, UniSize, Z_B, k, leaf, policyName)

  # After the LCE simulation, rebuild the network to prep for OPT.
  net_opt = constructNet(Vn, Z_A, k, ttl, tmax_val)
  seqFinal.nextReq = 0 # reset the sequence's next request counter.
  seqFinal.t = net_opt.clk.t # set the sequence to opt's network's clock (was lce's before)

  # rho_n is the only sequence that re-requests its target item, so it is the
  # only one that asks optSimulate to time that hit; the others get None back.
  cppName = {"A": "aOPT", "MW": "mwOPT", "n": "nOPT"}[seqType]
  trackItem = seqFinal.S[0].i if seqType == "n" else None
  latsOPT, gTime = sb.optSimulate(net_opt, seqFinal, cpp=cppName, leaf=leaf,
                                    policyName=policyName, trackItem=trackItem)

  # Sum both the latencies and return
  LLCE, LOPT, Z_B, k_T = sum(latsLCE), sum(latsOPT), Z_B, k_T
  #print(LLCE, LOPT)
  return LLCE, LOPT, Z_B, k_T, latsLCE, latsOPT, seqFinal, gTime


def runsim(TYPE: str = "A", showcase = None):
  # A = rho_A, MW = rho_MW, n = rho_n
  assert TYPE in ["A", "MW", "n"]

  TTL_VAL = 6
  TMAX_VAL = np.inf

  # `showcase` is a callable taking the sequence name and returning
  # (krange, Vrange, Z_Arange, Nmurange). It is passed TYPE so it can give
  # rho_n a different grid, and it takes precedence over the defaults below --
  # including for rho_n, whose defaults would otherwise overwrite it.
  if showcase is not None:
    krange, Vrange, Z_Arange, Nmurange = showcase(TYPE)
  elif TYPE == "n":
    # rho_n's family index is N_mu, not the network: Corollary 5.5.1 asks for
    # CR -> infinity with x_0 = (k, |V|, Z_A) fixed.
    # Vn is tied to k because phi can only walk item `g` down the line while k >= |V|.
    krange = np.array([2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64])   # Vn = k
    Vrange = krange                                              # unused; Vn = k
    Z_Arange = np.array([1, 2, 4, 8, 12, 16, 24, 32])
    Nmurange = np.unique(np.round(2 ** np.arange(10, 17.5, 0.5)).astype(int))
  else:
    # Geometric sweeps: log-spaced points span orders of magnitude with far
    # fewer configs than a linear range.
    # Cost per config grows like Vn*Z_A*(k+3), so the top corner dominates the total runtime.
    krange = 2 ** np.arange(8)          # 1,2,4,8,16,32,64,128
    Vrange = 2 ** np.arange(1, 8)       # 2,4,8,16,32,64,128
    Z_Arange = 2 ** np.arange(9)        # 1,2,4,8,16,32,64,128,256
    Nmurange = np.array([1])            # only rho_n has a mu phase

  if TYPE == "n":
    # Vn = k throughout, so |V| is not swept independently.
    configs = [(Nmu, k, k, Z_A) for Nmu in Nmurange
               for k in krange for Z_A in Z_Arange]
  else:
    # The k=|V|=128 cell is excluded at Z_A >= 64. Cost per configuration grows
    # as roughly k^2 |V|^2.5 Z_A^1.8, which puts that single cell at ~11 h for
    # Z_A=128 alone -- about two thirds of the whole sweep for 2 rows of 112.
    # CR factorises as f(k) g(Z_A) (the ratios of successive Z_A increments agree
    # to two decimals for every k=|V| from 2 to 128), so the Z_A behaviour there
    # is established by the cells that are affordable.
    SKIP_LARGE_Z_A = {(128, 128)}

    # Z_A=256 is a partial column. It was carried far enough to give every curve
    # of the k=|V| diagonal a point there, and no further: cost per configuration
    # grows as roughly k^2 |V|^2.5 Z_A^1.8, so the remaining cells at 256 would
    # have cost more than the rest of the sweep combined. The cells that were run:
    Z_A_256_CELLS = ({(int(k), int(V)) for k in (1, 2, 4, 8, 16) for V in Vrange}
                     | {(32, V) for V in (2, 4, 8, 16, 32)}
                     | {(64, 64)})

    configs = [(Nmu, k, Vn, Z_A) for Nmu in Nmurange for k in krange
               for Vn in Vrange for Z_A in Z_Arange
               if not (Z_A >= 64 and (int(k), int(Vn)) in SKIP_LARGE_Z_A)
               and (Z_A != 256 or (int(k), int(Vn)) in Z_A_256_CELLS)]

  rows = []
  epochs = len(configs)
  currepoch = 0
  start = time.time()

  # Freeze one config's traces, picked at random each run, so the latency
  # graphs are not always drawn from the last config in the sweep.
  keepIdx = len(configs)-1 #random.randrange(len(configs))
  keptLCE = keptOPT = keptSeq = keptGTime = None

  csvfile = open(f"./rho{TYPE}/{TYPE}_sim.csv", "w", newline="")
  writer = csv.writer(csvfile)
  writer.writerow(["N_mu", "k", "Vn", "Z_A", "CR"])
  for Nmu, k, Vn, Z_A in configs:

    UNIVERSE_SIZE = int(Vn) * int(k) + 1
    L_LCE, L_OPT, Z_B, k_T, latsLCE, latsOPT, seq_, gTime = runConfig(int(k), int(Vn), int(Z_A), TTL_VAL, TMAX_VAL,
                                       int(Nmu), UNIVERSE_SIZE, seqType=TYPE)
    if currepoch == keepIdx:
      keptLCE, keptOPT, keptSeq, keptGTime = latsLCE, latsOPT, seq_, gTime
      keptCfg = (Nmu, k, Vn, Z_A)
    CR = L_LCE / L_OPT if L_OPT else float("nan")
    rows.append([Nmu, k, Vn, Z_A, CR])
    writer.writerow([Nmu, k, Vn, Z_A, CR]); csvfile.flush()
    exec_ = time.time()-start
    print(f"[{currepoch} / {epochs}]{exec_:.2f} sec: Nmu={Nmu} k={k} Vn={Vn} Z_A={Z_A} Z_B={Z_B}  "
          f"L_LCE={L_LCE}  L_OPT={L_OPT}  CR={CR:.4f}")
    currepoch += 1
  
  print(f"SIM EXEC TIME TOTAL: {time.time() - start:.2f} seconds")

  csvfile.close()

  print(f"\nCSV written: /rho{TYPE}/{TYPE}_sim.csv")
  print(f"latency traces kept from config {keepIdx}/{epochs}: "
        f"Nmu={keptCfg[0]} k={keptCfg[1]} Vn={keptCfg[2]} Z_A={keptCfg[3]}")
  return keptLCE, keptOPT, [r.t.time for r in keptSeq.S], keptGTime




"""
for A and mw:
  krange = 2 ** np.arange(8)          # 1,2,4,8,16,32,64,128
  Vrange = 2 ** np.arange(1, 8)       # 2,4,8,16,32,64,128
  Z_Arange = 2 ** np.arange(6)        # 1,2,4,8,16,32
  Nmurange = 1 # set to 1 unless you're testing uncompetitiveness

"""