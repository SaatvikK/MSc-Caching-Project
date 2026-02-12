# policies.py
from typing import Tuple, FrozenSet
from cache import CacheState, I, T

# ---------- Classical LRU (value = last_access_time) ----------

def argminTimeStamp(C: FrozenSet[Tuple[I, T]]) -> Tuple[I, T]:
  # returns (i, ts) with minimal ts
  return min(C, key=lambda x: x[1])

def policyLRU(C_t: CacheState[T], r_i: I, r_t: T, ttl = None) -> Tuple[bool, CacheState[T]]:
  """
  δ_LRU(C_t, r_t) = (hit, C_{t+1})

  Representation: entries are (i, last_access_time).

  Semantics:
    - Hit:  replace (i, old_ts) with (i, r_t)
    - Miss:
        if |C| < k: insert (i, r_t)
        else: evict LRU (min timestamp), then insert
  """
  assert r_t == C_t.t + 1

  old = C_t.get(r_i)
  if old is not None:
    # hit: update timestamp
    C_t1 = C_t.replace(old, (r_i, r_t))
    return True, C_t1

  # miss:
  if len(C_t.C) < C_t.size:
    C_t1 = C_t.replace(None, (r_i, r_t))
    return False, C_t1

  victim = argminTimeStamp(C_t.C)
  C_t1 = C_t.replace(victim, (r_i, r_t))
  return False, C_t1


# ---------- TTL "R-policy" (value = remaining_ttl) ----------
# From Florin paper

def policyRTTL(C_t: CacheState[T], r_i: I, r_t: T, ttl: T) -> Tuple[bool, CacheState[T]]:
  """
  δ_R(C_t, r_t) = (hit, C_{t+1})

  Representation: entries are (i, θ) where θ is remaining TTL in *request-steps*.

  We use "expire before serving request" semantics:

    Expiry step:
      C̄ = {(j, θ-1) : (j,θ) ∈ C_t.C, θ-1 > 0}

    Then:
      if (r_i ∈ items(C̄)): hit and reset its TTL to ttl
      else: miss and admit ONLY if |C̄| < k (your current rule)

  Time:
    output state is at time t+1 (i.e. r_t).
  """
  assert ttl > 0
  assert r_t == C_t.t + 1

  # (1) expiry / decrement at time-step
  Cbar = frozenset((j, th - 1) for (j, th) in C_t.C if th - 1 > 0)

  # build intermediate state at same t (still pre-time-increment)
  C_mid = CacheState(t=C_t.t, C=Cbar, size=C_t.size)

  # (2) classify after expiry
  old = C_mid.get(r_i)
  if old is not None:
    # hit: reset TTL
    C_t1 = C_mid.replace(old, (r_i, ttl))
    return True, C_t1

  # miss: admit iff space
  if len(C_mid.C) < C_mid.size:
    C_t1 = C_mid.replace(None, (r_i, ttl))
    return False, C_t1

  # miss + full: no-admit
  C_t1 = C_mid.replace(None, None)  # just advance time
  return False, C_t1