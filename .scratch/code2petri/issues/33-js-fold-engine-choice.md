# 33 — JS Fold Engine: Choice Reduction

**What to build:**
Client-side implementation of Choice reduction. Left-clicking an intermediate place or choice pattern fuses parallel transitions into a single component while preserving boundary places.

**Blocked by:** 32 — JS Fold Engine: Sequence (Single-Place Contraction)

**Status:** ready-for-agent

- [ ] Place nodes qualifying for Choice reduction are visually styled (amber affordance)
- [ ] Left-clicking an eligible place fuses parallel outgoing transitions into a single opaque transition
- [ ] Choice penalty with 1.5x multiplier and new transition tau weight are calculated correctly
- [ ] Consumed nodes and edges are stored in the resulting component for local undo
