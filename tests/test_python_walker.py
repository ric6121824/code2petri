import unittest
import sys
import os
import ast
import xml.etree.ElementTree as ET

# Ensure repo root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from code2petri.python_walker import walk_function, parse_file, find_function
from code2petri.model import PetriNet, Place, Transition, Arc


class TestPythonWalkerSequential(unittest.TestCase):
    def setUp(self):
        self.fixture_path = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "petri_py",
            "sequential.py",
        )
        self.tree = parse_file(self.fixture_path)
        self.func_node = find_function(self.tree, "sequential_func")

    def test_fixture_loaded(self):
        self.assertIsNotNone(self.func_node)
        self.assertIsInstance(self.func_node, (ast.FunctionDef, ast.AsyncFunctionDef))

    def test_sequential_counts(self):
        net = walk_function(self.func_node)
        self.assertIsInstance(net, PetriNet)
        # 5 sequential statements + 1 return: 6 transitions, 7 places, 12 arcs
        self.assertEqual(len(net.transitions), 6)
        self.assertEqual(len(net.places), 7)
        self.assertEqual(len(net.arcs), 12)

    def test_start_and_end_places(self):
        net = walk_function(self.func_node)
        # Exactly one place with initial_tokens == 1 (the start place)
        start_places = [p for p in net.places if p.initial_tokens == 1]
        self.assertEqual(len(start_places), 1)
        start_place = start_places[0]
        self.assertEqual(start_place.label, "start")

        # The start place has an outgoing arc to the first transition
        outgoing_start = [a for a in net.arcs if a.source == start_place]
        self.assertEqual(len(outgoing_start), 1)
        self.assertEqual(outgoing_start[0].target, net.transitions[0])

        # End place is the target of the last transition (return statement)
        end_places = [p for p in net.places if p.label == "end"]
        self.assertEqual(len(end_places), 1)
        end_place = end_places[0]
        incoming_end = [a for a in net.arcs if a.target == end_place]
        self.assertEqual(len(incoming_end), 1)
        self.assertEqual(incoming_end[0].source, net.transitions[-1])

    def test_linear_connectivity(self):
        net = walk_function(self.func_node)
        # Check that the net forms a strict linear alternating path
        current_place = [p for p in net.places if p.initial_tokens == 1][0]
        for t in net.transitions:
            # Arc from current_place to t
            p_to_t = [a for a in net.arcs if a.source == current_place and a.target == t]
            self.assertEqual(len(p_to_t), 1, f"Missing arc from {current_place.id} to {t.id}")

            # Arc from t to next place
            t_to_next = [a for a in net.arcs if a.source == t]
            self.assertEqual(len(t_to_next), 1, f"Expected 1 outgoing arc from {t.id}")
            current_place = t_to_next[0].target

        self.assertEqual(current_place.label, "end")

    def test_statement_labels_and_line_numbers(self):
        net = walk_function(self.func_node)
        labels = [t.label for t in net.transitions]
        expected_labels = [
            "a = 1",
            "b = 2",
            "c = a + b",
            "d = c * 2",
            "call: print()",
            "return d",
        ]
        self.assertEqual(labels, expected_labels)

        # Verify line numbers match source lines in sequential.py
        line_numbers = [t.line_number for t in net.transitions]
        self.assertEqual(line_numbers, [2, 3, 4, 5, 6, 7])

    def test_call_expression_variations(self):
        code = """def call_variations():
    plain_call()
    pkg.sub.func()
    res = helper()
    return res
"""
        tree = ast.parse(code)
        func_node = find_function(tree, "call_variations")
        net = walk_function(func_node)
        labels = [t.label for t in net.transitions]
        self.assertEqual(labels[0], "call: plain_call()")
        self.assertEqual(labels[1], "call: pkg.sub.func()")
        self.assertEqual(labels[2], "res = call: helper()")
        self.assertEqual(labels[3], "return res")



class TestPythonWalkerMultiReturn(unittest.TestCase):
    def setUp(self):
        self.fixture_path = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "petri_py",
            "multi_return.py",
        )
        self.tree = parse_file(self.fixture_path)
        self.func_node = find_function(self.tree, "multi_return_func")

    def test_fixture_loaded(self):
        self.assertIsNotNone(self.func_node)

    def test_all_returns_converge_on_single_end_place(self):
        net = walk_function(self.func_node)
        # Find single terminal end place
        end_places = [p for p in net.places if p.label == "end"]
        self.assertEqual(len(end_places), 1, "There must be exactly one shared terminal 'end' place")
        end_place = end_places[0]

        # Find all return transitions
        return_transitions = [t for t in net.transitions if t.label.startswith("return")]
        self.assertEqual(len(return_transitions), 2, "Expected 2 return transitions in multi_return_func")

        # Assert every return transition has an outgoing arc directly to end_place
        for ret_t in return_transitions:
            outgoing = [a for a in net.arcs if a.source == ret_t]
            self.assertEqual(len(outgoing), 1, f"Return transition {ret_t.id} must have exactly 1 outgoing arc")
            self.assertIs(
                outgoing[0].target,
                end_place,
                f"Return transition {ret_t.id} must target the shared end place, got {outgoing[0].target.id}",
            )

    def test_multi_return_pnml_and_dot_serialization(self):
        net = walk_function(self.func_node)
        pnml = net.to_pnml()
        root = ET.fromstring(pnml)
        self.assertIsNotNone(root)

        dot = net.to_dot()
        self.assertTrue(dot.strip().startswith("digraph"))
        self.assertTrue(dot.strip().endswith("}"))


class TestPythonWalkerEdgeCases(unittest.TestCase):
    def test_invalid_ast_node_type_raises(self):
        invalid_node = ast.Pass()
        with self.assertRaises(TypeError):
            walk_function(invalid_node)  # type: ignore

    def test_find_function_not_found(self):
        tree = ast.parse("def existing_func(): pass")
        self.assertIsNone(find_function(tree, "non_existent"))

    def test_async_function_support(self):
        code = """async def async_worker():
    await do_work()
    return 42
"""
        tree = ast.parse(code)
        func_node = find_function(tree, "async_worker")
        self.assertIsNotNone(func_node)
        net = walk_function(func_node)
        self.assertEqual(len(net.places), 3)  # p0, p1, p_end
        self.assertEqual(len(net.transitions), 2)  # await, return


if __name__ == '__main__':
    unittest.main()



