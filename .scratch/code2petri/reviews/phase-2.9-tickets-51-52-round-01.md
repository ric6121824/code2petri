# Code Review — Phase 2.9 (Tickets 51–52), Round 01

**Comparison base:** `1fe76c4` (Phase 2.8 round 02 fixes)  
**Reviewed through:** `HEAD`  
**Diff:** `git diff 1fe76c4...HEAD` (3 files changed). Uncommitted worktree changes were excluded.  
**Master Spec:** [Phase 2.9: Session Snapshot Optimization](../specs/phase-2.9-session-snapshot-optimization.md)  
**Tickets:** [51 — Safari Large Session Download](../issues/51-safari-large-session-download.md), [52 — Reliable Save Session Downloads](../issues/52-reliable-save-session-downloads.md)  
**Standards:** [AGENTS.md](../../../AGENTS.md), [domain documentation guidance](../../../docs/agents/domain.md), [GLOSSARY.md](../../../GLOSSARY.md), and Fowler's 12-smell baseline. No dedicated coding-standards or contributing guide was found.  
**Tests:** Not run during this review.

---

## Standards

### (a) Documented Standards

**Status: PASS — 0 hard violations.** The session snapshot and download work follows the documented viewer concepts and introduces no conflict with the repository's documented domain or issue-tracker conventions.

### (b) Baseline Code Smells (Judgement Calls)

**S1 — Possible duplicated test helper: canonical snapshot assertions**

The embedded JavaScript node tests in [test_html_viewer.py](../../../tests/test_html_viewer.py#L6173) and [test_html_viewer.py](../../../tests/test_html_viewer.py#L6273) each define a recursive `assertCanonical` helper.

> **Suggestion:** Consider sharing the helper if more snapshot tests need it. The current duplication is small and keeps each test self-contained, so this is optional and low priority.

---

## Spec

### (a) Missing or Partial Requirements / Incorrect Behavior

**P2 — Performance evidence does not separate the requested stages or snapshot shapes**

The spec asks to measure capture, encoding, and download initiation separately, and to record byte size and elapsed time for fresh, folded, and deeply folded snapshots ([spec](../specs/phase-2.9-session-snapshot-optimization.md#L62)). The added performance coverage measures the complete save operation for a synthetic nested fixture in [test_html_viewer.py](../../../tests/test_html_viewer.py#L6159), but it does not report the stages separately or cover all three snapshot shapes.

> **Suggestion:** Add or record stage-level measurements for fresh, folded, and deeply folded 900-node nets, including output bytes and elapsed time. This can be a follow-up if the existing 900-node manual run already demonstrates acceptable user-perceived performance.

**P2 — Legacy snapshot compatibility tests stop at immediate resave**

The spec's compatibility matrix asks that supported legacy and canonical forms open, remain usable, and resave ([spec](../specs/phase-2.9-session-snapshot-optimization.md#L72)). Current coverage parses supported forms, constructs a graph, and immediately resaves them in [test_html_viewer.py](../../../tests/test_html_viewer.py#L6280). It does not verify that a restored legacy session can be continued before resaving.

> **Suggestion:** Extend one representative test per legacy form to perform a fold or unfold after restoration, then save and verify the resulting canonical snapshot.

### (b) Browser Validation and Acceptance Evidence

**Status: USER-REPORTED PASS — large-net saving works in Safari, Firefox, and Chrome.** The user manually tested session saving in all three browsers and confirmed success for a large net with 900 nodes. Safari was identified as version 18.6 (18621.3.11.19.1, 18621) earlier in this review context; exact Firefox and Chrome versions were not provided.

The spec requests browser/version details and completed-file evidence, including reopening a saved session and continuing folding/unfolding ([spec](../specs/phase-2.9-session-snapshot-optimization.md#L58), [line 66](../specs/phase-2.9-session-snapshot-optimization.md#L66)). The manual pass closes the reported save-reliability concern. For a fully reproducible acceptance record, add the Firefox and Chrome versions, downloaded file sizes, and whether each saved file was reopened and further edited.

### (c) Scope Creep

None found.

---

**Summary:** Standards: 0 hard violations and 1 optional low-priority maintainability suggestion. Spec: browser saving is reported as passing for 900-node nets in Safari, Firefox, and Chrome; 2 evidence/coverage suggestions remain for stage-level performance measurements and continued editing of restored legacy sessions. No blocking finding was identified.

## Implementation Follow-up

- Consolidated the repeated recursive canonical-snapshot assertion into one shared test helper, addressing S1.
- Added a 900-node/904-edge stage profile for fresh, one-fold, and 12-fold snapshots. One local Node run recorded:

  | Shape | Bytes | Capture | JSON encode | Blob create | Download initiation | Total save |
  | --- | ---: | ---: | ---: | ---: | ---: | ---: |
  | Fresh | 391,143 | 4.77 ms | 1.92 ms | 0.86 ms | 0.045 ms | 8.00 ms |
  | Folded | 392,095 | 3.63 ms | 1.93 ms | 0.96 ms | 0.006 ms | 7.15 ms |
  | Deeply folded | 402,987 | 2.96 ms | 2.73 ms | 0.82 ms | 0.006 ms | 7.69 ms |

  Download initiation is timed through the production save function's default helper with a controlled Node DOM/URL boundary; these measurements are not browser timings and have no threshold assertions.
- Extended the legacy-only, both-field, and mixed nested compatibility variants to continue folding after open, then resave with canonical-only restoration records.
- The reported Safari 18.6 / Firefox / Chrome pass remains user-reported evidence. Exact Firefox/Chrome versions, downloaded sizes, and continued editing of those browser-downloaded files were not supplied, so this implementation does not upgrade that report to independently verified browser acceptance.
- Validation after these changes: the focused snapshot and lifecycle classes pass (12 tests). Full unittest discovery ran 500 tests and reported two import errors because the configured system Python lacks `pygraphviz` (`tests.test_graphs`) and `pytest` (`tests.test_interface`); no assertion failures were reported.
