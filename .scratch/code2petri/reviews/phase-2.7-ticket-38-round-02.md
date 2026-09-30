# Code Review: Ticket 38 (JS Fold Engine: Unstructured Knot Isolation) — Round 02

**Commit:** [`f053f82`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/38-js-fold-engine-unstructured-knot-isolation.md) (`refactor(viewer): implement review round 01 feedback for ticket 38`)  
**Diff:** `git diff a7cf6d2...HEAD` (2 files changed, 143 insertions(+), 134 deletions(-))  
**Spec:** [`.scratch/code2petri/issues/38-js-fold-engine-unstructured-knot-isolation.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/38-js-fold-engine-unstructured-knot-isolation.md)  
**Standards:** [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) and Fowler 12-smell baseline  
**Test suite:** All 69 tests in [`tests/test_html_viewer.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py) pass.

---

## Standards

### (a) Round 1 Verification & Documented Standards
**Status: PASS (0 Hard Violations).**
All documented standards violations and smells flagged in Round 1 were addressed:

1. **Domain Vocabulary Drift ([`CONTEXT.md:63-66, 79-82`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md#L63-L66)) → ✅ RESOLVED**
   - [`tests/test_html_viewer.py:3280`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L3280): Replaced "multiplier option" with `Fold Config penalty weight`.
   - [`tests/test_html_viewer.py:3326`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L3326): Replaced "left-clicking boundary place" with `Place-Centric Fold Trigger`.

2. **Duplicated Code (Unstructured Penalty Calculation) → ✅ RESOLVED**
   - Extracted helper `_calculateUnstructuredOmega(nodeIds, compTrans)` in [`code2petri/viewer/template.html:2651-2693`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L2651-L2693), eliminating duplicate arc counting, weight computation, symmetry products, and $\tau/\omega$ accumulation between minimal knot detection and global fallback.

3. **Repeated Switches (SESE Precedence Cascades) → ✅ RESOLVED**
   - Replaced nested `if` cascades and ad-hoc flags with an ordered `STRUCTURAL_DETECTORS` strategy array and `getActiveStructuralCandidates()` in [`code2petri/viewer/template.html:1915-1959`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1915-L1959).

### (b) Baseline Code Smells in New Diff (Judgement Calls)

1. **Duplicated / Redundant Code — Boundary Map Resolution ([`code2petri/viewer/template.html:3230-3239`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L3230-L3239))**:
   - `boundaryTypeMap` pre-indexes boundary IDs from `activeStructural`, but `foldEngine.getFoldType(p)` already searches `activeStructural` internally. Consequently, `|| boundaryTypeMap.get(p.id())` is redundant.
   - **Recommendation (Non-blocking):** Either consume `boundaryTypeMap` directly to avoid re-evaluating `getActiveStructuralCandidates()`, or drop `boundaryTypeMap`.

2. **Speculative Generality — Unused Tier Metadata ([`code2petri/viewer/template.html:1918, 1927, 1935`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1918))**:
   - `foldTypes` is declared on each strategy object in `STRUCTURAL_DETECTORS` but is never referenced, as detector keys are read directly from `run()` output.
   - **Recommendation (Non-blocking):** Prune the unused `foldTypes` property unless planned for future registry lookups.

---

## Spec

### (a) Round 1 Verification & Acceptance Criteria
**Status: PASS (All Requirements Satisfied).**

1. **Round 1 Findings Resolution → ✅ RESOLVED**
   - Docstrings updated, penalty computation deduplicated, and precedence cascades refactored into strategy detectors without functional regressions.

2. **Acceptance Criteria Coverage (5/5 Satisfied)**:
   - **AC1 (Minimal Knot Isolation):** Subnets containing irreducible cycles are isolated and collapsed to minimal SESE components.
   - **AC2 (Preservation of Surrounding Flow):** Unaffected surrounding structured control flow remains eligible for subsequent reductions.
   - **AC3 (Penalty Formula):** Correct ProM penalty calculation verified against Python `_calculate_unstructured_omega()`.
   - **AC4 (Global Fallback):** When no internal SESE pair exists and $>1$ transitions remain, the entire remaining net collapses safely.
   - **AC5 (Math Parity):** Exact $\tau$ and $\omega$ matches verified against Python engine across all test fixtures.

### (b) New Scope Creep or Defects
- **None.** Commit `f053f82` strictly refactors the identified review findings. All 69 tests pass.

---

## Summary

- **Standards:** 0 hard violations, all 3 Round 1 findings resolved (docstring domain terms, `_calculateUnstructuredOmega` helper extraction, `STRUCTURAL_DETECTORS` strategy array).
- **Spec:** All 5 acceptance criteria verified and satisfied; math parity and Lassen Def. 21 precedence order fully intact.
