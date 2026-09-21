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
