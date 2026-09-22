# 32 — JS Fold Engine: Sequence (Single-Place Contraction)

**What to build:**
Client-side implementation of Single-Place Contraction. Left-clicking an intermediate place matching 1-in/1-out criteria contracts the place and merges adjacent transitions into an opaque transition directly in the browser.

**Blocked by:** 31 — Viewer: Input Remapping (Hold-to-Pan, Left-Click Actions)

**Status:** ready-for-agent

- [ ] Place nodes qualifying for Single-Place Contraction are visually styled (green affordance)
- [ ] Left-clicking an eligible place contracts it, merging the two adjacent transitions into an opaque transition
- [ ] Transition weight tau and SM penalty omega are computed accurately per ProM sequence rules
- [ ] Consumed nodes and edges are saved in the new node's internal data for future component-local undo
