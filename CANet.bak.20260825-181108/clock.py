# clock.py
from typing import Tuple, FrozenSet, TypeVar
from dataclasses import dataclass
import numpy as np

V = TypeVar("V")

@dataclass
class T:
  time: int 

@dataclass(frozen = True)
class I:
  item: int 

@dataclass
class Clock:
  t: T # current time
  tmax: T # total time
  
  def __post_init__(self):
    assert self.tmax.time >= 0
    assert 0 <= self.t.time <= self.tmax.time
  
  def step(self):
    assert self.t.time <= self.tmax.time

    if self.t.time < self.tmax.time:
        self.t.time += 1       # mutates the T object in-place
    else:
        self.t.time = np.inf

    return self.t
  
  def currentTime(self):
    return self.t.time, self.tmax.time
  