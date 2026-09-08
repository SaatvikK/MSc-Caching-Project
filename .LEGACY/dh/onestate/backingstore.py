from typing import Tuple, FrozenSet, TypeVar
from dataclasses import dataclass
from LEGACY.dh.onestate.sequence import Sequence, Request
from LEGACY.dh.onestate.clock import V, I, T, Clock
import numpy as np

@dataclass
class BackingStore:
  items: I 
  t: T
  Z_B: int

  def recvFetch(self, rj: Request):
    # Call this method every step
    if self.t.time - rj.t.time == self.Z_B:
      return rj.i
    return None