# 31 — Viewer: Input Remapping (Hold-to-Pan, Left-Click Actions)

**What to build:**
Remap viewport and node interaction events so that panning is handled by holding the right and middle mouse buttons, freeing left-click for place and transition actions.

**Blocked by:** 30 — Viewer: Nested Compound Nodes on Load

**Status:** ready-for-agent

- [ ] Holding and dragging the right or middle mouse button pans the canvas viewport
- [ ] Left-clicking a place node is reserved for fold triggering and does not trigger viewport panning
- [ ] Left-clicking a transition or component node selects the node and opens a placeholder inspector HUD panel
- [ ] Wheel zooming remains functional and smooth
