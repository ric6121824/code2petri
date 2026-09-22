# 40 — Viewer: Component-Local Unfold

**What to build:** The user can right-click any opaque component or Collapsed Compound State to instantly restore the exact sub-graph that was consumed when it was created. This unfold is local — other folds made elsewhere on the canvas remain in their folded state, unaffected.

**Blocked by:** 39 — Viewer: Collapsed Compound State

**Status:** ready-for-agent

- [ ] Right-clicking an opaque component restores the nodes and edges it consumed, removing the component node
- [ ] Right-clicking a Collapsed Compound State reopens the compound to its fully expanded internal state
- [ ] Arc connections at the boundary are correctly restored to the original elements
- [ ] Other folded components on the canvas are not affected by the unfold operation
- [ ] After unfold, the restored elements are selectable and eligible for further fold operations
