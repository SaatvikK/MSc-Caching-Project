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


df = pd.read_csv("MW_lowerbound_sweep.csv")
#print(df)

freevar = "k"
holdvar = "Vn"
numkvals = df[holdvar].nunique()
numZvals = df["Z_A"].nunique()

cols = plt.get_cmap("Blues")(np.linspace(0.35, 0.95, numkvals))

kvals = sorted(df[holdvar].unique())
zvals = sorted(df.Z_A.unique())

for i, kval in enumerate(kvals):
  for j, zval in enumerate(zvals):
    subdf = df[(df[holdvar] == kval) & (df.Z_A == zval)].sort_values(freevar)
    label = f"{"k" if holdvar == "k" else "|V|"}={kval}" if j == 0 else None
    plt.plot(subdf[freevar], subdf.CR, 'x-', color=cols[i], label=label)

plt.ylabel("Competitve Ratio")
plt.xlabel(f"{"k" if freevar == "k" else "|V|"}")
plt.legend(title=f"{"|V|" if holdvar == "Vn" else "k"}")
#plt.figure()


plt.savefig("rhoMW_holdV_PC.png")
#plt.show() # only do this once, at the end