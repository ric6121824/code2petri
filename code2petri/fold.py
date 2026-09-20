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
    MARKED_GRAPH = "marked_graph"
    STATE_MACHINE = "state_machine"
    WELL_STRUCTURED = "well_structured"
    UNSTRUCTURED = "unstructured"


PRIORITY_MAP: Dict[ComponentType, int] = {
    ComponentType.SEQUENCE: 1,
    ComponentType.CHOICE: 2,
    ComponentType.LOOP: 3,
    ComponentType.MARKED_GRAPH: 4,
    ComponentType.STATE_MACHINE: 5,
    ComponentType.WELL_STRUCTURED: 6,
    ComponentType.UNSTRUCTURED: 7,
}


@dataclass
class FoldConfig:
    """Configurable base penalty weights (rho) for structural folding.

    Default base penalty weights per Definition 21:
      sequence = 0.0
      choice = 1.0 (scales ProM 1.5x linear markup: tau_new = sum_tau * 1.5, omega = choice * sum_tau * 0.5;
               supersedes Lassen 2008 Definition 22 symmetry difference)
      loop = 3.0 (scales ProM 2.0x linear markup on loop body: tau_new = tau_src + tau_snk + 2.0 * tau_loop,
             omega = (loop / 3.0) * tau_loop; supersedes Lassen 2008 Definition 22 loop symmetry difference)
      marked_graph = 2.0
      state_machine = 2.0
      well_structured = 2.0
      unstructured = 7.0
    """
    sequence: float = 0.0
    choice: float = 1.0
    loop: float = 3.0
    marked_graph: float = 2.0
    state_machine: float = 2.0
    well_structured: float = 2.0
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
        for f_name in (
            "sequence",
            "choice",
            "loop",
            "marked_graph",
            "state_machine",
            "well_structured",
            "unstructured",
        ):
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
        self.trans_map: Dict[str, Transition] = {t.id: t for t in net.transitions}
        self.place_map: Dict[str, Place] = {p.id: p for p in net.places}
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
    use_subnet_degrees: bool = True,
) -> int:
    """Calculates the symmetry multiplier diff(X) per Definition 22 in subnet PN|C or net topology.

    diff(X) = ||{x in X | |x*| > 1}| - |{x in X | |*x| > 1}|| + 1
    where degrees are computed in the subnet projection PN|C (default) or full topology.
    """
    topo = net_or_topology if isinstance(net_or_topology, NetTopology) else NetTopology(net_or_topology)
    comp_set = set(component_node_ids)
    target_set = set(target_node_ids) if target_node_ids is not None else comp_set

    if use_subnet_degrees:
        subnet_out, subnet_in = topo.subnet_degrees(comp_set)
        splits = sum(1 for nid in target_set if subnet_out[nid] > 1)
        joins = sum(1 for nid in target_set if subnet_in[nid] > 1)
    else:
        splits = sum(1 for nid in target_set if topo.out_degree(nid) > 1)
        joins = sum(1 for nid in target_set if topo.in_degree(nid) > 1)

    return abs(splits - joins) + 1


def detect_sequences(
    net_or_topology: Union[PetriNet, NetTopology],
    config: Optional[FoldConfig] = None,
) -> List[Component]:
    """Detects single-place contraction candidates matching ProM 1 -> 1 -> 1 topology.

    A candidate is an intermediate place p with:
      - in_degree(p) == 1 and out_degree(p) == 1
      - initial_tokens == 0 (preserves marking state)
      - source_transition != sink_transition
      - out_degree(source_transition) == 1 (source only outputs to p)
      - in_degree(sink_transition) == 1 (sink only inputs from p)
    """
    cfg = config if config is not None else FoldConfig()
    topo = net_or_topology if isinstance(net_or_topology, NetTopology) else NetTopology(net_or_topology)
    sequences: List[Component] = []

    for place in sorted(topo.net.places, key=lambda p: p.id):
        # Do not contract marked places (preserves initial token state)
        if place.initial_tokens > 0:
            continue
        if topo.in_degree(place.id) != 1 or topo.out_degree(place.id) != 1:
            continue

        preds = topo.presets(place.id)
        succs = topo.postsets(place.id)
        t_src = next(iter(preds))
        t_snk = next(iter(succs))

        if t_src == t_snk:
            continue
        if topo.out_degree(t_src) != 1 or topo.in_degree(t_snk) != 1:
            continue

        sequences.append(
            Component(
                component_type=ComponentType.SEQUENCE,
                internal_node_ids={place.id},
                entrance=t_src,
                exit=t_snk,
                omega=cfg.sequence,
            )
        )

    return sequences


def _fold_first_candidate(
    net: PetriNet,
    candidates: List[Component],
    step_number: int,
) -> Optional[Tuple[PetriNet, FoldStep]]:
    """Helper to fold the first candidate component if any are detected."""
    if not candidates:
        return None
    return fold_component(net, candidates[0], step_number)


def fold_sequence(
    net: PetriNet,
    step_number: int,
    config: Optional[FoldConfig] = None,
) -> Optional[Tuple[PetriNet, FoldStep]]:
    """Performs Single-Place Contraction on an intermediate place connecting adjacent transitions per ProM (1 -> 1 -> 1)."""
    cfg = config if config is not None else FoldConfig()
    return _fold_first_candidate(net, detect_sequences(net, cfg), step_number)


fold_single_place_contraction = fold_sequence


def detect_choices(
    net_or_topology: Union[PetriNet, NetTopology],
    config: Optional[FoldConfig] = None,
) -> List[Component]:
    """Detects atomic parallel Choice components per ProM / Definition 18.

    Searches for sets of >= 2 transitions strictly connecting a single shared input place
    and a single shared output place. Note: Unlike strict ProM isolation which requires
    that p_source has no other outgoing transitions and p_sink has no other incoming
    transitions, this implementation generalizes Murata parallel transition reduction
    by grouping transitions by common target place. This allows folding parallel branches
    even in complex ASTs with fallthrough or multi-way branch routing.
    """
    cfg = config if config is not None else FoldConfig()
    topo = net_or_topology if isinstance(net_or_topology, NetTopology) else NetTopology(net_or_topology)
    choices: List[Component] = []
    seen_bundles: Set[Tuple[str, str]] = set()

    for p_source in sorted(topo.place_ids):
        # Group outgoing transitions by their unique target place
        target_groups: Dict[str, List[str]] = {}
        for tid in topo.postsets(p_source):
            if topo.in_degree(tid) == 1 and topo.out_degree(tid) == 1:
                target_place = next(iter(topo.postsets(tid)))
                if target_place != p_source:
                    target_groups.setdefault(target_place, []).append(tid)

        for p_sink, tids in sorted(target_groups.items()):
            if len(tids) < 2:
                continue

            bundle_key = (p_source, p_sink)
            if bundle_key in seen_bundles:
                continue
            seen_bundles.add(bundle_key)

            choice_trans = [t for t in topo.net.transitions if t.id in tids]
            sum_tau = sum(t.get_tau() for t in choice_trans)
            # ProM formula: 1.5x multiplier on the sum of weights: tau = sum_tau * 1.5
            # omega = config.choice * (sum_tau * 0.5)
            omega = cfg.choice * (sum_tau * 0.5)

            choices.append(
                Component(
                    component_type=ComponentType.CHOICE,
                    internal_node_ids=set(tids),
                    entrance=p_source,
                    exit=p_sink,
                    omega=omega,
                )
            )

    return choices


def fold_choice(
    net: PetriNet,
    step_number: int,
    config: Optional[FoldConfig] = None,
) -> Optional[Tuple[PetriNet, FoldStep]]:
    """Folds atomic parallel choice transitions between a shared input place and output place per ProM."""
    cfg = config if config is not None else FoldConfig()
    return _fold_first_candidate(net, detect_choices(net, cfg), step_number)


def detect_while(
    net_or_topology: Union[PetriNet, NetTopology],
    config: Optional[FoldConfig] = None,
) -> List[Component]:
    """Detects while loop candidates matching ProM 2-in/2-out place with self-loop transition.

    A candidate is an intermediate place p with:
      - in_degree(p) == 2 and out_degree(p) == 2
      - initial_tokens == 0 (preserves marking state)
      - exactly 1 shared transition t_loop in presets(p) & postsets(p) (self-looping transition)
      - in_degree(t_loop) == 1 and out_degree(t_loop) == 1
      - remaining source transition t_src with out_degree(t_src) == 1
      - remaining sink transition t_snk with in_degree(t_snk) == 1
    """
    cfg = config if config is not None else FoldConfig()
    topo = net_or_topology if isinstance(net_or_topology, NetTopology) else NetTopology(net_or_topology)
    while_loops: List[Component] = []

    for place in sorted(topo.net.places, key=lambda p: p.id):
        if place.initial_tokens > 0:
            continue
        if topo.in_degree(place.id) != 2 or topo.out_degree(place.id) != 2:
            continue

        preds = topo.presets(place.id)
        succs = topo.postsets(place.id)
        shared = preds & succs
        if len(shared) != 1:
            continue

        t_loop = next(iter(shared))
        t_src_set = preds - shared
        t_snk_set = succs - shared
        if len(t_src_set) != 1 or len(t_snk_set) != 1:
            continue

        t_src = next(iter(t_src_set))
        t_snk = next(iter(t_snk_set))

        # Check linearity of the three roles per ProM foldWhile()
        if topo.in_degree(t_loop) != 1 or topo.out_degree(t_loop) != 1:
            continue
        if topo.out_degree(t_src) != 1 or topo.in_degree(t_snk) != 1:
            continue

        loop_trans = topo.trans_map.get(t_loop)
        tau_loop = loop_trans.get_tau() if loop_trans is not None else 1.0
        # ProM formula: tau_new = tau(t_src) + tau(t_snk) + 2.0 * tau(t_loop)
        # In fold_component: tau_sum = tau(t_src) + tau(t_snk) + tau(t_loop)
        # Therefore, omega = (cfg.loop / 3.0) * tau_loop (when cfg.loop == 3.0, omega = 1.0 * tau_loop)
        omega = (cfg.loop / 3.0) * tau_loop

        while_loops.append(
            Component(
                component_type=ComponentType.LOOP,
                internal_node_ids={place.id, t_loop},
                entrance=t_src,
                exit=t_snk,
                omega=omega,
            )
        )

    return while_loops


def fold_while(
    net: PetriNet,
    step_number: int,
    config: Optional[FoldConfig] = None,
) -> Optional[Tuple[PetriNet, FoldStep]]:
    """Folds a while loop self-looping on a 2-in/2-out place per ProM foldWhile()."""
    cfg = config if config is not None else FoldConfig()
    return _fold_first_candidate(net, detect_while(net, cfg), step_number)


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
    config: Optional[FoldConfig] = None,
) -> List[Component]:
    """Detects simple directed cycles with a single entry place and a single exit arc."""
    cfg = config if config is not None else FoldConfig()
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

        # If entry_place is a canonical while loop (2-in/2-out sharing a self-loop transition),
        # detect_while handles it with the precise ProM loop body multiplier.
        if topo.in_degree(entry_place) == 2 and topo.out_degree(entry_place) == 2:
            preds = topo.presets(entry_place)
            succs = topo.postsets(entry_place)
            if len(preds & succs) == 1:
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
                omega=cfg.loop,
            )
        )

    return loops


def fold_loop(
    net: PetriNet,
    step_number: int,
    config: Optional[FoldConfig] = None,
) -> Optional[Tuple[PetriNet, FoldStep]]:
    """Folds an elementary cycle loop component."""
    cfg = config if config is not None else FoldConfig()
    return _fold_first_candidate(net, detect_loops(net, cfg), step_number)


def forward_reachability(topo: NetTopology, source_id: str, sink_id: str) -> Set[str]:
    """Computes the forward reachable set from source_id stopping at sink_id."""
    queue = [source_id]
    nodes = {source_id, sink_id}
    while queue:
        curr = queue.pop(0)
        for target in topo.postsets(curr):
            if target not in nodes:
                nodes.add(target)
                queue.append(target)
    return nodes


def backward_reachability(topo: NetTopology, sink_id: str, source_id: str) -> Set[str]:
    """Computes the backward reachable set from sink_id stopping at source_id."""
    queue = [sink_id]
    nodes = {sink_id, source_id}
    while queue:
        curr = queue.pop(0)
        for src in topo.presets(curr):
            if src not in nodes:
                nodes.add(src)
                queue.append(src)
    return nodes


def is_reachable(topo: NetTopology, source_id: str, sink_id: str) -> bool:
    """Returns True if sink_id is reachable from source_id via a directed path."""
    if source_id == sink_id:
        return True
    queue = [source_id]
    visited = {source_id}
    while queue:
        curr = queue.pop(0)
        for target in topo.postsets(curr):
            if target == sink_id:
                return True
            if target not in visited:
                visited.add(target)
                queue.append(target)
    return False


def find_sese_nodes(topo: NetTopology, source_id: str, sink_id: str) -> Optional[Set[str]]:
    """Returns the set of nodes in the SESE component bounded by (source_id, sink_id), or None.

    A pair (source, sink) forms a valid SESE component iff:
      sink is reachable from source,
      forward(source, sink) == backward(sink, source),
      and at least 2 transitions are contained within the component.
    """
    if not is_reachable(topo, source_id, sink_id):
        return None
    fwd = forward_reachability(topo, source_id, sink_id)
    bwd = backward_reachability(topo, sink_id, source_id)
    if fwd == bwd:
        trans_count = sum(1 for nid in fwd if topo.is_transition(nid))
        if trans_count > 1:
            return fwd
    return None


def detect_marked_graphs(
    net_or_topology: Union[PetriNet, NetTopology],
    config: Optional[FoldConfig] = None,
) -> List[Component]:
    """Detects maximal Marked Graph SESE components per ProM / Lassen Def. 17.

    A Marked Graph SESE component is bounded by transition pair (t_source, t_sink)
    where forward(t_source, t_sink) == backward(t_sink, t_source), contains > 1 transitions,
    and every place p in the component has in_degree(p) == 1 and out_degree(p) == 1.
    """
    cfg = config if config is not None else FoldConfig()
    topo = net_or_topology if isinstance(net_or_topology, NetTopology) else NetTopology(net_or_topology)
    candidates: List[Tuple[int, str, str, Set[str]]] = []

    for t_src in sorted(topo.trans_ids):
        for t_snk in sorted(topo.trans_ids):
            if t_src == t_snk:
                continue
            sese = find_sese_nodes(topo, t_src, t_snk)
            if sese is None:
                continue

            # Invariant: Every place in sese must have |*p| == 1 and |p*| == 1
            is_mg = True
            for nid in sese:
                if topo.is_place(nid):
                    if topo.in_degree(nid) != 1 or topo.out_degree(nid) != 1:
                        is_mg = False
                        break
            if not is_mg:
                continue

            candidates.append((len(sese), t_src, t_snk, sese))

    if not candidates:
        return []

    # ProM selects MAXIMAL marked graph
    candidates.sort(key=lambda x: (-x[0], x[1], x[2]))
    _, best_src, best_snk, best_nodes = candidates[0]

    diff = calculate_symmetry_multiplier(topo, best_nodes, use_subnet_degrees=False)

    comp_trans = [t for t in topo.net.transitions if t.id in best_nodes]
    tau_sum = sum(t.get_tau() for t in comp_trans)
    tau_new = sum(cfg.marked_graph * t.get_tau() for t in comp_trans) * diff
    omega = tau_new - tau_sum

    return [
        Component(
            component_type=ComponentType.MARKED_GRAPH,
            internal_node_ids=best_nodes - {best_src, best_snk},
            entrance=best_src,
            exit=best_snk,
            omega=omega,
        )
    ]


def fold_marked_graph(
    net: PetriNet,
    step_number: int,
    config: Optional[FoldConfig] = None,
) -> Optional[Tuple[PetriNet, FoldStep]]:
    """Folds maximal Marked Graph SESE component per ProM."""
    cfg = config if config is not None else FoldConfig()
    return _fold_first_candidate(net, detect_marked_graphs(net, cfg), step_number)


def detect_state_machines(
    net_or_topology: Union[PetriNet, NetTopology],
    config: Optional[FoldConfig] = None,
) -> List[Component]:
    """Detects maximal State Machine SESE components per ProM / Lassen Def. 17.

    A State Machine SESE component is bounded by place pair (p_source, p_sink)
    where forward(p_source, p_sink) == backward(p_sink, p_source), contains > 1 transitions,
    and every transition t in the component has in_degree(t) == 1 and out_degree(t) == 1.
    """
    cfg = config if config is not None else FoldConfig()
    topo = net_or_topology if isinstance(net_or_topology, NetTopology) else NetTopology(net_or_topology)
    candidates: List[Tuple[int, str, str, Set[str]]] = []

    for p_src in sorted(topo.place_ids):
        for p_snk in sorted(topo.place_ids):
            if p_src == p_snk:
                continue
            sese = find_sese_nodes(topo, p_src, p_snk)
            if sese is None:
                continue

            # Invariant: Every transition in sese must have |*t| == 1 and |t*| == 1
            is_state_machine = True
            for nid in sese:
                if topo.is_transition(nid):
                    if topo.in_degree(nid) != 1 or topo.out_degree(nid) != 1:
                        is_state_machine = False
                        break
            if not is_state_machine:
                continue

            candidates.append((len(sese), p_src, p_snk, sese))

    if not candidates:
        return []

    # ProM selects MAXIMAL state machine
    candidates.sort(key=lambda x: (-x[0], x[1], x[2]))
    _, best_src, best_snk, best_nodes = candidates[0]

    diff = calculate_symmetry_multiplier(topo, best_nodes, use_subnet_degrees=False)

    comp_trans = [t for t in topo.net.transitions if t.id in best_nodes]
    tau_sum = sum(t.get_tau() for t in comp_trans)
    tau_new = sum(cfg.state_machine * t.get_tau() for t in comp_trans) * diff
    omega = tau_new - tau_sum

    return [
        Component(
            component_type=ComponentType.STATE_MACHINE,
            internal_node_ids=best_nodes - {best_src, best_snk},
            entrance=best_src,
            exit=best_snk,
            omega=omega,
        )
    ]


def fold_state_machine(
    net: PetriNet,
    step_number: int,
    config: Optional[FoldConfig] = None,
) -> Optional[Tuple[PetriNet, FoldStep]]:
    """Folds maximal State Machine SESE component per ProM."""
    cfg = config if config is not None else FoldConfig()
    return _fold_first_candidate(net, detect_state_machines(net, cfg), step_number)


def detect_well_structured(
    net_or_topology: Union[PetriNet, NetTopology],
    config: Optional[FoldConfig] = None,
) -> List[Component]:
    """Detects maximal Well-Structured SESE components per ProM / Lassen Def. 18.

    A Well-Structured SESE component is bounded by place pair (p_source, p_sink)
    where forward(p_source, p_sink) == backward(p_sink, p_source), contains > 1 transitions,
    and exhibits no PT/TP handle confusion or internal cycles.
    """
    cfg = config if config is not None else FoldConfig()
    topo = net_or_topology if isinstance(net_or_topology, NetTopology) else NetTopology(net_or_topology)
    candidates: List[Tuple[int, str, str, Set[str]]] = []

    for p_src in sorted(topo.place_ids):
        for p_snk in sorted(topo.place_ids):
            if p_src == p_snk:
                continue
            sese = find_sese_nodes(topo, p_src, p_snk)
            if sese is None:
                continue

            # Invariant: no PT/TP confusion and no internal cycle
            is_ws = True
            for nid in sese:
                if nid != p_snk and topo.is_place(nid):
                    for tid in topo.postsets(nid):
                        if topo.out_degree(nid) > 1 and topo.in_degree(tid) > 1:
                            is_ws = False
                            break
                        if topo.in_degree(nid) > 1 and topo.in_degree(tid) > 1:
                            is_ws = False
                            break
                        if nid in forward_reachability(topo, tid, p_snk):
                            is_ws = False
                            break
                    if not is_ws:
                        break
            if not is_ws:
                continue

            candidates.append((len(sese), p_src, p_snk, sese))

    if not candidates:
        return []

    # ProM selects MAXIMAL well-structured component
    candidates.sort(key=lambda x: (-x[0], x[1], x[2]))
    _, best_src, best_snk, best_nodes = candidates[0]

    diff_p = calculate_symmetry_multiplier(
        topo, best_nodes, [nid for nid in best_nodes if topo.is_place(nid)], use_subnet_degrees=False
    )
    diff_t = calculate_symmetry_multiplier(
        topo, best_nodes, [nid for nid in best_nodes if topo.is_transition(nid)], use_subnet_degrees=False
    )

    comp_trans = [t for t in topo.net.transitions if t.id in best_nodes]
    tau_sum = sum(t.get_tau() for t in comp_trans)
    tau_new = sum(cfg.well_structured * t.get_tau() for t in comp_trans) * diff_p * diff_t
    omega = tau_new - tau_sum

    return [
        Component(
            component_type=ComponentType.WELL_STRUCTURED,
            internal_node_ids=best_nodes - {best_src, best_snk},
            entrance=best_src,
            exit=best_snk,
            omega=omega,
        )
    ]


def fold_well_structured(
    net: PetriNet,
    step_number: int,
    config: Optional[FoldConfig] = None,
) -> Optional[Tuple[PetriNet, FoldStep]]:
    """Folds maximal Well-Structured SESE component per ProM."""
    cfg = config if config is not None else FoldConfig()
    return _fold_first_candidate(net, detect_well_structured(net, cfg), step_number)


def _calculate_unstructured_omega(
    topo: NetTopology,
    p_c: Set[str],
    t_c: Set[str],
    f_c: Set[Tuple[str, str]],
    cfg: FoldConfig,
) -> float:
    """Calculates penalty omega for an unstructured subnet per Lassen Definition 22."""
    weight = 5 * (abs(len(f_c) - (len(p_c) + len(t_c))) + 1)
    if cfg.unstructured != 7.0:
        weight = (cfg.unstructured / 7.0) * weight

    diff_p = calculate_symmetry_multiplier(topo, p_c, p_c, use_subnet_degrees=False)
    diff_t = calculate_symmetry_multiplier(topo, t_c, t_c, use_subnet_degrees=False)

    trans_objs = [topo.trans_map[tid] for tid in t_c if tid in topo.trans_map]
    tau_sum = sum(t.get_tau() for t in trans_objs)
    tau_new = sum(weight * t.get_tau() for t in trans_objs) * diff_p * diff_t
    return tau_new - tau_sum


def detect_unstructured(net_or_topology: Any, config: Optional[FoldConfig] = None) -> List[Component]:
    """Detects an unstructured component per Definition 21/22 and ProM's foldUnstructured().

    Strategy:
    1. Minimal SESE knot isolation: searches for place pairs (p_source, p_sink) that form
       a valid SESE subnet (forward == backward, >1 transitions) and selects the MINIMAL
       subnet by node count, ensuring local irregularities (e.g. goto) are isolated.
    2. Global fallback: if no internal SESE pair exists, folds the entire remaining net
       bounded by source and sink places.
    """
    cfg = config if config is not None else FoldConfig()
    topo = net_or_topology if isinstance(net_or_topology, NetTopology) else NetTopology(net_or_topology)

    # 1. Minimal internal SESE knots
    candidates: List[Tuple[int, str, str, Set[str]]] = []
    for p_source in topo.net.places:
        for p_sink in topo.net.places:
            if p_source.id == p_sink.id:
                continue
            sese_nodes = find_sese_nodes(topo, p_source.id, p_sink.id)
            if sese_nodes is not None:
                candidates.append((len(sese_nodes), p_source.id, p_sink.id, sese_nodes))

    if candidates:
        # Select the MINIMAL component (isolates the exact unstructured knot per User Story 3)
        candidates.sort(key=lambda x: (x[0], x[1], x[2]))
        _, p_src_id, p_snk_id, comp_nodes = candidates[0]

        p_c = {nid for nid in comp_nodes if topo.is_place(nid)}
        t_c = {nid for nid in comp_nodes if topo.is_transition(nid)}
        f_c = {(u, v) for (u, v) in topo.direct_arcs if u in comp_nodes and v in comp_nodes}

        omega = _calculate_unstructured_omega(topo, p_c, t_c, f_c, cfg)

        return [
            Component(
                component_type=ComponentType.UNSTRUCTURED,
                internal_node_ids=comp_nodes - {p_src_id, p_snk_id},
                entrance=p_src_id,
                exit=p_snk_id,
                omega=omega,
            )
        ]

    # 2. Global fallback: whole net between source and sink places
    if len(topo.trans_ids) <= 1:
        return []

    source_candidates = topo.source_places()
    sink_candidates = topo.sink_places()
    p_src = source_candidates[0] if source_candidates else topo.net.places[0]
    p_snk = sink_candidates[0] if sink_candidates else topo.net.places[-1]
    if p_src.id == p_snk.id and len(topo.net.places) > 1:
        other_places = [p for p in topo.net.places if p.id != p_src.id]
        if other_places:
            p_snk = other_places[-1]

    p_c = set(topo.place_ids)
    t_c = set(topo.trans_ids)
    f_c = set(topo.direct_arcs)

    omega = _calculate_unstructured_omega(topo, p_c, t_c, f_c, cfg)

    internal_nodes = (p_c - {p_src.id, p_snk.id}) | t_c
    return [
        Component(
            component_type=ComponentType.UNSTRUCTURED,
            internal_node_ids=internal_nodes,
            entrance=p_src.id,
            exit=p_snk.id,
            omega=omega,
        )
    ]


def detect_components(net: PetriNet, config: Optional[FoldConfig] = None) -> List[Component]:
    """Detects all single-entry/single-exit structural components in net.

    Components are returned sorted per Definition 21:
    - Sequence (priority 1) -> Choice (priority 2) -> Loop (priority 3) -> Marked Graph (4)
      -> State Machine (5) -> Well Structured (6) -> Unstructured (7)
    - Ties broken by smallest internal node count (greedy, bottom-up reduction)
    - Fully deterministic secondary tie-breaking
    """
    if config is None:
        config = FoldConfig()

    topo = NetTopology(net)
    components: List[Component] = []
    components.extend(detect_sequences(topo, config))
    components.extend(detect_choices(topo, config))
    components.extend(detect_while(topo, config))
    components.extend(detect_loops(topo, config))

    # Macro-components are evaluated only if no elementary components are present per Definition 21
    if not components:
        components.extend(detect_marked_graphs(topo, config))
        components.extend(detect_state_machines(topo, config))
        components.extend(detect_well_structured(topo, config))

    # Unstructured components are evaluated as fallback per Definition 21 Priority 7
    if not components:
        components.extend(detect_unstructured(topo, config))

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
) -> Optional[Tuple[PetriNet, FoldStep]]:
    """Folds the minimal SESE knot or remaining irreducible net as an Unstructured component per ProM."""
    cfg = config if config is not None else FoldConfig()
    return _fold_first_candidate(net, detect_unstructured(net, cfg), step_number)


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
    Prioritizes fine-grained reductions, resolving unstructured knots via minimal SESE isolation.

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

    while not _is_trivial_workflow_net(current_net) and len(current_net.transitions) > 1:
        # Prioritize Sequence (Single-Place Contraction) -> Choice -> While (Loop)
        # -> Marked Graph -> State Machine -> Well Structured -> Elementary Loop
        # -> Unstructured (minimal SESE knot fallback) per ProM priority
        reduction_result = (
            fold_sequence(current_net, step_number, cfg)
            or fold_choice(current_net, step_number, cfg)
            or fold_while(current_net, step_number, cfg)
            or fold_marked_graph(current_net, step_number, cfg)
            or fold_state_machine(current_net, step_number, cfg)
            or fold_well_structured(current_net, step_number, cfg)
            or fold_loop(current_net, step_number, cfg)
            or fold_unstructured(current_net, step_number, cfg)
        )
        if reduction_result is not None:
            current_net, step = reduction_result
            steps.append(step)
            step_number += 1
            if step.component_type == ComponentType.UNSTRUCTURED:
                fully_reducible = False
                if len(current_net.transitions) <= 1 or len(current_net.places) <= 1:
                    break
            continue

        # Irreducible net with no further reduction possible
        break

    final_sm = current_net.transitions[0].get_tau() if current_net.transitions else 0.0

    return FoldResult(
        initial_net=initial_snapshot,
        steps=steps,
        final_sm=final_sm,
        fully_reducible=fully_reducible,
    )
