# 36 — JS Fold Engine: Marked Graph + State Machine Reductions

**What to build:**
Client-side reductions for maximal SESE Marked Graph subnets (all internal places are 1-in/1-out) and State Machine subnets (all internal transitions are 1-in/1-out).

**Blocked by:** 35 — JS Fold Engine: SESE Infrastructure (Bidirectional Reachability)

**Status:** ready-for-agent

- [ ] Marked graph detection identifies maximal SESE subnets where internal places satisfy 1-in/1-out
- [ ] State machine detection identifies maximal SESE subnets where internal transitions satisfy 1-in/1-out
- [ ] Left-clicking candidate boundary elements collapses the macro-component into an opaque transition
- [ ] Weight tau and penalty omega are calculated using the respective marked graph and state machine formulas
- [ ] Consumed elements are preserved inside the generated component node data for local undo
