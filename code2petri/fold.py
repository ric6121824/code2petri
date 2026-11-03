"""Structural component detection and fold configuration for Petri nets.

Implements structural component detection based on Lassen & van der Aalst (2008),
"Complexity Metrics for Workflow Nets", Definitions 16, 17, 18, 21, and 22.
"""

from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
import json
import math
import os
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple, Union
import xml.etree.ElementTree as ET

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


class ReductionOutcome(str, Enum):
    """Whether reduction completed and whether it required an Unstructured component."""

    COMPLETED_STRUCTURED = "completed_structured"
    COMPLETED_UNSTRUCTURED = "completed_unstructured"
    INCOMPLETE = "incomplete"


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
        final_sm: Final Structuredness Metric score, or None when reduction is incomplete.
        fully_reducible: Historical structural indicator, false if an Unstructured fold was used.
        outcome: Whether reduction completed through structured or Unstructured components.
        accumulated_weight: Sum of transition weights in the retained final net.
        incomplete_reason: Explanation for an incomplete result.
    """
    initial_net: PetriNet
    steps: List[FoldStep]
    final_sm: Optional[float]
    fully_reducible: bool
    outcome: ReductionOutcome
    accumulated_weight: float
    incomplete_reason: Optional[str] = None

    @property
    def final_net(self) -> PetriNet:
        """Returns the last retained reduction state, including an incomplete remainder."""
        return self.steps[-1].snapshot if self.steps else self.initial_net

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
            "final_net": self.final_net.to_dict(),
            "final_sm": float(self.final_sm) if self.final_sm is not None else None,
            "final_sm_available": self.final_sm is not None,
            "accumulated_reduction_weight": float(self.accumulated_weight),
            "reduction_outcome": self.outcome.value,
            "incomplete_reason": self.incomplete_reason,
            "fully_reducible": bool(self.fully_reducible),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent) + "\n"

    def to_dot(self) -> str:
        """Serializes the retained result net and includes its completion status in the title."""
        if self.outcome == ReductionOutcome.INCOMPLETE:
            return self.final_net.to_dot(title=self._incomplete_export_title())
        return self.penultimate_net.to_dot(title=f"SM score = {self.final_sm}")

    def to_pnml(self) -> str:
        """Serializes the appropriate fold state and records analysis status as tool metadata."""
        net = self.final_net if self.outcome == ReductionOutcome.INCOMPLETE else self.penultimate_net
        root = ET.fromstring(net.to_pnml())
        net_element = next((child for child in root if child.tag.endswith("net")), None)
        if net_element is None:
            raise ValueError("Generated PNML is missing its net element")
        namespace = root.tag[1:].split("}", 1)[0] if root.tag.startswith("{") else ""
        qualify = lambda tag: f"{{{namespace}}}{tag}" if namespace else tag
        toolspecific = ET.SubElement(
            net_element,
            qualify("toolspecific"),
            tool="code2petri",
            version="1.0",
        )
        properties = {
            "reduction_outcome": self.outcome.value,
            "final_sm_available": str(self.final_sm is not None).lower(),
            "accumulated_reduction_weight": str(self.accumulated_weight),
        }
        if self.final_sm is not None:
            properties["final_sm"] = str(self.final_sm)
        if self.incomplete_reason:
            properties["incomplete_reason"] = self.incomplete_reason
        for name, value in properties.items():
            prop = ET.SubElement(toolspecific, qualify("property"), name=name)
            text = ET.SubElement(prop, qualify("text"))
            text.text = value
        ET.indent(root, space="  ", level=0)
        return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")

    def _incomplete_export_title(self) -> str:
        title = f"Final SM unavailable — reduction incomplete (Accumulated Reduction Weight = {self.accumulated_weight:g})"
        if self.incomplete_reason:
            title += f" — {self.incomplete_reason}"
        return title


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
        self,
        component_node_ids: Iterable[str],
        target_node_ids: Optional[Iterable[str]] = None,
        use_subnet_degrees: bool = True,
    ) -> int:
        """Calculates the symmetry multiplier diff(X) per Definition 22 in subnet PN|C or net topology.

        diff(X) = ||{x in X | |x*| > 1}| - |{x in X | |*x| > 1}|| + 1
        where degrees are computed in the subnet projection PN|C (default) or full topology.
        """
        comp_set = set(component_node_ids)
        target_set = set(target_node_ids) if target_node_ids is not None else comp_set

        if use_subnet_degrees:
            subnet_out, subnet_in = self.subnet_degrees(comp_set)
            splits = sum(1 for nid in target_set if subnet_out[nid] > 1)
            joins = sum(1 for nid in target_set if subnet_in[nid] > 1)
        else:
            splits = sum(1 for nid in target_set if self.out_degree(nid) > 1)
            joins = sum(1 for nid in target_set if self.in_degree(nid) > 1)

        return abs(splits - joins) + 1


def _reachable_within(
    topo: NetTopology,
    start_id: str,
    allowed_ids: Set[str],
    reverse: bool = False,
) -> Set[str]:
    """Returns the nodes reachable from a boundary while staying in a candidate subnet."""
    neighbors = topo.presets if reverse else topo.postsets
    visited = {start_id}
    pending = [start_id]
    while pending:
        current = pending.pop()
        for neighbor in neighbors(current):
            if neighbor in allowed_ids and neighbor not in visited:
                visited.add(neighbor)
                pending.append(neighbor)
    return visited


def component_rejection_reason(net: PetriNet, component: "Component") -> Optional[str]:
    """Explains why replacing a candidate subnet would not preserve its interface or marking."""
    topo = NetTopology(net)
    node_ids = topo.place_ids | topo.trans_ids
    boundaries = {component.entrance, component.exit}
    interior = set(component.internal_node_ids)
    component_ids = boundaries | interior

    if component.entrance == component.exit:
        return "component source and sink must be distinct"
    missing = component_ids - node_ids
    if missing:
        return f"candidate references missing nodes: {', '.join(sorted(missing))}"
    if boundaries & interior:
        return "component boundaries cannot also be consumed interior nodes"
    if not any(tid in component_ids for tid in topo.trans_ids):
        return "candidate subnet contains no transitions"
    if component.exit not in _reachable_within(topo, component.entrance, component_ids):
        return "component sink is not reachable from its source"

    forward = _reachable_within(topo, component.entrance, component_ids)
    backward = _reachable_within(topo, component.exit, component_ids, reverse=True)
    if forward != component_ids or backward != component_ids:
        return "candidate does not cover every node on a source-to-sink path"

    for arc in net.arcs:
        source_id = arc.source.id
        target_id = arc.target.id
        source_inside = source_id in component_ids
        target_inside = target_id in component_ids
        if source_inside and not target_inside and source_id != component.exit:
            return f"candidate has an outgoing interface outside its sink at {source_id}"
        if target_inside and not source_inside and target_id != component.entrance:
            return f"candidate has an incoming interface inside its source at {target_id}"

    consumed_ids = interior | {
        boundary_id for boundary_id in boundaries if topo.is_transition(boundary_id)
    }
    affected_arc_pairs: Dict[Tuple[str, str], int] = defaultdict(int)
    for arc in net.arcs:
        pair = (arc.source.id, arc.target.id)
        if pair[0] in consumed_ids or pair[1] in consumed_ids or pair[0] in interior or pair[1] in interior:
            if arc.weight != 1:
                return f"candidate requires unsupported arc weight {arc.weight} on {pair[0]} -> {pair[1]}"
            affected_arc_pairs[pair] += 1
            if affected_arc_pairs[pair] > 1:
                return f"candidate contains parallel arcs on {pair[0]} -> {pair[1]}"

    for node_id in interior:
        place = topo.place_map.get(node_id)
        if place is not None and place.initial_tokens != 0:
            return f"candidate would consume marked place {node_id}"

    if not math.isfinite(float(component.omega)):
        return "candidate penalty must be a finite number"
    return None


def _workflow_net_rejection_reason(net: PetriNet) -> Optional[str]:
    """Checks whether whole-net fallback has one covered, unmarked workflow interface."""
    topo = NetTopology(net)
    source_places = [place for place in net.places if topo.in_degree(place.id) == 0]
    sink_places = [place for place in net.places if topo.out_degree(place.id) == 0]
    if len(source_places) != 1:
        return f"whole-net fallback requires one source place; found {len(source_places)}"
    if len(sink_places) != 1:
        return f"whole-net fallback requires one sink place; found {len(sink_places)}"
    source = source_places[0]
    sink = sink_places[0]
    if source.id == sink.id:
        return "whole-net fallback requires distinct source and sink places"

    all_node_ids = topo.place_ids | topo.trans_ids
    forward = _reachable_within(topo, source.id, all_node_ids)
    backward = _reachable_within(topo, sink.id, all_node_ids, reverse=True)
    if forward != all_node_ids or backward != all_node_ids:
        return "not every node lies on a source-to-sink path"

    for place in net.places:
        if place.id not in {source.id, sink.id} and place.initial_tokens != 0:
            return f"whole-net fallback would consume marked place {place.id}"
    return None


@dataclass(frozen=True)
class Subnet:
    """A structural subnet or SESE component within a Petri net.

    Encapsulates places, transitions, and internal arcs that travel together
    during structural reduction analysis and knot penalty calculation.
    """
    places: Set[str]
    transitions: Set[str]
    arcs: Set[Tuple[str, str]]

    @property
    def node_count(self) -> int:
        """Total number of nodes (places + transitions) in this subnet."""
        return len(self.places) + len(self.transitions)

    @property
    def arc_count(self) -> int:
        """Total number of internal directed arcs in this subnet."""
        return len(self.arcs)



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
    for candidate in candidates:
        if component_rejection_reason(net, candidate) is not None:
            continue
        return fold_component(net, candidate, step_number)
    return None


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


def _reachability(
    start_node: str,
    boundary_node: str,
    get_neighbors: Callable[[str], Iterable[str]],
) -> Set[str]:
    """Computes reachable set from start_node stopping at boundary_node."""
    queue = [start_node]
    nodes = {start_node, boundary_node}
    while queue:
        curr = queue.pop(0)
        for neighbor in get_neighbors(curr):
            if neighbor not in nodes:
                nodes.add(neighbor)
                queue.append(neighbor)
    return nodes


def forward_reachability(topo: NetTopology, source_id: str, sink_id: str) -> Set[str]:
    """Computes the forward reachable set from source_id stopping at sink_id."""
    return _reachability(source_id, sink_id, topo.postsets)


def backward_reachability(topo: NetTopology, sink_id: str, source_id: str) -> Set[str]:
    """Computes the backward reachable set from sink_id stopping at source_id."""
    return _reachability(sink_id, source_id, topo.presets)


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


def _find_sese_candidates(
    topo: NetTopology,
    boundary_ids: Optional[Iterable[str]] = None,
) -> Iterable[Tuple[str, str, Set[str]]]:
    """Yields (src, snk, sese_nodes) for all valid SESE pairs in boundary_ids.

    If boundary_ids is not provided, defaults to sorted topo.place_ids.
    """
    candidates = sorted(boundary_ids) if boundary_ids is not None else sorted(topo.place_ids)
    for src in candidates:
        for snk in candidates:
            if src == snk:
                continue
            sese = find_sese_nodes(topo, src, snk)
            if sese is not None:
                yield (src, snk, sese)


def _detect_macro(
    net_or_topology: Union[PetriNet, NetTopology],
    is_marked_graph: bool,
    config: Optional[FoldConfig] = None,
) -> List[Component]:
    """Helper to detect maximal Marked Graph or State Machine SESE components.

    - Marked Graph: bounded by transition pair, all internal places have in_degree == out_degree == 1.
    - State Machine: bounded by place pair, all internal transitions have in_degree == out_degree == 1.
    """
    cfg = config if config is not None else FoldConfig()
    topo = net_or_topology if isinstance(net_or_topology, NetTopology) else NetTopology(net_or_topology)
    candidates: List[Tuple[int, str, str, Set[str]]] = []

    boundary_ids = topo.trans_ids if is_marked_graph else topo.place_ids

    for src, snk, sese in _find_sese_candidates(topo, boundary_ids):
        valid = True
        for nid in sese:
            should_check = topo.is_place(nid) if is_marked_graph else topo.is_transition(nid)
            if should_check:
                if topo.in_degree(nid) != 1 or topo.out_degree(nid) != 1:
                    valid = False
                    break
        if not valid:
            continue

        candidates.append((len(sese), src, snk, sese))

    if not candidates:
        return []

    # ProM selects the maximal component, skipping any candidate that cannot be
    # represented by the supported boundary, marking, and arc contract.
    candidates.sort(key=lambda x: (-x[0], x[1], x[2]))
    comp_type = ComponentType.MARKED_GRAPH if is_marked_graph else ComponentType.STATE_MACHINE
    multiplier = cfg.marked_graph if is_marked_graph else cfg.state_machine
    for _, best_src, best_snk, best_nodes in candidates:
        diff = topo.calculate_symmetry_multiplier(best_nodes, use_subnet_degrees=False)
        comp_trans = [t for t in topo.net.transitions if t.id in best_nodes]
        tau_sum = sum(t.get_tau() for t in comp_trans)
        tau_new = sum(multiplier * t.get_tau() for t in comp_trans) * diff
        candidate = Component(
            component_type=comp_type,
            internal_node_ids=best_nodes - {best_src, best_snk},
            entrance=best_src,
            exit=best_snk,
            omega=tau_new - tau_sum,
        )
        if component_rejection_reason(topo.net, candidate) is None:
            return [candidate]
    return []


def detect_marked_graphs(
    net_or_topology: Union[PetriNet, NetTopology],
    config: Optional[FoldConfig] = None,
) -> List[Component]:
    """Detects maximal Marked Graph SESE components per ProM / Lassen Def. 16.

    A Marked Graph SESE component is bounded by transition pair (t_source, t_sink)
    where forward(t_source, t_sink) == backward(t_sink, t_source), contains > 1 transitions,
    and every place p in the component has in_degree(p) == 1 and out_degree(p) == 1.
    """
    return _detect_macro(net_or_topology, is_marked_graph=True, config=config)


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
    return _detect_macro(net_or_topology, is_marked_graph=False, config=config)


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

    for p_src, p_snk, sese in _find_sese_candidates(topo, topo.place_ids):
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

    # ProM selects the maximal valid well-structured component.
    candidates.sort(key=lambda x: (-x[0], x[1], x[2]))
    for _, best_src, best_snk, best_nodes in candidates:
        diff_p = topo.calculate_symmetry_multiplier(
            best_nodes, [nid for nid in best_nodes if topo.is_place(nid)], use_subnet_degrees=False
        )
        diff_t = topo.calculate_symmetry_multiplier(
            best_nodes, [nid for nid in best_nodes if topo.is_transition(nid)], use_subnet_degrees=False
        )

        comp_trans = [t for t in topo.net.transitions if t.id in best_nodes]
        tau_sum = sum(t.get_tau() for t in comp_trans)
        tau_new = sum(cfg.well_structured * t.get_tau() for t in comp_trans) * diff_p * diff_t
        candidate = Component(
            component_type=ComponentType.WELL_STRUCTURED,
            internal_node_ids=best_nodes - {best_src, best_snk},
            entrance=best_src,
            exit=best_snk,
            omega=tau_new - tau_sum,
        )
        if component_rejection_reason(topo.net, candidate) is None:
            return [candidate]
    return []


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
    subnet: Subnet,
    cfg: FoldConfig,
) -> float:
    """Calculates penalty omega for an unstructured subnet per Lassen Definition 22."""
    weight = 5 * (abs(subnet.arc_count - subnet.node_count) + 1)
    if cfg.unstructured != 7.0:
        weight = (cfg.unstructured / 7.0) * weight

    diff_p = topo.calculate_symmetry_multiplier(subnet.places, subnet.places, use_subnet_degrees=False)
    diff_t = topo.calculate_symmetry_multiplier(subnet.transitions, subnet.transitions, use_subnet_degrees=False)

    trans_objs = [topo.trans_map[tid] for tid in subnet.transitions if tid in topo.trans_map]
    tau_sum = sum(t.get_tau() for t in trans_objs)
    tau_new = sum(weight * t.get_tau() for t in trans_objs) * diff_p * diff_t
    return tau_new - tau_sum


def detect_unstructured(net_or_topology: Any, config: Optional[FoldConfig] = None) -> List[Component]:
    """Detects an unstructured component per Definition 21/22 and ProM's foldUnstructured().

    Strategy:
    1. Minimal SESE knot isolation: searches for place pairs (p_source, p_sink) that form
       a valid SESE subnet (forward == backward, >1 transitions) and selects the MINIMAL
       subnet by node count, ensuring local irregularities (e.g. goto) are isolated. Each
       candidate is revalidated for complete coverage, markings, interfaces, and weights.
    2. Whole-net fallback is available only for a connected, single-source/single-sink
       workflow net whose internal places and rewired arcs satisfy the supported contract.
    """
    cfg = config if config is not None else FoldConfig()
    topo = net_or_topology if isinstance(net_or_topology, NetTopology) else NetTopology(net_or_topology)

    # 1. Minimal internal SESE knots
    candidates: List[Tuple[int, str, str, Set[str]]] = []
    for p_src_id, p_snk_id, sese_nodes in _find_sese_candidates(topo, topo.place_ids):
        candidates.append((len(sese_nodes), p_src_id, p_snk_id, sese_nodes))

    if candidates:
        # Select the MINIMAL valid component (isolates the exact unstructured knot).
        candidates.sort(key=lambda x: (x[0], x[1], x[2]))
        for _, p_src_id, p_snk_id, comp_nodes in candidates:
            knot_subnet = Subnet(
                places={nid for nid in comp_nodes if topo.is_place(nid)},
                transitions={nid for nid in comp_nodes if topo.is_transition(nid)},
                arcs={(u, v) for (u, v) in topo.direct_arcs if u in comp_nodes and v in comp_nodes},
            )
            omega = _calculate_unstructured_omega(topo, knot_subnet, cfg)
            component = Component(
                component_type=ComponentType.UNSTRUCTURED,
                internal_node_ids=comp_nodes - {p_src_id, p_snk_id},
                entrance=p_src_id,
                exit=p_snk_id,
                omega=omega,
            )
            if component_rejection_reason(topo.net, component) is None:
                return [component]

    # 2. Global fallback: whole net only when its source/sink contract is justified.
    if len(topo.trans_ids) <= 1:
        return []

    if _workflow_net_rejection_reason(topo.net) is not None:
        return []

    p_src = next(place for place in topo.net.places if topo.in_degree(place.id) == 0)
    p_snk = next(place for place in topo.net.places if topo.out_degree(place.id) == 0)

    global_subnet = Subnet(
        places=set(topo.place_ids),
        transitions=set(topo.trans_ids),
        arcs=set(topo.direct_arcs),
    )

    omega = _calculate_unstructured_omega(topo, global_subnet, cfg)

    internal_nodes = (global_subnet.places - {p_src.id, p_snk.id}) | global_subnet.transitions
    component = Component(
        component_type=ComponentType.UNSTRUCTURED,
        internal_node_ids=internal_nodes,
        entrance=p_src.id,
        exit=p_snk.id,
        omega=omega,
    )
    return [component] if component_rejection_reason(topo.net, component) is None else []


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
    for detector in (detect_sequences, detect_choices, detect_while, detect_loops):
        components.extend(
            component for component in detector(topo, config)
            if component_rejection_reason(net, component) is None
        )

    # Macro-components are evaluated only if no elementary components are present per Definition 21
    if not components:
        for detector in (detect_marked_graphs, detect_state_machines, detect_well_structured):
            components.extend(
                component for component in detector(topo, config)
                if component_rejection_reason(net, component) is None
            )

    # Unstructured components are evaluated as fallback per Definition 21 Priority 7
    if not components:
        components.extend(
            component for component in detect_unstructured(topo, config)
            if component_rejection_reason(net, component) is None
        )

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
    rejection_reason = component_rejection_reason(net, component)
    if rejection_reason is not None:
        raise ValueError(f"Invalid reduction candidate: {rejection_reason}")

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
        return False
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
        expected_arcs = {(p_in_id, t.id), (t.id, p_out_id)}
        actual_arcs = [(arc.source.id, arc.target.id) for arc in net.arcs]
        if len(actual_arcs) != len(expected_arcs) or set(actual_arcs) != expected_arcs:
            return False
        if any(arc.weight != 1 for arc in net.arcs):
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

    while not _is_trivial_workflow_net(current_net):
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
            continue

        # Irreducible net with no further reduction possible
        break

    completed = _is_trivial_workflow_net(current_net)
    accumulated_weight = sum(t.get_tau() for t in current_net.transitions)
    if completed:
        final_sm = current_net.transitions[0].get_tau()
        outcome = (
            ReductionOutcome.COMPLETED_STRUCTURED
            if fully_reducible
            else ReductionOutcome.COMPLETED_UNSTRUCTURED
        )
        incomplete_reason = None
    else:
        final_sm = None
        outcome = ReductionOutcome.INCOMPLETE
        incomplete_reason = _reduction_incomplete_reason(current_net)

    return FoldResult(
        initial_net=initial_snapshot,
        steps=steps,
        final_sm=final_sm,
        fully_reducible=fully_reducible,
        outcome=outcome,
        accumulated_weight=accumulated_weight,
        incomplete_reason=incomplete_reason,
    )


def _reduction_incomplete_reason(net: PetriNet) -> str:
    """Returns the most useful reason a retained graph cannot claim a final SM."""
    if not net.transitions:
        return "no remaining transition can represent the complete workflow"
    workflow_reason = _workflow_net_rejection_reason(net)
    if workflow_reason is not None:
        return workflow_reason
    for arc in net.arcs:
        if arc.weight != 1:
            return f"unsupported arc weight {arc.weight} prevents a validated reduction"
    return "no eligible validated reduction remains; the graph is preserved"
