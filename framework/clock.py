# clock.py
from typing import Tuple, FrozenSet, TypeVar
from dataclasses import dataclass
import numpy as np


# In this file we define all the special types needed for the rest of the sim.
# Reason being is that this is the only file that *is* called but doesn't call any other file -- i.e. the only one that is absolutely
# definitely going to avoid circular import errors.

V = TypeVar("V")

@dataclass
class T:
  time: int 

@dataclass(frozen = True)
class I:
  item: int 


@dataclass
class Clock:
  """
  t is the current time -- typically initialised to 0.
  tmax is the max time the simulation will run until.
  """
  t: T # current time
  tmax: T # total time
  
  def __post_init__(self):
    assert self.tmax.time >= 0
    assert 0 <= self.t.time <= self.tmax.time

  def step(self) -> T:
    """
    Increment self.t by one, according to the below constraints.
    """
    assert self.t.time <= self.tmax.time

    if self.t.time < self.tmax.time:
        self.t.time += 1       # mutates the T object in-place
    else:
        self.t.time = np.inf

    return self.t
  
  def currentTime(self):
    return self.t.time, self.tmax.time
  