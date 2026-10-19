# Inspection Update — Phase 2.8, Ticket 66, Round 05

**Inspection date:** 2026-10-19
**Ticket:** [66 — Function-Scoped Structural Folding](../issues/66-function-scoped-structural-folding.md)
**Specification:** [Phase 2.8 — Viewer Interactive Enhancements](../specs/phase-2.8-viewer-interactive-enhancements.md)
**Result:** The Dots & Boxes `GameState._edge_for_move()` occurrence remains a caller-context folding failure in the supplied session. Static inspection and an in-memory production-engine replay reproduced a function-scope rejection. No source or saved-session files were changed.
**Prior report:** [Round 04](./phase-2.8-ticket-66-round-04.md)

## Finding — `_edge_for_move()` has two caller continuations after inlining

The inspected artifact is:

```text
/Users/pingchungtsai/My Drive (ric6121824@gmail.com)/Digital Media MSc/Semester 4/Graph Data/output_code2petri/Dots_and_Boxes-261017/dots_and_boxes_global_foldable_session_save.json
```

In [`rules.py`](</Volumes/SharedDrive/Documents/GitHub/Python-Games/Dots & Boxes/rules.py>), `_edge_for_move()` has a normal return and two explicit error paths (`TypeError` and `ValueError`). The generated callee net sends those terminal transitions to one shared `p_end` sink. The two exits visible in the inlined caller context are instead the call site's normal continuation and the exception-handler continuation in `GameState.apply_move()`. Current source catches `(TypeError, ValueError, KeyError)`; keep that source version distinct from the saved graph rather than assuming the artifact was generated from today's source.

The Python control-flow builder adds an exception-handler arc from transitions created inside a `try` block. The inliner collects every place after the call transition, removes the callee source/sink boundary places, then wires each transition entering the callee sink to every caller postset place. In this snapshot, the inlined `_edge_for_move()` children therefore connect to both caller-owned places `p3` and `p4`. This makes graph expansion possible with multiple caller continuations, even though the callee itself has one normalized sink.

Each callee completion is connected to both continuations. Under ordinary Petri-net firing semantics, a transition with those two outgoing arcs produces tokens in both places; it does not choose between normal return and exception handling. This is a control-flow translation correctness issue under Faithful Translation, independently of whether a structural reduction can preserve that generated topology. The exception arc is already introduced by the control-flow builder before inlining; repairing only the inliner would leave the original call-transition behavior unresolved.

## Folding replay

Running `executeFoldEntireFunction()` against the parsed snapshot in memory made no disk changes and reproduced:

```text
success: false
complete: false
passes: 1
folded: []
skipped: [edge_for_move's remaining owned place: "No eligible place-targeted reduction."]
message: candidate includes out-of-scope node 'c_80' that is not a direct caller boundary place
```

`c_80` is a StateMachine component owned by the separate `DotsAndBoxesGame.draw` function. The scope check rejects it, as it must. This confirms that the current reduction search does not complete `_edge_for_move()` in this saved caller context. The two caller continuations make the candidate-boundary problem relevant; the replay alone does not prove whether correcting multi-exit boundary handling is sufficient to expose a valid contained fold candidate.

## Disposition and suggestions

- Keep the `_edge_for_move()` foldability and caller-context investigation in Ticket 66. Its open acceptance criteria already call for evaluating the Dots & Boxes `_coerce_direction()` occurrences inside `_edge_for_move()` and `_adjacent_boxes()` independently, including nested exception routing and retained caller anchors.
- Trace candidate discovery for this exact saved graph with both caller continuations represented. Verify any proposed candidate's consumed interior and all incident arcs, while retaining both caller places and excluding sibling-owned nodes such as `c_80`.
- Track normal-return versus exception-path translation as a separate correctness follow-up covering the builder and inliner. Keep its implementation and acceptance distinct from Ticket 66's structural discovery and diagnostics.
- After any folding change, use the generated viewer with this Dots & Boxes session to verify the fold, preserve both caller continuations, save/reopen, and locally unfold. No browser interaction was run for this inspection.

**Status:** Ticket 66 remains partially verified. This finding adds evidence for its outstanding Dots & Boxes caller-context acceptance; it does not create a separate ticket or claim a fix.

## Ordered repair plan for Luna — 2026-10-19

Follow the steps in order. The plan below is proposed work; its checklists are not verification results. Keep the supplied session unchanged as the historical reproduction.

### 1. Capture and replay the exact failing occurrence

Baseline inspected for this follow-up:

- Repository HEAD: `74c1d320bb0c7e13ba53958838715aa5e84c41d7`.
- Snapshot SHA-256: `3fefd65c1af8836000e1034833c6c2b5890e95801476ee5c6985dab0a0be3711`.
- Snapshot schema: `1`; engine step counter: `90`; live graph: 120 nodes and 129 edges.
- Function compound: `inline_main__inline_DotsAndBoxesGame.handle_event__inline_GameState.apply_move__compound_GameState__edge_for_move`.
- Direct caller compound: `inline_main__inline_DotsAndBoxesGame.handle_event__compound_GameState_apply_move`.
- Its boundary places share prefix `inline_main__inline_DotsAndBoxesGame.handle_event__inline_GameState.apply_move__`: `p1` is the entrance, `p3` is `except_entry`, and `p4` is `try_exit`.
- Owned components `c_07`, `c_09`, and `c_11` each have outgoing arcs to both caller continuations. `c_80` belongs to `inline_main__compound_DotsAndBoxesGame_draw` and remains outside the selected function.

Run from the repository root. This uses the production snapshot parser and engine and changes only the in-memory graph:

```sh
node - '/Users/pingchungtsai/My Drive (ric6121824@gmail.com)/Digital Media MSc/Semester 4/Graph Data/output_code2petri/Dots_and_Boxes-261017/dots_and_boxes_global_foldable_session_save.json' <<'JS'
const fs = require('fs');
const cytoscape = require('./code2petri/viewer/vendor/cytoscape.min.js');
const { parseFoldStateSnapshot } = require('./code2petri/viewer/engine/session_snapshot.js');
const { LiveFoldReductionEngine } = require('./code2petri/viewer/engine/reduction_engine.js');
const snapshot = parseFoldStateSnapshot(fs.readFileSync(process.argv[2], 'utf8'));
const cy = cytoscape({ headless: true, elements: snapshot.elements });
const engine = new LiveFoldReductionEngine(cy, snapshot.engine.cfg);
engine.stepCounter = snapshot.engine.stepCounter;
engine.rememberedCustomNames = new Map(snapshot.engine.rememberedCustomNames);
const scope = 'inline_main__inline_DotsAndBoxesGame.handle_event__inline_GameState.apply_move__compound_GameState__edge_for_move';
console.log(JSON.stringify(engine.executeFoldEntireFunction(scope), null, 2));
cy.destroy();
JS
```

**Done when:** Record the actual commit, artifact hash, full function ID, result, and elapsed time. Confirm the rejection above, or explain any changed result before changing code. Extract a self-contained fixture with this function's complete incident arcs and retained interfaces; keep the original graph as a separate acceptance case. An incomplete result alone does not prove that a valid fold exists.

### 2. Specify and repair exception translation separately

Create a linked local correctness follow-up under the [issue-tracker conventions](../../../docs/agents/issue-tracker.md). Cover the builder and Inline Expansion together; keep Ticket 66 responsible for structural eligibility and reporting. Read [ADR 0002](../../../docs/adr/0002-boundary-place-unification.md) and [ADR 0003](../../../docs/adr/0003-adopt-prom-local-reduction-algorithm.md) before choosing the representation.

Trace these production paths:

- [`ControlFlowBuilder.new_transition()`](../../../code2petri/control_flow_builder.py): automatically adds an exception-handler output while inside a try block. Inspect `wire_try_catch()` and terminal-exception handling in the same module, and both language walkers that use this shared builder.
- [`_splice_callee_net()`](../../../code2petri/inline.py): obtains all caller postset places, removes callee boundary places, and connects every callee sink predecessor to every caller continuation. A shared callee sink loses the normal/exception distinction unless it is retained elsewhere before splicing.

Define the intended bounded outcome contract before implementation: a modeled normal completion reaches the normal continuation; a modeled matching exception reaches the handler; an uncaught exception propagates or terminates according to the existing source-control-flow contract. For a call with uncertain outcome, alternative normal/exception paths must remain alternatives rather than simultaneous output tokens. Preserve the distinction through callee construction and splicing. Full Python exception-type inference is not implied by this repair; document any unsupported matching cases explicitly.

Write a failing regression at the source-to-net seam before the fix. Exercise a normal return, an explicit caught raise, an uncaught raise, and nested try/handler routing, both before and after Inline Expansion. Assert reachable completion markings or execution paths, including that one completion cannot activate both caller continuations. Inspect affected JavaScript behavior because the builder is shared.

**Done when:** The linked follow-up records the chosen representation and its limitations, the behavioral regressions fail before and pass after the fix, and a fresh Dots & Boxes export preserves the modeled outcome distinction. Record any ADR/spec change if the representation changes the accepted boundary-unification or metric contract. A successful fold alone is insufficient evidence of correct translation.

### 3. Establish structural eligibility on the historical and corrected graphs

Evaluate the supplied snapshot and a fresh export from the corrected translation independently. Loading an old snapshot does not regenerate its topology; keep the two results labeled by artifact and source version.

Trace candidate discovery in [`reduction_engine.js`](../../../code2petri/viewer/engine/reduction_engine.js), including `_discoverSESESubnets()`, `_getFunctionScopeCandidateIssue()`, `_getConsumedInteriorIssue()`, and the type-specific validators. For each relevant candidate, record its type, source/sink, consumed nodes, retained anchors, incident crossing arcs, and rejection reason. Explain why unrelated nodes such as `c_80` entered the search.

Choose the implementation branch from that evidence:

- If an existing validated component is contained in the selected Function Fold Scope, repair discovery/selection so the internal trigger and Fold Entire Function expose it. Preserve its existing class, penalty formula, and transition weights.
- If no valid contained component exists, retain the safe partial/no-progress result and explain the actual unsupported interface. Two retained exit places cannot simply be treated as one sink under the current SESE contract. Support for a different component/interface requires an explicit design decision before implementation.

Keep caller anchors, sibling nodes, complete-container checks, and consumed-interior arc checks intact. Whole-net fallback remains restricted to whole-net reduction. A graph rewrite that changes the function's behavior or SM is not a folding repair.

**Done when:** Each artifact has either a demonstrated valid candidate exercised through the production action seam, or a documented unsupported-shape result backed by its exact interface and rejection evidence. Any accepted reduction preserves all external connections and has independently checked weights/SM.

### 4. Make the stopping reason describe the selected function

`_recordRejectionReason()` currently retains the first rejection only. Other structural detector tiers can search whole-graph candidates, so the first message can mention unrelated `draw()` component `c_80` without identifying the selected function's obstacle.

Prefer scope-relevant candidate discovery and a reason tied to the selected function's actual boundary or nearest relevant rejected candidate. Retain a clear fallback when no relevant candidate exists. Add a regression in which unrelated sibling content or candidate ordering changes without making an unrelated component the function's only explanation.

**Done when:** The user-facing result explains the selected occurrence's eligibility or unsupported interface, while the existing safety rejection still excludes `c_80` and all unrelated caller/sibling content.

### 5. Verify actions, restoration, and prior passing examples

Use the production-engine and generated-viewer seams already exercised by [`TestFoldEntireFunction`](../../../tests/test_html_viewer.py), plus the source-to-net/inlining tests for the translation repair. After focused regressions pass, run the appropriate affected suites and report environmental failures separately from new failures.

- [ ] The internal trigger and Fold Entire Function agree on the actual validated reduction type or specific unsupported outcome.
- [ ] Caller interfaces, tokens, hierarchy, unrelated folds, zoom, and pan survive accepted reductions; weights and SM match the existing formulas.
- [ ] Save/open, continued folding, and Component-Local Unfold restore the exact consumed topology, boundary arcs, names, weights, and hierarchy, including nested components.
- [ ] The historical Dots & Boxes session remains readable and its outcome is recorded independently from a fresh export. Any compatibility work preserves its stored semantics rather than silently rewriting its graph.
- [ ] The two nested `GameState._coerce_direction()` occurrences and Tic Tac Toe `isBoardFull()` retain the passing behavior reported in Rounds 03–04.
- [ ] Repeat the browser checks for the affected Dots & Boxes occurrence after implementation; distinguish agent-run, user-run, headless, and unperformed checks in the result.

**Done when:** Record commands/results and browser evidence for the affected acceptance cases. Earlier `_coerce_direction()` passes concern nested Function Fold Scopes; this report's enclosing `_edge_for_move()` failure does not itself establish a regression in those passes.

### 6. Update delivery records with separate dispositions

Append the implementation and verification evidence here and under Ticket 66's Comments. Link the separate translation follow-up and record its status there. Keep prior review findings and user-confirmed passes intact; update each outstanding acceptance item only when its own evidence exists.

**Done when:** The records clearly distinguish translation correctness, historical-session support, structural eligibility/diagnostics, and browser/session acceptance. Ticket 66 remains partially verified until its remaining checklist is satisfied; a safe unsupported-shape result must be recorded explicitly rather than counted as a complete function fold.

### Plan validation

The documented replay command was executed on 2026-10-19 against the baseline above and reproduced `success: false`, `complete: false`, one pass, no folds, and the `c_80` scope rejection. All local document links resolve, fenced code blocks are balanced, and `git diff --check` passed. These checks validate the handoff and reproduction only; no implementation change, regression suite, or browser acceptance was performed for this update.

## Implementation and verification — 2026-10-20

### Separate exception-outcome follow-up

Implemented the translation correction under [Ticket 70](../issues/70-alternative-exception-outcomes.md), with the chosen bounded representation recorded in [ADR 0006](../../../docs/adr/0006-alternative-exception-outcomes.md). Inside an active `try`, an operation's normal and exceptional outcomes are competing transitions that share the same input place. Explicit `raise`/`throw` has only an exceptional destination. Function nets preserve separate normal and exceptional exits, and Inline Expansion routes each exit to its corresponding caller continuation while retaining call-resolution and call-result metadata.

Handler matching remains type-agnostic, and `finally` completion modes are not represented precisely. Ordinary operations outside an active modeled handler are treated as non-raising unless an explicit raise or an inlined callee supplies an exceptional exit; unknown external calls outside `try` are not inferred to raise. These limits are now stated in the ADR and Ticket 70.

### Historical session replay

The supplied save remains unchanged (SHA-256 `3fefd65c1af8836000e1034833c6c2b5890e95801476ee5c6985dab0a0be3711`). Replaying `executeFoldEntireFunction()` after the fix against the same snapshot produced no fold in one pass (186 ms). The current message identifies the selected function's two caller continuations, `except_entry` (`p3`) and `try_exit` (`p4`), and says that a single-exit SESE region cannot safely consume the interface. It no longer cites unrelated sibling `c_80` as the function's only explanation. The historical occurrence remains a safe no-progress result.

### Fresh export and structure

Generated a fresh viewer from the clean Python-Games source at commit `0e33c1ca98d7f6eaa17b6f3dd4209285aacbd80d`:

```sh
python3 -m code2petri.engine '/Volumes/SharedDrive/Documents/GitHub/Python-Games/Dots & Boxes/main.py' --target-function main --context '/Volumes/SharedDrive/Documents/GitHub/Python-Games/Dots & Boxes' --inline --inline-depth 12 --output /private/tmp/dots_and_boxes_round05_fresh.html --quiet
```

The HTML SHA-256 is `1a4aee112ebe6b9c0d0e6cee13289e15b5013ff487eef67fb1b1a2b05cc24c14`; the composite net has 128 places, 158 transitions, 316 arcs, and 17 compounds. In the selected `_edge_for_move()` context, three explicit raises route to caller `except_entry` (`p3`), while the inlined normal return `return (first, second)` routes to `try_exit` (`p4`). No transition routes to both places. The reduced production-engine fixture is [`dots_and_boxes_edge_for_move_fresh.json`](../../../tests/fixtures/dots_and_boxes_edge_for_move_fresh.json); it retains the 35 selected-scope nodes, the three directly connected caller places, and all 40 incident arcs.

The selected-scope Fold Entire Function action on that fixture made eight safe internal Sequence reductions over two passes, then returned a partial result with the precise two-continuation explanation. The historical fixture has no such internal progress and remains no-progress. Both artifacts therefore preserve their distinct evidence: the generated graph has safe contained reductions, but neither graph supports consuming the full function through its two caller exits under the current single-exit SESE interface. No reduction bypassed validators or changed component weights.

#### Candidate trace on the fresh fixture

The production action accepted the following candidates. Each is a `Sequence` contraction consuming the listed source transition, place, and sink transition. The only incident external arcs are the recorded retained boundary arcs; every listed weight is 1. No candidate consumes either caller continuation or a sibling-owned node.

| Component | Consumed interior | Retained boundary arcs |
| --- | --- | --- |
| `c_01` | `_coerce_direction`: `if isinstance(direction, Direction)` → `p2` → `return direction` | `merge_t4 → c_01 → p5` |
| `c_02` | `_coerce_direction`: `if isinstance(direction, str)` → `p4` → `return Direction(direction.lower())` | `merge_t1 → c_02 → p5` |
| `c_03` | `_coerce_direction`: `except ValueError` → `p6` → `return Direction[direction.upper()]` | `except_entry → c_03 → p5` |
| `c_04` | `_coerce_direction`: `except KeyError` → `p8` → `pass` | `except_entry → c_04 → merge_t4` |
| `c_05` | `_canonical_edge`: `(first, second) = call: sorted()` → `p1` → `return (first, second)` | `p6 → c_05 → try_exit` |
| `c_06` | `_edge_for_move`: integer-coordinate `if` → `p2` → explicit `TypeError` raise | `merge_t1 → c_06 → except_entry` |
| `c_07` | `_edge_for_move`: coordinate-range `if` → `p4` → explicit `ValueError` raise | `merge_t1 → c_07 → except_entry` |
| `c_08` | `_edge_for_move`: `points = {...}` → `p6` → previously accepted `c_05` | `p5 → c_08 → try_exit` |

The historical fixture produced no accepted candidate. Its relevant owned components `c_07`, `c_09`, and `c_11` each connect to both retained caller places (`p3` = `except_entry`, `p4` = `try_exit`), so these paths do not form a single-exit SESE interface. `c_80` is a sibling-owned component and is rejected as out of scope; it is not evidence of a valid function candidate. Thus the fresh graph has eight accepted internal contractions, while the historical graph has no internal progress, and both stop before consuming the function across its two exits.

### Verification limits and results

- `python3 -m unittest tests.test_exception_outcome_routing tests.test_petri_try tests.test_petri_if_branching tests.test_petri_loops tests.test_inline_expansion tests.test_python_walker tests.test_javascript_walker -q`: 187 tests passed.
- `python3 -m unittest tests.test_html_viewer.TestFoldEntireFunction -q`: 12 tests passed, including historical and fresh two-exit scope behavior.
- `python3 -m unittest tests.test_walker_protocol.TestControlFlowBuilder.test_transitions_and_exception_hook -v`: 1 test passed; the assertion now verifies a shared input place and separate normal/exception transition outputs.
- Final full-suite run, `python3 -m unittest discover -q`: 617 tests ran in 47.871s; 1 failure and 4 errors remain. The failure is the prototype runner test's unavailable test port. Errors are missing optional `pygraphviz` and `pytest`, plus existing API-shape expectations for `PetriNet.initial_net` and two-value `WalkResult` unpacking. The earlier full-suite attempt also caught the stale exception-hook assertion; it was updated and passes in the final run.
- `python3 -m unittest tests.test_html_viewer -q`: 176 tests ran; one existing integration error remains in `test_javascript_assigned_functions_keep_owner_jsdoc_and_expression_text`, which expects `PetriNet.initial_net`. The same incompatible return-shape expectation is documented in earlier Ticket 66 records.
- `python3 -m compileall -q code2petri tests`, `node --check code2petri/viewer/engine/reduction_engine.js`, and `git diff --check` passed.
- Regression-first evidence: before the fixes, `test_continue_inside_try_does_not_activate_handler` failed because the handler was reachable from `continue`, and `test_returned_callee_exception_is_caught_after_inline_expansion` failed because the caught callee exception could not reach the caller's normal end. Both pass after their corresponding fixes. The returned-callee test also confirms that the handler entry is reachable and no reachable marking contains both the normal and exception continuations. The nested-handler-after-inlining regression passes and preserves the nested routing behavior.
- The full generated-export action previously exceeded 60 seconds and was interrupted. The compact fixture exercised the production engine's scoped action instead. No browser action, save/open, or local-unfold acceptance was performed for this Round 05 occurrence.

### Two-axis review

Reviewed the staged implementation against fixed point `74c1d320bb0c7e13ba53958838715aa5e84c41d7`.

- Standards: no documented-standard breaches or actionable code-smell findings remain.
- Spec: no remaining requirements gaps or scope creep. Browser, save/open, and local-unfold acceptance remain unperformed and open.

Ticket 66 remains partially verified. The precise outcome translation is resolved separately in Ticket 70; full function folding through this two-exit interface, browser interaction, and save/open/local-unfold acceptance remain open.
