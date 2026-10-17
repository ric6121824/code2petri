# Human Verification Update — Phase 2.8, Ticket 66, Round 04

**Verification date:** 2026-10-17
**Ticket:** [66 — Function-Scoped Structural Folding](../issues/66-function-scoped-structural-folding.md)
**Specification:** [Phase 2.8 — Viewer Interactive Enhancements](../specs/phase-2.8-viewer-interactive-enhancements.md)
**Overall result:** Partial pass. The saved-session replay and three reported function folds pass by user confirmation. The large batch-fold failure is fixed and manually browser-checked by the user. The distinct new-save validation failure is fixed, and the supplied 2026-10-17 save now passes snapshot parsing; browser reopen and continued editing have not been repeated.
**Prior reports:** [Round 02](./phase-2.8-ticket-66-round-02.md), [Round 03](./phase-2.8-ticket-66-round-03.md)

## Confirmed verification updates

The user reports that the saved-session browser replay passed and that these occurrences now fold in reasonable time:

- `GameState._coerce_direction()` in `_edge_for_move()`.
- `GameState._coerce_direction()` in `_adjacent_boxes()`.
- `isBoardFull()`.

The user also reports that the large batch-fold failure described in Round 03 was fixed in commit `4f8de6d3acb6eab6151e37febfcb0725dbf2ed65` and manually browser-checked. This supersedes Round 03's pending status for that batch-fold case. This report did not repeat the browser check.

## New finding — the 2026-10-17 session save failed snapshot validation

The user can open the 2026-10-13 save but cannot open the 2026-10-17 save. The new save reports:

```text
Invalid Fold State Snapshot: graph element.call_results[0].transition_id does not match its owning transition
```

Read-only replay using the current `parseFoldStateSnapshot()` confirmed the difference:

```text
Tic_Tac_Toe-261013/tic_tac_toe_global_foldable_session_save.json: PASS
Tic_Tac_Toe-261017/tic_tac_toe_global_foldable_session_save.json: FAIL
```

The older snapshot has no `call_results` records. The newer snapshot has 62 such records; 8 have an owner-ID mismatch across live graph elements and nested restoration data. For example, a cloned transition is owned by `inline_create_board__t1`, while its record still contains `transition_id: "t1"`. Similar mismatches occur on cloned `generate_boxes` transitions such as `inline_generate_boxes__t2`, `__t8`, and `__t9`.

### Cause

During inlining, [`_splice_callee_net()`](../../../code2petri/inline.py#L196) prefixes each cloned transition ID, then shallow-copies its metadata without updating `metadata.call_results[*].transition_id`. The viewer consequently saves the cloned graph ID and the original callee-local transition ID together. The snapshot validator requires the record's `transition_id` to equal its owning element ID in [`session_snapshot.js`](../../../code2petri/viewer/engine/session_snapshot.js#L154) and [`session_snapshot.js`](../../../code2petri/viewer/engine/session_snapshot.js#L194), so it correctly rejects the inconsistent record under the current schema invariant.

The evidence points to an inlining metadata-remap defect, not corruption of the JSON save. The mismatch is already present in the graph records and is repeated inside restoration snapshots; it is not introduced by loading.

### Suggested repair and verification

- When cloning a transition in `_splice_callee_net()`, copy each `call_results` record and set its `transition_id` to that clone's prefixed `new_id`. Preserve the original `call_site_id`, caller identity, expression, and source location.
- Add a regression for an inlined callee transition carrying call-result metadata. Assert that the cloned graph metadata and any folded/restorable copy use the cloned transition ID, then serialize and parse the resulting session snapshot.
- Decide whether already-created 2026-10-17 snapshots need a narrow compatibility migration. If so, only remap a call-result owner when the current owner is an inlined ID and the stored ID matches its local suffix; otherwise retain strict validation. Regenerating the save with corrected metadata is the simpler path when preservation of this exact artifact is unnecessary.
- Reopen the supplied 2026-10-17 save after the repair and confirm save/open continuation. Keep the successful 2026-10-13 replay as separate evidence; it does not cover newer `call_results` metadata.

## Implementation follow-up

Inlining now copies each transition's `call_results` records and assigns the cloned transition ID, preserving the original call-site identity, caller metadata, expression, and source location. Snapshot loading also performs a narrow compatibility migration for older version-1 saves: for graph nodes and serialized net transitions whose IDs are inlined IDs, it repairs a record only when its current `transition_id` exactly matches the local suffix after the last `__`. Other mismatches remain rejected by strict validation.

Regression coverage exercises an inlined Python callee with call-result metadata, verifies that the source record is unchanged and preserved metadata survives, and serializes/parses graph restoration data with the cloned ID. A second test checks migration for live graph records, nested restoration records, and `originalNet`, while confirming unrelated mismatches still fail. Read-only parsing of the supplied 2026-10-17 save now passes (308 graph elements; step counter 138). This validates parser acceptance, but does not repeat the browser reopen/continued-editing check requested above.

## Remaining Ticket 66 acceptance

The folding examples and saved-session replay noted above are passed by user confirmation. The batch-fold no-op is also reported fixed and manually browser-checked. The parser now accepts the supplied newer save after its narrow compatibility migration; browser reopen/continued-editing confirmation remains outstanding. Other caller/sibling, nested-container, stale-trigger, weight/SM, hierarchy/viewport, and exact-unfold criteria remain subject to the Ticket 66 checklist; this report does not mark them complete.

**Disposition:** The old saved-session browser replay is **passed**, and the large batch-fold failure is **fixed and manually browser-checked** per the user. The supplied newer save's `call_results.transition_id` mismatch is **fixed for new inlines and migrated narrowly for existing version-1 saves**; direct browser reopen/continued-editing confirmation and the other unchecked acceptance cases remain pending. Ticket 66 remains partially verified.
