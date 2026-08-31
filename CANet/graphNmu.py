# graphNmu.py -- plot for rho_n (report Sec 5.5.1) only.
#
# Unlike graph.py, nothing here is selectable: rho_n has one thing to show,
# so the panel is hard-coded. Reads n_lowerbound_sweep.csv, which comp sim.py
# writes with the columns N_mu,k,Vn,Z_A,CR (Vn == k throughout, since phi only
# walks g down the line while k >= |V|).
#
# Corollary 5.5.1 is pointwise in x_0 = (k, |V|, Z_A): P is uncompetitive as
# soon as ONE fixed network admits a family {rho_n} with CR -> infinity. So
# N_mu is the only variable on the x axis, and each of the 24 network configs
# drawn here is its own witness. The vertical offset between the bands is a
# scale factor, not a bound -- a larger network simply needs a longer psi to
# reach the same ratio.
#
# usage: python graphNmu.py

import matplotlib
matplotlib.use("Agg")  # no display under WSL2; Qt backend aborts on import
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

df = pd.read_csv("n_lowerbound_sweep.csv")

# The sweep runs k = |V| in {2,3,4,6,8,12,16}, but plotting all seven puts
# the four lightest shades of the Blues ramp on top of each other and the
# upper half of the panel becomes an indistinct mass. Four geometrically
# spaced values separate cleanly and tell the same story; the CSV keeps
# every k for anyone who wants the rest.
KPLOT = [2, 4, 8, 16]
df = df[df.k.isin(KPLOT)]

kvals = sorted(df.k.unique())
zvals = sorted(df.Z_A.unique())
cols = plt.get_cmap("Blues")(np.linspace(0.35, 0.95, len(kvals)))

# One colour per k=|V|; the six Z_A curves inside a colour are unlabelled, so
# each colour reads as a band rather than a single curve.
plt.figure()
for i, kv in enumerate(kvals):
  for j, zv in enumerate(zvals):
    sub = df[(df.k == kv) & (df.Z_A == zv)].sort_values("N_mu")
    plt.plot(sub.N_mu, sub.CR, 'x-', color=cols[i],
             label=f"$k=|V|$={kv}" if j == 0 else None)

plt.xlabel("$N_\\mu$")
plt.ylabel("Competitive Ratio")
plt.legend(title="$k=|V|$")
plt.savefig("rhon_xNmu_holdk_PC.png")
print("wrote rhon_xNmu_holdk_PC.png")
