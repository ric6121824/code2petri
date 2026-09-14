# Code Review: Tickets 07–10 (Round 7) — with Suggestions

Reviewing diff between `f41d6ba` and `HEAD` (`acceb27`).

---

## Standards

### Documented Standards Violations (Hard Violations)
**None (0 Hard Violations)**.
The diff strictly complies with [CONTEXT.md](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md):
- **Walker Protocol**: Defined as an `abc.ABC` and implemented via composition with `ControlFlowBuilder`.
- **Global Scope & Synthetic Wrapper**: Properly named and wrapped without forbidden terminology.
- **Faithful Translation**: Exact control flow accurately modeled.

---

### Baseline Smells (Judgement Calls)

1. **Duplicated Code** ([`code2petri/python_walker.py:L180-L202`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/python_walker.py#L180-L202) & [`code2petri/javascript_walker.py:L414-L437`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L414-L437))
   - **Issue**: Both walkers duplicate identical structural logic for wiring if-splits/merges and try-blocks instead of delegating to `ControlFlowBuilder`.
   - **Suggestion**: Extract `wire_if_split` and `wire_try_catch` helper methods onto [`ControlFlowBuilder`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/control_flow_builder.py). Let the builder orchestrate the branches using its existing `walk_branch` method and handle the creation of the `merge_place`.

2. **Feature Envy** ([`code2petri/javascript_walker.py:L546`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L546) & [`code2petri/python_walker.py:L241`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/python_walker.py#L241))
   - **Issue**: Walkers directly reach into `builder`'s internal data structures (`loop_stack` and `net.arcs`).
   - **Suggestion**: Add proper encapsulating helpers on `ControlFlowBuilder`:
     ```python
     def push_loop(self, head: Optional[Place], exit: Place) -> None:
         self.loop_stack.append(LoopContext(head=head, exit=exit))

     def pop_loop(self) -> Optional[LoopContext]:
         return self.loop_stack.pop() if self.loop_stack else None

     def has_incoming_arcs(self, node: Union[Place, Transition]) -> bool:
         return any(arc.target == node for arc in self.net.arcs)
     ```

3. **Primitive Obsession** ([`code2petri/javascript_walker.py:L705-706`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L705-L706)) & **Speculative Generality** ([`code2petri/javascript_walker.py:L867`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L867))
   - **Issue**: `JavascriptWalker` keys a dictionary cache by transient object memory addresses (`id(node)`) just to remember the names of functions. It also diverges from the `WalkerProtocol` by adding a `func_name` parameter to `walk_function`.
   - **Suggestion**: These two smells solve each other! Update [`WalkerProtocol`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/walker_protocol.py) to formally require the name: `def walk_function(self, ast_node: Any, func_name: str) -> PetriNet`. Then, update [`engine.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/engine.py) to pass the `target_function` string it already holds. This completely eliminates the need for the `id(node)` cache in `JavascriptWalker`.

4. **Message Chains** ([`code2petri/javascript_walker.py:L47-L52`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L47-L52))
   - **Issue**: Deep, manual dictionary navigation chains (`node.get("loc").get("start").get("line")`).
   - **Suggestion**: Add a single `get_nested` utility helper:
     ```python
     def get_nested(d: dict, *keys: str, default: Any = None) -> Any:
         curr = d
         for k in keys:
             if not isinstance(curr, dict):
                 return default
             curr = curr.get(k)
         return curr if curr is not None else default
     ```

---

## Spec

### (a) Missing or Partial Requirements
**None.** All requirements across Tickets 07–10 and `phase-1-js-walker.md` are fully satisfied.

### (b) Scope Creep (Behaviour Not Asked For)
- **Top-level `(global)` support added to PythonWalker:**
  - **Issue**: Synthetic `(global)` wrapper execution was specified strictly as a JavaScript feature for Acorn ASTs in Ticket 08. The diff implements identical top-level executable statement harvesting in `PythonWalker`.
  - **Suggestion**: Keep it. Parity across languages for top-level code is an architectural improvement. Document this intentional proactive parity in `phase-1-js-walker.md` to formally close the gap.

### (c) Implemented But Wrong
**None (0 defects)**. All control flow mechanics, Petri net transformations, and edge cases are correctly wired and verified by 165 passing unit and integration tests.

---

**Summary:**
- **Standards**: **0 Hard Violations**, 4 Baseline Smells (Duplicated Code, Feature Envy, Primitive Obsession + Speculative Generality, Message Chains).
- **Spec**: **0 Missing Requirements**, 1 benign Scope Creep (`(global)` in PythonWalker), **0 Logic Defects**.
