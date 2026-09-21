# Ticket 27: Code Review (Round 1)

**Diff:** `HEAD`  
**Files:** `code2petri/viewer/template.html`, `tests/test_html_viewer.py`  
**Spec:** `.scratch/code2petri/issues/27-viewer-right-click-pan.md`  

## Standards
**STATUS: PASS (0 Hard Violations, 3 Baseline Smells Addressed)**

### (a) Documented Repo Standards (`CONTEXT.md`)
- **Violations**: None (**Hard violations: 0**). Neither file touches or violates domain model terms defined in `CONTEXT.md`.

### (b) Baseline Code Smells (Fowler Refactoring ch. 3 — Judgement Calls)
1. **Primitive Obsession (Magic numbers for mouse buttons)**
   - *Issue*: Mouse button code `2` used directly instead of named constants.
   - *Resolution*: Defined `const MOUSE_BUTTON_RIGHT = 2;` and `const MOUSE_BUTTONS_RIGHT_MASK = 2;` in `template.html`.
2. **Duplicated Code (Coordinate assignment)**
   - *Issue*: Repeated coordinate assignment logic across `mousedown` and `mousemove`.
   - *Resolution*: Extracted `setDragPos(e)` helper in `template.html`.
3. **Primitive Obsession in Tests**
   - *Status*: Acknowledged; aligns with testing pattern used across `test_html_viewer.py`.

---

## Spec
**STATUS: PASS (All Findings Resolved)**

### (a) Requirements Missing or Partial
1. **Partial Event Listener Testing**:
   - *Finding*: `test_canvas_panning_and_ungrabify_settings` originally did not assert `mousemove` and `mouseup` listener registrations.
   - *Resolution*: Added explicit assertions for `'mousemove'` and `'mouseup'` lifecycle listeners.
2. **Missing Coexistence Test for Node Click Toggling**:
   - *Finding*: Needed verification that `cy.on('tap', 'node', ...)` and compound expansion/collapse state (`expandedNodes`) coexist with `autoungrabify: true` and `userPanningEnabled: false`.
   - *Resolution*: Added explicit assertions in `test_canvas_panning_and_ungrabify_settings` verifying `cy.on('tap', 'node'` and `expandedNodes` remain intact.

### (b) Scope Creep / Hover Cursor Behavior
1. **Cursor Management**:
   - *Finding*: Setting `cursor = 'default'` on `mouseup` could clobber `'pointer'` cursor if mouseup occurred over an interactive node.
   - *Resolution*: Reset `cyContainer.style.cursor = ''` on drag end so that element CSS/hover rules take precedence without hardcoding `'default'`.

### (c) Requirements Implemented Incorrectly
1. **Unchecked Button on Mouseup**:
   - *Finding*: `mouseup` previously aborted dragging regardless of which button was released.
   - *Resolution*: Added check `e.button === MOUSE_BUTTON_RIGHT` so only releasing the right mouse button terminates right-drag panning.
2. **Missing Buttons Mask Check**:
   - *Finding*: If mouse was released outside the window, dragging could remain stuck.
   - *Resolution*: Added `(e.buttons & MOUSE_BUTTONS_RIGHT_MASK) === 0` guard in `mousemove` to automatically terminate drag when right button is no longer depressed.

---

## Summary
- **Standards findings**: 0 hard violations, 3 baseline smells (all addressed).
- **Spec findings**: 0 missing requirements, 2 robustness fixes applied (button mask & mouseup filtering).

---

# Ticket 27: Code Review (Round 2 — Follow-up)

**User Feedback:**
1. "the scroll doesn't work after your implementation"
2. "I want the middle button to be able to pan as well. (both buttons work)"

### Root Cause & Resolution
1. **Scroll (Wheel Zoom) Inactive**:
   - *Root Cause*: Cytoscape's internal wheel event handler explicitly checks `n.panningEnabled() && n.userPanningEnabled() && n.zoomingEnabled() && n.userZoomingEnabled()`. By configuring `userPanningEnabled: false` (to disable left-click canvas panning), Cytoscape automatically suppressed wheel zoom events.
   - *Resolution*: Added an explicit `wheel` listener to `#cy` that calculates zoom factor based on `e.deltaY` and `wheelSensitivity`, invoking `cy.zoom({ level: targetZoom, renderedPosition })` centered at the cursor coordinates.
2. **Middle Mouse Button Drag Panning**:
   - *Resolution*: Expanded drag panning to accept `e.button === MOUSE_BUTTON_MIDDLE` (1) alongside `MOUSE_BUTTON_RIGHT` (2).
   - Added `auxclick` event listener on `#cy` calling `e.preventDefault()` to prevent browser autoscroll.
   - Combined button masks `PAN_BUTTON_MASKS = 4 | 2` (6) in `mousemove` and `mouseup` to ensure smooth panning with either or both buttons.
3. **Automated Verification**:
   - Enhanced `test_canvas_panning_and_ungrabify_settings` in `tests/test_html_viewer.py`.
   - Added `test_headless_canvas_panning_and_wheel_zoom` running headless Cytoscape via Node.js to verify programmatic `panBy` and wheel `cy.zoom` under `userPanningEnabled: false`.

---

# Ticket 27: Code Review (Round 3 — Node Dragging)

**User Feedback:**
- "I can't drag the nodes with the left mouse button."

### Root Cause & Resolution
- *Root Cause*: Ticket 27 originally specified `autoungrabify: true`, which prevented nodes from being dragged/repositioned.
- *Resolution*: Set `autoungrabify: false` in Cytoscape configuration so that users can grab and drag individual nodes using the left mouse button, while background left-drag panning remains disabled (`userPanningEnabled: false`).
- *Verification*: Updated `tests/test_html_viewer.py` and headless test to assert `autoungrabify: false` and `node.grabbable() === true`.


