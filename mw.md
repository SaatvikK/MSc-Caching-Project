Lower Bounds for Caching with Delayed Hits

Peter Manohar
Carnegie Mellon University
pmanohar@cs.cmu.edu

Jalani Williams
Carnegie Mellon University
jalaniw@cs.cmu.edu

ABSTRACT
Caches are a fundamental component of latency-sensitive

computer systems. Recent work of [ASWB20] has initi-
ated the study of delayed hits: a phenomenon in caches

that occurs when the latency between the cache and
backing store is much larger than the time between new
requests. We present two results for the delayed hits
caching model.
(1) Competitive ratio lower bound. We prove that the
competitive ratio of the algorithm in [ASWB20], and
more generally of any deterministic online algorithm
for delayed hits, is at least Ω(kZ), where k is the cache
size and Z is the delay parameter.

(2) Antimonotonicity of the delayed hits latency. Anti-
monotonicity is a naturally desirable property of cache

latency: having a cache hit instead of a cache miss should

result in lower overall latency. We prove that the la-
tency of the delayed hits model is not antimonotone by

exhibiting a scenario where having a cache hit instead
of a miss results in an increase in overall latency. We
additionally present a modification of the delayed hits
model that makes the latency antimonotone.