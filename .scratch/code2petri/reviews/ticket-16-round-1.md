# Ticket 16: Code Review & Suggestions (Round 1)

**Commit:** `d52b8b7`  
**Spec:** `.scratch/code2petri/issues/16-png-colored-borders.md`

## Standards Axis Findings & Suggestions

### 1. Primitive Obsession (Judgement Call)
**Finding:** String literals (`"#2e7d32"`, `"#e65100"`) and raw RGB hex bytes are used across `code2petri/model.py` and its tests to represent domain concepts (Resolved vs Unresolved status).  
**Suggestion:** Introduce a dedicated enum or constant configuration for transition status colors.
```python
class RenderingConfig:
    RESOLVED_COLOR = "#2e7d32"
    UNRESOLVED_COLOR = "#e65100"
```

### 2. Feature Envy (Judgement Call)
**Finding:** In `code2petri/model.py`, `PetriNet.to_dot()` is heavily inspecting the dictionary returned by `Transition.get_dot_attributes()`, specifically plucking out `"fillcolor"`, `"color"`, and `"tooltip"` to construct DOT syntax.  
**Suggestion:** Move the DOT serialization logic directly into the `Transition` class. The `PetriNet` should ideally just call `transition.to_dot_node()`.

### 3. Duplicated Code (Judgement Call)
**Finding:** In `test_game_of_life_validation.py`, the RGB proximity check is repeated almost identically for both green and orange.  
**Suggestion:** Extract the proximity logic into a helper function inside the test suite:
```python
def is_similar_color(r, g, b, target_hex, tolerance=15):
    # Implementation checking distance
```

### 4. Shotgun Surgery (Judgement Call)
**Finding:** Adding a new DOT attribute (`fillcolor`) required identical, hardcoded string test updates in both `test_petri_model.py` and `test_game_of_life_validation.py`.  
**Suggestion:** If DOT attribute serialization were encapsulated (as suggested in Finding 2), we could test the attribute dictionary directly in unit tests instead of grep-testing DOT string outputs everywhere.

---

## Spec Axis Findings & Suggestions

### (a) Missing or partial requirements
**Finding:** The ticket mandated removing the border width/color properties (Option A: "rather than relying on a thin border"). While `penwidth` wasn't actually present in the base commit, the existing `color` attributes were left intact.  
**Suggestion:** Remove the `attrs["color"]` assignments from `Transition.get_dot_attributes()`, and update `PetriNet.to_dot` so it relies exclusively on `fillcolor`.

### (b) Scope creep
**Finding:** The author introduced a complex, unprompted PyMuPDF image-parsing test (`test_png_rendering_distinguishes_resolution_status`) to verify pixel colors in a generated PNG.  
**Suggestion:** While rigorous, parsing raw PNG pixels via `pymupdf` in the unit test suite is brittle and wasn't requested. Consider removing this test, or moving it to a dedicated end-to-end integration test folder rather than the core validation suite. 

### (c) Implemented but looks wrong
**Finding:** The nodes will still render with a thin colored border alongside the new fill color, defeating the design intent of Option A to stop relying on borders entirely.  
**Suggestion:** Same fix as (a). Strip all `color="..."` properties from the transition DOT output so the `fillcolor` is the sole color indicator. Tests asserting `color="#..."` should be updated to assert `fillcolor="#..."` instead.
