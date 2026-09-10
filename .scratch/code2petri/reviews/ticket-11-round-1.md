# Code Review: Ticket 11 (Round 1) — with Suggestions

Reviewing diff between `0de953e` and `HEAD` (`2046f3d`): `feat(code2petri): implement WalkResult protocol return type and transition metadata (ticket 11)`.

---

## Standards

### (a) Documented Repo Standards (`CONTEXT.md`)
- **Hard Violations: None (0 Hard Violations).**
  The diff strictly adheres to the domain vocabulary and architecture:
  - **Walker Protocol**: Implemented via `WalkerProtocol(ABC)` with instance methods and proper abstract annotations, avoiding prohibited terms (*parser interface*, *walker base class*).
  - **Call Site**: Defined as [`CallSite`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/walker_protocol.py#L8-L16) dataclass with the exact domain attributes (`caller_function`, `caller_file`, `callee_name`, `callee_owner`, `line_number`, `transition_id`), avoiding deprecated terms (*call point*, *call transition info*).
  - **Variable Binding**: Introduced `collect_variable_bindings` matching the domain vocabulary, avoiding *type inference* or *symbol alias*.

---

### (b) Baseline Smells (Judgement Calls) & Suggestions

1. **Primitive Obsession & Data Clumps** ([`code2petri/model.py:47-82`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/model.py#L47-L82))
   - **Finding**: Resolution metadata attributes (`resolved`, `resolved_to`, `target_file`) travel together as loose dictionary keys within an untyped `Dict[str, Any]` across `to_dict`, `to_pnml`, and `to_dot`:
     ```python
     if "resolved" in self.metadata:
         d["resolved"] = self.metadata["resolved"]
     if "resolved_to" in self.metadata:
         d["resolved_to"] = self.metadata["resolved_to"]
     if "target_file" in self.metadata:
         d["target_file"] = self.metadata["target_file"]
     ```
   - **Suggestion**: Encapsulate call resolution metadata into a small dataclass or typed structure (e.g. `CallResolution` or helper accessors on `Transition`) to prevent reliance on magic string keys and ensure schema validation.

2. **Feature Envy & Repeated Switches** ([`code2petri/model.py:213-230`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/model.py#L213-L230), [`code2petri/model.py:282-304`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/model.py#L282-L304))
   - **Finding**: Both `PetriNet.to_pnml` and `PetriNet.to_dot` reach directly into `transition.metadata` and repeat branching logic on `transition.metadata.get("resolved")` to decide XML elements or Graphviz colors:
     ```python
     if transition.metadata.get("resolved"):
         attrs_list.append('color="#2e7d32"')
     elif transition.metadata.get("resolved") is False:
         attrs_list.append('color="#e65100"')
     ```
   - **Suggestion**: Delegate formatting rules to `Transition` methods (e.g. `transition.get_dot_attributes()` and `transition.get_pnml_toolspecific()`). `PetriNet` should only coordinate net-level structure without knowing the visual styling rules for resolved vs. unresolved call transitions.

3. **Duplicated Code** ([`tests/test_petri_if_branching.py:13`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_petri_if_branching.py#L13), [`tests/test_petri_loops.py:13`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_petri_loops.py#L13), [`tests/test_petri_try.py:13`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_petri_try.py#L13), [`tests/test_python_walker.py:16`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_python_walker.py#L16))
   - **Finding**: The adapter lambda unboxing `WalkResult.net` is duplicated verbatim across four test modules:
     ```python
     walk_function = lambda *args, **kwargs: walker.walk_function(*args, **kwargs).net
     ```
   - **Suggestion**: Extract a shared test fixture or helper function in [`tests/petri_assertions.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/petri_assertions.py) (e.g. `walk_net(walker, node, func_name) -> PetriNet`) to avoid repeated monkey-patching in individual test modules.

---

## Spec

### (a) Missing or Partial Requirements
**None (0 Missing).**
All core protocol requirements for Ticket 11 are implemented:
- `CallSite` dataclass and `WalkResult` named tuple are defined in `code2petri.walker_protocol` and exported in `code2petri/__init__.py` ([`11-prefactor-walk-result-and-metadata.md:9`](file:///.scratch/code2petri/issues/11-prefactor-walk-result-and-metadata.md#L9)).
- `WalkerProtocol`, `PythonWalker`, and `JavascriptWalker` implement `walk_function(ast_node, func_name) -> WalkResult` and abstract stub `collect_variable_bindings(tree) -> Dict[str, str]` ([`11-prefactor-walk-result-and-metadata.md:11-12`](file:///.scratch/code2petri/issues/11-prefactor-walk-result-and-metadata.md#L11-L12)).
- `engine.py` cleanly unpacks `walk_res.net` and `walk_res.call_sites` ([`11-prefactor-walk-result-and-metadata.md:13`](file:///.scratch/code2petri/issues/11-prefactor-walk-result-and-metadata.md#L13)).
- `Transition` supports optional `metadata: Optional[Dict[str, Any]] = None` preserved across dictionary copy and JSON export ([`11-prefactor-walk-result-and-metadata.md:10`](file:///.scratch/code2petri/issues/11-prefactor-walk-result-and-metadata.md#L10)).
- Test suite passes with 181 passing tests ([`11-prefactor-walk-result-and-metadata.md:14`](file:///.scratch/code2petri/issues/11-prefactor-walk-result-and-metadata.md#L14)).

---

### (b) Behaviour Not Asked For (Scope Creep) & Suggestions

1. **Premature Implementation of Ticket 14 Reference Serialization** ([`code2petri/model.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/model.py))
   - **Finding**: Ticket 11 was scoped as a protocol refactor. However, `code2petri/model.py` and `tests/test_petri_model.py` implemented Ticket 14's resolution serialization rules:
     - PNML `<toolspecific tool="code2petri">` tags with `<resolved>` and `<unresolved/>` elements.
     - Graphviz DOT green (`#2e7d32`) / orange (`#e65100`) borders and tooltips.
     - JSON root promotion for `resolved`, `resolved_to`, and `target_file`.
   - **Suggestion**: While technically out-of-scope for Ticket 11, this is productive forward-progress for Ticket 14. Rather than reverting it, keep the implementation and annotate Ticket 14 (`14-cli-context-and-reference-serialization.md`) that the model serialization layer is already delivered.

2. **`ControlFlowBuilder.add_transition` Metadata Parameter** ([`code2petri/control_flow_builder.py:76`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/control_flow_builder.py#L76))
   - **Finding**: `add_transition` was updated to accept an optional `metadata` parameter.
   - **Suggestion**: Retain this change. It provides a clean API for walkers and builders to attach metadata at transition creation time without secondary mutations.

---

### (c) Implemented But Wrong & Suggestions

1. **PNML Serializer Converts `None` Attributes to Literal `"None"` Strings** ([`code2petri/model.py:218-219`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/model.py#L218-L219))
   - **Finding**:
     ```python
     target = str(transition.metadata.get("resolved_to", ""))
     target_file = str(transition.metadata.get("target_file", ""))
     ```
     If `transition.metadata` has `{"resolved_to": None, "target_file": None}`, `dict.get("resolved_to", "")` returns `None`, which `str()` converts to `"None"`. This results in invalid XML output: `<resolved target="None" file="None"/>`.
   - **Suggestion**: Use `(transition.metadata.get("resolved_to") or "")` to guarantee empty string fallback:
     ```python
     target = str(transition.metadata.get("resolved_to") or "")
     target_file = str(transition.metadata.get("target_file") or "")
     ```

2. **Legacy Test Suites Bypassed Direct Testing of New Return Type**
   - **Finding**: Tests in `test_petri_if_branching.py`, `test_petri_loops.py`, `test_petri_try.py`, and `test_python_walker.py` were made green by monkey-patching `walk_function` to return `.net` directly, rather than asserting on `WalkResult`.
   - **Suggestion**: While acceptable as a non-breaking shim for control-flow tests focused purely on net topology, update `test_python_walker.py` and `test_javascript_walker.py` to explicitly verify that `res` is an instance of `WalkResult` and contains `res.call_sites` list.

---

## One-Line Summary

- **Standards**: 0 hard violations, 3 judgement calls (worst: Feature Envy & duplicated resolution branching in `PetriNet.to_pnml` and `to_dot`).
- **Spec**: 0 missing requirements, 2 scope creeps (benign early delivery of Ticket 14 serialization), 2 implementation defects (worst: literal `"None"` XML attribute serialization in PNML).

