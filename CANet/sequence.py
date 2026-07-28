# sequence.py
from dataclasses import dataclass
from typing import Tuple
from clock import V, I, T


@dataclass(frozen=True)
class Request:
  i: I
  t: T
  tmax: T

  def __post_init__(self):
    assert self.tmax.time >= 0
    assert 0 <= self.t.time <= self.tmax.time

@dataclass()
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
    assert self.tmax.time >= 0
    assert 0 <= self.t.time <= self.tmax.time

    self.nextReq = 0 # idx of next request in self.S

  def add(self, i: I, t: T = None) -> "Sequence":
    """
    Pre-state:  (S, t)
    Post-state: (S', t') where

      t' = t + 1
      r' = (i, t', tmax)
      S' = S ⊕ (r',)

    Here ⊕ is tuple concatenation.
    """
    t = self.t if t == None else t
    assert t.time <= self.tmax.time
    r1 = Request(i=I(item = i), t=t, tmax=self.tmax)
    new_seq = Sequence(S=self.S + (r1,), tmax=self.tmax, t=self.t)
    new_seq.nextReq = self.nextReq
    return new_seq

  def sendReq(self):
    out = []
    while self.nextReq < len(self.S) and self.S[self.nextReq].t.time <= self.t.time:
      out.append(self.S[self.nextReq])
      self.nextReq += 1
    return out
