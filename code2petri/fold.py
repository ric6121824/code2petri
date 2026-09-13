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

from code2petri.model import PetriNet, Place, Transition, Arc


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
        internal_node_ids: Set of node IDs to be removed / folded into a dummy transition.
        entrance: Boundary entry node ID.
        exit: Boundary exit node ID.
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


def calculate_diff(net: PetriNet, node_ids: Iterable[str]) -> int:
    """Calculates the symmetry multiplier diff(X) per Definition 22:

    diff(X) = ||{x in X | |x*| > 1}| - |{x in X | |*x| > 1}|| + 1
    """
    node_set = set(node_ids)
    out_degree: Dict[str, int] = defaultdict(int)
    in_degree: Dict[str, int] = defaultdict(int)

    for arc in net.arcs:
        out_degree[arc.source.id] += 1
        in_degree[arc.target.id] += 1

    splits = sum(1 for nid in node_set if out_degree[nid] > 1)
    joins = sum(1 for nid in node_set if in_degree[nid] > 1)

    return abs(splits - joins) + 1


def detect_sequences(net: PetriNet, config: FoldConfig) -> List[Component]:
    """Detects maximal unbranching sequence components (chains of alternating places/transitions).

    Per Definition 17 & 18:
    A sequence component is a maximal linear chain containing >= 2 transitions
    with no internal branching.
    """
    preset: Dict[str, Set[str]] = defaultdict(set)
    postset: Dict[str, Set[str]] = defaultdict(set)
    place_ids = {p.id for p in net.places}
    trans_ids = {t.id for t in net.transitions}

    for arc in net.arcs:
        postset[arc.source.id].add(arc.target.id)
        preset[arc.target.id].add(arc.source.id)

    def can_extend_backwards(nid: str) -> bool:
        if nid in place_ids:
            if len(preset[nid]) != 1:
                return False
            pred = next(iter(preset[nid]))
            return len(postset[pred]) == 1 and len(preset[pred]) == 1
        else:  # transition
            if len(preset[nid]) != 1 or len(postset[nid]) != 1:
                return False
            pred = next(iter(preset[nid]))
            return len(postset[pred]) == 1

    # Identify candidate start nodes of maximal sequences
    start_nodes: List[str] = []

    # Places that can start a chain
    for p_id in place_ids:
        if len(postset[p_id]) == 1 and not can_extend_backwards(p_id):
            start_nodes.append(p_id)

    # Transitions that can start a TT chain (e.g. branch out of an XOR-split)
    for t_id in trans_ids:
        if len(preset[t_id]) == 1 and len(postset[t_id]) == 1 and not can_extend_backwards(t_id):
            start_nodes.append(t_id)

    sequences: List[Component] = []
    seen_transition_sets: Set[Tuple[str, ...]] = set()

    for start in start_nodes:
        chain = [start]
        visited = {start}
        curr = start

        while True:
            succs = postset[curr]
            if len(succs) != 1:
                break
            nxt = next(iter(succs))
            if nxt in visited:
                break  # Cycle, not a simple linear sequence

            if nxt in place_ids:
                if len(preset[nxt]) != 1:
                    break  # Join place, cannot enter
                chain.append(nxt)
                visited.add(nxt)
                curr = nxt
                if len(postset[nxt]) != 1:
                    break  # Split place or sink, chain ends
            else:  # nxt is a transition
                if len(preset[nxt]) != 1 or len(postset[nxt]) != 1:
                    break
                chain.append(nxt)
                visited.add(nxt)
                curr = nxt

        # Count transitions in chain
        chain_transitions = [nid for nid in chain if nid in trans_ids]
        if len(chain_transitions) >= 2:
            trans_key = tuple(sorted(chain_transitions))
            if trans_key not in seen_transition_sets:
                seen_transition_sets.add(trans_key)
                entrance = chain[0]
                exit_node = chain[-1]
                if entrance in place_ids and exit_node in place_ids:
                    internal_nodes = set(chain[1:-1]) | set(chain_transitions)
                else:
                    internal_nodes = set(chain)

                sequences.append(
                    Component(
                        component_type=ComponentType.SEQUENCE,
                        internal_node_ids=internal_nodes,
                        entrance=entrance,
                        exit=exit_node,
                        omega=config.sequence,
                        priority=PRIORITY_MAP[ComponentType.SEQUENCE],
                    )
                )

    return sequences


def detect_choices(net: PetriNet, config: FoldConfig) -> List[Component]:
    """Detects XOR-split/join Choice components per Definition 18.

    A Choice component has P_C = {p_i, p_o} and T_C = p_i* = *p_o with |T_C| >= 2.
    """
    preset: Dict[str, Set[str]] = defaultdict(set)
    postset: Dict[str, Set[str]] = defaultdict(set)
    direct_arcs: Set[Tuple[str, str]] = set()

    for arc in net.arcs:
        postset[arc.source.id].add(arc.target.id)
        preset[arc.target.id].add(arc.source.id)
        direct_arcs.add((arc.source.id, arc.target.id))

    choices: List[Component] = []

    for place in net.places:
        p_split = place.id
        t_c = postset[p_split]
        if len(t_c) < 2:
            continue

        # Each transition must have only p_split as input and exactly one output
        valid_transitions = True
        target_places: Set[str] = set()

        for tid in t_c:
            if preset[tid] != {p_split} or len(postset[tid]) != 1:
                valid_transitions = False
                break
            target_places.add(next(iter(postset[tid])))

        if not valid_transitions or len(target_places) != 1:
            continue

        p_merge = next(iter(target_places))
        if p_merge == p_split:
            continue

        # p_merge must receive inputs exclusively from T_C
        if preset[p_merge] != t_c:
            continue

        # No direct arc from p_merge to p_split (Definition 16: (o_C, i_C) not in F)
        if (p_merge, p_split) in direct_arcs:
            continue

        diff_val = calculate_diff(net, [p_split, p_merge])
        omega = config.choice * diff_val

        choices.append(
            Component(
                component_type=ComponentType.CHOICE,
                internal_node_ids=set(t_c),
                entrance=p_split,
                exit=p_merge,
                omega=omega,
                priority=PRIORITY_MAP[ComponentType.CHOICE],
            )
        )

    return choices


def _find_elementary_cycles(net: PetriNet) -> List[List[str]]:
    """Finds all elementary directed cycles in the Petri net."""
    adj: Dict[str, List[str]] = defaultdict(list)
    for arc in net.arcs:
        adj[arc.source.id].append(arc.target.id)

    nodes = sorted(list({p.id for p in net.places} | {t.id for t in net.transitions}))
    node_indices = {n: i for i, n in enumerate(nodes)}
    cycles: List[List[str]] = []

    for start_idx, start_node in enumerate(nodes):
        stack = [start_node]
        visited = {start_node}

        def dfs(curr: str) -> None:
            for neighbor in adj.get(curr, []):
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


def detect_loops(net: PetriNet, config: FoldConfig) -> List[Component]:
    """Detects simple directed cycles with a single entry place and a single exit arc."""
    place_ids = {p.id for p in net.places}
    preset: Dict[str, Set[str]] = defaultdict(set)
    direct_arcs: Set[Tuple[str, str]] = set()

    for arc in net.arcs:
        preset[arc.target.id].add(arc.source.id)
        direct_arcs.add((arc.source.id, arc.target.id))

    cycles = _find_elementary_cycles(net)
    loops: List[Component] = []
    seen_cycles: Set[Tuple[str, ...]] = set()

    for cycle in cycles:
        v_cycle = set(cycle)
        cycle_key = tuple(sorted(cycle))
        if cycle_key in seen_cycles:
            continue
        seen_cycles.add(cycle_key)

        in_arcs = [a for a in net.arcs if a.source.id not in v_cycle and a.target.id in v_cycle]
        out_arcs = [a for a in net.arcs if a.source.id in v_cycle and a.target.id not in v_cycle]

        # Condition 1: Single entry place
        if in_arcs:
            entry_targets = {a.target.id for a in in_arcs}
            if len(entry_targets) != 1:
                continue
            entry_place = next(iter(entry_targets))
            if entry_place not in place_ids:
                continue
        else:
            entry_candidates = [
                p.id for p in net.places
                if p.id in v_cycle and (len(preset[p.id]) == 0 or p.initial_tokens > 0)
            ]
            if len(entry_candidates) == 1:
                entry_place = entry_candidates[0]
            else:
                continue

        # Condition 2: Single exit arc
        if len(out_arcs) != 1:
            continue

        exit_arc = out_arcs[0]
        exit_node = exit_arc.target.id

        # Definition 16: (o_C, i_C) not in F
        if (exit_node, entry_place) in direct_arcs:
            continue

        internal_nodes = v_cycle - {entry_place}

        loops.append(
            Component(
                component_type=ComponentType.LOOP,
                internal_node_ids=internal_nodes,
                entrance=entry_place,
                exit=exit_node,
                omega=config.loop,
                priority=PRIORITY_MAP[ComponentType.LOOP],
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

    components: List[Component] = []
    components.extend(detect_sequences(net, config))
    components.extend(detect_choices(net, config))
    components.extend(detect_loops(net, config))

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
