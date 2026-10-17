# Phase 2.8.1: Viewer Search and Action History

Status: implemented; browser acceptance incomplete

Design agreed 2026-10-17. Implementation is complete; the user manually confirmed Undo/Redo, while the remaining generated-viewer browser acceptance stays open in Tickets 68–69. This standalone specification owns the search and Undo/Redo requirements extracted from Phase 2.8; the delivered viewer remains its baseline. Retain the original two tickets with their approved scope and dependency. No further child-ticket split is planned.

## Problem Statement

Large nets are difficult to navigate by sight, especially when a desired node is retained inside several folded components. Users need to find the exact occurrence, distinguish repeated calls, and decide when to reveal it without disturbing unrelated folds.

The viewer also lacks chronological Undo/Redo for live edits. Component-Local Unfold restores a chosen subnet but does not reverse a rename, a move, Reset, or an entire multi-step gesture. Searching for hidden nodes adds a Reveal action that must be reversible as one gesture and must not leave a partially changed graph if restoration fails.

## Solution

Provide top-toolbar search across the current graph and all its restorable hidden nodes. Match labels, stored original function names, custom names, and IDs using case-insensitive substrings. Selecting a match performs Locate: center its visible node or containing component at the current zoom. An explicit Reveal action opens only the containing folds needed to expose the exact occurrence, preserving unrelated folds and using the existing Component-local Unfold layout behavior.

Add session-local Viewer Action History alongside Component-Local Unfold. One committed user gesture is one entry, including an entire batch, function fold, compound/group move, or nested Reveal. Undo/Redo restores exact graph/editing state while preserving current zoom/pan and viewing preferences. Save Session retains ordinary nested restoration records without action-history stacks; a successful Open Session starts fresh history and search.

## User Stories

1. As a user, I want to search visible nodes and nodes retained inside nested folds, so that folding does not prevent discovery.
2. As a user, I want partial matching across labels, original function names, custom names, and IDs regardless of case, so that exact display spelling is unnecessary.
3. As a user, I want repeated occurrences distinguished by caller path and ID, so that I choose the intended call.
4. As a user, I want only current/restorable occurrences in results, so that unused definitions and other playback states do not create misleading matches.
5. As a user, I want Locate to highlight and center a result or its visible container without editing the graph, so that searching does not fold or unfold nodes.
6. As a user, I want an explicit Reveal action for a hidden match, so that I control when its containing folds open.
7. As a user, I want one Undo to reverse the entire Reveal, so that multiple nested unfolds remain one intentional edit.
8. As a user, I want Locate and Reveal to preserve zoom and center their target, so that navigation does not fit the entire graph.
9. As a user, I want Reveal to preserve unrelated folds and use the same layout as right-click Component-local Unfold, so that opening a nested target behaves like the existing unfold gesture.
10. As a user, I want search and Undo/Redo in the top toolbar, so that they remain accessible with the sidebar hidden.
11. As a keyboard user, I want Up/Down to navigate results, Enter to Locate, and Escape to close the dropdown, so that I can search without accidental unfolding.
12. As a user, I want my query retained and results refreshed after edits, Reset, Undo, and Redo, so that results describe the current graph.
13. As a user, I want successful Open Session to clear search and history, so that a different document starts from its own current state.
14. As a user, I want Undo/Redo for folds, unfolds, committed renames, moves, Reset, playback, and function expansion/collapse, so that accidental edits are reversible.
15. As a user, I want each batch, function fold, drag, and Reveal to occupy one entry, so that history follows gestures rather than internal processing steps.
16. As a user, I want Redo to restore the exact recorded result, so that it does not choose another reduction or component identity.
17. As a user, I want Undo/Redo to preserve current zoom and pan, so that it does not rewind subsequent navigation.
18. As a user, I want errors to restore the starting graph and history position, so that failed multi-level restoration cannot leave partial edits.
19. As a user, I want new successful edits after Undo to clear Redo while failed/unchanged actions preserve it, so that branching is predictable.
20. As a user, I want history limited to the current open viewer, so that saved sessions retain local unfolding without large action stacks.
21. As a user, I want bounded history that retains the newest action, so that large nets do not accumulate unlimited states.
22. As a user, I want normal text-editing shortcuts inside text fields, so that Undo while typing does not unexpectedly change the graph.
23. As a user, I want search highlighting separate from selection and inspection, so that finding a node does not disturb a batch selection or draft.
24. As a user, I want unfinished naming text retained when its inspected node survives history restoration, so that unrelated history operations do not discard it.

## Implementation Decisions

### Search and Locate

- **Search universe:** Include active places, transitions, and function compounds plus nodes reachable through their nested restoration records. Read canonical and compatible legacy restoration fields with existing precedence; avoid duplicate traversal/results for the same logical occurrence. Exclude unused definitions, unexpanded callee-template copies outside this graph, original-net backups, and other playback states. Operate offline without reading or executing source.
- **Matching and occurrence identity:** Use literal case-insensitive substring matching on stored labels, original function names, custom names, and IDs. Do not invent overwritten labels or unavailable caller line numbers. Show repeated occurrences separately with caller path, unique ID, source location where available, and visible/hidden state. Track exact occurrence and restoration ownership separately from compound ancestry or shared callee-definition identity; re-resolve after mutation rather than retaining stale graph objects.
- **Toolbar interaction:** Use a top-toolbar search bar and keyboard-accessible dropdown. Place an X clear control inside the input at its right edge, showing it only while a query is present. Up/Down navigates, Enter Locates without Reveal, and Escape closes the dropdown while retaining the query. Clearing removes query/highlights without refolding. Provide readable context, empty/no-match feedback, and access to all matches when limiting rendered work.
- **Graph-neutral Locate:** Highlight and center the visible node or its currently visible containing component while retaining zoom. Do not dispatch ordinary node taps, which may fold or expand. Search highlighting is separate from selection and inspection; do not alter Batch Place Fold selection, replace inspection, commit/discard a draft, or reveal a hidden sidebar. A collapsed compound may already represent its hidden opaque child as a visible tile; matching that component ID Locates the tile rather than offering an unfold that destroys the matched component.
- **Query continuity:** Keep the query and refresh/reconcile results after edits, renames, Reset, playback/expansion changes, and Undo/Redo. Preserve exact result identity where it survives; do not substitute a different same-named occurrence. Successful Open Session clears query/results; rejected Open preserves current search and graph.

### Explicit Reveal

- **Restoration path:** Offer an accessible explicit Reveal control only when the selected hidden occurrence has an actually restorable retained interior. Restore only the containing folds needed to expose that exact occurrence. Opening one fold restores its complete immediate subnet, including neighbors; off-path Folded Components stay folded unless required for the target. After each required owner unfolds, run the same whole-graph Dagre layout as right-click Component-local Unfold, without fitting the camera. Unrelated node positions may change; retain zoom and center the exact revealed result.
- **One action and ordinary state:** Reveal is normal unfolding: update weights/SM, leave the result unfolded after clearing/changing search, and save the resulting graph through existing session capture. All internal restores form one history entry. Undo reverses the entire Reveal; Redo restores its exact graph result and occurrence while keeping the user's current camera.
- **Failure contract:** Revalidate target and current restoration ownership before mutation and after each unfold; success requires a visibly represented target. Stale, missing, or unrestorable targets produce useful feedback without reconstruction from source or historical copies. Any error rolls back graph, attempted navigation/UI changes, and history position. No partial failed Reveal or empty entry remains.

### Viewer Action History

- **Covered gestures:** Individual elementary/structural folds, Batch Place Fold, Fold-Entire-Function, Component-Local Unfold, Reveal, committed component renames, completed node/compound/selected-group moves, Reset, precomputed fold-step changes, and function-call expansion/collapse. Each gesture forms one entry, including valid partial progress before a supported stopping point. Uncommitted typing, unchanged/cancelled drags, search/highlighting, selection/inspection, sidebar visibility, pan/zoom, save, and export do not add entries.
- **Exact restoration:** Restore recorded before/after graph and editing state; do not rerun detection for Redo. Preserve topology, tokens, parents, collapsed state, nested restoration records, metadata associations, names and remembered names, positions, weights/SM inputs, component-ID allocation, and playback/expansion state. Continued editing remains valid without ID collisions. History representation and module factoring are implementation choices.
- **Atomicity and branching:** Use one reusable action boundary. Failed/unchanged actions add no entry and preserve Redo; successful new edits after Undo clear its old branch. Errors during an action or Undo/Redo restore the pre-attempt graph/view and history position. Do not treat silently missing restoration nodes/arcs as success. Failed work must not mutate retained history states.
- **Camera and current UI:** Undo/Redo keeps current zoom/pan, sidebar preference, and query. Reconcile current selection/inspection using surviving node IDs instead of replaying historical highlights or selection. Preserve unfinished text when the same inspected node survives, including when its committed name changes; refresh committed metadata separately. If it disappears, clear inspection and its draft using existing behavior. Do not force a hidden sidebar open.
- **Controls and text editing:** Place Undo/Redo beside search and disable them when unavailable. Support Cmd/Ctrl+Z, Cmd/Ctrl+Shift+Z, and Ctrl+Y where appropriate. Preserve native editing in inputs, textareas, editable content, and active text composition. Explicit toolbar history buttons remain graph operations even after a text field had focus.
- **Session boundaries:** History stays in the current open viewer only. Saving/exporting retains history without adding entries. Save Session writes current graph plus canonical nested local-unfold records without action stacks or a new schema. Successful Open starts empty history; rejected Open preserves it. Undo/Redo restoration must not masquerade as incoming-session Open or clear current query/history as a side effect. Reset/playback/expansion remain undoable within the same document.
- **Retention:** Keep at most 50 gestures across Undo and Redo together, with a soft approximate 32 MiB serialized-history-data budget. Evict oldest entries without breaking the remaining history path; keep the newest action undoable even if it alone exceeds the soft budget. This is not a hard JavaScript heap limit. Use compact detached records without recursive alias duplication, repeated complete document/playback payloads, or duplicated metadata catalogs; release unreachable states after eviction or branch clearing.

## Testing Decisions

- **One primary behavioral seam:** Extend production generated-viewer actions with real bundled Cytoscape and production snapshot continuation. Compare complete observable graph/restoration state before/after an action and after Undo/Redo. Reuse existing generated-viewer, nested-snapshot, inspector, and session acceptance prior art; add no lower-level seam simply to bypass production validation.
- **History coverage:** Exercise individual/batch/function folds and local unfolding, partial progress, names/remembered names after unfold/refold, whole node/compound/group drags, Reset/playback/expansion controls, continued IDs, branch changes, no-ops, injected restoration failures, eviction, oversized newest actions, detached states, surviving drafts/selection, and current-camera preservation. Ticket 68 is complete only when every approved mutation route has correct history coverage.
- **Search and Reveal coverage:** Use a self-contained nested/repeated-call fixture to find visible/hidden places, transitions, and compounds; retain exact ownership paths; deduplicate legacy aliases; handle tile representatives; Locate without mutation; and Reveal one occurrence without changing off-path folds. Verify the right-click Component-local Unfold layout runs after each required owner, while the complete Reveal remains one Undo/Redo action. Include literal special characters, custom/function names, stale/missing records, live refresh, and a failure after intermediate restores. Assert metadata, tokens, names, weights/SM, hierarchy, and positions through public behavior rather than helper names or markup snapshots.
- **Session coverage:** Save contains normal current state without history stacks, stays compact/compatible, reopens with empty history/search, and continues normal folding/local unfolding. Rejected Open preserves graph, query, and history. History restoration retains the active document and must not trigger Open's clearing semantics.
- **Rendered interaction acceptance:** Actual generated HTML in a browser must establish toolbar/dropdown placement, readable context and match access, disabled buttons, Up/Down/Enter/Escape, accessible pointer/keyboard activation of Reveal only for restorable targets, native text shortcuts/composition, pointer drag grouping, focus/draft behavior, independent highlights/selection/inspection, hidden-sidebar access, target centering at unchanged zoom, and preserved camera on Undo/Redo. Mocked DOM/CSS strings do not prove those behaviors. Record unavailable browser coverage as a gap, not a pass. Each vertical slice owns its relevant logic, UI, and acceptance checks.

## Out of Scope

- Project-wide source search, unused definitions, other playback states, unexpanded templates outside the active/restorable graph, source execution, and increasing inline depth to manufacture matches.
- Fuzzy/regular-expression query languages, source-code search, automatic refolding previews, or reconstructing overwritten names and unavailable locations.
- Saved/cross-document Undo/Redo stacks, browser-wide history, a branching-history browser, a new snapshot schema, or removal of ordinary nested local-unfold data.
- Changes to reduction rules, component classification/penalties, Call Site resolution, return evidence, document identity, or source/project metadata semantics.
- Reimplementing Phase 2.8's delivered sidebar/session infrastructure. Only the integration necessary for the approved search/history behavior belongs here.

## Further Notes

- [Phase 2.8](./phase-2.8-viewer-interactive-enhancements.md) remains the delivered baseline and links here without duplicating these requirements. [ADR 0005](../../../docs/adr/0005-session-local-viewer-action-history.md) records complementary session-local history; the [glossary](../../../GLOSSARY.md) defines Folded Component, Viewer Action History, and Component-Local Unfold. Existing boundary/reduction/sidebar decisions continue to apply.
- All 15 design recommendations were approved through grill-with-docs. This extraction changes documentation organization, not approved feature scope. The user requested retaining the original tickets when their work fits the intended model's context budget; the context assessment supports that choice. No application code or tests were changed or executed.
- [Ticket 68](../issues/68-viewer-action-history-undo-redo.md) and [Ticket 69](../issues/69-node-search-and-explicit-reveal.md) remain the implementation plan. Their requirements and blocking edge are unchanged; their specification links now point directly here to avoid loading the historical Phase 2.8 requirements.

### Implementation tickets

The five-slice alternative was evaluated and withdrawn after the context assessment. No child issues were published. Each original ticket still owns its end-to-end UI, production behavior, and acceptance checks.

| Ticket | End-to-end result | Blocked by |
| --- | --- | --- |
| [68 — Viewer Action History](../issues/68-viewer-action-history-undo-redo.md) | Undo/Redo across all approved graph gestures, including controls, exact restoration, rollback, retention, session boundaries, and UI continuity | None |
| [69 — Node Search and Explicit Reveal](../issues/69-node-search-and-explicit-reveal.md) | Current/restorable-node search, graph-neutral Locate, and exact transactional Reveal as one undoable action | 68 |

Implement 68 first, then 69. A fresh implementation chat for each ticket can load this focused specification and the relevant code/test sections without the original Phase 2.8 document or this design conversation. Internal incremental commits remain an implementation choice; neither ticket is complete until its full approved contract is covered.
