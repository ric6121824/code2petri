# Code Review: Ticket 35 (JS Fold Engine: SESE Infrastructure) — Round 01

**Commit:** `37202db` (`feat(viewer): implement live sese infrastructure and reachability engine (ticket 35)`)  
**Diff:** `git diff ed83412...HEAD` (4 files changed, 621 insertions(+), 5 deletions(-))  
**Spec:** [`.scratch/code2petri/issues/35-js-fold-engine-sese-infrastructure.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/35-js-fold-engine-sese-infrastructure.md)  
**Standards:** [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) and Fowler 12-smell baseline  
**Test suite:** All 49 tests in `test_html_viewer.py` and 407 repository tests pass.

---

## Standards

### (a) Documented Standards Violations (Hard Standards)

1. **Domain Vocabulary Drift ([`CONTEXT.md:27-29`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md#L27-L29))**:
   - **Rule**: `Composite Net` (*Avoid: Merged graph, global net*).
   - **Violation**: In [`tests/test_html_viewer.py:2210`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L2210) and [`.scratch/code2petri/issues/35-js-fold-engine-sese-infrastructure.md:12`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/35-js-fold-engine-sese-infrastructure.md#L12):
     ```python
     def test_sese_performance_large_composite_graph_headless(self):
         """Validates that SESE detection runs efficiently (<50ms) on a composite graph with 200+ nodes."""
     ```
   - **Actionable Fix:** Rename method to `test_sese_performance_large_composite_net_headless` and replace `"composite graph"` with the canonical domain term **`Composite Net`**.

2. **Commit Hygiene / Scope Leak**:
   - Commit `37202db` bundles `.scratch/code2petri/reviews/phase-2.7-ticket-34-round-01.md`, an unrelated review artifact for Ticket 34.
   - **Actionable Fix:** Avoid staging prior ticket review reports into subsequent feature commits.

### (b) Baseline Code Smells (Judgement Calls)

1. **Middle Man Delegation on Engine Prototype** ([`code2petri/viewer/template.html:1393-1419`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1393-L1419)):
   - `LiveFoldReductionEngine.prototype` defines 7 one-line pass-through methods (`forwardReachability`, `backwardReachability`, `isReachable`, `findSESENodes`, `calculateSymmetryMultiplier`, `calculateSubnetSymmetry`, `findAllSESECandidates`) that delegate directly to `this.sese.*` without augmenting behavior.
   - **Actionable Fix:** Remove the 7 forwarding methods and have callers access `engine.sese.*` directly, keeping `SESEInfrastructure` as an independent, cohesive module.

2. **Duplicated Code — BFS Traversal** ([`code2petri/viewer/template.html:1232-1249`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1232-L1249)):
   - `isReachable(sourceId, sinkId)` reimplements a full BFS traversal over `outgoers('edge')`, duplicating the graph walk from `_reachability(startId, boundaryId, forward)`.
   - **Actionable Fix:** Implement `isReachable(sourceId, sinkId)` as a simple call to `_reachability`: `return this._reachability(sourceId, null, true).has(sinkId)`.

3. **Duplicated Code — Test Net Topologies** ([`tests/test_html_viewer.py:2020-2101`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L2020-L2101)):
   - Inline JSON net structures for leak-in and leak-out topologies share identical node/arc scaffolding copy-pasted across tests.
   - **Actionable Fix:** Extract common fixture generators for synthetic SESE test topologies.

---

## Spec

### (a) Missing or Partial Requirements
**None.** All 4 acceptance criteria are implemented and pass headless automated tests:
1. Bidirectional reachability ($\text{forward}(u, v) == \text{backward}(v, u)$) correctly returns SESE candidate node sets.
2. Invariant validation excludes subnets with external leaks into/out of internal nodes.
3. Symmetry multiplier calculation matches Python `calculate_symmetry_multiplier` ($\text{diffP}$, $\text{diffT}$).
4. Performance on a 200+ node composite net executes well under budget (< 2ms vs 50ms target).

### (b) Scope Creep (Behaviour in Diff Not Asked For)

1. **All-Pairs SESE Candidate Search Generator:**
   - In [`code2petri/viewer/template.html:1367-1399`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1367-L1399), `findAllSESECandidates(boundaryIds = null, minTransitions = 2)` performs an exhaustive $O(N^2)$ candidate generation across all canvas places.
   - *Assessment:* Approved forward-compatible seam for Tickets 36–38 (Marked Graph, State Machine, Well-Structured SESE reduction).

### (c) Implementation Nuances / Questionable Areas

1. **Vacuous Test for External Leak-In Boundary Invariant:**
   - *Spec Line 10:* `"- [x] The module correctly excludes boundary nodes that violate the SESE invariant"`
   - *Finding:* In `test_sese_boundary_invariant_exclusion_headless` ([`tests/test_html_viewer.py:2025-2039`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L2025-L2039)), `net_leak_in` leaves `p1` completely disconnected from `p_src -> t1/t2 -> p_snk`. Consequently, `findSESENodes('p_src', 'p_snk')` returns a non-null valid set (`{p_src, t1, t2, p_snk}`). The assertion `self.assertIn("FAIL_LEAK_IN", proc.stdout)` passes vacuously only because the test script checks `if (res !== null && res.has('p1'))`. The actual leak-in invariant (where an external arc enters an *internal* transition `t1`) is not exercised by this graph.
   - **Actionable Fix:** Wire an arc from `p1` to an internal node (`t1`), so that `findSESENodes('p_src', 'p_snk')` returns `null` because of an illegal entry arc, asserting `self.assertIn("LEAK_IN_REJECTED", proc.stdout)`.

2. **Inverted Default Parameter for `useSubnetDegrees`:**
   - *Spec Line 11:* `"- [x] The symmetry multiplier calculation (diffP, diffT) produces values matching the Python fold engine for the same subnet"`
   - *Finding:* In Python ([`code2petri/fold.py:263`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/fold.py#L263)), `calculate_symmetry_multiplier` defaults to `use_subnet_degrees: bool = True`. In JS ([`template.html:1316`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1316)), `useSubnetDegrees = false` defaults to `false`.
   - **Actionable Fix:** Change the JS default to `useSubnetDegrees = true` to strictly match the Python method signature default, or document the rationale if `false` was intentional for ProM compatibility.

---

## Summary

- **Standards:** 1 hard vocabulary violation (`composite graph` instead of `Composite Net` in test name and docstring), 1 commit hygiene issue (bundled Ticket 34 review), 3 baseline smells (7-method Middle Man delegation, duplicated BFS in `isReachable`, duplicated test JSON fixtures). Worst issue: Middle Man delegation on `LiveFoldReductionEngine.prototype`.
- **Spec:** 0 missing requirements, all 4 acceptance criteria satisfied. 1 vacuous test case in leak-in boundary invariant validation, 1 inverted default parameter in symmetry multiplier calculation. Worst issue: Vacuous leak-in test in `test_html_viewer.py`.
