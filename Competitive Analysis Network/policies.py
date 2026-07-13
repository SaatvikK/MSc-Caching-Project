# policies.py
from clock import V, I, T
from cache import CacheState


def TTL(cache: CacheState):
  # Entries store (item, expiry_time). An item with expiry_time <= now has
  # TTL 0 but is NOT proactively removed — it just becomes the top eviction
  # candidate the next time a slot is needed.
  if len(cache.C) < cache.size:
    return None
  return min(cache.C, key=lambda entry: entry[1])


def policy(name: str, cache: CacheState):
  policies = {
    "TTL": TTL,
  }
  assert name in policies, f"Unknown policy '{name}'. Available: {list(policies.keys())}"
  return policies[name](cache)