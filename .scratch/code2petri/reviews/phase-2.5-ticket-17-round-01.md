# Ticket 17: Code Review & Suggestions (Round 1)

**Commit:** `ebdc0a6`  
**Spec:** `.scratch/code2petri/issues/17-fold-config-and-component-detection.md`

## Standards Axis Findings & Suggestions

### 1. Speculative Generality
**Finding:** In `code2petri/fold.py`, `ComponentType.MARKED_GRAPH` and `FoldConfig.marked_graph` were added, even though the issue explicitly states that AND-splits (marked graphs) are slated for Phase 3 extensibility.
**Suggestion:** Delete `MARKED_GRAPH` and `FoldConfig.marked_graph`. Add them back only when Phase 3 demands it.

### 2. Feature Envy
**Finding:** `detect_loops` in `code2petri/fold.py` initializes `topo = NetTopology(net)` but ignores it, reaching directly into `net.arcs` manually to filter arcs and find boundaries. `calculate_diff` also iterates over raw `net.arcs`.
**Suggestion:** Delegate to `NetTopology`'s `presets()` and `postsets()` instead of envying the raw `net.arcs` list.

### 3. Mysterious Name
**Finding:** The function `calculate_diff(...) -> int` in `code2petri/fold.py` calculates a structural symmetry multiplier, but its name implies a text or data diffing utility.
**Suggestion:** Rename the function to `calculate_symmetry_multiplier`.

### 4. Divergent Change
**Finding:** `FoldConfig` mixes pure domain configuration state with JSON parsing and file I/O responsibilities (`from_file()`).
**Suggestion:** Extract the file I/O and JSON loading logic into a separate factory or builder function outside the dataclass.

### 5. Duplicated Code
**Finding:** In `tests/test_fold_detection.py`, the `test_mixed_net_priority_sorting` test manually builds subnets line-by-line, copying the exact setup shape used in other tests (like `test_detect_3_transition_sequence`).
**Suggestion:** Extract shared net-building helpers (e.g., `build_sequence_net()`) and invoke them to keep tests DRY.

---

## Spec Axis Findings & Suggestions

### (a) Missing or partial requirements
**Finding:** The spec requested unit tests on hand-built nets for pure sequences, single XOR-split/joins, and single loops. The implementation skips isolated hand-built tests for sequences/XORs, and the loop test relies on a real walker fixture rather than a hand-built net.
**Suggestion:** Add dedicated, isolated hand-built net tests for all three component types to verify pure structural detection logic.

### (b) Scope creep (unasked for behaviour)
**Finding:** Serialization methods (`to_dict`, `to_json`) were added to the `Component` and `FoldConfig` classes beyond the requested JSON loading factory. Additionally, a `priority` state field was embedded in the `Component` model, whereas the spec only asked that the function *return* them as a sorted list.
**Suggestion:** Remove `to_dict`/`to_json` if unneeded. Remove the embedded `priority` field and simply sort the output list at return time.

### (c) Implemented but looks wrong [CRITICAL]
**Finding:** 
1. `detect_loops` calculates `internal_nodes = cycle_nodes - {entry_place}`. This fails to exclude the `exit_boundary_node` from the internal loop nodes if it is different from the entrance place.
2. The implementation sets the component exit node to `exit_arc.source.id`. Because this node is *inside* the cycle, its postset includes nodes inside the loop. The spec mandates a single exit arc. The loop exit boundary node should be the *destination* of the exit arc (`exit_arc.target.id`) to properly establish the component boundary.
**Suggestion:** Update `detect_loops` to exclude the exit target node from `internal_nodes` and set the component's `exit_node` to `exit_arc.target.id`.
