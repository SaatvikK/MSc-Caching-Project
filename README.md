## Disseratation Link
You can read the final dissertation here:
https://github.com/SaatvikK/MSc-Caching-Project/blob/companal/Masters%20Dissertation%20Caching.pdf

ABSTRACT:
This report formalises a so-called `delayed-hits-aware' line-network model, characterised by the number of caches $|V|$, the per-cache capacity $k$, and the inter-cache delay $Z_A$. It further establishes two lower-bounds on the competitive ratio of deterministic online placement
policies. The former is a trivial lower-bound on all placement policies ($\Omega(1)$), which grows independently of $|V|$ $k$, and $Z_A$. The latter is a lower-bound specifically for the \textsc{Leave-a-Copy-Everywhere} (LCE) placement policy ($\Omega(k|V|)$). Then, finally, by trying to find a corresponding upper-bound, this report shows that LCE is unbounded above and is therefore an uncompetitive online algorithm.

This work was initially motivated by the fact that caching has become vital in the implementation of networked systems over long geographical distances. This is because it allows data to be stored closer to end-users, reducing overall retrieval latency and improving the quality of service of networked systems. A major example of this is with Content Delivery Networks (CDNs) that have been implemented globally.

The final contribution of this report is a proof that the LCE placement policy, is, in fact, an uncompetitive online algorithm. By providing a sequence that forces the LCE's latency to grow, not with network-specific parameters, but with \textit{sequence}-specific parameters, it is shown that the LCE latency diverges from the optimal algorithm's latency, thereby proving uncompetitiveness. This lower-bound, and subsequent uncompetitive proof are two novel contributions to caching that work towards closing a major gap in the current literature. All results are then empirically validated by simulation work.

## Final simulation


FOR THE FINAL SIMULATION CODE, SWITCH TO THE `companal` BRANCH. 
