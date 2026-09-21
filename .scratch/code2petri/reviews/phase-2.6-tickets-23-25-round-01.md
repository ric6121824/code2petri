# Tickets 23 (Round 2), 24 & 25: Code Review

**Diff:** `b4d919f...HEAD`  
**Commits:** `445c45a` (ticket 24), `81c67f6` (ticket 25), `f7fadee` (ticket 23 round 2 refactor)  
**Specs:** 
- [`.scratch/code2petri/reviews/phase-2.6-ticket-23-round-02.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/reviews/phase-2.6-ticket-23-round-02.md)
- [`.scratch/code2petri/issues/24-prom-port-loops-sese.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/24-prom-port-loops-sese.md)
- [`.scratch/code2petri/issues/25-interactive-compound-node-expansion.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/25-interactive-compound-node-expansion.md)
- [`.scratch/code2petri/specs/phase-2.6-interactive-expansion.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/specs/phase-2.6-interactive-expansion.md)

---

## Standards
**STATUS: PASS (0 Hard Violations, 3 Baseline Smells)**

### (a) Verification of Ticket 23 Round 2 Standards Findings
1. **Duplication of symmetry difference calculation across macro detectors:** **RESOLVED**
   - In [`code2petri/fold.py:261-281`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/fold.py#L261-L281), `calculate_symmetry_multiplier` was parameterized with `use_subnet_degrees: bool = True` in commit `f7fadee`. It is now consistently reused across `detect_marked_graphs` (L712), `detect_state_machines` (L781), `detect_well_structured` (L859, L862), and `_calculate_unstructured_omega` (L904, L905).
2. **Redundant delegation in `fold_loop` (calling `fold_while`):** **RESOLVED**
   - In [`code2petri/fold.py:599-606`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/fold.py#L599-L606), `fold_loop` directly invokes `_fold_first_candidate(net, detect_loops(net, cfg), step_number)`. The redundant nested delegation to `fold_while` was eliminated; reduction precedence is cleanly managed in `fold_net()`.

### (b) Documented Standards Violations
* **None (0 hard violations).** A comprehensive audit against [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) confirmed that all prohibited terms (*zoom-in block*, *sub-graph replacement*, *sequence collapsing*, *chain reduction*, *well-structured block*, *isolated subgraph*, *graph compression*, *subnet deletion*, *macro collapsing*, *black box*, *leaf transition*, *merged graph*, *global net*) are absent across production code, test suites, ADR 0003, and viewer templates.

### (c) Baseline Code Smells (Judgement Calls)
1. **Duplicated Code** ([`code2petri/viewer/template.html:448-522`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L448-L522)):
   - **Hunk:**
     ```javascript
     (calleeNet.places || []).forEach(function(p) {
       const tokens = p.initial_tokens || 0;
       const label = (p.label || p.id) + (tokens > 0 ? ' (' + tokens + ')' : '');
       elements.push({ group: 'nodes', data: { id: prefix + p.id, parent: parentId, label: label, ... } });
     });
     ```
   - **Analysis:** In `applyExpansion()`, node object formatting for inlined places and transitions duplicates `netToElements()` (L316–389). Extracting a shared node-creation helper would prevent visual schema drift.
   - **Actionable Fix:** Extract a shared `createNodeElement(nodeData, prefix, parentId)` helper function in the JavaScript template to format places and transitions, and call it from both `applyExpansion()` and `netToElements()`.
2. **Duplicated Code** ([`code2petri/fold.py:683-728, 752-796`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/fold.py#L683-L728)):
   - **Analysis:** `detect_marked_graphs` and `detect_state_machines` follow identical structural logic (SESE candidate pair iteration, sorting, symmetry multiplier calculation, and component creation), differing only in swapping place/transition degree checks.
   - **Actionable Fix:** Extract a unified `_detect_macro(net, is_marked_graph=True)` helper or class to share the SESE iteration, sorting, and symmetry calculation, passing the specific degree checks as a lambda/flag.
3. **Duplicated Code** ([`code2petri/fold.py:609-633`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/fold.py#L609-L633)):
   - **Analysis:** `forward_reachability` and `backward_reachability` replicate BFS traversal logic, differing only by traversing `topo.postsets` versus `topo.presets`.
   - **Actionable Fix:** Extract a generalized `_reachability(start_node, neighbor_map)` BFS helper function, passing `topo.postsets` for forward and `topo.presets` for backward reachability.

---

## Spec
**STATUS: PASS (All Core Requirements Met, 2 Minor Partial/Edge-Case Findings, 2 Scope Notes, 1 Validated Design Difference)**

### (a) Status of Ticket 23 Round 2 Issues
1. **Infinite loop on single-place self-loops:** **RESOLVED**
   - In [`code2petri/fold.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/fold.py), `fold_net` terminates when `len(current_net.transitions) <= 1` or `len(current_net.places) <= 1`. [`test_unstructured_fold_on_single_place_net`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_fold_reduction.py#L251) passes in a single reduction step without hanging.
2. **Assertion mismatch (`156.0 != 7.0`):** **RESOLVED**
   - `_calculate_unstructured_omega` implements the formal Lassen/ProM Def. 22 formula: $5 \times (|F - (P+T)| + 1) \times \text{diffP} \times \text{diffT}$, producing $\omega = 156.0$. [`test_known_irreducible_net_terminates_with_unstructured_penalty`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_fold_reduction.py#L218) in `tests/test_fold_reduction.py` was updated to assert `156.0`.

### (b) Requirements Missing or Partial
1. **Fold Slider View Retention on Folded Callers (Minor Edge Case):**
   - *Spec Quote (Phase 2.6 line 23 / Ticket 25 line 13):* `"As an analyst, I want the fold slider to continue governing the outer graph even when a callee is expanded"` / `"- [x] Javascript: Ensure the fold slider ignores the expanded raw contents"`
   - *Finding:* The viewer renders pre-computed step snapshots. If the user advances the fold slider to a step where the caller transition itself is collapsed into an opaque transition ($t_{Cn}$), the compound node disappears because its parent ID is absent from that step snapshot. (When scrubbing through earlier steps where the caller exists, the expansion persists correctly).
   - **Suggestion:** Programmatically close/collapse the expansion view in the UI or show a "Folded away" visual indicator if the parent transition vanishes in the current slider snapshot.
2. **Pre-computation without `--context` (Minor CLI Limitation):**
   - *Spec Quote (Ticket 25 line 9):* `"- [x] Python CLI: Pre-compute and embed all resolved callee nets ... into a window.CALLEE_NETS_JSON dictionary in the HTML template."`
   - *Finding:* In [`code2petri/engine.py:244`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/engine.py#L244), `callee_nets` are precomputed only `if ext == "html" and symbol_table is not None`. Invoking the CLI without `--context` leaves `window.CALLEE_NETS_JSON` empty even for internal same-file calls.
   - **Actionable Fix:** Update `engine.py` to instantiate a single-file local `SymbolTable` on the fly when `--context` is omitted, so that same-file callees are successfully populated into `window.CALLEE_NETS_JSON`.

### (c) Behaviour in Diff Not Asked For (Scope Creep)
1. **Symmetry Multiplier Refactoring (Ticket 23 Smell):**
   - Commit `f7fadee` refactored `calculate_symmetry_multiplier(..., use_subnet_degrees=False)` to eliminate baseline smell duplication across macro detectors. This resolved a previous review smell rather than fulfilling Ticket 24/25.
   - **Suggestion:** Retain this refactor. It strictly improves code maintainability and directly addressed a smell identified in a previous review round.
2. **Extra Callee Net Lookup Keys:**
   - *Spec Quote (Phase 2.6 line 36):* `"flat dictionary keyed by the callee's fully qualified name"`
   - `precompute_callee_nets` in [`code2petri/inline.py:367-370`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/inline.py#L367-L370) also registers `sym.bare_name` and `cs.callee_name` aliases. This improves client-side hit rates but was unrequested.
   - **Suggestion:** Retain the extra aliases as they improve UX robustness and hit-rates on the client side with minimal cost.

### (d) Requirements Implemented with Intentional Architectural Differences
1. **Boundary Place Rewiring vs. Unification (ADR-0002):**
   - *Spec Quote (Ticket 25 line 12 / Phase 2.6 line 42):* `"- [x] Javascript: Dynamically rewire the callee's entrance/exit places to the caller's input/output arcs"`
   - *Finding:* Directly wiring caller preset places to callee entrance places would create illegal Place $\to$ Place arcs in Petri nets. The implementation intentionally unifies/drops boundary places (per ADR-0002), connecting preset places to callee entrance transitions directly, preserving strict bipartite graph validity.
   - **Suggestion:** Accept the implementation. The current behaviour accurately reflects structural correctness for Petri nets (preventing bipartite violations). This design drift should simply be recorded in the issue/spec as an approved deviation.

---

## Summary
- **Standards Axis:** 3 findings (0 hard violations, 3 baseline smells: worst is duplicated node formatting between `applyExpansion()` and `netToElements()` in `template.html`).
- **Spec Axis:** 3 findings (0 missing core requirements; 2 minor edge-case partials: worst is missing pre-computation when `--context` is omitted; 1 justified architectural variance: ADR-0002 boundary unification).
