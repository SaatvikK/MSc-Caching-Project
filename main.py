import framework as frmwk 
import simulations as sims
import graph
import numpy as np
import pathlib as pl
import json
import os

# WARNING WARNING WARNING WARNING WARNING WARNING 
# RUNNING THIS SCRIPT ON LINE 68 **WILL** 
# RESULT IN THE ~40 HOUR REAL SIMULATION RESULTS 
# BEING OVERWRITTEN IMMEDIATELY BACK UP EXISTS AT 
# `/REALRESULTS_BACKUP/`.
# WARNING WARNING WARNING WARNING WARNING WARNING 






# the simulations that the simulation will
# run through
# A = rho_A
# MW = rho_MW
# n = {rho_n}
# Add or remove any sequences as desired.
SEQS = ["A", "MW", "n"]

# If you'd like to test the simulation(s), use
# this showcase conflict
# It takes approximately 1.6 seconds and 1 second to
# run for rhoA and rhoMW, respectively
# rho_n will take ~26 seconds.
def showcase(seq = "A"):
  if seq == "A" or seq == "MW":
    krange = 2 ** np.arange(5)          # 1,2,4,8,16,32
    Vrange = 2 ** np.arange(1, 5)       # 2,4,8,16
    Z_Arange = 2 ** np.arange(6)        # 1,2,4,8,16,32
    Nmurange = np.array([1])            # only rho_n has a mu phase 
  else:
    krange = 2 ** np.arange(1, 4)       # 2,4,8
    Vrange = 2 ** np.arange(1, 4)       # 2,4,8
    Z_Arange = 4 ** np.arange(3)        # 1,2,4,16
    Nmurange = 2 ** np.arange(10, 16)   # 1024,2048,4096,8192,16384,32768

  return krange, Vrange, Z_Arange, Nmurange

latsLCE = {"A": [], "MW": [], "n": []}
latsOPT = {"A": [], "MW": [], "n": []}
reqtimes = {"A": [], "MW": [], "n": []}
gTimes = {"A": 0, "MW": 0, "n": 0}
# Run the simulations
for seq_ in SEQS:
  # .run() writes directly to csvs:
  # ./rho{TYPE}/rho{TYPE}_sim.csv
  # It returns the raw latencies for each policy.

  # .run() executes by first iterating
  # over all Nmu-values (if sim is for {rho_n}),
  # then all k-values, then |V|-values, then
  # Z_A-values
  # However, the Nmu iteration is trivial (usually set to a max of 1)
  # unless the simulation is for the {rho_n} sequence family.

  # IT SHOULD BE NOTED THAT the full default ranges
  # for all three sequences takes a total of ~40 hours to 
  # complete.
  lce, opt, times, thisgtime = sims.runner.runsim(TYPE = seq_, showcase = showcase) ## do showcase = None or showcase (note: not showcase() just showcase)
  latsLCE[seq_] = lce
  latsOPT[seq_] = opt
  reqtimes[seq_] = times
  gTimes[seq_] = thisgtime

  with open(f"rho{seq_}/{seq_}_latencies.json", "w") as f:
    json.dump({"LCE": lce, "OPT": opt, "times": times, "gTime": thisgtime}, f)
  print(f"Saved latencies to ./rho{seq_}/{seq_}_latencies.json")


# Now check that the csvs exist
for seq_ in SEQS:
  path = pl.Path(f"rho{seq_}/{seq_}_sim.csv")
  print(f"Checking for rho_{seq_}'s simulation results...{"FOUND" if path.exists() else "MISSING"}")
  if not path.exists(): 
    os._exit(1)
# Call the graphing function 
# (which will read the csvs, parse, and build the graphs)

for seq_ in SEQS:
  print(f"seq: {seq_}, gTime: {gTimes[seq_]}")
  if seq_ != "n":
    graph.graph(TYPE = seq_, holdvar = "Vn", freevar = "k")
    graph.graph(TYPE = seq_, holdvar = "k", freevar = "Vn")

    # then do for Z_A
    graph.graphZA(TYPE = seq_)

    # then do the latency graph
    graph.latencyGraph(latsLCE[seq_], latsOPT[seq_], reqtimes[seq_], TYPE = seq_, gTime = gTimes[seq_])
  else:
    graph.graphNmu()
    # then do the latency graph
    graph.latencyGraph(latsLCE["n"], latsOPT["n"], reqtimes["n"], TYPE = "n", gTime = gTimes["n"])
    idx = graph.findTimeIdx(gTimes["n"], reqtimes["n"])
    phiLatLCE = sum(latsLCE["n"][:idx])
    muLatLCE = sum(latsLCE["n"][idx:])
    phiLatOPT = sum(latsOPT["n"][:idx])
    muLatOPT = sum(latsOPT["n"][idx:])
    print(f"In the phi-subsequence, LCE incurred latency {phiLatLCE}, where as OPT incurred {phiLatOPT}.")
    print(f"In the mu-subsequence, OPT incurred latency {muLatLCE}, where as OPT incurred {muLatOPT}.")
# graphs are stored in /rho{TYPE}/

