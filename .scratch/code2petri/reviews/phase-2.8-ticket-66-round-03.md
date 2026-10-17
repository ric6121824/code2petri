# Human Verification Update — Phase 2.8, Ticket 66, Round 03

**Verification date:** 2026-10-17  
**Ticket:** [66 — Function-Scoped Structural Folding](../issues/66-function-scoped-structural-folding.md)  
**Specification:** [Phase 2.8 — Viewer Interactive Enhancements](../specs/phase-2.8-viewer-interactive-enhancements.md)  
**Overall result:** Partial pass. The saved-session browser replay is now user-confirmed as passed, and three reported function occurrences fold in reasonable time. Broader Ticket 66 acceptance remains open.  
**Prior report:** [Round 02](./phase-2.8-ticket-66-round-02.md)

## Verification updates

The user reports that all of the following now fold in reasonable time:

- `GameState._coerce_direction()` inside `_edge_for_move()`.
- `GameState._coerce_direction()` inside `_adjacent_boxes()`.
- `isBoardFull()`.

The user also confirms that **the saved-session browser replay passed**. This updates the pending replay recorded in Round 02. The report treats these as user-run browser results; no new browser replay was run while preparing this document.

The Round 02 implementation and headless regression evidence remain applicable. They show the fused function-entrance/loop-head topology completing through the validated State Machine reduction, while retaining caller anchors and supporting save/open continuation and exact local unfold in the generated-viewer test seam.

## Related viewer finding — large batch place fold

The user reports a separate issue in the generated Tic Tac Toe viewer at:

```text
/Users/pingchungtsai/My Drive (ric6121824@gmail.com)/Digital Media MSc/Semester 4/Graph Data/output_code2petri/Tic_Tac_Toe-261017/tic_tac_toe_global_foldable.html
```

After `create_board` and `generate_boxes` are folded, selecting `p1` through `p44` reports:

```text
Folded 42 places; skipped 2. Skipped: p11 (No eligible place-targeted reduction.); p12 (No eligible place-targeted reduction.).
```

The graph nevertheless appears unchanged. Static inspection of this generated file found a plausible rollback path:

1. `executeBatchFold()` computes the 42 successful folds and the two skips.
2. The batch handler writes the result text before `ViewerActionHistory` commits the gesture.
3. History then captures the post-fold graph. If that capture throws, `commitGesture()` attempts to restore the pre-action graph and rethrows. The result text is outside that rollback state, so it can continue to say 42 places folded.

The generated viewer contains 176 places, 220 transitions, and 440 arcs. Folded nodes retain restoration records under both `consumedSubnet` and the legacy `consumedSubgraph` alias. History's `canonicalElement()` JSON-clones an element before normalizing aliases, which can duplicate large nested restoration data during a large batch capture. This makes expensive or failing capture a strong hypothesis for the reported all-or-nothing behavior; the exact exception has not been observed, so the root cause is **not confirmed**. A small injected-failure harness reproduced the stale success message alongside graph rollback, but did not reproduce the failure on the user's graph.

This batch-fold issue appears related to the separate batch place folding work (Ticket 46), rather than a failure of Ticket 66's scoped structural reduction. Keep it tracked separately so it does not obscure the Ticket 66 result.

### Suggestions

- Capture the browser-console exception from the 44-place attempt to confirm whether post-action history capture is failing and identify the exact failure mode.
- Keep the batch-fold count provisional until the history gesture commits; on commit failure, replace it with a clear failure result instead of leaving a success count visible.
- Reduce history snapshot work for restoration data by canonicalizing aliases before deep serialization and avoiding repeated copies of unchanged nested subnets. Add a regression using this 44-place Tic Tac Toe case that asserts both the visible result and final graph state.

## Implementation follow-up

The batch handler now writes its result only after `ViewerActionHistory.perform()` returns. If folding or history capture throws, it replaces the result with a visible `Batch fold failed` message. The action history clone removes the legacy `consumedSubgraph` alias while cloning, so a second alias to the same restoration subnet is not traversed or copied. History change detection also compares changed elements by ID instead of serializing the full before and after element arrays before building the entry.

Focused regressions cover a generated 44-trigger batch that reports 44 folds, records one history entry, and undoes to the original graph; an injected post-fold history-capture failure that rolls back and reports failure; and duplicate-alias traversal without mutating the live graph. The headless replay of the supplied viewer's embedded graph (176 places, 220 transitions, 440 arcs) took over a minute preparing the two function folds and was stopped before it reached the selected-place batch. It therefore did not confirm the reported graph result or identify the browser-console exception. The exact cause of the original Tic Tac Toe no-op remains unconfirmed, and human verification of that case is still needed.

Automated validation on 2026-10-17 passed the focused viewer suite (39 tests), JavaScript syntax checking, Python compilation, and `git diff --check`. The full repository run executed 603 tests and ended with one failure and four errors: the prototype runner could not bind a test port; `pygraphviz` and `pytest` are unavailable in the environment; one test expects a missing `PetriNet.initial_net` attribute; and one WalkerProtocol test unpacks a three-value result into two variables.

## Remaining Ticket 66 acceptance

The reported Tic Tac Toe replay and the three function-fold examples above pass according to the user. Do not infer that every unchecked item in the issue is complete. In particular, preserve explicit coverage for caller/sibling contexts, protected nested containers, stale triggers, mathematical weights/SM, hierarchy and viewport, and exact local-unfold restoration across the remaining acceptance fixtures. The two Dots & Boxes occurrences are now reported foldable, but their broader caller-context invariants should remain covered by the existing acceptance checklist.

**Disposition:** The saved-session browser replay is **passed**. Ticket 66 remains **partially verified / ready for human** until the remaining acceptance criteria are checked. The large batch-fold discrepancy is a separate unresolved viewer finding; its capture-failure explanation remains a hypothesis pending the browser-console error or a direct reproduction.
