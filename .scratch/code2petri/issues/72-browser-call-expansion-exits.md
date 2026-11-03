# 72: Preserve normal and exceptional exits during browser call expansion

**What to build:** Expanding a resolved call in the generated viewer preserves the callee's distinct normal and exceptional outcomes and connects each to the correct caller destination. Users can expand and collapse a call without losing unrelated work, changing execution meaning, or introducing duplicate complexity contributions. Deliver the browser-expansion slice of Phase 2.8.2 — Call Refolding and Exit Preservation; opaque Call Refolding belongs to Ticket 71.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Reproduce the direction-coercion expansion defect using the retained standalone Dots & Boxes reference export. Verify successful return reaches the caller's next statement and uncaught raise reaches its exceptional boundary; neither outcome is disconnected or routed to the other destination.
- [ ] Identify normal and exceptional boundaries independently using semantic roles and validated provenance. Match the accepted backend Inline Expansion contract while testing independently expected reachable markings or execution traces, rather than relying only on implementation parity.
- [ ] Preserve exception routing with and without caller handlers, including nested handlers. Create or reuse an exceptional function boundary where the accepted contract requires it. Do not invent a reachable normal return for an exception-only callee merely because it contains an unused normal-end placeholder.
- [ ] Replace a paired opaque exception alternative only when an explicit callee exceptional outcome replaces it. Retain the existing bounded opaque-call exception behavior when the callee has no explicit exceptional exit. Do not add exception-type inference or unsupported finally-override semantics.
- [ ] Preserve unique identities for nested and repeated call occurrences, call-resolution and return information, source evidence, hierarchy, call-result ownership, and exception-alternative associations. Remap cloned references to their cloned owners.
- [ ] Preserve arc weights and the accepted backend initial-marking policy: cloning the callee does not introduce an extra invocation token. Expansion containers contribute no fictitious operation or duplicate transition weight to the top bar or export.
- [ ] Expansion and collapse operate on the current graph, preserving unrelated live folds, committed names, metadata, positions, and subsequent independent edits. Preserve the current camera and viewing preferences.
- [ ] Missing or ambiguous boundary information produces a specific refusal. Failed and unchanged actions leave graph state, component allocation, Undo/Redo history, and success messaging consistent; no partial splice remains.
- [ ] Undo/Redo, save/open, and PNML export retain correct occurrence identities, outcome alternatives, weights, and restoration data. Exported execution behavior agrees with the visible expanded graph; reopening permits continued editing.
- [ ] Verify through the existing production generated-viewer action and session/export seams, covering normal-only, exception-only, no-explicit-exception, repeated/nested calls, handlers, non-unit weights, metadata ownership, initial markings, and existing edits. Retain valid backend controls.
- [ ] Record an actual regenerated Dots & Boxes browser check of expansion/collapse, both outcome routes, score accounting, save/reopen, and continued editing. Record generator/source identities and distinguish agent-run, user-run, failed, interrupted, and unperformed checks; headless tests alone do not satisfy browser acceptance.

## Context and limits

Follow the canonical Phase 2.8.2 specification and ADR 0006's bounded exception semantics. Ticket 73 independently guards unsafe whole-net fallback and incomplete-result reporting. Ticket 71 depends on both fixes. Do not modify or close Tickets 66 or 70, rewrite the original failing artifacts, or implement opaque Call Refolding in this ticket.

Specification: [Phase 2.8.2 — Call Refolding and Exit Preservation](../specs/phase-2.8.2-call-refolding-and-exit-preservation.md). Design record: [Confirmed question tree](../specs/phase-2.8-ticket-71-question-tree.md).

## Comments

### 2026-11-03 — Approved publication

Published after the user approved the three-ticket breakdown, scopes, and blocking edges. Tickets 72 and 73 can start independently; Ticket 71 is blocked by both. Publication does not claim implementation or browser acceptance.
