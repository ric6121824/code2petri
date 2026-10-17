# Code Review — Tickets 65–67, Round 02

**Review date:** 2026-10-13  
**Comparison base:** `607e97bed84ec5f785e8f9c8683d9e5759b35c98`  
**Diff:** `git diff 607e97bed84ec5f785e8f9c8683d9e5759b35c98...HEAD`  
**Commits reviewed:** `3d54cbb` (implementation), `96b6fb5` (Round 01 fixes), `6c37849` (test harness helper)  
**Tickets and specs:** [Ticket 65](../issues/65-python-builtin-call-result-metadata.md) and [Phase 2.10](../specs/phase-2.10-function-return-metadata.md); [Ticket 66](../issues/66-function-scoped-structural-folding.md) and [Phase 2.8](../specs/phase-2.8-viewer-interactive-enhancements.md); [Ticket 67](../issues/67-cycle-nested-compound-colors.md) and [Phase 2.7](../specs/phase-2.7-live-fold-reduction.md).  
**Standards:** [AGENTS.md](../../../AGENTS.md), [issue tracker conventions](../../../docs/agents/issue-tracker.md), [triage labels](../../../docs/agents/triage-labels.md), [domain guidance](../../../docs/agents/domain.md), [GLOSSARY.md](../../../GLOSSARY.md), [ADR 0003](../../../docs/adr/0003-adopt-prom-local-reduction-algorithm.md), and Fowler's 12-smell baseline. No dedicated coding-standard or contributing guide was found.  
**Review method:** Independent Standards and Spec reviews. Tests were not run during this review.

---

## Standards

### (a) Documented standards

**S1 — Ticket 67 implementation history is outside the required Comments section**

The dated implementation entry at [Ticket 67, lines 28–32](../issues/67-cycle-nested-compound-colors.md#L28) appears before the `## Comments` heading. The issue tracker convention says comments and conversation history append under `## Comments` ([issue-tracker.md](../../../docs/agents/issue-tracker.md#L12)).

> **Suggestion:** Move the implementation entry below the `## Comments` heading.

### (b) Baseline code smells (judgement calls)

No well-supported new smell was identified. Both Round 01 duplicated-code suggestions are resolved: generated and refreshed compound-depth presentation use a shared helper, and snapshot record paths use shared evidence validators.

---

## Spec

### (a) Missing or partial requirements / incorrect behavior

**Ticket 65 — Rebinding an imported alias can retain built-in result evidence**

`_python_scope_bindings()` excludes imported names from `local_non_imports`; `local_writes` is then built from that set ([python_walker.py](../../../code2petri/python_walker.py#L882), [line 1115](../../../code2petri/python_walker.py#L1115)). Consequently, a later assignment to a locally imported built-in alias may not invalidate the import mapping:

```python
def f():
    from builtins import len as size
    size = custom
    return size([])
```

That call can still be reported as returning `int`, despite Ticket 65 requiring that “Rebinding ... must not inherit a catalog contract” ([Ticket 65, line 10](../issues/65-python-builtin-call-result-metadata.md#L10)). The same risk applies to rebinding a local alias for the `builtins` module.

> **Suggestion:** Track writes to imported names separately from import bindings, and add regression cases for rebinding both imported function aliases and `builtins` module aliases.

### (b) Scope creep

None found.

### (c) Round 01 finding status

- **Ticket 66 scoped structural candidates:** Resolved. Scoped discovery now permits partial consumption of the selected function while retaining checks against caller, sibling, and protected nested-container consumption. Regression coverage addresses unused function children, caller anchors, unrelated sibling folds, and stale triggers.
- **Ticket 67 color cycling:** No concrete implementation mismatch was identified. Pending rendered-color and session checks are human verification items, not a code finding in this review.

---

**Summary:** Standards: 1 issue-tracker convention breach; no new code-smell findings. Spec: 1 remaining Ticket 65 rebinding defect; the Round 01 Ticket 66 finding is resolved.
