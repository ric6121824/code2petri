# Code Review — Tickets 43 & 44, Round 01

**Commits:**
- [`c647339`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/43-viewer-camera-viewport-preservation.md) (`docs: publish tickets 43-44 (camera preservation, extended zoom-out)`)
- [`8f4eca0`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html) (`feat(viewer): preserve camera viewport on fold/unfold and allow zooming out to 0.001`)

**Diff:** `git diff 721c5a4...HEAD` (5 files changed, 166 insertions(+), 5 deletions(-))  
**Specs:**
- [`.scratch/code2petri/issues/43-viewer-camera-viewport-preservation.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/43-viewer-camera-viewport-preservation.md)
- [`.scratch/code2petri/issues/44-viewer-extended-zoom-out-range.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/44-viewer-extended-zoom-out-range.md)  
**Standards:** [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) and Fowler 12-smell baseline  
**Tests:** All 104 tests in [`tests/test_html_viewer.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py) and [`tests/test_live_fold_prototype.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_live_fold_prototype.py) pass.

---

## Standards

### (a) Documented Standards Violations (Hard Standards)

**S1 — Prohibited Vocabulary in Issue 43 ([`CONTEXT.md:79-82`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md#L79-L82))**
`CONTEXT.md` defines **Place-Centric Fold Trigger** with the explicit rule *Avoid: Node clicking, manual reduction*.
The issue specification in [`.scratch/code2petri/issues/43-viewer-camera-viewport-preservation.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/43-viewer-camera-viewport-preservation.md#L3) repeatedly uses prohibited phrasing:
- Line 3: *"When the user clicks a place node to fold it"*
- Line 9: *"- [ ] Left-clicking a place node to fold it leaves the zoom level unchanged"*
- Line 10: *"- [ ] ...same screen position as the place node that was clicked..."*

> **Fix:** Revise `43-viewer-camera-viewport-preservation.md` to use canonical domain terms: *"triggering a Place-Centric Fold"* and *"selecting a Place node to initiate Live Fold Reduction"*.

---

### (b) Baseline Code Smells (Judgement Calls)

**S2 — Duplicated Code: Viewport restoration logic across `template.html` and `prototype/index.html`**
The viewport restoration check:
```javascript
if (typeof cy.viewport === 'function') {
  cy.viewport({ zoom: currentZoom, pan: targetPan });
} else {
  if (typeof cy.zoom === 'function') cy.zoom(currentZoom);
  if (typeof cy.pan === 'function') cy.pan(targetPan);
}
```
is duplicated 3 times: [`template.html:1653-1659`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1653-L1659), [`template.html:1760-1765`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1760-L1765), and [`prototype/index.html:947-953`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/prototype/index.html#L947-L953).

> **Fix:** Extract a helper function `_restoreViewport(cy, zoom, pan)` to encapsulate the fallback branching.

**S3 — Duplicated Code: Test harness Petri net literal in `tests/test_html_viewer.py`**
The 17-line sequence net definition is copy-pasted verbatim between [`test_handle_fold_reduction_preserves_camera_viewport`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L5155-L5171) and [`test_handle_right_click_unfold_preserves_camera_viewport`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L5196-L5212).

> **Fix:** Extract a fixture or helper constant (e.g. `_SIMPLE_SEQUENCE_NET_LITERAL`).

**S4 — Data Clumps: `currentZoom` and `currentPan`**
`currentZoom` and `currentPan` always travel together across capture, offset math, and restoration in [`template.html:1633-1659`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1633-L1659) and [`template.html:1751-1765`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1751-L1765).

> **Fix:** Bundle into a single viewport state object: `_captureViewport(cy) -> { zoom, pan }`.

**S5 — Feature Envy: Screen-anchor pan calculation in `handleFoldReduction`**
[`template.html:1644-1651`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1644-L1651) performs raw node coordinate difference and screen-space pan math inside `handleFoldReduction`.

> **Fix:** Encapsulate into a dedicated viewport helper: `_computeAnchoredPan(currentPan, oldPos, newPos, zoom)`.

**S6 — Mysterious Name: `oldPos` and `newPos` in `template.html`**
[`template.html:1635-1646`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1635-L1646) names coordinates of two completely distinct entities (`oldPos` for the clicked place node, `newPos` for the resulting opaque transition).

> **Fix:** Rename to `preFoldPlacePos` and `postFoldCompPos`.

---

## Spec

### (a) Missing or Partial Requirements

**P1 — Viewport Pan and Screen Position Invariance Not Verified in Test Suite (Ticket 43)**
> Spec: *"- [ ] After a fold, the new component node appears at the same screen position as the place node that was clicked, keeping the point of interest on screen"*  
> Spec: *"- [ ] Right-clicking a component node to unfold it leaves the zoom level and pan position unchanged"*

In [`tests/test_html_viewer.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L5146-L5232), `test_handle_fold_reduction_preserves_camera_viewport` and `test_handle_right_click_unfold_preserves_camera_viewport` only assert `cy.zoom()`. Neither test asserts `cy.pan()` preservation nor verifies the invariant that the screen position of the component node equals the screen position of the clicked place `(pos.x * zoom + pan.x)`.

> **Fix:** Update test assertions in `tests/test_html_viewer.py` to verify `cy.pan()` preservation on unfold and verify screen-space anchor invariance: `Math.abs((newPos.x * postZoom + postPan.x) - (oldPos.x * initialZoom + initialPan.x)) < 1.0`.

**P2 — Functional Large-Net `cy.fit()` Auto-Fit Not Verified in Test Suite (Ticket 44)**
> Spec: *"- [ ] When a large net is opened, cy.fit() on initial load shows the complete graph without clipping"*

`test_template_min_zoom_allows_deep_zoom_out` only performs a static regex scan on `template.html`. No test verifies that a large net that previously hit the `0.2` floor now fits without clamping when `cy.fit()` runs.

> **Fix:** Add a headless test case loading a net with sufficient nodes to require `zoom < 0.2`, asserting `cy.fit()` sets `cy.zoom() < 0.2` without clipping.

---

### (b) Scope Creep

**P3 — Prototype File Modifications Outside Production Deliverables**
Tickets 43 and 44 explicitly specify viewer improvements (`Viewer: Camera Viewport Preservation on Fold and Unfold`, `Viewer: Extended Zoom-Out Range for Large Nets`).
[`code2petri/viewer/prototype/index.html`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/prototype/index.html#L913-L953) was modified in the diff. Prototype scripts are temporary testbeds rather than deliverables.

> **Fix:** Revert modifications to `prototype/index.html`, or ensure any changes there strictly match production logic.

---

### (c) Wrong Implementation

**P4 — Defective Viewport Logic in Prototype Sandbox (if retained)**
> Spec: *"- [ ] After a fold, the new component node appears at the same screen position as the place node that was clicked, keeping the point of interest on screen"*

In [`prototype/index.html:946-953`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/prototype/index.html#L946-L953), `runLayout()` resets pan to `currentPan` directly, omitting the delta pan calculation `(oldPos - newPos) * currentZoom`. Furthermore, it runs an animated layout (`animate: true`, 300ms) while synchronously forcing viewport coordinates before layout positions stabilize.

> **Fix:** If retained, set `animate: false` during fold updates and calculate delta pan matching `template.html`.

**P5 — 10x Loose Test Assertion Threshold (Ticket 44)**
> Spec: *"- [ ] The viewer allows zooming out to at most 0.1% zoom (minZoom <= 0.001)"*

In [`tests/test_html_viewer.py:5150`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L5150), `test_template_min_zoom_allows_deep_zoom_out` tests `self.assertLessEqual(min_zoom, 0.01)`. `0.01` is 1.0%, which is a factor of 10 looser than the spec requirement of 0.1% (`0.001`).

> **Fix:** Tighten the assertion to `self.assertLessEqual(min_zoom, 0.001)` and align the test docstring.
