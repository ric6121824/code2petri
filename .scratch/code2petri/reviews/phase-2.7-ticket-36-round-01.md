# Code Review: Ticket 36 (JS Fold Engine: Marked Graph + State Machine) — Round 01

**Commit:** `fbcf3e7` (`feat(viewer): implement live marked graph and state machine reduction engines (ticket 36)`)  
**Diff:** `git diff f6f4bb9...HEAD` (4 files changed, 1,197 insertions(+), 15 deletions(-))  
**Spec:** [`.scratch/code2petri/issues/36-js-fold-engine-marked-graph-state-machine.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/36-js-fold-engine-marked-graph-state-machine.md)  
**Standards:** [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) and Fowler 12-smell baseline  
**Test suite:** All 55 tests in `test_html_viewer.py` and 413 repository tests pass.

---

## Standards

### (a) Documented Standards Violations (Hard Standards)

1. **Domain Vocabulary Drift ([`CONTEXT.md:38-40`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md#L38-L40))**:
   - **Rule**: `Structural Fold` (*Avoid: Graph compression, subnet deletion, macro collapsing*); `SESE Subnet` (*Avoid: Well-structured block, isolated subgraph*).
   - **Violation**: In [`code2petri/viewer/template.html:2333`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L2333):
     `_detectMacroCandidates(isMarkedGraph)` uses prohibited "macro" terminology in private engine methods.
   - **Actionable Fix:** Rename method to `_detectSESESubnetCandidates(isMarkedGraph)` or `_detectStructuralFoldCandidates(isMarkedGraph)`.

2. **Commit Hygiene / Scope Leak**:
   - Commit `fbcf3e7` bundles `.scratch/code2petri/reviews/phase-2.7-ticket-35-round-02.md`, an unrelated review artifact from Ticket 35.
   - **Actionable Fix:** Remove or untrack prior review markdown files from feature commits.

### (b) Baseline Code Smells (Judgement Calls)

1. **Duplicated Code — Reduction Routine** ([`code2petri/viewer/template.html:2478-2780`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L2478-L2780)):
   - `executeMarkedGraphContraction` and `executeStateMachineContraction` duplicate ~110 lines of reduction logic: step number increment, opaque component ID formatting (`c_XX`), parent compound lookup, `consumedNodes`/`consumedInternalEdges` extraction, `_pruneConsumedCompounds`, element removal (`cy.remove`), and opaque node creation.
   - **Actionable Fix:** Extract a shared `_executeSESEReduction(candidate, boundaryHandlingFn)` helper inside `LiveFoldReductionEngine`.

2. **Duplicated Code — Test Topologies** ([`tests/test_html_viewer.py:2268, 2345, 2438, 2530, 2628, 2671`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L2268)):
   - The Marked Graph (6 nodes) and State Machine (9 nodes) JSON literals and runner assertions are copy-pasted verbatim 3 times each across detection, parity, and tap test cases.
   - **Actionable Fix:** Extract shared constants `MARKED_GRAPH_NET_JSON` and `STATE_MACHINE_NET_JSON` in `test_html_viewer.py`.

3. **Repeated Switches / Cascades** ([`code2petri/viewer/template.html:1840-1860, 2830-2860, 2901-2940`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1840-L1860)):
   - Type cascades (`if (foldType === 'marked_graph') ... else if (foldType === 'state_machine') ...`) recur across `getFoldType`, `updateFoldableHighlights`, and `cy.on('tap')`.
   - **Actionable Fix:** Unify fold type metadata (highlight CSS class, detection method, reduction executor) into a single registry object.

4. **Data Clump / Parameter Bloat** ([`code2petri/viewer/template.html:2596-2606`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L2596-L2606)):
   - `_createOpaqueComponentNode` continues to take 9 positional arguments where many values are already packaged inside `consumedSubnet`.
   - **Actionable Fix:** Refactor into an options object.

---

## Spec

### (a) Missing or Partial Requirements

1. **Prioritization Gating Behind Elementary Reductions:**
   - *Spec Line 9 & 11:* `"- [x] Marked Graph subnets are detected and their boundary nodes are visually highlighted to indicate eligibility"`, `"- [x] State Machine subnets are detected and their boundary nodes are visually highlighted"`
   - *Finding:* In `updateFoldableHighlights()` and `getFoldType()`, detection and highlighting are gated behind `!this.hasElementaryReductions()`. If any unreduced sequence, choice, or while pattern exists anywhere in the net, Marked Graph and State Machine subnets are not highlighted and cannot be clicked. While this matches the ProM/Python greedy reduction loop prioritization (Sequence $\to$ Choice $\to$ Loop $\to$ Macro), the spec does not explicitly mandate blocking macro user interaction while local folds exist.
   - **Actionable Fix:** Document this intentional prioritization in the code/spec, or allow boundary nodes to be highlighted and interactive even when elementary reductions are present if concurrent interactivity is desired.

### (b) Scope Creep (Behaviour in Diff Not Asked For)

1. **Automatic Inspector Opening on Reduction:**
   - Left-clicking a boundary node to fold immediately triggers `openInspector(res.node)` alongside Dagre canvas relayout.
   - *Assessment:* Approved standard usability feedback.
2. **Compound Boundary Validation & Pruning:**
   - `_validateSESEFunctionBoundaries` and `_pruneConsumedCompounds` enforce hierarchy scoping. Approved forward-compatible seam for Ticket 38.

### (c) Implementation Nuances / Questionable Areas

1. **Marking Discrepancy on Subnet Detection:**
   - *Spec Line 13:* `"- [x] JS tau and omega values match the Python fold engine for the same topologies"`
   - *Finding:* In Python (`fold.py:728-735`), `_detect_macro` evaluates node degrees and does not inspect markings. In JS (`template.html:2358, 2371`), `_detectMacroCandidates` explicitly rejects candidates if internal places have `initial_tokens > 0`. For workflow nets with initial markings on internal places, JS would reject subnets that Python accepts.
   - **Actionable Fix:** Align marking checks between Python and JS or document why JS enforces token emptiness for SESE candidates.
2. **Reconstitution Storage:**
   - `consumedSubnet` properly retains `consumedNodeIds`, full `nodes`, and `internalEdges` (including boundary-connecting arcs for state machines and external arcs for marked graphs), fulfilling spec line 14.

---

## Summary

- **Standards:** 1 domain vocabulary drift (`_detectMacroCandidates`), 1 commit hygiene issue (bundled prior review), 3 baseline smells (~110 lines duplicated reduction mechanics, duplicated test JSON fixtures, repeated fold type cascades). Worst issue: Duplicated reduction routine across `executeMarkedGraphContraction` and `executeStateMachineContraction`.
- **Spec:** All 6 acceptance criteria functionally implemented and verified against Python `fold.py`. 1 prioritization gating nuance (macros hidden until elementary folds are exhausted), 1 marking check divergence on non-zero initial tokens. Worst issue: Macro eligibility hidden behind `hasElementaryReductions()`.
