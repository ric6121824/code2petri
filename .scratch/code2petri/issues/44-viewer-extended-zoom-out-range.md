# 44 — Viewer: Extended Zoom-Out Range for Large Nets

**What to build:** The user can scroll the mouse wheel to zoom out far enough to see the entire graph at once, even when the net is very large. The current minimum zoom floor is lowered from 20% to 0.1%, so the initial `cy.fit()` call on page load no longer clips large composite nets, and the user can always reach a zoom level where the full graph is visible.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] The viewer allows zooming out to at most 0.1% zoom (minZoom ≤ 0.001)
- [ ] When a large net is opened, `cy.fit()` on initial load shows the complete graph without clipping
- [ ] The user can reach the full-graph overview using the scroll wheel without hitting an artificial floor
- [ ] Scroll-wheel zoom-in behaviour and the maxZoom ceiling are unaffected
