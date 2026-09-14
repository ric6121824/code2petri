# Code Review: Ticket 12 (Round 1)

Reviewing full diff against `5a5a28d` (`refactor(code2petri): resolve round 2 review issues for ticket 11`):
- Ticket: `.scratch/code2petri/issues/12-variable-bindings-and-call-sites.md`
- Architecture Reference: `docs/adr/0001-constructor-only-variable-resolution.md`, `CONTEXT.md`

---

## Standards

### (a) Documented Repo Standards (`CONTEXT.md`, ADR 0001)
- **Hard Violations: 0.**
  - **Walker Protocol**: Maintained `WalkerProtocol(ABC)` with `collect_variable_bindings(tree: Any) -> Dict[str, str]` and `walk_function(ast_node: Any, func_name: str = "", filepath: Optional[str] = None) -> WalkResult`.
  - **Constructor-Only Variable Resolution (ADR 0001)**: Followed ADR 0001 to implement lightweight, walker-internal constructor tracking for canonical instantiation patterns (`x = Foo()`, `self.x = Foo()`, `const/let/var x = new Foo()`, `this.x = new Foo()`), avoiding coupling to code2flow's internal variable model or complex multi-pass type inference.
  - **Call Site Domain Model**: `CallSite` instances accurately populate all domain attributes (`caller_function`, `caller_file`, `callee_name`, `callee_owner`, `line_number`, `transition_id`), ensuring transitions in the generated Petri net correspond 1:1 with `transition_id`.

---

### (b) Baseline Smells (Judgement Calls)
1. **Divergent Change / Feature Envy (Minor)**:
   - `ControlFlowBuilder` added `last_transition` property and `on_true_trans` callback hook on `wire_if_split`.
   - *Assessment*: This cleanly allows walkers to associate extracted AST call expressions with the exact transition generated for that statement/condition without exposing internal arc wiring or breaking builder encapsulation.
2. **Speculative Generality (Minor)**:
   - `_extract_target_name` in `python_walker.py` checks `hasattr(ast, "unparse")` for deep attribute targets.
   - *Assessment*: Standard defensive Python 3.9+ compatibility idiom; harmless and clean.

---

## Spec

### (a) Missing or Partial Requirements
**None (0 Missing).**
All Ticket 12 requirements are fully satisfied:
- `PythonWalker.collect_variable_bindings(tree)` extracts constructor assignments (`x = Foo(...)` and `self.x = Foo(...)`) into a `{variable_name: class_name}` map ([`12-variable-bindings-and-call-sites.md:9`](file:///.scratch/code2petri/issues/12-variable-bindings-and-call-sites.md#L9)).
- `JavascriptWalker.collect_variable_bindings(tree)` extracts constructor assignments (`const/let/var x = new Foo(...)` and `this.x = new Foo(...)`) into a `{variable_name: class_name}` map ([`12-variable-bindings-and-call-sites.md:10`](file:///.scratch/code2petri/issues/12-variable-bindings-and-call-sites.md#L10)).
- `PythonWalker.walk_function` populates `WalkResult.call_sites` with `CallSite` records capturing caller function, caller file, callee name, callee owner (if attribute call), line number, and corresponding transition ID ([`12-variable-bindings-and-call-sites.md:11`](file:///.scratch/code2petri/issues/12-variable-bindings-and-call-sites.md#L11)).
- `JavascriptWalker.walk_function` populates `WalkResult.call_sites` with `CallSite` records capturing caller function, caller file, callee name, callee owner (if MemberExpression call), line number, and corresponding transition ID ([`12-variable-bindings-and-call-sites.md:12`](file:///.scratch/code2petri/issues/12-variable-bindings-and-call-sites.md#L12)).
- Unit tests in `test_python_walker.py` and `test_javascript_walker.py` verify that `collect_variable_bindings` and `CallSite` extraction faithfully extract constructor targets and call records ([`12-variable-bindings-and-call-sites.md:13`](file:///.scratch/code2petri/issues/12-variable-bindings-and-call-sites.md#L13)).
- All 202 unit/integration tests pass without regression.

---

### (b) Behaviour Not Asked For (Scope Creep)
1. **Optional `filepath` Parameter on `WalkerProtocol.walk_function`**:
   - Allows passing the source file path during walking to populate `CallSite.caller_file`. Default is `None`, maintaining backward compatibility with single-file and synthetic AST test invocations.
2. **`on_true_trans` Callback in `wire_if_split`**:
   - Enables recording call sites located inside `if` condition expressions on the condition's transition.

---

### (c) Implemented But Wrong
**None (0 Defects).**
All call sites and bindings are verified against real test fixtures (`app.js`, `webgl_engine.js`, `sequential.py`, `mixed_pipeline.py`) and synthetic tests. Transition IDs in call site records reliably exist in the emitted `PetriNet`.

---

## One-Line Summary

- **Standards**: 0 hard violations, 2 judgement calls (benign builder hooks for call site attribution).
- **Spec**: 0 missing requirements, 2 minor scope additions (optional `filepath` and condition transition hook), 0 logic defects.
