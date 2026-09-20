# 3. Adopt ProM's Local Reduction Algorithm

Date: 2026-09-20

## Status

Accepted (Phase 2.6)

## Context

In Phase 2.5, we implemented the Structuredness Metric (SM) reduction engine using maximal pattern matchers for sequences, choices, and loops. However, AST-generated control flow often contains intermediate routing places (e.g., `p_split -> t_if -> p_branch_entry -> t_stmt -> p_merge`). These structurally correct but non-textbook topologies confounded our maximal detectors, preventing the algorithm from folding standard `if/else` and `while` blocks.

We analyzed `PNAnalysis.jar`, the ground-truth Java implementation of Lassen & van der Aalst's paper in the ProM framework. The analysis revealed that ProM does *not* search for maximal chains. Instead, it performs **local, single-place contractions** (removing one place at a time). This inherently collapses the intermediate AST routing places, transforming complex branches into atomic `p_split -> t_if -> p_merge` connections that are easily folded by subsequent passes. Furthermore, ProM uses bidirectional reachability ($forward(u, v) == backward(v, u)$) to detect Single-Entry Single-Exit (SESE) bounds for macro-components and unstructured knots.

## Decision

We will replace our maximal pattern matchers in `code2petri/fold.py` with direct Python ports of ProM's algorithms:
1. `foldSequence`: Single-place local contraction.
2. `foldChoice`: Atomic parallel branch collapse.
3. `foldWhile`: Local 2-in/2-out place self-loop collapse.
4. SESE invariant detection for the Unstructured fallback (targeting the *minimal* knot).

## Consequences

- **Positive:** Mathematically aligns our tool with the reference academic implementation.
- **Positive:** Automatically resolves AST branching anomalies without requiring pre-normalization or modifying the walkers.
- **Positive:** Step-by-step reduction is much finer-grained, providing better visual playback in the viewer.
- **Negative:** Completely replaces the existing logic in `fold.py`, requiring new unit tests.
