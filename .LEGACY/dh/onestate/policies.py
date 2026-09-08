# policies.py
from LEGACY.dh.onestate.clock import V, I, T
from LEGACY.dh.onestate.cache import CacheState


def LRU(cache: CacheState):
  if len(cache.C) < cache.size:
    return None
  return min(cache.C, key=lambda entry: entry[1])


def policy(name: str, cache: CacheState):
  policies = {
    "LRU": LRU,
  }
  assert name in policies, f"Unknown policy '{name}'. Available: {list(policies.keys())}"
  return policies[name](cache)