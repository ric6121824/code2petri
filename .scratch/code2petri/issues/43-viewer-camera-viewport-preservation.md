# 43 — Viewer: Camera Viewport Preservation on Fold and Unfold

**What to build:** When the user clicks a place node to fold it, or right-clicks a component node to unfold it, the canvas zoom level and pan position stay exactly where the user left them. The resulting component node appears at the same screen location as the place node that was clicked. The camera never jumps back to a default whole-graph fit.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] Left-clicking a place node to fold it leaves the zoom level unchanged
- [ ] After a fold, the new component node appears at the same screen position as the place node that was clicked, keeping the point of interest on screen
- [ ] Right-clicking a component node to unfold it leaves the zoom level and pan position unchanged
- [ ] The behaviour holds whether the user is zoomed in, zoomed out, or has panned away from the default viewport
- [ ] The layout is re-run after fold/unfold without triggering a `cy.fit()` reset
