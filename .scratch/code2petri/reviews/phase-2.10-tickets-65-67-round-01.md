# Code Review — Tickets 65–67, Round 01

**Review date:** 2026-10-13  
**Comparison base:** `607e97bed84ec5f785e8f9c8683d9e5759b35c98`  
**Diff:** `git diff 607e97bed84ec5f785e8f9c8683d9e5759b35c98...HEAD`  
**Commit reviewed:** `3d54cbb feat: implement follow-up tickets 65-67`  
**Tickets and specs:** [Ticket 65](../issues/65-python-builtin-call-result-metadata.md) and [Phase 2.10](../specs/phase-2.10-function-return-metadata.md); [Ticket 66](../issues/66-function-scoped-structural-folding.md) and [Phase 2.8](../specs/phase-2.8-viewer-interactive-enhancements.md); [Ticket 67](../issues/67-cycle-nested-compound-colors.md) and [Phase 2.7](../specs/phase-2.7-live-fold-reduction.md).  
**Standards:** [AGENTS.md](../../../AGENTS.md), [issue tracker conventions](../../../docs/agents/issue-tracker.md), [triage labels](../../../docs/agents/triage-labels.md), [domain guidance](../../../docs/agents/domain.md), [GLOSSARY.md](../../../GLOSSARY.md), [ADR 0003](../../../docs/adr/0003-adopt-prom-local-reduction-algorithm.md), and Fowler's 12-smell baseline. No dedicated coding-standard or contributing guide was found.  
**Review method:** Independent Standards and Spec reviews. Tests were not run during this review.

---

## Standards

### (a) Documented standards

**Status: PASS — 0 hard violations.** The ticket documents retain their required status and comments sections, use the canonical `ready-for-human` triage state, and do not conflict with the reviewed domain guidance.

### (b) Baseline code smells (judgement calls)

**S1 — Possible duplicated compound-depth presentation logic**

The initial compound element pass and `refreshCompoundDepthPresentation()` each walk parent ancestry and derive `depth-*` and `padding-depth-*` classes in [template.html](../../../code2petri/viewer/template.html#L1132) and [template.html](../../../code2petri/viewer/template.html#L1157).

> **Suggestion:** Consider extracting the ancestry/depth-to-presentation calculation into a shared helper so generated and restored compounds stay consistent. This is an optional maintainability suggestion, not a standards violation.

**S2 — Possible duplicated snapshot evidence validation**

The snapshot element-record path and transition-record path independently check that `function_return_evidence` is an object with string `expression`, `type`, and `provenance` fields in [session_snapshot.js](../../../code2petri/viewer/engine/session_snapshot.js#L187) and [session_snapshot.js](../../../code2petri/viewer/engine/session_snapshot.js#L447).

> **Suggestion:** Consider a shared validator for both record paths to keep malformed-session handling aligned. This is optional maintainability work, not a hard standards issue.

---

## Spec

### (a) Missing or partial requirements / incorrect behavior

**Ticket 66 — Scoped boundary validation rejects contained structural candidates**

[`_validateSESEFunctionBoundaries()`](../../../code2petri/viewer/engine/reduction_engine.js#L2044) rejects a candidate when it consumes only some direct children of a touched compound, unless that compound has already folded into one component. Scoped discovery calls this helper with `consumedForScope` at [reduction_engine.js](../../../code2petri/viewer/engine/reduction_engine.js#L2142). As a result, a valid structural candidate inside the selected function can be rejected when the function has other direct children outside the candidate.

The Phase 2.8 spec requires discovery to be scoped to the selected function and says a larger candidate crossing caller/sibling ownership “cannot eclipse an eligible contained candidate” ([lines 87–89](../specs/phase-2.8-viewer-interactive-enhancements.md#L87)). Ticket 66 also leaves contained-candidate discovery unchecked ([Ticket 66](../issues/66-function-scoped-structural-folding.md#L10)).

> **Suggestion:** Separate the selected function's allowed partial consumption from protected nested-container, caller, and sibling checks. Keep the existing containment protections for nodes the reduction actually consumes.

### (b) Scope creep

None found.

---

**Summary:** Standards: 0 hard violations and 2 optional duplicated-code suggestions. Spec: 1 functional gap in Ticket 66's scoped structural-candidate validation. No other actionable mismatch was identified in Tickets 65 or 67.
