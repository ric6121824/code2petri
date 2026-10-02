# Code Review: Phase 2.7 (Live Fold Reduction) — Round 03

**Commit:** [`acfda18`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html) (`refactor(viewer): resolve Phase 2.7 full review round 2 findings`)  
**Diff:** `git diff 4c8085b...HEAD` (12 files changed, 235 insertions(+), 84 deletions(-))  
**Master Spec:** [`.scratch/code2petri/specs/phase-2.7-live-fold-reduction.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/specs/phase-2.7-live-fold-reduction.md)  
**Previous Review:** [`.scratch/code2petri/reviews/phase-2.7-full-review-round-02.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/reviews/phase-2.7-full-review-round-02.md)  
**Standards:** [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) and Fowler 12-smell baseline  
**Test Suite:** All 104 viewer & prototype tests pass; full repository test suite (`python3 -m unittest discover tests`) passes.

---

## Standards

### (a) Verification of Round 2 Findings
**Status: PASS (0 Hard Violations).**
All documented standards violations and smells flagged in Round 2 were resolved:

1. **H1: Prohibited Term in Export API ([`CONTEXT.md:27-30`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md#L27-L30)) → ✅ RESOLVED**
   - Removed `downloadPnmlFile` alias from [`pnml_exporter.js:218-234`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/engine/pnml_exporter.js#L218-L234).
   - Updated prototype export call to `exportClientSidePnml` in [`prototype/index.html:1546`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/prototype/index.html#L1546).
   - Cleaned test harness regex in [`tests/test_html_viewer.py:91`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L91).

2. **H2: Prohibited Vocabulary in Master Spec ([`CONTEXT.md:7-10`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md#L7-L10)) → ✅ RESOLVED**
   - Replaced `"JS reduction math"` with `"Live Fold Reduction math"` in [`.scratch/code2petri/specs/phase-2.7-live-fold-reduction.md:50`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/specs/phase-2.7-live-fold-reduction.md#L50).

3. **J1: Mysterious Syntax in Inline Script Tag → ✅ RESOLVED**
   - Replaced `<!-- {{ENGINE_SCRIPTS}} -->` with valid JS block comment placeholder `/* {{ENGINE_SCRIPTS}} */` in [`template.html:1569`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1569).

4. **J2: Middle Man Prototype Facades → ✅ RESOLVED**
   - Deleted obsolete facade files `code2petri/viewer/prototype/reduction_engine.js` and `pnml_exporter.js`. Prototype index, runner, and tests now import directly from `code2petri/viewer/engine/` ([`run_prototype.py:33-34`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/run_prototype.py#L33-L34), [`tests/test_live_fold_prototype.py:23-24`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_live_fold_prototype.py#L23-L24)).

---

### (b) Baseline Code Smells in New Diff (Judgement Calls)

1. **Speculative Generality & Duplicated I/O ([`code2petri/viewer/__init__.py:63`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/__init__.py#L63))**:
   ```python
   _CACHED_TEMPLATE = raw_template.replace("/* {{ENGINE_SCRIPTS}} */", _load_engine_scripts()).replace("<!-- {{ENGINE_SCRIPTS}} -->", _load_engine_scripts())
   ```
   - *Analysis*: The chained `.replace("<!-- {{ENGINE_SCRIPTS}} -->", ...)` is a dead fallback for an HTML comment format no longer present in `template.html`. Moreover, it invokes `_load_engine_scripts()` a second time unconditionally, executing duplicate disk reads on both JS files during template caching.
   - *Recommendation (Non-blocking)*: Remove the dead replacement branch:
     ```python
     _CACHED_TEMPLATE = raw_template.replace("/* {{ENGINE_SCRIPTS}} */", _load_engine_scripts())
     ```

---

## Spec

### (a) Verification of Round 2 Findings
**Status: PASS (All Acceptance Criteria Satisfied).**

1. **P3: HUD Marked Graph Contraction Runtime Trigger → ✅ RESOLVED**
   - *Spec Line 40:* *"Left-Click (Transition/Component): Open floating HUD popover for metadata inspection... and explicit structural fold actions (e.g. 'Contract Marked Graph')."*
   - In [`template.html:1626-1650`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1626-L1650), `handleFoldReduction` was hoisted out of `cy.on('tap', 'node')` to viewer scope. The HUD Marked Graph click handler ([`template.html:1536`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1536)) now successfully invokes it without throwing `ReferenceError`.
   - The test harness in [`tests/test_html_viewer.py:80, 277, 288`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L80) was updated to extract and exercise the hoisted handler directly.

2. **Edge Case: `parentPlace` Pruning in Single-Place Contraction → ✅ RESOLVED**
   - *Spec Line 13:* *"When an entire inline expansion (a compound node) is fully folded from the inside out, it transitions into a 'Collapsed Compound State'..."*
   - In [`reduction_engine.js:960`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/engine/reduction_engine.js#L960), candidate compound inspection now includes `parentPlace` (`[parentSrc, parentSnk, parentPlace]`), deduplicating candidates. When a place's parent container is emptied by contraction, it is recorded in `consumedCompounds`, pruned from the canvas, and restored upon unfold. Verified by [`test_single_place_contraction_prunes_place_parent_compound_headless`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L3850).

---

### (b) Acceptance Criteria & Scope Verification
- **User Stories 1–10:** Fully satisfied across initial composite net assembly, nested compound rendering, place-centric live folds (Sequence, Choice, While Loop), macro SESE contractions (Marked Graph, State Machine, Well-Structured, Unstructured Knots), non-linear component-local unfold, floating HUD popover with running SM score & component renaming, and pure client-side PNML export.
- **Scope Creep:** None.
- **Incorrect Behavior:** None.

---

## Summary

- **Standards:** PASS (0 hard violations; export API cleaned of legacy aliases, master spec vocabulary aligned, valid JS placeholder adopted, obsolete prototype facades removed). Only 1 non-blocking cleanup noted (eliminate dead fallback `.replace` in `viewer/__init__.py`).
- **Spec:** PASS (All 10 User Stories and implementation decisions met; HUD Marked Graph contraction runtime crash resolved, place parent compound pruning fixed, 104 viewer/prototype tests pass).
