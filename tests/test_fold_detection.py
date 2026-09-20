import json
import os
import sys
import tempfile
import unittest
from typing import List, Tuple

# Ensure repo root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from code2petri.model import PetriNet
from code2petri.fold import (
    FoldConfig,
    Component,
    ComponentType,
    calculate_symmetry_multiplier,
    detect_components,
)


def build_sequence_net(num_transitions: int, prefix: str = "") -> Tuple[PetriNet, str, str, List[str]]:
    """Builds an isolated hand-built linear sequence of alternating places and transitions."""
    net = PetriNet()
    p_ids = [f"{prefix}p{i}" for i in range(num_transitions + 1)]
    t_ids = [f"{prefix}t{i+1}" for i in range(num_transitions)]

    places = [net.add_place(pid) for pid in p_ids]
    transitions = [net.add_transition(tid) for tid in t_ids]

    for i in range(num_transitions):
        net.add_arc(places[i], transitions[i])
        net.add_arc(transitions[i], places[i + 1])

    entrance = p_ids[0]
    exit_node = p_ids[-1]
    internal = p_ids[1:-1] + t_ids
    return net, entrance, exit_node, internal


def build_choice_net(branch_count: int, prefix: str = "") -> Tuple[PetriNet, str, str, List[str]]:
    """Builds an isolated hand-built XOR-split/join net with branch_count transitions."""
    net = PetriNet()
    p_split_id = f"{prefix}p_split"
    p_merge_id = f"{prefix}p_merge"
    t_ids = [f"{prefix}t{i+1}" for i in range(branch_count)]

    p_split = net.add_place(p_split_id)
    p_merge = net.add_place(p_merge_id)
    transitions = [net.add_transition(tid) for tid in t_ids]

    for t in transitions:
        net.add_arc(p_split, t)
        net.add_arc(t, p_merge)

    return net, p_split_id, p_merge_id, t_ids


def build_loop_net(prefix: str = "") -> Tuple[PetriNet, str, str, List[str]]:
    """Builds an isolated hand-built while-style cycle net."""
    net = PetriNet()
    p0 = net.add_place(f"{prefix}p0", initial_tokens=1)
    p_head = net.add_place(f"{prefix}p_head")
    p_body = net.add_place(f"{prefix}p_body")
    p_exit = net.add_place(f"{prefix}p_exit")

    t0 = net.add_transition(f"{prefix}t0")
    t_while = net.add_transition(f"{prefix}t_while")
    t_back = net.add_transition(f"{prefix}t_back")
    t_exit = net.add_transition(f"{prefix}t_exit")

    # Inflow to loop
    net.add_arc(p0, t0)
    net.add_arc(t0, p_head)

    # Cycle
    net.add_arc(p_head, t_while)
    net.add_arc(t_while, p_body)
    net.add_arc(p_body, t_back)
    net.add_arc(t_back, p_head)

    # Exit arc from loop to outside
    net.add_arc(p_head, t_exit)
    net.add_arc(t_exit, p_exit)

    entrance = f"{prefix}p_head"
    exit_node = f"{prefix}t_exit"
    internal = [f"{prefix}t_while", f"{prefix}p_body", f"{prefix}t_back"]
    return net, entrance, exit_node, internal


def combine_into_composite_net(dest: PetriNet, src: PetriNet) -> None:
    """Copies all places, transitions, and arcs from src into dest without duplication."""
    dest_nodes = dest.get_node_map()

    for p in src.places:
        if p.id not in dest_nodes:
            dest_nodes[p.id] = dest.add_place(p.id)
    for t in src.transitions:
        if t.id not in dest_nodes:
            dest_nodes[t.id] = dest.add_transition(t.id)
    for a in src.arcs:
        dest.add_arc(dest_nodes[a.source.id], dest_nodes[a.target.id])



class TestFoldConfig(unittest.TestCase):
    def test_default_weights(self):
        config = FoldConfig()
        self.assertEqual(config.sequence, 0.0)
        self.assertEqual(config.choice, 1.0)
        self.assertEqual(config.marked_graph, 2.0)
        self.assertEqual(config.loop, 3.0)
        self.assertEqual(config.unstructured, 7.0)

    def test_custom_weights(self):
        config = FoldConfig(
            sequence=1.5,
            choice=2.5,
            marked_graph=3.5,
            loop=4.5,
            unstructured=9.5,
        )
        self.assertEqual(config.sequence, 1.5)
        self.assertEqual(config.choice, 2.5)
        self.assertEqual(config.marked_graph, 3.5)
        self.assertEqual(config.loop, 4.5)
        self.assertEqual(config.unstructured, 9.5)

    def test_load_json_full(self):
        json_str = json.dumps({
            "sequence": 0.5,
            "choice": 2.0,
            "marked_graph": 3.0,
            "loop": 5.0,
            "unstructured": 8.0,
        })
        config = FoldConfig.load(json_str)
        self.assertEqual(config.sequence, 0.5)
        self.assertEqual(config.choice, 2.0)
        self.assertEqual(config.marked_graph, 3.0)
        self.assertEqual(config.loop, 5.0)
        self.assertEqual(config.unstructured, 8.0)

    def test_load_json_partial(self):
        json_str = '{"choice": 4.0, "loop": 6.0}'
        config = FoldConfig.load(json_str)
        self.assertEqual(config.choice, 4.0)
        self.assertEqual(config.loop, 6.0)
        self.assertEqual(config.sequence, 0.0)
        self.assertEqual(config.marked_graph, 2.0)
        self.assertEqual(config.unstructured, 7.0)

    def test_load_from_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(json.dumps({"choice": 3.5, "loop": 4.5}))
            tmp_path = f.name
        try:
            config = FoldConfig.load(tmp_path)
            self.assertEqual(config.choice, 3.5)
            self.assertEqual(config.loop, 4.5)
            self.assertEqual(config.sequence, 0.0)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_load_polymorphic(self):
        # From JSON string
        config_from_str = FoldConfig.load('{"choice": 4.5, "loop": 6.5}')
        self.assertEqual(config_from_str.choice, 4.5)
        self.assertEqual(config_from_str.loop, 6.5)

        # From file path
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(json.dumps({"choice": 2.5, "sequence": 1.0}))
            tmp_path = f.name
        try:
            config_from_file = FoldConfig.load(tmp_path)
            self.assertEqual(config_from_file.choice, 2.5)
            self.assertEqual(config_from_file.sequence, 1.0)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


class TestComponentBasics(unittest.TestCase):
    def test_component_attributes(self):
        c_seq = Component(
            component_type=ComponentType.SEQUENCE,
            internal_node_ids={"t1", "p1", "t2"},
            entrance="p0",
            exit="p2",
            omega=0.0,
        )
        self.assertEqual(c_seq.component_type, ComponentType.SEQUENCE)
        self.assertEqual(c_seq.internal_node_ids, {"t1", "p1", "t2"})
        self.assertEqual(c_seq.entrance, "p0")
        self.assertEqual(c_seq.exit, "p2")
        self.assertEqual(c_seq.omega, 0.0)


class TestSymmetryMultiplierCalculation(unittest.TestCase):
    def test_diff_symmetric_choice(self):
        net, p_in, p_out, trans_ids = build_choice_net(2)
        comp_nodes = {p_in, p_out} | set(trans_ids)
        multiplier = calculate_symmetry_multiplier(net, comp_nodes, [p_in, p_out])
        self.assertEqual(multiplier, 1)

    def test_diff_ignores_external_arcs_to_split_place(self):
        net, p_in, p_out, trans_ids = build_choice_net(2)
        p0 = net.add_place("p0")
        t0 = net.add_transition("t0")
        net.add_arc(p0, t0)
        net.add_arc(t0, net.places[0])  # External incoming arc to p_split

        comp_nodes = {p_in, p_out} | set(trans_ids)
        multiplier = calculate_symmetry_multiplier(net, comp_nodes, [p_in, p_out])
        self.assertEqual(multiplier, 1)

    def test_diff_asymmetric(self):
        net = PetriNet()
        p1 = net.add_place("p1")
        p2 = net.add_place("p2")
        p3 = net.add_place("p3")
        t1 = net.add_transition("t1")
        t2 = net.add_transition("t2")
        t3 = net.add_transition("t3")
        t4 = net.add_transition("t4")

        # In component subnet {p1, p2, p3, t1, t2, t3, t4}:
        # p1 splits to t1, t2; p2 splits to t3, t4 (2 splits)
        # p3 joins t1, t2 (1 join)
        net.add_arc(p1, t1)
        net.add_arc(p1, t2)
        net.add_arc(p2, t3)
        net.add_arc(p2, t4)
        net.add_arc(t1, p3)
        net.add_arc(t2, p3)

        comp_nodes = {"p1", "p2", "p3", "t1", "t2", "t3", "t4"}
        multiplier = calculate_symmetry_multiplier(net, comp_nodes, ["p1", "p2", "p3"])
        self.assertEqual(multiplier, 2)


class TestDetectPureSequence(unittest.TestCase):
    def test_detect_3_transition_sequence(self):
        net, entrance, exit_node, internal = build_sequence_net(3)
        components = detect_components(net)
        # In p0 -> t1 -> p1 -> t2 -> p2 -> t3 -> p3, there are two intermediate place candidates: p1 and p2
        self.assertEqual(len(components), 2)
        c1, c2 = components[0], components[1]
        self.assertEqual(c1.component_type, ComponentType.SEQUENCE)
        self.assertEqual(c1.entrance, "t1")
        self.assertEqual(c1.exit, "t2")
        self.assertEqual(c1.internal_node_ids, {"p1"})
        self.assertEqual(c1.omega, 0.0)

        self.assertEqual(c2.component_type, ComponentType.SEQUENCE)
        self.assertEqual(c2.entrance, "t2")
        self.assertEqual(c2.exit, "t3")
        self.assertEqual(c2.internal_node_ids, {"p2"})
        self.assertEqual(c2.omega, 0.0)

    def test_detect_2_transition_sequence(self):
        net, entrance, exit_node, internal = build_sequence_net(2)
        components = detect_components(net)
        self.assertEqual(len(components), 1)
        c = components[0]
        self.assertEqual(c.component_type, ComponentType.SEQUENCE)
        self.assertEqual(c.entrance, "t1")
        self.assertEqual(c.exit, "t2")
        self.assertEqual(c.internal_node_ids, {"p1"})
        self.assertEqual(c.omega, 0.0)

    def test_single_transition_not_detected_as_sequence(self):
        net, _, _, _ = build_sequence_net(1)
        components = detect_components(net)
        self.assertEqual(len(components), 0)

    def test_sequence_following_branch_place(self):
        # p_split -> t1 -> p1 -> t2 -> p2 -> t3 -> p3
        # p_split -> t_other -> p_other
        net = PetriNet()
        p_split = net.add_place("p_split")
        p_other = net.add_place("p_other")
        p1 = net.add_place("p1")
        p2 = net.add_place("p2")
        p3 = net.add_place("p3")

        t1 = net.add_transition("t1")
        t_other = net.add_transition("t_other")
        t2 = net.add_transition("t2")
        t3 = net.add_transition("t3")

        net.add_arc(p_split, t1)
        net.add_arc(p_split, t_other)
        net.add_arc(t_other, p_other)

        net.add_arc(t1, p1)
        net.add_arc(p1, t2)
        net.add_arc(t2, p2)
        net.add_arc(p2, t3)
        net.add_arc(t3, p3)

        components = detect_components(net)
        seq_comps = [c for c in components if c.component_type == ComponentType.SEQUENCE]
        self.assertEqual(len(seq_comps), 2)
        self.assertEqual(seq_comps[0].entrance, "t1")
        self.assertEqual(seq_comps[0].exit, "t2")
        self.assertEqual(seq_comps[0].internal_node_ids, {"p1"})
        self.assertEqual(seq_comps[1].entrance, "t2")
        self.assertEqual(seq_comps[1].exit, "t3")
        self.assertEqual(seq_comps[1].internal_node_ids, {"p2"})

    def test_sequence_terminating_at_join_place(self):
        # p0 -> t1 -> p1 -> t2 -> p_join
        # p_other -> t_other -> p_join
        net = PetriNet()
        p0 = net.add_place("p0")
        p1 = net.add_place("p1")
        p_other = net.add_place("p_other")
        p_join = net.add_place("p_join")

        t1 = net.add_transition("t1")
        t2 = net.add_transition("t2")
        t_other = net.add_transition("t_other")

        net.add_arc(p0, t1)
        net.add_arc(t1, p1)
        net.add_arc(p1, t2)
        net.add_arc(t2, p_join)

        net.add_arc(p_other, t_other)
        net.add_arc(t_other, p_join)

        components = detect_components(net)
        seq_comps = [c for c in components if c.component_type == ComponentType.SEQUENCE]
        self.assertEqual(len(seq_comps), 1)
        self.assertEqual(seq_comps[0].entrance, "t1")
        self.assertEqual(seq_comps[0].exit, "t2")
        self.assertEqual(seq_comps[0].internal_node_ids, {"p1"})


class TestDetectChoice(unittest.TestCase):
    def test_detect_2_branch_xor_split_join(self):
        net, entrance, exit_node, internal = build_choice_net(2)
        components = detect_components(net)
        self.assertEqual(len(components), 1)
        c = components[0]
        self.assertEqual(c.component_type, ComponentType.CHOICE)
        self.assertEqual(c.entrance, entrance)
        self.assertEqual(c.exit, exit_node)
        self.assertEqual(c.internal_node_ids, set(internal))
        self.assertEqual(c.omega, 1.0)

    def test_detect_3_branch_xor_split_join(self):
        net, entrance, exit_node, internal = build_choice_net(3)
        components = detect_components(net)
        self.assertEqual(len(components), 1)
        c = components[0]
        self.assertEqual(c.component_type, ComponentType.CHOICE)
        self.assertEqual(c.entrance, entrance)
        self.assertEqual(c.exit, exit_node)
        self.assertEqual(c.internal_node_ids, set(internal))
        # ProM 1.5x markup: sum_tau = 3.0, omega = 1.0 * (3.0 * 0.5) = 1.5
        self.assertEqual(c.omega, 1.5)


class TestDetectLoop(unittest.TestCase):
    def test_detect_single_loop(self):
        net, entrance, exit_node, internal = build_loop_net()
        components = detect_components(net)
        loop_comps = [c for c in components if c.component_type == ComponentType.LOOP]
        self.assertEqual(len(loop_comps), 1)
        c = loop_comps[0]
        self.assertEqual(c.entrance, entrance)
        self.assertEqual(c.exit, exit_node)
        self.assertEqual(c.internal_node_ids, set(internal))
        self.assertEqual(c.omega, 3.0)


class TestPrioritySortingAndTieBreaking(unittest.TestCase):
    def test_mixed_net_priority_sorting(self):
        # Build composite net using shared builders and combine_into_composite_net
        net = PetriNet()

        seq_net, _, _, _ = build_sequence_net(2, prefix="s_")
        choice_net, _, _, _ = build_choice_net(2, prefix="c_")
        loop_net, _, _, _ = build_loop_net(prefix="l_")

        combine_into_composite_net(net, seq_net)
        combine_into_composite_net(net, choice_net)
        combine_into_composite_net(net, loop_net)

        components = detect_components(net)
        types_in_order = [c.component_type for c in components]
        self.assertIn(ComponentType.SEQUENCE, types_in_order)
        self.assertIn(ComponentType.CHOICE, types_in_order)
        self.assertIn(ComponentType.LOOP, types_in_order)

        # Verify Definition 21 sorting: Sequence (1) < Choice (2) < Loop (3)
        first_seq_idx = types_in_order.index(ComponentType.SEQUENCE)
        first_choice_idx = types_in_order.index(ComponentType.CHOICE)
        first_loop_idx = types_in_order.index(ComponentType.LOOP)
        self.assertLess(first_seq_idx, first_choice_idx)
        self.assertLess(first_choice_idx, first_loop_idx)

    def test_tie_breaking_smallest_internal_nodes(self):
        net = PetriNet()

        # Choice 1 (2 branches -> 2 internal transition nodes)
        choice1_net, _, _, _ = build_choice_net(2, prefix="a_")
        # Choice 2 (3 branches -> 3 internal transition nodes)
        choice2_net, _, _, _ = build_choice_net(3, prefix="b_")

        combine_into_composite_net(net, choice1_net)
        combine_into_composite_net(net, choice2_net)

        components = detect_components(net)
        self.assertEqual(len(components), 2)
        # Smallest internal node count first
        self.assertLess(len(components[0].internal_node_ids), len(components[1].internal_node_ids))
        self.assertEqual(components[0].entrance, "a_p_split")
        self.assertEqual(components[1].entrance, "b_p_split")


class TestUnstructuredNet(unittest.TestCase):
    def test_unstructured_sync_split_net_returns_empty(self):
        net = PetriNet()
        p1 = net.add_place("p1")
        p2 = net.add_place("p2")
        p3 = net.add_place("p3")
        p4 = net.add_place("p4")
        p5 = net.add_place("p5")

        t1 = net.add_transition("t1")
        t2 = net.add_transition("t2")
        t3 = net.add_transition("t3")
        t4 = net.add_transition("t4")

        net.add_arc(p1, t1)
        net.add_arc(t1, p2)
        net.add_arc(p2, t2)
        net.add_arc(p2, t3)
        net.add_arc(t2, p3)
        net.add_arc(t3, p4)
        net.add_arc(p3, t4)
        net.add_arc(p4, t4)
        net.add_arc(t4, p5)

        components = detect_components(net)
        self.assertEqual(components, [])

    def test_unstructured_multi_entry_cycle_returns_empty(self):
        net = PetriNet()
        pa = net.add_place("pa")
        pb = net.add_place("pb")
        p_exit = net.add_place("p_exit")

        t_in1 = net.add_transition("t_in1")
        t_in2 = net.add_transition("t_in2")
        ta = net.add_transition("ta")
        tb = net.add_transition("tb")
        t_exit = net.add_transition("t_exit")

        net.add_arc(t_in1, pa)
        net.add_arc(t_in2, pb)
        net.add_arc(pa, ta)
        net.add_arc(ta, pb)
        net.add_arc(pb, tb)
        net.add_arc(tb, pa)
        net.add_arc(pa, t_exit)
        net.add_arc(t_exit, p_exit)

        components = detect_components(net)
        self.assertEqual(components, [])


class TestFoldConfigOverrides(unittest.TestCase):
    def test_custom_config_affects_omega(self):
        net, _, _, _ = build_sequence_net(2)
        config = FoldConfig(sequence=5.0)
        components = detect_components(net, config=config)
        self.assertEqual(len(components), 1)
        self.assertEqual(components[0].omega, 5.0)


if __name__ == '__main__':
    unittest.main()
