# Code Review: Ticket 40 (Viewer: Component-Local Unfold) — Round 01

**Commit:** [`2d5ba44`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/40-viewer-component-local-unfold.md) (`feat(viewer): implement component-local unfold (ticket 40)`)  
**Diff:** `git diff 6a29124...HEAD` (3 files changed, 660 insertions(+), 24 deletions(-))  
**Spec:** [`.scratch/code2petri/issues/40-viewer-component-local-unfold.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/40-viewer-component-local-unfold.md)  
**Standards:** [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) and Fowler 12-smell baseline  
**Test suite:** 81 tests pass (though 1 test has severed assertions).

---

## Standards

### (a) Documented Standards Violations (Hard Standards)

1. **Severed Preceding Test Assertions ([`tests/test_html_viewer.py:3668-3670`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L3668-L3670))**:
   - A bad hunk insertion boundary accidentally clipped the assertion tail of `test_collapsed_compound_inspector_details_headless`:
     ```python
             node_script = _setup_live_fold_test_harness(net_literal, test_logic)
             proc = _run_node_script(node_script)
         def test_unfold_opaque_component_right_click_headless(self):
     ```
     The verification lines (`self.assertEqual(proc.returncode, 0, ...)` and `self.assertIn("PASS", proc.stdout)`) were deleted, leaving the preceding test without execution verification.
   - **Actionable Fix:** Restore the missing assertion lines at the end of `test_collapsed_compound_inspector_details_headless`.

2. **Domain Vocabulary Drift — Opaque Transition vs. "Opaque Component" ([`CONTEXT.md:19-22`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md#L19-L22))**:
   - While adhering to `Component-Local Unfold` and avoiding forbidden terms (*Local undo*, *node expansion*), the diff introduces `type: 'opaque_component'`, `_unfoldSingleComponent()`, and code comments referencing "opaque component" instead of the standard domain term `Opaque Transition`.
   - **Actionable Fix:** Align return types and method naming with `Opaque Transition` (or `Opaque Transition / Component` domain conventions).

### (b) Baseline Code Smells (Judgement Calls)

1. **Duplicated Code — Boundary In/Out Arc Restoration ([`code2petri/viewer/template.html:1858-1907`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1858-L1907))**:
   - In-arc and out-arc boundary restoration duplicate identical Cytoscape edge resolution logic, fallback ID construction, and element insertion.
   - **Actionable Fix:** Extract a shared helper `_reinjectBoundaryArc(sourceId, targetId, bArc, idx)` in `LiveFoldReductionEngine`.

2. **Primitive Obsession — Ad-hoc Node State Predicates ([`code2petri/viewer/template.html:1927-1970`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1927-L1970))**:
   - Ad-hoc combinations of classes and boolean flags (`hasClass('collapsed-compound') || data('is_collapsed_compound') === true || Boolean(data('collapsed_opaque_id'))`) are repeatedly re-checked across methods.
   - **Actionable Fix:** Encapsulate node type checks into clean predicate helpers (`isCollapsedCompound(node)`, `isOpaqueTransition(node)`).

3. **Speculative Generality — Timestamped IDs and Arbitrary Loop Guards ([`code2petri/viewer/template.html:1867, 1893, 1948`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1867))**:
   - Generates non-deterministic edge IDs using `Date.now()` on collision, and employs an arbitrary `maxPasses = 100` loop counter rather than deterministic net state traversal.
   - **Actionable Fix:** Use deterministic edge naming based on boundary node IDs and index, and loop strictly while valid internal unfold candidates exist.

---

## Spec

### (a) Missing or Partial Requirements

1. **Nested Compound Fold Isolation (Partial)**:
   - *Spec Line 12:* `"- [x] Other folded components on the canvas are not affected by the unfold operation"`
   - *Finding:* `_findInternalOpaqueChild` recursively collects all descendants: `if (n.hasClass('compound')) collectDescendants(n.id())`. If an outer compound contains a nested inlined function compound with its own folded opaque transition, right-clicking the outer compound cascades into the inner compound and destroys its folded state.
   - **Actionable Fix:** Restrict `_findInternalOpaqueChild` to direct children of `compoundId` (`n.data('parent') === compoundId`), preserving folds inside nested sub-compounds.

2. **Boundary Arc ID Preservation (Partial)**:
   - *Spec Line 11:* `"- [x] Arc connections at the boundary are correctly restored to the original elements"`
   - *Finding:* While topological connections, weights, and classes are restored, sequence reductions did not store the original `edge.id()` in `boundaryInArcs`. During unfold, restored edges receive synthetic IDs (`arc_restore_...`) instead of their original identifiers.
   - **Actionable Fix:** Ensure fold step records capture original boundary edge IDs and restore them faithfully.

### (b) Scope Creep (Behaviour in Diff Not Asked For)

1. **Dead `this.history` Stack Pruning**:
   - *Spec:* `phase-2.7-live-fold-reduction.md:42` (*"Graph mutations in JS will not use a global state array."*)
   - *Finding:* In [`code2petri/viewer/template.html:1910`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1910), `_unfoldSingleComponent` filters `this.history`, retaining dead remnants of a linear global undo stack.
   - **Actionable Fix:** Remove `this.history` filtering.

2. **Unrelated Layout Guard Modification**:
   - Modifies `handleFoldReduction` (line 3726) to guard on `DAGRE_LAYOUT_OPTIONS.name`, which belongs outside Ticket 40 unfold scope.

### (c) Requirements Implemented but Look Wrong

1. **Recursive Cascade into Nested Compounds**:
   - *Spec Description:* *"This unfold is local — other folds made elsewhere on the canvas remain in their folded state, unaffected."*
   - *Finding:* Unfolding an outer collapsed compound should only restore its direct internal logic. Traversing through `descendantIds` into nested compounds violates the non-linear, localized undo guarantee.
   - **Actionable Fix:** Scope unfold operations strictly to direct child nodes of the target container.

2. **Spinning Loop on Unfold Failure**:
   - *Spec Line 10:* `"- [x] Right-clicking a Collapsed Compound State reopens the compound to its fully expanded internal state"`
   - *Finding:* `executeComponentLocalUnfold` runs `while (internalOpaque && maxPasses-- > 0)` without checking if `_unfoldSingleComponent(internalOpaque)` succeeds. If an opaque node lacks a valid `consumedSubnet`, it returns `null` without removing the node, causing an unhandled 100-pass no-op loop.
   - **Actionable Fix:** Break the loop and return failure if `_unfoldSingleComponent` returns null.

---

## Summary

- **Standards (5 findings):** 1 hard test defect (severed assertions in preceding test `test_collapsed_compound_inspector_details_headless`), 1 domain vocabulary drift ("opaque component" vs `Opaque Transition`), 3 baseline smells (duplicated boundary arc restoration, primitive obsession in node state checks, non-deterministic `Date.now()` fallback IDs). Worst issue: Severed test assertions in `tests/test_html_viewer.py`.
- **Spec (6 findings):** 2 partial requirements (nested compound folds destroyed by recursive unfold, synthetic boundary arc IDs), 2 scope creep issues (dead `this.history` pruning, unrelated layout option guards), 2 incorrect implementations (recursive cascade violating fold isolation, spinning loop on missing subnet data). Worst issue: Recursive descent destroying folded state in nested child compounds.
