# Code Review: Tickets 07–10 (Round 6) — with Suggestions

Reviewing diff between `f41d6ba` and `HEAD` (`3405b81`).

---

## Standards

### Documented Standard Violations (Hard)

1. **Walker Protocol (`CONTEXT.md: _Avoid_: Parser interface, walker base class`)**
   - **[`code2petri/walker_protocol.py:L8`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/walker_protocol.py#L8)**:
     ```python
     """Protocol interface establishing the contract for language-specific AST walkers."""
     ```
     Breaches the standard by introducing forbidden "interface" terminology (`"Protocol interface"`).
     - **Suggestion**: Replace `"Protocol interface"` with `"Walker protocol"`, e.g.:
       ```python
       """Walker protocol establishing the contract for language-specific AST walkers."""
       ```
   - **[`.scratch/code2petri/issues/07-prefactor-walker-protocol.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/07-prefactor-walker-protocol.md)** & **[`08-js-walker-skeleton.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/08-js-walker-skeleton.md)**:
     ```markdown
     - [x] PythonWalker inherits from the new ABC and base class.
     - [x] JavascriptWalker class is implemented, inheriting from the ABC and _BaseControlFlowWalker.
     ```
     Directly prescribes and documents prohibited walker base class inheritance in historical ticket specs.
     - **Suggestion**: Update both issue checklists to state:
       ```markdown
       - [x] PythonWalker implements WalkerProtocol and composes ControlFlowBuilder.
       - [x] JavascriptWalker class is implemented, implementing WalkerProtocol and composing ControlFlowBuilder.
       ```

### Baseline Smells (Judgement Calls)

1. **Feature Envy & Message Chains ([`code2petri/python_walker.py:L164`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/python_walker.py#L164), [`code2petri/javascript_walker.py:L418`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L418))**
   Walkers bypass builder encapsulation, reaching through `self.builder.net` and mutating stacks directly:
   ```python
   self.builder.net.add_arc(source=current_place, target=true_trans)
   self.builder.try_stack.append(TryContext(...))
   ```
   - **Suggestion**: Add delegating helper methods onto `ControlFlowBuilder`:
     ```python
     def add_arc(self, source: Union[Place, Transition], target: Union[Place, Transition]) -> Arc:
         return self.net.add_arc(source=source, target=target)

     def push_try(self, try_context: TryContext) -> None:
         self.try_stack.append(try_context)

     def pop_try(self) -> Optional[TryContext]:
         return self.try_stack.pop() if self.try_stack else None
     ```

2. **Data Clumps ([`code2petri/javascript_walker.py:L407-413`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L407-413))**
   `current_place`, `is_last`, `target_exit`, and `lineno` travel together across 11 handler signatures:
   ```python
   def _walk_if(self, stmt: dict, current_place: Place, is_last: bool, target_exit: Place, lineno: Optional[int]) -> Optional[Place]:
   ```
   - **Suggestion**: Bundle them into a lightweight dataclass or NamedTuple:
     ```python
     @dataclass(frozen=True)
     class StatementContext:
         current_place: Place
         is_last: bool
         target_exit: Place
         lineno: Optional[int] = None
     ```

3. **Duplicated Code ([`code2petri/python_walker.py:L326-331`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/python_walker.py#L326-331) vs [`code2petri/javascript_walker.py:L686-691`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L686-691))**
   Both walkers duplicate identical sequential statement chaining:
   ```python
   next_place = target_exit if is_last else self.builder.new_place(line_number=lineno)
   trans = self.builder.new_transition(label=label, line_number=lineno)
   self.builder.net.add_arc(source=current_place, target=trans)
   self.builder.net.add_arc(source=trans, target=next_place)
   ```
   - **Suggestion**: Move sequential statement wiring onto `ControlFlowBuilder`:
     ```python
     def wire_sequential_statement(
         self,
         current_place: Place,
         label: str,
         lineno: Optional[int],
         is_last: bool,
         target_exit: Place,
     ) -> Place:
         next_place = target_exit if is_last else self.new_place(line_number=lineno)
         trans = self.new_transition(label=label, line_number=lineno)
         self.net.add_arc(source=current_place, target=trans)
         self.net.add_arc(source=trans, target=next_place)
         return next_place
     ```

4. **Repeated Switches ([`code2petri/python_walker.py:L72-108`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/python_walker.py#L72-108), [`L145-325`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/python_walker.py#L145-325))**
   The same AST statement cascade repeats in `_format_statement_label` and `walk_block`:
   ```python
   if isinstance(stmt, ast.Return): ...
   elif isinstance(stmt, ast.If): ...
   elif isinstance(stmt, (ast.While, ast.For, ast.AsyncFor)): ...
   ```
   - **Suggestion**: Implement a handler dictionary in `PythonWalker` (matching `JavascriptWalker`):
     ```python
     self._statement_handlers = {
         ast.If: self._walk_if,
         ast.While: self._walk_loop,
         ast.For: self._walk_loop,
         ast.AsyncFor: self._walk_loop,
         ast.Return: self._walk_return,
         ast.Raise: self._walk_raise,
         ast.Try: self._walk_try,
     }
     ```

5. **Speculative Generality ([`code2petri/control_flow_builder.py:L194-196`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/control_flow_builder.py#L194-196))**
   ```python
   if not self.try_stack:
       target = self.get_active_finally() or self.end_place
   ```
   Dead branch: `get_active_finally()` unconditionally returns `None` if `try_stack` is empty.
   - **Suggestion**: Simplify to:
     ```python
     if not self.try_stack:
         target = self.end_place
     ```

---

## Spec

### (a) Missing or Partial Requirements

- **Walker Base Class Inheritance vs. Composition:**
  - **Spec quote (`phase-1-js-walker.md:21`):** *"11. As a developer, I want common Petri net construction logic (counters, loop stacks, try stacks) to be shared in a base class, so that language-specific walkers only deal with AST traversal."*
  - **Issue 07 quote (`07-prefactor-walker-protocol.md:11`):** *"`PythonWalker` inherits from the new ABC and base class."*
  - **Issue 08 quote (`08-js-walker-skeleton.md:9`):** *"`JavascriptWalker` class is implemented, inheriting from the ABC and `_BaseControlFlowWalker`."*
  - **Finding:** Neither `PythonWalker` nor `JavascriptWalker` inherits from a base class; both compose `ControlFlowBuilder`.
  - **Suggestion**: Update the leftover documentation in `phase-1-js-walker.md` (User Story 11) and `08-js-walker-skeleton.md`:
    - In `phase-1-js-walker.md`:
      ```markdown
      11. As a developer, I want common Petri net construction logic (counters, loop stacks, try stacks) to be encapsulated in a shared builder class (`ControlFlowBuilder`), so that language-specific walkers can compose it and focus purely on AST traversal.
      ```
    - In `08-js-walker-skeleton.md`:
      ```markdown
      - [x] `JavascriptWalker` class is implemented, adhering to `WalkerProtocol` and composing `ControlFlowBuilder`.
      ```

### (b) Scope Creep (Behaviour Not Asked For)

- **Extra Abstract Method on `WalkerProtocol` (`get_node_lineno`):**
  - **Spec quote (`07-prefactor-walker-protocol.md:9`):** *"`WalkerProtocol` is defined as an `abc.ABC` with `parse_file`, `find_function`, `find_all_functions`, and `walk_function` instance methods."*
  - **Finding:** `WalkerProtocol` defines a fifth abstract method: `get_node_lineno(self, ast_node: Any) -> int` (`code2petri/walker_protocol.py:31-33`).
  - **Suggestion**: Keep `get_node_lineno` because it legitimately eliminates Feature Envy in `engine.py` (preventing `engine.py` from inspecting language-specific AST structures). Retrofit the spec by adding `get_node_lineno` to the list of `WalkerProtocol` methods in `07-prefactor-walker-protocol.md` and `phase-1-js-walker.md`.

### (c) Implemented But Wrong

- **None.** All control-flow mechanics and language semantics are verified with 85 passing tests.

---

## Executive Action Plan

If you want to reach 100% clean across both axes, here are the 4 recommended quick actions:

1. **Fix vocabulary in code**: In [`code2petri/walker_protocol.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/walker_protocol.py#L8), change `"Protocol interface"` to `"Walker protocol"`.
2. **Align leftover spec docs**: In [`phase-1-js-walker.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/specs/phase-1-js-walker.md) and [`08-js-walker-skeleton.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/08-js-walker-skeleton.md), update User Story 11 and Issue 08 checklist item from "base class / inherits" to "ControlFlowBuilder / composes", and document `get_node_lineno`.
3. **Dead branch cleanup**: In [`code2petri/control_flow_builder.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/control_flow_builder.py#L194-L196), change `target = self.get_active_finally() or self.end_place` to `target = self.end_place` when `not self.try_stack`.
4. **Encapsulate builder arcs**: Add `add_arc` method to [`ControlFlowBuilder`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/control_flow_builder.py) so walkers don't reach into `self.builder.net.add_arc`.
