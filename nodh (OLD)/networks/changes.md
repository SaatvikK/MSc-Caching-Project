- `cache.py/CacheState` now changed to `CacheNode`. Has extra properties:
  - root: signifies if the node is the root in the network
  - leaf: signifies if the node is a leaf in the network.
  - Each cache now has a specific policy associated with it.
  