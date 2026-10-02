# Code Review: Phase 2.7 (Live Fold Reduction) — Round 02

**Commit:** [`4c8085b`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html) (`refactor(viewer): resolve Phase 2.7 full review findings (S1-S6, P1-P4)`)  
**Diff:** `git diff 690c539...HEAD` (25 files changed, 4,026 insertions(+), 4,159 deletions(-))  
**Master Spec:** [`.scratch/code2petri/specs/phase-2.7-live-fold-reduction.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/specs/phase-2.7-live-fold-reduction.md)  
**Previous Review:** [`.scratch/code2petri/reviews/phase-2.7-full-review.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/reviews/phase-2.7-full-review.md)  
**Standards:** [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) and Fowler 12-smell baseline  
**Test Suite:** All 98 tests in [`tests/test_html_viewer.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py) and full repository test suite pass.

---

## Standards

### (a) Verification of Round 1 Findings

- **S1 (Vocabulary — Client-Side Export) → ⚠️ PARTIALLY RESOLVED:**  
  Core functions, JSDoc, and test methods were renamed to `client_side_export` / `exportClientSidePnml`. However, `downloadPnmlFile` was retained as an alias in the exported object of [`pnml_exporter.js:221`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/engine/pnml_exporter.js#L221).
- **S2 (Prohibited Vocabulary in Master Spec) → ⚠️ PARTIALLY RESOLVED:**  
  Master spec was updated to use canonical terms ("Live Fold Reduction Engine", "Component-Local Unfold", "premature structural folding"). However, line 50 still contains prohibited vocabulary: `"to validate the JS reduction math"`.
- **S3 (Duplicated Code & Divergent Change) → ✅ RESOLVED:**  
  Extracted [`reduction_engine.js`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/engine/reduction_engine.js) (2,500 lines) and [`pnml_exporter.js`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/engine/pnml_exporter.js) (236 lines) into `code2petri/viewer/engine/`. Stripped 2,975 lines of inlined JS from [`template.html`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html), resolving the monolithic Divergent Change smell.
- **S4 (Refused Bequest on `CompoundContainer`) → ✅ RESOLVED:**  
  Removed dict protocol methods (`__getitem__`, `get`, `keys`, `items`) from [`CompoundContainer`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/model.py#L49-L63). Callers in [`inline.py:150`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/inline.py#L150) access dataclass fields (`c.id`) directly.
- **S5 (Primitive Obsession in Viewer Assembly) → ✅ RESOLVED:**  
  [`generate_html`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/__init__.py#L76-L118) now strictly enforces `Union[PetriNet, FoldResult]` and raises `TypeError` for raw `dict` payloads.
- **S6 (Magic Number `UNLIMITED_DEPTH`) → ✅ RESOLVED:**  
  Replaced `999` with `Optional[int] = None` in [`engine.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/engine.py#L53) and [`inline.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/inline.py#L125).

---

### (b) Hard Documented Standards Violations

**H1 — Prohibited Term in Export API ([`CONTEXT.md:27-30`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md#L27-L30))**
- **Location:** [`code2petri/viewer/engine/pnml_exporter.js:221, 234`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/engine/pnml_exporter.js#L221-L234)
- **Hunk:**
  ```javascript
  const downloadPnmlFile = exportClientSidePnml; // Backwards-compatible alias
  return {
    escapeXml,
    serializeToPnml,
    triggerClientSideExport: _triggerBlobDownload,
    exportClientSidePnml,
    downloadPnmlFile
  };
  ```
- **Rule:** Canonical term is **Client-Side Export** (*Avoid: Browser download, frontend save*). Retaining `downloadPnmlFile` in the public API retains prohibited vocabulary.
- **Fix:** Remove `downloadPnmlFile` from the export object. Update the test harness regex in [`tests/test_html_viewer.py:87`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L87) to only check `triggerClientSideExport`.

**H2 — Prohibited Vocabulary in Master Spec ([`CONTEXT.md:7-10`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md#L7-L10))**
- **Location:** [`.scratch/code2petri/specs/phase-2.7-live-fold-reduction.md:50`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/specs/phase-2.7-live-fold-reduction.md#L50)
- **Hunk:**
  ```markdown
  Development will begin on the feature/live-fold-reduction-js-prototype branch to validate the JS reduction math and the Cytoscape UI/UX feel...
  ```
- **Rule:** Canonical term is **Live Fold Reduction** (*Avoid: Client-side folding, JS reduction*).
- **Fix:** Replace `"JS reduction math"` with `"Live Fold Reduction math"`.

---

### (c) Baseline Code Smells (Judgement Calls)

**J1 — Mysterious Syntax: HTML Comment Inside `<script>` Block ([`template.html:1569`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1569))**
```html
cy.on('tap', function(evt) { ... });

<!-- {{ENGINE_SCRIPTS}} -->

function updateFoldableHighlights() { ... }
```
- **Smell:** HTML comment syntax `<!-- ... -->` is placed directly inside an active inline `<script>` tag. While Python string substitution replaces it before browser parsing, it risks breaking JS syntax highlighters and linters analyzing `template.html`.
- **Fix:** Replace placeholder with a JS comment placeholder (`/* {{ENGINE_SCRIPTS}} */`).

**J2 — Middle Man: Prototype Delegation Facades ([`prototype/reduction_engine.js`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/prototype/reduction_engine.js), [`prototype/pnml_exporter.js`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/prototype/pnml_exporter.js))**
- **Smell:** These files are now thin facades that only forward imports to `../engine/*`.
- **Fix:** Update prototype references to import directly from `code2petri/viewer/engine/` and delete the prototype facade files.

---

## Spec

### (a) Verification of Round 1 Findings

- **P1 (Running SM Score Display in Composite Viewer) → ✅ RESOLVED:**  
  `#badge-sm` is preserved in composite mode ([`template.html:1780`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1780)), updates live upon fold and unfold operations ([`template.html:1662, 1736`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1662)), and `#inspector-sm` is rendered in the HUD popover stat pills ([`template.html:460, 1466`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L460)).
- **P2 (Macro SESE & Non-Place Reductions) → ✅ RESOLVED:**  
  Master Spec was updated to formally incorporate Tickets 35–38 (SESE discovery, Marked Graph, State Machine, Well-Structured SESE, and Unstructured Knot isolation) ([`phase-2.7-live-fold-reduction.md:31-37`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/specs/phase-2.7-live-fold-reduction.md#L31-L37)).
- **P3 (Left-Click Interaction Collision) → ❌ BROKEN / UNRESOLVED:**  
  Left-clicking transitions now strictly opens the HUD ([`template.html:1681`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1681)). However, the HUD "Contract Marked Graph" button throws a runtime error (see below).
- **P4 (Cross-Boundary Parent Hierarchy Loss) → ✅ RESOLVED:**  
  Implemented `_findLowestCommonAncestor` in [`reduction_engine.js:226-263`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/engine/reduction_engine.js#L226-L263), assigning cross-boundary fold nodes to their lowest common ancestor compound container rather than canvas root (`null`).

---

### (b) Requirements Implemented Incorrectly

**1. Uncaught ReferenceError on HUD Marked Graph Contraction Button ([`template.html:1536`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1536))**
- **Spec Quote:** Master Spec Line 40: *"Left-Click (Transition/Component): Open floating HUD popover for metadata inspection... and explicit structural fold actions (e.g. 'Contract Marked Graph')."*
- **Problem:** `hudEls.contractMgBtnEl.addEventListener` calls `handleFoldReduction(target, 'marked_graph')` at line 1536. However, `handleFoldReduction` is defined inside the callback of `cy.on('tap', 'node', function(evt) { ... })` at line 1644. Because `handleFoldReduction` is lexically scoped inside the tap handler, clicking the button in the HUD throws:
  ```
  Uncaught ReferenceError: handleFoldReduction is not defined
  ```
- **Masking Cause:** The test harness in [`tests/test_html_viewer.py:277-293`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L277-L293) bypassed `template.html`'s click listener and called its own reduction logic, allowing tests to pass despite the runtime crash.
- **Fix:** Hoist `function handleFoldReduction(...)` out of `cy.on('tap', 'node')` into the outer viewer scope so `hudEls.contractMgBtnEl` can invoke it.

**2. Compound Container Cleanup Omission in `executeSinglePlaceContraction` ([`reduction_engine.js:959`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/engine/reduction_engine.js#L959))**
- **Spec Quote:** Master Spec Line 13: *"When an entire inline expansion (a compound node) is fully folded from the inside out, it transitions into a 'Collapsed Compound State'..."*
- **Problem:** In `executeSinglePlaceContraction`, `consumedCompounds` only inspects `[parentSrc, parentSnk]`. If `placeNode` belongs to a distinct compound `parentPlace` whose remaining elements reach 0, it is omitted from `consumedCompounds`.
- **Fix:** Update candidate array from `[parentSrc, parentSnk]` to `[parentSrc, parentSnk, parentPlace]` (matching line 1435 in while-loop contraction).

---

### (c) Behaviour in Diff Not Asked For (Scope Creep)
- **None.** All changes directly implemented fixes for the Round 1 review findings.

---

## Summary

- **Standards:** 2 hard violations remaining (retained `downloadPnmlFile` alias in `pnml_exporter.js`, `"JS reduction"` on line 50 of master spec); 2 judgement calls (`<!-- {{ENGINE_SCRIPTS}} -->` inside script tag, prototype facade files). Major win: S3 completely resolved by modularizing engine scripts and reducing `template.html` by nearly 3,000 lines.
- **Spec:** 3 of 4 findings resolved (P1, P2, P4 verified). Worst defect: **P3** (HUD "Contract Marked Graph" button throws runtime `ReferenceError` due to `handleFoldReduction` being trapped inside tap callback scope).
