# Code Review: Tickets 07–10 (Phase 1 — Walker Protocol & JavaScript Support)

**Review Target:** Changes between commit `f41d6ba` and `HEAD` (`a7d9ad2`) covering Tickets 07–10:
- `e87b993` feat(code2petri): implement WalkerProtocol and shared base walker infrastructure (ticket 07)
- `d8ca94c` refactor(code2petri): address code-review findings on qualification and exports (ticket 07)
- `7d62b7a` feat(code2petri): implement JavaScript walker skeleton and sequential statements (ticket 08)
- `29c7369` refactor(code2petri): address code-review findings on JS walker (ticket 08)
- `fbecfac` feat(code2petri): implement JavaScript core control flow constructs (ticket 09)
- `a2fc9bc` refactor(code2petri): address code-review findings on JS core control flow (ticket 09)
- `d186bb1` feat(code2petri): implement JavaScript specifics and game-loop translation (ticket 10)
- `a7d9ad2` refactor(code2petri): address code-review findings on Ticket 10

> [!NOTE]
> A subsequent re-review following fix commit `d72e78f` is available at [tickets-07-10-round-2.md](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/reviews/tickets-07-10-round-2.md).

---

## Standards

### Standards Violations (Hard)

1. **[CONTEXT.md](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) — Walker Protocol** (`_Avoid_: Parser interface, walker base class`):
   - **File**: [`code2petri/base_walker.py#L20`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/base_walker.py#L20), [`code2petri/__init__.py#L4`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/__init__.py#L4)
   - **Breach**: Introduces and exports `BaseControlFlowWalker` / `_BaseControlFlowWalker` in `base_walker.py` as a shared walker base class, conflicting with the domain vocabulary rule favoring `WalkerProtocol` over "walker base class".

2. **[CONTEXT.md](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) — Global Scope** (`addressable in the CLI as (global)`):
   - **File**: [`code2petri/python_walker.py#L43-L62`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/python_walker.py#L43-L62)
   - **Breach**: While `JavascriptWalker` supports `(global)`, `PythonWalker` omits top-level script scope discovery in `find_all_functions` and `find_function`, violating the requirement that global-scope top-level code be addressable as `(global)`.

3. **[CONTEXT.md](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) — Faithful Translation** (`_Avoid_: Normalization, cleanup`):
   - **File**: [`code2petri/javascript_walker.py#L16`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L16)
   - **Breach**: Docstring explicitly uses prohibited vocabulary: `"""Normalizes an AST node or list into a list of statement dicts."""`.

---

### Baseline Smells (Judgement Calls)

1. **Middle Man**:
   - **File**: [`code2petri/python_walker.py#L375-L398`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/python_walker.py#L375-L398)
   - **Quote**:
     ```python
     class PythonWalker(WalkerProtocol):
         def parse_file(self, filepath: str) -> ast.AST: return parse_file(filepath)
         def find_function(self, tree, func_name): return find_function(tree, func_name)
         def find_all_functions(self, tree): return find_all_functions(tree)
         def walk_function(self, ast_node): return walk_function(ast_node)
     ```
   - All instance methods purely delegate onward to module-level functions of identical names.

2. **Repeated Switches**:
   - **File**: [`code2petri/javascript_walker.py#L91-L186`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L91-L186), [`code2petri/javascript_walker.py#L299-L533`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L299-L533)
   - **Quote**:
     ```python
     stmt_type = stmt.get("type")
     if stmt_type == "ReturnStatement": ...
     elif stmt_type in ("BreakStatement", "ContinueStatement"): ...
     elif stmt_type == "IfStatement": ...
     ```
   - Multiple parallel `if/elif` cascades on `stmt_type` across `_format_statement_label`, `walk_block`, and `_find_raf_call` instead of dictionary or polymorphic dispatch.

3. **Duplicated Code**:
   - **File**: [`code2petri/javascript_walker.py#L187-L201`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L187-L201) vs [`code2petri/base_walker.py#L66-L76`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/base_walker.py#L66-L76)
   - `_walk_branch` duplicates `_BaseControlFlowWalker._walk_branch` arc wiring instead of reusing or invoking `super()`.

4. **Message Chains**:
   - **File**: [`code2petri/javascript_walker.py#L30`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L30), [`code2petri/javascript_walker.py#L616`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L616)
   - Deep nested dict navigation: `elem.get("loc", {}).get("start", {}).get("line")` and `stmts[0]["loc"]["start"].get("line", default)`.

5. **Speculative Generality**:
   - **File**: [`code2petri/base_walker.py#L16-L17`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/base_walker.py#L16-L17), [`code2petri/base_walker.py#L88`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/base_walker.py#L88)
   - Redundant aliases: `_LoopContext = LoopContext`, `_TryContext = TryContext`, and `BaseControlFlowWalker = _BaseControlFlowWalker`.

---

## Spec

### (a) Missing or Partial Requirements

1. **Missing TODO Marker for Game Loops**:
   - **Spec quote**: *"A TODO marker will be left for extending this to `setTimeout` or `setInterval`."* ([phase-1-js-walker.md#L30](file:///.scratch/code2petri/specs/phase-1-js-walker.md#L30))
   - **Finding**: While cycle detection was added for `requestAnimationFrame`, no `TODO` comment was added in [`code2petri/javascript_walker.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py) or anywhere in the diff for extending detection to `setTimeout` or `setInterval`.

2. **Partial Qualification for Scoped JS Classes**:
   - **Spec quote**: *"Class methods will use qualified names (`ClassName.methodName`) across both Python and JS."* ([phase-1-js-walker.md#L32](file:///.scratch/code2petri/specs/phase-1-js-walker.md#L32))
   - **Finding**: In [`javascript_walker.py#L620`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L620), method qualification hardcodes `f"{cls_name}.{key}"` without prepending outer `scope`. If a class is declared inside an outer function, outer scope qualifiers are dropped, unlike `python_walker.py` which preserves the full enclosing scope stack.

### (b) Scope Creep (Unrequested Behaviour)

1. **Automatic ES Module Fallback**:
   - **Spec quote**: *"Support for complex ES modules (`source_type="module"`) that fail standard script parsing. Auto-detection is planned, but full module resolution is out of scope for Phase 1."* ([phase-1-js-walker.md#L49](file:///.scratch/code2petri/specs/phase-1-js-walker.md#L49))
   - **Finding**: [`javascript_walker.py#L578-L580`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L578-L580) catches `AssertionError` and automatically falls back to re-parsing with `LanguageParams(source_type="module")`, implementing auto-detection explicitly marked out of scope for Phase 1.

2. **Unrequested Registration of `.mjs` Extension**:
   - **Spec quote**: *"`engine.py` correctly routes `.js` files to `JavascriptWalker`."* ([08-js-walker-skeleton.md#L10](file:///.scratch/code2petri/issues/08-js-walker-skeleton.md#L10))
   - **Finding**: [`code2petri/engine.py#L14`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/engine.py#L14) adds `".mjs": JavascriptWalker` to `WALKERS`, which was not requested in the spec user stories or issue tickets.

### (c) Incorrect Implementation

1. **`requestAnimationFrame` Drops Trailing Statements**:
   - **Spec quote**: *"As a user, I want a `requestAnimationFrame(loop)` call to be translated into a back-arc cycle in the Petri net, so that standard game-loop recursion is accurately modeled."* ([phase-1-js-walker.md#L17](file:///.scratch/code2petri/specs/phase-1-js-walker.md#L17))
   - **Finding**: In [`javascript_walker.py#L533-L541`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L533-L541), encountering an enclosing RAF call connects to `start_place` and executes `return None`. Because RAF is an asynchronous callback registration rather than a terminating jump/return, returning `None` terminates `walk_block` prematurely and drops any subsequent statements in the enclosing block.

2. **Divergent Exception Modeling (`throw` vs. `raise`)**:
   - **Spec quote**: *"`throw` statements are modeled identically to Python `raise` exceptions."* ([10-js-specifics-and-game-loop.md#L11](file:///.scratch/code2petri/issues/10-js-specifics-and-game-loop.md#L11))
   - **Finding**: [`javascript_walker.py#L522-L531`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L522-L531) routes unhandled `throw` statements to `end_place` and terminates block traversal. In contrast, `python_walker.py` has no `ast.Raise` handler; Python raises fall through to sequential statement handling without connecting to `end_place` or terminating traversal.

---

## Summary

- **Standards:** 8 findings (worst: `PythonWalker` missing `(global)` scope discovery mandated by `CONTEXT.md`).
- **Spec:** 6 findings (worst: `requestAnimationFrame` returning `None` and prematurely terminating block traversal, dropping trailing statements).
