# policies.py
from clock import V, I, T
from cache import CacheState


def TTL(cache: CacheState):
  if len(cache.C) < cache.size:
    return None
  return min(cache.C, key=lambda entry: (entry[1], entry[0].item))


def policy(name: str, cache: CacheState):
  policies = {
    "TTL": TTL,
  }
  assert name in policies, f"Unknown policy '{name}'. Available: {list(policies.keys())}"
  return policies[name](cache)