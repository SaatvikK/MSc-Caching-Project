import os
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# graph.py is at the project root
ROOT = os.path.dirname(os.path.abspath(__file__))


def _load(TYPE):
  """Load the CSV file of the requested simulation."""
  d = os.path.join(ROOT, f"rho{TYPE}")
  return d, pd.read_csv(os.path.join(d, f"{TYPE}_sim.csv"))


def graph(TYPE="A", holdvar="Vn", freevar="k"):
  """
  Main graphing function used to graph rho_A and rho_MW for x-axis = [k, |V|].

  holdvar: The variable that is fixed per curve-family. One colour and one curve per value shown.
  freevar: The x-axis variable that is free to grow.
  TYPE: The sequence ["A", "MW", "n"].
  """

  PRETTY = {"k": "k", "Vn": "|V|", "Z_A": "$Z_A$"} # for graphing

  # Assertions.
  assert holdvar in PRETTY and freevar in PRETTY, f"vars must be in {list(PRETTY)}"
  assert holdvar != freevar, "held and free variable cannot be the same"

  # Get the third variable: the one that is neither fixed nor held.
  # Do this iteratively, for each config get the variable not in the tuple
  # (holdvar, freevar)
  innervar = [v for v in ("k", "Vn", "Z_A") if v not in (holdvar, freevar)][0]

  DIR, df = _load(TYPE)

  # Sort them by size order.
  holdvals = sorted(df[holdvar].unique())
  innervals = sorted(df[innervar].unique())
  cols = plt.get_cmap("Blues")(np.linspace(0.35, 0.95, len(holdvals)))

  # Graph the data
  # First iterate through the heldvariables then the inners.
  # We create a subdataframe by only choosing values that match both the chosen `hval` and the chosen `ival`.
  # In other words, keep the free variable free. 
  plt.figure()
  for i, hval in enumerate(holdvals):
    for j, ival in enumerate(innervals):
      subdf = df[(df[holdvar] == hval) & (df[innervar] == ival)].sort_values(freevar)
      label = f"{PRETTY[holdvar]}={hval}" if j == 0 else None
      plt.plot(subdf[freevar], subdf.CR, 'x-', color=cols[i], label=label)

  plt.ylabel("Competitive Ratio")
  plt.xlabel(PRETTY[freevar])
  plt.legend(title=PRETTY[holdvar])


  # Now save the created plot.
  SHORT = {"k": "k", "Vn": "V", "Z_A": "ZA"}
  if freevar in ("k", "Vn"):
    outfile = f"rho{TYPE}_hold{SHORT[holdvar]}_PC.png"
  else:
    outfile = f"rho{TYPE}_x{SHORT[freevar]}_hold{SHORT[holdvar]}_PC.png"
  plt.savefig(os.path.join(DIR, outfile), bbox_inches="tight")
  plt.close()
  print(f"wrote {outfile}  ({freevar} on x, {holdvar} held, {innervar} inner, "
        f"{len(df)} rows)")


def graphZA(TYPE="A"):
  """
  Plots CR vs Z_A, but only for (k, |V|) configs in which k=|V| (so the diagonal).

  Has been separated from graph() because that function draws *every* (k, |V|) combination as its own line,
  which causes the same 56 lines, making the graph hard to read. 

  Only plotting the k=|V| values makes a more readable graph that maintains the same trend.
  """

  DIR, df = _load(TYPE)

  # the k = |V| values
  df = df[df.k == df.Vn]

  # The k=|V|=128 configs were skipped (a single config there costs
  # ~11 h), so that curve stops at Z_A=32 while the others run to 128 or 256.
  df = df[df.k < 128]

  kvals = sorted(df.k.unique())
  cols = plt.get_cmap("Blues")(np.linspace(0.35, 0.95, len(kvals)))

  # k=|V| so no need to iterated through both k and |V|.
  plt.figure()
  for i, kv in enumerate(kvals):
    sub = df[df.k == kv].sort_values("Z_A")
    plt.plot(sub.Z_A, sub.CR, 'x-', color=cols[i], label=f"$k=|V|$={kv}")

  plt.xlabel("$Z_A$")
  plt.ylabel("Competitive Ratio")
  # rho_A's plots take the whole space.
  # There's no convenient place inside the square for a legend, so
  # place it outside.
  if TYPE == "A":
    plt.legend(title="$k=|V|$", loc="center left", bbox_to_anchor=(1.02, 0.5),
               borderaxespad=0.0)
  else:
    plt.legend(title="$k=|V|$", loc="upper left")
  plt.savefig(os.path.join(DIR, f"rho{TYPE}_xZA_PC.png"), bbox_inches="tight")
  plt.close()
  print(f"wrote rho{TYPE}_xZA_PC.png  ({len(df)} rows, k=|V| in {kvals})")


def graphNmu(KPLOT=(2, 8, 32, 64)):
  """rho_n's CR against N_mu -- the uncompetitiveness panel.
  """

  DIR = os.path.join(ROOT, "rhon")
  df = pd.read_csv(os.path.join(DIR, "n_sim.csv"))
  df = df[df.k.isin(list(KPLOT))]

  kvals = sorted(df.k.unique())
  zvals = sorted(df.Z_A.unique())
  cols = plt.get_cmap("Blues")(np.linspace(0.35, 0.95, len(kvals)))

  # One colour per k=|V|; the Z_A curves inside a colour are unlabelled, so
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
  plt.savefig(os.path.join(DIR, "rhon_xNmu_holdk_PC.png"), bbox_inches="tight")
  plt.close()
  print(f"wrote rhon_xNmu_holdk_PC.png  ({len(df)} rows, k=|V| in {kvals})")


def findTimeIdx(timeVal: int, times: list):
  try:
    ret = times.index(timeVal)
    print("gTime: Indexed.")
    return ret
  except:
    for i in range(len(times)):
      time = times[i]
      if timeVal <= time:
        print(f"gTime: Stop value found: idx {i} with time {time}")
        if i == 0: return 0

        idist = time - timeVal
        iMinus1Dist = timeVal - times[i-1]
        print(f"gTime: distances. idist: {idist}, i-1 dist: {iMinus1Dist}")
        if idist > iMinus1Dist: return i
        else: return i - 1

def latencyGraph(LP: list, LOPT: list, timeOfRequests: list, TYPE = "A", gTime = None):
  # x-axis: time
  # y-axis: latency

  assert len(LP) > 0 and len(LOPT) > 0 and len(timeOfRequests) > 0
  assert len(LP) == len(LOPT) and len(LOPT) == len(timeOfRequests)
  assert TYPE in ["A", "MW", "n"]

  cumLP, cumLOPT = [], []

  # cumulate the frequences
  for i in range(len(timeOfRequests)):
    if i == 0:
      cumLP.append(LP[i])
      cumLOPT.append(LOPT[i])
    else:
      cumLP.append(LP[i] + cumLP[i-1])
      cumLOPT.append(LOPT[i] + cumLOPT[i-1])
  plt.plot(timeOfRequests, cumLP, label = "Latency of P")
  plt.plot(timeOfRequests, cumLOPT, label = "Latency of OPT")

  if TYPE == "n":
    LBL = r"$L^{\mathcal{O}}_{(i,\,t=%d)}$ is %d"

    plt.annotate(LBL % (0, cumLOPT[0]),
                xy=(timeOfRequests[0], cumLOPT[0]), xycoords='data',
                xytext=(35, 90), textcoords='offset points',
                arrowprops=dict(arrowstyle="-|>", color="black", lw=1, mutation_scale=10,
                                shrinkA=0, shrinkB=5, relpos=(0.5, 0.0)),
                horizontalalignment='center', verticalalignment='bottom')

    plt.annotate(LBL % (timeOfRequests[-1], cumLOPT[-1]),
                xy=(timeOfRequests[-1], cumLOPT[-1]), xycoords='data',
                xytext=(-40, 90), textcoords='offset points',
                arrowprops=dict(arrowstyle="-|>", color="black", lw=1, mutation_scale=10,
                                shrinkA=0, shrinkB=5, relpos=(0.5, 0.0)),
                horizontalalignment='center', verticalalignment='bottom')

    if gTime != None:
      idx = findTimeIdx(gTime, timeOfRequests)
      print("gtime idx", idx)
      plt.annotate(LBL % (gTime, cumLOPT[idx]),
                  xy=(timeOfRequests[idx], cumLOPT[idx]), xycoords='data',
                  xytext=(20, 90), textcoords='offset points',
                  arrowprops=dict(arrowstyle="-|>", color="black", lw=1, mutation_scale=10,
                                  shrinkA=0, shrinkB=5, relpos=(0.5, 0.0)),
                  horizontalalignment='center', verticalalignment='bottom')

  plt.xlabel("Time (Step)")
  plt.ylabel("Cumulative Latency")
  plt.legend()
  plt.savefig(f"./rho{TYPE}/{TYPE}_cumlatencies.png", bbox_inches="tight")
  print(f"Saved plot to ./rho{TYPE}/{TYPE}_cumlatencies.png")
  plt.close()
