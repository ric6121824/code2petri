import json
import os
import sys
import tempfile
import unittest

# Ensure repo root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from code2petri.model import PetriNet, Place, Transition, Arc
from code2petri.fold import (
    FoldConfig,
    Component,
    ComponentType,
    calculate_diff,
    detect_components,
)
from code2petri.python_walker import PythonWalker
from tests.petri_assertions import walk_net


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

    def test_from_json_full(self):
        json_str = json.dumps({
            "sequence": 0.5,
            "choice": 2.0,
            "marked_graph": 3.0,
            "loop": 5.0,
            "unstructured": 8.0,
        })
        config = FoldConfig.from_json(json_str)
        self.assertEqual(config.sequence, 0.5)
        self.assertEqual(config.choice, 2.0)
        self.assertEqual(config.marked_graph, 3.0)
        self.assertEqual(config.loop, 5.0)
        self.assertEqual(config.unstructured, 8.0)

    def test_from_json_partial(self):
        json_str = '{"choice": 4.0, "loop": 6.0}'
        config = FoldConfig.from_json(json_str)
        self.assertEqual(config.choice, 4.0)
        self.assertEqual(config.loop, 6.0)
        self.assertEqual(config.sequence, 0.0)
        self.assertEqual(config.marked_graph, 2.0)
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
    def test_component_attributes_and_priority_default(self):
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
        self.assertEqual(c_seq.priority, 1)

        c_choice = Component(
            component_type=ComponentType.CHOICE,
            internal_node_ids={"t1", "t2"},
            entrance="p_split",
            exit="p_merge",
            omega=1.0,
        )
        self.assertEqual(c_choice.priority, 2)

        c_loop = Component(
            component_type=ComponentType.LOOP,
            internal_node_ids={"t_while", "p_body", "t_back"},
            entrance="p_head",
            exit="p_head",
            omega=3.0,
        )
        self.assertEqual(c_loop.priority, 3)

    def test_component_to_dict(self):
        c = Component(
            component_type=ComponentType.CHOICE,
            internal_node_ids={"t2", "t1"},
            entrance="p0",
            exit="p1",
            omega=1.0,
            priority=2,
        )
        d = c.to_dict()
        self.assertEqual(d["component_type"], "choice")
        self.assertEqual(d["internal_node_ids"], ["t1", "t2"])
        self.assertEqual(d["entrance"], "p0")
        self.assertEqual(d["exit"], "p1")
        self.assertEqual(d["omega"], 1.0)
        self.assertEqual(d["priority"], 2)


class TestDiffCalculation(unittest.TestCase):
    def test_diff_symmetric_choice(self):
        net = PetriNet()
        p_in = net.add_place("p_in")
        p_out = net.add_place("p_out")
        t1 = net.add_transition("t1")
        t2 = net.add_transition("t2")
        net.add_arc(p_in, t1)
        net.add_arc(p_in, t2)
        net.add_arc(t1, p_out)
        net.add_arc(t2, p_out)

        # In subnet {p_in, p_out, t1, t2}:
        # p_in has out-degree 2 (1 split), p_out has in-degree 2 (1 join)
        # diff = |1 - 1| + 1 = 1
        component_nodes = {"p_in", "p_out", "t1", "t2"}
        diff_val = calculate_diff(net, component_nodes, ["p_in", "p_out"])
        self.assertEqual(diff_val, 1)

    def test_diff_ignores_external_arcs_to_split_place(self):
        # External arc t0 -> p_in does not make p_in a join inside the component
        net = PetriNet()
        p0 = net.add_place("p0")
        t0 = net.add_transition("t0")
        p_in = net.add_place("p_in")
        p_out = net.add_place("p_out")
        t1 = net.add_transition("t1")
        t2 = net.add_transition("t2")

        net.add_arc(p0, t0)
        net.add_arc(t0, p_in)  # External incoming arc to p_in
        net.add_arc(p_in, t1)
        net.add_arc(p_in, t2)
        net.add_arc(t1, p_out)
        net.add_arc(t2, p_out)

        component_nodes = {"p_in", "p_out", "t1", "t2"}
        diff_val = calculate_diff(net, component_nodes, ["p_in", "p_out"])
        # Should still be 1 (symmetric choice), not inflated by external arc
        self.assertEqual(diff_val, 1)

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

        # splits = 2, joins = 1 -> diff = |2 - 1| + 1 = 2
        comp_nodes = {"p1", "p2", "p3", "t1", "t2", "t3", "t4"}
        diff_val = calculate_diff(net, comp_nodes, ["p1", "p2", "p3"])
        self.assertEqual(diff_val, 2)


class TestDetectPureSequence(unittest.TestCase):
    def test_detect_3_transition_sequence(self):
        # p0 -> t1 -> p1 -> t2 -> p2 -> t3 -> p3
        net = PetriNet()
        p0 = net.add_place("p0", initial_tokens=1)
        p1 = net.add_place("p1")
        p2 = net.add_place("p2")
        p3 = net.add_place("p3")

        t1 = net.add_transition("t1")
        t2 = net.add_transition("t2")
        t3 = net.add_transition("t3")

        net.add_arc(p0, t1)
        net.add_arc(t1, p1)
        net.add_arc(p1, t2)
        net.add_arc(t2, p2)
        net.add_arc(p2, t3)
        net.add_arc(t3, p3)

        components = detect_components(net)
        self.assertEqual(len(components), 1)
        c = components[0]
        self.assertEqual(c.component_type, ComponentType.SEQUENCE)
        self.assertEqual(c.entrance, "p0")
        self.assertEqual(c.exit, "p3")
        self.assertEqual(c.internal_node_ids, {"t1", "p1", "t2", "p2", "t3"})
        self.assertEqual(c.omega, 0.0)
        self.assertEqual(c.priority, 1)

    def test_detect_2_transition_sequence(self):
        # p0 -> t1 -> p1 -> t2 -> p2
        net = PetriNet()
        p0 = net.add_place("p0")
        p1 = net.add_place("p1")
        p2 = net.add_place("p2")
        t1 = net.add_transition("t1")
        t2 = net.add_transition("t2")

        net.add_arc(p0, t1)
        net.add_arc(t1, p1)
        net.add_arc(p1, t2)
        net.add_arc(t2, p2)

        components = detect_components(net)
        self.assertEqual(len(components), 1)
        c = components[0]
        self.assertEqual(c.component_type, ComponentType.SEQUENCE)
        self.assertEqual(c.entrance, "p0")
        self.assertEqual(c.exit, "p2")
        self.assertEqual(c.internal_node_ids, {"t1", "p1", "t2"})
        self.assertEqual(c.omega, 0.0)

    def test_single_transition_not_detected_as_sequence(self):
        # p0 -> t1 -> p1 (trivial, only 1 transition -> cannot reduce)
        net = PetriNet()
        p0 = net.add_place("p0")
        p1 = net.add_place("p1")
        t1 = net.add_transition("t1")
        net.add_arc(p0, t1)
        net.add_arc(t1, p1)

        components = detect_components(net)
        self.assertEqual(len(components), 0)


class TestDetectChoice(unittest.TestCase):
    def test_detect_2_branch_xor_split_join(self):
        # p_split -> {t1, t2} -> p_merge
        net = PetriNet()
        p_split = net.add_place("p_split")
        p_merge = net.add_place("p_merge")
        t1 = net.add_transition("t1")
        t2 = net.add_transition("t2")

        net.add_arc(p_split, t1)
        net.add_arc(p_split, t2)
        net.add_arc(t1, p_merge)
        net.add_arc(t2, p_merge)

        components = detect_components(net)
        self.assertEqual(len(components), 1)
        c = components[0]
        self.assertEqual(c.component_type, ComponentType.CHOICE)
        self.assertEqual(c.entrance, "p_split")
        self.assertEqual(c.exit, "p_merge")
        self.assertEqual(c.internal_node_ids, {"t1", "t2"})
        self.assertEqual(c.omega, 1.0)
        self.assertEqual(c.priority, 2)

    def test_detect_3_branch_xor_split_join(self):
        # p_split -> {t1, t2, t3} -> p_merge
        net = PetriNet()
        p_split = net.add_place("p_split")
        p_merge = net.add_place("p_merge")
        t1 = net.add_transition("t1")
        t2 = net.add_transition("t2")
        t3 = net.add_transition("t3")

        net.add_arc(p_split, t1)
        net.add_arc(p_split, t2)
        net.add_arc(p_split, t3)
        net.add_arc(t1, p_merge)
        net.add_arc(t2, p_merge)
        net.add_arc(t3, p_merge)

        components = detect_components(net)
        self.assertEqual(len(components), 1)
        c = components[0]
        self.assertEqual(c.component_type, ComponentType.CHOICE)
        self.assertEqual(c.entrance, "p_split")
        self.assertEqual(c.exit, "p_merge")
        self.assertEqual(c.internal_node_ids, {"t1", "t2", "t3"})
        self.assertEqual(c.omega, 1.0)


class TestDetectLoop(unittest.TestCase):
    def test_detect_single_loop(self):
        # Entry: p0 -> t0 -> p_head
        # Cycle: p_head -> t_while -> p_body -> t_back -> p_head
        # Exit: p_head -> t_exit -> p_exit
        net = PetriNet()
        p0 = net.add_place("p0", initial_tokens=1)
        p_head = net.add_place("p_head")
        p_body = net.add_place("p_body")
        p_exit = net.add_place("p_exit")

        t0 = net.add_transition("t0")
        t_while = net.add_transition("t_while")
        t_back = net.add_transition("t_back")
        t_exit = net.add_transition("t_exit")

        net.add_arc(p0, t0)
        net.add_arc(t0, p_head)

        # Cycle
        net.add_arc(p_head, t_while)
        net.add_arc(t_while, p_body)
        net.add_arc(p_body, t_back)
        net.add_arc(t_back, p_head)

        # Exit arc from loop
        net.add_arc(p_head, t_exit)
        net.add_arc(t_exit, p_exit)

        components = detect_components(net)
        loop_comps = [c for c in components if c.component_type == ComponentType.LOOP]
        self.assertEqual(len(loop_comps), 1)
        c = loop_comps[0]
        self.assertEqual(c.entrance, "p_head")
        self.assertEqual(c.exit, "p_head")
        self.assertEqual(c.internal_node_ids, {"t_while", "p_body", "t_back"})
        self.assertEqual(c.omega, 3.0)
        self.assertEqual(c.priority, 3)


class TestPrioritySortingAndTieBreaking(unittest.TestCase):
    def test_mixed_net_priority_sorting(self):
        # Build net with a sequence, a choice, and a loop
        net = PetriNet()

        # Sequence: p_s0 -> t_s1 -> p_s1 -> t_s2 -> p_s2
        p_s0 = net.add_place("p_s0")
        p_s1 = net.add_place("p_s1")
        p_s2 = net.add_place("p_s2")
        t_s1 = net.add_transition("t_s1")
        t_s2 = net.add_transition("t_s2")
        net.add_arc(p_s0, t_s1)
        net.add_arc(t_s1, p_s1)
        net.add_arc(p_s1, t_s2)
        net.add_arc(t_s2, p_s2)

        # Choice: p_c_in -> {t_c1, t_c2} -> p_c_out
        p_c_in = net.add_place("p_c_in")
        p_c_out = net.add_place("p_c_out")
        t_c1 = net.add_transition("t_c1")
        t_c2 = net.add_transition("t_c2")
        net.add_arc(p_c_in, t_c1)
        net.add_arc(p_c_in, t_c2)
        net.add_arc(t_c1, p_c_out)
        net.add_arc(t_c2, p_c_out)

        # Loop: p_l0 -> t_l0 -> p_l_head -> t_l_body -> p_l_body -> t_l_back -> p_l_head
        # Exit: p_l_head -> t_l_exit -> p_l_exit
        p_l0 = net.add_place("p_l0")
        p_l_head = net.add_place("p_l_head")
        p_l_body = net.add_place("p_l_body")
        p_l_exit = net.add_place("p_l_exit")
        t_l0 = net.add_transition("t_l0")
        t_l_body = net.add_transition("t_l_body")
        t_l_back = net.add_transition("t_l_back")
        t_l_exit = net.add_transition("t_l_exit")
        net.add_arc(p_l0, t_l0)
        net.add_arc(t_l0, p_l_head)
        net.add_arc(p_l_head, t_l_body)
        net.add_arc(t_l_body, p_l_body)
        net.add_arc(p_l_body, t_l_back)
        net.add_arc(t_l_back, p_l_head)
        net.add_arc(p_l_head, t_l_exit)
        net.add_arc(t_l_exit, p_l_exit)

        components = detect_components(net)
        # Should have at least one of each
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
        # Two independent sequences of different lengths
        net = PetriNet()

        # Sequence 1 (shorter): 2 transitions -> internal nodes: {"t_a1", "p_a1", "t_a2"} (len 3)
        p_a0 = net.add_place("p_a0")
        p_a1 = net.add_place("p_a1")
        p_a2 = net.add_place("p_a2")
        t_a1 = net.add_transition("t_a1")
        t_a2 = net.add_transition("t_a2")
        net.add_arc(p_a0, t_a1)
        net.add_arc(t_a1, p_a1)
        net.add_arc(p_a1, t_a2)
        net.add_arc(t_a2, p_a2)

        # Sequence 2 (longer): 3 transitions -> internal nodes: {"t_b1", "p_b1", "t_b2", "p_b2", "t_b3"} (len 5)
        p_b0 = net.add_place("p_b0")
        p_b1 = net.add_place("p_b1")
        p_b2 = net.add_place("p_b2")
        p_b3 = net.add_place("p_b3")
        t_b1 = net.add_transition("t_b1")
        t_b2 = net.add_transition("t_b2")
        t_b3 = net.add_transition("t_b3")
        net.add_arc(p_b0, t_b1)
        net.add_arc(t_b1, p_b1)
        net.add_arc(p_b1, t_b2)
        net.add_arc(t_b2, p_b2)
        net.add_arc(p_b2, t_b3)
        net.add_arc(t_b3, p_b3)

        components = detect_components(net)
        self.assertEqual(len(components), 2)
        # Smallest internal node count first
        self.assertLess(len(components[0].internal_node_ids), len(components[1].internal_node_ids))
        self.assertEqual(components[0].entrance, "p_a0")
        self.assertEqual(components[1].entrance, "p_b0")


class TestUnstructuredNet(unittest.TestCase):
    def test_unstructured_sync_split_net_returns_empty(self):
        # A net with an XOR-split followed by synchronization (AND-join):
        # p1 -> t1 -> p2 -> {t2 -> p3, t3 -> p4} -> t4 (synchronizes p3 and p4) -> p5
        # Each branch has only 1 transition (no sequence >= 2),
        # branches lead to different places (no XOR-merge choice),
        # and there are no cycles.
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
        # A cycle between pa and pb where both places receive entries from outside,
        # violating the single-entry condition of well-structured loops.
        net = PetriNet()
        pa = net.add_place("pa")
        pb = net.add_place("pb")
        p_exit = net.add_place("p_exit")

        t_in1 = net.add_transition("t_in1")
        t_in2 = net.add_transition("t_in2")
        ta = net.add_transition("ta")
        tb = net.add_transition("tb")
        t_exit = net.add_transition("t_exit")

        # Two outside entries
        net.add_arc(t_in1, pa)
        net.add_arc(t_in2, pb)

        # Cycle
        net.add_arc(pa, ta)
        net.add_arc(ta, pb)
        net.add_arc(pb, tb)
        net.add_arc(tb, pa)

        # Exit
        net.add_arc(pa, t_exit)
        net.add_arc(t_exit, p_exit)

        components = detect_components(net)
        self.assertEqual(components, [])


class TestFoldConfigOverrides(unittest.TestCase):
    def test_custom_config_affects_omega(self):
        net = PetriNet()
        p0 = net.add_place("p0")
        p1 = net.add_place("p1")
        p2 = net.add_place("p2")
        t1 = net.add_transition("t1")
        t2 = net.add_transition("t2")
        net.add_arc(p0, t1)
        net.add_arc(t1, p1)
        net.add_arc(p1, t2)
        net.add_arc(t2, p2)

        config = FoldConfig(sequence=5.0)
        components = detect_components(net, config=config)
        self.assertEqual(len(components), 1)
        self.assertEqual(components[0].omega, 5.0)


class TestRealWalkerNets(unittest.TestCase):
    def test_detect_loop_in_walker_while_net(self):
        walker = PythonWalker()
        fixture_path = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "petri_py",
            "while_loop.py",
        )
        tree = walker.parse_file(fixture_path)
        func_node = walker.find_function(tree, "while_loop_func")
        net = walk_net(walker, func_node)

        components = detect_components(net)
        loop_comps = [c for c in components if c.component_type == ComponentType.LOOP]
        self.assertGreaterEqual(len(loop_comps), 1)
        c = loop_comps[0]
        self.assertEqual(c.omega, 3.0)
        self.assertEqual(c.priority, 3)


if __name__ == '__main__':
    unittest.main()
