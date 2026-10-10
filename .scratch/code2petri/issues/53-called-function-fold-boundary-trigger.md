# 53: Called-function folding does not trigger at an entrance/exit boundary

**What to build:** Allow an existing Choice reduction over parallel transitions owned by the selected called function when its shared entrance or exit place belongs to the caller. Expose eligible function-internal split/merge places to the normal green highlight and place-fold action, and let Fold-Entire-Function finish both reported shapes without consuming caller boundaries or losing Component-Local Unfold history.

**Related phase:** Phase 2.8 — Fold-Entire-Function and existing boundary folding, separate from Phase 2.10 Function Return Metadata.

**Related ticket:** [47 — Fold-Entire-Function](./47-fold-entire-function-compound.md).

**Blocked by:** None; reproduction and controlled diagnosis are complete.

**Status:** ready-for-agent

- [x] Identify the affected generated viewer, called-function occurrences, and symptom. "Opposite side" means graph direction, not layout.
- [x] Reproduce the reported absence of green highlights and incomplete Fold-Entire-Function results; minimize both shapes to seven nodes and six arcs.
- [x] Distinguish rejected boundary eligibility from a missing internal trigger using controlled probes; rule priority does not cause these stalls.
- [ ] Add failing regressions through the actual generated-viewer/headless seam for exit-side splitting and entrance-side merging, including green highlights, individual place folding, and the sidebar Fold-Entire-Function action. Both must complete through existing Choice followed by Sequence reductions.
- [ ] Validate a Choice bundle by ownership of the transitions it consumes. Shared caller-owned places may serve as retained anchors; do not broadly remove function-boundary guards or combine unresolved functions merely because their transitions share a destination.
- [ ] Make an eligible entrance-side Choice reachable from a function-internal place. Keep detection, highlights, individual folding, Batch Place Fold, and Fold-Entire-Function consistent. Do not add arbitrary caller places to the function's batch loop.
- [ ] Preserve caller and sibling nodes, caller-owned boundary places and tokens, exterior connections, names, weights/SM, and local unfolding of nested consumed components. Verify containment when caller boundaries have additional unrelated branches and when nested functions remain unresolved.
- [ ] Retain complete/partial/no-progress reporting, a single final layout, and zoom/pan preservation. Legitimately unsupported graphs may still stop partially; no whole-net fallback, new mathematical reduction rule, or changed token-flow semantics is introduced.
- [ ] Re-run the original Aeroblasters graph against the corrected engine and verify all four affected call occurrences. Newly generated HTML must embed the corrected engine; the already exported HTML does not update automatically.

## Report

### 2026-10-10 — User report during Phase 2.10 design

"I can't fold a called function when its entrance or exit is not resolved into one place (the fold mechanic is not triggered when either entrance or exit is on the opposite side of the other)."

Existing Fold-Entire-Function permits partial completion; that contract alone does not explain this report.

### 2026-10-10 — Reproduction details supplied

- Affected viewer: [aeroblasters_global_foldable.html](</Users/pingchungtsai/My Drive (ric6121824@gmail.com)/Digital Media MSc/Semester 4/Graph Data/output_code2petri/Aeroblasters-261010/aeroblasters_global_foldable.html>).
- Affected functions: `BlinkingText.update()` and `Message.update()`.
- Symptom: the relevant place is not highlighted foldable green, and the called function cannot be reduced entirely into a component node.
- "Opposite side" describes graph connections, not rendered positions.

## Comments

### 2026-10-10 — Reproduction and diagnosis

The supplied HTML's embedded engine matches the current repository engine. Replaying its actual embedded net reproduces the stall in all four matching call occurrences: one `BlinkingText.update()` and three `Message.update()` compounds. Each stops with one internal place and three transitions, without an eligible green internal place or complete collapse.

The minimized remainder shapes are:

```text
BlinkingText.update(): caller entry -> linear transition -> internal place
                      -> {two parallel transitions} -> caller exit

Message.update():     caller entry -> {two parallel transitions}
                      -> internal place -> linear transition -> caller exit
```

All three transitions belong to the called function; the shared outer places belong to the caller after [boundary place unification](../../../docs/adr/0002-boundary-place-unification.md).

Controlled probes identify two obstructions in [the reduction engine](../../../code2petri/viewer/engine/reduction_engine.js):

- `detectChoiceCandidates` rejects otherwise parallel function-owned transitions when a shared source or sink place has a different parent and the function is not already collapsed. Bypassing only those checks in memory allows Choice then Sequence to complete the exit-side shape.
- For the entrance-side shape, the current Choice trigger is the caller's exterior source place. `executeFoldEntireFunction` considers only descendant places, so it still stalls after the boundary-check bypass. Applying that Choice directly in the diagnostic replay lets the existing function action complete while retaining both caller boundaries.
- Rule-priority bypass does not help either internal place; no elementary reductions were available in the baseline. No new reduction type is needed for these examples.

The portable [diagnostic replay and notes](../debug/called-function-boundary-folding/README.md) preserve both minimal cases. Running `node .scratch/code2petri/debug/called-function-boundary-folding/repro.cjs` from the repository root currently exits 1 with two failures. This is diagnosis evidence, not a passing regression or production fix.

Ticket 47's containment contract remains: consumption stays inside the selected function and its descendants. Its prohibition on exterior triggers is refined here only for a retained caller boundary anchoring a verified function-owned Choice bundle. The internal-place affordance must make this usable without requiring the user to select a caller place.
