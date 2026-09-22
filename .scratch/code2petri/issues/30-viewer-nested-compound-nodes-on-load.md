# 30 — Viewer: Nested Compound Nodes on Load

**What to build:**
When opening the generated HTML viewer, the view should immediately display the full composite net. Callee subnets are enclosed within visual compound nodes indicating function boundaries on initial render.

**Blocked by:** 29 — Prefactor: Backend Composite Assembly

**Status:** ready-for-agent

- [ ] Viewer reads node parent hierarchy from data payload on initial render
- [ ] Nodes belonging to inlined functions are rendered inside nested compound nodes
- [ ] Compound nodes display readable headers indicating their enclosing function name
- [ ] Canvas layout successfully lays out compound hierarchy without visual overlap
