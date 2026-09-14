# Ticket 19: Code Review (Round 4)

**Diff:** `2ddace6...HEAD`  
**Commit:** `43e6e87`  
**Spec:** `.scratch/code2petri/issues/19-inline-expansion-engine.md`

## Standards Axis Findings & Suggestions
**STATUS: PASS (Clean, 0 Hard Violations, Minor Judgement Calls)**

### Verification of Round 3 Findings
1. **"Merge net" vocabulary ([`test_inline_expansion.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_inline_expansion.py#L373)):** **RESOLVED**. Updated to `# Build composite net and combine call sites`, adhering to `CONTEXT.md` (*Composite Net*).
2. **Duplicated boundary place logic:** **RESOLVED**. Extracted properties [`Place.is_start`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/model.py#L69-L72) and `Place.is_end` onto `Place` in `model.py`; both `PetriNet.find_boundary_places` and `_is_self_referencing_game_loop` now use `p.is_start`.
3. **Feature Envy in cycle annotation:** **RESOLVED**. Moved into [`Transition.mark_recursive_cycle()`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/model.py#L231-L235).
4. **Speculative Generality:** **RESOLVED**. The unrequested `walker_cache` dictionary was completely removed.
5. **Primitive Obsession in game loop check:** **RESOLVED**. Replaced raw string split with structured `CallFrame.from_caller(cs)` and `frame.bare_name`.

### Documented Standards Violations (Hard Violations)
- None.

### Baseline Smells (Judgement Calls)
1. **Duplicated Code ([`inline.py:L236-249`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/inline.py#L236-L249)):** Caller and callee frame population logic (expanding qualified and bare name variants) is duplicated. Unifying this in a helper on `CallFrame` would clean up both sites.
2. **Duplicated Code ([`test_inline_expansion.py:L375-390`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_inline_expansion.py#L375-L390)):** Manual prefixing and cloning of nets in `test_multi_caller_initial_stack` duplicates composite net construction shapes.
3. **Residual Primitive Obsession ([`inline.py:L183-187`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/inline.py#L183-L187)):** Substring containment against `trans.label` in `_is_self_referencing_game_loop` is still used as a secondary fallback.

---

## Spec Axis Findings & Suggestions
**STATUS: PASS WITH ADVISORY (Critical Round 3 Bug Fixed, 1 Edge-Case Advisory)**

### Verification of Round 3 Findings
- **Horizontal Recursion Guard [CRITICAL]:** **RESOLVED**. The horizontal `initial_stack` aggregation across all call sites in `inline_expand` was eliminated. Root call sites independently establish vertical path-dependent call stacks, and recursive calls pass `new_stack` downward vertically.

### (a) Missing or Partial Requirements
- **Spec Line 9 & Line 21 (Bipartite Splicing Boundary):**
  - Callee source/sink places are merged/eliminated rather than wired via Place $\to$ Place arcs. This deviation from literal wording is mathematically required to maintain bipartite Petri net validity per Line 22.

### (b) Scope Creep (Unasked Behaviour)
- **Spec Line 23 (Browser-Specific API hardcoding):**
  - `_is_self_referencing_game_loop` hardcodes checks for `cs.callee_name != "requestAnimationFrame"` and `this.` prefixes. While the spec used `requestAnimationFrame(loop)` as an example, embedding browser-specific API names into the core expansion engine is slight scope creep (though harmless for JS game loops).

### (c) Implemented but Looks Wrong (Advisory)
- **Spec Line 11 (Same-file Multi-class Method Name Collision):**
  - In `inline.py:240-241` and `inline.py:248-250`, both qualified name (`ClassA.step`) and bare name (`step`) register as `CallFrame(filepath, "step")`.
  - If two different classes in the same file define methods with the same bare name (e.g. `gpuEngine.step()` in `WebGLEngine` calling `cpuEngine.step()` in `CPUEngine`), both register `CallFrame(file, "step")`, producing a false-positive recursion cycle that halts valid inlining.
  - **Suggestion:** Only fall back to matching `bare_name` if one of the names is actually unqualified (e.g., `"." not in caller_frame.name or "." not in sym.name`). If both sides are qualified (have `.` in their names), compare only full qualified names.
