from framework.clock import V, I, T, Clock
from framework.network import CacheNetwork
import random as rand 
from framework.sequence import Sequence as Seq
from framework.policies import TTL

# SIMULATE SEQUENCES WITH LCE -------------------------------------------------------


def appendBurst(seq, item, startTime, Z_B):
  """Append a bursty request (null^Z_B, item^Z_B, null^Z_B)"""
  startTime += Z_B ## add the initial Z_B of no requests
  for j in range(Z_B):
    seq = seq.add(item, T(time=startTime + j))
  
  startTime += Z_B*2 # then increase the time once, to account for the Z_B items
  # and then again, to account for the final Z_B wait of no requests.
  return seq, startTime

def appendPure(seq, item, startTime, Z_B):
  """Append a bursty request (null^Z_B, item, null^Z_B)"""
  startTime += Z_B ## add the initial Z_B of no requests
  seq = seq.add(item, T(time=startTime))
  
  startTime += Z_B + 1 # then increase the time once, to account for the Z_B items
  # and then again, to account for the final Z_B wait of no requests.
  return seq, startTime


# SIMULATE SEQUENCES WITH OPT -------------------------------------------------------

# The optSimulate function below uses the sequences that were fully constructed
# in the LCE simulations in order to find the latency that OPT incurs.
# Unlike the functions in sequenceBuild.py, this function never modify the sequence in anyway,
# as the adversary response to the *online* policy's behaviour and tries to 'work *with* OPT' --
# attempting to give it every opportunity to incur minimal/low latency. 

def optSimulate(net, seq, cpp, leaf=0, policyName="TTL", trackItem=None):
  latencies = []
  # A list of lists that keeps track of every request, its location, 
  # its ingress cache, and its latency, that is currently in the network.
  # Qreq[i] = [
  #   [0]: Request # the request object itself
  #   [1]: int # the CURRENT vertex number (net.M[Qreq[i][1]] --> the cache state object for that vertex)
  #   [2]: int # the origin leaf, as a bove
  #   [3]: int # the time that it arrived at vertex [1]
  #   [4]: int # the accumulated latency thus far
  # ]
  Qreq = []
  clk = net.clk

  # rho_n only: the step at which trackItem (g) first hits at v0. mu is the only
  # part of the sequence that re-requests g, so this is where phi ends.
  trackTime = None

  # Stop the sim by default when the clock time exceeds the prescribed max time.
  while clk.t.time < clk.tmax.time:
    # Each iteration always starts by stepping.
    # As explained in Section 6.1, this is the **only** place were a clock or time is manually 
    # updated.
    clk.step()

    seq, Qreq, latencies, stop, trackTime = processRequest(seq, Qreq, leaf, clk, net, latencies, policyName, cpp, trackItem, trackTime)
    if stop == True: break

  return latencies + net.dhLatencies, trackTime


# SIMULATE SEQUENCES WITH LCE -------------------------------------------------------

# NOTE: A lot of the structure of these functions w.r.t. the way requests are processed in a
# network are the same here as in optSimulate or processRequest.
# Since that function already explains the request-network process indepthly,
# only the mechanisms behind dynamically appending requests to the sequence will be
# explained here.

def simulateAdversarial(net, seq, W_items, Z_B, leaf=0, policyName="TTL"):
  """
  net: Network
  seq: Sequence
  W_item: set
  Z_B: int
  leaf: int

  Drives the LCE network, under the prescribed configurations, usinig the initial part 
  of the sequence created before (`seq0`). Then, based on the network/LCE's response to
  the sequence thus far, it dynamically appends new requests onto the end until the criteria
  for a rho_A sequence has been fulfilled, as outlined in the dissertation.

  Returns then the full sequence, and the latency of LCE.
  """

  latencies = []
  Qreq = []  # [req, current_v, origin_leaf, t_arrived, latency]
  clk = net.clk

  # rho_A makes one pure request (which is already in seq), and then exactly
  # |W| bursty requests such that every w in W is requested once.
  usedItems = set() # use this to keep track of which elems in W have already been requested.
  burstsDone = 0
  maxBursts = len(W_items)

  # First burst starts right after the initial fetch resolves
  # Tracks when the next burst should start.
  burstCursor = 2

  while clk.t.time < clk.tmax.time:
    clk.step()

    # Scheduling must happen AFTER clk.step() (i.e. using the tick that
    # sendReq() is about to check against), not before.

    ##### Sequence modification----------------------
    if burstsDone < maxBursts and clk.t.time >= burstCursor:
      present = net.getItems()
      candidates = [w for w in W_items if w not in present and w not in usedItems]
      assert candidates, (
        f"no unused item in W={W_items} absent from network at "
        f"t={clk.t.time}; adversarial construction assumption violated"
      )
      item = candidates[0]
      usedItems.add(item)
      seq, burstCursor = appendBurst(seq, item, burstCursor, Z_B)
      burstsDone += 1

    ##### Request processing---------------
    seq, Qreq, latencies, stop, _ = processRequest(seq, Qreq, leaf, clk, net, latencies, policyName)
    # stop identifies whether the sequence is over, the second clause 
    # signifies that there are no more requests that need to be added 
    # (i.e. the construction process is over)
    if stop == True and burstsDone >= maxBursts: break

  return latencies + net.dhLatencies, seq

def simulateManoharWilliams(net, ISize, Z_B, k, leaf=0, policyName="TTL"):
  latencies = []
  Qreq = []  # [req, current_v, origin_leaf, t_arrived, latency]
  clk = net.clk

  burstsDone = 0
  burstCursor = 2*Z_B+1  # first burst starts right after the initial fetch resolves

  # add initial pure request: (0^Z_B, i, 0^Z_B)
  N_0 = {i.item for i in net.getItems()}
  universe = { i for i in range(ISize + 1)} 
  notin = universe - N_0
  initItem = rand.sample(sorted(notin), 1)[0]  # 3.11+ removed sampling from a set
  seq = Seq((), tmax=clk.tmax, t=clk.t)
  seq = seq.add(initItem, T(time = Z_B))

  while clk.t.time < clk.tmax.time:
    clk.step()

    # Scheduling must happen AFTER clk.step() (i.e. using the tick that
    # sendReq() is about to check against), not before.
    if burstsDone < k and clk.t.time >= burstCursor:
      present = {i.item for i in net.getItems()}
      notin = universe - present

      assert notin, (  # not `assert candidate`: item 0 is valid but falsy
        f"no unused item in I absent from network at "
        f"t={clk.t.time}; adversarial construction assumption violated"
      )
      candidate = rand.sample(sorted(notin), 1)[0]

      seq, burstCursor = appendBurst(seq, candidate, burstCursor, Z_B)
      burstsDone += 1

    ##### Request processing---------------
    seq, Qreq, latencies, stop, _ = processRequest(seq, Qreq, leaf, clk, net, latencies, policyName)
    # stop identifies whether the sequence is over, the second clause 
    # signifies that there are no more requests that need to be added 
    # (i.e. the construction process is over)
    if stop == True and burstsDone >= k: break

  return latencies + net.dhLatencies, seq

def simulateRhon(net, Nmu, ISize, Z_B, k, leaf=0, policyName="TTL"):
  latencies = []
  Qreq = []  # [req, current_v, origin_leaf, t_arrived, latency]
  clk = net.clk

  def getItemNotIn():
    N_0 = {i.item for i in net.getItems()}
    universe = {i for i in range(ISize + 1)}
    notin = universe - N_0
    assert notin, f"no item of I outside the network at t={clk.t.time}"
    return sorted(notin)[0]  # 3.11+ removed sampling from a set

  # the opening pure request (0^Z_B, g, 0^Z_B) leaves g in every cache
  target = getItemNotIn()
  seq = Seq((), tmax=clk.tmax, t=clk.t)
  seq, cursor = appendPure(seq, target, clk.t.time, Z_B)

  vi = 0                          # cache phi is currently evicting g from
  lastCache = len(net.G[0]) - 1   # g is left here, so mu's hits cost d * Z_A
  muReqsDone = 0

  while clk.t.time < clk.tmax.time:
    clk.step()

    # Scheduling must happen AFTER clk.step() (i.e. using the tick that
    # sendReq() is about to check against), not before.
    if clk.t.time >= cursor:
      if vi < lastCache:
        cache = net.M[vi]
        victim = TTL(cache)
        if victim is not None and victim[0].item == target:
          seq, cursor = appendPure(seq, getItemNotIn(), cursor, Z_B)
          vi += 1
        else:
          # only items absent from every shallower cache actually reach vi
          shallower = {i.item for n in range(vi) for (i, _) in net.M[n].C}
          items = sorted(i.item for i in cache.getall()
                         if i.item != target and i.item not in shallower)
          assert items, (
            f"nothing at v{vi} can be refreshed at t={clk.t.time}: every "
            f"entry besides {target} is shadowed by a shallower cache"
          )
          seq, cursor = appendPure(seq, rand.choice(items), cursor, Z_B)
      elif muReqsDone < Nmu:
        seq = seq.add(target, T(time=clk.t.time))
        cursor = clk.t.time + 1
        muReqsDone += 1

    ##### Request processing---------------
    seq, Qreq, latencies, stop, _ = processRequest(seq, Qreq, leaf, clk, net, latencies, policyName)
    # stop identifies whether the sequence is over, the second clause 
    # signifies that there are no more requests that need to be added 
    # (i.e. the construction process is over)
    if stop == True and (vi >= lastCache and muReqsDone >= Nmu): break

  return latencies + net.dhLatencies, seq

def processRequest(
    seq: Seq, Qreq: list, 
    leaf: int, clk: Clock, 
    net: CacheNetwork, 
    latencies: list, 
    policyName: str, 
    cpp: str = "lce",
    trackItem = None,
    trackTime = None
  ):

  
  # Send the next request to v0 down the QReq pipeline.
  req = seq.sendReq()
  if req is not None:
    Qreq.append([req, leaf, leaf, clk.t.time, 0])

  toRmv = []

  # At each step we iterate through the requests currently working their way
  # through the network, and deal with each in turn.
  for i in range(len(Qreq)):
    reqT = Qreq[i]

    # If the request's current vertex *is not* its the ingress and if the current time minus
    # the latency incurred by the request thus far is *less* than the inter-cache delay parameter,
    # skip to the next request 
    # This basically means: If the cache has not reached the next vertex yet (it takes Z_A timesteps)
    # then just go to the next request and check again next step.
    if reqT[1] != reqT[2] and clk.t.time - reqT[3] < net.Z_A:
      continue

    # Drive the request one cache further through the network.
    # Returns the status (one of ["hit", "miss", "delayed hit"]), and the next cache to which the 
    # request is sent.
    _, stat, vNext = net.forward(reqT[0], reqT[1])

    if stat == 2: #hit
      if trackItem is not None and trackTime is None and reqT[0].i == trackItem:
        trackTime = clk.t.time

      # add the NZLH-incurred latency to the list
      latencies.append(reqT[4])
      toRmv.append(i) # then slate the item for removal from Qreq.
      path = [n for n in net.pathTo(reqT[2], "b") if n != "b"] # construct its path from ingress to hit-cache.
      item = reqT[0].i

      # Using the constructed path, iteratively remove every queued request for the same item
      # at each cache
      # these are delayed hits. 
      for node in path:
        if item in net.QFetch[node]:
          net.QFetch[node].remove(item)
          _, dhs = net.resolve(item, node)
          net.dhCount += dhs
          
    elif stat == 1: # DH
      toRmv.append(i)
    
    elif stat == "b": # a full network-miss

      # invoke the CPP with the item, the ingress vector, the eviction policy, and the cpp.
      net.cpp(reqT[0].i, reqT[2], policyName, cpp=cpp, seq=seq)
      latencies.append(reqT[4])
      toRmv.append(i)

    elif stat == 0: # node miss
      Qreq[i][1] = vNext
      Qreq[i][3] = clk.t.time
      Qreq[i][4] += net.Z_A

  # Remove all items that were slated for removal during this step.
  for i in reversed(toRmv):
    Qreq.pop(i)

  # If there are no more requests then stop.
  if req is None and not Qreq and seq.nextReq >= len(seq.S):
    stop = True
  else:
    stop = False

  return seq, Qreq, latencies, stop, trackTime