# 53: Complete called-function folding at shared boundaries

**What to build:** Users can fold a called function completely when eligible parallel branches inside it share an entrance or exit place owned by the caller. The function's internal place is highlighted green and supports the normal Place-Centric Fold Trigger; Batch Place Fold and Fold-Entire-Function perform the same eligible reductions. Caller boundaries and surrounding functions remain intact, and the resulting components can still be saved, reopened, and locally unfolded.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] Reproduce both reported shapes: an internal split whose parallel transitions converge on the caller's exit, and an internal merge whose parallel transitions originate at the caller's entrance. In each case, all affected transitions belong to the called function.
- [x] Highlight the eligible internal split or merge place green. Clicking it performs the existing Choice reduction in the correct graph direction, retaining both shared places. Batch Place Fold uses the same immediate eligibility check and skips ineligible places as before.
- [x] Fold-Entire-Function completes each reported shape through existing Choice and Single-Place Contraction reductions, including when only one internal place remains. The sidebar reports complete collapse accurately and the function reaches Collapsed Compound State.
- [x] Validate the entire Choice bundle before mutation. A caller-owned place may be a retained anchor, but the reduction must consume only transitions belonging to the same eligible function container. Retain existing protection against combining unresolved nested functions, siblings, or caller transitions.
- [x] Preserve caller-owned boundary places and tokens, unrelated incident arcs, sibling nodes, other folds, component names, and existing weights/Structuredness Metric calculations. Verify this when the shared boundary also connects to unrelated caller or sibling branches.
- [x] Preserve recursive restoration records. Component-Local Unfold restores the exact consumed subgraph, hierarchy, and connections, including earlier components within the newly folded Choice. Save/open followed by continued folding and local unfolding preserves that behavior without component-ID collisions.
- [x] Keep a single final layout and retain zoom/pan for Fold-Entire-Function. Partial/no-progress results remain valid for unsupported graphs; do not introduce a new mathematical reduction, broadly disable function-boundary safeguards, or force completion through whole-net fallback.
- [x] Add regressions at the generated-viewer/headless action seam for green highlights, individual place folding, Batch Place Fold, and the sidebar function action. Include both boundary directions, already-folded branch components, containment rejection, nested unfolding, session resumption, and viewport preservation.
- [x] Replay the original Aeroblasters net against the corrected engine and verify all four affected call occurrences. Confirm that newly generated HTML embeds the fix; previously exported HTML retains its embedded engine until regenerated.

## Context

This is a Phase 2.8 follow-up to [47 — Fold-Entire-Function](./47-fold-entire-function-compound.md), separate from Phase 2.9 snapshot optimization and Phase 2.10 Function Return Metadata. Ticket 47 is resolved and supplies the existing action; it is not an outstanding blocker.

Function containment concerns the nodes a reduction consumes. A retained caller boundary can anchor a function-owned Choice without being consumed. The internal-place trigger makes that Choice accessible without requiring the user to select an exterior caller place or adding arbitrary caller places to the function's batch scope.

## Comments

### 2026-10-10 — Implementation complete

Implemented the round-02 findings and added generated-viewer/headless regressions. `python3 -m unittest tests.test_html_viewer` passes (150 tests). The full suite ran 547 tests and has three unrelated errors (missing `pygraphviz`, missing `pytest`, and an existing `WalkResult` unpacking mismatch). The read-only round-02 review snapshot reports the Aeroblasters manual acceptance check passed. See the [round-02 implementation review](../reviews/phase-2.8-ticket-53-round-02.md).

### 2026-10-10 — User report

The user cannot fold `BlinkingText.update()` and `Message.update()` entirely into component nodes in the Aeroblasters viewer generated on 2026-10-10 because the relevant internal place is not highlighted green. "Opposite side" means graph connection direction, not rendered position.

### 2026-10-10 — Confirmed diagnosis

The supplied viewer embeds the same engine as the repository. Replaying its net reproduces the stall in one `BlinkingText.update()` and three `Message.update()` call occurrences. Each stops at one internal place and three transitions.

Two controlled probes distinguish the causes:

1. Relaxing only the Choice boundary checks in memory makes the exit-side split eligible; existing Choice followed by Single-Place Contraction completes the function.
2. With those checks relaxed, the entrance-side merge still lacks an internal trigger. Applying Choice from its exterior entrance lets the existing function action finish while retaining both caller boundary places.

Bypassing elementary-rule priority does not help either internal place. The required refinement is eligibility and trigger access for existing reductions, with consumption containment retained. The diagnostic bypass is not a safe implementation.

The [diagnostic replay and reproduction notes](../debug/called-function-boundary-folding/README.md) preserve both minimized real-world shapes and the original input location. The replay currently fails both cases as expected; no production fix has been applied.

### 2026-10-10 — Ticket rewrite

Rewritten with to-tickets as one complete, independently verifiable folding fix covering eligibility, UI actions, restoration, and regression evidence. No prefactoring ticket or outstanding blocking edge is required.

### 2026-10-12 — Reopened: Tic Tac Toe `create_board()`

The user reports that `create_board()` also cannot be folded in the Tic Tac Toe global viewer because its entrance and exit places are not marked green. This is a new affected game/function occurrence for the called-function folding issue. The reported missing green highlights suggest the boundary places are not being offered as eligible fold triggers; inspect the generated viewer and determine whether this is the same shared-boundary eligibility/trigger problem described above.

The supplied Tic Tac Toe global session save (`/Users/pingchungtsai/Downloads/tic_tac_toe_global_foldable_session_save.json`) contains two depth-0 `create_board()` compounds (`compound_create_board` and `compound_inline_create_board_t123`) with preassembled subnets. The snapshot captures the saved graph state but does not encode green-highlight state or a fold attempt, so it is supporting context rather than a reproduction. Re-triage and inspect this occurrence before treating the ticket's previous acceptance checks as complete.

### 2026-10-12 — Ordinary singleton acceptance case

- [x] An ordinary singleton-transition function stays expanded and retains its called-function compound until the user selects Fold Entire Function. Initial load/highlight refresh does not create a component or advance the fold counter.
- [x] A safe ordinary singleton with caller-owned entry/exit places is accepted as atomic for the surrounding Sequence boundary eligibility checks, without relaxing containment for other function shapes.
- [x] Fold Entire Function replaces only the singleton transition with one reversible opaque component inside the same compound, keeps the existing brown Collapsed Compound State presentation, preserves caller boundaries, source/function identity, transition weight, zero penalty, and SM, and reports success/completion with zero place-reduction passes.
- [x] Repeating the function action is a safe no-op. Component-Local Unfold restores the original ordinary transition, metadata, hierarchy, and arcs; if a caller Sequence later consumes the completed function, unfolding that Sequence restores the function's previously expanded or explicitly collapsed state.
- [x] The sidebar action reports completion, performs one final layout, and preserves zoom/pan. Existing Choice, containment, nested-function, and unfold behavior remains covered by the Ticket 53 regressions.

### 2026-10-12 — Implementation complete

Added a reversible zero-penalty completion for ordinary singleton-transition functions and narrowly allowed that shape through function-boundary Sequence eligibility. The action traverses nested compounds before reducing the selected function's places. Regression coverage verifies initial state, highlights, collapsed styling, repeated action, weight/SM preservation, metadata and arc restoration, caller-boundary Sequence folding/unfolding, sidebar viewport/layout behavior, and existing Ticket 53 protections. Focused and full-suite results are recorded in the round-03 implementation review.
