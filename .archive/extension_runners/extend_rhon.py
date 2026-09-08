# extend_rhon.py -- extends the rho_n sweep to larger k=|V|.
#
# The published rho_n sweep runs k=|V| in {2,3,4,6,8,12,16}, topping out at 16,
# while every other sweep in the project reaches 128. That makes the apparent
# decay of CR with k=|V| hard to separate from small-parameter volatility, so
# this adds the larger networks on the same (Z_A, N_mu) grid.
#
# Cost is dominated by N_mu, not by the network: at Z_A=32, N_mu=131072 the
# per-config time was 59s / 43s / 53s for k=|V| = 16 / 24 / 32 -- flat in k.
#
# Rows go to n_lowerbound_sweep_ext.csv, NOT the original sweep file. Resumable:
# any (k, Z_A, N_mu) already present is skipped, so re-running continues rather
# than restarting.
#
# usage: python extend_rhon.py

import csv
import os
import time
import importlib.util
import numpy as np

spec = importlib.util.spec_from_file_location("compsim", "comp sim.py")
compsim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compsim)

TTL_VAL = 6
TMAX_VAL = np.inf

NEW_K = [24, 32, 48, 64]        # k = |V| throughout. 96 and 128 dropped:
                                # cost goes as k^2.81, so those two alone are
                                # 86% of the full grid (~34 h of ~40 h).
Z_ARANGE = [1, 2, 4, 8, 12, 16, 24, 32]              # unchanged from the sweep
NMURANGE = np.unique(np.round(2 ** np.arange(10, 17.5, 0.5)).astype(int)).tolist()

# Each config is run REPEATS times. The sequence builder draws g and every bait
# item with an unseeded rand, so a single run of one config carries roughly 31%
# spread in CR (measured: 99.29-129.85 over five runs of k=|V|=4, Z_A=4,
# N_mu=1024). At large k=|V| the ratio is already near 1, so one run per config
# cannot separate a trend from that noise -- take the median of the repeats.
REPEATS = 3

configs = [(nmu, k, k, z, r) for k in NEW_K for z in Z_ARANGE for nmu in NMURANGE
           for r in range(REPEATS)]

outfile = "n_lowerbound_sweep_ext.csv"
completed = set()
if os.path.exists(outfile):
  with open(outfile, newline="") as f:
    for row in csv.DictReader(f):
      completed.add((int(row["N_mu"]), int(row["k"]), int(row["Z_A"]), int(row["rep"])))

todo = [c for c in configs if (int(c[0]), int(c[1]), int(c[3]), int(c[4])) not in completed]
print(f"rho_n: {len(configs)} configs, {len(completed)} already done, {len(todo)} to run",
      flush=True)

new_file = not os.path.exists(outfile) or os.path.getsize(outfile) == 0
csvfile = open(outfile, "a", newline="")
writer = csv.writer(csvfile)
if new_file:
  writer.writerow(["N_mu", "k", "Vn", "Z_A", "rep", "CR"])
  csvfile.flush()

start = time.time()
for i, (Nmu, k, Vn, Z_A, rep) in enumerate(todo, start=1):
  t0 = time.time()
  L_LCE, L_OPT, Z_B, k_T = compsim.runConfig(int(k), int(Vn), int(Z_A), TTL_VAL,
                                             TMAX_VAL, int(Nmu), int(Vn) * int(k) + 1,
                                             seqType="n")
  CR = L_LCE / L_OPT if L_OPT else float("nan")
  writer.writerow([Nmu, k, Vn, Z_A, rep, CR])
  csvfile.flush()
  elapsed = time.time() - start
  print(f"[n {i}/{len(todo)}] k=|V|={k} Z_A={Z_A} N_mu={Nmu} rep={rep} CR={CR:.4f}  "
        f"config={time.time() - t0:.1f}s  elapsed={elapsed / 60:.1f}m  "
        f"eta={elapsed / i * (len(todo) - i) / 60:.1f}m", flush=True)

csvfile.close()
print(f"n DONE in {(time.time() - start) / 60:.1f} min -> {outfile}", flush=True)
