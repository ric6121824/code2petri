# Inspection — Ticket 53, Round 03: Tic Tac Toe `create_board()`

**Date:** 2026-10-12  
**Repository revision inspected:** `3bd8a93`  
**Ticket:** [53 — Complete called-function folding at shared boundaries](../issues/53-called-function-fold-boundary-trigger.md)  
**Previous review:** [Round 02](./phase-2.8-ticket-53-round-02.md)  
**Input:** `/Users/pingchungtsai/Downloads/tic_tac_toe_global_foldable_session_save.json`  
**Scope:** Diagnosis of the reported missing green entrance/exit highlights, followed by the agreed implementation requirements for another agent. No production fix was applied.  
**Requirement clarification:** 2026-10-12 — The user requires the **Fold Entire Function** button to fold `create_board()` into a **brown component node**. The required behavior below supersedes the earlier representation alternatives.

## Finding

**P2 — Functions that begin with one ordinary transition cannot reach recognized completion.**

Both saved `create_board()` call occurrences reproduce the report against the current repository engine and the actual viewer highlight function. Their caller-owned entrance and exit places are not green. Fold-Entire-Function performs zero passes and reports no progress.

This is a different graph shape from Ticket 53's previously repaired Choice cases. There are no parallel branches, no internal split/merge place, and no internal place at all. The source function contains one return statement:

```python
def create_board():
    return ['#'] + [' ' for i in range(9)]
```

After Boundary Place Unification, its function container owns just one ordinary transition. The surrounding entrance and exit places belong to the caller. The implementation recognizes a singleton function as complete only when its child is already an Opaque Transition. A function with no internal places has no available local reduction to create that opaque child, leaving completion and boundary eligibility blocked.

## Source verification and representation decision

Follow-up inspection of the original [main.py](<../../../../Python-Games/Tic Tac Toe/pygame/main.py>) confirms that the call classification is correct:

- Line 8 explicitly imports `create_board` from `objects`.
- Line 50 calls `board = create_board()` during initialization.
- Line 144 calls it again when restarting the game.
- [objects.py](<../../../../Python-Games/Tic Tac Toe/pygame/objects.py>) lines 28–29 define that function. There is no intervening rebinding of `create_board` in the inspected caller.

The saved compounds point to this definition and correspond to the two source call sites. [SymbolTable.resolve_call()](../../../code2petri/symbol_table.py#L279) resolves bare calls using local definitions followed by context definitions; [inline expansion](../../../code2petri/inline.py#L337) then expands resolved callees subject to depth and recursion guards. No minimum callee size excludes this function. Its return expression includes a list comprehension; “atomic” here describes the current Petri-net representation, not an absence of computation in the Python function.

**Decision:** Keep the resolved function identity, its compound container, and the Fold Entire Function action. This follows the [Phase 2.7 spec](../specs/phase-2.7-live-fold-reduction.md), which requests nested compounds for inlined functions, and supports the user's explicit brown-component requirement. Omitting the container or automatically replacing the ordinary child with an opaque component on load is not the selected implementation.

Recognize an ordinary singleton as structurally atomic for safe boundary eligibility while retaining its expanded visual state until the user folds it. The explicit function action must produce a real reversible component. These are distinct states: being safe for surrounding Sequence contraction does not mean the user has already folded the function.

## Reproduction evidence

The attachment is a schema-version-1 `code2petri-fold-state` snapshot with 692 saved elements and a step counter of 52. Its document identifies Tic Tac Toe's `pygame/main.py` as the Global Scope source. The two affected compounds reference `pygame/objects.py::create_board@28:0`.

| Call occurrence | Only owned transition | Entrance | Exit | Boundary green | Function action |
|---|---|---|---|---|---|
| `compound_create_board` | `inline_create_board__t1` | `p28` | `p29` | Both false | `complete: false`, `passes: 0` |
| `compound_inline_create_board_t123` | `inline_create_board_t123__t1` | `p101` | `p102` | Both false | `complete: false`, `passes: 0` |

Both children have label `return ['#'] + [' ' for i in range(9)]`, type `Transition`, and are not opaque. Each of the four caller boundary places has exactly one incoming and one outgoing arc. The engine reports these specific reasons:

```text
Entrance: Succeeding transition belongs to function container '<compound>',
          which is not yet folded into a single component node.
Exit:     Preceding transition belongs to function container '<compound>',
          which is not yet folded into a single component node.
```

The function action returns:

```text
No progress folding function '<compound>'; no eligible descendant places were found.
```

Replay uses the repository Cytoscape bundle, `LiveFoldReductionEngine`, and `updateFoldableHighlights()` extracted from the current template. Highlights are recomputed; saved CSS classes are not taken as an eligibility verdict. Both real occurrences reproduced on repeated runs. A separate six-node/four-arc model reproduces the same rejection with no other functions, folds, recursion, token markings, or structural candidates:

```text
caller_before -> entrance -> [function: ordinary_return] -> exit -> caller_after
```

The two places are outside the function container. The compound and its sole child are separate Cytoscape nodes.

## Cause and controlled probes

The relevant engine paths are in [reduction_engine.js](../../../code2petri/viewer/engine/reduction_engine.js):

1. `_updateCollapsedCompoundStates()` (line 452) changes a container to Collapsed Compound State only if its sole child passes `isOpaqueTransition()`.
2. `isFunctionFoldedIntoSingleComponent()` (line 589) likewise rejects a sole ordinary transition.
3. `canSinglePlaceContract()` (line 813; boundary guards at line 863) rejects crossing into or out of a function that the preceding predicate considers incomplete.
4. `executeFoldEntireFunction()` (line 1348) considers only descendant places. It exits immediately when there are none, without completing the ordinary singleton.
5. [updateFoldableHighlights()](../../../code2petri/viewer/template.html#L1881) follows the resulting eligibility decision, so the missing green highlight is a consequence of the engine state rather than a styling defect.

Three explanations were checked: a missing ordinary-singleton completion case, a necessary caller-boundary safeguard, and unrelated reductions suppressing eligibility. The isolated model reproduces the failure, ruling out unrelated graph activity as a necessary cause. The caller-boundary guard is functioning as implemented; its completion prerequisite cannot be satisfied by this function shape.

Only in-memory diagnostic changes were used:

| Probe on isolated model | Boundaries green | Function complete | Visually collapsed | Local unfolding |
|---|---|---|---|---|
| Baseline | Neither | No | No | Not applicable |
| Override only the completion predicate to true | Both, Sequence | Yes | No | Not tested |
| Mark only the ordinary child `is_opaque: true` | Both, Sequence | Yes | Yes | Fails: missing restoration record |

All three probes retain SM = 3. The flag-only probe fails with `Failed to unfold internal opaque transition 'return'.` It establishes the obstruction but is not a safe implementation.

The current engine therefore reproduces this shape independently of the exporter that produced the attachment. This inspection does not establish the exact engine version embedded in the original Tic Tac Toe HTML, which was not supplied.

## Required behavior and acceptance criteria

The brown-component requirement is compatible with the reversible completion approach. Implement the following together; fixing only the boundary highlights or only the function button does not satisfy this inspection.

- [ ] **Initial state:** Both `create_board()` occurrences remain identifiable called-function compounds with their ordinary return transition visible. Selecting either occurrence exposes a working **Fold Entire Function** button. Loading the graph or recomputing highlights must not allocate a component, increment the fold counter, or silently collapse the function.
- [ ] **Boundary highlights:** The saved examples' entrance/exit pairs (`p28`/`p29` and `p101`/`p102`) are green immediately after opening/restoring and refreshing highlights. They permit the usual surrounding Sequence contraction even before the explicit function action, subject to all existing topology, token, and ownership safeguards. Merely having one child must not authorize arbitrary boundary folding.
- [ ] **Explicit function fold:** Clicking Fold Entire Function on either untouched occurrence succeeds despite there being no internal places. It creates one uniquely identified Opaque Transition/component inside the same function compound, with a complete restoration record. The action reports `success: true` and `complete: true`, and the sidebar confirms completion.
- [ ] **Brown presentation:** The selected compound enters the existing **Collapsed Compound State**, displayed as the brown/gold component-style node already used for fully folded functions. Use the current `collapsed-compound` styling in [template.html](../../../code2petri/viewer/template.html#L1378), including the function name and component ID (for example, `create_board (c_XX)`) and the hidden internal opaque child. A green boundary highlight, a plain return transition, or an “already collapsed” message with an expanded container does not meet this requirement.
- [ ] **Contained action:** Folding the function consumes only its ordinary child representation. It preserves the caller's entrance and exit place IDs, tokens, incident connections, surrounding transitions, the other call occurrence, sibling nodes, and unrelated folds. Retain a valid bipartite graph.
- [ ] **Weights and identity:** Preserve the original transition weight (including the existing default when absent), keep the total Structuredness Metric unchanged, and add zero penalty. Preserve source information, function identity/reference, return metadata, labels/custom names, and the original child data needed for restoration. Use the existing component ID allocation conventions without collisions with saved or nested history.
- [ ] **Repeatability:** Repeating the action on an already collapsed function is a safe no-op with `complete: true`; it creates no extra component or fold-counter change. The two call occurrences can be folded independently, and nested singleton functions can be completed by the existing recursive Fold Entire Function action.
- [ ] **Local unfolding:** Component-Local Unfold restores the exact ordinary return transition, its metadata, hierarchy, and arcs; the function becomes visibly expanded and its Fold Entire Function button is available again. A later fold/unfold cycle works. Restoration must not immediately auto-collapse the ordinary singleton during highlight refresh.
- [ ] **Session continuation:** Existing saves, including the supplied version-1 attachment, load without requiring new fields. Saving/opening before or after the explicit action retains the corresponding expanded/collapsed state and permits continued folding/unfolding. If a later caller Sequence consumes the function, local unfolding restores the recorded prior state: an ordinary expanded singleton if no explicit function fold preceded it, or the reversible collapsed component if it did.
- [ ] **UI consistency:** The sidebar action performs one final layout and preserves zoom/pan, following the existing function action contract. The brown appearance, button availability, action result, and actual graph state agree.

## Implementation guidance

Handle an already-atomic function explicitly and consistently across completion detection, compound presentation, boundary eligibility, and restoration. A singleton ordinary transition needs no mathematical reduction to become structurally atomic. Retain the ownership checks that protect functions with internal places, multiple transitions, or unresolved nested compounds.

Add a shared reversible completion path for an ordinary singleton, invoked by the explicit function action and by its traversal of nested functions. Create the opaque representation using the existing allocation/restoration conventions, capturing the original child and exact connections before mutation. Treat this as zero-penalty representation of an already-atomic function, without fabricating an internal place or a new mathematical reduction. A bare opaque flag is insufficient because it leaves Component-Local Unfold without restoration data.

Separate safe atomic boundary eligibility from completed visual folding. In particular, simply broadening `isFunctionFoldedIntoSingleComponent()` to return true for an ordinary singleton is insufficient: [the sidebar](../../../code2petri/viewer/template.html#L1755) uses it to hide Fold Entire Function, and [the engine action](../../../code2petri/viewer/engine/reduction_engine.js#L1368) uses it to return “already fully collapsed” before doing any work. Keep these callers consistent with the explicit user action and actual opaque/collapsed state. Use a narrowly scoped atomic-shape check where boundary eligibility needs it; retain containment checks for non-atomic or unresolved nested functions.

Handle the singleton before the function action exits for lack of descendant places. Count the explicit component creation as successful progress in its result/UI even though no internal place was removed; zero descendant-place passes are valid. Keep the existing action-result structure compatible with the sidebar formatter. [handleFoldEntireFunction()](../../../code2petri/viewer/template.html#L1828) refreshes the graph and inspector only when `result.success` is true. Preserve the no-progress behavior for genuinely unsupported graphs. Audit callers of any changed eligibility/completion helper, including structural candidate validation and caller Sequence restoration, to avoid expanding permission beyond this shape.

Folding a green entrance or exit place then performs a surrounding caller Sequence contraction; it is not a reduction wholly inside `create_board()`. Keep that action distinct from Fold-Entire-Function, which must preserve caller-owned boundary places. Do not add caller places to the function's batch scope, permit arbitrary crossing of incomplete functions, invent a penalty-bearing reduction, or use whole-net fallback.

This remains a Phase 2.8 completion/eligibility follow-up. It does not show that the prior shared-boundary Choice repair has regressed. Extend the reopened ticket with an explicit ordinary-singleton acceptance case; keep its earlier Choice and containment requirements.

## Required regression coverage

Use the generated-viewer/headless seam in [test_html_viewer.py](../../../tests/test_html_viewer.py), including the sidebar action and actual highlight refresh:

- Generate a caller with a one-return-statement callee. Assert the initial green boundary highlights, expanded ordinary child, and visible function button together. Include both call occurrences from the saved snapshot, and verify initial load/highlight refresh creates no component.
- Exercise the actual sidebar function button. Assert successful completion, a new reversible opaque child, and the existing brown Collapsed Compound State with the function/component label. Verify the caller boundaries, other call occurrence, surrounding transitions, sibling nodes, and unrelated folds remain intact.
- Verify repeated action is a no-op and an ordinary singleton nested in another function is completed through the existing recursive action. Retain negative checks for multi-node functions and a singleton place/compound child that does not satisfy the atomic-transition case.
- In separate graph copies, fold each eligible entrance/exit place both before and after explicit function folding, then locally unfold to the correct prior state. Preserve token and degree restrictions; not every function boundary should become green unconditionally.
- Verify weight/SM preservation, component naming, source/return metadata, unique component IDs, viewport preservation, and one final layout for the sidebar action.
- Save/open expanded and completed states, continue folding, and locally unfold. Restore the original ordinary transition, its hierarchy and exact arcs, including when a subsequent caller Sequence consumed the completed function. Confirm the function button reappears and another fold/unfold cycle succeeds.
- Re-run the existing Ticket 53 split/merge, mixed-parent rejection, and nested-restoration cases to retain the earlier protections.

Existing inspected tests cover multi-transition functions reducing to an opaque singleton and the two Choice boundary directions. They do not cover this starting state. A full test-suite run was not part of this inspection.

## Runnable diagnostic

Run this from the repository root with Node.js and the supplied snapshot at its recorded path. This command was run during inspection and completed in about half a second with exit status 1 and `{"failures":3,"cases":3}`. Each case printed `green: false` for both boundaries, `complete: false`, `collapsed: false`, and `passes: 0`.

The diagnostic asserts the required initial green boundaries and completion after the explicit function action. It is a focused reproduction rather than the complete acceptance suite: the implementing agent must additionally exercise the sidebar button, brown styling, preservation, and restoration requirements above.

```sh
node <<'JS'
const fs = require('fs'), vm = require('vm');
const base = process.cwd() + '/code2petri/viewer/';
const cytoscape = require(base + 'vendor/cytoscape.min.js');
const { LiveFoldReductionEngine } = require(base + 'engine/reduction_engine.js');
const save = JSON.parse(fs.readFileSync('/Users/pingchungtsai/Downloads/tic_tac_toe_global_foldable_session_save.json', 'utf8'));
const html = fs.readFileSync(base + 'template.html', 'utf8');
const tail = html.slice(html.indexOf('function updateFoldableHighlights()'));
const highlight = tail.slice(0, /\n      \}/.exec(tail).index + 8);
const n = (id, classes, parent) => ({group: 'nodes', classes,
  data: {id, ...(parent ? {parent} : {})}});
const minimal = [n('fn', 'compound'), n('before', 'transition'),
  n('entry', 'place'), n('body', 'transition', 'fn'), n('exit', 'place'),
  n('after', 'transition'),
  ...[['before','entry'],['entry','body'],['body','exit'],['exit','after']]
    .map(([source,target],i) => ({group:'edges',data:{id:'a'+i,source,target}}))];
minimal[0].data.is_compound = true;
let failures = 0;
for (const [label, elements, compoundId, boundaries] of [
  ['saved-first', save.elements, 'compound_create_board', ['p28', 'p29']],
  ['saved-second', save.elements, 'compound_inline_create_board_t123', ['p101', 'p102']],
  ['minimal', minimal, 'fn', ['entry', 'exit']]
]) {
  const cy = cytoscape({headless:true, elements});
  const foldEngine = new LiveFoldReductionEngine(cy);
  const context = {cy, foldEngine, LiveFoldReductionEngine};
  vm.createContext(context);
  vm.runInContext(highlight + '\nupdateFoldableHighlights();', context);
  const boundaryStates = boundaries.map(id => ({id,
    green:cy.$id(id).hasClass('contractible'),
    reason:foldEngine.canSinglePlaceContract(cy.$id(id)).reason || null}));
  const result = foldEngine.executeFoldEntireFunction(compoundId);
  const collapsed = cy.$id(compoundId).hasClass('collapsed-compound');
  const pass = boundaryStates.every(b => b.green) && result.complete && collapsed;
  console.log(JSON.stringify({label, boundaryStates, passes:result.passes,
    complete:result.complete, collapsed, pass}));
  if (!pass) failures++;
  cy.destroy();
}
console.log(JSON.stringify({failures, cases:3}));
process.exitCode = failures ? 1 : 0;
JS
```

## Validation and limits

The saved graph and isolated model reproduce the exact reported symptom using current production eligibility/highlight code. In-memory probes establish the completion prerequisite and show why shortcut fixes break display or unfolding. The original exported HTML was not opened or regenerated, and no production implementation, test files, source game files, or session-save data were modified.

The suggestions preserve [Boundary Place Unification](../../../docs/adr/0002-boundary-place-unification.md), the existing [local reduction rules](../../../docs/adr/0003-adopt-prom-local-reduction-algorithm.md), and [Component-Local Unfold](../../../GLOSSARY.md). The ticket remains open pending a safe implementation and its regression checks.
