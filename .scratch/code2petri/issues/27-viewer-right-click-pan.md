# 27 — Canvas Panning via Right Mouse Button

**What to build:** Canvas panning is reassigned to the right mouse button. Left-clicking and dragging on the background canvas does nothing, nodes cannot be dragged out of layout (`autoungrabify`), and left-clicking on nodes continues to handle compound expansion and collapse.

**Blocked by:** None — can start immediately

# 27 — Canvas Panning via Right Mouse Button

**What to build:** Canvas panning is reassigned to the right mouse button. Left-clicking and dragging on the background canvas does nothing, nodes cannot be dragged out of layout (`autoungrabify`), and left-clicking on nodes continues to handle compound expansion and collapse.

**Blocked by:** None — can start immediately

**Status:** resolved

- [x] Left-click dragging on the canvas background does nothing (default Cytoscape user panning disabled).
- [x] Nodes are locked to layout (`autoungrabify: true`) so they cannot be dragged out of alignment.
- [x] Right-click dragging smoothly pans the viewport.
- [x] Left-clicking on interactive call transitions and compound nodes continues to toggle expansion and collapse.
- [x] Automated tests verify the Cytoscape canvas settings and panning event listeners.

## Answer
1. **Cytoscape Canvas Configuration**:
   - `autoungrabify: true` ensures nodes cannot be dragged out of layout by users.
   - `userPanningEnabled: false` disables default left-drag canvas panning.
   - `boxSelectionEnabled: false` prevents box/marquee selection when dragging with the left mouse button.
2. **Right-Click Drag Panning**:
   - Suppressed context menu with `contextmenu.preventDefault()` on `#cy`.
   - Listened to `mousedown` on `#cy` for `e.button === 2` to initiate right-drag panning and set cursor to `grabbing`.
   - Listened to `window.mousemove` while dragging to compute mouse delta (`dx`, `dy`) and call `cy.panBy({ x: dx, y: dy })`.
   - Listened to `window.mouseup` to cleanly reset drag state and cursor.
3. **Preserved Tap Behavior**:
   - Cytoscape `tap` events continue to handle compound expansion and collapse on left-clicks (`button === 0`).
4. **Verification**:
   - Unit test `test_canvas_panning_and_ungrabify_settings` added to `tests/test_html_viewer.py`.

