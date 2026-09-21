## Problem Statement

The current `code2petri` workflow strictly segregates reduction logic from the visualization layer. The Python backend fully pre-computes a linear sequence of fold steps using the Structuredness Metric (SM) rules, and the HTML Cytoscape viewer acts merely as a playback mechanism (the fold slider). Furthermore, inline function expansion is completely orthogonal to the fold process: clicking an opaque transition splices the raw callee sub-net into a compound node, but the user cannot interactively "fold" specific parts of that newly expanded logic, nor can they view the entire composite program structure in full detail upon first opening the HTML artifact. 

This leads to a rigid, top-down exploration experience. Users cannot selectively simplify messy knots, rename abstracted transitions for clarity, or export the resulting "half-folded" architecture to external tools like ProM. They are trapped on a linear undo slider that doesn't understand the localized, non-linear nature of program comprehension.

## Solution

The viewer will be fundamentally rearchitected to support **Live Fold Reduction**. 

Instead of opening a collapsed graph, the viewer will boot into a fully-expanded composite view, showing all inlined functions nested within visual compound nodes right from the start. The ProM local reduction algorithms (Sequence, Choice, Loop) will be ported from Python to JavaScript. This allows the user to left-click any intermediate routing place on the canvas to trigger a "Place-Centric Fold Trigger," dynamically contracting that place and updating transition weights in real-time. 

When an entire inline expansion (a compound node) is fully folded from the inside out, it transitions into a "Collapsed Compound State" visually resembling a closed folder labeled with the function's name and component ID. Folds are fully reversible via "Component-Local Unfold" (clicking the collapsed element restores its internal nodes without affecting folds made elsewhere). Finally, the user can rename any generated component node via a sidebar and trigger a "Client-Side Export" to download the current interactive graph state as a PNML file.

## User Stories

1. As a developer, I want the HTML viewer to display the entire inline-expanded graph in maximum detail immediately upon load, so I don't have to manually click through a deep call tree to see the full picture.
2. As a developer, I want all inlined functions to be visually encapsulated inside Nested Compound Nodes by default, so I can clearly see the boundaries of each function in the global composite graph.
3. As an analyst, I want to left-click an intermediate place node to instantly collapse it (Single-Place Contraction) directly in the browser, so I can manually clean up AST routing anomalies where I choose.
4. As an analyst, I want the browser to calculate the component penalty ($\omega$) and new transition weight ($\tau$) in real-time when I perform a Live Fold Reduction, so the cognitive complexity score remains mathematically rigorous.
5. As an analyst, I want to pan the canvas by holding the right and middle mouse buttons, so left-click is freed up entirely for interacting with nodes.
6. As a developer, I want a fully folded function to appear as a Collapsed Compound Node (a closed folder) displaying `function_name (c_XX)`, so I can distinguish a collapsed function from a generic opaque transition.
7. As an analyst, I want to click on a Collapsed Compound Node or opaque transition to instantly unfold it (Component-Local Unfold), without having to use a linear global undo slider that would revert my other unrelated folds.
8. As a developer, I want to left-click a transition/component node to open a sidebar or modal, so I can view its metadata ($\tau$ weight, SM score, line number).
9. As a developer, I want to use that sidebar/modal to rename a generated component (e.g., changing `c_04` to `calculate_tax`), so the folded graph better reflects domain semantics.
10. As an analyst, I want to click an "Export PNML" button in the viewer that triggers a standard browser file download, so I can save my manually half-folded graph state and open it in ProM without needing a Python backend server.

## Implementation Decisions

- **Initial Assembly:** Python's `inline.py` engine (specifically a variant or flag on `inline_expand`) will pre-assemble the entire Composite Net. It will inject hierarchy metadata (`enclosing_function` or explicit `parent` pointers) into the nodes before generating the `{{DATA_JSON}}` payload. 
- **JS Reduction Engine:** The core reduction algorithms from `fold.py` (specifically `fold_single_place_contraction`, `fold_choice`, and `fold_while`) will be rewritten in JavaScript within `template.html` (or a bundled script). 
- **Interaction Mapping:** 
  - Left-Click (Place): Trigger Place-Centric Live Fold.
  - Left-Click (Transition/Component): Open sidebar for metadata inspection and node renaming.
  - Right/Middle Mouse Hold: Canvas Pan.
- **Undo Architecture:** Graph mutations in JS will not use a global state array. Instead, when a fold occurs, the newly created node's `data` dictionary will store a serialized copy of the nodes and edges it consumed. Component-Local Unfolding simply reads this data, removes the component node, and injects the stored elements back into the Cytoscape instance.
- **Client-Side Export:** A new JS function will traverse the current Cytoscape elements array, convert the places, transitions, arcs, and initial tokens into standard PNML XML syntax, and construct a `Blob` URL attached to a hidden `<a download>` tag to force a save-as prompt.
- **Prototyping Strategy:** Development will begin on the `feature/live-fold-reduction-js-prototype` branch to validate the JS reduction math and the Cytoscape UI/UX feel before replacing the main Phase 2.6 infrastructure.

## Testing Decisions

- A good test for Live Fold Reduction ensures that the mathematical invariants of the Petri net (conservancy, structural soundness) are maintained after arbitrary sequences of user interactions, and that the resulting $\tau$ weights exactly match the Python reference implementation.
- **Modules to Test:** 
  1. The Python composite assembly logic (ensuring parent hierarchy metadata survives the splice).
  2. The JavaScript fold engine (via a headless JS test runner like Jest, or robust DOM tests using Playwright/Selenium).
- **Prior Art:** Since JS testing is new to this project, we will establish a pattern: we will dump a known AST-generated composite graph to JSON, run the JS fold functions on it, and assert the resulting graph topology and SM scores match the output of `pytest tests/test_fold_detection.py`.

## Out of Scope

- **Component-Centric Folding (Lasso / Shift-Click):** While discussed as a future enhancement for folding maximal SESE subnets in one click, the initial prototype will strictly implement Place-Centric Folding (Single-Place Contraction).
- **Round-trip execution:** The exported PNML is one-way. We are not building a feature to re-import a half-folded PNML file back into the `code2petri` CLI.

## Further Notes

- The decision tree that formed this spec is documented in the project logs, confirming the architectural shift from Python-led reduction to Browser-led interactive reduction.
