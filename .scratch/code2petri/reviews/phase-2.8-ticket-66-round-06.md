# Code Review — Phase 2.8, Ticket 66, Round 06

**Review date:** 2026-10-20
**Review range:** `74c1d320bb0c7e13ba53958838715aa5e84c41d7...HEAD`
**Commit reviewed:** `e401ee5 fix: preserve alternative exception outcomes`
**Spec sources:** [Round 05 implementation plan and evidence](./phase-2.8-ticket-66-round-05.md), [Ticket 70 — Alternative Exception Outcomes](../issues/70-alternative-exception-outcomes.md), and [ADR 0006](../../../docs/adr/0006-alternative-exception-outcomes.md)
**Result:** Standards review found no issues. Spec review found an uncaught-exception routing defect through `finally`; generated-viewer browser/session acceptance also remains pending.

## Standards

No documented-standard breaches or actionable baseline code smells were found in the reviewed diff. The issue and decision records follow the repository's local Markdown conventions and domain vocabulary.

## Spec

### [P1] An uncaught exception through `finally` becomes normal completion

Round 05 requires: “an uncaught exception propagates or terminates according to the existing source-control-flow contract.” In [`ControlFlowBuilder.wire_try_catch()`](</Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/control_flow_builder.py:317>), when there are no handlers but a `finally` block exists, the synthetic `exception` transition sends the exception to `finally_target`; the finally body then always targets `try_exit`. For a final try statement, `try_exit` is the normal function end.

I reproduced this with:

```python
def sample():
    try:
        raise ValueError()
    finally:
        cleanup()
```

The generated net has no `exception_end` place and reaches `end`. The documented limitation that exception propagation through `finally` is not modeled precisely does not make routing an uncaught exception to successful completion conservative.

#### Suggestions — preserve the pending outcome through cleanup

1. **Start with a failing behavioral regression.** Translate the sample above through the production Python walker and enumerate its reachable markings. Assert that normal completion is unreachable, an exceptional boundary is reachable, and every completing exceptional path runs cleanup first. Also test a non-final try statement followed by an ordinary statement: an uncaught exception must not resume that statement. Place/transition counts or the presence of a finally-entry arc alone do not establish these behaviors.
2. **Retain the incoming completion outcome until finally completes.** The shared finally entry currently merges normal and exceptional flows, losing the distinction needed at its exit. Give the routing enough state to resume either normal execution or the pending exception correctly. Separate ordinary-net paths are one representation option; document the chosen representation rather than merging the paths and choosing an arbitrary output afterward. Keep one completion on one outcome path, with bipartite arcs and existing caller interfaces intact.
3. **Resume exception propagation after cleanup.** Once a normally completing finally body has run, route the pending exception to the active outer handler or exceptional function boundary. Exercise nested finally blocks so cleanup ordering is preserved and an inner cleanup does not discard the exception. An explicit raise inside cleanup must also remain exceptional. Keep still-unsupported return/break/continue overrides and exception-type matching explicitly bounded; the simple uncaught-raise case is part of the normal/exception correctness contract.
4. **Verify both languages and Inline Expansion.** Add the equivalent JavaScript throw/try/finally case because the builder is shared. Use a callee that raises through finally and a caller that catches it; assert that cleanup precedes the caller handler, that the caller's normal post-call continuation is not taken on that exception, and that no marking activates normal and exceptional continuations together. Include normal-through-finally and handled-exception-through-finally controls so the repair preserves successful paths. Retain the existing nested-handler and returned-callee exception regressions.
5. **Record the representation's consequences.** If the repair creates additional control-flow nodes, check their IDs, call metadata, Inline Expansion mapping, and transition-weight accounting. Distinguish expected net/SM changes from presentation changes; do not infer that an increasing running score means inline transitions were absent. Update [ADR 0006](../../../docs/adr/0006-alternative-exception-outcomes.md) with the supported propagation behavior and remaining limits when the implementation exists.
6. **Track the repair in the existing Ticket 70.** [Ticket 70](../issues/70-alternative-exception-outcomes.md) is reopened as `ready-for-agent` with the original implementation history retained and new unchecked finally criteria. Keep this as a verifiable source-to-net-to-inlined-caller repair. Full multi-exit call refolding and concurrency recognition do not gate this fix.

**Completion evidence:** Record a failing-before/passing-after regression for the minimal case, execution-path or reachable-marking evidence for the controls and inlined caller, the affected Python/JavaScript suite results, and the final commit. A passing existing suite that lacks the reproduction does not close this finding.

### Acceptance still pending

Round 05's verification plan calls for browser checks using the affected Dots & Boxes session, including save/reopen and local unfold. The report records these checks as unperformed. The headless regressions and 174 passing focused tests do not establish that generated-viewer/session acceptance.

#### Suggestions — verify the actual generated viewer and session lifecycle

1. After the routing repair, generate a fresh Dots & Boxes viewer and record the source commit, generator commit, artifact hash, and exact selected function occurrence. Keep the historical session as a separately identified artifact; opening it does not regenerate its stored topology.
2. Exercise the generated viewer's internal fold trigger and Fold Entire Function action. Record accepted reductions, final completeness, remaining normal/exception interfaces, displayed weights/SM, and specific stopping reasons. Verify that caller/sibling nodes, tokens, hierarchy, node positions, zoom, and pan remain intact. Preserve the earlier user-confirmed nested `_coerce_direction()` and `isBoardFull()` passes as separate evidence.
3. Save the edited graph, open it in a fresh viewer instance, continue an eligible edit, and use Component-Local Unfold on a resulting component and a nested component. Compare topology, caller arcs and weights, alternative outcomes, names, hierarchy, positions, and viewport against the captured expected state. Check that rejected malformed sessions leave the current document intact.
4. Run the real browser workflow in addition to the production-engine/generated-viewer headless regressions. If a large export exceeds the runtime limit, record the interrupted operation and its elapsed time; a compact fixture is supporting evidence, not a replacement browser pass. Report checks as agent-run, user-run, failed, or unperformed, with the relevant artifact IDs.

**Completion evidence:** A reproducible browser/session record covering those actions, plus the relevant automated regression results. Leave unperformed items open in Ticket 66; successful parser acceptance or headless folding alone does not satisfy them.

**Scope clarification from the user:** The intended function action restores an expanded function to an opaque call abstraction, as if it had not been Inline Expanded, while retaining its alternative caller outcomes and reversible subnet. The currently reported safe partial SESE reduction does not fulfill that broader refolding goal. Specify and implement that call-level abstraction separately from Ticket 70's outcome-routing repair, including its accumulated-weight/SM contract; preserve distinct normal and exception routes rather than connecting both as simultaneous outputs of one ordinary transition. Existing Marked Graph folding handles AND synchronization patterns, which have different semantics from these alternative exits.

## Verification

The following focused suite passed during this review:

```text
python3 -m unittest tests.test_exception_outcome_routing tests.test_petri_try tests.test_javascript_walker tests.test_python_walker tests.test_inline_expansion tests.test_html_viewer.TestFoldEntireFunction -q
Ran 174 tests — OK
```

The focused suite does not cover the uncaught-raise-through-`finally` case above. No code was changed during this review.

**Totals:** Standards: 0 findings. Spec: 2 findings (one behavioral defect and one incomplete acceptance item). The worst issue is the P1 loss of exceptional completion through `finally`.

## Suggestion validation — 2026-10-20

An independent production-walker replay at `e401ee5e6233782f13db3397df1ab5349ccd4b69`, using the existing reachable-marking helper, returned `normal_end_reachable: true`, `exception_end_exists: false`, and `exception_end_reachable: false` for the sample above. The assertion that an uncaught exception cannot reach normal completion failed as expected. This confirms the P1 reproduction; no implementation repair, new permanent regression, full-suite rerun, or browser/session acceptance was performed while adding these suggestions.

## Human browser check — session snapshot open — 2026-10-20

**User-reported browser result:** The Tic Tac Toe 2026-10-17 session opens in its generated viewer. Opening the Dots & Boxes 2026-10-17 session in its generated viewer fails with:

```text
Invalid Fold State Snapshot: graph element.call_results[0].transition_id does not match its owning transition
```

**Read-only artifact comparison:** The current production `parseFoldStateSnapshot()` accepts both supplied saves. The Tic Tac Toe save has zero call-result owner-ID mismatches. The Dots & Boxes save has 138 mismatches across graph elements and nested restoration records; for example, `inline_main__t1` owns a record whose `transition_id` is still `t1`.

The generated viewer bundles differ. The Tic Tac Toe HTML contains `_migrateLegacyInlineCallResultIds`; the Dots & Boxes HTML lacks that migration but contains the same strict owner check. This explains the reported contrast: the Dots & Boxes save is accepted by the current parser, but its existing generated viewer predates the compatibility migration and rejects the legacy inlined ID. The evidence points to a stale embedded viewer bundle, not new corruption of the save.

Artifact identities:

| Artifact | SHA-256 |
| --- | --- |
| Tic Tac Toe session save | `f52b5fad2f0cdc68fdbd0bdc6ea8ad5de5a81bd611d61a060bab0c0047c37e0a` |
| Dots & Boxes session save | `853392baaa43ff3c8bbfe521f2a6f4011b0d29102082a0fdc78f08fb02c0eef9` |
| Tic Tac Toe generated HTML | `4cc56982d3cc513658a01b70a600c25259df7127f308895705e4c82a707fccea` |
| Dots & Boxes generated HTML | `fa96bba96767dafc7b01b54663ef7d0eda59daae745a1ce59a68ed2dae12dee5` |

The user's initial browser attempt is recorded as **failed in the existing 261017 Dots & Boxes viewer**. The agent did not modify that HTML or either save.

### Follow-up — newest Dots & Boxes export

The user reports that they exported Dots & Boxes with the newest project version and confirmed the open-session issue is fixed. This is a **user-run browser pass for the newest export**; the agent did not operate the browser. The current export is in `Dots_and_Boxes-261020`. Its generated HTML now embeds `_migrateLegacyInlineCallResultIds`, and its session save passes the current production parser (203 graph elements; engine step counter 102).

| Newest artifact | SHA-256 |
| --- | --- |
| `Dots_and_Boxes-261020/dots_and_boxes_global_foldable.html` | `31d8671d2af89cc839c5da5bf8b068639bd312dc80229d1a8949a907b4cd4034` |
| `Dots_and_Boxes-261020/dots_and_boxes_global_foldable_session_save.json` | `fcf5c18646487441f4e8cb2c19e2a62dfe815aa84c3eede41749c9073802e9b4` |

This supersedes the pending retry for the newest export: session opening is **passed by user confirmation**. The historical 261017 viewer remains stale and still lacks the migration; the old browser failure is retained as historical evidence. This does not check off Ticket 66's broader save/edit/unfold acceptance criterion, and that checklist remains unchanged.

## Implementation follow-up — 2026-10-20

### Finally outcome repair

The new Python production-walker regressions failed before the repair: the uncaught raise through `finally` produced no `exception_end`, and an uncaught exception from a non-final try could execute the following statement. The shared builder now translates the cleanup body on separate normal and pending-exception paths. Normal cleanup returns to the try exit; normally completing exceptional cleanup relays to the enclosing handler or function exceptional boundary. Exceptions in handler/`else` bodies run cleanup before propagation, and exceptions raised by cleanup replace the pending completion. Return/break/continue overrides and exception-type matching remain unsupported.

The regression paths cover uncaught Python raise, following-statement suppression, normal completion and handled raise controls, nested cleanup order, cleanup raise, JavaScript throw/finally, and Inline Expansion into a catching caller. The inlined caller trace runs cleanup before its handler, skips the in-try continuation, and completes the handler's following statement. The test also verifies that the two cloned cleanup call sites have distinct transition IDs, retain matching call-result owner IDs after Inline Expansion, and start at transition weight `1.0`.

The first focused command passed: `python3 -m unittest tests.test_exception_outcome_routing tests.test_petri_try tests.test_javascript_walker tests.test_python_walker tests.test_inline_expansion -q` — **170 tests, OK**. The Spec review identified two remaining evidence gaps: JavaScript controls for normal/handled/cleanup-raise outcomes, and a direct cleanup-before-handler order assertion in the inlined trace. Both are now covered in `tests.test_exception_outcome_routing`. The updated exception-routing module passes **19 tests**, including the additional JavaScript controls and explicit order check. `compileall` for the changed Python modules and `git diff --check` also passed. The full-suite result and final implementation commit are recorded below after the final verification pass.

### Final implementation verification — 2026-10-20

The final focused suite passed after the review fixes:

```text
python3 -m unittest tests.test_exception_outcome_routing tests.test_petri_try tests.test_javascript_walker tests.test_python_walker tests.test_inline_expansion -q
Ran 172 tests — OK
```

The full suite was run once with `python3 -m unittest discover -q`:

```text
Ran 627 tests in 46.795s
FAILED (failures=1, errors=4)
```

The failure was `tests.test_live_fold_prototype.TestLiveFoldPrototype.test_prototype_runner_check`, whose prototype runner reported that it could not bind a test port. The four errors were: missing optional `pygraphviz` while importing `tests.test_graphs`; missing `pytest` while importing `tests.test_interface`; `PetriNet` lacking the `initial_net` attribute expected by `test_javascript_assigned_functions_keep_owner_jsdoc_and_expression_text`; and `test_walk_result_namedtuple` expecting two-value unpacking from a three-value result. These failures are outside the changed finally-routing paths. The focused changed-area suite passed.

Both required code-review axes were rerun against `e401ee5...2f5c492` after the review fixes:

- **Standards:** 0 findings. The earlier duplicate try-context and firing-helper concerns were addressed.
- **Spec:** 0 findings. Python/JavaScript outcomes, nested cleanup, cleanup exceptions, and Inline Expansion caller propagation match the Round 06 implementation criteria.

The implementation commits are `6a1e97f` (`fix: preserve exceptions through finally`), `b5ea509` (`test: cover JavaScript finally outcomes`), `4cf6ea4` (`refactor: share exception routing helpers`), and `2f5c492` (`refactor: simplify optional finally context`). Browser/session save-edit-unfold acceptance remains open in Ticket 66; the user-confirmed newest-export open pass is recorded above.
