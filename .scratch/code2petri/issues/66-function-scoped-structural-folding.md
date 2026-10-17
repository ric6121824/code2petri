# 66: Function-Scoped Structural Folding

**What to build:** Let a user simplify an expanded called function through an internal foldable trigger or Fold Entire Function after its own elementary reductions are exhausted, using existing validated structural reductions even when unrelated elementary reductions remain elsewhere. Preserve caller-owned entrance/exit places and show the existing brown/gold Collapsed Compound State when the function fully reduces.

**Blocked by:** None (can start immediately).

**Status:** ready-for-human

**Implementation:** complete (`3d54cbb`; scoped-candidate/containment fix in `96b6fb5`).

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
