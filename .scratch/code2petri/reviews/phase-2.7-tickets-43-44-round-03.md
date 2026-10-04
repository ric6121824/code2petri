# Code Review: Tickets 43 & 44 (Viewer: Viewport Preservation & Extended Zoom-Out) — Round 03

**Commits:**
- [`0d35a4b`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py) (`refactor(tests): decouple viewport helper extraction from declaration order`)
- [`dcff09e`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/engine/viewport.js) (`refactor(viewer): extract viewport module into engine/viewport.js (Option 3)`)

**Diff:** `git diff 1972fef...HEAD` (4 files changed, 191 insertions(+), 33 deletions(-))  
**Specs:**
- [`.scratch/code2petri/issues/43-viewer-camera-viewport-preservation.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/43-viewer-camera-viewport-preservation.md)
- [`.scratch/code2petri/issues/44-viewer-extended-zoom-out-range.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/44-viewer-extended-zoom-out-range.md)
- Option 3 remediation defined in [`.scratch/code2petri/reviews/phase-2.7-tickets-43-44-round-02.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/reviews/phase-2.7-tickets-43-44-round-02.md)  
**Standards:** [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) and Fowler 12-smell baseline  
**Test Suite:** All 112 tests across [`tests/test_html_viewer.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py) and [`tests/test_live_fold_prototype.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_live_fold_prototype.py) pass.

---

## Standards

### (a) Verification of Round 02 Standards Baseline Smell Remediation

- **Fragile Coupling / Implicit Order Dependency in Test Regex: VERIFIED RESOLVED (Option 3)**  
  The multi-function regex extraction (`m_vp = re.search(...)`) in [`tests/test_html_viewer.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L97) has been completely removed. Viewport helpers (`_captureViewport`, `_computeAnchoredPan`, `_restoreViewport`) are now encapsulated within a standalone module in [`code2petri/viewer/engine/viewport.js`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/engine/viewport.js) and directly imported into test harnesses via `require()`.

### (b) Documented Standards Violations (Hard Standards)

- **None detected.** All code, tests, and documentation adhere to [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) rules and use canonical domain terms.

*(Optional Domain Vocabulary Polish in JSDocs):*
- In [`code2petri/viewer/engine/viewport.js:3`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/engine/viewport.js#L3), `"during fold and unfold operations"` can be updated to canonical terms **Live Fold Reduction** ([`CONTEXT.md:75`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md#L75)) and **Component-Local Unfold** ([`CONTEXT.md:87`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md#L87)).
- In [`viewport.js:31`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/engine/viewport.js#L31), `"replacement component node"` can use the canonical term **Opaque Transition** ([`CONTEXT.md:19, 48`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md#L19)).

### (c) Baseline Smells in Diff (Judgement Calls)

- **S1 — Speculative Generality / Duplicated Code: Triple-Aliased Module Exports ([`viewport.js:70-87`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/engine/viewport.js#L70-L87))**  
  The module exports functions under three concurrent shapes:
  1. Underscored aliases: `_captureViewport`, `_computeAnchoredPan`, `_restoreViewport`
  2. Public aliases: `captureViewport`, `computeAnchoredPan`, `restoreViewport`
  3. Engine namespace attachment: `LiveFoldReductionEngine.viewport = { capture, computeAnchoredPan, restore }`  
  Neither `captureViewport` nor `LiveFoldReductionEngine.viewport` is consumed by the viewer UI ([`template.html:1633-1644`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1633-L1644) still calls the underscored names). The dual aliasing and monkey-patching anticipate alternative consumer shapes without a direct requirement in `template.html`.  
  *(Fix optional: Standardize on clean public export names or purely on `LiveFoldReductionEngine.viewport`.)*

- **S2 — Mysterious Name: Public Module Functions with Leading Underscores ([`viewport.js:23, 45, 60`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/engine/viewport.js#L23))**  
  In modern JavaScript modules, leading underscores typically signal private module internals. Exporting and consuming `_captureViewport`, `_computeAnchoredPan`, and `_restoreViewport` as public APIs across [`template.html`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1633-L1644) and [`tests/test_html_viewer.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L97-L100) blurs the boundary between private helpers and public module contracts.  
  *(Fix optional: Define the module functions without leading underscores: `captureViewport`, `computeAnchoredPan`, `restoreViewport`.)*

---

## Spec

### (a) Missing or Partial Requirements

- **None.** All requirements specified under the Option 3 remediation plan and originating tickets 43 & 44 are fully met:
  1. Viewport functions extracted to standalone module [`code2petri/viewer/engine/viewport.js`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/engine/viewport.js).
  2. Module dynamically bundled and injected via `/* {{ENGINE_SCRIPTS}} */` in [`code2petri/viewer/__init__.py:53`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/__init__.py#L53).
  3. Brittle multi-function regex parsing removed from [`tests/test_html_viewer.py:97-104`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L97-L104) and replaced with direct `require('./code2petri/viewer/engine/viewport.js')`.
  4. All 112 test cases pass cleanly without regressions.

### (b) Behaviour in Diff Not Asked For (Scope Creep)

1. **Dual Export Aliasing & Engine Namespace Attachment:**  
   The diff implements multiple export interfaces (direct CommonJS exports, global binding, and `LiveFoldReductionEngine.viewport` namespace attachment) alongside underscored aliases. This is benign forward-compatibility and harmless to runtime execution.
2. **Dedicated Unit Test Class ([`tests/test_html_viewer.py:5312-5409`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L5312-L5409)):**  
   Added `TestViewportModule` covering bundle injection, CommonJS export signatures, engine namespace attachment, and mathematical screen coordinate invariance. While beyond the minimal 3-bullet specification, this provides valuable unit test coverage for the new module.

### (c) Requirements Implemented Wrong

- **None.** Screen coordinate invariance math `targetPan = currentPan + (preFoldPlacePos - postFoldCompPos) * zoom` is mathematically verified by unit tests, and layout execution with `fit: false` prevents camera jumps during live fold operations.

---

## Summary

- **Standards:** PASS (0 hard violations, 2 minor baseline smell judgement calls on export aliasing).
- **Spec:** PASS (0 missing/partial requirements, 0 wrong implementations, 1 benign scope creep of expanded test coverage).
- **Smell Remediation:** Verified resolved. The regex coupling baseline smell is fully eliminated.
