# 31 — Viewer: Input Remapping

**What to build:** The viewer's mouse controls are remapped so that panning is done by holding and dragging the right or middle mouse button, and left-click is completely free for node interactions. Left-clicking a transition or component node opens an inspector panel showing that node's static metadata.

**Blocked by:** 30 — Viewer: Nested Compound Nodes on Load

**Status:** ready-for-agent

- [ ] Holding and dragging the right mouse button pans the canvas
- [ ] Holding and dragging the middle mouse button pans the canvas
- [ ] Left-clicking a place node does not trigger panning or viewport movement
- [ ] Left-clicking a transition or component node opens an inspector panel displaying the node's label, tau weight, component type, and source line number
- [ ] Scroll wheel zoom continues to work
