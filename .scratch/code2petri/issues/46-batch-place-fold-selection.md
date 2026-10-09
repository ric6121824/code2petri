# 46: Batch Place Fold from Box Selection

**What to build:** Drag a selection rectangle around places, then use "Fold Selected Places" in the sidebar to apply one pass of existing local reductions to the selected places.

**Blocked by:** 45 — Docked Sidebar Inspector.

**Status:** resolved

- [ ] A box-selection gesture selects places without folding them. Finishing the drag does not also trigger a place-click fold; ordinary clicks, right/middle-drag panning, and wheel zoom retain their existing behavior.
- [ ] "Fold Selected Places" appears when at least two places are selected. Selected transitions and compounds do not count toward the threshold or become fold triggers.
- [ ] Activating the action captures the selected places in current graph order and evaluates each original place ID exactly once against the graph as it exists at that moment.
- [ ] Each evaluation applies at most one successful reduction, using existing Sequence, Choice, then While eligibility and weighting rules. Missing or non-contractible places are skipped; structural macro reductions are outside this batch action.
- [ ] Only originally selected places act as triggers. Earlier places are not revisited if they become eligible later, and a surviving Choice boundary place is not automatically folded again in this pass.
- [ ] Existing reduction rules determine participating neighboring transitions and boundary rewiring. Unselected places are preserved, and the action does not widen into an automatic whole-net reduction.
- [ ] The single-pass behavior is reusable for an ordered set containing one or more places, independently of sidebar selection; the two-place minimum applies only to button visibility.
- [ ] Successful folds retain hierarchy, weights, names, and Component-Local Unfold records. After the batch, refresh the graph, sidebar, fold affordances, and SM while retaining zoom and pan, with one final layout instead of camera movement between individual folds.
- [ ] The sidebar reports successful reductions and skipped places, including a no-progress result. Partially folded selections remain usable.
- [ ] Verification covers the real selection/button interaction and reduction behavior: mixed eligibility, ignored non-place selections, stale IDs, a Choice whose boundary place survives, an earlier skipped place enabled later, and viewport preservation.

## Answer

Implemented one-pass selected-place folding and selection controls, including skipped/no-progress reporting, batched layout, and camera preservation. The focused viewer/live-fold regression suite passed (130 tests). Manual browser verification was not run.
