# Ticket 23: Code Review (Round 1)

**Diff:** `9d46ae6...HEAD`  
**Commits:** `8d2772b feat(code2petri): port ProM local sequence and choice reduction (ticket 23)`  
**Spec:** `.scratch/code2petri/issues/23-prom-port-sequence-choice.md`  

## Standards
**STATUS: WARN (2 Hard Violations, 3 Baseline Smells)**

### (a) Documented Repo Standards (`CONTEXT.md`)
1. **[`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md#L71-L74) — Single-Place Contraction** (*Avoid: Sequence collapsing, chain reduction*)
   - **Locations**: [`code2petri/fold.py:213-226`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/fold.py#L213-L226) & [`code2petri/__init__.py:16-19`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/__init__.py#L16-L19)
   - **Finding**: The fine-grained 1→1→1 reduction operation is exported as `fold_sequence` / `foldSequence`, and docstrings/comments describe "Sequence collapsing" / "collapsing parallel transitions". `CONTEXT.md` explicitly defines this operation as **Single-Place Contraction** and strictly prohibits the aliases *"Sequence collapsing"* and *"chain reduction"*.
   - **Suggestion**:
     - Align docstrings and comments strictly with `CONTEXT.md`: document that `fold_sequence` performs **Single-Place Contraction** (e.g. `"""Performs Single-Place Contraction on an intermediate place connecting adjacent transitions per ProM (1 -> 1 -> 1)."""`).
     - Remove prohibited phrases (*"Sequence collapsing"*, *"chain reduction"*) from module comments and docstrings.
     - Optionally add `fold_single_place_contraction = fold_sequence` as an alias if domain consistency is prioritized.

2. **[`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md#L31-L34)** & **[`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md#L47-L50)** — **Structural Fold** (*Avoid: macro collapsing*) & **Faithful Translation** (*Avoid: Normalization*)
   - **Location**: [`docs/adr/0003-adopt-prom-local-reduction-algorithm.md:13-22`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/docs/adr/0003-adopt-prom-local-reduction-algorithm.md#L13-L22)
   - **Finding**: ADR 0003 introduces prohibited vocabulary: line 13 cites *"bounds for macro-components"* (violating *Structural Fold* / macro collapsing), line 18 cites *"parallel branch collapse"*, and line 22 refers to avoiding *"pre-normalization"* (violating *Faithful Translation* / Normalization).
   - **Suggestion**:
     - Line 13: Replace *"bounds for macro-components"* with *"bounds for compound SESE subnets"* or *"composite components"*.
     - Line 18: Replace *"parallel branch collapse"* with *"Choice component reduction"* or *"atomic parallel transition fold"*.
     - Line 22: Replace *"pre-normalization"* with *"synthetic AST transformation"* or *"pre-processing AST routing places"*.

---

### (b) Baseline Code Smells (Fowler Refactoring ch. 3 — Judgement Calls)
1. **Speculative Generality / Mysterious Name** (Judgement Call)
   - **Locations**: [`code2petri/fold.py:226, 293`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/fold.py#L226-L293), [`code2petri/__init__.py:16-52`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/__init__.py#L16-L52)
   - **Hunk**:
     ```python
     foldSequence = fold_sequence
     ...
     foldChoice = fold_choice
     ```
   - **Finding**: CamelCase aliases mirroring Java ProM method names were introduced and re-exported in `__all__`. Python idioms prescribe snake_case (`fold_sequence`); exposing redundant dual names clutters the public API without a spec requirement.
   - **Suggestion**:
     - Remove the CamelCase aliases (`foldSequence`, `foldChoice`) from `code2petri/fold.py` and `code2petri/__init__.py`. Standardize entirely on idiomatic Python snake_case (`fold_sequence`, `fold_choice`).

2. **Duplicated Code** (Judgement Call)
   - **Locations**: [`code2petri/fold.py:213-224`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/fold.py#L213-L224) vs [`code2petri/fold.py:280-291`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/fold.py#L280-L291)
   - **Finding**: `fold_sequence` and `fold_choice` share identical 5-line wrapper boilerplate (default config fallback, query candidate list, empty check, call `fold_component`).
   - **Suggestion**:
     - Extract a shared helper in `code2petri/fold.py`:
       ```python
       def _fold_first_candidate(
           net: PetriNet,
           candidates: List[Component],
           step_number: int,
       ) -> Optional[Tuple[PetriNet, FoldStep]]:
           if not candidates:
               return None
           return fold_component(net, candidates[0], step_number)
       ```
     - Then implement `fold_sequence` and `fold_choice` concisely:
       ```python
       def fold_sequence(net: PetriNet, step_number: int, config: Optional[FoldConfig] = None):
           cfg = config if config is not None else FoldConfig()
           return _fold_first_candidate(net, detect_sequences(net, cfg), step_number)
       ```

3. **Middle Man** (Judgement Call)
   - **Location**: [`code2petri/fold.py:213-224`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/fold.py#L213-L224)
   - **Finding**: `fold_sequence` and `fold_choice` act purely as thin single-step delegates forwarding to `detect_*` and `fold_component`. In `fold_net`, loop reduction bypasses this pattern by calling `detect_loops` directly.
   - **Suggestion**:
     - Standardize reduction stages across `fold_net`:
       - *Option A (Consistent Wrappers)*: Implement `fold_loop(net, step_number, config)` following the same pattern, allowing `fold_net` to cleanly dispatch to `res = fold_seq(...) or fold_choice(...) or fold_loop(...)`.
       - *Option B (Direct Detection)*: Have `fold_net` directly query `detect_sequences`, `detect_choices`, and `detect_loops`, eliminating the single-step helper functions if they are not intended as standalone public API entry points.

---

## Spec
**STATUS: WARN (0 Missing Requirements, 2 Scope Creep, 1 Implementation Advisory)**

### (a) Requirements Missing or Partial
* **None (0 missing requirements).** All 4 spec checklist items from `.scratch/code2petri/issues/23-prom-port-sequence-choice.md` are fully implemented:
  - `foldSequence` ($1 \to 1 \to 1$ intermediate place contraction).
  - `foldChoice` (parallel transition collapse between shared input and output places).
  - Prioritized greedy loop (Sequence $\to$ Choice $\to$ Loop) restarting on success via `continue`.
  - Synthetic AST topology tests (`TestASTTopologyReduction` in `tests/test_fold_reduction.py`).

---

### (b) Behaviour in Diff Not Asked For (Scope Creep)
1. **Replacement of Definition 22 Choice Penalty Formula:**
   - **Spec Quote**: `"- [x] Implement foldChoice collapsing parallel transitions between a single shared input place and single shared output place."`
   - **Finding**: The diff replaces the paper's symmetry difference formula (`calculate_symmetry_multiplier`) with ProM's hardcoded 1.5x weight markup: `omega = cfg.choice * (sum_tau * 0.5)` (yielding $\tau_{new} = \sum \tau \times 1.5$). The ticket specification only requested topological collapse of parallel transitions, not modifying the structuredness metric calculation.
   - **Suggestion**:
     - Update `.scratch/code2petri/issues/23-prom-port-sequence-choice.md` to explicitly state the metric formula change (or cite user story 1 from `phase-2.6-interactive-expansion.md`: *"evaluate if/else branches using the formal Choice multiplier (1.5x)"*).
     - Ensure this multiplier change is documented in `FoldConfig` docstrings so that users know Choice folding now uses ProM's 1.5x linear scaling rather than Lassen 2008 Def. 22 symmetry difference.

2. **Unrequested Documentation & ADR Artifacts:**
   - **Finding**: The commit introduces a 427-line reverse-engineering log (`.scratch/code2petri/prom-analysis-process.md`), a formal ADR (`docs/adr/0003-adopt-prom-local-reduction-algorithm.md`), and updates to `CONTEXT.md`. While helpful context, these were not requested by ticket 23.
   - **Suggestion**:
     - Retain these valuable architectural records, but in future PRs/tickets split large architectural documentation and ADRs into a dedicated `docs(...)` commit (as done in Phase 2.5) to keep feature commit diffs focused strictly on implementation.

---

### (c) Requirements Implemented But Implementation Looks Wrong (Advisory)
1. **Divergence from ProM's Choice Isolation Invariant:**
   - **Spec Quote**: `"- [x] Implement foldChoice collapsing parallel transitions between a single shared input place and single shared output place."`
   - **Finding**: In ProM (`PNAnalysis.jar`), `foldChoice()` requires `targetTransitions.equals(sourceTransitions)`, meaning $p_{source}$ must have *no other* outgoing transitions and $p_{sink}$ must have *no other* incoming transitions. In the diff, `detect_choices` groups transitions by destination place and collapses any parallel bundle of size $\ge 2$ even if $p_{source}$ or $p_{sink}$ has external connections. While this is valid under Murata reduction rules, if the intent was strict parity with ProM's reference implementation, this isolation check was omitted.
   - **Suggestion**:
     - **If strict ProM parity is intended**: Add isolation assertions in `detect_choices` verifying that `set(topo.postsets(p_source)) == set(tids)` and `set(topo.presets(p_sink)) == set(tids)`.
     - **If generalized Murata parallel reduction is intentional**: Keep the current behavior (as it gracefully handles complex AST branching with fallthroughs/early exits), but explicitly document this architectural divergence in `docs/adr/0003-adopt-prom-local-reduction-algorithm.md` and `detect_choices` docstring so maintainers know it is an intentional extension beyond ProM.

---

## Summary
- **Standards Axis:** 5 findings (2 hard violations: worst is prohibited vocabulary in `CONTEXT.md` / `ADR 0003`; 3 baseline smells: worst is redundant CamelCase alias exports in public API).
- **Spec Axis:** 3 findings (0 missing requirements; 2 scope creep: worst is unrequested replacement of Definition 22 SM formula; 1 implementation advisory: omission of ProM's choice isolation invariant).
