# Phase 2.8.2 Ticket 71 — exit-place scoring projection validation

**Read-only exploration at integration HEAD `10c7553b1c8459e0777ee2790a076123de88c0f7`.** No repository code or ticket files changed. I ran the examples directly through the public `code2petri.fold.fold_net` API using transient in-memory `PetriNet` values.

## Projection exercised

On a clone used only for scoring, retain the semantic normal exit place as the abstract completion place, redirect every incoming exceptional-exit arc to it with the same arc weight, then remove the exceptional exit place. The original graph retains its two distinct exit places and transition alternatives. The sample projection was accepted only for distinct, terminal, unmarked exit places; the entrance and visible graph were not modified.

## Results and independent calculations

| Example | Projected reductions | Independently derived result | API result |
| --- | --- | --- | --- |
| 3-transition sequence (single-exit control) | Sequence `(ω=0, τ: 1+1=2)`, then Sequence `(ω=0, τ=2+1=3)` | Final SM `3`, structured | `completed_structured`, `final_sm=3`, accumulated `3` |
| Conditional return/error | Two unit branches share the projected sink: Choice `(ω=1×(2×0.5)=1, τ=3)`; then Sequence combines the condition with that result `(ω=0, τ=1+3=4)` | Final SM `4`, structured; neither exit multiplicity nor the choice is classified Unstructured | `completed_structured`, `final_sm=4`, accumulated `4`. Without projection, the unchanged two-exit net remains incomplete (`whole-net fallback requires one sink place; found 2`). |
| Nested handler | First, inner rethrow + outer handler Sequence `(ω=0, τ=2)`; then normal-return/outer-exception Choice `(ω=1, τ=3)`; then the containing State Machine | Before the last fold, five transition weights sum to `8`; state-machine multiplier `2`; full-topology `diff=|2 split places − 1 join place|+1=2`; final `τ=2×8×2=32`, `ω=32−8=24`. Final class is State Machine, not Unstructured. | `completed_structured`, `final_sm=32`, accumulated `32`. Original two-exit graph is incomplete without projection. |
| Existing genuinely Unstructured single-exit milestone net | One Unstructured component | `|F|=9`, `|P|+|T|=8`, base factor `5×(|9−8|+1)=10`; two place splits vs one place join gives `diffP=2`; one transition join gives `diffT=2`; `τnew=(4 transitions×10)×2×2=160`; `ω=160−4=156` | `completed_unstructured`, `final_sm=160`, accumulated `160` |

The sequence and Unstructured calculations match the existing single-exit controls in `tests/test_fold_reduction.py:40-74, 300-335`. The relevant formulas are in `code2petri/fold.py:320-342, 378-430, 890-906, 1049-1122, 1353-1401`.

The nested sample has an inner call's exceptional alternative entering an inner handler; that handler can return normally or raise into an outer handler. After the inner outcomes rejoin, the function has an outer normal return and uncaught exception. The API's projected fold steps were: `sequence ω0 τ2`, `choice ω1 τ3`, `state_machine ω24 τ32`.

## Judgment

This experiment validates a **mechanically precise candidate scope**: “the existing SM of a function-net projection in which explicit terminal normal/exception outcomes are identified as one abstract completion.” On the tested examples it preserves the established single-exit controls, keeps the visible two-outcome net unchanged, gives the conditional return/error graph a valid Choice+Sequence reduction, and leaves nested caught/propagated exceptions in supported structural classes.

It does **not** show that this projection preserves the existing SM of the original multi-exit net. The projection is non-injective: the normal and exceptional final markings become the same abstract final marking, so callers cannot recover which outcome occurred from the scoring copy. The existing ProM/Lassen score is defined for its accepted single-source/single-sink workflow-net representation; applying it after this quotient defines a derived, outcome-erased score. The papers recorded in the project research note support single-sink WF-net metric assumptions and multi-final-state behavioral models separately; they do not establish that quotienting exception outcomes leaves SM invariant.

Therefore this is defensible only if Ticket 71 explicitly names the scoring scope as `SM(exit-quotiented function net)` (or similarly precise), keeps that score separate from the unchanged visible outcome graph, documents the semantic loss and any metric/ADR amendment, and reports the value as a score of that projection rather than claiming it is the unchanged SM of the original multi-exit net. Without that scope decision, it remains an unproven normalization for the requested call-level SM. The four checks are representative examples, not a general invariance argument.

## Preconditions and refusal cases

The tested projection is only plausible when all of the following hold:

- The scoring input is isolated to one function occurrence, and every mapped terminal is identified by validated normal/exception semantic provenance, not position or first/last list order.
- Normal and exceptional exit places are distinct, terminal (no outgoing arcs), unmarked, and represent mutually exclusive one-token completions. The projection preserves incoming arc weights.
- Every other terminal/interface is either given an explicit supported semantic role and deliberate mapping rule or causes the scoring projection to refuse. It must not silently consume arbitrary sinks, disconnected nodes, caller nodes, or sibling occurrences.
- Projection leaves the visible net, its alternative transition paths, and caller routing unchanged. It is performed on a disposable clone, never on the viewer's graph.
- The projected net still satisfies the reducer's accepted workflow/component preconditions. Unsupported non-unit arcs, invalid initial/interior markings, multiple sources, disconnected nodes, or unsupported interfaces continue to produce an incomplete result, not a forced score.
- A transition that fires to both outcome places is not made into an alternative by merging the places; reject that input unless the original model independently proves one terminal token per execution.

If accepted, the UI/API/export should identify this as a projected function score, while reduction-completion status and the visible graph's outcome semantics remain distinct. A final score from this projection must not be relabeled as evidence that the original multi-exit net is itself a WF-net or that its two final markings are behaviorally equivalent.
