from clock import V, I, T, Clock
from network import CacheNetwork
import random as rand 
from sequence import Sequence as Seq

def aOptSimulate(net, seq, cpp, leaf=0, policyName="TTL"):
  """Pure replay of an ALREADY-FINALISED sequence (no live decisions)
  through `net` using the given cpp ('lce' or 'opt'). Caller must reset
  seq.nextReq = 0 before calling this a second time on the same Sequence
  object."""
  latencies = []
  Qreq = []
  clk = net.clk

  while clk.t.time < clk.tmax.time:
    clk.step()

    req = seq.sendReq()
    if req is not None:
      Qreq.append([req, leaf, leaf, clk.t.time, 0])

    to_remove = []
    for i in range(len(Qreq)):
      reqT = Qreq[i]
      if reqT[1] != reqT[2] and clk.t.time - reqT[3] < net.Z_A:
        continue

      _, stat, vNext = net.forward(reqT[0], reqT[1])

      if stat == 2: #hit
        latencies.append(reqT[4])
        to_remove.append(i)


        path = [n for n in net.pathTo(reqT[2], "b") if n != "b"]
        item = reqT[0].i
        for node in path:
          if item in net.QFetch[node]:
            net.QFetch[node].remove(item)
            _, dhs = net.resolve(item, node)
            net.dhCount += dhs
            
      elif stat == 1: # DH
        to_remove.append(i)
      elif stat == "b":
        net.cpp(reqT[0].i, reqT[2], policyName, cpp=cpp)
        latencies.append(reqT[4])
        to_remove.append(i)
      elif stat == 0: # node miss
        Qreq[i][1] = vNext
        Qreq[i][3] = clk.t.time
        Qreq[i][4] += net.Z_A

    for i in reversed(to_remove):
      Qreq.pop(i)

    if req is None and not Qreq and seq.nextReq >= len(seq.S):
      break

  return latencies + net.dhLatencies


def mwOptSimulate(net, seq, cpp, leaf=0, policyName="TTL", UNIVERSE_SIZE = 6):
  """Pure replay of an ALREADY-FINALISED sequence (no live decisions)
  through `net` using the given cpp ('lce' or 'opt'). Caller must reset
  seq.nextReq = 0 before calling this a second time on the same Sequence
  object."""
  latencies = []
  Qreq = []
  clk = net.clk

  while clk.t.time < clk.tmax.time:
    clk.step()

    req = seq.sendReq()
    if req is not None:
      Qreq.append([req, leaf, leaf, clk.t.time, 0])

    to_remove = []
    for i in range(len(Qreq)):
      reqT = Qreq[i]
      if reqT[1] != reqT[2] and clk.t.time - reqT[3] < net.Z_A:
        continue

      _, stat, vNext = net.forward(reqT[0], reqT[1])

      if stat == 2: #hit
        latencies.append(reqT[4])
        to_remove.append(i)


        path = [n for n in net.pathTo(reqT[2], "b") if n != "b"]
        item = reqT[0].i
        for node in path:
          if item in net.QFetch[node]:
            net.QFetch[node].remove(item)
            _, dhs = net.resolve(item, node)
            net.dhCount += dhs
            
      elif stat == 1: # DH
        to_remove.append(i)
      elif stat == "b":
        net.cpp(reqT[0].i, reqT[2], policyName, cpp=cpp, seq=seq)
        latencies.append(reqT[4])
        to_remove.append(i)

      elif stat == 0: # node miss
        Qreq[i][1] = vNext
        Qreq[i][3] = clk.t.time
        Qreq[i][4] += net.Z_A

    for i in reversed(to_remove):
      Qreq.pop(i)

    if req is None and not Qreq and seq.nextReq >= len(seq.S):
      break

  return latencies + net.dhLatencies
