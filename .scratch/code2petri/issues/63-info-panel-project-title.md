# 63: Show Project Title in the Info Panel

**What to build:** Users can identify the source project alongside the file and root function in the existing info panel. A Tic Tac Toe view displays Project: Tic Tac Toe, File: main.py, and Function: Global Scope in that order. The title applies across the project's Global Scope and function views and remains correct when the user saves, reopens, and continues working on a session.

**Blocked by:** None (can start immediately).

**Status:** ready-for-human

- [x] The existing CLI and generation API accept an optional explicit Project Title and carry it into the self-contained generated viewer's active document metadata. Preserve human-readable capitalization, spaces, punctuation, and Unicode. Omitted or blank titles are unavailable; do not guess from source/output folders, filenames, run suffixes, or source comments.
- [x] Batch generation supplies each game's original human-readable name to all Global Scope and named-function HTML outputs before filename normalization. Tic Tac Toe and Dots & Boxes retain those titles across dated and fixed-run outputs; moving or renaming the generated HTML does not change project identity.
- [x] Add a Project row above the existing File and Function rows. Use the current light-theme info-panel styling, render supplied titles as text, and handle long titles without overlapping controls. Titles resembling markup must not execute or render as HTML. Preserve the existing source-file label, qualified root-function name, canonical Global Scope label, and return information.
- [x] Selecting an inlined callee, folding/unfolding, or renaming a component leaves the active document's Project Title intact. The project row uses active document identity; it does not replace the root-function label or repurpose the existing graph/header title.
- [x] Save Session captures the optional Project Title in the existing version-1 Fold State Snapshot document context. Open Session restores it offline from the incoming snapshot and updates the info panel. Opening a Tic Tac Toe snapshot inside another game's viewer displays Tic Tac Toe; reset and playback continue to describe that incoming project.
- [x] Missing or blank titles, including older snapshots without the new metadata, display Project: Unavailable. Loading such a snapshot clears the host viewer's previous project identity. The Unavailable label is a display fallback, not a fabricated title persisted as project evidence.
- [x] Validate recognized title metadata as a string through the existing safe-open flow. Malformed additions are rejected before active session replacement, preserving the current graph, document identity, and viewport. Snapshot capture stays detached and project metadata does not multiply across graph nodes or nested restoration records.
- [ ] Verify through the existing source-to-generated-viewer/session workflow with self-contained fixtures: explicit CLI/API input, batch titles, Global Scope and named functions, dated/fixed outputs, absent/blank titles, long names, Unicode, punctuation, markup-like text, cross-project session opening, old sessions, reset/playback, and rejection of malformed metadata. Assert observable identity and panel row order, then save/open and continue existing folding/renaming/local-unfold actions; include browser rendering checks for long-title readability.
- [x] Preserve graph identity/topology, tokens, Call Site resolution, function metadata, fold eligibility/results, component names, Transition Weight, Component Penalty, Structuredness Metric, configuration, and viewport. Provide title input during generation only; a viewer title editor, automatic project discovery, other export formats, and output naming changes are outside this ticket.

## Context

This is a Phase 2.8 follow-up to the resolved Ticket 50, extending its active-document identity presentation. Batch generation already knows each game's human-readable name, but that identity does not reach the info panel. Project Title is a shared source-project label across its file/function views and analysis runs. The existing generation and Save/Open workflows supply the required seams; no prefactoring ticket or outstanding blocker is needed.

Specification: [Phase 2.8 — Viewer Interactive Enhancements](../specs/phase-2.8-viewer-interactive-enhancements.md).

## Comments

### 2026-10-13 — Published

The user approved all Project Title decisions through grill-with-docs and requested this single ticket with to-tickets after incorporating the agreements into Phase 2.8 with to-spec. Ticket 50 remains resolved. The title feature is independent of Ticket 53's folding work and Phase 2.10's return-inference follow-up.

### 2026-10-13 — Implemented

Implementation is complete in commits `3ec9664` and `ef115ab`; human verification remains. The focused Ticket 63 tests pass, including all-games batch fixtures for Tic Tac Toe and Dots & Boxes across dated/fixed outputs. The full unittest suite ran 563 tests; five pre-existing environment/baseline failures remain (missing `pytest`, missing `pygraphviz`, unrelated walker/API mismatches, and the prototype runner's unavailable test port). The browser tool policy blocked opening a local preview, so the long-title browser rendering check and direct post-open interaction sequence were not performed; the active document metadata is only reset during initialization or incoming-session restore.
