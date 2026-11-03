# Phase 2.8.2 — Code Review and Fold/Unfold Finding

**Review date:** 2026-11-03

**Comparison:** `git diff 64e456f...HEAD`

**HEAD:** `b83875b` (`docs: publish phase 2.8.2 spec and tickets 71-73`)

**Specification:** [Phase 2.8.2 — Call Refolding and Exit Preservation](/Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/specs/phase-2.8.2-call-refolding-and-exit-preservation.md)

**Standards result:** No documented-standard violations or actionable baseline smells found.

## User-reported Fold/Unfold bug

The user reports that every Fold of `GameState._coerce_direction()` creates a new component node labeled `c_x`; Unfold leaves that node behind; the next Fold creates another component with the next ID. This is an accumulation bug. The `c_x` naming itself is expected: the viewer assigns sequential IDs when it creates reduction components.

### Saved-session evidence

The supplied [session save](/Users/pingchungtsai/Downloads/backend-inlined_session_save.json) has `engine.stepCounter: 4` and contains live components `c_01`, `c_02`, and `c_04`; `c_03` appears inside `c_04`'s restoration subnet. The saved `originalNet` has no `c_x` components, so these were created during viewer folding. `c_01` is a Sequence reduction of the transitions for `if isinstance(direction, Direction)` and `return direction`, across the intermediate place in the `_coerce_direction()` occurrence nested under `_adjacent_boxes()`.

The live `c_01`, `c_02`, and `c_04` nodes have no `data.parent`, while their `consumedSubnet.parentCompound` points to that nested `_coerce_direction()` container. In this snapshot `c_01` also has a direct route from `p6` to `_adjacent_boxes()`'s normal continuation, in parallel with the restored call transition. A read-only graph check found both routes:

```text
normal p6 -> ... -> p1 routes:
['inline_GameState._adjacent_boxes__t1', 'c_01']
```

This is consistent with Fold leaving reduction components outside the function's live hierarchy, so function-level Unfold does not remove them. The component allocator advances for each new reduction; it is not reusing or misnaming the IDs. The saved snapshot has no action-event log (`foldSteps` empty; playback at 0/0), so the exact sequence of clicks is based on the user's reproduction rather than reconstructed from the file.

Relevant implementation paths: component IDs are allocated during sequence contraction in [reduction_engine.js](/Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/engine/reduction_engine.js:1096); local Unfold restores the selected opaque component's consumed subnet in [reduction_engine.js](/Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/engine/reduction_engine.js:839). The saved live-parent mismatch indicates that the generated component is no longer owned by the function when Unfold runs. The exact point where ownership is lost still needs tracing against the same generated HTML/build used for the manual reproduction.

**Disposition:** Treat this as a Fold/Unfold lifecycle defect, separate from whether `c_x` is a valid component ID. Fixing the behavior must remove or restore every reduction created by the function Fold so repeated Fold/Unfold cycles do not leave extra nodes or duplicate caller routes.

**Artifacts:** Generated HTML under `/private/tmp/code2petri-phase-2.8.2/backend-inlined.html`; saved progression `/Users/pingchungtsai/Downloads/backend-inlined_session_save.json`.

## Standards

No documented-standard violations or actionable Fowler baseline smells found in the reviewed diff.

## Spec findings

### 1. Browser call expansion still uses a single sink

`findBoundaryPlaces()` selects one sink, and `applyExpansion()` splices that sink into the caller's normal postset. The browser path therefore cannot independently connect normal and exceptional completion as required. See [template.html](/Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html:988) and spec requirement: “Identify normal and exceptional boundaries independently by explicit semantic roles and validated provenance. Route normal completion to normal caller continuation and exceptional completion to the paired exception destination, modeled enclosing handler, or exceptional function boundary.” ([spec, Implementation Decisions](/Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/specs/phase-2.8.2-call-refolding-and-exit-preservation.md:90)).

### 2. Incomplete Python reductions can still claim a final score

When reduction stops, `fold.py` assigns `final_sm` from the first remaining transition, or zero when none remains ([fold.py](/Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/fold.py:1209)). The spec says: “Do not substitute the first remaining transition, an arbitrary zero, or the running total as final SM,” and requires Reduction Outcome and score availability to reach the public API and consumers ([spec](/Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/specs/phase-2.8.2-call-refolding-and-exit-preservation.md:101)).

### 3. Passing browser acceptance is not recorded

The spec requires a generated-HTML Dots & Boxes browser run covering both expansion paths, normal and exceptional interfaces, score/status, save/reopen, continued editing, and local unfolding; it states that headless action runs do not replace browser acceptance ([spec, Browser acceptance](/Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/specs/phase-2.8.2-call-refolding-and-exit-preservation.md:123)). The user has manually tested the generated HTML and reported the Fold/Unfold accumulation defect, but that is not a passing acceptance record for the required scenarios.

## Summary

- **Standards:** 0 findings.
- **Spec:** 3 findings: browser expansion does not route outcomes separately; incomplete Python reduction can claim an invalid final SM; passing browser acceptance remains unrecorded.
- **Additional runtime defect:** repeated function Fold/Unfold leaves generated `c_x` components in the graph, and subsequent folds accumulate more components.
- **Verification performed:** read-only inspection of the supplied saved-session JSON and graph connections. No code changes, automated test run, or browser replay was performed.

## Follow-up inspection and implementation instructions — 2026-11-03

This section supplements the original review above. Its verification statements apply to this follow-up only. Preserve the original observations as historical evidence; use the build identities and confirmed cause below for the repair.

### 1. Correct the implementation-review baseline

The original comparison ends at `b83875b90fc2a8082cbe8fe162ac4025e344ecd6`, which publishes the Phase 2.8.2 specification and tickets but does not contain their implementation. The browser artifact comes from the later integration implementation. Findings 1 and 2 describe the older checkout and must not be treated as newly demonstrated defects in that integration implementation.

- **Implementation branch inspected:** `codex/phase-2.8.2-call-refolding`, at `d6b9a7973d8dfc0ac6faf7caab031eb7e9fe839f`.
- **Implementation review comparison:** `git diff b83875b90fc2a8082cbe8fe162ac4025e344ecd6...d6b9a7973d8dfc0ac6faf7caab031eb7e9fe839f`.
- **Integration worktree:** `/private/tmp/code2flow-phase-2.8.2-integration`.
- **Generated backend-inlined artifact:** `/private/tmp/code2petri-phase-2.8.2/backend-inlined.html`, SHA-256 `d30dd0dc91d63986df1b092bed10a26253f6ad3467389213f70d72d70659d170`. The integration tracking record identifies its generator commit as `10c7553b1c8459e0777ee2790a076123de88c0f7`.
- **Saved progression inspected:** `/Users/pingchungtsai/Downloads/backend-inlined_session_save.json`, SHA-256 `54958fa266b8afb6cf7e119ae1a0715a75ae1ee3ee7b876196b7e622e98d45f8`.

The artifact embeds the integration worktree's reduction engine exactly. Its `findBoundaryPlaces`, `handleFoldEntireFunction`, and `performComponentLocalUnfold` functions also match that worktree. They do not match the older main checkout. The integration already contains separate normal/exception boundary handling and incomplete-result reporting; the focused checks listed below pass. Re-review the actual implementation and its consumers before carrying either old finding forward or declaring either ticket fully accepted. The original Standards result does not establish a standards review of the newer implementation.

### 2. P1 — Fix post-reduction cleanup in Ticket 71

**Confirmed cause:** The backend-inlined branch of `handleFoldEntireFunction` collects `localNodeIds` from `beforeElements`, runs `executeFoldEntireFunction`, and then removes elements using that original ID set. Automatic structural reductions create new component IDs which are absent from the set. Those new components survive while their function container is removed. Graph reconstruction leaves them at the root, alongside the restored opaque call and its routes.

The relevant integration implementation is the backend Call Refolding branch in `code2petri/viewer/template.html`: the pre-action collection begins around line 2648, reductions run around line 2678, and the incorrect post-reduction filter is around lines 2697–2700. These are integration-worktree line references, not references to the older main checkout.

Instrumentation of `_createOpaqueComponentNode` confirmed that `c_01` through `c_04` have the correct `_coerce_direction()` parent at creation. Thus the saved missing-parent state is a consequence of the refolding cleanup; it does not establish that Sequence contraction initially assigns the wrong parent. Do not start by resetting component IDs or changing their labels.

The affected occurrence is `GameState._coerce_direction()` nested under `GameState._adjacent_boxes()` in the backend-inlined artifact. Its production-handler replay produced:

| Completed Fold/Unfold cycle | Extra live reduction components after Unfold | Accumulated Reduction Weight |
| --- | --- | --- |
| 1 | `c_01`, `c_02`, `c_04` — 3 total | 68 |
| 2 | 6 total | 75 |
| 3 | 9 total | 82 |

Each action performed four reductions; `c_03` was consumed into `c_04` in the first action. The restored call's retained contribution was 13, while the leaked live components added another 7 per cycle. This reproduces the user's accumulation symptom through the production Fold Entire Function and Component-Local Unfold handlers, not merely by inspecting the saved result.

**Implementation steps for Luna:**

1. Keep the exact pre-action local snapshot for Component-Local Unfold. It must include the user's prior manual folds and remain independent of the automatic reductions performed by this action.
2. Separately determine the selected occurrence's post-reduction removal set before removing its container. Include its surviving live descendants and the applicable original local IDs. Account for components generated by this scoped action, using validated ownership and action results where containers have been pruned or replaced. Do not rely exclusively on pre-action IDs, an ID prefix, or a global counter range.
3. Before inserting the opaque call and its exception alternatives, remove the post-reduction function representation and every incident arc of the removed nodes. Preserve retained caller boundary places, unrelated components, sibling occurrences, and their arcs. Validate the replacement graph before rendering it.
4. Keep pre-action restoration data separate from this cleanup set. Fixing only Unfold's removal list is insufficient: leaked components already duplicate the call's routes and contribution immediately after Fold.
5. Preserve the selected function's accumulated contribution once in the restored call representation, including justified structural penalties. Remove the live reduced representation that it summarizes. Preserve alternative outcomes without simultaneous normal/exception firing, and keep container presentation out of operation counting.
6. Retain the existing one-gesture action transaction. A failed validation, splice, rendering operation, or history capture must restore graph state, score/status state, component allocation, and Undo/Redo availability.
7. Inspect the browser-expanded Call Refolding path for the same invariant. Its collapse helper must remove newly created descendants as well as original nodes, while preserving unrelated current edits. Do not assume that a backend-only fix establishes acceptance for both paths.

**Isolated experiment:** In a temporary copy of the generated test harness, expanding the backend removal set with the active compound's post-reduction descendants eliminated the leak. Three cycles left zero extra live components and retained Accumulated Reduction Weight 61 throughout; the call contribution stayed 13. This validates the immediate cause and repair direction on this artifact. It is not a production patch, a complete solution for pruned-container cases, or proof that 61 is final SM. Both the integration worktree and the main checkout's implementation files were left unchanged.

### 3. Add a regression that performs reductions before Call Refolding

The existing `ViewerActionHistoryTests.test_production_fold_entire_function_refolds_backend_inlined_occurrence` passes on the affected implementation. Its fixture has separate return/raise transitions but performs no eligible internal contraction before refolding. It therefore cannot detect a component created between pre-action capture and cleanup.

Add a self-contained source/graph fixture through the existing generated-viewer action seam with at least one eligible Sequence contraction inside a multi-outcome called function. Assert that automatic reduction actually occurs, then exercise the production internal-trigger/function-button and Unfold paths as applicable. Use the real Dots & Boxes artifact as an additional acceptance reproduction, not the only automated fixture.

- Assert immediately after Fold that the call and its alternative outcomes are the only live representation of the removed function interior: no newly generated component remains orphaned, no parallel duplicate caller route exists, and contribution accounting counts the function once.
- Run at least three Fold/Unfold cycles. After each Unfold, compare the exact pre-action local nodes, arcs, weights, tokens, hierarchy, metadata, names, and positions. Verify stable accumulated contribution for equivalent cycles. New component numbers on a later Fold are allowed; leaked components and score inflation are not.
- Start from a function with prior manual reductions. Those pre-existing components must be restored, so do not assert that all `c_x` nodes disappear globally. Verify an unrelated sibling fold and a later independent edit remain intact.
- Cover both browser-expanded and backend-inlined paths, nested occurrences, retained caller anchors, and the caller-handler versus uncaught-exception contexts. Assert actual outcome destinations or reachable behavior, not only node counts.
- Exercise one-gesture Undo/Redo, failure rollback, save/reopen, continued editing, history eviction, and Component-Local Unfold. Verify persistence retains the correct local snapshot and does not reintroduce orphan components or duplicate routes.
- Keep accumulated weight distinct from final-score availability. The lifecycle fix must not turn an unvalidated multi-outcome score into a verified final SM.

**Verification performed during this follow-up:**

- The existing backend-inlined Call Refolding test and uncaught-callee-exception browser-expansion test both passed.
- All seven `TestIncompleteReductionOutcome` tests passed, including preserved multi-exit results and incomplete exports. Nine relevant existing tests therefore passed in total; this is not a full-suite result or complete Ticket 72/73 acceptance.
- The additional real-artifact production-handler probe failed after three cycles with `REGRESSION: Fold/Unfold left 9 generated components`.
- The same probe with only the temporary post-reduction cleanup experiment passed with no leaked components and stable accumulated weight.
- No actual browser interaction was run during this follow-up. The user's manual accumulation failure remains a failed browser check, not a passing acceptance record.

### 4. Acceptance and ticket disposition

Track the accumulation repair and its regressions under [Ticket 71](../issues/71-call-refolding.md); it directly violates that ticket's contribution, exact-restoration, and repeated-cycle criteria. No new ticket is needed merely to rename this defect. [Ticket 72](../issues/72-browser-call-expansion-exits.md) owns browser outcome-expansion parity; [Ticket 73](../issues/73-safe-fallback-and-incomplete-results.md) owns safe fallback and truthful incomplete-result reporting.

After the repair, regenerate both expansion variants from the exact candidate commit. Record generator/source commits and artifact hashes, then run the Dots & Boxes browser matrix: both affected direction-coercion occurrences, expansion/refolding, normal and exceptional routes, score/status display, one-gesture history, save/reopen, continued edits, and exact pre-action local unfolding. Keep failed, passed, interrupted, and unperformed checks explicit.

The mathematical scoring gate remains separate. Keep final SM unavailable until the scoring representation and metric scope satisfy the agreed validation requirement. Correcting the leaked-node total does not approve the disposable exit projection or any other new metric construction. Do not close Ticket 71, claim browser acceptance, or close Ticket 66 on the strength of this follow-up or its temporary experiment.
