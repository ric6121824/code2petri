# Code Review: Tickets 43 & 44 (Viewer: Viewport Preservation & Extended Zoom-Out) — Round 04

**Commit:** [`28de052`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/engine/viewport.js) (`refactor(viewer): standardize viewport exports on canonical public names and polish domain terms`)  
**Diff:** `git diff 2f8c6b1...HEAD` (3 files changed, 38 insertions(+), 30 deletions(-))  
**Specs:**
- [`.scratch/code2petri/issues/43-viewer-camera-viewport-preservation.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/43-viewer-camera-viewport-preservation.md)
- [`.scratch/code2petri/issues/44-viewer-extended-zoom-out-range.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/44-viewer-extended-zoom-out-range.md)
- Smell remediation recommendations from [`.scratch/code2petri/reviews/phase-2.7-tickets-43-44-round-03.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/reviews/phase-2.7-tickets-43-44-round-03.md)  
**Standards:** [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) and Fowler 12-smell baseline  
**Test Suite:** All 112 tests across [`tests/test_html_viewer.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py) and [`tests/test_live_fold_prototype.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_live_fold_prototype.py) pass.

---

## Standards

### (a) Verification of Round 03 Standards Baseline Smells

- **S1 — Speculative Generality / Duplicated Code: VERIFIED RESOLVED**  
  Export declarations and calling code in [`code2petri/viewer/template.html`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1630-L1644) and [`tests/test_html_viewer.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L97-L100) have standardized on canonical, clean public function names (`captureViewport`, `computeAnchoredPan`, `restoreViewport`).
- **S2 — Mysterious Name (Public Leading Underscores): VERIFIED RESOLVED**  
  Functions in [`code2petri/viewer/engine/viewport.js`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/engine/viewport.js) are declared cleanly without leading underscores (`captureViewport`, `computeAnchoredPan`, `restoreViewport`). Underscored identifiers are retained strictly as backward-compatibility shims on the export object.

### (b) Documented Standards Violations (Hard Standards)

- **None detected.** JSDoc terminology in `viewport.js` now uses the canonical domain term **Opaque Transition** ([`CONTEXT.md:19, 48`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md#L19)) and avoids all prohibited terms.

### (c) Baseline Smells in Diff (Judgement Calls)

- **Parameter Abbreviation / Naming Polish ([`viewport.js:45`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/engine/viewport.js#L45)):**  
  Parameter name `postFoldCompPos` still uses `Comp` (component). Renaming to `postFoldTransitionPos` or `postFoldNodePos` would bring parameter names into full alignment with the updated JSDoc.
- **Middle Man Shims ([`viewport.js:74-76`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/engine/viewport.js#L74-L76)):**  
  Backward-compatible aliases (`_captureViewport`, etc.) can be deprecated once all downstream consumers migrate completely.

---

## Spec

### (a) Missing or Partial Requirements

- **None.** Canonical public exports are consumed across `template.html` and tests. Screen coordinate anchor invariance:
  $$\text{targetPan} = \text{currentPan} + (\text{preFoldPlacePos} - \text{postFoldCompPos}) \times \text{zoom}$$
  is preserved without regressions.

### (b) Behaviour in Diff Not Asked For (Scope Creep)

- **None.** The diff strictly implements the baseline smell remediation and domain terminology polish requested in Round 03. Added assertions in `TestViewportModule` verify functional equivalence between canonical and legacy export names.

### (c) Requirements Implemented Wrong

- **None.**

---

## Summary

- **Standards:** PASS (0 hard violations, 2 minor non-blocking naming polishes).
- **Spec:** PASS (0 missing/partial requirements, 0 scope creep, 0 wrong implementations).
- All 112 tests across the test suites pass with exit code 0.
