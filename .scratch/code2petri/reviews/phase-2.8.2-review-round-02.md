# Phase 2.8.2 — Implementation Review, Round 02

**Review date:** 2026-11-03  
**Branch:** `codex/phase-2.8.2-call-refolding`  
**Candidate:** `99f798c576e04905b3143c42695e2e7127d690dd`  
**Comparison:** `git diff b83875b90fc2a8082cbe8fe162ac4025e344ecd6...codex/phase-2.8.2-call-refolding`  
**Spec:** [Phase 2.8.2 — Call Refolding and Exit Preservation](../specs/phase-2.8.2-call-refolding-and-exit-preservation.md)  
**Review inputs:** the Phase 2.8.2 round-01 findings supplied by the user and the implementation guidance recorded in Ticket 71.

Commits reviewed:

```text
99f798c docs: record final review and browser artifacts
0d7ecee refactor: share compound descendant collection
c43e73a docs: record Fold Unfold leak repair
683bc84 fix: clean up generated components during refolding
e8a27b8 docs: record outcome-aware scoring direction
d6b9a79 docs: record phase 2.8.2 validation gates
10c7553 Merge call-local unfold review fixes
635e390 test: check restored call score state
df42fef test: isolate stale unfold analysis regression
4f61a3b fix: preserve call-local unfold state
16781d3 Merge branch 'codex/phase-2.8.2-ticket71' into codex/phase-2.8.2-call-refolding
2d6a438 Record Ticket 71 validation and acceptance gaps
a2c0ac7 Implement occurrence-local call refolding
75476f7 Merge Ticket 72 browser outcome expansion
d0e5e1e Fix browser call outcome expansion
1b35a9e Merge branch 'codex/phase-2.8.2-ticket73' into codex/phase-2.8.2-call-refolding
e0207ad fix: preserve exits in incomplete reductions
```

## Standards

No documented-standard violations found in `AGENTS.md`, the domain docs, glossary, or applicable ADRs.

**Possible Duplicated Code — judgment call:** Python inlining and the browser adapter both remap `call_results[].transition_id` and `exception_alternative_of` while cloning occurrences ([inline.py](/private/tmp/code2flow-phase-2.8.2-integration/code2petri/inline.py:187), [template.html](/private/tmp/code2flow-phase-2.8.2-integration/code2petri/viewer/template.html:1190)). They are separate runtime adapters with a shared metadata contract, so this duplication is understandable; parity coverage is important.

## Spec

### Round-01 findings now addressed

- **Browser expansion:** Ticket 72 now resolves normal and exceptional boundaries independently and routes them to their caller destinations.
- **Incomplete reduction score:** Ticket 73 carries completion state and reports final SM as unavailable for incomplete results, with accumulated weight kept separate.
- **Fold/Unfold accumulation:** Ticket 71 cleanup now includes component IDs created by the reduction and their descendants. Production-action regressions cover repeated cycles for backend-inlined and browser-expanded occurrences, prior manual folds, stable contribution, caller routes, and exact local restoration.

### Acceptance and design gates still open

1. **Actual browser acceptance remains unperformed.** The regenerated Dots & Boxes artifacts are recorded, but the branch records that they have not been opened and checked in a browser. The spec requires both expansion paths, outcome routing, score/status, history, save/reopen, continued editing, and exact local unfolding ([spec](../specs/phase-2.8.2-call-refolding-and-exit-preservation.md:123)).
2. **Ticket 73's historical refusal scenario remains unverified in a browser.** The retained standalone session needed to reproduce the invalid final-fold state was unavailable in the integration worktree; the regenerated artifacts do not substitute for that baseline ([spec](../specs/phase-2.8.2-call-refolding-and-exit-preservation.md:119)).
3. **The outcome-aware SM derivation remains unresolved by design.** The tested projection changes the scoring scope, so the implementation correctly keeps final SM unavailable for multi-outcome refolded calls. Ticket 71 remains incomplete until the agreed metric gate is satisfied; no final-score claim should be made ([spec](../specs/phase-2.8.2-call-refolding-and-exit-preservation.md:103)).

No additional scope creep or incorrect implementation was identified in this review. These three items are outstanding acceptance/design gates, not newly found code defects.

## Verification record

The branch records passing focused action-history and expansion checks, including three-cycle regressions, plus `compileall` and `git diff --check`. Those commands were not rerun for this review. No browser interaction was performed by the reviewer; the branch's regenerated HTML files remain pending human acceptance.

## Summary

- **Standards:** 0 hard findings; 1 possible duplication smell (judgment call).
- **Spec:** 0 implementation mismatches among the reviewed fixes; 3 acceptance/design gates remain open. The broadest open item is actual browser acceptance on the regenerated artifacts.
