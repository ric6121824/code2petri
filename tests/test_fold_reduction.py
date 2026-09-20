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
    fold_sequence,
    foldSequence,
    fold_choice,
    foldChoice,
    _is_trivial_workflow_net,
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
        # Under fine-grained Single-Place Contraction, 3 transitions reduce across 2 contractions
        self.assertEqual(len(result.steps), 2)

        step1 = result.steps[0]
        self.assertEqual(step1.step_number, 1)
        self.assertEqual(step1.component_type, ComponentType.SEQUENCE)
        self.assertEqual(step1.opaque_transition_id, "t_C1")
        self.assertEqual(step1.omega, 0.0)
        self.assertEqual(step1.tau, 2.0)

        step2 = result.steps[1]
        self.assertEqual(step2.step_number, 2)
        self.assertEqual(step2.component_type, ComponentType.SEQUENCE)
        self.assertEqual(step2.opaque_transition_id, "t_C2")
        self.assertEqual(step2.omega, 0.0)
        self.assertEqual(step2.tau, 3.0)
        self.assertEqual(step2.running_sm, 3.0)
        self.assertEqual(result.final_sm, 3.0)

        # Folded net at step 2 should have exactly 1 transition (t_C2) between p0 and p3
        folded_net = step2.snapshot
        self.assertEqual(len(folded_net.transitions), 1)
        self.assertEqual(folded_net.transitions[0].id, "t_C2")
        self.assertTrue(folded_net.transitions[0].metadata.get("opaque"))
        self.assertEqual(folded_net.transitions[0].metadata.get("tau"), 3.0)
        self.assertEqual(len(folded_net.places), 2)
        place_ids = {p.id for p in folded_net.places}
        self.assertEqual(place_ids, {"p0", "p3"})
        self.assertEqual(len(folded_net.arcs), 2)

    def test_prom_single_place_contraction_direct(self):
        """Validates that fold_sequence directly contracts one intermediate place (1 -> 1 -> 1)."""
        net, entrance, exit_node, internal = build_sequence_net(2)
        res = fold_sequence(net, step_number=1, config=FoldConfig())

        self.assertIsNotNone(res, "fold_sequence should return a result for a valid sequence")
        folded_net, step = res

        self.assertEqual(step.step_number, 1)
        self.assertEqual(step.component_type, ComponentType.SEQUENCE)
        self.assertEqual(step.opaque_transition_id, "t_C1")
        self.assertEqual(step.consumed_node_ids, {"t1", "p1", "t2"})
        self.assertEqual(step.omega, 0.0)
        self.assertEqual(step.tau, 2.0)

        # The folded net must have p0, p2, and t_C1
        self.assertEqual({p.id for p in folded_net.places}, {"p0", "p2"})
        self.assertEqual({t.id for t in folded_net.transitions}, {"t_C1"})
        self.assertEqual(len(folded_net.arcs), 2)
        self.assertTrue(_is_trivial_workflow_net(folded_net))


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

        folded_net = step1.snapshot
        self.assertEqual(len(folded_net.transitions), 1)
        self.assertEqual(folded_net.transitions[0].id, "t_C1")
        self.assertEqual(folded_net.transitions[0].metadata.get("tau"), 3.0)
        self.assertEqual(len(folded_net.places), 2)

    def test_prom_choice_fold_direct(self):
        """Validates that fold_choice directly folds parallel transitions between shared places."""
        net, entrance, exit_node, internal = build_choice_net(2)
        res = fold_choice(net, step_number=1, config=FoldConfig())

        self.assertIsNotNone(res, "fold_choice should return a result for a valid choice")
        folded_net, step = res

        self.assertEqual(step.step_number, 1)
        self.assertEqual(step.component_type, ComponentType.CHOICE)
        self.assertEqual(step.opaque_transition_id, "t_C1")
        self.assertEqual(step.consumed_node_ids, {"t1", "t2"})
        self.assertEqual(step.omega, 1.0)
        self.assertEqual(step.tau, 3.0)

        self.assertEqual({p.id for p in folded_net.places}, {"p_split", "p_merge"})
        self.assertEqual({t.id for t in folded_net.transitions}, {"t_C1"})
        self.assertEqual(len(folded_net.arcs), 2)
        self.assertTrue(_is_trivial_workflow_net(folded_net))


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
        self.assertEqual(step1.opaque_transition_id, "t_C1")

        step2 = result.steps[1]
        self.assertEqual(step2.component_type, ComponentType.SEQUENCE)
        self.assertEqual(step2.omega, 0.0)
        self.assertEqual(step2.tau, 7.0)
        self.assertEqual(step2.opaque_transition_id, "t_C2")
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

        self.assertFalse(_is_trivial_workflow_net(net))
        result = fold_net(net)
        self.assertFalse(result.fully_reducible)
        self.assertEqual(len(result.steps), 1)
        step = result.steps[0]
        self.assertEqual(step.component_type, ComponentType.UNSTRUCTURED)
        # Verify opaque transition has both input and output arcs connected to p0
        final_net = step.snapshot
        self.assertEqual(len(final_net.transitions), 1)
        opaque_t = final_net.transitions[0]
        self.assertEqual(len(final_net.arcs), 2)
        sources = {a.source.id for a in final_net.arcs}
        targets = {a.target.id for a in final_net.arcs}
        self.assertIn("p0", sources)
        self.assertIn(opaque_t.id, sources)
        self.assertIn("p0", targets)
        self.assertIn(opaque_t.id, targets)

    def test_single_place_self_loop_not_trivial_workflow_net(self):
        # A single-place net with a self-loop is NOT a trivial workflow net (must have distinct source and sink)
        net = PetriNet()
        p0 = net.add_place("p0")
        t0 = net.add_transition("t0")
        net.add_arc(p0, t0)
        net.add_arc(t0, p0)
        self.assertFalse(_is_trivial_workflow_net(net))


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
        # Penultimate net is step 1's snapshot
        self.assertEqual(result.penultimate_net, result.steps[0].snapshot)

    def test_penultimate_net_single_step(self):
        net, _, _, _ = build_sequence_net(2)
        result = fold_net(net)

        self.assertEqual(len(result.steps), 1)
        # For single step, penultimate net is initial net
        self.assertEqual(result.penultimate_net, result.initial_net)

    def test_json_serialization_schema(self):
        net, _, _, _ = build_sequence_net(2)
        result = fold_net(net)

        d = result.to_dict()
        self.assertNotIn("function", d)
        self.assertNotIn("file", d)
        self.assertIn("initial_net", d)
        self.assertIn("fold_steps", d)
        self.assertIn("final_sm", d)
        self.assertIn("fully_reducible", d)
        self.assertEqual(d["final_sm"], 2.0)
        self.assertTrue(d["fully_reducible"])

        step_d = d["fold_steps"][0]
        self.assertEqual(step_d["step"], 1)
        self.assertEqual(step_d["component_type"], "sequence")
        self.assertEqual(step_d["opaque_transition"], "t_C1")
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


class TestASTTopologyReduction(unittest.TestCase):
    def test_ast_if_else_reduction(self):
        """Validates that a synthetic AST if/else topology (matching wire_if_split) folds cleanly."""
        net = PetriNet()
        p_split = net.add_place("p_split", initial_tokens=1)
        p_true = net.add_place("p_true")
        p_false = net.add_place("p_false")
        p_merge = net.add_place("p_merge")

        t_if = net.add_transition("t_if")
        t_else = net.add_transition("t_else")
        t_stmt1 = net.add_transition("t_stmt1")
        t_stmt2 = net.add_transition("t_stmt2")

        # True branch: p_split -> t_if -> p_true -> t_stmt1 -> p_merge
        net.add_arc(p_split, t_if)
        net.add_arc(t_if, p_true)
        net.add_arc(p_true, t_stmt1)
        net.add_arc(t_stmt1, p_merge)

        # False branch: p_split -> t_else -> p_false -> t_stmt2 -> p_merge
        net.add_arc(p_split, t_else)
        net.add_arc(t_else, p_false)
        net.add_arc(p_false, t_stmt2)
        net.add_arc(t_stmt2, p_merge)

        result = fold_net(net)
        self.assertTrue(result.fully_reducible)
        # Sequence step 1 & 2 fold the two branches, Choice step 3 collapses the parallel branches
        self.assertEqual(len(result.steps), 3)
        self.assertEqual(result.steps[0].component_type, ComponentType.SEQUENCE)
        self.assertEqual(result.steps[1].component_type, ComponentType.SEQUENCE)
        self.assertEqual(result.steps[2].component_type, ComponentType.CHOICE)

        # Check no unstructured step occurred
        for s in result.steps:
            self.assertNotEqual(s.component_type, ComponentType.UNSTRUCTURED)

        final_net = result.steps[-1].snapshot
        self.assertEqual(len(final_net.transitions), 1)
        self.assertEqual(len(final_net.places), 2)

    def test_ast_if_without_else_reduction(self):
        """Validates an AST if statement with empty else (fallthrough branch)."""
        net = PetriNet()
        p_split = net.add_place("p_split", initial_tokens=1)
        p_true = net.add_place("p_true")
        p_merge = net.add_place("p_merge")

        t_if = net.add_transition("t_if")
        t_stmt = net.add_transition("t_stmt")
        t_fallthrough = net.add_transition("t_fallthrough")

        # True branch: p_split -> t_if -> p_true -> t_stmt -> p_merge
        net.add_arc(p_split, t_if)
        net.add_arc(t_if, p_true)
        net.add_arc(p_true, t_stmt)
        net.add_arc(t_stmt, p_merge)

        # Fallthrough branch: p_split -> t_fallthrough -> p_merge
        net.add_arc(p_split, t_fallthrough)
        net.add_arc(t_fallthrough, p_merge)

        result = fold_net(net)
        self.assertTrue(result.fully_reducible)
        # Step 1: Sequence folds p_true (t_if, t_stmt)
        # Step 2: Choice folds parallel branches between p_split and p_merge
        self.assertEqual(len(result.steps), 2)
        self.assertEqual(result.steps[0].component_type, ComponentType.SEQUENCE)
        self.assertEqual(result.steps[1].component_type, ComponentType.CHOICE)

        for s in result.steps:
            self.assertNotEqual(s.component_type, ComponentType.UNSTRUCTURED)

    def test_ast_nested_if_else_reduction(self):
        """Validates nested if/else AST structures reduce completely without unstructured fallback."""
        net = PetriNet()
        p_split = net.add_place("p_split", initial_tokens=1)
        p_outer_false = net.add_place("p_outer_false")
        p_merge = net.add_place("p_merge")

        # Outer false branch
        t_outer_else = net.add_transition("t_outer_else")
        t_stmt_outer_else = net.add_transition("t_stmt_outer_else")
        net.add_arc(p_split, t_outer_else)
        net.add_arc(t_outer_else, p_outer_false)
        net.add_arc(p_outer_false, t_stmt_outer_else)
        net.add_arc(t_stmt_outer_else, p_merge)

        # Outer true branch leads to nested split
        t_outer_if = net.add_transition("t_outer_if")
        p_inner_split = net.add_place("p_inner_split")
        net.add_arc(p_split, t_outer_if)
        net.add_arc(t_outer_if, p_inner_split)

        # Nested true branch
        p_inner_true = net.add_place("p_inner_true")
        p_inner_merge = net.add_place("p_inner_merge")
        t_inner_if = net.add_transition("t_inner_if")
        t_stmt_inner1 = net.add_transition("t_stmt_inner1")
        net.add_arc(p_inner_split, t_inner_if)
        net.add_arc(t_inner_if, p_inner_true)
        net.add_arc(p_inner_true, t_stmt_inner1)
        net.add_arc(t_stmt_inner1, p_inner_merge)

        # Nested false branch
        p_inner_false = net.add_place("p_inner_false")
        t_inner_else = net.add_transition("t_inner_else")
        t_stmt_inner2 = net.add_transition("t_stmt_inner2")
        net.add_arc(p_inner_split, t_inner_else)
        net.add_arc(t_inner_else, p_inner_false)
        net.add_arc(p_inner_false, t_stmt_inner2)
        net.add_arc(t_stmt_inner2, p_inner_merge)

        # From nested merge to outer merge
        t_after_nested = net.add_transition("t_after_nested")
        net.add_arc(p_inner_merge, t_after_nested)
        net.add_arc(t_after_nested, p_merge)

        result = fold_net(net)
        self.assertTrue(result.fully_reducible)
        for s in result.steps:
            self.assertNotEqual(s.component_type, ComponentType.UNSTRUCTURED)
        final_net = result.steps[-1].snapshot
        self.assertEqual(len(final_net.transitions), 1)


if __name__ == '__main__':
    unittest.main()
