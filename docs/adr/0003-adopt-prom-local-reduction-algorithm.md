# 3. Adopt ProM's Local Reduction Algorithm

Date: 2026-09-20

## Status

Accepted (Phase 2.6)

## Context

In Phase 2.5, we implemented the Structuredness Metric (SM) reduction engine using maximal pattern matchers for sequences, choices, and loops. However, AST-generated control flow often contains intermediate routing places (e.g., `p_split -> t_if -> p_branch_entry -> t_stmt -> p_merge`). These structurally correct but non-textbook topologies confounded our maximal detectors, preventing the algorithm from folding standard `if/else` and `while` blocks.

We analyzed `PNAnalysis.jar`, the ground-truth Java implementation of Lassen & van der Aalst's paper in the ProM framework. The analysis revealed that ProM does *not* search for maximal chains. Instead, it performs **Single-Place Contractions** (removing one place at a time). This inherently reduces intermediate AST routing places, transforming complex branches into atomic `p_split -> t_if -> p_merge` connections that are easily folded by subsequent passes. Furthermore, ProM uses bidirectional reachability ($forward(u, v) == backward(v, u)$) to detect Single-Entry Single-Exit (SESE) bounds for compound SESE subnets and unstructured knots.

## Decision

We replace our maximal pattern matchers in `code2petri/fold.py` with direct Python ports of ProM's algorithms across two stages:

### Part I: Local Reductions (Ticket 23)
1. `fold_sequence` (`fold_single_place_contraction`): Single-Place Contraction on an intermediate place connecting adjacent transitions ($t_1 \to p \to t_2$ where $|*p|=1, |p*|=1, |t_1*|=1, |*t_2|=1$).
2. `fold_choice`: Atomic parallel transition fold with ProM 1.5x choice multiplier.

### Part II: Loops & SESE Macro-Components (Ticket 24)
3. `fold_while`: Local 2-in/2-out place loop fold on a place sharing a self-loop transition ($t_{loop}$ with $|*t_{loop}|=1, |t_{loop}*|=1$), folding into entry transition with weight $\tau(t_{src}) + \tau(t_{snk}) + 2.0 \times \tau(t_{loop})$ ($\omega = (\text{cfg.loop} / 3.0) \times \tau(t_{loop})$). Linear intra-loop places contract via `fold_sequence` first, collapsing multi-node cycles into canonical self-loop transitions.
4. **SESE Bidirectional Reachability Invariant:** Single-Entry Single-Exit subnets bounded by entry node $u$ and exit node $v$ are discovered via exact bidirectional BFS reachability equality: $\text{forward}(u, v) == \text{backward}(v, u)$, with $|T| > 1$.
5. **Maximal SESE Macro-Components:**
   - `fold_marked_graph`: Detects the *maximal* SESE subnet bounded by transitions $(t_{src}, t_{snk})$ where all internal places satisfy $|\bullet p| = 1$ and $|p \bullet| = 1$.
   - `fold_state_machine`: Detects the *maximal* SESE subnet bounded by places $(p_{src}, p_{snk})$ where all internal transitions satisfy $|\bullet t| = 1$ and $|t \bullet| = 1$.
   - `fold_well_structured`: Detects the *maximal* SESE subnet bounded by places $(p_{src}, p_{snk})$ free from PT/TP handles and internal cycles.
6. **Minimal SESE Knot Isolation (`fold_unstructured`):**
   - When structured reduction rules are exhausted, `fold_unstructured` searches for the *minimal* internal SESE subnet ($\text{forward} == \text{backward}$) containing $> 1$ transition.
   - It collapses only this localized irreducible knot into an opaque transition using ProM's penalty formula:
     $$\text{weight} = 5 \times (||F_C| - (|P_C| + |T_C|)| + 1)$$
     $$\tau_{new} = \left(\sum_{t \in T_C} \text{weight} \times \tau(t)\right) \times \text{diffP} \times \text{diffT}$$
   - The greedy reduction loop in `fold_net` then continues, allowing the surrounding outer workflow structure (e.g., surrounding sequence or choice nodes) to cleanly reduce down to a single transition rather than aborting or swallowing the entire net.
   - Global fallback collapses the entire net if no internal SESE pair exists and $|T| > 1$. Termination is guaranteed when $|T| \le 1$.

### Architectural Note: Generalized Murata Choice Reduction
While ProM's `foldChoice()` requires strict isolation (where $p_{source}$ and $p_{sink}$ have no other incident transitions), code2petri generalizes Murata parallel transition reduction by grouping parallel transitions by destination place. This allows atomic parallel folds even when boundary places have other branches, which is essential for ASTs with fallthroughs or multi-branch splits.

## Consequences

- **Positive:** Mathematically aligns our tool with the reference academic implementation (`PNAnalysis.jar` / Lassen & van der Aalst 2008).
- **Positive:** Automatically resolves AST branching and loop anomalies without requiring pre-processing AST routing places or modifying language walkers.
- **Positive:** Isolates irreducible knots (e.g., from `goto` or unstructured breaks/continues), preserving the reducibility of surrounding workflow control flow.
- **Positive:** Step-by-step reduction is much finer-grained, providing better visual playback in the viewer.
- **Negative:** Replaced legacy heuristic matchers in `fold.py`, requiring comprehensive unit tests covering all 7 Definition 21 component classes.
