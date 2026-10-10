# Code Review — Ticket 53: Called-function fold boundary trigger, Round 01

**Commit:** `f1c84d6` (`Fix called-function boundary choice folding`)
**Comparison base:** `HEAD~1`
**Diff:** `git diff HEAD~1...HEAD` (1 file changed, 186 insertions(+), 49 deletions(-))
**Spec:** [Ticket 53](../issues/53-called-function-fold-boundary-trigger.md)
**Standards:** [issue tracker conventions](../../../docs/agents/issue-tracker.md), [triage labels](../../../docs/agents/triage-labels.md), [domain guidance](../../../docs/agents/domain.md), and Fowler baseline smells
**Tests:** `pytest tests/test_live_fold_prototype.py -q` could not run in this environment (`pytest` not installed), so this review is static-only.

---

## Standards

### (a) Documented standards

**Status: PASS — 0 hard violations.**

The implementation stays within the repo’s architectural pattern for the viewer engine and does not obviously violate the project’s documented issue-tracker/domain conventions. The change is narrowly scoped to [code2petri/viewer/engine/reduction_engine.js](../../code2petri/viewer/engine/reduction_engine.js) and preserves the existing reduction logic without broadening the scope beyond the fold-boundary fix.

### (b) Baseline code smells (judgement calls)

**None spotted.**

The updated guard logic is compact and local; I do not see an obvious Fowler smell in the new lines that would require a structural refactor for this ticket.

---

## Spec

### (a) Missing or partial requirements / incorrect behavior

**Status: FAIL — 2 findings.**

1. **Required regression coverage is missing.**
   - The ticket explicitly requires regression coverage at the generated-viewer/headless seam for green highlights, individual place folding, Batch Place Fold, and the sidebar function action, with both boundary directions, containment rejection, nested unfolding, session resumption, and viewport preservation: [Ticket 53](../issues/53-called-function-fold-boundary-trigger.md).
   - The current diff modifies only [code2petri/viewer/engine/reduction_engine.js](../../code2petri/viewer/engine/reduction_engine.js) and does not add the required validation tests. The acceptance criteria remain unproven by the patch itself.
   - **Suggestion:** Add a focused headless regression in [tests/test_html_viewer.py](../../tests/test_html_viewer.py) covering:
     - split-exit case and merge-entrance case,
     - green highlight eligibility,
     - individual place folding,
     - batch place fold,
     - nested containment rejection,
     - local unfold and session restore behavior.

2. **The parent-containment guard is still too permissive for unrelated function containers.**
   - The logic in [code2petri/viewer/engine/reduction_engine.js](../../code2petri/viewer/engine/reduction_engine.js) treats different parent IDs as valid when they are each “folded into a single component,” via `isFunctionFoldedIntoSingleComponent()`. This is exactly the kind of boundary check the ticket explicitly warns against: “retain existing protection against combining unresolved nested functions, siblings, or caller transitions.”
   - The ticket’s spec calls out that a retained caller boundary can anchor a function-owned Choice without being consumed, but it still requires containment safety. Allowing multi-parent selection to pass merely because each parent is internally single-component can still merge unrelated caller/sibling branches.
   - **Suggestion:** Tighten the guard so it only accepts a mixed-parent bundle when all involved parents are the same function container or the same retained caller boundary; otherwise reject the bundle. In other words, keep the `isFunctionFoldedIntoSingleComponent()` shortcut only for the exact eligible function-container case, not as a general cross-container bypass.

### (b) Scope creep

**None found.** The change is narrowly scoped to the choice-boundary eligibility fix and does not add unrelated behavior beyond the reduction engine improvement.

---

## Summary

- **Standards:** 0 findings; no hard violations.
- **Spec:** 2 findings; worst issues are: missing regression coverage and an over-permissive boundary guard.
- **Recommended next step:** add the missing headless regressions and tighten the mixed-parent containment check before considering the ticket complete.
