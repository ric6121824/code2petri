# Code Review: Tickets 07–10 (Phase 1 — Round 2 Re-Review)

**Review Target:** Changes between commit `f41d6ba` and `HEAD` (`d72e78f`), re-evaluating the full feature set following fix commit `d72e78f`:
- `d72e78f` fix(code2petri): resolve issues identified in code review for tickets 07-10
- `a7d9ad2` refactor(code2petri): address code-review findings on Ticket 10
- `d186bb1` feat(code2petri): implement JavaScript specifics and game-loop translation (ticket 10)
- `a2fc9bc` refactor(code2petri): address code-review findings on JS core control flow (ticket 09)
- `fbecfac` feat(code2petri): implement JavaScript core control flow constructs (ticket 09)
- `29c7369` refactor(code2petri): address code-review findings on JS walker (ticket 08)
- `7d62b7a` feat(code2petri): implement JavaScript walker skeleton and sequential statements (ticket 08)
- `d8ca94c` refactor(code2petri): address code-review findings on qualification and exports (ticket 07)
- `e87b993` feat(code2petri): implement WalkerProtocol and shared base walker infrastructure (ticket 07)

*Previous review report:* [tickets-07-10.md](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/reviews/tickets-07-10.md)

---

## Status of Previous Findings

| Finding from Round 1 | Status in Round 2 | Resolution Note |
|---|---|---|
| `PythonWalker` missing `(global)` scope | **Resolved** | Added `_get_executable_statements()` and `(global)` support in `python_walker.py` |
| Prohibited "normalizes" vocabulary in docstring | **Resolved** | Replaced prohibited term in `javascript_walker.py` |
| Redundant base walker aliases exported in package | **Resolved** | Cleaned up `__all__` in `code2petri/__init__.py` |
| Missing TODO marker for `setTimeout`/`setInterval` | **Resolved** | Added TODO comment in `javascript_walker.py` |
| Scoped JS class methods dropping outer function scope | **Resolved** | Preserves full `scope + [cls_name, key]` in `javascript_walker.py` |
| Automatic ES module fallback (`source_type="module"`) | **Resolved** | Removed auto-fallback in `javascript_walker.py` |
| Unrequested `.mjs` extension registration | **Resolved** | Removed `.mjs` from `WALKERS` in `engine.py` |
| `requestAnimationFrame` dropping trailing statements | **Resolved** | Corrected non-terminating arc flow and added tests |
| Divergent `throw` vs. `raise` exception handling | **Resolved** | Unified exception flow across Python and JavaScript walkers |

---

## Standards

### Standards Violations (Hard)

1. **[CONTEXT.md](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) — Walker Protocol** (`_Avoid_: Parser interface, walker base class`):
   - **File**: [`code2petri/base_walker.py#L16`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/base_walker.py#L16), [`tests/test_walker_protocol.py#L198`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_walker_protocol.py#L198)
   - **Breach**: Introduces `base_walker.py` defining `class _BaseControlFlowWalker` with docstring `"""Base control flow walker..."""` and test `test_package_does_not_export_walker_base_class`. The repo domain standard establishes `WalkerProtocol` as the strict abstraction and explicitly forbids "walker base class".

---

### Baseline Smells (Judgement Calls)

1. **Repeated Switches**:
   - **File**: [`code2petri/javascript_walker.py#L98-L188`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L98-L188), [`code2petri/javascript_walker.py#L305-L562`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L305-L562), [`code2petri/javascript_walker.py#L241-L261`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L241-L261)
   - **Quote**:
     ```python
     stmt_type = stmt.get("type")
     if stmt_type == "ReturnStatement": ...
     elif stmt_type in ("BreakStatement", "ContinueStatement"): ...
     ```
   - Repeated `if/elif` cascades branch on `stmt_type` across `_format_statement_label`, `walk_block`, and `_find_raf_call` instead of using dictionary dispatch or polymorphic visitor methods.

2. **Duplicated Code**:
   - **File**: [`code2petri/javascript_walker.py#L355-L380`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L355-L380) vs [`code2petri/python_walker.py#L221-L246`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/python_walker.py#L221-L246)
   - **Quote**:
     ```python
     self.loop_stack.append(LoopContext(head=loop_head, exit=loop_exit))
     self._walk_branch(..., loop_trans, loop_head, ...)
     self.loop_stack.pop()
     self.net.add_arc(source=exit_trans, target=loop_exit)
     ```
   - Identical Petri net loop-wiring logic is duplicated across both language walkers rather than unified. Also, string slicing in `_JavascriptControlFlowWalker._slice` duplicates `JavascriptWalker._slice_node`.

3. **Primitive Obsession**:
   - **File**: [`code2petri/javascript_walker.py#L620-L646`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L620-L646)
   - **Quote**:
     ```python
     results.append({"qual_name": qual_name, "bare_name": bare_name, "lineno": lineno, "node": node})
     ```
   - Discovered function metadata is passed as ad-hoc string-keyed `dict` primitives instead of a domain `NamedTuple` or dataclass (comparable to `LoopContext`).

4. **Divergent Change**:
   - **File**: [`code2petri/javascript_walker.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py)
   - A single 783-line module handles AST normalization, source slicing, statement formatting, game-loop cycle detection, net construction, and AST traversal.

5. **Middle Man**:
   - **File**: [`code2petri/python_walker.py#L427-L432`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/python_walker.py#L427-L432)
   - **Quote**:
     ```python
     _default_walker = PythonWalker()
     parse_file = _default_walker.parse_file
     find_function = _default_walker.find_function
     find_all_functions = _default_walker.find_all_functions
     walk_function = _default_walker.walk_function
     ```
   - Module-level functions exist merely to forward calls onward to `_default_walker`.

---

## Spec

### (a) Missing or Partial Requirements

1. **Acorn npm Dependency Documentation/Handling**:
   - **Spec Quote**: *"The `code2flow` Acorn script (`get_ast.js`) is used natively by this project; ensure the dependency on the `acorn` npm package is documented or handled."* ([phase-1-js-walker.md#L54](file:///.scratch/code2petri/specs/phase-1-js-walker.md#L54))
   - **Finding**: Neither setup documentation nor runtime verification for the external `acorn` npm package dependency was added.

2. **Walker Class Inheritance Contract**:
   - **Spec Quote**: *"PythonWalker inherits from the new ABC and base class."* ([07-prefactor-walker-protocol.md#L11](file:///.scratch/code2petri/issues/07-prefactor-walker-protocol.md#L11)) / *"JavascriptWalker class is implemented, inheriting from the ABC and `_BaseControlFlowWalker`."* ([08-js-walker-skeleton.md#L9](file:///.scratch/code2petri/issues/08-js-walker-skeleton.md#L9))
   - **Finding**: Neither `PythonWalker` nor `JavascriptWalker` inherits from `_BaseControlFlowWalker`; they only inherit from `WalkerProtocol`. `_BaseControlFlowWalker` is instead inherited by internal block walkers (`_PythonControlFlowWalker` / `_JavascriptControlFlowWalker`).

### (b) Scope Creep (Unrequested Behaviour)

1. **Arbitrary Suffix Function Matching**:
   - **Spec Quote**: *"Class methods will use qualified names (`ClassName.methodName`) across both Python and JS."* ([phase-1-js-walker.md#L32](file:///.scratch/code2petri/specs/phase-1-js-walker.md#L32))
   - **Finding**: In [`javascript_walker.py#L707-L712`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L707-L712), `find_function` implements fuzzy suffix matching (`qual_name.endswith(f".{func_name}")`), permitting partial qualification matches not specified in the user stories or tickets.

### (c) Incorrect Implementation

1. **`ReturnStatement` Shadows `requestAnimationFrame` Cycle Detection**:
   - **Spec Quote**: *"As a user, I want a `requestAnimationFrame(loop)` call to be translated into a back-arc cycle in the Petri net, so that standard game-loop recursion is accurately modeled."* ([phase-1-js-walker.md#L17](file:///.scratch/code2petri/specs/phase-1-js-walker.md#L17))
   - **Finding**: In [`javascript_walker.py#L307-L314`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L307-L314), `walk_block` unconditionally intercepts `ReturnStatement` before reaching `_is_raf_cycle_call` at line 541. Despite `_find_raf_call` ([L257-L260](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L257-L260)) specifically extracting calls from `ReturnStatement`, statements like `return requestAnimationFrame(loop);` exit directly to `end_place` without creating a cycle.

2. **JavaScript Function Line Number Logging in CLI**:
   - **Spec Quote**: *"As a user, I want to pass a `.js` file to `code2petri`, so that I can generate Petri nets from JavaScript code."* ([phase-1-js-walker.md#L11](file:///.scratch/code2petri/specs/phase-1-js-walker.md#L11))
   - **Finding**: In [`engine.py#L99`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/engine.py#L99), `getattr(func_node, "lineno", 0)` expects Python AST objects. For JS dict nodes, it always defaults to `0`, logging `line 0` for all JS functions.

---

## Summary

- **Standards:** 6 findings (worst: `base_walker.py` naming/docstring violating domain standard against "walker base class").
- **Spec:** 5 findings (worst: `ReturnStatement` unconditionally intercepting `return requestAnimationFrame(loop);` and bypassing cycle creation).
