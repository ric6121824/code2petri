# 73: Preserve exit boundaries and report incomplete reduction honestly

**What to build:** Python analysis and the generated viewer refuse whole-net Unstructured fallback when it would erase an exit or violate the applicable component assumptions. Users retain the graph and safe local reduction actions. When analysis cannot safely complete, export still produces the preserved diagram, with final SM explicitly unavailable and Accumulated Reduction Weight shown separately. Deliver this independently verifiable safety-and-reporting slice of Phase 2.8.2 — Call Refolding and Exit Preservation.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Reconstruct the state immediately before the invalid final fold in the retained standalone Dots & Boxes session. Refuse the fallback that selects the normal sink and consumes the exceptional exit: both exits survive, and running weight 22 is not transformed into the invalid apparent final score 2200.
- [ ] Validate distinct justified source and sink boundaries, applicable single-entry/single-exit structure, complete source-to-sink coverage, consumed-place markings, incident/crossing interfaces, and relevant arc weights. Multiple exits, disconnected remainders, missing exits, identical source/sink, or unsupported interfaces cannot be repaired by choosing an arbitrary boundary.
- [ ] Reject unsafe candidates during discovery and independently revalidate immediately before execution, including stale or directly supplied candidates in Python and browser entry points. Validate before changing graph state, allocating component IDs, advancing counters, or committing history.
- [ ] Refusal preserves nodes, arcs, tokens, weights, names, metadata, accumulated weight, component allocation, history, and camera. Provide a specific explanation; do not leave partial replacement or misleading success state.
- [ ] Preserve weights and markings under the applicable validated reduction rules. Explicitly refuse unsupported weighted rewiring or internal-token consumption rather than silently creating unit arcs or dropping tokens. Preserve valid local reductions inside a larger unsupported graph.
- [ ] Retain supported single-exit workflow reductions, including legitimate Unstructured components and their established penalties. Update legacy tests that forced numeric results for invalid non-WF inputs; preserve dead ends and infinite loops as faithful diagrams rather than forcing termination.
- [ ] Represent three distinct Reduction Outcomes: completed through structured components, completed using Unstructured components, and incomplete analysis with its remaining graph preserved. Preserve the historical meaning of the structural-reducibility indicator; it must not stand in for completion. A single remaining transition or stored number alone does not prove a valid final SM.
- [ ] For incomplete analysis, continue exporting the preserved diagram and display “Final SM unavailable—reduction incomplete” with its reason. Report Accumulated Reduction Weight separately. Never present the first remaining transition, zero, or the running total as a verified final SM. Keep legitimate completed scores and actual input/output-error behavior correct.
- [ ] Carry outcome, reason, and final-score availability consistently through public analysis results, CLI messages, JSON, supported graph exports, generated HTML presentation, inspector/playback, and saved document state. Export the intended preserved result rather than an unrelated earlier playback state.
- [ ] Keep supported legacy sessions openable without guessed topology repairs. Missing completion evidence is unknown, not proof of final SM. Validate recognized new metadata and reject malformed incoming state transactionally, preserving the active document.
- [ ] Verify through public Python API/CLI/export behavior and existing production viewer action, parity, history, and session/export seams. Cover multiple sources/sinks, missing or identical boundaries, disconnected nodes, marked interiors, crossing interfaces, unsupported weights, stale/direct candidates, valid local folds, and all three Reduction Outcomes with independent topology and score-availability assertions.
- [ ] Record an actual regenerated Dots & Boxes browser check of refusal, preserved exits, explanatory status, accumulated weight, save/reopen, and continued valid editing. Record artifact and source identities and distinguish performed checks from unperformed browser acceptance.

## Context and limits

Follow the canonical Phase 2.8.2 specification and ADR 0007, which amends ADR 0003's fallback applicability. This ticket is independent of Ticket 72 and does not wait for Ticket 71's scoring construction. It does not implement multi-exit Call Refolding, approve a common-sink projection, repair already-damaged historical topology, or change parent-ticket status.

Specification: [Phase 2.8.2 — Call Refolding and Exit Preservation](../specs/phase-2.8.2-call-refolding-and-exit-preservation.md). Design record: [Confirmed question tree](../specs/phase-2.8-ticket-71-question-tree.md).

## Comments

### 2026-11-03 — Approved publication

Published after the user approved the three-ticket breakdown, scopes, and blocking edges. Tickets 72 and 73 can start independently; Ticket 71 is blocked by both. Publication does not claim implementation or browser acceptance.
