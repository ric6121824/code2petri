# Ticket 66 — Round 08: Repair the Fold Entire Function tests

**Reviewed** 2026-11-16 on `codex/phase-2.8.2-call-refolding` at `45be92e`.

The user passed the `isBoardFull()` fold, save/reopen, and local-unfold checks. They also confirmed that [Round 07](phase-2.8-ticket-66-round-07.md) now names the correct pair of continuations for each `_coerce_direction()` occurrence. [Ticket 66](../issues/66-function-scoped-structural-folding.md) is awaiting a passing automated run on the repaired tests.

## Finding

The [shared test harness](../../../tests/test_html_viewer.py#L72) already defines the Fold Entire Function button mock and `hudEls` and wires the production handler. Four test methods add their own copies to the same JavaScript script. Node stops at `SyntaxError: Identifier 'hudBtnFoldEntireFunction' has already been declared` before any of their graph checks run. The fourth method has two affected subtests, `split` and `merge`.

| Test method | Checks to retain |
| --- | --- |
| [`test_compound_inspector_offers_action_and_reports_completion`](../../../tests/test_html_viewer.py#L7235) | Button visibility, completion message, one layout, and stable zoom/pan. |
| [`test_fused_function_entrance_loop_head_is_scoped_state_machine_and_reversible`](../../../tests/test_html_viewer.py#L7343) | Internal trigger and sidebar action, caller boundaries, sibling eligibility, rejection reasons, State Machine weight and SM, and exact save/reopen/unfold restoration. |
| [`test_ordinary_singleton_sidebar_action_and_boundary_sequence_unfold_preserve_prior_state`](../../../tests/test_html_viewer.py#L7183) | Sidebar fold, stable zoom/pan, and unfolding a surrounding Sequence that restores the previously collapsed function. |
| [`test_fold_entire_function_sidebar_action_completes_both_boundary_directions`](../../../tests/test_html_viewer.py#L6319) | Successful sidebar folds for both Choice boundary directions, preserving caller places, tokens, and the unrelated path. |

## Implementation steps for Luna

1. In `_setup_live_fold_test_harness` in `tests/test_html_viewer.py`, add one `const inspectorActionResult = {{ textContent: '' }};` alongside the other element mocks. In the fake `document.getElementById`, return it for `'inspector-action-result'` so the [production element resolver](../../../code2petri/viewer/template.html#L2355) can find it. Keep the existing shared button, `hudEls`, and production event registration.
2. In all four methods above, remove the local declarations of `inspectorActionResult`, `hudBtnFoldEntireFunction`, and `hudEls`. Remove the local `action_match` and `fold_helpers` extraction and the lines that insert them into each script. The shared harness already extracts those functions from the viewer template. Keep the compound-inspector test's assertions about the template's controls and handler.
3. After `openInspector(...)`, use `hudBtnFoldEntireFunction.click()` in each test. In the fused loop test, check the button's visibility and let the completion assertions verify that the click reached the real listener. Keep the fixtures, existing layout mocks and counters, and behavioral assertions in the table. Confine the repair to `tests/test_html_viewer.py`.

## Verification

All four affected methods passed after applying these steps to a temporary copy of the test module, including both boundary subtests. The broader run passed 57 tests, including the Round 07 external-continuation diagnostic and the viewer action history checks. Run the same test targets from the `code2flow` repository after applying the repair.

```sh
python3 -m unittest \
  tests.test_html_viewer.TestFoldEntireFunction \
  tests.test_html_viewer.TestCalledFunctionChoiceBoundary \
  tests.test_html_viewer.TestBatchPlaceFold \
  tests.test_viewer_action_history
```

Record the run and its commit under Ticket 66. Use the passing tests and the recorded browser checks to reconcile the remaining checklist items before closing the ticket.
