"""Structural component detection and fold configuration for Petri nets.

Implements structural component detection based on Lassen & van der Aalst (2008),
"Complexity Metrics for Workflow Nets", Definitions 16, 17, 18, 21, and 22.
"""

from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
import json
import os
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union

from code2petri.model import PetriNet, Place, Transition


class ComponentType(str, Enum):
    """Supported structural component types per Lassen & van der Aalst (2008)."""
    SEQUENCE = "sequence"
    CHOICE = "choice"
    LOOP = "loop"
    UNSTRUCTURED = "unstructured"


PRIORITY_MAP: Dict[ComponentType, int] = {
    ComponentType.SEQUENCE: 1,
    ComponentType.CHOICE: 2,
    ComponentType.LOOP: 3,
    ComponentType.UNSTRUCTURED: 7,
}


@dataclass
class FoldConfig:
    """Configurable base penalty weights (rho) for structural folding.

    Default base penalty weights per Definition 21:
      sequence = 0.0
      choice = 1.0
      marked_graph = 2.0
      loop = 3.0
      unstructured = 7.0
    """
    sequence: float = 0.0
    choice: float = 1.0
    marked_graph: float = 2.0
    loop: float = 3.0
    unstructured: float = 7.0

    @classmethod
    def load(cls, source: str) -> "FoldConfig":
        """Factory method to load FoldConfig from either a file path or JSON string."""
        if os.path.isfile(source):
            with open(source, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = json.loads(source)

        kwargs: Dict[str, float] = {}
        for f_name in ("sequence", "choice", "marked_graph", "loop", "unstructured"):
            if f_name in data:
                kwargs[f_name] = float(data[f_name])
        return cls(**kwargs)


@dataclass
class Component:
    """Represents a detected single-entry/single-exit structural component in a Petri net.

    Attributes:
        component_type: Type of the component (Sequence, Choice, Loop, etc.).
        internal_node_ids: Set of node IDs strictly internal to the component.
        entrance: Boundary entry node ID.
        exit: Boundary exit node ID.
        omega: Computed penalty weight per Definition 22.
    """
    component_type: ComponentType
    internal_node_ids: Set[str]
    entrance: str
    exit: str
    omega: float


@dataclass
class FoldStep:
    """Represents a single reduction step in the structural fold algorithm.

    Attributes:
        step_number: 1-indexed step number.
        component_type: Type of the component folded.
        consumed_node_ids: Set of node IDs consumed by this fold step.
        opaque_transition_id: ID of the generated opaque transition (e.g. 't_C1').
        omega: Penalty weight for this component per Definition 22.
        tau: Accumulated weight on the opaque transition.
        running_sm: Running SM score (sum of transition weights) after this step.
        snapshot: Snapshot of the PetriNet after this fold step.
    """
    step_number: int
    component_type: ComponentType
    consumed_node_ids: Set[str]
    opaque_transition_id: str
    omega: float
    tau: float
    running_sm: float
    snapshot: PetriNet

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step_number,
            "component_type": self.component_type.value,
            "folded_nodes": sorted(list(self.consumed_node_ids)),
            "opaque_transition": self.opaque_transition_id,
            "omega": float(self.omega),
            "tau": float(self.tau),
            "sm_score": float(self.running_sm),
            "net": self.snapshot.to_dict(),
        }


@dataclass
class FoldResult:
    """Represents the complete result of reducing a Petri net via Definition 23.

    Attributes:
        initial_net: Initial PetriNet prior to any reduction steps.
        steps: Ordered list of FoldStep snapshots.
        final_sm: Final Structuredness Metric score (raw unnormalized tau).
        fully_reducible: True if net reduced to a single transition with no unstructured fallback.
    """
    initial_net: PetriNet
    steps: List[FoldStep]
    final_sm: float
    fully_reducible: bool

    @property
    def penultimate_net(self) -> PetriNet:
        """Returns the PetriNet state immediately prior to the final fold."""
        if len(self.steps) >= 2:
            return self.steps[-2].snapshot
        return self.initial_net

    def to_dict(self) -> Dict[str, Any]:
        return {
            "initial_net": self.initial_net.to_dict(),
            "fold_steps": [s.to_dict() for s in self.steps],
            "final_sm": float(self.final_sm),
            "fully_reducible": bool(self.fully_reducible),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent) + "\n"

    def to_dot(self) -> str:
        """Serializes the penultimate fold state to Graphviz DOT format with the final SM score in the title."""
        return self.penultimate_net.to_dot(title=f"SM score = {self.final_sm}")

    def to_pnml(self) -> str:
        """Serializes the penultimate fold state to PNML format."""
        return self.penultimate_net.to_pnml()


class NetTopology:
    """Encapsulates indexed graph topology and queries for a PetriNet."""

    def __init__(self, net: PetriNet):
        self.net = net
        self.place_ids: Set[str] = {p.id for p in net.places}
        self.trans_ids: Set[str] = {t.id for t in net.transitions}
        self.preset: Dict[str, Set[str]] = defaultdict(set)
        self.postset: Dict[str, Set[str]] = defaultdict(set)
        self.direct_arcs: Set[Tuple[str, str]] = set()

        for arc in net.arcs:
            self.postset[arc.source.id].add(arc.target.id)
            self.preset[arc.target.id].add(arc.source.id)
            self.direct_arcs.add((arc.source.id, arc.target.id))

    def presets(self, node_id: str) -> Set[str]:
        return self.preset.get(node_id, set())

    def postsets(self, node_id: str) -> Set[str]:
        return self.postset.get(node_id, set())

    def in_degree(self, node_id: str) -> int:
        return len(self.preset.get(node_id, set()))

    def out_degree(self, node_id: str) -> int:
        return len(self.postset.get(node_id, set()))

    def source_places(self) -> List[Place]:
        """Returns places with in_degree == 0 or initial_tokens > 0."""
        return [p for p in self.net.places if self.in_degree(p.id) == 0 or p.initial_tokens > 0]

    def sink_places(self) -> List[Place]:
        """Returns places with out_degree == 0."""
        return [p for p in self.net.places if self.out_degree(p.id) == 0]


    def is_place(self, node_id: str) -> bool:
        return node_id in self.place_ids

    def is_transition(self, node_id: str) -> bool:
        return node_id in self.trans_ids

    def has_arc(self, source_id: str, target_id: str) -> bool:
        return (source_id, target_id) in self.direct_arcs

    def incoming_arcs(self, node_set: Set[str]) -> List[Tuple[str, str]]:
        """Returns all arcs (u, v) entering node_set from outside."""
        arcs: List[Tuple[str, str]] = []
        for target_id in node_set:
            for source_id in self.presets(target_id):
                if source_id not in node_set:
                    arcs.append((source_id, target_id))
        return arcs

    def outgoing_arcs(self, node_set: Set[str]) -> List[Tuple[str, str]]:
        """Returns all arcs (u, v) leaving node_set to outside."""
        arcs: List[Tuple[str, str]] = []
        for source_id in node_set:
            for target_id in self.postsets(source_id):
                if target_id not in node_set:
                    arcs.append((source_id, target_id))
        return arcs

    def subnet_degrees(self, comp_set: Set[str]) -> Tuple[Dict[str, int], Dict[str, int]]:
        """Calculates in-degree and out-degree within the component subnet PN|C."""
        subnet_out: Dict[str, int] = defaultdict(int)
        subnet_in: Dict[str, int] = defaultdict(int)
        for source_id in comp_set:
            for target_id in self.postsets(source_id):
                if target_id in comp_set:
                    subnet_out[source_id] += 1
                    subnet_in[target_id] += 1
        return subnet_out, subnet_in


def calculate_symmetry_multiplier(
    net_or_topology: Union[PetriNet, NetTopology],
    component_node_ids: Iterable[str],
    target_node_ids: Optional[Iterable[str]] = None,
) -> int:
    """Calculates the symmetry multiplier diff(X) per Definition 22 in subnet PN|C.

    diff(X) = ||{x in X | |x*| > 1}| - |{x in X | |*x| > 1}|| + 1
    where degrees are computed in the subnet projection PN|C.
    """
    topo = net_or_topology if isinstance(net_or_topology, NetTopology) else NetTopology(net_or_topology)
    comp_set = set(component_node_ids)
    target_set = set(target_node_ids) if target_node_ids is not None else comp_set

    subnet_out, subnet_in = topo.subnet_degrees(comp_set)

    splits = sum(1 for nid in target_set if subnet_out[nid] > 1)
    joins = sum(1 for nid in target_set if subnet_in[nid] > 1)

    return abs(splits - joins) + 1


def detect_sequences(
    net_or_topology: Union[PetriNet, NetTopology],
    config: FoldConfig,
) -> List[Component]:
    """Detects linear chains of place -> transition -> place with no branching.

    Per Definition 17 & 18:
    A sequence component is a maximal linear chain starting and ending with a place,
    containing >= 2 transitions with no internal branching.
    """
    topo = net_or_topology if isinstance(net_or_topology, NetTopology) else NetTopology(net_or_topology)

    def can_extend_backwards(place_id: str) -> bool:
        if topo.in_degree(place_id) != 1:
            return False
        preds = topo.presets(place_id)
        if len(preds) != 1:
            return False
        pred_trans = next(iter(preds))
        if topo.out_degree(pred_trans) != 1 or topo.in_degree(pred_trans) != 1:
            return False
        pred_places = topo.presets(pred_trans)
        if len(pred_places) != 1:
            return False
        pred_place = next(iter(pred_places))
        return topo.out_degree(pred_place) == 1

    # Place-started candidate start nodes
    start_places = [
        p_id for p_id in topo.place_ids
        if topo.out_degree(p_id) == 1 and not can_extend_backwards(p_id)
    ]

    sequences: List[Component] = []
    seen_transition_sets: Set[Tuple[str, ...]] = set()

    for start_p in start_places:
        chain = [start_p]
        visited = {start_p}
        curr = start_p

        while True:
            succs = topo.postsets(curr)
            if len(succs) != 1:
                break
            nxt = next(iter(succs))
            if nxt in visited:
                break  # Cycle encountered

            if topo.is_place(nxt):
                chain.append(nxt)
                visited.add(nxt)
                curr = nxt
                if topo.in_degree(nxt) != 1 or topo.out_degree(nxt) != 1:
                    break  # Split place, join place, or sink: cannot be internal, ends sequence here as exit
            else:  # nxt is a transition
                if topo.in_degree(nxt) != 1 or topo.out_degree(nxt) != 1:
                    break
                chain.append(nxt)
                visited.add(nxt)
                curr = nxt

        # Sequence must end at a place
        if not topo.is_place(chain[-1]):
            chain.pop()

        chain_transitions = [nid for nid in chain if topo.is_transition(nid)]
        if len(chain_transitions) >= 2 and len(chain) >= 3:
            trans_key = tuple(sorted(chain_transitions))
            if trans_key not in seen_transition_sets:
                seen_transition_sets.add(trans_key)
                entrance = chain[0]
                exit_node = chain[-1]
                # Internal nodes are strictly intermediate nodes between entrance and exit
                internal_nodes = set(chain[1:-1])

                sequences.append(
                    Component(
                        component_type=ComponentType.SEQUENCE,
                        internal_node_ids=internal_nodes,
                        entrance=entrance,
                        exit=exit_node,
                        omega=config.sequence,
                    )
                )

    return sequences


def detect_choices(
    net_or_topology: Union[PetriNet, NetTopology],
    config: FoldConfig,
) -> List[Component]:
    """Detects XOR-split/join Choice components per Definition 18.

    A Choice component has P_C = {p_i, p_o} and T_C = p_i* = *p_o with |T_C| >= 2.
    """
    topo = net_or_topology if isinstance(net_or_topology, NetTopology) else NetTopology(net_or_topology)
    choices: List[Component] = []

    for place in topo.net.places:
        p_split = place.id
        choice_transitions = topo.postsets(p_split)
        if len(choice_transitions) < 2:
            continue

        # Each transition must have only p_split as input and exactly one output
        valid_transitions = True
        target_places: Set[str] = set()

        for tid in choice_transitions:
            if topo.presets(tid) != {p_split} or topo.out_degree(tid) != 1:
                valid_transitions = False
                break
            target_places.add(next(iter(topo.postsets(tid))))

        if not valid_transitions or len(target_places) != 1:
            continue

        p_merge = next(iter(target_places))
        if p_merge == p_split:
            continue

        # p_merge must receive inputs exclusively from choice_transitions
        if topo.presets(p_merge) != choice_transitions:
            continue

        # No direct arc from p_merge to p_split (Definition 16: (o_C, i_C) not in F)
        if topo.has_arc(p_merge, p_split):
            continue

        component_nodes = {p_split, p_merge} | choice_transitions
        diff_val = calculate_symmetry_multiplier(topo, component_nodes, [p_split, p_merge])
        omega = config.choice * diff_val

        choices.append(
            Component(
                component_type=ComponentType.CHOICE,
                internal_node_ids=set(choice_transitions),
                entrance=p_split,
                exit=p_merge,
                omega=omega,
            )
        )

    return choices


def _find_elementary_cycles(net: PetriNet, topology: NetTopology) -> List[List[str]]:
    """Finds all elementary directed cycles in the Petri net."""
    nodes = sorted(list(topology.place_ids | topology.trans_ids))
    node_indices = {n: i for i, n in enumerate(nodes)}
    cycles: List[List[str]] = []

    for start_idx, start_node in enumerate(nodes):
        stack = [start_node]
        visited = {start_node}

        def dfs(curr: str) -> None:
            for neighbor in topology.postsets(curr):
                n_idx = node_indices.get(neighbor, -1)
                if n_idx < start_idx:
                    continue
                if neighbor == start_node:
                    cycles.append(list(stack))
                elif neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
                    dfs(neighbor)
                    stack.pop()
                    visited.remove(neighbor)

        dfs(start_node)

    return cycles


def detect_loops(
    net_or_topology: Union[PetriNet, NetTopology],
    config: FoldConfig,
) -> List[Component]:
    """Detects simple directed cycles with a single entry place and a single exit arc."""
    topo = net_or_topology if isinstance(net_or_topology, NetTopology) else NetTopology(net_or_topology)
    cycles = _find_elementary_cycles(topo.net, topo)
    loops: List[Component] = []
    seen_cycles: Set[Tuple[str, ...]] = set()

    for cycle in cycles:
        cycle_nodes = set(cycle)
        cycle_key = tuple(sorted(cycle))
        if cycle_key in seen_cycles:
            continue
        seen_cycles.add(cycle_key)

        in_arcs = topo.incoming_arcs(cycle_nodes)
        out_arcs = topo.outgoing_arcs(cycle_nodes)

        # Condition 1: Single entry place
        if in_arcs:
            entry_targets = {target_id for _, target_id in in_arcs}
            if len(entry_targets) != 1:
                continue
            entry_place = next(iter(entry_targets))
            if not topo.is_place(entry_place):
                continue
        else:
            entry_candidates = [
                p.id for p in topo.net.places
                if p.id in cycle_nodes and (topo.in_degree(p.id) == 0 or p.initial_tokens > 0)
            ]
            if len(entry_candidates) == 1:
                entry_place = entry_candidates[0]
            else:
                continue

        # Condition 2: Single exit arc
        if len(out_arcs) != 1:
            continue

        _, exit_target_id = out_arcs[0]

        # Definition 16: (o_C, i_C) not in F
        if topo.has_arc(exit_target_id, entry_place):
            continue

        # Internal nodes are strictly nodes in the cycle minus entry and exit target
        internal_nodes = (cycle_nodes - {entry_place}) - {exit_target_id}

        loops.append(
            Component(
                component_type=ComponentType.LOOP,
                internal_node_ids=internal_nodes,
                entrance=entry_place,
                exit=exit_target_id,
                omega=config.loop,
            )
        )

    return loops


def detect_components(net: PetriNet, config: Optional[FoldConfig] = None) -> List[Component]:
    """Detects all single-entry/single-exit structural components in net.

    Components are returned sorted per Definition 21:
    - Sequence (priority 1) -> Choice (priority 2) -> Loop (priority 3)
    - Ties broken by smallest internal node count (greedy, bottom-up reduction)
    - Fully deterministic secondary tie-breaking
    """
    if config is None:
        config = FoldConfig()

    topo = NetTopology(net)
    components: List[Component] = []
    components.extend(detect_sequences(topo, config))
    components.extend(detect_choices(topo, config))
    components.extend(detect_loops(topo, config))

    # Definition 21 sorting:
    # 1. priority rank (lowest integer = highest priority)
    # 2. internal node count (smallest first)
    # 3. entrance, exit, internal_node_ids (deterministic tie-breaking)
    components.sort(
        key=lambda c: (
            PRIORITY_MAP.get(c.component_type, 7),
            len(c.internal_node_ids),
            c.entrance,
            c.exit,
            sorted(list(c.internal_node_ids)),
        )
    )

    return components


def _add_opaque_transition(
    net: PetriNet,
    step_number: int,
    component_type: str,
    tau: float,
) -> Tuple[str, Transition]:
    """Adds a standard Transition representing an opaque folded component."""
    opaque_id = f"t_C{step_number}"
    opaque_t = net.add_transition(
        id=opaque_id,
        label=opaque_id,
        metadata={
            "opaque": True,
            "component_type": component_type,
            "tau": tau,
        },
    )
    return opaque_id, opaque_t


def fold_component(
    net: PetriNet,
    component: Component,
    step_number: int,
) -> Tuple[PetriNet, FoldStep]:
    """Replaces component C in net by a single opaque transition t_C per Definition 19.

    Args:
        net: The PetriNet containing component.
        component: The Component to fold.
        step_number: 1-indexed reduction step number.

    Returns:
        A tuple of (folded_petri_net, fold_step_record).
    """
    folded_net = net.clone()
    topo = NetTopology(folded_net)

    # 1. Determine consumed nodes
    consumed_node_ids: Set[str] = set(component.internal_node_ids)
    if topo.is_transition(component.entrance):
        consumed_node_ids.add(component.entrance)
    if topo.is_transition(component.exit):
        consumed_node_ids.add(component.exit)

    # 2. Identify all transitions belonging to component C
    comp_trans_ids = (consumed_node_ids | {component.entrance, component.exit}) & topo.trans_ids
    comp_transitions = [t for t in folded_net.transitions if t.id in comp_trans_ids]

    # 3. Calculate accumulated tau: tau(t_C) = omega(C) + sum(tau(t) for t in T_C)
    tau_sum = sum(t.get_tau() for t in comp_transitions)
    accumulated_tau = float(component.omega) + tau_sum

    # 4. Create fresh opaque transition t_C
    comp_type_str = component.component_type.value
    opaque_id, opaque_t = _add_opaque_transition(
        folded_net, step_number, comp_type_str, accumulated_tau
    )

    node_map = folded_net.get_node_map()

    # 5. Rewire boundary arcs per Definition 19
    if topo.is_place(component.entrance):
        folded_net.add_arc(node_map[component.entrance], opaque_t)
    else:
        for p_id in topo.presets(component.entrance):
            if p_id not in consumed_node_ids and p_id in node_map:
                folded_net.add_arc(node_map[p_id], opaque_t)

    if topo.is_place(component.exit):
        folded_net.add_arc(opaque_t, node_map[component.exit])
    else:
        for p_id in topo.postsets(component.exit):
            if p_id not in consumed_node_ids and p_id in node_map:
                folded_net.add_arc(opaque_t, node_map[p_id])

    # 6. Remove consumed nodes and any incident arcs
    folded_net.remove_nodes(consumed_node_ids)

    # 7. Compute running SM score: sum of all tau weights on remaining transitions
    running_sm = sum(t.get_tau() for t in folded_net.transitions)

    step = FoldStep(
        step_number=step_number,
        component_type=component.component_type,
        consumed_node_ids=consumed_node_ids,
        opaque_transition_id=opaque_id,
        omega=float(component.omega),
        tau=accumulated_tau,
        running_sm=running_sm,
        snapshot=folded_net.clone(),
    )

    return folded_net, step


def fold_unstructured(
    net: PetriNet,
    step_number: int,
    config: Optional[FoldConfig] = None,
) -> Tuple[PetriNet, FoldStep]:
    """Folds all remaining irreducible internal nodes as a single Unstructured component (rho = 7).

    Args:
        net: The irreducible PetriNet.
        step_number: 1-indexed reduction step number.
        config: Optional fold configuration.

    Returns:
        A tuple of (folded_petri_net, fold_step_record).
    """
    cfg = config if config is not None else FoldConfig()
    folded_net = net.clone()
    topo = NetTopology(folded_net)

    # Identify net entrance and exit places
    source_candidates = topo.source_places()
    sink_candidates = topo.sink_places()

    p_src = source_candidates[0] if source_candidates else folded_net.places[0]
    p_snk = sink_candidates[0] if sink_candidates else folded_net.places[-1]

    # If source and sink resolve to the same place but other places exist, pick a distinct sink
    if p_src.id == p_snk.id and len(folded_net.places) > 1:
        other_places = [p for p in folded_net.places if p.id != p_src.id]
        if other_places:
            p_snk = other_places[-1]

    # Consumed nodes: all transitions, and all places except p_src and p_snk
    consumed_places = {p.id for p in folded_net.places if p.id not in (p_src.id, p_snk.id)}
    consumed_transitions = {t.id for t in folded_net.transitions}
    consumed_node_ids = consumed_places | consumed_transitions

    tau_sum = sum(t.get_tau() for t in folded_net.transitions)
    omega = float(cfg.unstructured)
    accumulated_tau = omega + tau_sum

    opaque_id, opaque_t = _add_opaque_transition(
        folded_net, step_number, ComponentType.UNSTRUCTURED.value, accumulated_tau
    )

    # Retain only boundary places and the new opaque transition
    folded_net.remove_nodes(consumed_node_ids)
    folded_net.arcs = []

    node_map = folded_net.get_node_map()
    folded_net.add_arc(node_map[p_src.id], opaque_t)
    folded_net.add_arc(opaque_t, node_map[p_snk.id])

    running_sm = accumulated_tau

    step = FoldStep(
        step_number=step_number,
        component_type=ComponentType.UNSTRUCTURED,
        consumed_node_ids=consumed_node_ids,
        opaque_transition_id=opaque_id,
        omega=omega,
        tau=accumulated_tau,
        running_sm=running_sm,
        snapshot=folded_net.clone(),
    )

    return folded_net, step


def _is_trivial_workflow_net(net: PetriNet) -> bool:
    """Returns True if the net is reduced to a trivial workflow net (single transition connecting distinct source to sink)."""
    if len(net.transitions) == 0:
        return len(net.places) <= 1
    if len(net.transitions) == 1:
        t = net.transitions[0]
        topo = NetTopology(net)
        presets = topo.presets(t.id)
        postsets = topo.postsets(t.id)
        if len(presets) != 1 or len(postsets) != 1:
            return False
        p_in_id = next(iter(presets))
        p_out_id = next(iter(postsets))
        if p_in_id == p_out_id:
            return False
        if {p.id for p in net.places} != {p_in_id, p_out_id}:
            return False
        if topo.presets(p_in_id) or topo.postsets(p_out_id):
            return False
        return True
    return False


def fold_net(
    net: PetriNet,
    config: Optional[FoldConfig] = None,
) -> FoldResult:
    """Executes the full Lassen & van der Aalst reduction loop (Definition 23).

    Iteratively detects the simplest/smallest remaining component, folds it into an opaque
    transition, and accumulates the penalty omega onto the transition weight tau.
    If the net is irreducible, terminates with the unstructured penalty.

    Args:
        net: The target PetriNet to reduce.
        config: Optional FoldConfig base penalty configuration.

    Returns:
        FoldResult containing initial net, fold steps, final SM, and reducibility flag.
    """
    cfg = config if config is not None else FoldConfig()
    current_net = net.clone()
    initial_snapshot = current_net.clone()
    steps: List[FoldStep] = []
    step_number = 1
    fully_reducible = True

    while not _is_trivial_workflow_net(current_net):
        components = detect_components(current_net, cfg)
        if components:
            # Pick highest priority / smallest component per Definition 21
            best_comp = components[0]
            current_net, step = fold_component(current_net, best_comp, step_number)
            steps.append(step)
            step_number += 1
        else:
            # Irreducible net with multiple unreduced nodes remaining
            current_net, step = fold_unstructured(current_net, step_number, cfg)
            steps.append(step)
            fully_reducible = False
            break

    final_sm = current_net.transitions[0].get_tau() if current_net.transitions else 0.0

    return FoldResult(
        initial_net=initial_snapshot,
        steps=steps,
        final_sm=final_sm,
        fully_reducible=fully_reducible,
    )
