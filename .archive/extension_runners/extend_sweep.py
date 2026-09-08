# extend_sweep.py -- extends the rho_A and rho_MW sweeps to Z_A in {64,128,256}.
#
# Same (k, |V|) grid as `comp sim.py`'s A/MW branch -- 8 x 7 = 56 pairs -- run
# at the three Z_A values above the current ceiling of 32, so the saturation in
# Z_A is visible rather than inferred. 168 configs per sequence.
#
# Rows go to {TYPE}_lowerbound_sweep_ext.csv, NOT to the existing sweep file:
# a crash or a kill part-way through then cannot damage the 336 rows already
# collected. Concatenate the two once the run finishes.
#
# Resumable: the ext CSV is appended to, not overwritten, and any (k, |V|, Z_A)
# already present in it is skipped. A kill -- or an OOM while something else is
# loading the machine -- therefore costs only the config that was in flight,
# and re-running the same command picks up where it stopped.
#
# usage: python extend_sweep.py [A|MW]

import csv
import os
import sys
import time
import importlib.util
import numpy as np

spec = importlib.util.spec_from_file_location("compsim", "comp sim.py")
compsim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compsim)

TTL_VAL = 6
TMAX_VAL = np.inf
NEW_Z_A = [64, 128]   # 256 dropped 2026-09-04: 53.7h vs 15.1h, against a Tue 12:00 deadline

TYPE = sys.argv[1] if len(sys.argv) > 1 else "A"
assert TYPE in ("A", "MW"), "type must be A or MW"

krange = 2 ** np.arange(8)       # 1,2,4,8,16,32,64,128
Vrange = 2 ** np.arange(1, 8)    # 2,4,8,16,32,64,128
# The k=|V|=128 cell alone is ~2/3 of the entire run (a single config at
# Z_A=128 projects to ~11 h), for 2 rows out of 112. It is dropped: CR
# factorises as f(k)*g(Z_A) -- the ratios of successive Z_A increments are
# 1.14/0.91/0.74/0.63 for every k=|V| from 2 to 128 -- so the Z_A shape at
# k=|V|=128 is established by the curves that are cheap to compute.
SKIP = {(128, 128)}

configs = [(1, k, Vn, Z_A) for k in krange for Vn in Vrange for Z_A in NEW_Z_A
           if (int(k), int(Vn)) not in SKIP]

# One-off additions beyond the NEW_Z_A grid. k=|V|=64 at Z_A=256 squares off the
# diagonal figure: without it that curve stops at 128 while k=|V| <= 32 reach 256.
# ~3-4 h for the single config (measured cost per Z_A doubling is ~5.6x).
EXTRA = {"A": [(1, 64, 64, 256)], "MW": []}
configs += EXTRA[TYPE]

# Anything already in the ext CSV was completed by an earlier invocation.
outfile = f"{TYPE}_lowerbound_sweep_ext.csv"
completed = set()
if os.path.exists(outfile):
  with open(outfile, newline="") as f:
    for row in csv.DictReader(f):
      completed.add((int(row["k"]), int(row["Vn"]), int(row["Z_A"])))

todo = [c for c in configs if (int(c[1]), int(c[2]), int(c[3])) not in completed]
print(f"{TYPE}: {len(configs)} configs, {len(completed)} already done, "
      f"{len(todo)} to run", flush=True)

# Cost per config is Vn*Z_A*(k+3), so the remaining-work estimate is far better
# than "configs left / configs done" -- the last few configs are most of the run.
# Only the outstanding work is counted, so the ETA reflects this invocation.
cost = lambda k, Vn, Z_A: int(Vn) * int(Z_A) * (int(k) + 3)
total_cost = sum(cost(k, Vn, Z_A) for _, k, Vn, Z_A in todo)
done_cost = 0

start = time.time()
new_file = not os.path.exists(outfile) or os.path.getsize(outfile) == 0
csvfile = open(outfile, "a", newline="")
writer = csv.writer(csvfile)
if new_file:
  writer.writerow(["N_mu", "k", "Vn", "Z_A", "CR"])
  csvfile.flush()

for i, (Nmu, k, Vn, Z_A) in enumerate(todo, start=1):
  UNIVERSE_SIZE = int(Vn) * int(k) + 1
  t0 = time.time()
  L_LCE, L_OPT, Z_B, k_T = compsim.runConfig(int(k), int(Vn), int(Z_A), TTL_VAL,
                                             TMAX_VAL, int(Nmu), UNIVERSE_SIZE,
                                             seqType=TYPE)
  CR = L_LCE / L_OPT if L_OPT else float("nan")
  writer.writerow([Nmu, k, Vn, Z_A, CR])
  csvfile.flush()

  done_cost += cost(k, Vn, Z_A)
  elapsed = time.time() - start
  eta = elapsed * (total_cost - done_cost) / done_cost
  print(f"[{TYPE} {i}/{len(todo)}] k={k} Vn={Vn} Z_A={Z_A} "
        f"CR={CR:.4f}  config={time.time() - t0:.1f}s  elapsed={elapsed / 60:.1f}m  "
        f"work={100 * done_cost / total_cost:.1f}%  eta={eta / 60:.1f}m",
        flush=True)

csvfile.close()
print(f"{TYPE} DONE in {(time.time() - start) / 60:.1f} min -> "
      f"{TYPE}_lowerbound_sweep_ext.csv", flush=True)
