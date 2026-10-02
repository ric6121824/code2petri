# Code Review: Tickets 43 & 44 (Viewer: Viewport Preservation & Extended Zoom-Out) — Round 02

**Commit:** [`2b13cba`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html) (`refactor(viewer): resolve tickets 43-44 review findings (S1-S6, P1-P5)`)  
**Diff:** `git diff 721c5a4...HEAD` (5 files changed, 345 insertions(+), 3 deletions(-))  
**Specs:**  
- [`.scratch/code2petri/issues/43-viewer-camera-viewport-preservation.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/43-viewer-camera-viewport-preservation.md)  
- [`.scratch/code2petri/issues/44-viewer-extended-zoom-out-range.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/44-viewer-extended-zoom-out-range.md)  
**Standards:** [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) and Fowler 12-smell baseline  
**Test suite:** All 103 tests in [`tests/test_html_viewer.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py) pass.

---

## Standards

### (a) Verification of Round 1 Standards Findings

- **S1 — Prohibited Vocabulary in Issue 43 ([`CONTEXT.md:79-82`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md#L79-L82)): VERIFIED RESOLVED**  
  Prohibited phrases (*"clicks a place node"*, *"Left-clicking"*, *"Right-clicking"*) in [`.scratch/code2petri/issues/43-viewer-camera-viewport-preservation.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/43-viewer-camera-viewport-preservation.md) were replaced with canonical terms: *"selects a Place node to initiate Live Fold Reduction"*, *"Triggering a Place-Centric Fold"*, and *"Initiating Component-Local Unfold"*.

- **S2 — Duplicated Code (Viewport Restoration): VERIFIED RESOLVED**  
  Extracted helper `_restoreViewport(cy, zoom, pan)` at [`template.html:1642-1650`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1642-L1650), unifying fallback viewport restoration across `handleFoldReduction` and `handleRightClickUnfold`. Out-of-scope prototype edits were reverted.

- **S3 — Duplicated Code (Test Net Literal): VERIFIED RESOLVED**  
  Extracted class-level constant `_SIMPLE_SEQUENCE_NET_LITERAL` in [`tests/test_html_viewer.py:5152-5168`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L5152-L5168), eliminating duplicate JSON strings across viewport tests.

- **S4 — Data Clumps (`currentZoom`, `currentPan`): VERIFIED RESOLVED**  
  Captured jointly as `{ zoom, pan }` via helper `_captureViewport(cy)` in [`template.html:1626-1631`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1626-L1631).

- **S5 — Feature Envy (Anchor Pan Calculation): VERIFIED RESOLVED**  
  Coordinate math extracted into pure helper `_computeAnchoredPan(currentPan, preFoldPlacePos, postFoldCompPos, zoom)` at [`template.html:1633-1640`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1633-L1640).

- **S6 — Mysterious Name (`oldPos`/`newPos`): VERIFIED RESOLVED**  
  Renamed to domain-explicit `preFoldPlacePos` and `postFoldCompPos` in [`template.html:1660, 1667`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1660).

### (b) Hard Violations of Documented Standards

- **None detected.** Code, tests, and documentation adhere to `CONTEXT.md` conventions and the domain vocabulary.

### (c) Baseline Smells in Diff (Judgement Calls)

- **Fragile Coupling / Implicit Order Dependency in Test Regex ([`tests/test_html_viewer.py:79-82`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L79-L82)):**  
  The test harness extracts helper functions via `re.search(r'function _captureViewport\(cy\) \{.*?function _restoreViewport\(cy, zoom, pan\) \{.*?\n      \}', html, re.DOTALL)`. This spans from `_captureViewport` through `_restoreViewport`, implicitly coupling the test harness to the exact declaration order of those functions in `template.html`. Reordering helpers in the future would break harness extraction.  
  *(Low severity; test suite currently executes and passes cleanly.)*

  > **Chosen Remediation — Architectural Module Extraction (Option 3):**  
  > Align viewport management with the Phase 2.7 engine modularization architecture (which cleanly extracted [`reduction_engine.js`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/engine/reduction_engine.js) and [`pnml_exporter.js`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/engine/pnml_exporter.js)):  
  > 1. Extract `_captureViewport`, `_computeAnchoredPan`, and `_restoreViewport` into a dedicated engine module (`code2petri/viewer/engine/viewport.js`) or attach them directly as a static utility namespace on `LiveFoldReductionEngine.viewport = { capture, computeAnchoredPan, restore }`.  
  > 2. Inject the script bundle into `template.html` at build time via the existing `/* {{ENGINE_SCRIPTS}} */` injection point in [`code2petri/viewer/__init__.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/__init__.py).  
  > 3. In [`tests/test_html_viewer.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py), load the engine module directly in Node.js harnesses via `require()`, completely eliminating brittle multi-function regular expression slicing from HTML templates.

---

## Spec

### (a) Verification of Round 1 Spec Findings

- **P1 — Viewport Pan & Screen Invariance (Ticket 43): VERIFIED RESOLVED**  
  Spec quotes:
  > *"- [ ] After a fold, the new component node appears at the same screen position as the place node where the fold was triggered, keeping the point of interest on screen"* (line 10)  
  > *"- [ ] Initiating Component-Local Unfold leaves the zoom level and pan position unchanged"* (line 11)  
  [`test_handle_fold_reduction_preserves_camera_viewport`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L5207) asserts screen coordinate invariance (`Math.abs(c01Screen - p1Screen) <= 1.0`), and [`test_handle_right_click_unfold_preserves_camera_viewport`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L5266) asserts exact zoom and pan preservation (`Math.abs(postPan - initialPan) <= 1e-4`).

- **P2 — Large-Net Auto-Fit Test (Ticket 44): VERIFIED RESOLVED**  
  Spec quote:
  > *"- [ ] When a large net is opened, cy.fit() on initial load shows the complete graph without clipping"* (line 10)  
  Added [`test_large_net_autofit_zooms_below_point_two_without_clamping_headless`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L5339), running layout + `cy.fit()` on a 100-node pipeline and asserting `fittedZoom < 0.2` and `>= 0.001`.

- **P3 — Prototype File Scope Creep: VERIFIED RESOLVED**  
  Modifications to `code2petri/viewer/prototype/index.html` were fully reverted in `2b13cba`.

- **P4 — Defective Prototype Viewport Logic: VERIFIED RESOLVED**  
  Non-deliverable prototype edits were eliminated with the P3 reversion.

- **P5 — 10x Loose Test Assertion (Ticket 44): VERIFIED RESOLVED**  
  Spec quote:
  > *"- [ ] The viewer allows zooming out to at most 0.1% zoom (minZoom ≤ 0.001)"* (line 9)  
  [`test_template_min_zoom_allows_deep_zoom_out`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L5328) assertion was tightened to `self.assertLessEqual(min_zoom, 0.001)`.

### (b) Missing or Partial Requirements

- **None.** All requirements across Ticket 43 (*"- [ ] Triggering a Place-Centric Fold leaves the zoom level unchanged"*, *"- [ ] The layout is re-run after fold/unfold without triggering a cy.fit() reset"*) and Ticket 44 (*"- [ ] The user can reach the full-graph overview using the scroll wheel without hitting an artificial floor"*) are implemented and verified.

### (c) Behaviour in Diff Not Asked For (Scope Creep)

- **None.** Diff is cleanly scoped to production `template.html`, `test_html_viewer.py`, and tracking docs.

### (d) Requirements Implemented Wrong

- **None.** Anchor calculation `pan + (preFoldPos - postFoldPos) * zoom` correctly preserves screen position invariance, and `cy.layout({ fit: false })` avoids fit resets.

---

## Summary

- **Standards:** PASS (0 hard violations, 1 minor non-blocking baseline smell: regex coupling in test helper extraction).
- **Spec:** PASS (0 missing/partial requirements, 0 scope creep, 0 wrong implementations; all 5 round-01 findings verified resolved).
