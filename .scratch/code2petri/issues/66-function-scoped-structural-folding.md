# 66: Function-Scoped Structural Folding

**What to build:** Let a user simplify an expanded called function through an internal foldable trigger or Fold Entire Function after its own elementary reductions are exhausted, using existing validated structural reductions even when unrelated elementary reductions remain elsewhere. Preserve caller-owned entrance/exit places and show the existing brown/gold Collapsed Compound State when the function fully reduces.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

**Implementation:** complete (`3d54cbb`; scoped-candidate/containment fix in `96b6fb5`; fused-boundary loop follow-up recorded below).

**Verification:** full caller-context, browser/session, and invariance acceptance remains pending in the unchecked criteria below.

- [x] Apply elementary-before-structural priority within the selected Function Fold Scope, including eligible descendants. Unrelated elementary reductions elsewhere do not block a valid scoped structural fold; whole-net priority remains unchanged.
- [x] Discover and select structural candidates within that scope so a larger candidate crossing caller/sibling ownership cannot hide an eligible contained component. Retain existing class precedence, maximal/minimal selection rules, SESE reachability, validators, penalties, and transition-weight calculations within the scope.
- [x] Allow caller-owned entrance and exit places as retained anchors. Validate containment using the actually consumed interior; do not consume the anchors or unrelated caller/sibling nodes, or partially consume a protected nested container.
- [x] Expose a function-owned internal place trigger identifying the actual reduction type, using existing type-specific fold styling. Structural eligibility must not be mislabeled as green Sequence eligibility.
- [x] Make that trigger and Fold Entire Function expose the same safe candidate and revalidate immediately before mutation. Preserve containment and stale-target safety in individual/batch interactions involving the trigger.
- [x] Continue valid scoped reductions until completion or a fixed point. A completed function uses the existing brown/gold tile and function/component label; an unsupported or unsafe region reports a specific partial/no-progress reason.
- [ ] Never force completion through whole-net fallback, arbitrary component classification/weights, or disabled boundary checks. Preserve source call resolution and unresolved-call metadata.
- [ ] Cover both GameState._coerce_direction() occurrences in the Dots & Boxes reproduction, inside _edge_for_move() and _adjacent_boxes(), using self-contained fixtures with conditional returns and nested exception routing. Assess actual structural eligibility independently in both caller contexts rather than hard-coding a component type.
- [ ] Exercise the actual generated viewer's internal trigger and function button with a positively validated structural fixture; verify unrelated elementary folds do not veto it, eligible local elementary folds run first, retained anchors work in both directions, and larger surrounding candidates do not obscure it.
- [ ] Cover mixed-parent/sibling rejection, nested-container protection, stale eligibility, unsupported shapes, and unchanged unrelated folds, external interfaces, tokens, hierarchy, zoom/pan, and mathematically correct weights/SM.
- [ ] Save/open the resulting session, continue folding, and locally unfold nested components with exact consumed topology, boundary arcs, names, weights, and hierarchy restored. Use the existing generated-viewer/headless and browser/session seams rather than private-helper-only checks.

## Context and decisions

The observed function interiors each contain four places and seven transitions. No elementary place reduction is available. Whole-graph elementary gating and containment checks counting retained caller anchors prevent useful structural access; surrounding maximal candidates also need scoped selection. Finding an SESE region alone does not prove its structural class or authorize bypassing validators.

This extends the completed elementary-only contracts of Tickets 47 and 53. Those tickets remain resolved. It is independent of Phase 2.7's color follow-up and Phase 2.10's return metadata.

See the [Phase 2.8 specification](../specs/phase-2.8-viewer-interactive-enhancements.md), [Function Fold Scope glossary](../../../GLOSSARY.md), and [ProM reduction policy amendment](../../../docs/adr/0003-adopt-prom-local-reduction-algorithm.md).

## Comments

- 2026-10-13: User approved scope-local elementary priority, an internal marker and sidebar action sharing validated eligibility, retained caller anchors, existing mathematical rules, and partial outcomes for unsupported regions. Published locally with to-spec and to-tickets.

### 2026-10-13 — Implementation

Implemented scope-aware elementary gating, structural discovery and containment, retained caller anchors, internal place triggers, stale-trigger revalidation, and the existing Fold Entire Function action. Focused headless tests cover unrelated sibling elementary work, retained anchors, a validated state-machine fold, and a stale trigger. Full Dots & Boxes caller-context, nested-container, weights/SM, session/unfold, and generated-browser interaction verification remain pending; keep this ticket ready for human verification.

The final full suite ran 576 tests with 1 failure and 4 errors: the prototype runner could not bind its test port; optional `pygraphviz` and `pytest` dependencies are unavailable; and two pre-existing integration expectations disagree with current return shapes (`PetriNet.initial_net` and two-value `WalkerProtocol` unpacking). Focused regression suites and `compileall` passed.

### 2026-10-16 — Review disposition and delivery documentation

The user confirmed implementation completion. Commit `96b6fb5` addresses the Round 01 candidate-discovery defect: the selected function may contribute a valid partial interior while caller/sibling and protected nested-container checks remain enforced. The [Round 02 review](../reviews/phase-2.10-tickets-65-67-round-02.md) explicitly records that finding as resolved, with regression coverage for unused children, retained anchors, unrelated siblings, and stale triggers; the discovery criterion above reflects that evidence.

The [Phase 2.8 delivery record](../specs/phase-2.8-viewer-interactive-enhancements.md), README, and [grand plan](../grand_plan.md) now show the extension as implemented. Remaining acceptance requires both Dots & Boxes caller contexts, broader containment/weights/SM checks, actual viewer interactions, and session/unfold continuation. No tests, new code review, or browser checks were run for this documentation update.

### 2026-10-17 — Fused entrance/loop-head follow-up

Scoped structural discovery now supports the reported shared caller-entrance and loop-head topology through the existing validated State Machine reduction. Function-scoped reverse reachability may cross the selected source place while remaining inside the selected function's induced graph and direct caller-place anchors; global SESE traversal is unchanged. Before accepting a scoped candidate, every consumed interior node must have all incident arcs inside that candidate. This retains caller arcs and rejects hidden caller/sibling crossings without changing component classification or weight formulas. Fold Entire Function reports the interior node and external endpoint for crossing-edge rejection and gives specific reasons for scope, component-validation, and protected nested-function rejections. If no candidate reaches those rejection checks, its fallback explains that no elementary reduction or contained SESE region satisfied the function-scope rules.

The new production-engine/generated-viewer regression in `tests.test_html_viewer.TestFoldEntireFunction.test_fused_function_entrance_loop_head_is_scoped_state_machine_and_reversible` exercises the internal trigger and Fold Entire Function button, State Machine weight and SM calculation, caller anchors/tokens/hierarchy, unrelated sibling eligibility, viewport, save/open continuation, exact local-unfold restoration, and rejection of an interior crossing edge. The saved Tic Tac Toe session and both Dots & Boxes caller contexts still need human acceptance; this headless regression does not claim those checks passed.

The regression also checks specific reason text for scope-fit, token-bearing component validation, protected nested-function boundaries, and the no-candidate fallback. Token-bearing place checks across the structural validators now share one helper. The focused `TestFoldEntireFunction` class passes (9 tests); the full suite ran 599 tests with the same 1 failure and 4 errors recorded in the review report.

### 2026-10-19 — Dots & Boxes multi-continuation inspection

The [Round 05 inspection](../reviews/phase-2.8-ticket-66-round-05.md) records a reproduced function-scope rejection when folding `GameState._edge_for_move()` in the supplied Dots & Boxes session. The inlined callee has one shared sink, while its caller call-site has both normal and exception continuations; the current splice connects each callee completion to both. Keep foldability in this caller context within Ticket 66's open Dots & Boxes acceptance. Track precise normal-return versus exception-path modeling separately if that broader inlining behavior is to be changed.

### 2026-10-20 — Round 05 implementation evidence

The normal/exception translation issue is implemented and tracked separately as [Ticket 70](./70-alternative-exception-outcomes.md), with its bounded contract in [ADR 0006](../../../docs/adr/0006-alternative-exception-outcomes.md). The supplied historical save (SHA-256 `3fefd65c1af8836000e1034833c6c2b5890e95801476ee5c6985dab0a0be3711`) still safely makes no fold for `_edge_for_move()`: the current production-engine result names the retained `except_entry` (`p3`) and `try_exit` (`p4`) continuations and no longer explains the selected function through sibling `c_80`.

A fresh export from Python-Games commit `0e33c1ca98d7f6eaa17b6f3dd4209285aacbd80d` has SHA-256 `1a4aee112ebe6b9c0d0e6cee13289e15b5013ff487eef67fb1b1a2b05cc24c14`. In that graph, three explicit raises reach `except_entry`; the inlined normal return reaches `try_exit`; no transition targets both. The scoped production-engine fixture permits eight safe internal Sequence reductions in two passes, then returns a partial result because the function still has two caller continuations. The historical and fresh results remain separate because their interior topology differs. The eight accepted fresh candidates are all `Sequence` contractions: `_coerce_direction()` `p2`, `p4`, `p6`, and `p8`; `_canonical_edge()` `p1`; and `_edge_for_move()` `p2`, `p4`, and `p6`. Each consumes its source transition, listed place, and sink transition with one incoming and one outgoing boundary arc of weight 1. The historical graph has no accepted candidate; owned components `c_07`, `c_09`, and `c_11` each reach both retained caller places, while sibling `c_80` is rejected as out of scope.

Focused translation tests passed (187 tests), and `TestFoldEntireFunction` passed (12 tests). Before the fixes, the `continue` handler-isolation regression and returned-callee-exception regression failed for the expected routing gaps; both pass after their fixes. Nested handler routing after inlining also passes. The complete `tests.test_html_viewer` module ran 176 tests with one pre-existing error: an integration assertion expects `PetriNet.initial_net`. The full-suite and review results are recorded in the Round 05 report. No browser interaction, session save/open, or local-unfold acceptance was performed for this occurrence; those Ticket 66 criteria remain open.

### 2026-10-20 — Round 06 code review

The [Round 06 review](../reviews/phase-2.8-ticket-66-round-06.md) reviewed the Round 05 implementation against `74c1d32...HEAD`. Standards review found no issues. Spec review reproduced an uncaught exception inside `try/finally` reaching the normal function end because the finally path always targets `try_exit`; the focused 174-test suite passes but does not cover this case. The generated-viewer browser, save/open, and local-unfold acceptance remains unperformed. Ticket 66 remains `ready-for-human`, and its unchecked acceptance checklist is unchanged.

The user then reported a browser save-open comparison: the Tic Tac Toe 2026-10-17 session opens, but the Dots & Boxes 2026-10-17 session fails with `graph element.call_results[0].transition_id does not match its owning transition`. Round 06 records this explicitly as a **user-run failed browser check** against the stale 261017 Dots & Boxes viewer, whose bundle lacks `_migrateLegacyInlineCallResultIds`. The user subsequently exported Dots & Boxes with the newest project version and confirmed that the open-session issue is fixed. The 261020 viewer bundle contains the migration and its current save parses with the production validator; Round 06 records the newest export as a **user-run browser pass**. The 261017 failure remains historical evidence. Ticket 66 stays `ready-for-human`; no checklist item was checked off because the broader save/edit/unfold acceptance is still open.

### 2026-11-03 — Reopened after `_coerce_direction()` fold failure

The user reports that `GameState._coerce_direction()` still cannot be folded in `dots_and_boxes_global_foldable_session_save copy.json`. The [Round 07 inspection](../reviews/phase-2.8-ticket-66-round-07.md) replays the copied snapshot through the current production JavaScript reduction engine. Both inlined occurrences—inside `_edge_for_move()` and `_adjacent_boxes()`—make no progress after the three existing Sequence folds in each occurrence. The full-graph diagnostic names out-of-scope `c_41`, owned by sibling `DotsAndBoxesGame.draw`; removing `c_41` merely changes the reported sibling node, and isolated scopes still have no eligible contained SESE. Both occurrences expose separate normal and exceptional continuations, with the exceptional place outside the direct caller compound. The exception outcomes remain distinct; this replay does not show a Ticket 70 routing defect.

Reopened as `ready-for-agent` to investigate safe function-scoped reductions and accurate diagnostics for these residual multi-continuation shapes. All existing acceptance checklist items remain unchanged; no unchecked item was marked complete.
