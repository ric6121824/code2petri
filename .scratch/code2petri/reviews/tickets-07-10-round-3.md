# Code Review: Tickets 07–10 (Phase 1 — Round 3 Re-Review)

**Review Target:** Changes between commit `f41d6ba` and `HEAD` (`59d4643`), re-evaluating the full feature set following fix commit `59d4643`:
- `59d4643` fix(code2petri): resolve round 2 code review issues for tickets 07-10
- `d72e78f` fix(code2petri): resolve issues identified in code review for tickets 07-10
- `a7d9ad2` refactor(code2petri): address code-review findings on Ticket 10
- `d186bb1` feat(code2petri): implement JavaScript specifics and game-loop translation (ticket 10)
- `a2fc9bc` refactor(code2petri): address code-review findings on JS core control flow (ticket 09)
- `fbecfac` feat(code2petri): implement JavaScript core control flow constructs (ticket 09)
- `29c7369` refactor(code2petri): address code-review findings on JS walker (ticket 08)
- `7d62b7a` feat(code2petri): implement JavaScript walker skeleton and sequential statements (ticket 08)
- `d8ca94c` refactor(code2petri): address code-review findings on qualification and exports (ticket 07)
- `e87b993` feat(code2petri): implement WalkerProtocol and shared base walker infrastructure (ticket 07)

*Previous review reports:*
- Round 1: [tickets-07-10.md](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/reviews/tickets-07-10.md)
- Round 2: [tickets-07-10-round-2.md](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/reviews/tickets-07-10-round-2.md)

---

## Status of Previous Findings

| Finding from Round 2 | Status in Round 3 | Resolution Note |
|---|---|---|
| `ReturnStatement` shadowing `requestAnimationFrame` cycle calls | **Resolved** | Sliced and checked `_is_raf_cycle_call` before standard return handling in `javascript_walker.py:L309` |
| JavaScript AST node line number logging in `engine.py` | **Resolved** | Added dict loc extraction (`loc["start"]["line"]`) in `engine.py:L99-L106` |
| Suffix matching in `find_function` (scope creep) | **Resolved** | Suffix match removed; only qualified, bare, and anonymous matches retained in `javascript_walker.py:L724-L745` |
| Subclassing `_BaseControlFlowWalker` vs `WalkerProtocol` | **Partial** | Inherited from `_BaseControlFlowWalker`, but internal delegation persists |
| Shared loop wiring duplication | **Resolved** | Extracted `_wire_standard_loop()` helper in `base_walker.py:L78` |
| `_FuncItem` Primitive Obsession in `javascript_walker.py` | **Resolved** | Refactored discovered function items to `FunctionInfo` NamedTuple |

---

## Standards

### Standards Violations (Hard)

1. **[CONTEXT.md](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) (Walker Protocol — *Avoid: walker base class*)**:
   - **Files**: [`code2petri/base_walker.py#L16`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/base_walker.py#L16), [`code2petri/python_walker.py#L339`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/python_walker.py#L339), [`code2petri/javascript_walker.py#L577`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L577)
   - **Breach**: The documented standard mandates that language parsers implement `WalkerProtocol` (`abc.ABC`) and explicitly specifies: `Avoid: Parser interface, walker base class`. Introducing `_BaseControlFlowWalker` and having `PythonWalker` and `JavascriptWalker` inherit from it (`class PythonWalker(WalkerProtocol, _BaseControlFlowWalker):`) violates this rule by imposing a base class inheritance hierarchy instead of relying purely on the protocol.

---

### Baseline Smells (Judgement Calls)

1. **Refused Bequest**:
   - **Files**: [`code2petri/python_walker.py#L339-L346`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/python_walker.py#L339-L346) & [`code2petri/javascript_walker.py#L577-L585`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L577-L585)
   - **Quote**:
     ```python
     class PythonWalker(WalkerProtocol, _BaseControlFlowWalker):
         def __init__(self, net=None, end_place=None):
             super().__init__(net=net, end_place=end_place)
     ```
   - Both `PythonWalker` and `JavascriptWalker` subclass `_BaseControlFlowWalker`, but neither implements `walk_block` (leaving it to raise `NotImplementedError`) nor uses inherited helpers (`new_place`, `_wire_standard_loop`). Instead, `walk_function` instantiates a distinct internal walker (`_PythonControlFlowWalker` / `_JavascriptControlFlowWalker`) and delegates to it, ignoring inherited behavior.

2. **Feature Envy & Message Chains**:
   - **File**: [`code2petri/engine.py#L99-L106`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/engine.py#L99-L106)
   - **Quote**:
     ```python
     if isinstance(func_node, dict):
         loc = func_node.get("loc")
         if isinstance(loc, dict) and isinstance(loc.get("start"), dict):
             lineno = loc["start"].get("line", 0)
         else:
             lineno = func_node.get("lineno", 0)
     else:
         lineno = getattr(func_node, "lineno", 0)
     ```
   - `code2petri` envies language-specific AST structures. It inspects dictionary vs object AST representations and navigates a message chain (`loc["start"].get("line", 0)`) to extract line numbers, rather than asking the walker to provide node metadata or having the protocol expose a uniform helper.

3. **Duplicated Code**:
   - **Files**: [`code2petri/python_walker.py#L314-L323`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/python_walker.py#L314-L323) & [`code2petri/javascript_walker.py#L551-L560`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L551-L560)
   - **Quote**:
     ```python
     label = self._format_statement_label(stmt)
     trans = self.new_transition(label=label, line_number=lineno)
     self.net.add_arc(source=current_place, target=trans)
     if not self.try_stack:
         self.net.add_arc(source=trans, target=self.end_place)
     return None
     ```
   - Terminal exception routing (`ast.Raise` vs `ThrowStatement`) duplicates identical arc topology logic across Python and JavaScript walkers instead of sharing a helper.

---

## Spec

### (a) Missing or Partial Requirements

1. **Walker Base Class Inheritance Contract**:
   - **Spec Quote**: *"Shared Infrastructure: A shared internal base class (`_BaseControlFlowWalker`) will provide the counters, loop stacks, try stacks, and helper methods. Language-specific walkers will inherit from this and override only the AST dispatch logic."* ([phase-1-js-walker.md#L27](file:///.scratch/code2petri/specs/phase-1-js-walker.md#L27))
   - **Finding**: In [`python_walker.py#L339`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/python_walker.py#L339) and [`javascript_walker.py#L577`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L577), `PythonWalker` and `JavascriptWalker` inherit `_BaseControlFlowWalker` nominally to satisfy `issubclass()` checks, but neither implements `walk_block` (calling it raises `NotImplementedError`). AST traversal and net construction remain delegated to separate inner classes (`_PythonControlFlowWalker` and `_JavascriptControlFlowWalker`), leaving base walker state on the public classes unused.

### (b) Scope Creep (Unrequested Behaviour)

- **None**: All previous scope creep identified in Rounds 1 and 2—automatic ES module fallback (`source_type="module"`), registration of `.mjs` in `WALKERS`, and fuzzy suffix matching (`qual_name.endswith(f".{func_name}")`)—has been completely removed as of commit `59d4643`. All remaining constructs and helper methods match the spec tickets.

### (c) Incorrect Implementation

1. **`requestAnimationFrame` Cycle Detection on Method References**:
   - **Spec Quote**: *"Game-Loop Cycles: For now, game-loop cycle detection is narrowly restricted to `requestAnimationFrame` where the argument matches the enclosing function name."* ([phase-1-js-walker.md#L30](file:///.scratch/code2petri/specs/phase-1-js-walker.md#L30))
   - **Finding**: In [`javascript_walker.py#L291-L293`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L291-L293), `_is_raf_cycle_call` slices non-identifier arguments into raw strings (e.g., `"this.step"`) and checks `arg_name in (self.func_name, bare_func_name)`. When analyzing a class method (`WebGLEngine.step`), recursive calls written as `requestAnimationFrame(this.step)` fail matching against `("WebGLEngine.step", "step")` because `arg_name` is `"this.step"`, failing to generate the back-arc cycle.

---

## Summary

- **Standards:** 4 findings (worst: `PythonWalker` and `JavascriptWalker` subclassing `_BaseControlFlowWalker`, in direct conflict with `CONTEXT.md`'s rule to *Avoid: walker base class*).
- **Spec:** 2 findings (worst: `requestAnimationFrame` cycle detection failing on method member expressions like `this.step`).
