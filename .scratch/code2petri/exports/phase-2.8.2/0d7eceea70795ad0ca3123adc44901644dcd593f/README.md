# Phase 2.8.2 — Call Refolding browser artifacts

This directory contains regenerated browser builds from generator commit `0d7eceea70795ad0ca3123adc44901644dcd593f`. It is a new commit-named snapshot; existing exports and reviewed builds were left unchanged.

## Provenance

- **Generator repository:** `code2flow`, integration branch `codex/phase-2.8.2-call-refolding`
- **Generator commit:** `0d7eceea70795ad0ca3123adc44901644dcd593f`
- **Source game:** `Python-Games/Dots & Boxes/rules.py`
- **Source-game commit:** `3ea8f5ea8b8514dca03e706c45b6cd7e8ca5672c`
- **Target:** `GameState.apply_move`, containing the `GameState._edge_for_move` call occurrence

## Generation commands

These commands were run from `/private/tmp/code2flow-phase-2.8.2-integration` at the generator commit above. The generated files were then moved from the temporary output directory into this snapshot.

```sh
python3 -c 'from code2petri.engine import code2petri; code2petri(source_path="/Volumes/SharedDrive/Documents/GitHub/Python-Games/Dots & Boxes/rules.py", target_function="GameState.apply_move", output_file="/private/tmp/code2petri-phase-2.8.2/browser-call-expansion.html", no_fold=True)'

python3 -c 'from code2petri.engine import code2petri; code2petri(source_path="/Volumes/SharedDrive/Documents/GitHub/Python-Games/Dots & Boxes/rules.py", target_function="GameState.apply_move", output_file="/private/tmp/code2petri-phase-2.8.2/backend-inlined.html", context=["/Volumes/SharedDrive/Documents/GitHub/Python-Games/Dots & Boxes/rules.py"], inline=True, no_fold=True)'
```

`browser-call-expansion.html` starts without backend inline expansion. `backend-inlined.html` is generated with `--inline` behavior through the Python API and the source file as call-resolution context.

## SHA-256

| File | SHA-256 |
| --- | --- |
| `backend-inlined.html` | `ff3a1dd355f9458e7a73cd743f83768b2ea07b01efc43865b7ee2bf09e9253fe` |
| `browser-call-expansion.html` | `cf57974ccbd9d3be0fc136c8eb97f5dd72f6062e723c1289dfaa9eacb4af175e` |
| `backend-inlined_session_save.json` | `54958fa266b8afb6cf7e119ae1a0715a75ae1ee3ee7b876196b7e622e98d45f8` |

The session file was copied from `/Users/pingchungtsai/Downloads/backend-inlined_session_save.json`. It is the saved progression cited in the review and contains the leaked live reduction components from the pre-fix Fold/Unfold failure.

## Related review and acceptance

- Phase 2.8.2 review round 01 records the reproduced leak, saved-session evidence, and repair requirements. It is tracked on `master` in commit `5fddc58306360b260db124d9d5cfb595f7063acb` and has not yet been merged into this integration branch. Retrieve the exact report with `git show 5fddc58306360b260db124d9d5cfb595f7063acb:.scratch/code2petri/reviews/phase-2.8.2-review-round-01.md`. Its repository location after integration is `.scratch/code2petri/reviews/phase-2.8.2-review-round-01.md`.
- The leak fix is in commit `683bc84`; descendant collection was consolidated in generator commit `0d7ecee`.
- The reviewer's earlier backend-inlined build had SHA-256 `d30dd0dc91d63986df1b092bed10a26253f6ad3467389213f70d72d70659d170`. The regenerated builds in this directory were generated after the fix.
- **User-run browser check:** The user recorded manual testing in `phase-2.8.2-human-acceptance-checklist.md` using Safari 18.6. They marked normal/exception routing, Fold/Unfold, three-cycle leak removal, history, save/reopen, and continued editing as done for both paths; backend-inlined PNML outcome preservation was also checked. They reported layout/position restoration problems during Undo/Redo/Unfold, skipped browser-expanded PNML export, and could not read the full inline node ID in the inspector. The Ticket 73 historical invalid-fallback scenario was skipped because its old session fails to open with a duplicate node ID. Browser acceptance remains partial, not complete.
- Multi-outcome final SM remains unavailable while outcome-aware metric research continues.
