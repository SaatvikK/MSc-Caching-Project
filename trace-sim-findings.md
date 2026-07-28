# Trace-driven simulation: findings

Notes on why `trace sim.py` returns no latencies, and on how to map the
`cache-u-00` trace onto the model's time axis.

---

## 1. Why `latencies` stays empty

`simulate()` only appends to `latencies` from inside the `Qreq` loop, and `Qreq`
is only ever filled when `seq.sendReq()` returns non-`None`. It never does.
Three things combine.

### 1a. Dispatch is an exact equality test on the head request only

`sequence.py:53-60`:

```python
def sendReq(self):
    if self.nextReq >= len(self.S):
        return None
    req = self.S[self.nextReq]
    if self.t.time == req.t.time:
        self.nextReq += 1
        return req
    return None
```

`nextReq` advances *only* on an exact time match. If the clock ever passes
`S[nextReq].t.time` without landing on it exactly, that request blocks the head
of the queue permanently, `nextReq` freezes at that index for the rest of the
run, and every later request becomes unreachable.

### 1b. The clock is stepped before the first `sendReq()`

`trace sim.py:75-80`:

```python
while clk.t.time < clk.tmax.time:
    clk.step()            # t is already 1 here
    ...
    req = seq.sendReq()   # first check ever made happens at t == 1
```

`Clock` starts at `t=0` and `step()` increments *before* anything reads it, so
`t=0` is never observed. The trace's first rows are all at `time=0`:

```
time,req,item,respTime
0,0,0,0.000165
0,1,1,0.00017
0,2,1,0.441594
0,3,0,0.00019
```

`S[0]` (t=0) is therefore missed on tick 1 and blocks forever. `sendReq()`
returns `None` for the whole simulation, `Qreq` stays empty, `latencies` stays
empty, `sum(latsLCE) == 0`.

### 1c. Even with the off-by-one fixed, it stalls one tick later

`sendReq()` returns at most **one** request per tick, but the trace has ~1,300
requests sharing each timestamp. At `t=0` you would emit row 0, the clock moves
to 1, and `S[1]` — still stamped 0 — blocks forever. Same outcome.

The single-request-per-tick dispatch is *faithful to the formalism* (see §2); it
is the trace that violates it.

### Consequences

- The early-exit at `trace sim.py:119-120` needs `seq.nextReq >= len(seq.S)`,
  which is never true, so the loop grinds through every tick up to `tmax` doing
  nothing but printing clock progress.
- `net.dhLatencies` is empty for the same reason, so the returned
  `latencies + net.dhLatencies` is `[]`.

### Fix

`sendReq` needs to be a drain-loop rather than a single equality check — pop
*all* requests with `t.time <= clk.t.time` so late and duplicate timestamps are
flushed rather than blocking:

```python
def sendReqs(self):
    out = []
    while self.nextReq < len(self.S) and self.S[self.nextReq].t.time <= self.t.time:
        out.append(self.S[self.nextReq])
        self.nextReq += 1
    return out
```

with `simulate` appending one `Qreq` entry per returned request. Moving
`clk.step()` to the **end** of the while body fixes the off-by-one, but on its
own is not sufficient — 1c is what actually kills a real trace.

Not needed if the trace is re-indexed so that exactly one request lands per tick
(§2), in which case the existing `sendReq` works unmodified.

---

## 2. Time axis: one request per tick

The model's arrival process is strictly one request per timestep. This is a
property of the formalism, not an artifact of the simulator:

- `sequence.py:35-51` — `add` documents `t' = t + 1`, i.e. request index *is*
  time.
- `LB sim.py` — `appendBurst` emits `seq.add(item, T(time=startTime + j))`, one
  request per tick.

Note this constrains **arrivals** only. In-flight requests are not serialised:
`Qreq` holds arbitrarily many concurrently, and `QFetch` / `QResolve` /
`dhLatencies` (`network.py:114-138`) exist precisely to handle a second request
arriving for an item whose fetch is still outstanding — the delayed-hit
mechanism.

The trace has 1-second granularity and ~1,323 requests/second, so it does not
satisfy the one-per-tick property as-is. Two ways to reconcile.

### Option A — re-index: tick = arrival index

Assign tick *n* to the *n*-th request in file order. This is literally what
`Sequence.add` already says (`t' = t+1`), keeps every request, preserves order,
and needs no change to `sendReq`.

Cost: a units change to state in the report. `Z_A` and `ttl` become *request
arrivals*, not seconds. At 1,323 req/s, `Z_A = 1` tick ≈ **0.76 ms**, so the
current sweep `Z_Arange = 2 ** np.arange(3)` spans sub-4ms link delays.

### Option B — dedup: keep one request per second

Keeps tick = 1 real second, so `Z_A` and `ttl` are in seconds and directly
comparable to `respTime`, and latency totals are wall-clock meaningful. Over the
full file this yields exactly 86,400 requests spanning `t = 0..86399` — one per
tick, so `TMAX_VAL = 86399` is correct and the existing `sendReq` works with
zero code changes.

Cost: it is a 1:1323 downsample. See §4 for what that does to the measurement.

### Trade-off

|  | Option A (re-index) | Option B (dedup) |
|---|---|---|
| requests kept | all | 86,400 (0.1%) |
| tick means | one arrival | one real second |
| `Z_A` units | arrivals | seconds |
| reuse preserved | 89.7% | 19.2% |
| code changes | none | none |

`time_firstbyte` (`respTime`) is bimodal — fast values are served locally, slow
values are origin fetches (rows 1-3 of the trace: `0.000165`, `0.00017`,
`0.441594`). The slow mode is a direct empirical measurement of the fetch delay
being modelled as `Z_A`, and can be used to calibrate it under either option.

---

## 3. The `item` column is the wrong column

`dataset analysis/hi.py` factorises and renames:

```python
df.hashed_path_query = pd.factorize(df.hashed_path_query)[0]
df.image_type        = pd.factorize(df.image_type)[0]
df.columns = ["time", "req", "item", "respTime"]
```

so `item` = `image_type` and `req` = `hashed_path_query`. These are the wrong
way round for the simulation.

`hashed_path_query` is a hash of the request's **path + query string** — i.e.
the URL, which on an image-serving CDN identifies the file. It is *not* a
per-request unique ID: two requests for the same image produce the same hash.
Measured over the first 2M rows:

```
distinct hashed_path_query: 1,007,550   (a per-request ID would give 2,000,000)
mean requests per distinct URL: 1.99     max: 9,161
repeat requests to an already-seen URL: 992,450 (49.6%)
```

`image_type` is the file format (png, jpeg, svg, gif, webp, …) — **9 distinct
values across all 114,350,675 rows**. It cannot be the item:

- A cache of capacity `k` stores `k` items. With 9 items, any `k >= 9` holds the
  entire universe and the hit rate is 100% forever. `krange = 2 ** np.arange(16)`
  goes to `k = 32768`, so nearly the whole sweep is degenerate.
- "Evict png, admit jpeg" is not a cache operation — you cannot fetch *a png*
  from the backing store.

### Column semantics

| tsv column | meaning | role in the model |
|---|---|---|
| `relative_unix` | seconds since trace start | `t` |
| `hashed_path_query` | hash of URL → **the object** | `item` (`I`) |
| `image_type` | file format, 9 values | covariate |
| `response_size` | bytes | covariate (currently dropped) |
| `time_firstbyte` | TTFB | calibrates `Z_A` |

`item` should be the factorised `hashed_path_query`. `image_type` and
`response_size` are attributes of the object, useful for slicing results, not
for identity.

---

## 4. Dedup measurements

All figures over the full `cache-u-00-cleaned.csv`.

### Shape of the trace

```
rows                 114,350,675
distinct timestamps       86,400   (1-second granularity, exactly 24h)
requests per second: mean 1,323.5   median 1,484   max 2,774
```

On the first 100,000 rows — what `makeSeq`'s `df.head(n=100000)` actually reads:

```
rows                     100,000
distinct timestamps           57   (t = 0..56)
requests per second: mean 1,754.4   median 1,749   max 2,157
```

So the `head(100000)` truncation gives a trace spanning 57 seconds. Removing it
is what makes dedup coherent: dedup over the full file gives 86,400 requests,
not 57.

### Effect of dedup on reuse

Reuse — a request for an item already seen — is what makes LCE and OPT
distinguishable at all. If an item is never re-requested, both policies just pay
the fetch cost and the competitive ratio measures cold-start behaviour rather
than replacement behaviour.

Measured with `item` correctly set to the URL hash:

```
FULL trace:   114,350,675 rows      11,827,234 distinct URLs
              URLs seen exactly once:  5,729,139  (48.4% of URLs)
              reuse requests:        102,523,441  (89.7% of rows)

DEDUP (first row per second):
                   86,400 rows          69,781 distinct URLs
              URLs seen exactly once:     64,265  (92.1% of kept URLs)
              reuse requests:             16,619  (19.2% of kept rows)
```

**Reuse collapses from 89.7% to 19.2%**, and 92.1% of the URLs surviving dedup
appear exactly once. A deduped trace is ~80% compulsory misses.

For completeness, with the current (wrong) `item = image_type`, 99.6% of rows
are same-second repeats of the same item — 113,939,392 of 114,350,675. Those are
exactly the concurrent same-item arrivals that generate delayed hits, so dedup
under the current column mapping also removes the delayed-hit phenomenon the
model exists to measure.

### Conclusion

Re-indexing (Option A) is preferred. Dedup discards the temporal locality the
study depends on.

If dedup is used anyway, note that "keep the first row of each second" is a
biased sample — it inherits whatever ordering the log happens to have within a
second. A random pick per second, or a fixed offset, is easier to defend.

---

## 5. Other issues in `trace sim.py`

- **`TMAX_VAL` is taken over the wrong thing.** `trace sim.py:155` reads the
  entire 114M-row CSV into pandas just to get `time.max() = 86399`, but
  `makeSeq` truncates to the first 100k rows, which end at `t = 56`. So even
  once requests flow, `simulate` spins ~86,343 further ticks with an empty queue
  before reaching `clk.tmax` — per sweep point, times 720 sweep points. `tmax`
  should come from the truncated sequence.

- **`makeSeq` is quadratic.** `trace sim.py:57-62` rebuilds the whole tuple per
  row (`self.S + (r1,)`), so building 100k requests is O(n²) — and `runConfig`
  rebuilds the sequence from scratch inside every one of the 720 sweep points,
  from an unchanged file.

- **`seq.t` is aliased to `netLCE.clk.t`** (the same mutable `T` object), which
  is what makes the equality check in `sendReq` track the clock at all. The
  commented-out OPT replay at `trace sim.py:144` will need that rebind to
  `netOPT.clk.t` before it works, as the existing comment notes.
