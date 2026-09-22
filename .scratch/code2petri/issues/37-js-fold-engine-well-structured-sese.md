# 37 — JS Fold Engine: Well-Structured SESE Reduction

**What to build:**
Client-side reduction for maximal Well-Structured SESE subnets that are free from PT/TP handles and internal cycles.

**Blocked by:** 36 — JS Fold Engine: Marked Graph + State Machine Reductions

**Status:** ready-for-agent

- [ ] SESE search identifies maximal subnets free of PT/TP handles and cycles
- [ ] Well-structured reduction rule collapses the detected subnet into a single opaque transition
- [ ] Weight tau and penalty omega match the reference well-structured formula
- [ ] Consumed subnet elements are saved in node data for local undo
