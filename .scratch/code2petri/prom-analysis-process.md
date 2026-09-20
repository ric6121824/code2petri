# ProM PNAnalysis.jar — Structuredness Metric & Structural Reduction Deep Dive

**Target Artifact:** `/Applications/prom-6.15-all-platforms/packages/pnanalysis-6.13.1/PNAnalysis.jar`  
**Primary Class Analyzed:** `org.processmining.pnanalysis.metrics.impl.PetriNetStructurednessMetric.java`  
**Author Reference:** K.B. Lassen and W.M.P. van der Aalst, *"Complexity Metrics for Workflow Nets"*, Information and Software Technology, 51(3):610–626, 2009.  
**Analysis Date:** 2026-09-20  
**Intended Reader:** Engineering & Reasoning Agents (e.g., Claude Opus, Antigravity) for Phase 2.6 design and implementation.

---

## 1. Executive Summary

`PNAnalysis.jar` contains the authoritative, reference open-source implementation of Lassen & van der Aalst's Structuredness Metric (SM) created by the original authors and their research group for the ProM process mining platform.

The most critical discovery from inspecting the decompiled source code is that **ProM implements fine-grained, local reductions rather than searching for maximal multi-transition chains upfront**:

1. **`foldSequence()` collapses exactly one intermediate place at a time.** It does not attempt to find an entire maximal sequence chain. It locates a place $p$ with $|*p| = 1$ and $|p*| = 1$ whose neighboring transitions satisfy local single-fan constraints, deletes $p$ and the downstream transition $t_{sink}$, and merges $t_{sink}$'s output arcs into $t_{source}$.
2. **This single architectural choice completely solves the AST branching dilemma.** In code2petri, an `if/else` statement constructs `p_split -> t_if -> p_branch -> t_stmt -> p_merge`. Because ProM's `foldSequence()` only inspects `p_branch` (which has in-degree 1 and out-degree 1), it contracts `t_if -> p_branch -> t_stmt` into `t_if` *before* choice detection runs, naturally producing `p_split -> t_if -> p_merge`.
3. **`foldChoice()` operates on simplified atomic branches.** It only triggers after intra-branch sequences have been folded down to single transitions directly bridging $p_{split}$ and $p_{merge}$.
4. **`foldWhile()` operates on self-loops on a single place.** Once the loop body reduces to a single transition looping from $p_{head}$ to $p_{head}$, `foldWhile()` matches the 2-in/2-out place pattern and eliminates the cycle.
5. **SESE components are identified via a bidirectional reachability intersection:**  
   $$\text{SESE}(s, e) \iff forward(s, e) == backward(e, s)$$
   This graph-theoretic invariant is used universally across `foldMarkedGraph`, `foldStateMachine`, `foldWellStructured`, and `foldUnstructured`.
6. **Maximal vs. Minimal Search Priority:**
   - Structured macro-components (`MarkedGraph`, `StateMachine`, `WellStructured`) select the **MAXIMAL** matching subnet ($|nodes|$ maximal).
   - Unstructured components select the **MINIMAL** matching subnet ($|nodes|$ minimal) to avoid blowing up the entire net in one step.

---

## 2. Pre-flight Workflow Net Validation & Normalization

Before initiating the reduction loop, `compute(PluginContext, Petrinet, Marking)` prepares the net:

```java
Petrinet clonedNet = PetrinetFactory.clonePetrinet(net);
// 1. Compute boundary sets:
// sourcePlaces: places with in-edges == 0
// sinkPlaces: places with out-edges == 0
// sourceTransitions: transitions with in-edges == 0
// sinkTransitions: transitions with out-edges == 0
```

### Synthetic Sink Normalization
If the net has:
- Exactly 1 source place ($|SourceP| = 1$)
- 0 sink places ($|SinkP| = 0$)
- 0 source transitions ($|SourceT| = 0$)
- Exactly 1 sink transition ($|SinkT| = 1$)

ProM automatically normalizes the net into a sound WF-net structure by creating a synthetic sink place:
```java
Place sinkPlace = clonedNet.addPlace("sink");
clonedNet.addArc(sinkTransitions.iterator().next(), sinkPlace);
sinkPlaces.add(sinkPlace);
```

### WF-Net Invariant Check
The reduction engine requires:
- $|SourceP| == 1$
- $|SinkP| == 1$
- $|SourceT| == 0$
- $|SinkT| == 0$

If violated, it aborts immediately with log `"Net is not a workflow net."` and returns `-1.0`.

### Transition Weight Initialization
Every transition $t \in T$ is assigned an initial weight $\tau(t) = 1.0$ in a map `metrics`:
```java
metrics = new HashMap<Transition, Double>();
for (Transition transition : clonedNet.getTransitions()) {
    metrics.put(transition, 1.0);
}
```

---

## 3. The Reduction Loop (`getMetric`)

The reduction loop is a deterministic, prioritized greedy loop:

```java
private double getMetric(Petrinet net) {
    while (net.getTransitions().size() > 1) {
        if (foldSequence())       continue;
        if (foldChoice())         continue;
        if (foldWhile())          continue;
        if (foldMarkedGraph())    continue;
        if (foldStateMachine())   continue;
        if (foldWellStructured()) continue;
        if (foldUnstructured())   continue;
    }
    return metrics.get(net.getTransitions().iterator().next());
}
```

### Key Loop Properties:
- **Priority Order:** Sequence $\to$ Choice $\to$ While $\to$ Marked Graph $\to$ State Machine $\to$ Well Structured $\to$ Unstructured.
- **Immediate Restart (`continue`):** As soon as *any* reduction rule succeeds, the loop immediately restarts from the highest-priority rule (`foldSequence()`). This guarantees that fine-grained local simplifications always take precedence over coarse macro-folds.
- **Termination:** Terminates when exactly 1 transition remains (`net.getTransitions().size() == 1`).
- **Final Result:** The return value is the scalar weight $\tau$ stored on the single surviving transition.

---

## 4. Detailed Reduction Pass Algorithms

### 4.1. `foldSequence()` — Local Place Contraction

Instead of finding an entire chain, `foldSequence()` scans for an internal place connecting two distinct transitions.

```java
private boolean foldSequence() {
    for (Place place : net.getPlaces()) {
        // Place must have exactly 1 in-edge and 1 out-edge
        if (net.getInEdges(place).size() != 1 || net.getOutEdges(place).size() != 1) {
            continue;
        }
        Transition sourceTransition = (Transition) net.getInEdges(place).iterator().next().getSource();
        Transition sinkTransition = (Transition) net.getOutEdges(place).iterator().next().getTarget();

        // Must be distinct transitions; source must only output to place; sink must only input from place
        if (sourceTransition == sinkTransition || 
            net.getOutEdges(sourceTransition).size() > 1 || 
            net.getInEdges(sinkTransition).size() > 1) {
            continue;
        }

        // --- CONTRACT ---
        net.removePlace(place);

        // Re-route sinkTransition's downstream edges to sourceTransition
        for (PetrinetEdge<?, ?> edge : net.getOutEdges(sinkTransition)) {
            net.addArc(sourceTransition, (Place) edge.getTarget());
        }

        net.removeTransition(sinkTransition);

        // Weight accumulation (Definition 22: Sequence omega = 0.0)
        metrics.put(sourceTransition, metrics.get(sourceTransition) + metrics.get(sinkTransition));
        return true;
    }
    return false;
}
```

#### Why This Works on ASTs:
Notice what is *not* constrained:
- $|*sourceTransition|$ is unrestricted! $sourceTransition$ can have multiple input arcs (e.g. from an `if` branch split place $p_{split}$).
- $|sinkTransition*|$ is unrestricted! $sinkTransition$ can have multiple output arcs (e.g. to a merge place $p_{merge}$).
Only the intermediate connection `sourceTransition -> place -> sinkTransition` must be strictly linear ($1 \to 1 \to 1$).

---

### 4.2. `foldChoice()` — Atomic Parallel Transition Collapse

`foldChoice()` searches for a set of $\ge 2$ transitions that strictly share the same single input place and single output place:

```java
private boolean foldChoice() {
    for (Transition transition : net.getTransitions()) {
        if (net.getInEdges(transition).size() != 1 || net.getOutEdges(transition).size() != 1) {
            continue;
        }
        Place sourcePlace = (Place) net.getInEdges(transition).iterator().next().getSource();
        Place sinkPlace = (Place) net.getOutEdges(transition).iterator().next().getTarget();
        if (sourcePlace == sinkPlace) {
            continue;
        }

        Set<Transition> targetTransitions = new HashSet<Transition>();
        Set<Transition> sourceTransitions = new HashSet<Transition>();

        // Collect all transitions exiting sourcePlace that only have 1 input
        for (PetrinetEdge<?, ?> edge : net.getOutEdges(sourcePlace)) {
            if (net.getInEdges(edge.getTarget()).size() == 1) {
                targetTransitions.add((Transition) edge.getTarget());
            }
        }
        // Collect all transitions entering sinkPlace that only have 1 output
        for (PetrinetEdge<?, ?> edge : net.getInEdges(sinkPlace)) {
            if (net.getOutEdges(edge.getSource()).size() == 1) {
                sourceTransitions.add((Transition) edge.getSource());
            }
        }

        if (targetTransitions.size() < 2 || !targetTransitions.equals(sourceTransitions)) {
            continue;
        }

        // --- CONTRACT ---
        double metric = 0.0;
        for (Transition targetTransition : targetTransitions) {
            metric += metrics.get(targetTransition);
            if (targetTransition != transition) {
                net.removeTransition(targetTransition);
            }
        }

        // ProM Implementation Formula: metric = sum * 1.5
        metric *= 1.5;
        metrics.put(transition, metric);
        return true;
    }
    return false;
}
```

#### Ground Truth Finding:
In Lassen & van der Aalst (2008), Definition 21 specifies base penalty $\rho(choice) = 1.0$, and Definition 22 adds symmetry multiplier $diff(X)$.
In ProM's `PetriNetStructurednessMetric.java`, the author implemented this directly as:
$$\tau_{new} = \left(\sum_{t \in T_{choice}} \tau(t)\right) \times 1.5$$
This acts as a fixed $50\%$ penalty markup on the branch alternatives.

---

### 4.3. `foldWhile()` — Self-Loop Place Reduction

`foldWhile()` looks for a place $p$ with in-degree 2 and out-degree 2, where one transition is an atomic loopback:

```java
private boolean foldWhile() {
    for (Place place : net.getPlaces()) {
        if (net.getInEdges(place).size() != 2 || net.getOutEdges(place).size() != 2) {
            continue;
        }

        Set<Transition> sourceTransitions = new HashSet<Transition>();
        for (PetrinetEdge<?, ?> edge : net.getInEdges(place)) sourceTransitions.add((Transition) edge.getSource());

        Set<Transition> targetTransitions = new HashSet<Transition>();
        for (PetrinetEdge<?, ?> edge : net.getOutEdges(place)) targetTransitions.add((Transition) edge.getTarget());

        // The loopback transition is in BOTH sourceTransitions and targetTransitions
        Set<Transition> sharedTransitions = new HashSet<Transition>(sourceTransitions);
        sharedTransitions.retainAll(targetTransitions);
        if (sharedTransitions.size() != 1) {
            continue;
        }

        sourceTransitions.removeAll(sharedTransitions);
        targetTransitions.removeAll(sharedTransitions);

        Transition sourceTransition = sourceTransitions.iterator().next();
        Transition sharedTransition = sharedTransitions.iterator().next();
        Transition sinkTransition = targetTransitions.iterator().next();

        // Check linearity of the three roles
        if (net.getInEdges(sharedTransition).size() != 1 || net.getOutEdges(sharedTransition).size() != 1) continue;
        if (net.getInEdges(sinkTransition).size() != 1 || net.getOutEdges(sourceTransition).size() != 1) continue;

        // --- CONTRACT ---
        net.removePlace(place);
        
        // Weight calculation:
        // tau(source) = tau(source) + tau(sink) + 2.0 * tau(shared)
        metrics.put(sourceTransition,
            metrics.get(sourceTransition) + metrics.get(sinkTransition) + 2.0 * metrics.get(sharedTransition));

        net.removeTransition(sharedTransition);

        // Re-route sinkTransition out-edges to sourceTransition
        for (PetrinetEdge<?, ?> edge : net.getOutEdges(sinkTransition)) {
            net.addArc(sourceTransition, (Place) edge.getTarget());
        }
        net.removeTransition(sinkTransition);
        return true;
    }
    return false;
}
```

#### Ground Truth Finding:
- The while loop assumes the loop body has already reduced to a single self-loop transition (`sharedTransition`).
- Penalty: $\tau(source) \leftarrow \tau(source) + \tau(sink) + 2.0 \times \tau(sharedTransition)$.
- The cycle body is doubled in weight ($2.0 \times \tau_{body}$).

---

### 4.4. SESE Subnet Detection Primitives (`forward` and `backward`)

For all macro-components (`MarkedGraph`, `StateMachine`, `WellStructured`, `Unstructured`), ProM detects candidate Single-Entry Single-Exit (SESE) regions using BFS/DFS reachability:

```java
private Set<PetrinetNode> forward(PetrinetNode sourceNode, PetrinetNode sinkNode) {
    List<PetrinetNode> toDo = new ArrayList<PetrinetNode>();
    toDo.add(sourceNode);
    Set<PetrinetNode> nodes = new HashSet<PetrinetNode>();
    nodes.add(sourceNode);
    nodes.add(sinkNode);
    while (!toDo.isEmpty()) {
        PetrinetNode node = toDo.remove(0);
        nodes.add(node);
        for (PetrinetEdge<?, ?> edge : net.getOutEdges(node)) {
            if (!nodes.contains(edge.getTarget())) {
                toDo.add(edge.getTarget());
                nodes.add(edge.getTarget());
            }
        }
    }
    return nodes;
}
```
`backward(sinkNode, sourceNode)` is identical, traversing upstream via `net.getInEdges()`.

#### Mathematical Principle:
A pair of boundary nodes $(u, v)$ defines a sound SESE component if and only if:
$$\text{forward}(u, v) == \text{backward}(v, u) \quad \text{and} \quad |T| > 1$$

---

### 4.5. `foldMarkedGraph()` — Parallel / Concurrency Reduction

- **Boundary Nodes:** Iterates over all transition pairs $(t_{source}, t_{sink})$.
- **SESE Check:** `forward(t_source, t_sink).equals(backward(t_sink, t_source))`.
- **Marked Graph Invariant:** Every place inside the forward set must have $|*p| == 1$ and $|p*| == 1$:
  ```java
  for (PetrinetNode node : forwardNodes) {
      if (node instanceof Place && (net.getInEdges(node).size() != 1 || net.getOutEdges(node).size() != 1)) {
          isMarkedGraph = false;
      }
  }
  ```
- **Selection:** Finds the **MAXIMAL** marked graph (`forwardNodes.size() > bestNodes.size()`).
- **Metric Formula:**
  $$diff = |\text{diffPre} - \text{diffPost}| + 1$$
  $$\tau_{new} = \left(\sum_{t \in C} 2.0 \times \tau(t)\right) \times diff$$
- **Contraction:** Re-links all out-edges of $t_{sink}$ to $t_{source}$, deletes all other nodes in $C$, assigns $\tau_{new}$ to $t_{source}$.

---

### 4.6. `foldStateMachine()` — Free Conflict Reduction

- **Boundary Nodes:** Iterates over all place pairs $(p_{source}, p_{sink})$.
- **SESE Check:** `forward(p_source, p_sink).equals(backward(p_sink, p_source))`.
- **State Machine Invariant:** Every transition inside the forward set must have $|*t| == 1$ and $|t*| == 1$:
  ```java
  for (PetrinetNode node : forwardNodes) {
      if (node instanceof Transition && (net.getInEdges(node).size() != 1 || net.getOutEdges(node).size() != 1)) {
          isStateMachine = false;
      }
  }
  ```
- **Selection:** Finds the **MAXIMAL** state machine (`forwardNodes.size() > bestNodes.size()`).
- **Metric Formula:**
  $$diff = |\text{diffPre} - \text{diffPost}| + 1$$
  $$\tau_{new} = \left(\sum_{t \in C} 2.0 \times \tau(t)\right) \times diff$$
- **Contraction:** Selects `survivorTransition` from $p_{source}*$, adds arc to $p_{sink}$, removes all other nodes, assigns $\tau_{new}$.

---

### 4.7. `foldWellStructured()` — Generalized Non-confusing Reduction

- **Boundary Nodes:** Iterates over place pairs $(p_{source}, p_{sink})$.
- **SESE Check:** `forward(p_source, p_sink).equals(backward(p_sink, p_source))`.
- **Well-Structured Conditions:** Checks for absence of PT/TP handle confusion:
  ```java
  for (PetrinetNode node : forwardNodes) {
      if (node != sinkNode && node instanceof Place) {
          for (PetrinetEdge<?, ?> outEdge : net.getOutEdges(node)) {
              if (net.getOutEdges(node).size() > 1 && net.getInEdges(outEdge.getTarget()).size() > 1) isWellStructured = false;
              if (net.getInEdges(node).size() > 1 && net.getInEdges(outEdge.getTarget()).size() > 1) isWellStructured = false;
              if (forward(outEdge.getTarget(), sinkNode).contains(node)) isWellStructured = false; // No internal cycles
          }
      }
  }
  ```
- **Selection:** Finds the **MAXIMAL** well-structured component.
- **Metric Formula:**
  $$diffPlace = |\text{diffPlacePre} - \text{diffPlacePost}| + 1$$
  $$diffTransition = |\text{diffTransitionPre} - \text{diffTransitionPost}| + 1$$
  $$\tau_{new} = \left(\sum_{t \in C} 2.0 \times \tau(t)\right) \times diffPlace \times diffTransition$$

---

### 4.8. `foldUnstructured()` — Minimal Knot Fallback

When all structured patterns fail:
- **Boundary Nodes:** Iterates over place pairs $(p_{source}, p_{sink})$.
- **SESE Check:** `forward(p_source, p_sink).equals(backward(p_sink, p_source))` with $|T| > 1$.
- **Selection:** Crucially, selects the **MINIMAL** component:
  ```java
  if (bestNodes.size() == 0 || forwardNodes.size() < bestNodes.size()) {
      bestNodes = forwardNodes;
      bestSourceNode = sourceNode;
      bestSinkNode = sinkNode;
  }
  ```
  *(Selecting the minimal SESE component isolates the exact unstructured knot rather than swallowing the entire workflow net into one penalty).*
- **Complexity Multiplier Calculation:**
  $$weight = 5 \times (| |F| - (|P| + |T|) | + 1)$$
  $$\tau_{new} = \left(\sum_{t \in C} weight \times \tau(t)\right) \times diffPlace \times diffTransition$$

---

## 5. Other Relevant Metrics in PNAnalysis.jar

1. **`PetriNetCardosoMetric.java` (Extended Cardoso Metric):**
   ```java
   int metric = 0;
   for (Place place : net.getPlaces()) {
       Set<Set<Place>> successorPlaces = new HashSet<Set<Place>>();
       for (DirectedGraphEdge<?, ?> placeEdge : net.getOutEdges(place)) {
           Set<Place> successors = new HashSet<Place>();
           for (DirectedGraphEdge<?, ?> transitionEdge : net.getOutEdges(placeEdge.getTarget())) {
               successors.add((Place) transitionEdge.getTarget());
           }
           successorPlaces.add(successors);
       }
       metric += successorPlaces.size();
   }
   return metric;
   ```
2. **`PetriNetCyclomaticMetric.java` (Extended Cyclomatic Metric):**
   Constructs the full reachability / coverability graph (up to 10,000 states) using `CyclomaticSemantics`. Analyzes Strongly Connected Components ($p$) and returns:
   $$M = |E| - |V| + p$$

---

## 6. Synthesis & Concrete Recommendations for code2petri Phase 2.6

| Component / Step | ProM Ground Truth Behavior | Recommended code2petri Adaptation |
|---|---|---|
| **Sequence Folding** | Folds **1 intermediate place** at a time ($t_1 \to p \to t_2$). Does not require boundary places to be degree-1. | Replace maximal sequence search with single-place contraction `fold_single_sequence_place()`. This automatically collapses `p_split -> t_if -> p_branch -> t_stmt -> p_merge` down to `p_split -> t_if -> p_merge`. |
| **Choice Folding** | Matches after branch bodies are collapsed. Collapses all parallel transitions between $p_{in}$ and $p_{out}$. Multiplies sum by $1.5$. | Keep `detect_choices()`, which will now match naturally once intra-branch sequences are collapsed. Use $1.5$ multiplier or maintain configurable $\rho=1.0 \times diff$. |
| **While Folding** | Matches a place with 2 in-edges and 2 out-edges with 1 shared loopback transition. | Ensure sequence reduction collapses the loop body into a direct self-loop transition before loop reduction runs. |
| **SESE Macro Detection** | Uses `forward(u, v) == backward(v, u)` reachability intersection. | Port the `forward == backward` BFS/DFS helper into `code2petri/fold.py`. This is standard, elegant, and $O(V+E)$. |
| **Marked Graph** | Max SESE where all places have in=1, out=1. Multiplier: $2.0 \times diff$. | Implement as optional/future-proof concurrency detector. |
| **Unstructured** | **Minimal** SESE where forward == backward. Multiplier: $5 \times (|F| - |P \cup T| + 1) \times diffP \times diffT$. | Change fallback from "whole net" to "minimal SESE knot" using `forward == backward`. |
