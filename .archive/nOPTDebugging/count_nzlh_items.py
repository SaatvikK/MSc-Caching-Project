# count_nzlh_items.py -- per k=|V|, how many DISTINCT items produce an NZLH.
# usage: python count_nzlh_items.py
import contextlib, io, importlib.util, re
import numpy as np

spec = importlib.util.spec_from_file_location("compsim", "comp sim.py")
compsim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compsim)

KS = [2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64]
Z_A, NMU = 8, 65536
PAT = re.compile(r"hit on I\(item=(\d+)\) at time \d+ on v(\d+), incurring latency (\d+)")

print(f"{'k=|V|':>5} {'universe':>9} {'NZLH events':>12} {'distinct items':>15} "
      f"{'as % of universe':>17} {'depths seen':>14}")
print("-"*80, flush=True)
for k in KS:
  buf = io.StringIO()
  with contextlib.redirect_stdout(buf):
    try:
      compsim.runConfig(k, k, Z_A, 6, np.inf, NMU, k*k+1, seqType="n")
    except Exception:
      pass
  hits = [(int(a), int(b)) for a, b, c in PAT.findall(buf.getvalue()) if int(c) > 0]
  items = {a for a, _ in hits}
  depths = sorted({b for _, b in hits})
  uni = k*k + 2                       # getItemNotIn uses range(k*k+2) -> 0..k_T+1
  pct = 100*len(items)/uni
  print(f"{k:>5} {uni:>9} {len(hits):>12} {len(items):>15} {pct:>16.1f}% "
        f"{str(depths):>14}", flush=True)
