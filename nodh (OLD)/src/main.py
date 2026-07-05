# main.py
from sequence import Sequence
from simulate import run_LRU, run_R_TTL

# build a sequence
seqSize = 10
seq = Sequence(tuple(), seqSize, 0)

seq = seq.add(1)
seq = seq.add(2)
seq = seq.add(1)
seq = seq.add(3)
seq = seq.add(23)
seq = seq.add(2)

print("Sequence t =", seq.t)
print("Requests =", seq.S)
print(" ")

# classical LRU
run_LRU(seq, cache_size=4, verbose=True)

print("\n")

# TTL R-policy (no-admit on miss when full)
run_R_TTL(seq, cache_size=4, ttl=5, verbose=True)
