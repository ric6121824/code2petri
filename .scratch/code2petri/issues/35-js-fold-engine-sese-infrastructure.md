# 35 — JS Fold Engine: SESE Infrastructure (Bidirectional Reachability)

**What to build:** A shared client-side module that, given any two boundary nodes on the canvas, determines whether they bound a Single-Entry Single-Exit (SESE) subnet and returns the exact set of nodes inside it. This is the mathematical foundation that the three macro-component tickets (36, 37, 38) all depend on.

**Blocked by:** 34 — JS Fold Engine: While Loop Reduction

**Status:** ready-for-agent

- [ ] Given an entry node u and exit node v, the module returns the node set satisfying bidirectional reachability (forward reachable from u equals backward reachable from v)
- [ ] The module correctly excludes boundary nodes that violate the SESE invariant
- [ ] The symmetry multiplier calculation (diffP, diffT) produces values matching the Python fold engine for the same subnet
- [ ] Performance is acceptable on a composite graph with 200+ nodes without visible UI lag
