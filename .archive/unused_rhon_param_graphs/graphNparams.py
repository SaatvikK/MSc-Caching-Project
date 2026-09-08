# graphNparams.py -- rho_n against the network parameters, rather than N_mu.
#
# graphNmu.py answers "does CR diverge as the mu phase lengthens?" (Cor. 5.5.1).
# These two panels answer the companion question: how CR moves with the network
# itself, k=|V| and Z_A, at fixed sequence lengths.
#
# Same conventions as graphNmu.py: one colour per held value from the Blues
# ramp, the remaining variable drawn as unlabelled lines in the same colour so
# each colour reads as a band rather than a single curve.
#
# usage: python graphNparams.py [k|Z]     (k -> x is k=|V|;  Z -> x is Z_A)

import sys
import os
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

WHICH = sys.argv[1] if len(sys.argv) > 1 else "k"
assert WHICH in ("k", "Z"), "argument must be k or Z"

df = pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "n_lowerbound_sweep.csv"))

# All 15 N_mu values would put fifteen shades on the ramp and the panel becomes
# an indistinct mass; four geometrically spaced values separate cleanly and
# span the same three decades. The CSV keeps every value.
NMU_PLOT = [1024, 4096, 16384, 65536]
df = df[df.N_mu.isin(NMU_PLOT)]

freevar, innervar = ("k", "Z_A") if WHICH == "k" else ("Z_A", "k")
holdvals = sorted(df.N_mu.unique())
innervals = sorted(df[innervar].unique())
cols = plt.get_cmap("Blues")(np.linspace(0.35, 0.95, len(holdvals)))

plt.figure()
for i, nmu in enumerate(holdvals):
  for j, iv in enumerate(innervals):
    sub = df[(df.N_mu == nmu) & (df[innervar] == iv)].sort_values(freevar)
    plt.plot(sub[freevar], sub.CR, 'x-', color=cols[i],
             label=f"$N_\\mu$={nmu}" if j == 0 else None)

plt.xlabel("$k=|V|$" if WHICH == "k" else "$Z_A$")
plt.ylabel("Competitive Ratio")
plt.legend(title="$N_\\mu$", loc="center left", bbox_to_anchor=(1.02, 0.5),
           borderaxespad=0.0)
out = f"rhon_x{'kV' if WHICH == 'k' else 'ZA'}_PC.png"
D = os.path.dirname(os.path.abspath(__file__))
plt.savefig(os.path.join(D, out), bbox_inches="tight")

plt.xscale("log", base=2)
plt.yscale("log")
logout = out.replace(".png", "_log.png")
plt.savefig(os.path.join(D, logout), bbox_inches="tight")
print(f"wrote {out} + {logout}  ({len(df)} rows, N_mu {holdvals}, inner {innervar} {innervals})")
