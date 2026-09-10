# Code Review: Phase 2 (Round 3) — Issues Yet to Be Addressed

This report documents the remaining open items across Phase 2 (Tickets 11–15) following the resolution of the bare-call resolution defect and primary code smells in commit `6d0bcec`.

All **234 tests are passing** with **0 Hard Standards Violations** and **0 Functional Logic Defects**. The items below represent residual architectural smells (judgement calls) and documentation synchronizations.

---

## 1. Standards: Baseline Smells (Judgement Calls)

### Issue 1: Middle Man Property Alias on `Transition`
- **Location:** [`code2petri/model.py:89-91`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/model.py#L89-L91)
- **Code:**
  ```python
  @property
  def call_resolution(self) -> Optional[CallResolution]:
      """Returns typed CallResolution if call resolution is present."""
      return self.resolution
  ```
- **Analysis:** `self.resolution` is already a public attribute on `Transition`. `call_resolution` is a redundant property alias acting as a middle man.
- **Actionable Suggestion:** 
  Delete `@property def call_resolution` and ensure all internal callers and test assertions consistently access `transition.resolution`.

---

### Issue 2: Duplicated Lookup & Logging Shape in Symbol Table
- **Location:** [`code2petri/symbol_table.py:263-290`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/symbol_table.py#L263-L290)
- **Code:**
  ```python
  # Local symbol lookup & ambiguity logging:
  sym = self._find_unique_bare_symbol_match(local_symbols, call_site.callee_name)
  if sym:
      return sym
  if len([s for s in local_symbols if s.name == call_site.callee_name or (not s.is_method and s.bare_name == call_site.callee_name)]) > 1:
      logger.warning(...)

  # Context symbol lookup & ambiguity logging repeats identical structure:
  sym = self._find_unique_bare_symbol_match(context_symbols, call_site.callee_name)
  if sym:
      return sym
  if len([s for s in context_symbols if s.name == call_site.callee_name or (not s.is_method and s.bare_name == call_site.callee_name)]) > 1:
      logger.warning(...)
  ```
- **Analysis:** The disambiguation count check and warning logging is duplicated verbatim between local and context symbol searches.
- **Actionable Suggestion:**
  Extract a single private helper:
  ```python
  def _resolve_bare_in_symbols(
      self, symbols: List[Symbol], call_site: CallSite, scope_label: str
  ) -> Optional[Symbol]:
      sym = self._find_unique_bare_symbol_match(symbols, call_site.callee_name)
      if sym:
          return sym
      ambiguous = [
          s for s in symbols
          if s.name == call_site.callee_name or (not s.is_method and s.bare_name == call_site.callee_name)
      ]
      if len(ambiguous) > 1:
          logger.warning(
              "Ambiguous call '%s' matches multiple %s symbols: %s",
              call_site.callee_name,
              scope_label,
              [s.name for s in ambiguous],
          )
      return None
  ```

---

### Issue 3: Feature Envy / Temporal Coupling (`last_transition`)
- **Location:**
  - [`code2petri/python_walker.py:325-327`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/python_walker.py#L325-L327)
  - [`code2petri/javascript_walker.py:683-685`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L683-L685)
- **Code:**
  ```python
  res = self.builder.wire_sequential_statement(...)
  if self.builder.last_transition:
      self._record_calls_in_expr(stmt, self.builder.last_transition.id, stmt.lineno)
  ```
- **Analysis:** Walkers reach into `self.builder.last_transition` after statement wiring to extract and attribute call sites to transitions. This introduces stateful temporal coupling on the builder.
- **Actionable Suggestion:**
  In a future builder cleanup, let `wire_sequential_statement` return a `(Place, Transition)` tuple directly, or accept an `on_statement_trans` callback (mirroring `on_true_trans` in `wire_if_split`).

---

## 2. Spec: Documentation Synchronization

### Issue 4: Ticket 15 Markdown Text vs. Real AST Structure
- **Location:** [`.scratch/code2petri/issues/15-game-of-life-cross-file-validation.md:10`](file:///.scratch/code2petri/issues/15-game-of-life-cross-file-validation.md#L10)
- **Analysis:** The checklist item describes `gpuEngine.randomize()` and `gpuEngine.drawToScreen()` as being directly inside `init()`. In the actual `app.js` source code, `init()` calls `randomizeBoth()`, which calls `gpuEngine.randomize()`, which in turn calls `gpuEngine.drawToScreen()`. The test suite faithfully asserts on the real code locations.
- **Actionable Suggestion:** Ensure the checklist item wording in `15-game-of-life-cross-file-validation.md` remains synchronized with the true AST call hierarchy.

---

## Summary of Open Issues

| Issue | Severity | File(s) | Suggested Fix |
|---|---|---|---|
| **Middle Man** | Minor Smell | `code2petri/model.py` | Remove `@property def call_resolution`, use `self.resolution` directly |
| **Duplicated Code** | Minor Smell | `code2petri/symbol_table.py` | Extract `_resolve_bare_in_symbols` helper for lookup & warning logging |
| **Feature Envy** | Judgement Call | `python_walker.py`, `javascript_walker.py` | Return `(Place, Transition)` from `wire_sequential_statement` |
| **Spec Sync** | Doc Hygiene | `15-game-of-life-cross-file-validation.md` | Confirm checklist wording matches actual AST hierarchy |

