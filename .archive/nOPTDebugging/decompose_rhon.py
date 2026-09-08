# decompose_rhon.py -- splits rho_n's competitive ratio into its parts.
#
# The sweep CSVs store only CR = L(LCE)/L(O), so when CR moves with k=|V| there
# is no way to tell which side moved. This records L(LCE) and L(O) separately,
# and separates the phi and mu contributions by running each configuration
# twice: once with N_mu = 0 (phi only) and once with the full mu phase. The mu
# contribution is then the difference.
#
#   L_phi     = L(N_mu = 0)
#   L_mu      = L(N_mu = NMU) - L(N_mu = 0)
#
# Z_A and N_mu are held fixed so k=|V| is the only variable. REPEATS handles the
# unseeded rand in the sequence builder; medians are taken per configuration.
#
# usage: python decompose_rhon.py   ->  rhon_decomposition.csv

import contextlib
import csv
import io
import statistics as st
import time
import importlib.util
import numpy as np

spec = importlib.util.spec_from_file_location("compsim", "comp sim.py")
compsim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compsim)


def run(k, Z_A, nmu):
  """runConfig prints "LLCE LOPT" and returns nothing, so read its stdout."""
  buf = io.StringIO()
  with contextlib.redirect_stdout(buf):
    try:
      compsim.runConfig(k, k, Z_A, 6, np.inf, nmu, k * k + 1, seqType="n")
    except TypeError:
      pass
  a, b = buf.getvalue().strip().split()[-2:]
  return float(a), float(b)

KS = [2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64]
Z_A = 8
NMU = 65536
REPEATS = 3

out = open("rhon_decomposition.csv", "w", newline="")
w = csv.writer(out)
w.writerow(["k", "Z_A", "N_mu",
            "L_LCE_phi", "L_OPT_phi", "L_LCE_mu", "L_OPT_mu",
            "L_LCE_total", "L_OPT_total", "CR"])

start = time.time()
for k in KS:
  phiL, phiO, totL, totO = [], [], [], []
  for r in range(REPEATS):
    a, b = run(k, Z_A, 0)
    phiL.append(a); phiO.append(b)
    a, b = run(k, Z_A, NMU)
    totL.append(a); totO.append(b)
  lp, op = st.median(phiL), st.median(phiO)
  lt, ot = st.median(totL), st.median(totO)
  w.writerow([k, Z_A, NMU, lp, op, lt - lp, ot - op, lt, ot, lt / ot if ot else float("nan")])
  out.flush()
  print(f"k=|V|={k:>3}  phi: LCE={lp:>10.0f} OPT={op:>8.0f}  "
        f"mu: LCE={lt-lp:>12.0f} OPT={ot-op:>8.0f}  "
        f"CR={lt/ot if ot else float('nan'):>9.2f}  [{time.time()-start:.0f}s]", flush=True)

out.close()
print(f"wrote rhon_decomposition.csv in {(time.time()-start)/60:.1f} min", flush=True)
