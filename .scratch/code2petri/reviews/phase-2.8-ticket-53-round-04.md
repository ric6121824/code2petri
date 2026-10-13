# Code Review — Ticket 53: Called-function fold boundary trigger, Round 04

**Review date:** 2026-10-13  
**Comparison base:** `3bd8a93a16a656129e97a5a0b5160df45ca9067b`  
**Diff:** `git diff 3bd8a93a16a656129e97a5a0b5160df45ca9067b...HEAD`, plus staged, unstaged, and untracked changes  
**Commits reviewed:** `7742051`, `05d96f8`, `3c0ea39`, `8a0bfaa`  
**Spec:** [Ticket 53](../issues/53-called-function-fold-boundary-trigger.md), [Round 03 acceptance report](./phase-2.8-ticket-53-round-03.md)  
**Related scope:** [Ticket 62](../issues/62-python-list-return-inference.md), [Phase 2.10 spec](../specs/phase-2.10-function-return-metadata.md)  
**Standards:** [AGENTS.md](../../../AGENTS.md), [domain guidance](../../../docs/agents/domain.md), [issue tracker conventions](../../../docs/agents/issue-tracker.md), [triage labels](../../../docs/agents/triage-labels.md), [GLOSSARY.md](../../../GLOSSARY.md), [ADR 0002](../../../docs/adr/0002-boundary-place-unification.md), [ADR 0003](../../../docs/adr/0003-adopt-prom-local-reduction-algorithm.md), and Fowler's 12-smell baseline. No dedicated coding-standard or contributing guide was found.
**Review method:** Independent Standards and Spec reviews. The reviewers made no changes.

---

## Standards

### (a) Documented standards

**Status: PASS — 0 hard violations.** No conflict with the reviewed repository guidance or domain decisions was found.

### (b) Baseline code smells (judgement calls)

**S1 — Possible duplicated component ID allocation**

[`_allocateComponentId()`](../../code2petri/viewer/engine/reduction_engine.js#L635) increments the step counter and formats `c_XX` IDs, while other reduction methods repeat the counter-and-format pattern.

> **Suggestion:** Route component creation through a shared allocator so ID generation and collision handling stay consistent. This is optional maintainability work, not a standards violation.

---

## Spec

### (a) Missing or partial requirements / incorrect behavior

**No implementation defect was identified.** The delegated Spec review found the ordinary-singleton completion, boundary eligibility, local-unfold restoration, and regression coverage addressed. It reported 11 focused workflow and folding tests passing.

**Manual acceptance remains unverified — supplied session and original HTML**

Ticket 53 requires that “Existing saves, including the supplied version-1 attachment, load without requiring new fields.” The Round 03 report also records: “The original exported HTML was not opened or regenerated.” The added tests use reconstructed nets and synthetic snapshots, so they do not demonstrate the supplied-session workflow or the original HTML.

> **Suggestion:** Open the supplied version-1 session in the viewer, fold and unfold the singleton function and a surrounding boundary Sequence, save/reopen, and continue folding. Regenerate and inspect the original HTML separately if that artifact is part of the acceptance target. Record the browser/manual result in the ticket.

### (b) Scope creep

**Project Title glossary entry is unrelated to Ticket 53 and Ticket 62.** The changed [GLOSSARY.md](../../../GLOSSARY.md#L15) adds “Project Title,” while Ticket 62 scopes its work to list-return inference and its metadata lifecycle. The entry is not required by either ticket.

> **Suggestion:** Remove the entry from this change or track and justify it in a separate domain-documentation change.

---

**Summary:** Standards: 0 hard violations and 1 optional smell suggestion. Spec: 2 findings; the supplied-session/manual acceptance remains unverified, and the unrelated glossary addition should be removed or separately justified. No implementation defect was found.
