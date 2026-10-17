# Human Verification — Phase 2.8, Ticket 66, Round 02

**Verification date:** 2026-10-17  
**Ticket:** [66 — Function-Scoped Structural Folding](../issues/66-function-scoped-structural-folding.md)  
**Specification:** [Phase 2.8 — Viewer Interactive Enhancements](../specs/phase-2.8-viewer-interactive-enhancements.md)  
**Result:** FAIL — the reported Tic Tac Toe `isBoardFull()` occurrence remains partially folded. Ticket 66's human acceptance has not passed for this scenario.  
**Source inspected/replayed:** working-tree reduction engine at HEAD `1885e6144e000f794f4b15ec645aac9da0f9c60a`; no engine changes were made during diagnosis.  
**Method:** User-reported viewer failure, headless Node.js replay of the saved graph through the production Live Fold Reduction engine, minimized replay, and targeted reachability probes. This records the diagnosis from the same conversation; no new browser interaction or full test suite was run for this report.

## Previous code reviews and their disposition

Ticket 66 was previously reviewed together with Tickets 65 and 67, under filenames associated with Phase 2.10:

- [Tickets 65–67, Round 01](./phase-2.10-tickets-65-67-round-01.md) identified a Ticket 66 defect: scoped boundary validation rejected a valid contained structural candidate when other children of the selected function remained outside it.
- [Tickets 65–67, Round 02](./phase-2.10-tickets-65-67-round-02.md) recorded that finding as resolved after `96b6fb5`, including regression coverage for partial consumption of the selected function, retained caller anchors, unrelated siblings, and stale triggers. Tests were not run during those code reviews.

The earlier Ticket 66 finding remains resolved. This report records a distinct human-verification failure involving a loop back to a retained caller entrance. It does not replace either shared code review or imply their filenames assign Ticket 66 to Phase 2.10. Ownership remains Phase 2.8; no new phase is needed.

## Finding — Function entrance also acts as loop head

### Reproduction artifact

Saved Fold State Snapshot:

```text
/Users/pingchungtsai/My Drive (ric6121824@gmail.com)/Digital Media MSc/Semester 4/Graph Data/output_code2petri/Tic_Tac_Toe-261013/tic_tac_toe_global_foldable_session_save.json
```

- SHA-256: `f05595ea68e622467638a45591f8c3492a30fb5404cfb1aecc85db1c225051a3`.
- Snapshot schema version: `1`; engine step counter: `136`.
- Selected Function Fold Scope: `compound_isBoardFull`.
- Source: `Python-Games/Tic Tac Toe/pygame/logic.py`, function `isBoardFull`, lines 4–9.
- Its nested `check_space()` occurrence is already in Collapsed Compound State as `c_135`.
- Caller-owned retained entrance: `p80` (`merge_t93`); retained exit: `p85`.

The source iterates over the board, returns `False` when `check_space(cell)` succeeds, and returns `True` after the loop finishes. The loop's `else` path returns control to `p80`, the same place used as the function entrance.

**Viewer reproduction:** Open the snapshot in the generated viewer, inspect `isBoardFull()`, and invoke Fold Entire Function. The user reports that the function cannot fully fold. Production-engine replay confirms partial completion.

### Observed result

Replaying `executeFoldEntireFunction('compound_isBoardFull')` against all 422 saved elements produced:

```text
success: true
complete: false
passes: 2
folded: inline_isBoardFull__p3 -> c_137 (Sequence)
message: Function 'compound_isBoardFull' remains partially folded after 1 reduction; no further eligible places were found.
```

`success: true` means one reduction occurred; it does not mean the function completed. The Sequence consumes the remaining route between collapsed `check_space()` and `return False`. The nested function container no longer blocks the remaining graph.

The same failure reproduces in a minimized graph retaining only the selected function, its descendants, their incident arcs, and caller boundary endpoints. After the Sequence fold, its control-flow topology is:

```text
p80 -> for-cell transition -> internal p2
internal p2 -> else transition -> p80
internal p2 -> c_137 (check_space ; return False) -> p85
p80 -> c_103 (loop exit ; return True) -> p85
```

No eligible elementary reduction remains, and scoped structural discovery returns no candidate.

### Cause established by targeted probes

[`SESEInfrastructure._reachability()`](../../../code2petri/viewer/engine/reduction_engine.js#L23) pre-marks the opposite boundary as visited, preventing traversal through that boundary. [`findSESENodes()`](../../../code2petri/viewer/engine/reduction_engine.js#L93) requires the resulting forward and backward node sets to match exactly.

For the minimized graph's intended entrance/exit pair `(p80, p85)`:

```text
forwardReachability(p80, p85) minus backwardReachability(p85, p80)
  = { inline_isBoardFull__t4 }  // else / loop-back transition
backwardReachability(p85, p80) minus forwardReachability(p80, p85)
  = {}
```

Forward traversal starts at `p80` and encounters the loop-back transition. Backward traversal stops at `p80`, so it never follows that place's incoming loop-back arc. The sets differ, rejecting this boundary pair before containment/classification can yield a function-scoped reduction. No place-bounded SESE pair survives in the minimized remaining graph.

[`detectUnstructured(scopeId)`](../../../code2petri/viewer/engine/reduction_engine.js#L2403) also correctly excludes the whole-net fallback for a selected function. Therefore the function action stops at this fixed point rather than forcing completion.

### Controlled diagnostic variation

In a temporary minimized graph, separating the caller entrance from a new function-owned loop-head place, joined by an entrance transition, allowed complete folding: the Sequence was followed by a State Machine reduction, leaving one opaque transition between `p80` and `p85`.

This isolates the shared entrance/loop-head topology as the cause. It is not an approved repair or evidence of correct original-graph weights: adding a transition changes the graph and potentially SM. [ADR 0002](../../../docs/adr/0002-boundary-place-unification.md) explicitly chooses boundary-place unification over synthetic intermediate transitions because of those effects. A generation change using such transitions would require revisiting that decision. The source, saved session, and production engine were not modified; temporary diagnostic files were removed.

## Acceptance impact and required follow-up

Human acceptance for this reported occurrence fails, and Ticket 66 should not be recorded as fully verified. The prior implementation and resolved code-review finding remain part of its delivery history.

The [Phase 2.8 specification](../specs/phase-2.8-viewer-interactive-enhancements.md) and [ADR 0003](../../../docs/adr/0003-adopt-prom-local-reduction-algorithm.md) allow partial outcomes for unsupported shapes; they do not promise every function is reducible. This reproduction establishes the current limitation and the generic stopping message, rather than authorizing a forced fold or proving a replacement reduction mathematically valid.

Follow-up under Phase 2.8 / Ticket 66 should:

- Add a self-contained regression for the original fused-boundary loop and early-return shape at the production engine/generated-viewer seam, preserving the saved-session reproduction as the acceptance reference.
- Determine whether a valid reduction can support this topology while preserving boundary unification, existing SESE/reduction rules, Faithful Translation, and correct weights/SM. Do not bypass reachability or containment checks, force a component class, or use whole-net fallback.
- If the shape remains unsupported, expose the specific shared entrance/loop-head reason instead of only reporting that no eligible places were found, and explicitly document the limitation for acceptance.
- Recheck the internal trigger and Fold Entire Function, caller/sibling preservation, tokens and hierarchy, viewport, save/open continuation, and exact Component-Local Unfold restoration after any repair.
- Retain Ticket 66's other pending acceptance cases, including both Dots & Boxes caller contexts; this Tic Tac Toe failure neither verifies nor invalidates those untested cases.

**Disposition:** Human verification failed for the supplied Tic Tac Toe session; remediation and repeat acceptance remain outstanding. This report documents the finding only and does not claim a fix, new test coverage, or a passing browser/session check.
