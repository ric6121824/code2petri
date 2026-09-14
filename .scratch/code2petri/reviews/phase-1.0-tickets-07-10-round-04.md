## Standards

### Documented Standard Violations (Hard Violations)

**Walker Protocol** (`code2petri/base_walker.py`)
The rule dictates: "_Avoid_: Parser interface, walker base class". However, the diff introduces `class _BaseControlFlowWalker` as a base class that both `PythonWalker` and `JavascriptWalker` inherit from, violating the explicit ban on walker base classes. *(Note: Code inspection shows this inheritance may have been refactored out in the latest fix commit `1acdf37`, but the subagent flagged its presence in the overall diff).*

**Faithful Translation** (`code2petri/javascript_walker.py`)
The rule demands "modeling the exact control flow present in the source AST... without attempting to sanitize". In `walk_block`, the use of `_is_raf_cycle_call` intercepts asynchronous `requestAnimationFrame` calls and semantically alters them into synchronous back-arc cycles in the Petri net. This normalizes game loops at the expense of representing the exact source AST control flow.

---

### Baseline Smells (Judgement Calls)

**Middle Man** (`code2petri/python_walker.py`)
The top-level module functions now merely instantiate and delegate to `PythonWalker`, adding an unnecessary layer of indirection.
```python
def walk_function(ast_node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> PetriNet:
    """Walks a Python function definition AST and constructs a PetriNet model."""
    return PythonWalker().walk_function(ast_node)
```

**Duplicated Code** (`code2petri/python_walker.py` & `code2petri/javascript_walker.py`)
Both walkers duplicate the exact same structural logic block for handling terminal exceptions within their respective `walk_block` methods.
```python
            elif isinstance(stmt, ast.Raise):  # Or stmt_type == "ThrowStatement" in JS
                self._wire_terminal_exception(
                    current_place=current_place,
                    label=_format_statement_label(stmt),
                    line_number=stmt.lineno,
                )
                return None
```

**Repeated Switches** (`code2petri/javascript_walker.py`)
The codebase repeatedly branches on the exact same AST node type (`stmt_type`). It switches once via a massive `if / elif` cascade in `walk_block`, and again via the `_statement_formatters` dictionary mapping in `__init__`.

**Data Clumps** (`code2petri/base_walker.py`)
The `_wire_standard_loop` method accepts a clump of tightly bound Petri net routing parameters (`loop_head`, `loop_trans`, `exit_trans`, `loop_exit`) that always travel together during loop construction and cry out for a dedicated type.
```python
    def _wire_standard_loop(
        self,
        loop_head: Place,
        loop_trans: Transition,
        exit_trans: Transition,
        loop_exit: Place,
        body_stmts: Any,
        lineno: Optional[int] = None,
    ) -> None:
```

## Spec

**(a) Missing or partial requirements**
- **Label Slicing:** The spec states that *"JavaScript transition labels will be created by slicing the raw source string using Acorn's start and end byte offsets, rather than attempting to unparse the AST."* However, for `if`, `while`, `do...while`, and `switch`, the walker manually reconstructs the statement strings (e.g., by prepending `"if ("` to the sliced test condition) rather than slicing the entire source text up to the block body.
- **Finally Block Bypass:** The spec asks that *"`try / catch / finally` statements are modeled with exception-arcs and standard try-exit logic."* However, if a `return`, `break`, or `continue` statement occurs inside a `try` or `catch` block, the walker wires it to jump directly to the loop exit or function termination, entirely bypassing the `finally` block.

**(b) Scope creep (behavior not asked for)**
- **Game-Loop `.bind()` unwrapping:** The spec states that *"game-loop cycle detection is narrowly restricted to requestAnimationFrame where the argument matches the enclosing function name."* The implementation in `_is_raf_cycle_call` introduces specialized AST unwrapping logic for `.bind(...)` expressions (e.g., `this.step.bind(this)`), which was not requested.

**(c) Implemented but wrong**
- **Switch Fallthrough:** The spec mandates that *"`switch / case / default` is modeled as an XOR-split"*. While the XOR-split decision tree is present, the walker routes every individual `case_body` directly to `switch_exit`. This incorrectly breaks JavaScript's `switch` semantics, as execution must fall through to the subsequent case block if no `break` is encountered.

---

**Summary**
- Standards: 2 Hard Violations, 4 Smells. Worst issue: Faithful Translation violation with `requestAnimationFrame` rewriting the AST structure.
- Spec: 4 Findings. Worst issue: Switch Fallthrough breaking JS execution semantics.
