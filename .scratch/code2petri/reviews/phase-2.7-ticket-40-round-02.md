# Code Review: Ticket 40 (Viewer: Component-Local Unfold) — Round 02

**Commit:** [`58d55b9`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/40-viewer-component-local-unfold.md) (`refactor(viewer): resolve round 1 review findings for ticket 40`)  
**Diff:** `git diff 2d5ba44...HEAD` (2 files changed, 240 insertions(+), 90 deletions(-))  
**Spec:** [`.scratch/code2petri/issues/40-viewer-component-local-unfold.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/40-viewer-component-local-unfold.md)  
**Standards:** [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) and Fowler 12-smell baseline  
**Test suite:** All 83 tests in [`tests/test_html_viewer.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py) pass.

---

## Standards

### (a) Round 1 Verification & Documented Standards
**Status: PASS (0 Hard Violations).**
All documented standards violations and smells flagged in Round 1 were addressed:

1. **Severed Preceding Test Assertions ([`tests/test_html_viewer.py:3670-3671`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L3670-L3671)) → ✅ RESOLVED**
   - Restored execution and output assertions (`self.assertEqual(proc.returncode, 0, ...)` and `self.assertIn("PASS", proc.stdout)`) to `test_collapsed_compound_inspector_details_headless`.

2. **Domain Vocabulary ([`CONTEXT.md:19-22`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md#L19-L22)) → ✅ RESOLVED**
   - Renamed core method to `_unfoldSingleOpaqueTransition`, aligned payload to `type: 'opaque_transition'`, updated error messages, and aligned inline comments with *Opaque Transition*. No forbidden vocabulary (*Local undo*, *node expansion*) introduced.

3. **Duplicated Code (Boundary Arc Restoration) → ✅ RESOLVED**
   - Extracted helper `_reinjectBoundaryArc` ([`code2petri/viewer/template.html:1799-1823`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1799-L1823)), unifying Cytoscape element creation across boundary in-arcs and out-arcs.

4. **Primitive Obsession → ✅ RESOLVED**
   - Encapsulated ad-hoc class/data checks into reusable predicate methods on `LiveFoldReductionEngine`: `isCollapsedCompound(node)`, `isOpaqueTransition(node)`, and `isCollapsedChild(node)` ([`code2petri/viewer/template.html:1630-1651`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1630-L1651)).

5. **Speculative Generality → ✅ RESOLVED**
   - Replaced timestamp-based `Date.now()` edge ID generation with a deterministic counter (`${baseEdgeId}_${++counter}`). Removed arbitrary `maxPasses = 100` guard in `executeComponentLocalUnfold`, replacing it with deterministic traversal and explicit null-result failure handling.

### (b) Baseline Code Smells in New Diff (Judgement Calls)

1. **Middle Man ([`code2petri/viewer/template.html:1909-1911`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1909-L1911))**:
   - `_unfoldSingleComponent` is retained as an uncalled alias delegating directly to `_unfoldSingleOpaqueTransition`.
   - **Recommendation (Non-blocking):** Prune the unused alias and invoke `_unfoldSingleOpaqueTransition` directly.

---

## Spec

### (a) Round 1 Verification & Acceptance Criteria
**Status: PASS (All Requirements Satisfied).**

1. **Nested Compound Fold Isolation → ✅ RESOLVED**
   - `_findInternalOpaqueChild` now queries direct children (`n.data('parent') === compoundId`), preventing traversal into nested sub-compounds. Verified by [`test_unfold_nested_compound_isolation_headless`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L4059).

2. **Boundary Arc ID Preservation → ✅ RESOLVED**
   - `executeSinglePlaceContraction` now records `edgeId: edge.id()`, and `_reinjectBoundaryArc()` reuses `edgeId`. Verified by [`test_unfold_opaque_component_boundary_arcs_headless`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L3845).

3. **Dead `this.history` Stack Pruning → ✅ RESOLVED**
   - Obsolete `this.history.filter` block in `_unfoldSingleOpaqueTransition` was deleted, preserving the component-local undo architecture.

4. **Spinning Loop on Unfold Failure → ✅ RESOLVED**
   - `executeComponentLocalUnfold` now halts and returns `{ success: false, reason: ... }` if `_unfoldSingleOpaqueTransition` returns null. Verified by [`test_unfold_corrupt_opaque_node_fails_safely_headless`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L4132).

5. **Reverted Unrelated Layout Guard → ✅ RESOLVED**
   - Reverted `DAGRE_LAYOUT_OPTIONS.name` guards back to standard `typeof DAGRE_LAYOUT_OPTIONS !== 'undefined'`.

6. **Acceptance Criteria Coverage (5/5 Satisfied)**:
   - **AC1 (Opaque Restoration):** Right-clicking an opaque transition restores consumed nodes and edges.
   - **AC2 (Compound Reopening):** Right-clicking a collapsed compound reopens it to its internal logic.
   - **AC3 (Boundary Arc Restoration):** Boundary connections, weights, classes, and original IDs are faithfully restored.
   - **AC4 (Fold Isolation):** Unfolding is strictly local; sibling and nested compound folds remain unaffected.
   - **AC5 (Re-fold Eligibility):** Restored nodes and boundary arcs are immediately selectable and eligible for subsequent folds.

### (b) New Scope Creep or Defects
- **None.** Commit `58d55b9` strictly refactors the identified review findings. All 83 tests pass.

---

## Summary

- **Standards:** 0 hard violations, all 5 Round 1 findings resolved (severed test assertions restored, vocabulary aligned to `Opaque Transition`, `_reinjectBoundaryArc` helper extracted, predicate helpers added, deterministic collision numbering).
- **Spec:** All 5 acceptance criteria verified and satisfied; nested compound fold isolation, boundary arc ID preservation, and failure safety fully validated.
