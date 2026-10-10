# Code Review — Ticket 53: Called-function fold boundary trigger, Round 02

**Commit reviewed:** `f1c84d6` (`Fix called-function boundary choice folding`)
**Comparison base:** `3c8f019` (the parent of `f1c84d6`, corresponding to Round 01's `HEAD~1`)
**Diff:** `git diff 3c8f019...f1c84d6` (1 file changed, 137 insertions, 49 deletions). No later Ticket 53 implementation or test commit was present for this round.
**Ticket:** [53 — Complete called-function folding at shared boundaries](../issues/53-called-function-fold-boundary-trigger.md)
**Previous Review:** [Ticket 53, Round 01](./phase-2.8-ticket-53-round-01.md)
**Standards:** [AGENTS.md](../../../AGENTS.md), [issue tracker conventions](../../../docs/agents/issue-tracker.md), [triage labels](../../../docs/agents/triage-labels.md), [domain guidance](../../../docs/agents/domain.md), [GLOSSARY.md](../../../GLOSSARY.md), [ADR 0002](../../../docs/adr/0002-boundary-place-unification.md), [ADR 0003](../../../docs/adr/0003-adopt-prom-local-reduction-algorithm.md), and Fowler's 12-smell baseline. No dedicated coding-standard or contributing guide was found.
**Tests:** Not run during this review.

---

## Standards

### (a) Documented Standards

**Status: PASS — 0 hard violations.** The change stays within the viewer engine and does not conflict with the repository's documented domain guidance or relevant reduction decisions.

### (b) Baseline Code Smells (Judgement Calls)

**S1 — Possible duplicated code: split and merge candidate detection**

[`detectChoiceCandidates`](../../code2petri/viewer/engine/reduction_engine.js#L1094) and its merge-direction path at [line 1142](../../code2petri/viewer/engine/reduction_engine.js#L1142) repeat transition validation, parent checks, and bundle grouping.

> **Suggestion:** Consider extracting the common checks into a helper parameterized by graph direction so the split and merge paths stay aligned. This is optional maintainability work, not a standards violation.

---

## Spec

### (a) Missing or Partial Requirements / Incorrect Behavior

**P2 — Mixed-parent Choice validation can accept unrelated containers**

Ticket 53 requires that “the reduction must consume only transitions belonging to the same eligible function container” and retain protection against “siblings, or caller transitions” ([ticket](../issues/53-called-function-fold-boundary-trigger.md)). At [reduction_engine.js:1118](../../code2petri/viewer/engine/reduction_engine.js#L1118), a parent that differs from the first candidate is allowed if it has folded into one component. This condition is not restricted to the eligible function and its retained caller boundary, so a bundle can include transitions from unrelated collapsed sibling or caller containers. The merge-direction guard has the same weakness.

> **Suggestion:** Validate the complete Choice bundle against the eligible function container and its retained shared boundary before mutation. Reject unrelated parents even when each has collapsed to one component. Add a regression where sibling/caller transitions are excluded while the valid boundary case remains eligible.

**P2 — Ticket-required headless regressions are absent**

The ticket asks to “Add regressions at the generated-viewer/headless action seam” for both boundary directions, containment rejection, nested unfolding, session resumption, and viewport preservation ([ticket](../issues/53-called-function-fold-boundary-trigger.md)). The reviewed diff changes only `reduction_engine.js`; it adds no tests for these acceptance cases.

> **Suggestion:** Add focused generated-viewer/headless coverage for the split-exit and merge-entrance shapes, green eligibility, individual place folding, Batch Place Fold, sidebar Fold-Entire-Function behavior, containment rejection, local unfolding, save/open continuation, and viewport preservation.

### (b) Manual Acceptance Checks

The ticket also calls for replaying the original Aeroblasters net and verifying all four affected call occurrences, then confirming newly generated HTML embeds the fix ([ticket](../issues/53-called-function-fold-boundary-trigger.md)). These checks were not evidenced in the review material.

> **Manual steps:** Regenerate the Aeroblasters viewer from the current source, then replay the original net. Check all four reported function-call occurrences for complete folding, preserved caller/sibling boundaries, and working local unfold after save/open. Confirm the regenerated HTML contains the updated behavior. Previously exported HTML keeps its embedded engine and must be regenerated to include the fix.

### (c) Scope Creep

None found.

---

**Summary:** Standards: 0 hard violations and 1 optional low-priority duplication suggestion. Spec: 2 findings; the most serious is the permissive mixed-parent containment guard. Manual Aeroblasters replay and regenerated-viewer acceptance remain unverified.

---

## Implementation Follow-up — 2026-10-10

Investigated the reported missing green highlight for `reset()` when its `Player.reset` child is collapsed. The saved-session graph reproduces the issue: the remaining place in `reset()` has `getFoldType() === null`. The single-place boundary guard rejected the preceding transition because it belongs to `compound_reset`, the same function container as the candidate place, but `reset()` had not itself been folded into one component yet. Recomputing collapsed-compound state did not change the result.

Updated [`reduction_engine.js:863`](../../code2petri/viewer/engine/reduction_engine.js#L863) so the guard requires a neighboring function container to be folded only when that container differs from the candidate place's container. This allows reductions within the active `reset()` container while retaining the folded-container check for transitions across function boundaries.

**Validation:** The failure and cause were reproduced against the attached session data before the change. Tests and post-change browser checks were not run.

## Implementation Result — 2026-10-10

Addressed the mixed-parent bundle finding in `detectChoiceCandidates`. A complete Choice bundle now requires every consumed transition to belong to the trigger place's same function container. Its retained anchors may belong to that function or its direct caller, while unrelated parents are rejected even when collapsed. At global scope, split candidates remain eligible only from their source-place trigger; this preserves the existing plain-net behavior and avoids highlighting the opposite merge endpoint.

Added generated-viewer/headless regressions for split and merge boundary shapes, individual folding, Batch Place Fold, rejection of collapsed sibling/caller transitions, Fold-Entire-Function action completion, preservation of caller tokens and unrelated arcs, and save/open continuation followed by nested local unfolding. The tests also cover the existing single-place boundary fix for an active function beside a collapsed child.

**Validation:** `python3 -m unittest tests.test_html_viewer` passed (150 tests). `python3 -m unittest discover -s tests` ran 547 tests and reported three unrelated errors: `pygraphviz` and `pytest` are missing for two test modules, and `test_walk_result_namedtuple` expects two unpacked values while the current result supplies more. `git diff --check` passed. The read-only attachment snapshot records the Aeroblasters manual acceptance check as passed; that snapshot was not edited.
