# sequence.py
from dataclasses import dataclass
from typing import Tuple

I = int
T = int

@dataclass(frozen=True)
class Request:
  i: I
  t: T
  tmax: T

  def __post_init__(self):
    assert self.tmax >= 0
    assert 0 <= self.t <= self.tmax

@dataclass(frozen=True)
class Sequence:
  """
  Sequence state:
    S : (r_1, r_2, ..., r_t)
    t : current length / last request time
    tmax : horizon
  """
  S: Tuple[Request, ...]
  tmax: T
  t: T

  def __post_init__(self):
    assert self.tmax >= 0
    assert 0 <= self.t <= self.tmax
    assert len(self.S) == self.t

  def add(self, i: I) -> "Sequence":
    """
    Pre-state:  (S, t)
    Post-state: (S', t') where

      t' = t + 1
      r' = (i, t', tmax)
      S' = S ⊕ (r',)

    Here ⊕ is tuple concatenation.
    """
    t1 = self.t + 1
    assert t1 <= self.tmax
    r1 = Request(i=i, t=t1, tmax=self.tmax)
    return Sequence(S=self.S + (r1,), tmax=self.tmax, t=t1)
