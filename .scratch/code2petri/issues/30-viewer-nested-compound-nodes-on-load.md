# 30 — Viewer: Nested Compound Nodes on Load

**What to build:** When the HTML viewer opens, every inlined function's nodes are visually enclosed inside a labelled bounding box (compound node) indicating the function boundary. The user can see the full hierarchy of nested calls at a glance — if A calls B which calls C, three nested containers are visible on the canvas from the first render.

**Blocked by:** 29 — Prefactor: Backend Composite Assembly

**Status:** ready-for-agent

- [ ] Each inlined function appears as a distinct named container on first load, with its callee nodes rendered inside it
- [ ] Nested compound nodes (A containing B containing C) are visually distinguishable and do not overlap unintentionally
- [ ] The canvas lays out the full hierarchy without the user needing to interact first
- [ ] Compound node headers display a readable function name
