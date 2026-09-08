## Standards

### Documented Standard Violations

**File: `code2petri/walker_protocol.py`**
- **Hard Violation (Walker Protocol)**: The class docstring (`"Abstract base class establishing the contract..."`) directly breaches the rule from `CONTEXT.md`: _Avoid: walker base class_.

**File: `code2petri/base_walker.py`**
- **Hard Violation (Walker Protocol)**: The filename itself (`base_walker.py`) and the explicit alias `_BaseControlFlowWalker = ControlFlowBuilder` breach the rule from `CONTEXT.md`: _Avoid: walker base class_.

**File: `tests/test_walker_protocol.py`**
- **Hard Violation (Walker Protocol)**: The test class `TestBaseControlFlowWalker` uses the forbidden terminology, perpetuating the "walker base class" naming in the test suite.

### Baseline Smells

**File: `code2petri/base_walker.py`**
- **Mysterious Name (Judgement Call)**: Keeping the `_BaseControlFlowWalker` alias alive obscures the design. If `ControlFlowBuilder` is the honest name for this component, the alias makes the codebase murky and should be dropped.

**Files: `code2petri/python_walker.py` & `code2petri/javascript_walker.py`**
- **Middle Man (Judgement Call)**: `_PythonControlFlowWalker` and `_JavascriptControlFlowWalker` both define `new_place`, `new_transition`, and `_walk_branch` that merely delegate onward:
  ```python
  def new_place(self, label, line_number):
      return self.builder.new_place(label=label, line_number=line_number)
  ```
  These should be cut, and the real target (`self.builder`) called directly.
- **Duplicated Code (Judgement Call)**: The exact same delegation boilerplate shapes for `new_place`, `new_transition`, and `_walk_branch` are duplicated across both language walker files.

**File: `code2petri/javascript_walker.py`**
- **Message Chains (Judgement Call)**: In `_collect_all_functions`, there are deep dictionary navigations like `node.get("id", {}).get("name", "(anonymous_class)")` and `node.get("body", {}).get("body", [])`. The walker shouldn't depend on navigating this deeply manually in one line; extracting a small AST helper would hide the walk.


## Spec

The implementation of the JavaScript walker and shared infrastructure successfully resolves all major logic flaws flagged in previous reviews, including Switch fallthrough, Try/Finally block bypasses, and Transition label string slicing. However, some structural requirements from the spec remain unfulfilled.

### (a) Missing or partial requirements

- **Shared Infrastructure Inheritance:** The spec explicitly states: *"Language-specific walkers will inherit from this [`_BaseControlFlowWalker`] and override only the AST dispatch logic."* 
  In the diff, neither `PythonWalker` nor `JavascriptWalker` inherit from `_BaseControlFlowWalker`. Instead, they instantiate a `ControlFlowBuilder` class internally via composition. While this was likely done to comply with the project's coding standard that bans walker base classes (as noted in the Round 4 review), it remains a direct violation of the spec's architectural mandate.
- **Game-Loop TODO Marker:** The spec explicitly states: *"A TODO marker will be left for extending this to setTimeout or setInterval."* 
  No such TODO comment exists in `javascript_walker.py` around the `requestAnimationFrame` game-loop cycle logic (`_is_raf_cycle_call`).

### (b) Scope creep (behaviour not asked for)

- **None remaining.** The previously flagged scope creep (AST unwrapping for `.bind(...)` inside game loops) was successfully stripped out in the fix commit. The introduction of `ControlFlowBuilder` represents a deviation in architecture (composition instead of inheritance), rather than extraneous behavior.

### (c) Implemented but wrong

- **None remaining.** All major logic errors identified in the previous code review have been accurately fixed. The transition labels are correctly sliced from `raw_source`, `_walk_switch` now correctly routes fallthrough executions, and `_walk_try` correctly routes `break`/`continue`/`return` statements through the active `finally` blocks via `self.builder.get_active_finally()`.

---

**Summary**
- Standards: 3 Hard Violations, 4 Smells. Worst issue: Lingering "base walker" terminology in filenames and test classes.
- Spec: 2 Findings. Worst issue: Intentional deviation from the spec's inheritance mandate to comply with repo standards.
