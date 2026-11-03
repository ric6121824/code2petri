# Ticket 71 — Call Refolding question tree

**Last updated:** 2026-11-03

**State:** Product decisions and test seams are captured in the published Phase 2.8.2 spec. Tickets 72 and 73 have no remaining product questions. Ticket 71's scoring construction remains engineering validation work; implementation issues 72, 73, and 71 were published after user approval on 2026-11-03.

**Ticket:** [71 — Fold expanded functions back to opaque calls](../issues/71-call-refolding.md).

**Related work:** [Ticket 66](../issues/66-function-scoped-structural-folding.md), [Ticket 70](../issues/70-alternative-exception-outcomes.md), [Round 06](../reviews/phase-2.8-ticket-66-round-06.md), and [Round 07](../reviews/phase-2.8-ticket-66-round-07.md).

**Vocabulary:** [Call Refolding](../../../GLOSSARY.md); existing reduction policy in [ADR 0003](../../../docs/adr/0003-adopt-prom-local-reduction-algorithm.md) and exception outcomes in [ADR 0006](../../../docs/adr/0006-alternative-exception-outcomes.md).

## Goal — settled

The user wants to fold an expanded `_edge_for_move()` back to its opaque call abstraction, as if it had never been Inline Expanded. The function must preserve its normal and exceptional caller outcomes, and its expanded subnet must remain available for unfolding. Merely explaining that the current SESE rules cannot completely reduce it does not fulfill this goal.

The user said: “my goal is to fold `_edge_for_move()` as if it were never being inline-expanded, like an unresolved call.”

## Decision tree

```text
Restore an expanded function to its opaque call abstraction [SETTLED GOAL]
|
+-- Q1. Preserve its accumulated complexity contribution? [SETTLED]
|   +-- Keep 18 when the current contribution is 18; do not reset it to 1.
|
+-- Q2. Apply structural reductions before restoring the call? [USER PREFERENCE]
|   +-- User prefers reductions first to obtain the function's score.
|   +-- Final-score interpretation depends on Q3; extra penalties can change 18.
|
+-- Q3. How is scoring completed for a region outside supported boundaries?
|   +-- Initial accumulated-weight-versus-final-score choices [NOT SELECTED]
|   +-- User proposed an unstructured residual penalty [PROPOSAL, NOT APPROVED]
|   +-- Simple return-or-error function remains foldable [AGREED REQUIREMENT]
|   +-- Two outcomes alone do not justify Unstructured classification [AGREED]
|   +-- Scoring representation and mathematical justification [OPEN ENGINEERING WORK]
|
+-- Preserve distinct caller outcomes during every reduction/refold [GOAL]
|   +-- Existing whole-net fallback deletes exception_end [CONFIRMED DEFECT]
|   +-- Fix must retain this interface or safely reject the invalid reduction.
|
+-- Restoration and expansion coverage [SETTLED]
|   +-- Q4. Restore the function's pre-action diagram, including prior manual folds.
|   +-- Q5. Support both browser-expanded and backend-inlined occurrences.
|
+-- Q6. What does export do if analysis cannot safely complete? [SETTLED]
|   +-- Export the preserved graph; mark final SM unavailable and weight separately.
|
+-- Q7. Which test seams verify the phase? [SETTLED]
|   +-- Existing generated-viewer actions, session/export, public CLI/export, browser.
|
+-- Engineering validation and publication status
    +-- Ticket 71's outcome-aware scoring construction and weight accounting.
    +-- Representation and compatibility factoring subject to the published contract.
    +-- Tickets 72, 73, and 71 published via to-tickets after user approval [DONE].
```

### Q1 — settled: preserve accumulated complexity

The user answered “keep 18” when offered preservation of a current contribution of 18 versus resetting the opaque call to an unanalyzed-call weight of 1. Refolding alone should preserve the accumulated contribution and avoid charging it again on repeated fold/unfold cycles.

This does not settle how to finish the structural analysis or which additional penalties are valid. In particular, an automatic reduction before refolding may add a justified penalty; the final contribution then differs from the illustrative initial 18.

### Q2 — user prefers structural reductions first

The user answered: “I think our current mechanics need a function to be structurally reduced before an accurate score calculation, right? if that so, then it would need to perform structural reductions first so present an accurate score for the folded opaque call.”

Current mechanics count initial transition weights before reduction, including expanded-function transitions. Structural reductions accumulate additional penalties. The agreed direction is to perform valid reductions first, then retain the accumulated result in the restored call. What qualifies as a completed final score for the remaining multi-exit region is still Q3, not an assumed decision.

### Q3 — product requirement agreed; scoring derivation remains open

The initial question offered preserving accumulated weight with an incomplete-analysis indication versus requiring a final SM before refolding. The user did not choose either option; they proposed an unstructured penalty for the remaining region instead.

The revised question was: may Ticket 71 use a separate function-local analysis representation that treats normal and exceptional termination as completion for scoring, while preserving them as distinct outcomes in the actual graph?

The user initially deferred this question, then resumed it and agreed on 2026-11-03: “A simple return-or-error function should still be foldable, and should not become ‘unstructured’ solely because it has two outcomes.”

This is an acceptance requirement, not approval of a specific mathematical construction. Normal and exceptional outcomes remain distinct in the actual graph. The existence of two outcomes alone cannot be used either to reject Call Refolding or to assign an Unstructured penalty. A separate scoring copy, a common completion place, a richer outcome-aware representation, and their weighting consequences remain engineering alternatives requiring explicit justification and validation. The user is not expected to select an untested formula.

The original metric assumes a WF-net with one source place and one sink place; even its unstructured components have defined source/sink boundaries. An unstructured classification does not automatically authorize removing additional exit interfaces. See Definitions 9, 16, and 18 in [Lassen and van der Aalst, Complexity Metrics for Workflow Nets](https://www.vdaalst.com/publications/p497.pdf).

**Engineering completion condition:** Before claiming a final SM for the refolded call, document the analyzed representation and metric scope, and validate it on small examples: a sequence, a conditional return/error, nested exception handling, and an eligible genuinely unstructured component. Distinguish preservation of visible outcomes from preservation or derivation of a numeric score. Keep the exit-loss defect independently fixable.

**Research pointer:** The [cited reading note](../research/phase-2.8.2-function-refolding-papers.md) surveys relevant papers from van der Aalst's publication list. It separates the original SM assumptions from richer normal/fault interfaces and substitution models with multiple final states. It supplies alternatives to investigate and does not establish a scoring method or approve outcome-merging.

### Q4 — settled: restore the pre-action diagram

If the user has already manually reduced part of a function, then invokes automatic reductions plus Call Refolding, should unfolding restore the exact expanded state before that whole action, or expose the further-reduced interior produced automatically?

The user answered “the pre-action diagram.” Unfolding restores the selected function's exact expanded state before automatic reductions plus Call Refolding, retaining the user's earlier manual folds. Keep this component-local: unrelated changes made elsewhere after refolding must survive. Any analysis cache or alternative inspection view is an implementation/design detail, not permission to change that restoration contract.

### Q5 — settled: support both expansion paths

Should Call Refolding support both functions expanded by clicking a resolved call and functions already Inline Expanded in an exported Composite Net?

The user answered “both.” Support browser-expanded calls and backend-inlined occurrences with equivalent caller-outcome behavior. Under that agreed scope, Tickets 72 (browser expansion routing) and 73 (whole-net exit preservation) are correctness prerequisites for Ticket 71's complete acceptance; they do not depend on one another. The user subsequently requested publication of the Phase 2.8.2 spec before implementation tickets.

### Q6 — settled: export incomplete graphs with honest score availability

The code audit found that refusing an invalid fallback could leave Python presenting the first remaining transition's weight as final SM, and that the historical reducibility flag does not establish completion. The user chose “Export diagram; mark final SM unavailable” on 2026-11-03. Preserve the graph for export, label reduction incomplete with its reason, and report Accumulated Reduction Weight separately. The exact fields and unavailable-value representation are engineering choices; valid completed results and actual export-error behavior must remain correct.

### Q7 — settled: existing production test seams plus browser acceptance

The user confirmed generated-viewer actions, session/export tests, the public Python CLI/export path, and a recorded Dots & Boxes browser check. Reuse these existing high-level seams; private helpers or parser passes alone do not establish acceptance.

### Tickets 72 and 73 — grilling frontier closed

The read-only audit identified no additional Ticket 72 product decisions. Backend outcome parity supplies the contract for handlers versus no handler, exception-only/no-exception callees, nested/repeated calls, token/weight preservation, metadata remapping, and safe failure without discarding unrelated work. These are engineering parity requirements.

Ticket 73's one new product question was Q6; it is answered. Validate discovery and execution, preserve interfaces and accumulated weight, keep legitimate reductions available, and report all three Reduction Outcomes through consumers. Legacy tests expecting forced reduction of non-WF graphs do not override that contract. No further human choice is required for these two defect tickets. Ticket 71's mathematical construction remains a separate engineering validation gate.

## Confirmed defect — whole-net fallback consumes an exceptional exit

**Artifact:** [GameState__edge_for_move_foldable_session_save.json](</Users/pingchungtsai/My Drive (ric6121824@gmail.com)/Digital Media MSc/Semester 4/Graph Data/output_code2petri/Dots_and_Boxes-261020/GameState__edge_for_move_foldable_session_save.json>)

**SHA-256:** `1c752c903b5b3694ab64fa4cd42e863ba5c6f87ea6217ed34781fd3009e1b418`

**Repository HEAD when recording this tree:** `a6b329e026ea5b13320b4748661fb44accfd07c2`.

The original graph stored in the snapshot contains both `p_end` (`end`) and `p_exception_end` (`exception_end`). The final `c_14` restoration record lists `p_exception_end` among its consumed nodes and retains only `p0` and `p_end` as the outer boundary.

The production-engine replay reconstructed the state immediately before the last fold from its retained nodes and edges plus the recorded consumed subnet, then executed the selected unstructured candidate:

| Check | Before the last fold | After the last fold |
| --- | --- | --- |
| Final places | `end`, `exception_end` | `end` only |
| Running transition weight | 22 | 2200 |
| Elementary reduction available | No | Not evaluated |
| Exceptional exit preserved | Yes | No |

The selected candidate had `isGlobalFallback: true`, source `p0`, sink `p_end`, and included `p_exception_end`. An assertion requiring the exceptional exit to remain present failed. This reproduces the actual loss of the modeled interface, rather than merely observing that the final display has one exit. The artifact and source code were left unchanged.

Cause: [`detectUnstructured()`](../../../code2petri/viewer/engine/reduction_engine.js#L2597) selects one available sink for its whole-net fallback and includes all remaining places and transitions in the candidate. [`_executePlaceSESEReduction()`](../../../code2petri/viewer/engine/reduction_engine.js#L2924) consumes every candidate node except its chosen source and sink, then creates only one outgoing boundary arc. On this two-exit input the other exit is therefore removed. Scoped function folding excludes that global fallback, explaining why a standalone function view can finish through this path while its inlined occurrence remains partial.

The observed 2200 is the implementation's output, not verified evidence that the original SM applies correctly to this two-exit graph. A single-exit result obtained by deleting an outcome must not be used as the expected successful refolding fixture.

## Relationship to Ticket 71

The defect is directly relevant to Ticket 71's requirement to preserve caller outcomes during analysis and Call Refolding. Ticket 70 corrected outcome construction and Inline Expansion; this failure occurs later, during reduction. This reproduction alone does not invalidate Ticket 70's completed routing repairs.

Repairing the whole-net fallback would stop this exit loss, but would not by itself implement reversible multi-exit Call Refolding. Ticket 71 must both avoid the invalid reduction and provide the requested opaque call abstraction. Conversely, simply enabling the current whole-net fallback inside a function would reproduce the defect rather than solve Ticket 71.

**Proposed acceptance guardrail:** Use the supplied standalone save, a fresh standalone export, and the corresponding inlined caller occurrence to verify that normal and exceptional outcomes remain distinct through reductions, refolding, save/open, and unfolding. Score accounting must count a function contribution once across any outcome alternatives; its final derivation remains open under Q3's agreed product requirement.

**Spec allocation:** The published Phase 2.8.2 spec assigns this independently verifiable fallback and incomplete-reporting repair to Ticket 73, with no blocker. Ticket 71 depends on it. No parent ticket is modified by this design note, and implementation issue files were published separately after user approval.

## Additional confirmed defect — browser expansion reverses exit routing

**Artifact:** [standalone reference export](../exports/GameState__edge_for_move.html), inspected on 2026-11-03. Its payload has mode `no-fold`, an unexpanded initial net, and separately embedded callee nets.

Before interactive expansion, the resolved `_coerce_direction()` call is `t7`, with incoming arc `p3 -> t7` and outgoing arc `t7 -> p5`. The missing normal continuation appears after the browser expands that call, not in the original opaque call's normal arc.

A replay of the actual exported `findBoundaryPlaces()` and `netToElements()` functions, with `t7` marked expanded, selected `p_exception_end` as the callee's normal sink. The normal `t7__p_end` remained inside the expanded container, and the only outgoing child arc to the caller was `t7__t11 -> p5`: the explicit raise was connected to the normal continuation. Assertions requiring normal return to reach `p5` and the raise to reach the caller's exceptional boundary failed.

The cause is the browser boundary helper's reverse scan: both `p_end` and `p_exception_end` satisfy the ID suffix `_end`, so it selects the latter. The browser splice also represents only one sink, unlike the backend inliner, which separately maps normal and exceptional exits.

A separate production Python-walker/Inline Expansion check of this call passed: `return direction -> p5`, and `raise ValueError('unsupported direction') -> p_exception_end`. This establishes the expected routing for the inspected call; it does not validate every part of either graph or the later whole-net fold.

Expected meanings and connections:

- The callee's `end` means it returned a direction successfully; it continues to the caller's next statement at `p5`.
- The callee's `exception_end` means it raised an uncaught error; it propagates to the caller's `exception_end` in this context.
- A container need not have its own outgoing arc after expansion if its internal terminal transitions connect correctly to the caller. The observed dangling normal end and misrouted raise are the defects.

**Spec allocation:** Ticket 72 brings browser reference expansion into parity with backend normal/exception routing. Ticket 73 guards whole-net fallback and reports incomplete analysis honestly. They are independent fixes beyond Ticket 66's scoped action. Ticket 71 covers Call Refolding and depends on both under the agreed two-expansion-path scope. The implementation issues were published separately after user approval; no unvalidated scoring construction is approved.

## Publication status

This file is the persistent interview/question-tree record. The [Phase 2.8.2 specification](./phase-2.8.2-call-refolding-and-exit-preservation.md) is published as ready-for-agent with the required to-spec sections, extensive user stories, and user-confirmed testing seams. The user subsequently approved the three-ticket breakdown and requested publication and commit. [Ticket 72](../issues/72-browser-call-expansion-exits.md) and [Ticket 73](../issues/73-safe-fallback-and-incomplete-results.md) were published first with no blockers, followed by [Ticket 71](../issues/71-call-refolding.md), blocked by both. All three carry ready-for-agent status; this does not claim that their work is complete. [ADR 0007](../../../docs/adr/0007-preserve-exits-and-report-incomplete-analysis.md) records the confirmed exit-preservation and incomplete-result contract. There is no implementation claim or approval of a particular scoring normalization or new penalty formula.
