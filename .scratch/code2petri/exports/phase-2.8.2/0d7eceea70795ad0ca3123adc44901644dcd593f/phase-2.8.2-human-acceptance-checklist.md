# Phase 2.8.2 — Human Browser Acceptance Checklist

Use this checklist to record actual browser results for the open Phase 2.8.2 acceptance gates. Run each artifact from a fresh browser tab and save evidence before moving to the next case. Do not treat a headless test, an older generated file, or a different saved session as a pass.

## Test identity

- Tester: ______________________________
- Date/time and timezone: ______________________________
- Browser/version and OS: __Safari Version 18.6 (18621.3.11.19.1, 18621)____
- Candidate branch/commit: `codex/phase-2.8.2-call-refolding` / `99f798c576e04905b3143c42695e2e7127d690dd` (code candidate `0d7eceea70795ad0ca3123adc44901644dcd593f`)
- Dots & Boxes source commit: `3ea8f5ea8b8514dca03e706c45b6cd7e8ca5672c`
- Generator commit: `0d7eceea70795ad0ca3123adc44901644dcd593f`
- Evidence folder or links: ______________________________

Before testing, verify the files' hashes. If either file differs, stop and record the actual artifact identity before using it.

**Artifact location and verification:** the two files are now in the commit-named export snapshot below. I verified that both SHA-256 values match the snapshot's `README.md`. Open these exported copies. If you replace or regenerate one, record its new generator commit and hash before testing.

| Expansion path | File | Expected SHA-256 | Actual SHA-256 | Result |
| --- | --- | --- | --- | --- |
| Browser-expanded call | `/Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/exports/phase-2.8.2/0d7eceea70795ad0ca3123adc44901644dcd593f/browser-call-expansion.html` | `cf57974ccbd9d3be0fc136c8eb97f5dd72f6062e723c1289dfaa9eacb4af175e` | `cf57974ccbd9d3be0fc136c8eb97f5dd72f6062e723c1289dfaa9eacb4af175e` | Not run |
| Backend-inlined call | `/Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/exports/phase-2.8.2/0d7eceea70795ad0ca3123adc44901644dcd593f/backend-inlined.html` | `ff3a1dd355f9458e7a73cd743f83768b2ea07b01efc43865b7ee2bf09e9253fe` | `ff3a1dd355f9458e7a73cd743f83768b2ea07b01efc43865b7ee2bf09e9253fe` | Not run |

The same folder contains `backend-inlined_session_save.json` (SHA-256 `54958fa266b8afb6cf7e119ae1a0715a75ae1ee3ee7b876196b7e622e98d45f8`), the **pre-fix Fold/Unfold leak progression**. It is useful as evidence for the `c_x` regression, but it is not the historical Ticket 73 pre-fallback session and must not be used as a substitute for that case.

## 1. Browser-expanded call

Open the browser-expanded artifact above. The target is `GameState.apply_move`, including the `_edge_for_move()` call occurrence.

- [x] Locate and expand the target call. Record the occurrence ID and visible caller context: _Current graph, line 96, ID t4, occurrence [[],"t4"]_
- [x] Verify a normal return connects to the caller's next statement; there is no disconnected normal ending.
- [x] Verify an uncaught exception connects to the caller's exceptional boundary; it does not enter normal continuation.
- [x] If a caller handler is present, verify the exception reaches that handler. Record the handler/context: _return self._rejected('unsupported_move')_
- [x] Verify normal and exceptional outcomes remain alternatives, not a transition fan-out that activates both.
- [x] Make an unrelated edit and/or fold a sibling component before folding the target. Verify those edits remain intact.
- [x] Run **Fold Entire Function**. Verify the call abstraction and its separate outcomes are restored, and no expanded interior remains as a duplicate route or operation.
- [x] Confirm the multi-outcome result does not claim a verified final SM. The UI shows final SM unavailable and accumulated reduction weight separately.
 - QA note: The final SM score display is removed.
- [x] Run **Component-Local Unfold**. Verify the exact pre-fold function diagram, prior manual folds, names, metadata, hierarchy, weights, markings, and positions return. Verify the unrelated edit remains.
- [x] Repeat Fold → Unfold for three cycles. After each Fold, no new `c_x` reduction component leaks into the live graph; after each Unfold, no automatic component remains. Later component numbers may advance, but graph state and accumulated contribution must not inflate.
- [x] Verify one Undo reverses the complete Fold action and Redo restores that recorded Fold result.
 - QA note: Although the connections are restored, the layout isn't: nodes other than the folded/unfolded nodes remain at their position after undo/redo.
- [x] Save, reopen, and continue editing; verify local Unfold still restores the function without relying on chronological Undo history.
- [ ] Export PNML and inspect that outcome alternatives and operation weights match the visible graph.
 - QA note: skipped.

Result: **Partial** — routing, Fold/Unfold, three-cycle, history, and save/reopen checks are marked done. The user reported layout/position restoration problems during Undo/Redo; PNML export was skipped for this path.  
Notes, steps to reproduce, screenshots, and saved-session path:  
____________________________________________________________________________
____________________________________________________________________________

## 2. Backend-inlined call

Open the backend-inlined artifact above. It targets `GameState.apply_move` with backend inlining enabled.

- [ ] Locate the `_edge_for_move()` occurrence and both nested `_coerce_direction()` occurrences. Record IDs: _The ID is too long. The node inspector can't display the full node ID_
- [x] Verify normal and exceptional routes independently, including the applicable caller handler or exceptional boundary.
- [x] Make a prior manual fold inside the selected function and an unrelated edit outside it.
- [x] Run **Fold Entire Function**. Verify only the intended occurrence is reduced/refolded; no generated `c_x` survives as an extra live node, duplicate path, or extra score contribution.
- [x] Confirm final SM remains unavailable for the multi-outcome result and accumulated weight is separate.
- [x] Run **Component-Local Unfold**. Verify the selected function returns exactly to its pre-action state, including the prior manual fold; preserve the unrelated later edit and current view.
 - QA note: Although the connections are restored, the layout isn't: nodes other than the folded/unfolded nodes remain at their position after unfolding. The folding mechanic still adjusts its layout.
- [x] Repeat Fold → Unfold for three cycles. Record any surviving `c_x` IDs after each action: cycle 1 _none_; cycle 2 _none_; cycle 3 ___none___. Expected: none from the automatic refold remain live after Fold; exact pre-action state returns after Unfold.
- [x] Verify Undo/Redo as one action, save/reopen, continued editing, and PNML outcome preservation.

Result: **Partial** — routing, Fold/Unfold, three-cycle, history, save/reopen, and PNML checks are marked done. The user reported layout/position restoration problems during Unfold. The inspector did not display the long inline node ID; use the Search graph result row for its full occurrence ID and owner path.  
Notes, steps to reproduce, screenshots, and saved-session path:  
____________________________________________________________________________
____________________________________________________________________________

## 3. Ticket 73 historical invalid-fallback reproduction

The exact retained session from immediately before the invalid final whole-net fold is not available as an openable graph. The exported `backend-inlined_session_save.json` is the pre-fix Fold/Unfold leak progression, not the Ticket 73 refusal session. The fresh HTML files are **not** substitutes for that historical refusal scenario.

- Historical session/artifact located? **No**.
- Open attempt result: **Skipped**. The old graph was rejected with `Invalid Fold State Snapshot: graph or restoration data contains a duplicate node ID`.
- Do not repair or substitute another graph for this historical refusal check.
- [ ] Open the exact pre-fold state and invoke the same whole-net fallback that previously consumed the exceptional exit.
- [ ] Verify refusal leaves both exits, nodes, arcs, markings, weights, names, metadata, component allocation, history, and camera unchanged.
- [ ] Verify the result explains why the reduction is incomplete; final SM is unavailable, and accumulated weight is reported separately. Confirm the old misleading `2200` result is not presented for the recorded running weight `22`.
- [ ] Verify safe local reductions remain available where eligible.
- [ ] Export the preserved graph and reopen it; verify the exit topology remains intact.
- [ ] Run a supported single-exit control and verify its established score and behavior remain valid.

Result: **Skipped** (historical session cannot be opened; duplicate node ID in fold-state snapshot).  
Notes and evidence:  
____________________________________________________________________________
____________________________________________________________________________

## 4. Scoring decision gate (not a browser pass)

Ticket 71's outcome-aware SM derivation is intentionally unresolved. The current implementation should keep final SM unavailable for multi-outcome refolded calls. Do not enter a numeric final SM as accepted based on these browser checks. Keep the metric gate open until the scoring representation, boundary treatment, and expected values are independently justified for a sequence, conditional return/error, nested handlers, and a genuinely Unstructured control, while preserving established single-exit results.

- Current UI reports final SM unavailable for multi-outcome calls: **Pass**
- Accumulated weight is visible separately: **Pass**
- Metric/design decision reference, if resolved: ______________________________
- Ticket 71 scoring gate: **Open**

## Final disposition

- Ticket 71 browser acceptance: **Open** (layout/position restoration and score-design gates remain)
- Ticket 72 browser acceptance: **Open** (manual checks recorded; complete acceptance remains outstanding)
- Ticket 73 historical refusal acceptance: **Skipped — invalid historical session snapshot (duplicate node ID)**
- Remaining failures or blocked evidence: layout/position restoration during Undo/Redo/Unfold; browser-expanded PNML export skipped; full backend-inlined occurrence IDs not copied from Search graph; Ticket 73 historical session skipped; score-design gate open.
- Follow-up review/report updated at: `.scratch/code2petri/reviews/phase-2.8.2-review-round-02.md`

Record browser acceptance as passed only for scenarios actually completed on the identified candidate artifacts. Keep failures and unperformed checks explicit in Tickets 71–73.
