# 24 — ProM Algorithm Port II: Loops & SESE Macro-Components

**What to build:** The reduction engine mathematically aligns with ProM by correctly folding loops (`foldWhile`), detecting macro-components via bidirectional reachability (SESE), and gracefully handling knots via a minimal-SESE unstructured fallback.

**Blocked by:** 23 — ProM Algorithm Port I: Local Sequence & Choice

**Status:** resolved

- [x] Implement `foldWhile` to collapse transitions that self-loop on a single 2-in/2-out place.
- [x] Implement SESE bound detection using bidirectional reachability ($forward == backward$).
- [x] Implement `foldMarkedGraph`, `foldStateMachine`, and `foldWellStructured` to detect and fold the *maximal* SESE subnet satisfying their respective properties.
- [x] Implement `foldUnstructured` as the fallback, isolating and folding the *minimal* SESE knot.
- [x] Add tests verifying these topologies reduce correctly.

## Answer

Ticket 24 has mathematically aligned `code2petri/fold.py` with ProM's `PetriNetStructurednessMetric.java`:
1. **Local While Loop Reduction (`fold_while`):**
   - Detects 2-in/2-out places sharing a self-loop transition ($t_{loop}$ where $|*t_{loop}|=1, |t_{loop}*|=1$).
   - Calculates $\omega = (\text{cfg.loop} / 3.0) \times \tau(t_{loop})$, producing the exact ProM formula $\tau_{new} = \tau(t_{src}) + \tau(t_{snk}) + 2.0 \times \tau(t_{loop})$.
   - Multi-node loop bodies contract intra-loop places via `fold_sequence` first, collapsing cyclic paths into canonical self-loop transitions for `fold_while`.
2. **SESE Bidirectional Reachability Invariant (`find_sese_nodes`):**
   - Implemented `forward_reachability` and `backward_reachability` BFS traversals.
   - SESE subnets are bounded by node pairs where $\text{forward}(u, v) == \text{backward}(v, u)$ and $|T| > 1$.
3. **Maximal SESE Macro-Components:**
   - `fold_marked_graph`: Detects maximal transition-bounded SESE subnets where internal places have in/out degree 1.
   - `fold_state_machine`: Detects maximal place-bounded SESE subnets where internal transitions have in/out degree 1.
   - `fold_well_structured`: Detects maximal place-bounded SESE subnets free from PT/TP handles and internal cycles.
4. **Minimal SESE Knot Fallback (`fold_unstructured`):**
   - Discovers minimal internal SESE subnets to isolate irreducible knots (User Story 3).
   - Folds the knot using ProM's formula: $\text{weight} = 5 \times (||F| - (|P| + |T|)| + 1)$, scaling with $\text{diffP} \times \text{diffT}$.
   - The outer greedy reduction loop continues after minimal knot collapse, allowing surrounding workflow sequences/choices to cleanly finish reducing.
   - Strict termination guards ($|T| \le 1$) prevent infinite loops on irreducible or non-workflow topologies.
5. **Comprehensive Tests:**
   - 29 detection tests in `tests/test_fold_detection.py` and 25 reduction tests in `tests/test_fold_reduction.py` passing with 0 failures. All 340 repo tests pass.
