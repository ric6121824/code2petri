# Boundary Place Unification for Bipartite Graph Integrity

## Context

In Phase 2.5, Inline Expansion splices resolved callee Petri net subgraphs into caller Petri nets where opaque call transitions reside. The entrance of the callee subnet must receive control flow from the caller transition's preset place, and the exit of the callee subnet must transfer control flow to the caller transition's postset place.

## Status

Accepted

## Considered Options

- **Direct place-to-place arcs**: Creating arcs directly from the caller transition's preset place to the callee's start place ($p_{\\text{preset}} \\to p_{\\text{start}}$), and from the callee's sink place to the caller's postset place ($p_{\\text{sink}} \\to p_{\\text{postset}}$).
- **Synthetic intermediate transitions**: Inserting silent/empty transitions between the caller place and the callee place ($p_{\\text{preset}} \\to t_{\\text{enter}} \\to p_{\\text{start}}$).
- **Boundary place unification (place fusion)**: Redirecting incoming arcs from the caller's preset place directly to the callee's entrance transitions, and redirecting outgoing arcs from the callee's exit transitions directly to the caller's postset place, fusing the boundaries.

## Decision

Unify the boundary places by redirecting arcs directly:
1. All transitions in the callee that consume tokens from the callee's source place are rewired to consume tokens directly from the caller call transition's preset place.
2. All transitions in the callee that produce tokens into the callee's sink place are rewired to produce tokens directly into the caller call transition's postset place.
3. The callee's internal source and sink places and the caller's opaque call transition are deleted from the composite net.

## Rationale & Consequences

Petri nets are strictly bipartite directed graphs $(P, T, F)$ where flow relations connect places to transitions or transitions to places ($F \\subseteq (P \\times T) \\cup (T \\times P)$). Connecting caller places to callee places via direct arcs would introduce illegal place-to-place arcs ($P \\times P$), breaking reachability analysis and standard token game firing semantics.

Inserting synthetic intermediate transitions avoids bipartite violations but artificially inflates the net size, alters complexity metrics (Structuredness Metric SM), and introduces unobservable silent steps.

By performing boundary place unification (place fusion), bipartite graph integrity is strictly preserved, 1-safe sound token flow is maintained, and no synthetic intermediate transitions are required.
