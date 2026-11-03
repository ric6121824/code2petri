# Phase 2.8.2 — Outcome-aware Structuredness Metric research

**Scope:** Read-only investigation following the user direction to keep final SM unavailable and continue seeking an outcome-aware metric. This note proposes no approved formula and changes no repository code, tickets, ADRs, or metric behavior.

## Finding

The inspected primary sources provide a lossless *semantic representation* for distinct terminal outcomes, but they do not provide an outcome-aware extension of the Lassen–van der Aalst Structuredness Metric (SM). The established SM is defined for a single-source/single-sink workflow net; each component has one source and one sink, and the algorithm replaces components with one transition until one transition remains. Its component weights are acknowledged by the authors as experience-based choices rather than uniquely derivable costs. Extending it to normal/exception multi-exit functions therefore needs a new component/interface definition and a declared metric scope. No source examined determines a unique scalar aggregation.

Keep `finalSmAvailable=false` for multi-outcome Call Refolding. The strongest outcome-aware direction to investigate next is a **multi-final-marking / multi-interface decomposition with outcome-indexed results**. This can preserve normal and exceptional completions without merging them; an overall scalar would remain unavailable until a scalarization rule is independently justified and approved.

## Evidence from primary sources and project contracts

1. **The SM's domain and reduction contract are single-exit.** Lassen and van der Aalst define a WF-net with a source and sink, define components using distinct single source/sink boundaries, and define SM as a sequence of folds that replaces each selected component by one transition until a trivial WF-net with one transition remains. Their Definition 23 describes that final transition as the output score. They also state that the component weight function cannot be proven “right”; it is an example based on experience. [Author-hosted paper, *Complexity Metrics for Workflow Nets*, Definitions 16, 19, 22, and 23](https://www.vdaalst.com/publications/p497.pdf#page=13) (see especially pp. 13–19).

   The implementation reflects this domain: `fold_net` completes only when `_is_trivial_workflow_net` finds one source, one sink, and one remaining transition; otherwise it returns `ReductionOutcome.INCOMPLETE` and no `final_sm`. See `/private/tmp/code2flow-phase-2.8.2-integration/code2petri/fold.py` around `fold_net`, `_is_trivial_workflow_net`, and `_workflow_net_rejection_reason`.

2. **Distinct final outcomes can be modeled without merging them.** Van der Aalst, Lohmann, and La Rosa define an open net as a Petri net plus a finite set `Ω` of final markings and a transition-label function. The paper explicitly contrasts this with an earlier WF-net approach limited to one final place and discusses multiple final markings and weak termination. This supports representing normal and exceptional completion as distinct labeled final markings. It defines behavioral correctness/configuration notions, not a structuredness score. [Author-hosted paper, *Ensuring Correctness During Process Configuration via Partner Synthesis*, Definitions 1–3 and discussion of multiple final markings](https://www.vdaalst.com/publications/p666.pdf#page=6).

3. **Multi-final-state substitution is related but does not define complexity.** The project’s research note summarizes Stahl and van der Aalst’s behavioral service-substitution model, which uses open nets and multiple possible final states to reason about replacement compatibility. That gives vocabulary for preserving an opaque function’s outcome interface. It supplies no SM component weights or scalarization rule. [Author-hosted paper, *Behavioral Service Substitution*](https://www.vdaalst.com/publications/p764.pdf#page=4); project summary: `/private/tmp/code2flow-phase-2.8.2-integration/.scratch/code2petri/research/phase-2.8.2-function-refolding-papers.md`.

4. **Project semantics require normal and exceptional outcomes to remain alternatives.** ADR 0006 retains separate `end` and `exception_end` places and models potentially raising operations as alternatives that consume the same input token. ADR 0007 rejects a scoring construction that authorizes deleting or conflating these interfaces. The Phase 2.8.2 question tree expressly says that a richer outcome-aware representation is an engineering alternative, not an approved formula. The existing disposable exit-place projection removes the distinction and cannot establish the score of the original graph.

## Outcome-aware candidates

### Candidate A: A set of labeled final markings and an outcome-indexed score profile

Represent a function by its initial marking, a finite set of terminal markings labeled by semantic outcome (for example, `normal` and `exception`), and the transition relation. Compute a result per outcome or per outcome class while retaining the output label in every reduction record. A profile could be exposed as `{normal: value, exception: value}` or, if route-specific weights are not defined, as a set of unreduced per-outcome residuals with explicit unavailability.

This is the least lossy research direction: it avoids the projection’s non-injective rewrite. It does **not** yet produce the scalar `final_sm` required by the present result type. Shared prefixes may appear in each outcome-conditioned calculation, so summing profiles would double-count them; taking max/min/mean or weighting by probabilities would introduce assumptions absent from the SM and source code. Keep any vector/profile as diagnostic research data, not a replacement final score, until shared-component accounting and compositionality are defined.

### Candidate B: A multi-port component with an outcome relation

Generalize a component interface from one source and one sink to an input plus a set of typed output ports and a relation that maps executions to those ports. A reduction summary could retain one shared function contribution and preserve the normal/exception mapping, then compose with caller context.

This could address the refolding problem more directly than an ordinary transition. However, the current Petri-net folding operation produces a transition with a single component interface. A plain transition that arcs to both outcome places fires to both places, which violates the project’s alternative-outcome semantics. A summary therefore needs richer semantics (for example, an outcome-labeled open-net component or a separate shared operation plus exclusive result-routing interface). The SM source does not define such multi-port component types, their recognition priorities, or their penalties. This is a new metric/interface extension and needs a preservation argument plus a named scope.

### Candidate C: Assign the existing Choice cost to a distinct-exit “Outcome Choice”

The existing Choice rule costs `1.5 × sum(τ)` for parallel transitions sharing a source and sink. One could hypothesize the same cost for branches sharing an entry but ending at different typed output ports, while storing the output relation rather than merging the exits. This would give the same scalar as the tested exit-place projection on the simple return/error example (4 including the condition), while retaining a separate semantic interface in the summary.

The paper’s Choice definition does not cover different exits, and no source examined supports this extension. Matching one example is insufficient: the new rule must specify whether different output interfaces are structurally one choice, how nested handlers and unstructured components compose with it, and how the summary avoids firing both outputs in Petri-net semantics. Treat this only as a falsifiable hypothesis.

## Why the previous projection is still not accepted

The experiment in [the project validation note](/private/tmp/code2flow-phase-2.8.2-integration/.scratch/code2petri/research/phase-2.8.2-scoring-projection-validation.md) validated the mechanics and independently reproduced single-exit controls (3 for the sequence and 160 for the Unstructured control); it derived 4 for the return/error example and 32 for nested handlers after redirecting exceptional completions to a common completion place on a disposable copy. The visible graph was unchanged, but the scoring projection maps two final markings to one. The result is a score of the quotient representation, not evidence that the original multi-outcome net has that SM. Relabeling the projection score would be a metric-scope change, which the user has not approved.

## Validation obligations for any future scalar

Before a candidate may set `finalSmAvailable=true` for a multi-outcome call, it should:

- define outcome labels/final markings and the semantic equivalence preserved by each fold;
- define component types, interface bounds, priority, penalty weights, and a fold operation that does not make one firing produce both normal and exception tokens;
- explain how shared prefixes and common subcomponents contribute once across outcomes;
- leave every existing single-exit control’s score unchanged, including sequence and genuinely Unstructured controls;
- independently derive expected values for a conditional return/error function and a nested handler with both caught and escaping exceptions;
- test multiple representations of the same labeled outcome behavior and state which representation changes are expected to affect the metric;
- establish compositionality: folding a nested outcome-aware component and then its caller must agree with the specified composition rule;
- compare traces/final-marking labels before and after summary, not just topology or numeric values;
- identify whether the proposed result remains “the existing SM” or is a separately named outcome-aware extension, and obtain an ADR/scope amendment before exposing it as a final scalar.

## Conclusion

Current literature supports richer Petri-net semantics for multiple final markings, and it supports behavioral replacement reasoning across interfaces. The inspected literature does not extend the project’s SM to that setting. An outcome-indexed profile or multi-port component is a viable next research seam, but neither defines a defensible scalar today. The implementation should continue to retain the graph, report the multi-outcome reduction as incomplete, and leave final SM unavailable while this research continues.
