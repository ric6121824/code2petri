# Phase 2.8.2 — Call Refolding and Exit Preservation

**Status:** ready-for-agent

**Published:** 2026-11-03

**Tickets:** [72](../issues/72-browser-call-expansion-exits.md) and [73](../issues/73-safe-fallback-and-incomplete-results.md) can start independently; [71](../issues/71-call-refolding.md) is blocked by both. Published after user approval on 2026-11-03.

**Design record:** [Question tree and confirmed decisions](./phase-2.8-ticket-71-question-tree.md).

**Research:** [Primary-source reading note](../research/phase-2.8.2-function-refolding-papers.md).

**Readiness:** Implementation and focused review are integrated. The reported Fold/Unfold accumulation regression is fixed in the integration branch and has focused repeated-cycle coverage. Tickets 71–73 still need the regenerated Dots & Boxes browser acceptance. The user directed that multi-outcome final SM remain unavailable while outcome-aware metric research continues; no quotient projection, normalization, or penalty formula is approved.

## Problem Statement

Users cannot reliably simplify an expanded called function back to its opaque call representation when it has normal and exceptional outcomes. Existing function-scoped reductions can stop at that interface, leaving understandable functions expanded. The user expects a simple return-or-error function to remain foldable and not become Unstructured solely because it has two outcomes.

Two existing defects undermine that goal. Browser expansion of a resolved call can mistake the exceptional ending for the normal ending, disconnect successful returns, and route an error to ordinary caller execution. Whole-net Unstructured fallback can select one exit and consume another, making a graph appear fully folded by deleting an outcome.

Simply rejecting that invalid fallback also exposes misleading scoring: incomplete Python reduction currently takes the first remaining transition's weight as final SM, and consumers present it as a completed score. Users need a preserved, usable graph and an honest distinction between accumulated weight and final SM.

## Solution

Provide consistent normal and exceptional interfaces across backend Inline Expansion, interactive browser expansion, structural reductions, Call Refolding, session persistence, and export.

Fold Entire Function performs eligible reductions, then restores an opaque call abstraction with its justified accumulated contribution counted once. Preserve alternative caller outcomes and enough local restoration data to unfold to the function's exact pre-action diagram, including earlier manual folds. Support both browser-expanded calls and occurrences already Inline Expanded in a Composite Net.

Reject invalid whole-net reductions before they change the graph, component IDs, accumulated weight, or history. If analysis cannot safely complete, still export the preserved diagram, explain why reduction is incomplete, mark final SM unavailable, and show accumulated weight separately. Valid single-exit reductions remain available.

This work extends the existing viewer and analysis pipeline. It preserves the historical delivery and review records of Tickets 66 and 70.

## User Stories

1. As a viewer user, I want to refold an expanded called function into an opaque call, so that I can return to a readable caller-level diagram.
2. As a viewer user, I want a simple return-or-error function to remain foldable, so that multiple outcomes do not leave ordinary functions permanently expanded.
3. As an analyst, I want component classification based on actual structure, so that two outcomes alone do not cause an Unstructured penalty.
4. As an analyst, I want eligible structural reductions performed before Call Refolding, so that justified penalties contribute to the retained complexity.
5. As an analyst, I want the accumulated contribution preserved when the opaque call is restored, so that known complexity is not reset to an unanalyzed-call weight.
6. As an analyst, I want each refolded function contribution counted once across alternative outcomes, so that several exit routes do not duplicate its score.
7. As an analyst, I want repeated fold/unfold cycles from the same starting state to avoid score inflation, so that presentation changes do not repeatedly charge complexity.
8. As a viewer user, I want normally returning calls to reach their normal continuation, so that the caller proceeds to its next statement.
9. As a viewer user, I want exceptional completion to reach the appropriate handler or exceptional function boundary, so that failures do not become ordinary success.
10. As a viewer user, I want normal and exceptional outcomes to remain alternatives, so that one completion does not activate both routes.
11. As a viewer user, I want the same refolding behavior for browser-expanded and backend-inlined functions, so that the export method does not change what the action supports.
12. As a viewer user, I want an expanded call's internal terminal transitions connected correctly to the caller, so that the diagram does not end at a disconnected internal normal exit.
13. As a viewer user, I want expansion of a callee with only exceptional completion to avoid inventing a normal return, so that unreachable success does not appear in the graph.
14. As a viewer user, I want a callee without an explicit exceptional exit to retain the existing bounded opaque-call exception behavior, so that expansion does not silently strengthen the analysis assumptions.
15. As a viewer user, I want nested and repeated call occurrences to retain separate identities, so that expanding or refolding one occurrence does not change another.
16. As an analyst, I want arc weights and initial markings preserved consistently during expansion, so that the token-flow meaning is unchanged.
17. As an analyst, I want container presentation to avoid adding a fictitious operation or duplicate contribution, so that hierarchy does not distort transition accounting.
18. As a viewer user, I want call identity, resolution, return information, and call-result evidence retained through expansion and refolding, so that inspection remains meaningful.
19. As a viewer user, I want unrelated folds and names to survive expanding or collapsing another call, so that navigation does not reset my editing work.
20. As a viewer user, I want rejected or failed expansion to preserve the current graph and history, so that missing boundary information cannot leave a partial splice.
21. As a viewer user, I want invalid whole-net fallback rejected without losing exits, so that normal and exceptional completion remain distinguishable.
22. As an analyst, I want source/sink and component-interface assumptions checked before a reduction, so that a numeric penalty does not authorize an invalid graph replacement.
23. As a viewer user, I want a candidate revalidated when executed, so that an outdated highlight or supplied candidate cannot bypass current safety checks.
24. As a viewer user, I want rejected reductions to preserve nodes, arcs, tokens, weights, component allocation, and history, so that refusal is a true no-op on graph state.
25. As an analyst, I want eligible contained reductions to remain usable in a larger unsupported graph, so that rejecting a whole-net fold does not prevent safe local progress.
26. As an analyst, I want legitimate single-exit unstructured reductions to keep working, so that the safety repair does not remove valid complexity analysis.
27. As an analyst, I want Python and browser reductions to agree about boundary safety, so that CLI and live analysis do not produce contradictory graphs.
28. As an analyst, I want analysis completion distinguished from structural reducibility, so that using an Unstructured component is not confused with an unfinished analysis.
29. As an analyst, I want incomplete analysis to have no claimed final SM, so that a remaining transition's weight is not presented as the complexity of the whole net.
30. As an analyst, I want accumulated weight visible separately when analysis is incomplete, so that partial progress is still useful without being mislabeled.
31. As a CLI user, I want a preserved diagram exported when reduction cannot safely finish, so that unsupported structure does not prevent me from inspecting the graph.
32. As a CLI user, I want console messages and exported metadata to identify incomplete reduction, so that automated comparisons do not treat partial analysis as a final score.
33. As a viewer user, I want the top bar, inspector, playback, and reopened session to report completion consistently, so that the same graph does not acquire different score claims across views.
34. As a viewer user, I want Unfold to restore the selected function's pre-action diagram, so that automatic reductions do not erase the state I chose to work with.
35. As a viewer user, I want my earlier manual folds retained after unfolding, so that the function returns to its prior editing state.
36. As a viewer user, I want unrelated later edits preserved by Component-Local Unfold, so that unfolding one function does not rewind the whole document.
37. As a viewer user, I want names, metadata, weights, hierarchy, and node positions restored with the function, so that local unfolding is exact.
38. As a viewer user, I want current zoom, pan, sidebar, and viewing preferences preserved during graph actions, so that simplification does not disrupt navigation.
39. As a viewer user, I want automatic reductions plus Call Refolding to form one history gesture, so that one Undo reverses the whole action.
40. As a viewer user, I want Redo to restore the recorded result, so that it does not select another reduction or score.
41. As a viewer user, I want operation failures to restore graph and history state, so that failed analysis or capture does not leave half-completed work.
42. As a viewer user, I want save/open to retain the opaque call, outcome interfaces, score meaning, and restoration records, so that editing can continue offline.
43. As a viewer user, I want to unfold nested components after reopening without depending on old Undo stacks, so that local restoration remains durable.
44. As a viewer user, I want invalid incoming sessions to leave my current document intact, so that rejected input cannot destroy my work.
45. As a user of older sessions, I want supported snapshots to remain openable without guessed topology repairs, so that historical evidence is preserved.
46. As an analyst, I want legacy graphs with insufficient provenance to receive a specific explanation, so that missing data does not cause invented caller routing or verified-score claims.
47. As an export user, I want PNML and other supported outputs to retain outcome alternatives and documented weight meaning, so that the exported graph agrees with the viewer.
48. As an analyst, I want a traceable scoring representation validated on small known examples, so that a final SM claim has a defensible derivation.
49. As a maintainer, I want tests through production viewer actions and public CLI/export behavior, so that fixes work across their real entry points.
50. As a maintainer, I want actual browser/session acceptance recorded separately from headless tests, so that missing human-visible verification stays explicit.

## Implementation Decisions

- **Ticket ownership and sequencing:** Ticket 72 corrects browser expansion; Ticket 73 protects whole-net fallback and its incomplete-result reporting. They have no blocking edge between them. Ticket 71 depends on both because the user requires both expansion paths and reductions before refolding. The user approved this breakdown and publication on 2026-11-03. Keep the three numbers and existing parent-ticket histories; publishing these issues does not close or modify parent issues.
- **Two distinct operations:** A Structural Fold must satisfy the existing validated component interface, priority, and weight rules. Call Refolding restores the call-level abstraction. It cannot acquire permission to consume caller outcomes by being labeled a Structural Fold or Unstructured component.
- **Common outcome contract for Ticket 72:** Identify normal and exceptional boundaries independently by explicit semantic roles and validated provenance. Route normal completion to normal caller continuation and exceptional completion to the paired exception destination, modeled enclosing handler, or exceptional function boundary. Use backend behavior as prior art, and verify it independently against expected outcomes rather than assuming every backend result is correct.
- **Bounded exception semantics:** Preserve the accepted source-language exception contract. Outside an active caller handler, create or reuse the caller's exceptional boundary when an expanded callee supplies an explicit exceptional exit. Preserve existing paired opaque-call alternatives when the callee does not supply one; remove the paired alternative only when the concrete callee outcome replaces it. An unused normal-end placeholder does not imply a reachable normal return. This phase does not add new exception-type inference or precise unsupported finally overrides.
- **Occurrence-local expansion:** Preserve unique repeated/nested occurrence identities, call references, source evidence, resolution state, and hierarchy. Cloned call-result owner IDs and exception-alternative associations must refer to the cloned owning transition. Preserve arc weights; apply the backend's existing policy that cloned callee-place initial markings do not create an additional invocation token.
- **Operate on the current graph:** Expanding or collapsing one call preserves unrelated live reductions, committed names, metadata, positions, and current view. Rebuilding from original source/playback data is acceptable only if the complete current editing state is retained correctly. An old expansion record must not silently replace later graph edits.
- **Presentation is not another operation:** An expanded call container must not add a duplicate transition contribution merely because it also retains call-display information. Export and score accounting must agree on which objects represent actual operations versus containers.
- **Atomic expansion and boundary failure:** Resolve and validate all required caller/callee connections before committing a splice. Ambiguous or missing information yields a specific safe refusal. Use the established action-history transaction boundary to prevent partial graph changes, advanced counters, lost Redo, or stale success messages.
- **Whole-net eligibility for Ticket 73:** Validate that the proposed whole-net region has distinct, justified source and sink boundaries, the applicable single-entry/single-exit structure, complete source-to-sink coverage, and no consumed interior markings or interfaces that the replacement would erase. Validate all relevant incident arcs and weights. A multiple-exit whole net, disconnected remainder, missing boundary, or unsupported weighted interface is not repaired by selecting an arbitrary first/last place. Preserve valid local reductions in an otherwise unsupported graph.
- **Discovery and execution safety:** Unsafe fallback candidates must not be offered as eligible. Independently revalidate immediately before execution, including public execution paths accepting supplied or stale candidates, before incrementing counters, creating components, removing nodes/arcs, or committing history. Apply the same observable contract in the Python reduction engine and Live Fold Reduction engine.
- **Weighted and marked graphs:** Preserve weights and markings wherever the existing validated reduction defines their replacement. If the operation cannot preserve them, refuse explicitly rather than rewiring unit arcs or dropping internal tokens. A positive result must demonstrate its applicable conservation rules; counting sinks alone is insufficient.
- **Legacy non-WF expectations:** Existing arbitrary multi-entry, no-exit, or same-source/sink fallback tests are not evidence that those inputs satisfy the original WF-net assumptions. Update such cases to assert preserved unsupported/incomplete results unless a separately justified existing abstraction contract applies. Keep valid workflow controls green and preserve Faithful Translation of dead ends and infinite loops in exported graphs rather than forcing them to become terminating nets.
- **Reduction Outcome contract:** Distinguish completion through structured reductions, completion that used Unstructured components, and incomplete/unsupported analysis. The historical structural-reducibility indicator must not be silently repurposed as a completion flag. Neither one remaining transition nor a stored numeric field alone proves a valid final SM.
- **User-confirmed incomplete-result behavior:** Continue exporting the retained graph when safe reductions reach a fixed point without a valid final result. Show “Final SM unavailable—reduction incomplete” with an actionable reason, and report Accumulated Reduction Weight separately. Do not substitute the first remaining transition, an arbitrary zero, or the running total as final SM. Preserve legitimate completed scores for supported cases. Actual input, filesystem, or serialization errors retain their existing failure behavior.
- **Propagate completion honestly:** Carry Reduction Outcome and score availability through public analysis results, CLI console output, JSON, supported graph exports, HTML titles/top bar/inspector/playback, and saved document state. Exact field names, unavailable-value representation, and compatibility factoring are engineering choices, but consumers must not read an incomplete result as verified final SM. Retain support for old parseable sessions and label missing completion evidence as unknown rather than inventing proof.
- **Ticket 71's scoring validation gate:** Establish the analyzed function representation, boundary treatment, and component/weight derivation before claiming a final call-level SM. Validate a sequence, a conditional return/error, nested exception handling, and an eligible genuinely unstructured component. Check known single-exit cases against the established metric and independently derived expected values. Multiple outcomes alone must neither prevent Call Refolding nor trigger an Unstructured penalty.
- **No unapproved score normalization:** A separate scoring copy, common completion place, richer outcome-aware interface, or other construction remains an engineering alternative requiring evidence. Record the chosen scope, assumptions, and any necessary metric/ADR amendment. If the proposed construction cannot satisfy the agreed foldability and outcome requirements, record the obstacle and keep Ticket 71 incomplete rather than inventing a final score.
- **Preserve contribution once:** Valid reductions may increase the function's contribution through their existing penalties; restoring an opaque call adds no further charge and never resets analyzed complexity to an unanalyzed-call default. Alternative routes, nested summaries, presentation containers, persistence, and repeated cycles must not duplicate the retained contribution.
- **Capture the pre-action function state:** Preserve the selected function's exact state before automatic reductions plus Call Refolding, including prior manual folds and the retained caller interface. Component-Local Unfold restores that state while preserving unrelated later changes. This local record must remain usable after history eviction and save/open; a chronological whole-document undo snapshot is not a substitute.
- **History, view, and failures:** Group the entire function action as one Viewer Action History gesture. Redo replays the recorded result; failed or unchanged actions do not add history or advance component allocation. Preserve current camera and viewing preferences, and retain detached canonical restoration records under the established compact-snapshot contract.
- **Persistence and export:** Save/open must preserve outcome roles, accumulated contribution, Reduction Outcome, names, metadata ownership, hierarchy, positions, and nested restoration. Retain legacy loading with strict validation of recognized new metadata and transactional rejection of malformed sessions. PNML export must express alternative outcomes using a semantically valid graph even when the viewer presents one opaque function tile; ordinary transition fan-out to both alternatives is not sufficient.
- **Historical artifacts and limits:** Source repairs do not rewrite existing saved topology or update embedded old HTML. Keep failing artifacts unchanged as evidence, regenerate viewers to exercise corrected bundles, and recover interfaces only from sufficient retained data. Automatic repair of the already-invalid fully folded graph is separate work unless specifically authorized.

## Testing Decisions

The user confirmed these seams: existing production generated-viewer actions, session/export tests, the public Python API/CLI/export path, and a recorded browser check on Dots & Boxes. Use those seams in preference to new private-helper tests. Test observable outcome paths, graph state, available actions, weights, completion reporting, and restoration; do not mirror helper implementation or assert only node counts.

- **Primary integration family — generated viewer:** Generate self-contained HTML through the public source-to-viewer path and drive the actual expansion, reduction, refolding, history, save/open, and PNML actions using bundled Cytoscape. Reuse the existing viewer action, function-fold, snapshot-validation, and export harnesses. Test the same function through browser reference expansion and backend-preassembled Inline Expansion.
- **Public analysis/CLI parity:** Reuse the existing fold-and-inline CLI integration and Python/JavaScript parity seams. Assert retained topology, outcomes, accumulated weight, completion status, and availability of final SM across API results, console messages, and JSON/DOT/PNML/HTML output. Ensure an incomplete result still exports the intended preserved graph rather than an unrelated earlier playback snapshot.
- **Ticket 72 baseline reproduction:** Replay the supplied standalone reference export with the resolved direction-coercion call expanded. Verify that normal returns reach the next caller statement and uncaught raises reach the caller's exceptional boundary. Assert that the container does not retain a disconnected normal ending or route a raise into ordinary continuation.
- **Ticket 72 boundary matrix:** Cover caller handlers versus no handler, nested handlers, normal-only and exception-only callees, no explicit exceptional callee exit, nested/repeated call occurrences, non-unit arc weights, call-result ownership, exception-alternative identities, and initial-token parity. Include current live folds, names, and an unrelated later edit. Check expected reachable markings or execution traces, not only agreement between two implementations that might share an error.
- **Ticket 73 baseline reproduction:** Reconstruct the state before the supplied final whole-net fold from its retained record. The invalid action must not consume the exceptional exit or turn running weight 22 into 2200. Assert unchanged nodes, arcs, tokens, weights, IDs, counters, history, and camera on refusal, plus a specific explanation.
- **Ticket 73 eligibility and reporting matrix:** Cover multiple sources/sinks, no exit, identical proposed source/sink, disconnected nodes, marked interior places, crossing interfaces, unsupported weighted rewiring, and stale/directly supplied candidates. Add a valid single-exit workflow that completes structurally and a valid one that completes with an Unstructured component. Verify all three Reduction Outcomes and that the legacy reducibility flag cannot falsely establish completion. Keep safe local folds available when the whole graph is unsupported.
- **Ticket 71 scoring and restoration:** Use small examples with independently justified component classifications and expected values, then the real edge-for-move function and both nested direction-coercion occurrences. Start from partial manual folds, run automatic reductions plus Call Refolding, edit elsewhere, and unfold. Verify exact pre-action function restoration, independent edits, outcome alternatives, metadata, weights, names, hierarchy, and positions.
- **Persistence and action lifecycle:** Exercise one-gesture Undo/Redo, no-op and injected-failure rollback, component-ID allocation, save/open continuation, history eviction, nested Component-Local Unfold, and export. Reopening starts ordinary empty action history while retaining local restoration. Reject malformed or ambiguous metadata without changing the active document. Repeated equivalent cycles must not inflate accumulated contribution.
- **Browser acceptance:** Record an actual generated-HTML browser run for the affected Dots & Boxes occurrences, including both expansion paths, normal and exception interfaces, graph controls, score/status presentation, save/reopen, continued editing, and local unfolding. Record source/generator commits and artifact identities. Distinguish agent-run, user-run, failed, interrupted, and unperformed checks. A compact fixture, parser pass, source-pattern match, or headless action run supports but does not replace browser acceptance.

## Out of Scope

- Source-language concurrency recognition or a new AND component; existing Marked Graph reductions remain available for eligible synchronization patterns.
- Precise exception-class inference, new external-call exception inference, or full return/break/continue override semantics through finally.
- Disabling containment, token, interface, or stale-candidate checks to force completion; arbitrary selection, deletion, or merging of exit outcomes.
- Treating every multi-exit function as Unstructured or assuming a common-sink scoring projection preserves the original SM without validation.
- Broader redesign of call resolution, return inference, parser architecture, or source-language control flow unrelated to the accepted outcome contract.
- Automatically repairing historical graphs already damaged by an invalid fold, modifying original source games, or rewriting old exported HTML.
- Persisting chronological Undo/Redo stacks in saved sessions, adding a new viewer application, or replacing PNML with a custom export format.
- Implementing the tickets or changing parent-ticket status as part of specification and ticket publication.

## Further Notes

### Work ownership and dependencies

| Ticket | End-to-end delivery | Blocked by |
| --- | --- | --- |
| [72 — Preserve normal and exceptional exits during browser call expansion](../issues/72-browser-call-expansion-exits.md) | Correct, backend-equivalent occurrence-local expansion/collapse with outcome, metadata, state, session, and export preservation. | None; can start immediately. |
| [73 — Preserve exit boundaries and report incomplete reduction honestly](../issues/73-safe-fallback-and-incomplete-results.md) | Safe rejection of invalid whole-net folds, continued graph export, truthful incomplete-score reporting, and valid-control preservation in Python and the browser. | None; can start immediately. |
| [71 — Fold expanded functions back to opaque calls](../issues/71-call-refolding.md) | Both expansion paths support justified reductions followed by Call Refolding, exact pre-action unfolding, consistent accumulated weight, and history/session/export continuation. | 72 and 73. |

Tickets 72 and 73 are independent and do not wait for Ticket 71's scoring research. Following user approval, the prerequisite issues were published before Ticket 71 on 2026-11-03, retaining the requested numbers. Tickets 66 and 70 remain related delivery context rather than new blocking edges for the two defect fixes.

### Resolved grilling frontier

The read-only code audit found no additional product decisions for Ticket 72: backend outcome semantics, occurrence identity, bounded exception handling, state preservation, and safe rejection already define the required behavior. Missing weight/metadata copying and destructive whole-document rebuilding are parity defects to fix through the existing seams, not new user preferences.

The audit found one open product decision for Ticket 73. On 2026-11-03 the user selected continued diagram export with final SM explicitly unavailable when reduction is incomplete. The user also confirmed the testing seams above. Exact status fields, error-return factoring, representation of unavailable numeric values, and internal validation modules remain engineering choices. There are no remaining human product questions for Tickets 72 or 73.

### Design and evidence references

- [Question tree, user answers, and original reproductions](./phase-2.8-ticket-71-question-tree.md).
- [Research note and primary-paper reading locations](../research/phase-2.8.2-function-refolding-papers.md).
- [Phase 2.8 delivered viewer/function-fold baseline](./phase-2.8-viewer-interactive-enhancements.md).
- [Phase 2.8.1 history and restoration contract](./phase-2.8.1-viewer-search-and-action-history.md).
- [ADR 0002 — Boundary Place Unification](../../../docs/adr/0002-boundary-place-unification.md).
- [ADR 0003 — ProM Reduction Policy](../../../docs/adr/0003-adopt-prom-local-reduction-algorithm.md).
- [ADR 0005 — Session-local Viewer Action History](../../../docs/adr/0005-session-local-viewer-action-history.md).
- [ADR 0006 — Alternative Exception Outcomes](../../../docs/adr/0006-alternative-exception-outcomes.md).
- [ADR 0007 — Preserve exits and report incomplete analysis honestly](../../../docs/adr/0007-preserve-exits-and-report-incomplete-analysis.md).

The audit confirmed that the existing Python completion flag records whether Unstructured reduction occurred, while the final-score path can select the first remaining transition even after no-progress. The new observable completion contract must therefore reach the consumers as well as the fallback detector. Legacy tests that expect a numeric fallback for non-WF shapes need revised behavioral expectations, not protection of their old scores.

At publication this document specified required behavior and validation without claiming implementation, new passing tests, a repaired historical session, or browser acceptance. The current integration and open acceptance gates are recorded below.

## Comments

### 2026-11-03 — Integrated implementation and acceptance state

Implementation is integrated on `codex/phase-2.8.2-call-refolding`. The final two-axis code review found no Spec mismatch and no documented Standards breach. The user-supplied round-01 report identified and reproduced a repeated Fold/Unfold accumulation defect; the fix and 3-cycle regressions are recorded in Ticket 71. Twenty-nine focused action-history and expansion tests pass; compileall and `git diff --check` pass. Other focused parser suites had Acorn parse errors on JavaScript fixtures before assertions; those are recorded in the relevant ticket comments and are not reported as passing. The descendant-collection duplication was consolidated; one judgment call remains for small analogous metadata-remapping logic in separate Python and browser runtime adapters.

Actual Dots & Boxes browser acceptance remains open for Tickets 71–73. Fresh browser-expanded and backend-inlined artifacts are recorded in Ticket 71 with the source/generator commits and hashes; they await human retest. Ticket 73's historical retained standalone session is not available in this integration worktree as a browser artifact.

The scoring projection evidence is recorded in [the validation note](../research/phase-2.8.2-scoring-projection-validation.md). It mechanically reproduces expected single-exit controls and derives representative conditional-return/error and nested-handler scores, but it collapses the normal/exception distinction in a disposable scoring copy. It therefore establishes a possible `SM(exit-quotiented function net)`, not invariance of the existing SM for the visible multi-outcome graph. The user directed that final SM remain unavailable while an outcome-aware metric is investigated; Ticket 71 remains incomplete.

The ongoing literature investigation is recorded in [the outcome-aware metric research note](../research/phase-2.8.2-outcome-aware-metric-research.md). It identifies multi-final-marking profiles and multi-port components as research directions, without a justified scalarization rule.

### 2026-11-03 — User-run browser checklist update

The user completed substantial manual checks in Safari 18.6 on the regenerated browser-expanded and backend-inlined artifacts (generator commit `0d7eceea70795ad0ca3123adc44901644dcd593f`). Both paths' normal/exception routing, Fold/Unfold, three-cycle leak removal, score availability, history, and save/reopen were marked done; backend-inlined PNML outcome preservation was checked. Browser-expanded PNML export was skipped. The user reported layout/position restoration problems during Undo/Redo and Component-Local Unfold, so Ticket 71 restoration acceptance remains open. Ticket 73's historical refusal scenario was skipped because the old session cannot load due to a duplicate node ID. The metric gate remains open; details are in the checklist stored with the generator export snapshot.
