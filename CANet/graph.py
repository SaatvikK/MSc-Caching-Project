import matplotlib.pyplot as plt
import pandas as pd
import csv
import pprint as pp
import numpy as np

# 0,1,2
ks, Vns, Z_As = [], [], []
CRs = [] # 8


df = pd.read_csv("cr_sweep.csv")
#print(df)

numkvals = df["k"].nunique()
numZvals = df["Z_A"].nunique()

cols = plt.get_cmap("Blues")(np.linspace(0.35, 0.95, numkvals))

kvals = sorted(df.k.unique())
zvals = sorted(df.Z_A.unique())

for i, kval in enumerate(kvals):
  for zval in zvals:
    subdf = df[(df.k == kval) & (df.Z_A == zval)].sort_values("Vn")
    plt.plot(subdf.Vn, subdf.CR, 'x-', color=cols[i])

plt.ylabel("Competitve Ratio")
plt.xlabel("|V|")
#plt.figure()



plt.show() # only do this once, at the end