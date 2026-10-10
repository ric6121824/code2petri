# 44 — Viewer: Extended Zoom-Out Range for Large Nets

**What to build:** The user can scroll the mouse wheel to zoom out far enough to see the entire graph at once, even when the net is very large. The current minimum zoom floor is lowered from 20% to 0.1%, so the initial `cy.fit()` call on page load no longer clips large composite nets, and the user can always reach a zoom level where the full graph is visible.

**Blocked by:** None — can start immediately.

**Status:** resolved

- [x] The viewer allows zooming out to at most 0.1% zoom (minZoom ≤ 0.001)
- [x] When a large net is opened, `cy.fit()` on initial load shows the complete graph without clipping
- [x] The user can reach the full-graph overview using the scroll wheel without hitting an artificial floor
- [x] Scroll-wheel zoom-in behaviour and the maxZoom ceiling are unaffected

## Answer

Lowered the viewer's minimum zoom to 0.1%, allowing initial fit and scroll-wheel zoom to show very large composite nets.
