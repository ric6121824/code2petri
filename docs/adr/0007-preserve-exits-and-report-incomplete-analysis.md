# Preserve exit interfaces and report incomplete analysis honestly

Date: 2026-11-03

Status: accepted; implementation pending in Phase 2.8.2

Whole-net Unstructured fallback currently assumes that selecting one source and sink is sufficient, even when the graph contains another terminal outcome. The reproduced fold deletes the exceptional exit and produces an apparently final score. A detector-only repair is insufficient because execution can accept a supplied candidate, and the Python result path can label the first remaining transition's weight as final SM after no-progress.

Preserve normal and exceptional interfaces across both expansion paths and validate a proposed reduction's applicable boundary, marking, and arc assumptions before discovery exposes it and immediately before mutation. A graph outside those assumptions remains available for safe local reductions and export; it is not forced into one completion outcome to guarantee termination. The user selected continued diagram export with “Final SM unavailable—reduction incomplete,” with Accumulated Reduction Weight reported separately. Actual input/output errors retain ordinary failure behavior.

Keep Reduction Outcome distinct from the historical structural-reducibility flag: a valid completed reduction using Unstructured components is different from an incomplete analysis. Carry final-score availability through API results, CLI output, graph exports, the viewer, and sessions. This favors faithful graphs and truthful results over the former unconditional-looking final-score/termination behavior on unsupported inputs. Existing non-WF fallback expectations must not preserve an invalid numeric score merely because they are encoded in tests.

Call Refolding is a separate abstraction from Structural Fold. The user requires a simple return-or-error function to remain foldable without being classified as Unstructured solely because it has two outcomes. Preserve its accumulated contribution once and restore its pre-action diagram on local unfolding, including prior manual folds. The final scoring construction remains an engineering validation requirement; this decision does not approve a common-sink projection or a new penalty formula.

This amends the applicability of the whole-net fallback in [ADR 0003](./0003-adopt-prom-local-reduction-algorithm.md), preserves the outcome semantics of [ADR 0006](./0006-alternative-exception-outcomes.md), and uses the existing history contract in [ADR 0005](./0005-session-local-viewer-action-history.md). The canonical scope, confirmed test seams, and published Tickets 71–73 are in the [Phase 2.8.2 specification](../../.scratch/code2petri/specs/phase-2.8.2-call-refolding-and-exit-preservation.md).
