# 35 — JS Fold Engine: SESE Infrastructure (Bidirectional Reachability)

**What to build:**
A shared client-side graph analysis module that discovers Single-Entry Single-Exit (SESE) subnets using bidirectional reachability (`forward == backward`) and computes symmetry multipliers (diffP, diffT).

**Blocked by:** 34 — JS Fold Engine: While Loop Reduction

**Status:** ready-for-agent

- [ ] Bidirectional BFS search correctly identifies candidate SESE subnet boundaries across Cytoscape elements
- [ ] Invariant check verifies forward reachable set from entry equals backward reachable set from exit
- [ ] Symmetry multiplier utility calculates diffP and diffT for candidate subnets
- [ ] Fast boundary indexing avoids UI lag on large composite graphs
