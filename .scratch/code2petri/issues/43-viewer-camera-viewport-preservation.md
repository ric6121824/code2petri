# 43 — Viewer: Camera Viewport Preservation on Fold and Unfold

**What to build:** When the user selects a Place node to initiate Live Fold Reduction, or initiates Component-Local Unfold on a component node, the canvas zoom level and pan position stay exactly where the user left them. The resulting component node appears at the same screen location as the place node where the fold was triggered. The camera never jumps back to a default whole-graph fit.

**Blocked by:** None — can start immediately.

**Status:** resolved

- [x] Triggering a Place-Centric Fold leaves the zoom level unchanged
- [x] After a fold, the new component node appears at the same screen position as the place node where the fold was triggered, keeping the point of interest on screen
- [x] Initiating Component-Local Unfold leaves the zoom level and pan position unchanged
- [x] The behaviour holds whether the user is zoomed in, zoomed out, or has panned away from the default viewport
- [x] The layout is re-run after fold/unfold without triggering a `cy.fit()` reset

## Answer

Implemented viewport capture and restore for Live Fold Reduction and Component-Local Unfold, keeping the affected component at the selected place's screen location while preserving zoom and pan.
