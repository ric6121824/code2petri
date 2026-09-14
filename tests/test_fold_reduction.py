import json
import os
import sys
import unittest
from typing import List, Tuple

# Ensure repo root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from code2petri.model import PetriNet, Place, Transition
from code2petri.fold import (
    FoldConfig,
    ComponentType,
    FoldStep,
    FoldResult,
    fold_net,
    fold_component,
    detect_components,
)
from tests.test_fold_detection import (
    build_sequence_net,
    build_choice_net,
    build_loop_net,
    combine_into_composite_net,
)


class TestFoldSequence(unittest.TestCase):
    def test_pure_3_transition_sequence_fold(self):
        net, entrance, exit_node, internal = build_sequence_net(3)
        result = fold_net(net)

        self.assertTrue(result.fully_reducible)
        self.assertEqual(len(result.steps), 1)

        step1 = result.steps[0]
        self.assertEqual(step1.step, 1)
        self.assertEqual(step1.step_number, 1)
        self.assertEqual(step1.component_type, ComponentType.SEQUENCE)
        self.assertEqual(step1.dummy_transition_id, "t_C1")
        self.assertEqual(step1.omega, 0.0)
        # 3 transitions initially with tau=1.0 -> 0.0 + 1 + 1 + 1 = 3.0
        self.assertEqual(step1.tau, 3.0)
        self.assertEqual(step1.running_sm, 3.0)
        self.assertEqual(step1.sm_score, 3.0)
        self.assertEqual(result.final_sm, 3.0)

        # Folded net at step 1 should have exactly 1 transition (t_C1) between p0 and p3
        folded_net = step1.net
        self.assertEqual(len(folded_net.transitions), 1)
        self.assertEqual(folded_net.transitions[0].id, "t_C1")
        self.assertTrue(folded_net.transitions[0].metadata.get("dummy"))
        self.assertEqual(folded_net.transitions[0].metadata.get("tau"), 3.0)
        self.assertEqual(len(folded_net.places), 2)
        place_ids = {p.id for p in folded_net.places}
        self.assertEqual(place_ids, {"p0", "p3"})
        self.assertEqual(len(folded_net.arcs), 2)

    def test_pure_2_transition_sequence_fold(self):
        net, entrance, exit_node, internal = build_sequence_net(2)
        result = fold_net(net)

        self.assertTrue(result.fully_reducible)
        self.assertEqual(len(result.steps), 1)
        self.assertEqual(result.steps[0].omega, 0.0)
        self.assertEqual(result.steps[0].tau, 2.0)
        self.assertEqual(result.final_sm, 2.0)


class TestFoldChoice(unittest.TestCase):
    def test_symmetric_choice_fold(self):
        net, entrance, exit_node, internal = build_choice_net(2)
        result = fold_net(net)

        self.assertTrue(result.fully_reducible)
        self.assertEqual(len(result.steps), 1)

        step1 = result.steps[0]
        self.assertEqual(step1.component_type, ComponentType.CHOICE)
        self.assertEqual(step1.omega, 1.0)
        # omega=1.0 + 2 transitions (tau=1 each) = 3.0
        self.assertEqual(step1.tau, 3.0)
        self.assertEqual(step1.running_sm, 3.0)
        self.assertEqual(result.final_sm, 3.0)

        folded_net = step1.net
        self.assertEqual(len(folded_net.transitions), 1)
        self.assertEqual(folded_net.transitions[0].id, "t_C1")
        self.assertEqual(folded_net.transitions[0].metadata.get("tau"), 3.0)
        self.assertEqual(len(folded_net.places), 2)


class TestFoldLoop(unittest.TestCase):
    def test_single_loop_fold(self):
        net, entrance, exit_node, internal = build_loop_net()
        result = fold_net(net)

        self.assertTrue(result.fully_reducible)
        # Step 1: Loop component folded (omega = 3.0, tau = 3.0 + 3 = 6.0)
        # Step 2: Linear sequence (t0 -> p_head -> t_C1) folded (omega = 0.0, tau = 1.0 + 6.0 = 7.0)
        self.assertEqual(len(result.steps), 2)

        step1 = result.steps[0]
        self.assertEqual(step1.component_type, ComponentType.LOOP)
        self.assertEqual(step1.omega, 3.0)
        self.assertEqual(step1.tau, 6.0)
        self.assertEqual(step1.dummy_transition_id, "t_C1")

        step2 = result.steps[1]
        self.assertEqual(step2.component_type, ComponentType.SEQUENCE)
        self.assertEqual(step2.omega, 0.0)
        self.assertEqual(step2.tau, 7.0)
        self.assertEqual(step2.dummy_transition_id, "t_C2")
        self.assertEqual(result.final_sm, 7.0)


class TestFoldMixedAndPriority(unittest.TestCase):
    def test_mixed_net_priority_order_reduction(self):
        net = PetriNet()

        # Connect in series: seq (s_) -> choice (c_) -> loop (l_)
        seq_net, s_entrance, s_exit, _ = build_sequence_net(2, prefix="s_")
        choice_net, c_entrance, c_exit, _ = build_choice_net(2, prefix="c_")
        loop_net, l_entrance, l_exit, _ = build_loop_net(prefix="l_")

        combine_into_composite_net(net, seq_net)
        combine_into_composite_net(net, choice_net)
        combine_into_composite_net(net, loop_net)

        # Connect sequence exit to choice entrance via intermediate transition
        t_s2c = net.add_transition("t_s2c")
        net.add_arc(next(p for p in net.places if p.id == s_exit), t_s2c)
        net.add_arc(t_s2c, next(p for p in net.places if p.id == c_entrance))

        # Connect choice exit to loop entrance via intermediate transition
        p_l0 = next(p for p in net.places if p.id == "l_p0")
        p_l0.initial_tokens = 0
        t_c2l = net.add_transition("t_c2l")
        net.add_arc(next(p for p in net.places if p.id == c_exit), t_c2l)
        net.add_arc(t_c2l, p_l0)

        result = fold_net(net)
        step_types = [s.component_type for s in result.steps]

        # The first folded component must be SEQUENCE (priority 1)
        self.assertEqual(step_types[0], ComponentType.SEQUENCE)
        # CHOICE must be folded before LOOP
        choice_idx = step_types.index(ComponentType.CHOICE)
        loop_idx = step_types.index(ComponentType.LOOP)
        self.assertLess(choice_idx, loop_idx)
        # A connected mixed workflow net reduces fully
        self.assertTrue(result.fully_reducible)
        self.assertEqual(len(result.steps[-1].snapshot.transitions), 1)


class TestFoldIrreducible(unittest.TestCase):
    def test_known_irreducible_net_terminates_with_unstructured_penalty(self):
        # Build an irreducible net with interlocking non-SESE cycles/branching
        net = PetriNet()
        p_in = net.add_place("p_in", initial_tokens=1)
        p1 = net.add_place("p1")
        p2 = net.add_place("p2")
        p_out = net.add_place("p_out")

        t1 = net.add_transition("t1")
        t2 = net.add_transition("t2")
        t3 = net.add_transition("t3")
        t4 = net.add_transition("t4")

        # Entangled cross-connections (milestone pattern)
        net.add_arc(p_in, t1)
        net.add_arc(p_in, t2)
        net.add_arc(t1, p1)
        net.add_arc(t2, p2)
        net.add_arc(p1, t3)
        net.add_arc(p2, t3)
        net.add_arc(p1, t4)
        net.add_arc(t3, p_out)
        net.add_arc(t4, p2)

        result = fold_net(net)
        self.assertFalse(result.fully_reducible)
        self.assertGreaterEqual(len(result.steps), 1)

        last_step = result.steps[-1]
        self.assertEqual(last_step.component_type, ComponentType.UNSTRUCTURED)
        self.assertEqual(last_step.omega, 7.0)
        self.assertGreater(result.final_sm, 7.0)

    def test_unstructured_fold_on_single_place_net(self):
        # Build an irreducible net with a single place and multiple transitions
        net = PetriNet()
        p = net.add_place("p0", initial_tokens=1)
        t1 = net.add_transition("t1")
        t2 = net.add_transition("t2")
        # Both transitions loop on p0
        net.add_arc(p, t1)
        net.add_arc(t1, p)
        net.add_arc(p, t2)
        net.add_arc(t2, p)

        result = fold_net(net)
        self.assertFalse(result.fully_reducible)
        self.assertEqual(len(result.steps), 1)
        step = result.steps[0]
        self.assertEqual(step.component_type, ComponentType.UNSTRUCTURED)
        # Verify dummy transition has both input and output arcs connected to p0
        final_net = step.snapshot
        self.assertEqual(len(final_net.transitions), 1)
        dummy_t = final_net.transitions[0]
        self.assertEqual(len(final_net.arcs), 2)
        sources = {a.source.id for a in final_net.arcs}
        targets = {a.target.id for a in final_net.arcs}
        self.assertIn("p0", sources)
        self.assertIn(dummy_t.id, sources)
        self.assertIn("p0", targets)
        self.assertIn(dummy_t.id, targets)


class TestFoldConfigOverrides(unittest.TestCase):
    def test_config_overrides_change_sm(self):
        net, _, _, _ = build_choice_net(2)
        custom_config = FoldConfig(choice=5.0)
        result = fold_net(net, config=custom_config)

        self.assertEqual(result.steps[0].omega, 5.0)
        # 5.0 + 2.0 = 7.0
        self.assertEqual(result.steps[0].tau, 7.0)
        self.assertEqual(result.final_sm, 7.0)


class TestFoldResultPropertiesAndSerialization(unittest.TestCase):
    def test_penultimate_net_state(self):
        net, _, _, _ = build_loop_net()
        result = fold_net(net)

        self.assertEqual(len(result.steps), 2)
        # Penultimate net is step 1's net
        self.assertEqual(result.penultimate_net, result.steps[0].net)
        self.assertEqual(result.penultimate_state, result.steps[0].net)

    def test_penultimate_net_single_step(self):
        net, _, _, _ = build_sequence_net(2)
        result = fold_net(net)

        self.assertEqual(len(result.steps), 1)
        # For single step, penultimate net is initial net
        self.assertEqual(result.penultimate_net, result.initial_net)

    def test_json_serialization_schema(self):
        net, _, _, _ = build_sequence_net(2)
        result = fold_net(net, function_name="testFunc", file_path="test.js")

        d = result.to_dict()
        self.assertEqual(d["function"], "testFunc")
        self.assertEqual(d["file"], "test.js")
        self.assertIn("initial_net", d)
        self.assertIn("fold_steps", d)
        self.assertIn("final_sm", d)
        self.assertIn("fully_reducible", d)
        self.assertEqual(d["final_sm"], 2.0)
        self.assertTrue(d["fully_reducible"])

        step_d = d["fold_steps"][0]
        self.assertEqual(step_d["step"], 1)
        self.assertEqual(step_d["component_type"], "sequence")
        self.assertEqual(step_d["dummy_transition"], "t_C1")
        self.assertEqual(step_d["omega"], 0.0)
        self.assertEqual(step_d["tau"], 2.0)
        self.assertEqual(step_d["sm_score"], 2.0)
        self.assertIn("folded_nodes", step_d)
        self.assertIn("net", step_d)

        # JSON round-trip
        json_str = result.to_json()
        parsed = json.loads(json_str)
        self.assertEqual(parsed["final_sm"], 2.0)
        self.assertEqual(len(parsed["fold_steps"]), 1)

    def test_single_transition_net_is_trivial(self):
        net = PetriNet()
        p0 = net.add_place("p0")
        t0 = net.add_transition("t0")
        p1 = net.add_place("p1")
        net.add_arc(p0, t0)
        net.add_arc(t0, p1)

        result = fold_net(net)
        self.assertTrue(result.fully_reducible)
        self.assertEqual(len(result.steps), 0)
        self.assertEqual(result.final_sm, 1.0)


if __name__ == '__main__':
    unittest.main()
