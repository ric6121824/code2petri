import unittest
import sys
import os
import ast

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from code2petri.python_walker import walk_function, parse_file, find_function
from code2petri.model import PetriNet, Place, Transition, Arc


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
        # 4 transitions: t_cond(if), t_true(y=1), t_false(y=2), t_ret(return y)
        self.assertEqual(len(net.transitions), 4)
        # 5 places: p0(start), p_true, p_false, p_merge, p_end
        self.assertEqual(len(net.places), 5)
        # 9 arcs
        self.assertEqual(len(net.arcs), 9)

    def test_fork_and_merge_structure(self):
        net = walk_function(self.func_node)

        # Condition transition
        cond_transitions = [t for t in net.transitions if "if" in t.label]
        self.assertEqual(len(cond_transitions), 1)
        cond_t = cond_transitions[0]

        # Condition transition forks into 2 places
        cond_outputs = [a.target for a in net.arcs if a.source == cond_t]
        self.assertEqual(len(cond_outputs), 2)
        p_true, p_false = cond_outputs
        self.assertNotEqual(p_true, p_false)

        # True branch transition
        true_trans = [a.target for a in net.arcs if a.source == p_true]
        self.assertEqual(len(true_trans), 1)
        t_true = true_trans[0]
        self.assertIn("y = 1", t_true.label)

        # False branch transition
        false_trans = [a.target for a in net.arcs if a.source == p_false]
        self.assertEqual(len(false_trans), 1)
        t_false = false_trans[0]
        self.assertIn("y = 2", t_false.label)

        # Both branches merge into the same merge place
        true_exit_places = [a.target for a in net.arcs if a.source == t_true]
        false_exit_places = [a.target for a in net.arcs if a.source == t_false]
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
        # 4 transitions: y=0, if x > 0, y=1, return y
        self.assertEqual(len(net.transitions), 4)
        # 5 places: p0(start), p1(after y=0), p2(true entry), p3(merge), p_end
        self.assertEqual(len(net.places), 5)
        # 9 arcs
        self.assertEqual(len(net.arcs), 9)

    def test_false_branch_skips_directly_to_merge(self):
        net = walk_function(self.func_node)

        # Condition transition
        cond_transitions = [t for t in net.transitions if "if" in t.label]
        self.assertEqual(len(cond_transitions), 1)
        cond_t = cond_transitions[0]

        # Transition for y = 1 (true branch)
        y1_transitions = [t for t in net.transitions if "y = 1" in t.label]
        self.assertEqual(len(y1_transitions), 1)
        t_y1 = y1_transitions[0]

        # Target place of y = 1 is the merge place
        y1_outputs = [a.target for a in net.arcs if a.source == t_y1]
        self.assertEqual(len(y1_outputs), 1)
        merge_place = y1_outputs[0]

        # Condition transition has 2 outputs: one to true branch entry place, one skipping directly to merge place!
        cond_outputs = [a.target for a in net.arcs if a.source == cond_t]
        self.assertEqual(len(cond_outputs), 2)
        self.assertIn(merge_place, cond_outputs, "False branch arc must skip directly to the merge place")

        # The other output is the entry place to t_y1
        true_entry = [p for p in cond_outputs if p != merge_place][0]
        true_entry_outputs = [a.target for a in net.arcs if a.source == true_entry]
        self.assertEqual(true_entry_outputs, [t_y1])


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
        # 6 transitions: if x > 0, y=1, if x < 0, y=-1, y=0, return y
        self.assertEqual(len(net.transitions), 6)
        # 7 places: p0(start), p1(true1), p2(false1/elif entry), p3(true2), p4(else), p5(merge), p_end
        self.assertEqual(len(net.places), 7)
        # 14 arcs
        self.assertEqual(len(net.arcs), 14)

    def test_cascading_elif_and_shared_merge(self):
        net = walk_function(self.func_node)

        # Transition 1: outer if
        t_if1 = next(t for t in net.transitions if "if x > 0" in t.label)
        # Transition 2: inner if (elif)
        t_if2 = next(t for t in net.transitions if "if x < 0" in t.label)

        # False branch of outer if feeds into the entry place of inner if (elif)
        if1_outputs = [a.target for a in net.arcs if a.source == t_if1]
        self.assertEqual(len(if1_outputs), 2)

        if2_inputs = [a.source for a in net.arcs if a.target == t_if2]
        self.assertEqual(len(if2_inputs), 1)
        elif_entry_place = if2_inputs[0]
        self.assertIn(elif_entry_place, if1_outputs, "Outer if false branch must connect to elif condition transition")

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


