# 18 — Fold Reduction Engine & SM Computation

**What to build:** Given a `PetriNet` and a `FoldConfig`, a fold function executes the full Lassen & van der Aalst reduction loop (Definition 23). At each iteration it detects the simplest remaining component (via Ticket 17's detection), replaces it with a weighted Dummy Transition ($t_C$) by rewiring boundary arcs per Definition 19, and accumulates the penalty $\omega$ onto the dummy's transition weight $\tau$.

The function returns a `FoldResult` containing: the ordered list of `FoldStep` snapshots (each recording the component type, consumed node IDs, dummy transition ID, $\omega$, $\tau$, running SM score, and the full `PetriNet` state after the fold), the final SM score (raw unnormalized $\tau$), and a boolean `fully_reducible` flag.

When the net is irreducible (no well-structured components found, multiple nodes remain), the algorithm treats all remaining internal nodes as a single Unstructured Component with $\rho = 7$, folds them into a final dummy transition, and terminates.

The penultimate fold state (the last snapshot before the final unstructured-block or final-collapse fold) is accessible from the `FoldResult` for static visual output rendering.

**Blocked by:** 17 — FoldConfig & Structural Component Detection.

**Status:** ready-for-agent

- [ ] `FoldStep` dataclass exists recording: step number, component type, consumed node IDs, dummy transition ID, $\omega$, $\tau$, running SM score, and the `PetriNet` snapshot at that step.
- [ ] `FoldResult` dataclass exists recording: the initial net, the ordered list of `FoldStep`s, the final SM score, the `fully_reducible` boolean, and a property/method to access the penultimate state.
- [ ] Dummy transitions are standard `Transition` instances with `metadata={"dummy": True, "component_type": "<type>", "tau": <float>}`.
- [ ] The fold function correctly rewires boundary arcs when replacing a component with $t_C$: preset places of the entrance arc to $t_C$, $t_C$ to postset places of the exit.
- [ ] The fold loop terminates correctly for fully-reducible nets (single final transition).
- [ ] The fold loop terminates correctly for irreducible nets (remaining block folded as Unstructured with $\rho = 7$).
- [ ] Accumulated $\tau$ on a dummy transition equals $\omega(C) + \sum_{t \in C} \tau(t)$, where internal transitions start at $\tau = 1$.
- [ ] Unit tests verify: a pure 3-transition sequence folds to 1 step with $\omega = 0$; a single XOR-split with 2 symmetric branches folds correctly with $\omega = 1$; a single loop folds with $\omega = 3$; a mixed net folds in the correct priority order; a known-irreducible net terminates with the unstructured penalty and `fully_reducible = False`.
- [ ] Unit tests verify that `FoldConfig` weight overrides change the computed $\omega$ and final SM score.
- [ ] `FoldResult` JSON serialization produces the schema documented in the grand plan (initial net, fold steps array, final SM).
- [ ] Existing tests continue to pass.
