# count_ladder.py -- runs the k=|V| ladder and counts the individual events that
# opts.nOptSimulate prints, rather than only the summed latency.
#
# usage: python count_ladder.py
import contextlib, io, importlib.util, re, sys
import numpy as np

spec = importlib.util.spec_from_file_location("compsim", "comp sim.py")
compsim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compsim)

KS = [2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64]
Z_A, NMU = 8, 65536

hdr = (f"{'k=|V|':>5} {'g miss':>7} {'oth miss':>9} {'DH':>4} {'NZLH':>6} "
       f"{'NZLH lat':>9} {'g hits':>8} {'phi evts':>9} {'L(OPT)':>10} {'L(LCE)':>12}")
print(hdr); print("-"*len(hdr), flush=True)

for k in KS:
  buf = io.StringIO()
  with contextlib.redirect_stdout(buf):
    try:
      compsim.runConfig(k, k, Z_A, 6, np.inf, NMU, k*k+1, seqType="n")
    except Exception:
      pass
  out = buf.getvalue().splitlines()
  gmiss = sum(1 for l in out if l.startswith("g miss"))
  omiss = sum(1 for l in out if l.startswith("miss on item"))
  dh    = sum(1 for l in out if "DH" in l)
  nzlh  = [int(m.group(1)) for l in out
           if (m := re.search(r"incurring latency (\d+)", l)) and int(m.group(1)) > 0]
  ghits = sum(1 for l in out if l.startswith("g hit"))
  tot   = [l for l in out if re.fullmatch(r"\d+ \d+", l.strip())]
  LLCE, LOPT = (tot[-1].split() if tot else ("?", "?"))
  print(f"{k:>5} {gmiss:>7} {omiss:>9} {dh:>4} {len(nzlh):>6} {sum(nzlh):>9} "
        f"{ghits:>8} {gmiss+omiss+len(nzlh):>9} {LOPT:>10} {LLCE:>12}", flush=True)
