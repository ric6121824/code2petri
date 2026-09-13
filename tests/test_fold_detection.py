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
    calculate_diff,
    load_fold_config,
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


class TestFoldConfig(unittest.TestCase):
    def test_default_weights(self):
        config = FoldConfig()
        self.assertEqual(config.sequence, 0.0)
        self.assertEqual(config.choice, 1.0)
        self.assertEqual(config.loop, 3.0)
        self.assertEqual(config.unstructured, 7.0)

    def test_custom_weights(self):
        config = FoldConfig(
            sequence=1.5,
            choice=2.5,
            loop=4.5,
            unstructured=9.5,
        )
        self.assertEqual(config.sequence, 1.5)
        self.assertEqual(config.choice, 2.5)
        self.assertEqual(config.loop, 4.5)
        self.assertEqual(config.unstructured, 9.5)

    def test_from_json_full(self):
        json_str = json.dumps({
            "sequence": 0.5,
            "choice": 2.0,
            "loop": 5.0,
            "unstructured": 8.0,
        })
        config = FoldConfig.from_json(json_str)
        self.assertEqual(config.sequence, 0.5)
        self.assertEqual(config.choice, 2.0)
        self.assertEqual(config.loop, 5.0)
        self.assertEqual(config.unstructured, 8.0)

    def test_from_json_partial(self):
        json_str = '{"choice": 4.0, "loop": 6.0}'
        config = FoldConfig.from_json(json_str)
        self.assertEqual(config.choice, 4.0)
        self.assertEqual(config.loop, 6.0)
        self.assertEqual(config.sequence, 0.0)
        self.assertEqual(config.unstructured, 7.0)

    def test_from_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(json.dumps({"choice": 3.5, "loop": 4.5}))
            tmp_path = f.name
        try:
            config = FoldConfig.from_file(tmp_path)
            self.assertEqual(config.choice, 3.5)
            self.assertEqual(config.loop, 4.5)
            self.assertEqual(config.sequence, 0.0)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_load_polymorphic(self):
        # From JSON string
        config_from_str = load_fold_config('{"choice": 4.5, "loop": 6.5}')
        self.assertEqual(config_from_str.choice, 4.5)
        self.assertEqual(config_from_str.loop, 6.5)

        # From file path
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(json.dumps({"choice": 2.5, "sequence": 1.0}))
            tmp_path = f.name
        try:
            config_from_file = load_fold_config(tmp_path)
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

    def test_backward_compatible_calculate_diff_alias(self):
        net, p_in, p_out, trans_ids = build_choice_net(2)
        comp_nodes = {p_in, p_out} | set(trans_ids)
        self.assertEqual(calculate_diff(net, comp_nodes, [p_in, p_out]), 1)


class TestDetectPureSequence(unittest.TestCase):
    def test_detect_3_transition_sequence(self):
        net, entrance, exit_node, internal = build_sequence_net(3)
        components = detect_components(net)
        self.assertEqual(len(components), 1)
        c = components[0]
        self.assertEqual(c.component_type, ComponentType.SEQUENCE)
        self.assertEqual(c.entrance, entrance)
        self.assertEqual(c.exit, exit_node)
        self.assertEqual(c.internal_node_ids, set(internal))
        self.assertEqual(c.omega, 0.0)

    def test_detect_2_transition_sequence(self):
        net, entrance, exit_node, internal = build_sequence_net(2)
        components = detect_components(net)
        self.assertEqual(len(components), 1)
        c = components[0]
        self.assertEqual(c.component_type, ComponentType.SEQUENCE)
        self.assertEqual(c.entrance, entrance)
        self.assertEqual(c.exit, exit_node)
        self.assertEqual(c.internal_node_ids, set(internal))
        self.assertEqual(c.omega, 0.0)

    def test_single_transition_not_detected_as_sequence(self):
        net, _, _, _ = build_sequence_net(1)
        components = detect_components(net)
        self.assertEqual(len(components), 0)


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
        self.assertEqual(c.omega, 1.0)


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
        # Build composite net using shared builders
        net = PetriNet()

        # Sequence sub-net
        _, s_ent, s_exit, _ = build_sequence_net(2, prefix="s_")
        for p in build_sequence_net(2, prefix="s_")[0].places:
            net.add_place(p.id)
        for t in build_sequence_net(2, prefix="s_")[0].transitions:
            net.add_transition(t.id)
        for a in build_sequence_net(2, prefix="s_")[0].arcs:
            net.add_arc(next(p for p in net.places + net.transitions if p.id == a.source.id),
                        next(p for p in net.places + net.transitions if p.id == a.target.id))

        # Choice sub-net
        for p in build_choice_net(2, prefix="c_")[0].places:
            net.add_place(p.id)
        for t in build_choice_net(2, prefix="c_")[0].transitions:
            net.add_transition(t.id)
        for a in build_choice_net(2, prefix="c_")[0].arcs:
            net.add_arc(next(p for p in net.places + net.transitions if p.id == a.source.id),
                        next(p for p in net.places + net.transitions if p.id == a.target.id))

        # Loop sub-net
        for p in build_loop_net(prefix="l_")[0].places:
            net.add_place(p.id)
        for t in build_loop_net(prefix="l_")[0].transitions:
            net.add_transition(t.id)
        for a in build_loop_net(prefix="l_")[0].arcs:
            net.add_arc(next(p for p in net.places + net.transitions if p.id == a.source.id),
                        next(p for p in net.places + net.transitions if p.id == a.target.id))

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

        # Sequence 1 (shorter, 2 transitions -> internal nodes len 3)
        for p in build_sequence_net(2, prefix="a_")[0].places:
            net.add_place(p.id)
        for t in build_sequence_net(2, prefix="a_")[0].transitions:
            net.add_transition(t.id)
        for a in build_sequence_net(2, prefix="a_")[0].arcs:
            net.add_arc(next(p for p in net.places + net.transitions if p.id == a.source.id),
                        next(p for p in net.places + net.transitions if p.id == a.target.id))

        # Sequence 2 (longer, 3 transitions -> internal nodes len 5)
        for p in build_sequence_net(3, prefix="b_")[0].places:
            net.add_place(p.id)
        for t in build_sequence_net(3, prefix="b_")[0].transitions:
            net.add_transition(t.id)
        for a in build_sequence_net(3, prefix="b_")[0].arcs:
            net.add_arc(next(p for p in net.places + net.transitions if p.id == a.source.id),
                        next(p for p in net.places + net.transitions if p.id == a.target.id))

        components = detect_components(net)
        self.assertEqual(len(components), 2)
        # Smallest internal node count first
        self.assertLess(len(components[0].internal_node_ids), len(components[1].internal_node_ids))
        self.assertEqual(components[0].entrance, "a_p0")
        self.assertEqual(components[1].entrance, "b_p0")


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
