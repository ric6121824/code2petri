# Session-local Viewer Action History alongside Component-Local Unfold

Date: 2026-10-17

Status: accepted

The viewer's consumed-subnet records support Component-Local Unfold of a chosen folded component, but do not provide chronological Undo/Redo of a whole gesture, a rename, or a node move. Add complementary Viewer Action History within the current open document, recording one committed user gesture as one entry and restoring its exact before/after graph and editing state; retain current camera, search, and sidebar preferences rather than rewinding subsequent navigation.

Search Reveal uses the same action boundary so all containing unfolds are undone together and failures leave neither a partially revealed graph nor an advanced history cursor. Component-Local Unfold remains available and is itself an undoable action; precomputed playback remains a separate graph-changing feature whose controls/state must also restore correctly.

Keep Undo/Redo stacks out of saved Fold State Snapshots. Persist the ordinary graph and nested local-unfold records as before, and start empty action history only after a successful Open Session. This trades cross-reopen chronological history for bounded session size and compatibility with compact restoration records. The in-memory policy is at most 50 gestures across Undo/Redo and a soft approximate 32 MiB serialized-data budget, evicting oldest entries while retaining the newest action even when it alone exceeds that budget.

This amends Phase 2.7's original exclusion of global state-array undo without prescribing snapshots versus deltas or replacing consumed-subnet restoration. The agreed [Phase 2.8.1 specification](../../.scratch/code2petri/specs/phase-2.8.1-viewer-search-and-action-history.md) owns the action, interface, and acceptance contracts after extraction from Phase 2.8. Original [Tickets 68](../../.scratch/code2petri/issues/68-viewer-action-history-undo-redo.md) and [69](../../.scratch/code2petri/issues/69-node-search-and-explicit-reveal.md) remain the two implementation tickets, with 69 depending on 68 and no further child-ticket split. The architectural decision itself is unchanged.
