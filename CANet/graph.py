import sys
import matplotlib
matplotlib.use("Agg")  # no display under WSL2; Qt backend aborts on import
import matplotlib.pyplot as plt
import pandas as pd
import csv
import pprint as pp
import numpy as np

# 0,1,2
ks, Vns, Z_As = [], [], []
CRs = [] # 8


# usage: python graph.py [A|MW] [holdvar] [freevar]
#   holdvar -- the HELD variable: one colour + one legend entry per value
#   freevar -- the variable on the x axis (default: k if Vn is held, else Vn)
# The remaining third variable is drawn as extra unlabelled lines in the same
# colour, so each colour is a family of curves rather than a single curve.
TYPE    = sys.argv[1] if len(sys.argv) > 1 else "MW"
holdvar = sys.argv[2] if len(sys.argv) > 2 else "Vn"
freevar = sys.argv[3] if len(sys.argv) > 3 else ("k" if holdvar == "Vn" else "Vn")

PRETTY = {"k": "k", "Vn": "|V|", "Z_A": "$Z_A$"}
assert holdvar in PRETTY and freevar in PRETTY, f"vars must be in {list(PRETTY)}"
assert holdvar != freevar, "held and free variable cannot be the same"
innervar = [v for v in ("k", "Vn", "Z_A") if v not in (holdvar, freevar)][0]

df = pd.read_csv(f"{TYPE}_lowerbound_sweep.csv")
#print(df)

holdvals = sorted(df[holdvar].unique())
innervals = sorted(df[innervar].unique())

cols = plt.get_cmap("Blues")(np.linspace(0.35, 0.95, len(holdvals)))

for i, hval in enumerate(holdvals):
  for j, ival in enumerate(innervals):
    subdf = df[(df[holdvar] == hval) & (df[innervar] == ival)].sort_values(freevar)
    label = f"{PRETTY[holdvar]}={hval}" if j == 0 else None
    plt.plot(subdf[freevar], subdf.CR, 'x-', color=cols[i], label=label)

plt.ylabel("Competitve Ratio")
plt.xlabel(PRETTY[freevar])
plt.legend(title=PRETTY[holdvar])
#plt.figure()


# Keep the original names for the k/|V| x-axis plots; tag the others by x var.
SHORT = {"k": "k", "Vn": "V", "Z_A": "ZA"}
if freevar in ("k", "Vn"):
  outfile = f"rho{TYPE}_hold{SHORT[holdvar]}_PC.png"
else:
  outfile = f"rho{TYPE}_x{SHORT[freevar]}_hold{SHORT[holdvar]}_PC.png"
plt.savefig(outfile)
print(f"wrote {outfile}  ({freevar} on x, {holdvar} held, {innervar} inner, {len(df)} rows)")
#plt.show() # only do this once, at the end
