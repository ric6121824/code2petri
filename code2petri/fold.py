"""Structural component detection and fold configuration for Petri nets.

Implements structural component detection based on Lassen & van der Aalst (2008),
"Complexity Metrics for Workflow Nets", Definitions 16, 17, 18, 21, and 22.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
import json
import os
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from code2petri.model import PetriNet


class ComponentType(str, Enum):
    """Supported structural component types per Lassen & van der Aalst (2008)."""
    SEQUENCE = "sequence"
    CHOICE = "choice"
    LOOP = "loop"
    MARKED_GRAPH = "marked_graph"
    UNSTRUCTURED = "unstructured"


PRIORITY_MAP: Dict[ComponentType, int] = {
    ComponentType.SEQUENCE: 1,
    ComponentType.CHOICE: 2,
    ComponentType.LOOP: 3,
    ComponentType.MARKED_GRAPH: 4,
    ComponentType.UNSTRUCTURED: 7,
}


@dataclass
class FoldConfig:
    """Configurable base penalty weights (rho) for structural folding.

    Default base penalty weights:
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
    def from_json(cls, json_str: str) -> "FoldConfig":
        """Creates a FoldConfig from a JSON string, applying defaults for omitted fields."""
        data = json.loads(json_str)
        kwargs: Dict[str, float] = {}
        for f_name in cls.__dataclass_fields__:
            if f_name in data:
                kwargs[f_name] = float(data[f_name])
        return cls(**kwargs)

    @classmethod
    def from_file(cls, file_path: str) -> "FoldConfig":
        """Loads a FoldConfig from a JSON configuration file."""
        with open(file_path, "r", encoding="utf-8") as f:
            return cls.from_json(f.read())

    @classmethod
    def load(cls, source: str) -> "FoldConfig":
        """Unified factory method to load FoldConfig from either a file path or JSON string."""
        if os.path.isfile(source):
            return cls.from_file(source)
        return cls.from_json(source)

    def to_dict(self) -> Dict[str, float]:
        """Serializes configuration to a dictionary."""
        return {
            "sequence": self.sequence,
            "choice": self.choice,
            "marked_graph": self.marked_graph,
            "loop": self.loop,
            "unstructured": self.unstructured,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serializes configuration to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


@dataclass
class Component:
    """Represents a detected single-entry/single-exit structural component in a Petri net.

    Attributes:
        component_type: Type of the component (Sequence, Choice, Loop, etc.).
        internal_node_ids: Set of node IDs strictly internal to the component.
        entrance: Boundary entry node ID belonging to the component.
        exit: Boundary exit node ID belonging to the component.
        omega: Computed penalty weight per Definition 22.
        priority: Priority rank per Definition 21 (1 = Sequence, 2 = Choice, 3 = Loop, etc.).
    """
    component_type: ComponentType
    internal_node_ids: Set[str]
    entrance: str
    exit: str
    omega: float
    priority: int = field(default=0)

    def __post_init__(self) -> None:
        if not self.priority:
            self.priority = PRIORITY_MAP.get(self.component_type, 7)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the Component into a JSON-compatible dictionary."""
        type_str = self.component_type.value if isinstance(self.component_type, ComponentType) else str(self.component_type)
        return {
            "component_type": type_str,
            "internal_node_ids": sorted(list(self.internal_node_ids)),
            "entrance": self.entrance,
            "exit": self.exit,
            "omega": self.omega,
            "priority": self.priority,
        }


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

    def is_place(self, node_id: str) -> bool:
        return node_id in self.place_ids

    def is_transition(self, node_id: str) -> bool:
        return node_id in self.trans_ids

    def has_arc(self, source_id: str, target_id: str) -> bool:
        return (source_id, target_id) in self.direct_arcs


def calculate_diff(
    net: PetriNet,
    component_node_ids: Iterable[str],
    target_node_ids: Optional[Iterable[str]] = None,
) -> int:
    """Calculates the symmetry multiplier diff(X) per Definition 22 in subnet PN|C.

    diff(X) = ||{x in X | |x*| > 1}| - |{x in X | |*x| > 1}|| + 1
    where degrees are computed in the subnet projection PN|C.
    """
    comp_set = set(component_node_ids)
    target_set = set(target_node_ids) if target_node_ids is not None else comp_set

    # Count in-degree and out-degree strictly within the component subnet PN|C
    subnet_out: Dict[str, int] = defaultdict(int)
    subnet_in: Dict[str, int] = defaultdict(int)

    for arc in net.arcs:
        if arc.source.id in comp_set and arc.target.id in comp_set:
            subnet_out[arc.source.id] += 1
            subnet_in[arc.target.id] += 1

    splits = sum(1 for nid in target_set if subnet_out[nid] > 1)
    joins = sum(1 for nid in target_set if subnet_in[nid] > 1)

    return abs(splits - joins) + 1


def detect_sequences(net: PetriNet, config: FoldConfig, topology: Optional[NetTopology] = None) -> List[Component]:
    """Detects linear chains of place -> transition -> place with no branching.

    Per Definition 17 & 18:
    A sequence component is a maximal linear chain starting and ending with a place,
    containing >= 2 transitions with no internal branching.
    """
    topo = topology if topology is not None else NetTopology(net)

    def can_extend_backwards(place_id: str) -> bool:
        if topo.in_degree(place_id) != 1:
            return False
        pred_trans = next(iter(topo.presets(place_id)))
        return topo.out_degree(pred_trans) == 1 and topo.in_degree(pred_trans) == 1

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
                if topo.in_degree(nxt) != 1:
                    break  # Join place, cannot enter
                chain.append(nxt)
                visited.add(nxt)
                curr = nxt
                if topo.out_degree(nxt) != 1:
                    break  # Split place or sink, chain ends
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


def detect_choices(net: PetriNet, config: FoldConfig, topology: Optional[NetTopology] = None) -> List[Component]:
    """Detects XOR-split/join Choice components per Definition 18.

    A Choice component has P_C = {p_i, p_o} and T_C = p_i* = *p_o with |T_C| >= 2.
    """
    topo = topology if topology is not None else NetTopology(net)
    choices: List[Component] = []

    for place in net.places:
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
        diff_val = calculate_diff(net, component_nodes, [p_split, p_merge])
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


def detect_loops(net: PetriNet, config: FoldConfig, topology: Optional[NetTopology] = None) -> List[Component]:
    """Detects simple directed cycles with a single entry place and a single exit arc."""
    topo = topology if topology is not None else NetTopology(net)
    cycles = _find_elementary_cycles(net, topo)
    loops: List[Component] = []
    seen_cycles: Set[Tuple[str, ...]] = set()

    for cycle in cycles:
        cycle_nodes = set(cycle)
        cycle_key = tuple(sorted(cycle))
        if cycle_key in seen_cycles:
            continue
        seen_cycles.add(cycle_key)

        in_arcs = [a for a in net.arcs if a.source.id not in cycle_nodes and a.target.id in cycle_nodes]
        out_arcs = [a for a in net.arcs if a.source.id in cycle_nodes and a.target.id not in cycle_nodes]

        # Condition 1: Single entry place
        if in_arcs:
            entry_targets = {a.target.id for a in in_arcs}
            if len(entry_targets) != 1:
                continue
            entry_place = next(iter(entry_targets))
            if not topo.is_place(entry_place):
                continue
        else:
            entry_candidates = [
                p.id for p in net.places
                if p.id in cycle_nodes and (topo.in_degree(p.id) == 0 or p.initial_tokens > 0)
            ]
            if len(entry_candidates) == 1:
                entry_place = entry_candidates[0]
            else:
                continue

        # Condition 2: Single exit arc
        if len(out_arcs) != 1:
            continue

        exit_arc = out_arcs[0]
        exit_boundary_node = exit_arc.source.id

        # Definition 16: (o_C, i_C) not in F (if exit_boundary is different from entry)
        if exit_boundary_node != entry_place and topo.has_arc(exit_boundary_node, entry_place):
            continue

        internal_nodes = cycle_nodes - {entry_place}

        loops.append(
            Component(
                component_type=ComponentType.LOOP,
                internal_node_ids=internal_nodes,
                entrance=entry_place,
                exit=exit_boundary_node,
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
    components.extend(detect_sequences(net, config, topo))
    components.extend(detect_choices(net, config, topo))
    components.extend(detect_loops(net, config, topo))

    # Definition 21 sorting:
    # 1. priority (lowest integer = highest priority)
    # 2. internal node count (smallest first)
    # 3. entrance, exit, internal_node_ids (deterministic tie-breaking)
    components.sort(
        key=lambda c: (
            c.priority,
            len(c.internal_node_ids),
            c.entrance,
            c.exit,
            sorted(list(c.internal_node_ids)),
        )
    )

    return components
