# 27 — Canvas Panning via Right Mouse Button & Middle Mouse Button

**What to build:** Canvas panning is reassigned to the right and middle mouse buttons. Left-clicking and dragging on the background canvas does nothing, nodes cannot be dragged out of layout (`autoungrabify`), left-clicking on nodes continues to handle compound expansion and collapse, and mouse wheel / trackpad scroll zooming remains fully functional.

**Blocked by:** None — can start immediately

**Status:** resolved

- [x] Left-click dragging on the canvas background does nothing (default Cytoscape user panning disabled).
- [x] Nodes are locked to layout (`autoungrabify: true`) so they cannot be dragged out of alignment.
- [x] Right-click and middle-click dragging smoothly pan the viewport.
- [x] Mouse wheel and trackpad scroll zooming operates smoothly, anchored to cursor position.
- [x] Left-clicking on interactive call transitions and compound nodes continues to toggle expansion and collapse.
- [x] Automated tests verify Cytoscape canvas settings, middle/right button panning, wheel zooming, and node tap event listeners.

## Answer
1. **Cytoscape Canvas Configuration**:
   - `autoungrabify: true` ensures nodes cannot be dragged out of layout by users.
   - `userPanningEnabled: false` disables default left-drag canvas panning.
   - `boxSelectionEnabled: false` prevents box/marquee selection when dragging with the left mouse button.
2. **Right & Middle Click Drag Panning**:
   - Suppressed context menu (`contextmenu.preventDefault()`) and middle-click autoscroll (`auxclick.preventDefault()`) on `#cy`.
   - Listened to `mousedown` on `#cy` for `e.button === MOUSE_BUTTON_MIDDLE` (1) or `e.button === MOUSE_BUTTON_RIGHT` (2) to initiate drag panning and set cursor to `grabbing`.
   - Listened to `window.mousemove` while dragging to verify button depression (`(e.buttons & PAN_BUTTON_MASKS) !== 0`), compute mouse delta (`dx`, `dy`), and call `cy.panBy({ x: dx, y: dy })`.
   - Listened to `window.mouseup` to cleanly reset drag state and cursor when pan buttons are released.
3. **Scroll Wheel Zooming**:
   - Because Cytoscape's internal wheel handler requires `userPanningEnabled: true`, an explicit `wheel` event listener is attached to `cyContainer`.
   - Computes zoom delta using Cytoscape's formula (`s = deltaY / -250 * wheelSensitivity`) and invokes `cy.zoom({ level: targetZoom, renderedPosition: { x, y } })` anchored to mouse cursor coordinates.
4. **Preserved Tap Behavior**:
   - Cytoscape `tap` events continue to handle compound expansion and collapse on left-clicks (`button === 0`).
5. **Verification**:
   - Unit tests `test_canvas_panning_and_ungrabify_settings` and `test_headless_canvas_panning_and_wheel_zoom` added to `tests/test_html_viewer.py`.


