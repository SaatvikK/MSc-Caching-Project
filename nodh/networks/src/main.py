# main.py
from sequence import Sequence
from simulate import run_LRU, run_R_TTL
from cache import CacheNode
from typing import FrozenSet, Tuple, Optional, TypeVar, Generic
from networks import CacheNetwork as CN
from policies import policyLRU, policyRTTL

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
ttl = 5

lruCache = CacheNode[T](t=0, C=frozenset(), size=cacheSize, policy=policyLRU, polName="lru", root=False, leaf=False)
ttlPolicy = lambda C_t, i, t: policyRTTL(C_t, i, t, ttl)
ttlCache = CacheNode[T](t=0, C=frozenset(), size=cacheSize, policy=ttlPolicy, polName="rttl", root=False, leaf=False)

### Line of Caches (2): LRU
lineStates = {
  0: CacheNode[T](t=0, C=frozenset(), size=cacheSize, policy=policyLRU, polName="lru", root=True,  leaf=False),
  1: CacheNode[T](t=0, C=frozenset(), size=cacheSize, policy=policyLRU, polName="lru", root=False, leaf=True),
}
lineTopology = {
  "root": 0,
  0: [1],
  1: []
}

### Tree topology where root has 2 children: LRU
treeStates = {
  0: CacheNode[T](t=0, C=frozenset(), size=cacheSize, policy=policyLRU, polName="lru", root=True,  leaf=False),
  1: CacheNode[T](t=0, C=frozenset(), size=cacheSize, policy=policyLRU, polName="lru", root=False, leaf=True),
  2: CacheNode[T](t=0, C=frozenset(), size=cacheSize, policy=policyLRU, polName="lru", root=False, leaf=True),
}
treeTopology = {
  "root": 0,
  0: [1, 2],
  1: [],
  2: [],
}

### Line of Caches (2): TTL
ttlLineStates = {
  0: CacheNode[T](t=0, C=frozenset(), size=cacheSize, policy=ttlPolicy, polName="rttl", root=True,  leaf=False),
  1: CacheNode[T](t=0, C=frozenset(), size=cacheSize, policy=ttlPolicy, polName="rttl", root=False, leaf=True),
}


lruNet = CN(N=treeTopology, S=treeStates, t=0)
ttlNet = CN(N=lineTopology, S=ttlLineStates, t=0)

print("Sequence t =", seq.t)
print("Requests =", seq.S)
print(" ")

# classical LRU
run_LRU(seq, lruNet, verbose=True)

print("\n")

# TTL R-policy
run_R_TTL(seq, ttlNet, verbose=True)
