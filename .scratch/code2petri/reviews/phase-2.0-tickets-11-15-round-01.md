# Code Review: Phase 2 (Tickets 11–15) — with Suggestions

Reviewing full Phase 2 diff between `0de953e` and `HEAD`:
- `de21291 test(code2petri): add GameOfLife simulator cross-file validation suite (ticket 15)`
- `967a084 feat(code2petri): implement CLI context ingestion and reference serialization (ticket 14)`
- `1eac3d2 feat(code2petri): implement symbol table and cross-file call resolution (ticket 13)`
- `5230f85 feat(code2petri): implement variable bindings and call site extraction (ticket 12)`
- `5a5a28d refactor(code2petri): resolve round 2 review issues for ticket 11`
- `44b9154 refactor(code2petri): resolve round 1 review issues for ticket 11`
- `2046f3d feat(code2petri): implement WalkResult protocol return type and transition metadata (ticket 11)`

---

## Standards

### (a) Documented Repo Standards (`CONTEXT.md`, ADR 0001)
- **Hard Violations: 0.**
  The diff strictly adheres to the domain model vocabulary and architectural guidelines:
  - **Walker Protocol** ([`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md)): Directly implemented via `WalkerProtocol(ABC)` on [`PythonWalker`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/python_walker.py#L379) and [`JavascriptWalker`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L724) without intermediate base classes.
  - **Resolution Context & Call Site** ([`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md)): The CLI `--context` flag builds [`SymbolTable`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/symbol_table.py#L40) without converting context files into analysis targets; calls are modeled via [`CallSite`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/walker_protocol.py#L9).
  - **Constructor-Only Resolution** ([`docs/adr/0001-constructor-only-variable-resolution.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/docs/adr/0001-constructor-only-variable-resolution.md)): Walkers extract bindings via `collect_variable_bindings` without coupling to `code2flow`'s internal variable model. Unresolvable calls degrade to unexpanded transitions marked unresolved.

---

### (b) Baseline Smells (Judgement Calls) & Suggestions

1. **Duplicated Code**:
   - **Registry duplication** ([`code2petri/engine.py:13-16`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/engine.py#L13-L16) vs [`code2petri/symbol_table.py:12-15`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/symbol_table.py#L12-L15)):
     ```python
     WALKERS = {".py": PythonWalker, ".js": JavascriptWalker}
     ```
     *Suggestion*: Extract a centralized `SUPPORTED_WALKERS` dictionary into `code2petri/walker_protocol.py` or `code2petri/__init__.py`.
   - **Symbol disambiguation repetition** ([`code2petri/symbol_table.py:245-280`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/symbol_table.py#L245-L280)):
     ```python
     exact = [s for s in symbols if s.name == call_site.callee_name]
     matches = exact if exact else [s for s in symbols if s.bare_name == call_site.callee_name]
     if len(matches) == 1: return matches[0]
     ```
     *Suggestion*: Extract into a helper method `_find_unique_symbol_match(symbols, callee_name)`.
   - **Metadata key blacklist** ([`code2petri/model.py:131, 157`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/model.py#L131)):
     `skip_keys = {"resolved", "resolved_to", "target_file"}` is repeated across PNML and DOT formatters.
     *Suggestion*: Define a class constant `Transition.RESERVED_METADATA_KEYS`.

2. **Feature Envy / Temporal Coupling** ([`code2petri/control_flow_builder.py:90`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/control_flow_builder.py#L90) & [`code2petri/python_walker.py:325-327`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/python_walker.py#L325-L327))
   - **Finding**: Walkers query `self.builder.last_transition` after statement wiring to attribute call sites:
     ```python
     res = self.builder.wire_sequential_statement(...)
     if self.builder.last_transition:
         self._record_calls_in_expr(stmt, self.builder.last_transition.id, stmt.lineno)
     ```
   - *Suggestion*: Future refactor: have `wire_sequential_statement` return `(Place, Transition)` directly to eliminate stateful property queries.

3. **Primitive Obsession / Data Clumps (Residual)** ([`code2petri/symbol_table.py:305-320`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/symbol_table.py#L305-L320))
   - **Finding**: Resolution metadata is assembled as a dictionary then converted into `CallResolution`:
     ```python
     res_meta = {"resolved": True, "resolved_to": sym.name, "target_file": sym.filepath}
     t.metadata = {**t.metadata, **res_meta}
     t.resolution = CallResolution.from_metadata(t.metadata)
     ```
   - *Suggestion*: Instantiate `CallResolution(resolved=True, resolved_to=sym.name, target_file=sym.filepath)` directly and assign it to `t.resolution`.

---

## Spec

### (a) Missing or Partial Requirements & Suggestions

1. **Ticket 15 / Master Spec — `init` Resolution Assertions**:
   - **Spec line**: [`.scratch/code2petri/issues/15-game-of-life-cross-file-validation.md:10`](file:///.scratch/code2petri/issues/15-game-of-life-cross-file-validation.md#L10):
     > *"Integration test analyzes `init` in `app.js` with directory context `--context ./tests/test_code/game_of_life/`, asserting `gpuEngine.randomize()` and `gpuEngine.drawToScreen()` resolve to `WebGLEngine.randomize` and `WebGLEngine.drawToScreen`."*
   - **Finding**: In actual `app.js` source code, `init()` only invokes `randomizeBoth()` and `setupEventListeners()`. `gpuEngine.randomize()` is located inside `randomizeBoth()`, and `gpuEngine.drawToScreen()` is inside `WebGLEngine.randomize()`. The tests accurately assert resolution on those actual locations.
   - *Suggestion*: Update the ticket specification in `15-game-of-life-cross-file-validation.md` to reflect the faithful AST structure of the GameOfLife source files.

2. **User Story 9 — `[unresolved]` Annotation in Metadata**:
   - **Spec line**: [`.scratch/code2petri/specs/phase-2-cross-file-tracing.md:25`](file:///.scratch/code2petri/specs/phase-2-cross-file-tracing.md#L25):
     > *"calls to external libraries, browser APIs, or unresolvable targets to be explicitly annotated as `[unresolved]` in the Petri net metadata"*
   - **Finding**: Unresolved transitions set `metadata={"resolved": False}`. While DOT tooltips display `"Unresolved call"` and PNML emits `<unresolved/>`, the string `"[unresolved]"` is not stored as a metadata attribute.
   - *Suggestion*: Harmless; the boolean flag `resolved=False` and XML tag `<unresolved/>` satisfy machine readability. Optionally add `metadata["status"] = "[unresolved]"` if required by external consumers.

---

### (b) Behaviour Not Asked For (Scope Creep) & Suggestions

1. **`CallResolution` First-Class Domain Model** ([`code2petri/model.py:40-57`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/model.py#L40-L57)): Introduced in Round 1 to replace loose dictionaries with a validated dataclass. (Benign forward improvement).
2. **Generic Metadata Property Serialization** ([`code2petri/model.py:126-136, 156-161`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/model.py#L126-L136)): Emits `<property name=... value=...>` in PNML and comma-delimited tooltips in DOT for arbitrary metadata keys.
3. **Direct Class Receiver Resolution Fallback** ([`code2petri/symbol_table.py:207`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/symbol_table.py#L207)): Supports resolving direct static/class calls `ClassName.method()` when `callee_owner` is not bound as an instance variable.

---

### (c) Implemented Incorrectly & Suggestions

1. **Bare Calls Fallback Resolving to Class Methods** ([`code2petri/symbol_table.py:250-252, 268-270`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/symbol_table.py#L250-L252)):
   - **Spec line**: [`.scratch/code2petri/issues/13-symbol-table-and-call-resolution.md:11`](file:///.scratch/code2petri/issues/13-symbol-table-and-call-resolution.md#L11):
     > *"Call resolution resolves bare function calls (`func()`) against local file definitions first, then against unique matching symbols across context files of the same language."*
   - **Finding**: In `symbol_table.py`, when an exact top-level match for a bare call (e.g. `step()`) is not found, the fallback query matches `[s for s in symbols if s.bare_name == call_site.callee_name]`. Because `WebGLEngine.step` has `bare_name == "step"`, an un-owned bare call `step()` can erroneously resolve to `WebGLEngine.step` if no top-level `step` function exists!
   - *Suggestion*: For bare function calls (`call_site.callee_owner is None`), resolution should only match top-level/global functions (where `not s.is_method`), never class methods.

---

## One-Line Summary

- **Standards**: 0 hard violations, 3 judgement calls (worst: symbol disambiguation logic duplicated in `symbol_table.py`).
- **Spec**: 0 missing requirements, 3 scope creeps (benign forward extensions), **1 logic defect** (bare function calls erroneously falling back to match class methods via `bare_name`).

