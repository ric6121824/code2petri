# 23 — ProM Algorithm Port I: Local Sequence & Choice

**What to build:** The `fold.py` engine successfully reduces AST-generated `if/else` structures (which contain intermediate branch routing places) using fine-grained Single-Place Contraction (`foldSequence`) and Atomic Choice Collapse (`foldChoice`), avoiding the Unstructured fallback.

**Blocked by:** None — can start immediately.

**Status:** resolved

- [x] Implement `foldSequence` matching the ProM $1 \to 1 \to 1$ topology (contracting exactly one intermediate place and merging its adjacent transitions).
- [x] Implement `foldChoice` collapsing parallel transitions between a single shared input place and single shared output place.
- [x] Update the greedy reduction loop to prioritize Sequence then Choice, restarting the loop whenever a fold succeeds.
- [x] Create synthetic AST topology tests (e.g., mimicking `wire_if_split`) that prove the new algorithms correctly collapse them down to a single transition without unstructured penalties.

## Answer

1. **Single-Place Contraction (`fold_sequence`)**:
   - Implemented in `code2petri/fold.py` following ProM's reference $1 \to 1 \to 1$ topology (`PNAnalysis.jar`).
   - Identifies an intermediate place $p$ with $|*p| = 1$, $|p*| = 1$, $t_{src} \ne t_{snk}$, $|t_{src}*| = 1$, and $|*t_{snk}| = 1$.
   - Includes safety guards: does not contract marked places (`initial_tokens > 0`), and avoids collapsing 2-transition cycles into self-loops (`presets(t_src) & postsets(t_snk) == empty`).
   - Merges adjacent transitions into a single opaque transition $t_C$, accumulating $\tau = \tau(t_{src}) + \tau(t_{snk})$ with $\omega = 0.0$.

2. **Atomic Choice Fold (`fold_choice`)**:
   - Implemented in `code2petri/fold.py` grouping outgoing transitions from each place by common single output place (generalizing Murata parallel transition reduction).
   - Matches any bundle of $\ge 2$ parallel transitions between shared entrance $p_{source}$ and shared exit $p_{sink}$.
   - Applies ProM's 1.5x complexity markup (per Phase 2.6 User Story 1): $\tau_{new} = \sum \tau \times 1.5$, setting $\omega = \text{cfg.choice} \times (\sum \tau \times 0.5)$.

3. **Greedy Prioritized Reduction Loop (`fold_net`)**:
   - Updated `fold_net` to prioritize Sequence first, then Choice, then Loop, then Unstructured fallback.
   - Uses `continue` to immediately restart from the top priority (Sequence) whenever any reduction rule succeeds.

4. **Synthetic AST Topology Test Suite (`tests/test_fold_reduction.py`)**:
   - Added `TestASTTopologyReduction` covering:
     - `test_ast_if_else_reduction`: standard AST `if/else` with intermediate places `p_true` and `p_false` reduces completely in 3 steps (2 sequence contractions + 1 choice fold) with 0 unstructured penalties.
     - `test_ast_if_without_else_reduction`: AST `if` with fallthrough branch reduces completely in 2 steps (1 sequence contraction + 1 choice fold).
     - `test_ast_nested_if_else_reduction`: nested `if/else` inside then-branch reduces completely without unstructured fallback.
   - All 326 unit and regression tests pass.
