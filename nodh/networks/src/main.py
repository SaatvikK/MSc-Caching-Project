# main.py
from sequence import Sequence
from simulate import run_LRU, run_R_TTL
from cache import CacheState
from typing import FrozenSet, Tuple, Optional, TypeVar, Generic
from networks import CacheNetwork as CN
from policies import *
# build a sequence
seqSize = 10
seq = Sequence(tuple(), seqSize, 0)

seq = seq.add(1)
seq = seq.add(2)
seq = seq.add(1)
seq = seq.add(3)
seq = seq.add(23)
seq = seq.add(2)


## Construct cache networks
T = int
cacheSize = 2
cs = CacheState[T](t = 0, C = frozenset(), size = cacheSize, policy = policyLRU, polName = "lru")

### Line of Caches (2):
lineStates = {
  0: cs,
  1: cs
}
lineTopology = {
  "root": 0,
  0: [1],
  1: []
}

### Tree topology where root has 2 children.
treeStates = {
  0: cs,
  1: cs,
  2: cs
}

treeTopology = {
  "root": 0,
  0: [1,2],
  1: [],
  2: [],
}


net = CN(N = treeTopology, S = treeStates, t = 0)

print("Sequence t =", seq.t)
print("Requests =", seq.S)
print(" ")

# classical LRU
run_LRU(seq, net, verbose=True)

print("\n")

# TTL R-policy (no-admit on miss when full)
#run_R_TTL(seq, cache_size=4, ttl=5, verbose=True)
