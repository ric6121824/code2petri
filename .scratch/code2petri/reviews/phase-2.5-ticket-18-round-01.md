# Ticket 18: Code Review (Round 1)

**Commit:** `HEAD`
**Spec:** `.scratch/code2petri/issues/18-fold-reduction-engine-and-sm.md`

## Standards Axis Findings & Suggestions

### 1. Documented Standard Violation (Hard Violation)
**Finding:** In `code2petri/fold.py`, the code repeatedly uses the term "dummy transition" (e.g., `dummy_transition_id`, `dummy_t = folded_net.add_transition(...)`, `{"dummy": True}`) to represent folded components. This violates the `CONTEXT.md` vocabulary standard, which mandates using "Opaque Transition" for a single Petri net transition representing a block of code whose internal structure is abstracted.
**Suggestion:** Replace all instances of "dummy" terminology with "opaque" (e.g., `opaque_transition_id`, `{"opaque": True}`).

### 2. Middle Man
**Finding:** `FoldStep` and `FoldResult` define properties that merely alias their own existing fields (`step`, `net`, `folded_nodes`, `sm_score`, `penultimate_state`). There is also a module-level alias `fold = fold_net` that delegates onward without adding value.
**Suggestion:** Cut the aliases and use the real fields and targets directly.

### 3. Data Clumps / Scope Creep
**Finding:** `function_name` and `file_path` are continually passed together through the folding logic purely for serialization later, adding fields to JSON output that the spec did not request.
**Suggestion:** Bundle these into a single context type (e.g., `TargetContext`) rather than polluting the algorithm's signature, or simply attach them at the very end during serialization.

### 4. Mysterious Name
**Finding:** Using "global" to describe the overall net boundaries (e.g., `# Identify global entrance and exit places`) clashes with the established **Global Scope** domain concept. 
**Suggestion:** Prefer "net entrance/exit" to maintain clarity.

### 5. Duplicated Code
**Finding:** The logic shape for mapping node IDs to node objects is repeated across multiple files (in `fold_component`, `fold_unstructured`, `PetriNet.clone`, and `combine_into_composite_net`):
```python
node_map = {p.id: p for p in folded_net.places}
node_map.update({t.id: t for t in folded_net.transitions})
```
**Suggestion:** Extract a shared `get_node_map()` helper method on the `PetriNet` class.

---

## Spec Axis Findings & Suggestions

### (a) Missing or partial requirements
All core requirements (the fold loop, dataclasses, termination conditions, accumulated $\tau$ calculations, unstructured fallback, and unit tests) appear fully implemented.

### (b) Scope creep (unasked for behaviour)
**Finding:** As noted above, the `FoldResult` dataclass and its JSON serialization were expanded to include `function_name` and `file_path` attributes, injecting `"function"` and `"file"` fields into the output payload that weren't specified.
**Suggestion:** Remove them from the folding logic if they aren't necessary for the fold process itself.

### (c) Implemented but looks wrong [CRITICAL]
**Finding (Trivial Net Validation):** 
The `_is_trivial_workflow_net` function incorrectly classifies a single-place net with a self-looping transition as a trivial workflow net. Because Python sets eliminate duplicates, the check `{p.id for p in net.places} != {p_in_id, p_out_id}` evaluates to `{'p0'} != {'p0'}` (False) when the source and sink are the exact same place. This mistakenly allows a self-loop to pass as a fully reduced workflow net, bypassing the structural requirement for distinct source and sink places.
**Suggestion:** Add a check `if p_in_id == p_out_id: return False` to require exactly two distinct places (a source and a sink) for a valid trivial workflow net.

**Finding (Rewiring Wording):**
The rewiring logic operates against the component's entrance *node* (`component.entrance`), rather than an "entrance arc". While this is the mathematically correct approach for Petri net component boundaries, it technically conflicts with the literal phrasing in the spec.
**Suggestion:** Keep the implementation (it is structurally correct), but this is a note that the spec's literal phrasing was imprecise.
