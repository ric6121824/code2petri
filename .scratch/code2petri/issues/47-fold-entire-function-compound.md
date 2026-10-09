# 47: Fold-Entire-Function

**What to build:** Select a called-function compound and use "Fold Entire Function" in its sidebar to repeat Batch Place Fold over its descendant places, including nested called functions. Stop when the compound reaches Collapsed Compound State or a complete pass makes no progress; partial completion is valid.

**Blocked by:** 46 — Batch Place Fold from Box Selection.

**Status:** resolved

- [ ] Clicking a compound selects it for inspection. The "Fold Entire Function" sidebar action starts folding; selecting the background alone does not.
- [ ] Each pass refreshes the surviving descendant places and uses Batch Place Fold's graph order, immediate eligibility checks, and Sequence, Choice, and While reductions. It also works when only one descendant place remains.
- [ ] Removed places are skipped. Places that become eligible after their turn can be reconsidered in the next pass.
- [ ] Any successful fold counts as progress, including a Choice that preserves its boundary places. Processing stops after a full pass without successful folds or when the selected compound reaches Collapsed Compound State.
- [ ] Every reduction is contained within the selected call occurrence and its descendants, respecting existing nested-function boundary rules. Caller and sibling nodes, caller-owned boundary places, and unrelated folds are not consumed; exterior connections are maintained by the existing rewiring rules.
- [ ] The action does not introduce additional reduction rules, trigger folds outside the compound, or use whole-net fallback to force completion. A compound requiring other reduction types may remain partially folded.
- [ ] The sidebar distinguishes complete collapse from partial/no-progress results. Already collapsed compounds do not start another reduction loop.
- [ ] Final labels, weights, SM, inspection, and fold affordances reflect the resulting graph. Refresh the layout once and retain zoom and pan throughout the operation.
- [ ] Every resulting component retains existing Component-Local Unfold behavior, including restoration of nested consumed subgraphs. A separate undo operation for the whole batch is not introduced.
- [ ] Verification covers the sidebar action, multiple passes, Choice progress without place removal, one-place remainders, nested compounds, partial completion, containment, local unfolding, and preservation of unrelated folds and the viewport.

## Answer

Implemented the compound-scoped repeated fold action with partial/completion reporting, one final layout, and viewport preservation. The focused viewer/live-fold suite passed (130 tests). Manual browser verification was not run.
