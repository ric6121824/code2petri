import unittest
import sys
import os
import ast

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from code2petri.python_walker import walk_function, parse_file, find_function  # noqa: E402
from code2petri.model import PetriNet, Place, Transition, Arc  # noqa: E402


class TestIfElseBranching(unittest.TestCase):
    def setUp(self):
        self.fixture_path = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "petri_py",
            "if_else.py",
        )
        self.tree = parse_file(self.fixture_path)
        self.func_node = find_function(self.tree, "if_else_func")

    def test_fixture_loaded(self):
        self.assertIsNotNone(self.func_node)

    def test_if_else_counts(self):
        net = walk_function(self.func_node)
        self.assertIsInstance(net, PetriNet)
        # 5 transitions: t_true_cond(if x > 0), t_true_body(y = 1),
        #                t_false_cond(else), t_false_body(y = 2), t_ret(return y)
        self.assertEqual(len(net.transitions), 5)
        # 5 places: p0(start/decision), p_true, p_false, p_merge, p_end
        self.assertEqual(len(net.places), 5)
        # 10 arcs
        self.assertEqual(len(net.arcs), 10)

    def test_fork_and_merge_structure(self):
        net = walk_function(self.func_node)

        # Decision place (start place p0)
        start_place = next(p for p in net.places if p.initial_tokens == 1)

        # Standard XOR-split: start place connects to 2 competing transitions
        decision_outgoing_trans = [a.target for a in net.arcs if a.source == start_place]
        self.assertEqual(len(decision_outgoing_trans), 2)

        t_if = next(t for t in decision_outgoing_trans if "if x > 0" in t.label)
        t_else = next(t for t in decision_outgoing_trans if t.label == "else")

        # True condition transition leads to true entry place
        t_if_outputs = [a.target for a in net.arcs if a.source == t_if]
        self.assertEqual(len(t_if_outputs), 1)
        p_true_entry = t_if_outputs[0]

        # False/else condition transition leads to else entry place
        t_else_outputs = [a.target for a in net.arcs if a.source == t_else]
        self.assertEqual(len(t_else_outputs), 1)
        p_else_entry = t_else_outputs[0]

        self.assertNotEqual(p_true_entry, p_else_entry)

        # True branch body transition (y = 1)
        true_trans = [a.target for a in net.arcs if a.source == p_true_entry]
        self.assertEqual(len(true_trans), 1)
        t_true_body = true_trans[0]
        self.assertIn("y = 1", t_true_body.label)

        # False branch body transition (y = 2)
        false_trans = [a.target for a in net.arcs if a.source == p_else_entry]
        self.assertEqual(len(false_trans), 1)
        t_false_body = false_trans[0]
        self.assertIn("y = 2", t_false_body.label)

        # Both branches merge into the same XOR-join merge place
        true_exit_places = [a.target for a in net.arcs if a.source == t_true_body]
        false_exit_places = [a.target for a in net.arcs if a.source == t_false_body]
        self.assertEqual(len(true_exit_places), 1)
        self.assertEqual(len(false_exit_places), 1)
        merge_place = true_exit_places[0]
        self.assertIs(merge_place, false_exit_places[0])
        self.assertNotEqual(merge_place.label, "end")

        # Merge place flows into return transition
        ret_trans = [a.target for a in net.arcs if a.source == merge_place]
        self.assertEqual(len(ret_trans), 1)
        t_ret = ret_trans[0]
        self.assertIn("return y", t_ret.label)

        # Return transition arcs to end place
        end_places = [a.target for a in net.arcs if a.source == t_ret]
        self.assertEqual(len(end_places), 1)
        self.assertEqual(end_places[0].label, "end")

    def test_choice_semantics_and_mutual_exclusion(self):
        """Verifies standard Petri net XOR-split: 1 decision place, 2 competing transitions, each with 1 output."""
        net = walk_function(self.func_node)

        start_place = next(p for p in net.places if p.initial_tokens == 1)
        competing_transitions = [a.target for a in net.arcs if a.source == start_place]

        # The decision place must branch into exactly 2 alternative transitions (XOR-split)
        self.assertEqual(len(competing_transitions), 2)

        # Neither transition is an AND-fork: each must have exactly 1 output place
        for t in competing_transitions:
            outputs = [a.target for a in net.arcs if a.source == t]
            self.assertEqual(
                len(outputs), 1,
                f"Transition {t.id} ({t.label}) must have exactly 1 output place (not an AND-fork)",
            )
            # Each competing transition has only the decision place as preset
            inputs = [a.source for a in net.arcs if a.target == t]
            self.assertEqual(inputs, [start_place])



class TestIfNoElseBranching(unittest.TestCase):
    def setUp(self):
        self.fixture_path = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "petri_py",
            "if_no_else.py",
        )
        self.tree = parse_file(self.fixture_path)
        self.func_node = find_function(self.tree, "if_no_else_func")

    def test_fixture_loaded(self):
        self.assertIsNotNone(self.func_node)

    def test_if_no_else_counts(self):
        net = walk_function(self.func_node)
        self.assertIsInstance(net, PetriNet)
        # 5 transitions: y=0, if x > 0, y=1, else, return y
        self.assertEqual(len(net.transitions), 5)
        # 5 places: p0(start), p1(decision after y=0), p_true, p_merge, p_end
        self.assertEqual(len(net.places), 5)
        # 10 arcs
        self.assertEqual(len(net.arcs), 10)

    def test_false_branch_skips_directly_to_merge(self):
        net = walk_function(self.func_node)

        # Transition for y = 0 feeds the decision place
        t_y0 = next(t for t in net.transitions if "y = 0" in t.label)
        y0_outputs = [a.target for a in net.arcs if a.source == t_y0]
        self.assertEqual(len(y0_outputs), 1)
        decision_place = y0_outputs[0]

        # Standard XOR-split: decision place has 2 competing transitions
        decision_outgoing = [a.target for a in net.arcs if a.source == decision_place]
        self.assertEqual(len(decision_outgoing), 2)

        t_if = next(t for t in decision_outgoing if "if x > 0" in t.label)
        t_else = next(t for t in decision_outgoing if t.label == "else")

        # True branch: t_if -> p_true -> t_y1 -> merge_place
        t_if_outputs = [a.target for a in net.arcs if a.source == t_if]
        self.assertEqual(len(t_if_outputs), 1)
        p_true = t_if_outputs[0]

        t_y1 = next(t for t in net.transitions if "y = 1" in t.label)
        y1_inputs = [a.source for a in net.arcs if a.target == t_y1]
        self.assertEqual(y1_inputs, [p_true])

        y1_outputs = [a.target for a in net.arcs if a.source == t_y1]
        self.assertEqual(len(y1_outputs), 1)
        merge_place = y1_outputs[0]

        # False branch (no else): t_else skips directly to the merge place!
        else_outputs = [a.target for a in net.arcs if a.source == t_else]
        self.assertEqual(len(else_outputs), 1)
        self.assertIs(
            else_outputs[0],
            merge_place,
            "False branch transition must skip directly to the merge place",
        )

        # Both paths merge before return y
        ret_trans = next(t for t in net.transitions if "return y" in t.label)
        ret_inputs = [a.source for a in net.arcs if a.target == ret_trans]
        self.assertEqual(ret_inputs, [merge_place])


class TestIfElifElseBranching(unittest.TestCase):
    def setUp(self):
        self.fixture_path = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "petri_py",
            "if_elif_else.py",
        )
        self.tree = parse_file(self.fixture_path)
        self.func_node = find_function(self.tree, "if_elif_else_func")

    def test_fixture_loaded(self):
        self.assertIsNotNone(self.func_node)

    def test_if_elif_else_counts(self):
        net = walk_function(self.func_node)
        self.assertIsInstance(net, PetriNet)
        # 8 transitions:
        #   Outer if: t_if1(if x > 0), t_else1(else)
        #   Outer body: t_y1(y = 1)
        #   Elif: t_if2(if x < 0), t_else2(else)
        #   Elif body: t_y_neg(y = -1)
        #   Final else body: t_y0(y = 0)
        #   Return: t_ret(return y)
        self.assertEqual(len(net.transitions), 8)
        # 7 places: p0(decision1), p_true1, p_elif_decision, p_true2, p_else_body, p_merge, p_end
        self.assertEqual(len(net.places), 7)
        # 16 arcs
        self.assertEqual(len(net.arcs), 16)

    def test_cascading_elif_and_shared_merge(self):
        net = walk_function(self.func_node)

        start_place = next(p for p in net.places if p.initial_tokens == 1)

        # Outer XOR-split from start place
        outer_transitions = [a.target for a in net.arcs if a.source == start_place]
        self.assertEqual(len(outer_transitions), 2)
        t_if1 = next(t for t in outer_transitions if "if x > 0" in t.label)
        t_else1 = next(t for t in outer_transitions if t.label == "else")

        # Outer else transition connects to the elif decision place
        else1_outputs = [a.target for a in net.arcs if a.source == t_else1]
        self.assertEqual(len(else1_outputs), 1)
        elif_decision_place = else1_outputs[0]

        # Inner XOR-split from elif decision place
        inner_transitions = [a.target for a in net.arcs if a.source == elif_decision_place]
        self.assertEqual(len(inner_transitions), 2)
        t_if2 = next(t for t in inner_transitions if "if x < 0" in t.label)
        t_else2 = next(t for t in inner_transitions if t.label == "else")

        # The 3 branch execution transitions: y = 1, y = -1, y = 0
        t_y1 = next(t for t in net.transitions if "y = 1" in t.label)
        t_y_neg = next(t for t in net.transitions if "y = -1" in t.label)
        t_y0 = next(t for t in net.transitions if "y = 0" in t.label)

        # All 3 branches must converge on the exact same merge place
        out_y1 = [a.target for a in net.arcs if a.source == t_y1][0]
        out_y_neg = [a.target for a in net.arcs if a.source == t_y_neg][0]
        out_y0 = [a.target for a in net.arcs if a.source == t_y0][0]

        self.assertIs(out_y1, out_y_neg, "True branch 1 and elif true branch must merge into the same place")
        self.assertIs(out_y1, out_y0, "All three branches must merge into the same place")
        merge_place = out_y1
        self.assertNotEqual(merge_place.label, "end")

        # The return transition must read from the shared merge place
        t_ret = next(t for t in net.transitions if "return y" in t.label)
        ret_inputs = [a.source for a in net.arcs if a.target == t_ret]
        self.assertEqual(ret_inputs, [merge_place])

        # Return transition must target end place
        ret_outputs = [a.target for a in net.arcs if a.source == t_ret]
        self.assertEqual(len(ret_outputs), 1)
        self.assertEqual(ret_outputs[0].label, "end")


if __name__ == '__main__':
    unittest.main()


