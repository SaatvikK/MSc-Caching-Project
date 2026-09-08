"""Simulation drivers: the sequences of Chapter 5 run against the framework.

  sequenceBuild   builds each adversarial sequence live against LCE, since every
                  request depends on the eviction state the previous ones left
                  (Sec 6.1.3), and returns the finalised sequence; `optSimulate`
                  then replays that finalised sequence against a network running
                  the corresponding O instance. Both drive the same
                  `processRequest` pipeline -- the O side differs only in the CPP
                  it names.
  runner          the driver: sweeps (k, |V|, Z_A[, N_mu]) and writes
                  {TYPE}_sim.csv
"""

from simulations import sequenceBuild
from simulations import runner

__all__ = ["sequenceBuild", "runner"]
