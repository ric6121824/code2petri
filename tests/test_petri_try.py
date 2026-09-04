import ast
import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from code2petri.python_walker import walk_function, parse_file, find_function  # noqa: E402
from code2petri.model import PetriNet, Place, Transition, Arc  # noqa: E402


class TestTryExcept(unittest.TestCase):
    def setUp(self):
        self.fixture_path = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "petri_py",
            "try_except.py",
        )
        self.tree = parse_file(self.fixture_path)
        self.func_node = find_function(self.tree, "try_except_func")

    def test_fixture_loaded(self):
        self.assertIsNotNone(self.func_node)

    def test_try_except_counts(self):
        net = walk_function(self.func_node)
        self.assertIsInstance(net, PetriNet)
        # 6 transitions: a = 1, b = a + 1, c = b * 2, except, c = 0, return c
        self.assertEqual(len(net.transitions), 6)
        # 7 places: p0(start), p1, p2, p_except, p_hand_entry, p_merge, p_end
        self.assertEqual(len(net.places), 7)
        # 14 arcs
        self.assertEqual(len(net.arcs), 14)

    def test_exception_arcs_from_try_body_transitions(self):
        net = walk_function(self.func_node)

        # Locate except_entry place
        p_except = next(p for p in net.places if "except_entry" in p.label)

        # Locate the transitions within the try body
        t_b = next(t for t in net.transitions if "b = a + 1" in t.label)
        t_c = next(t for t in net.transitions if "c = b * 2" in t.label)

        # Assert exception arcs exist from each try-body transition to except_entry
        t_b_targets = [a.target for a in net.arcs if a.source == t_b]
        t_c_targets = [a.target for a in net.arcs if a.source == t_c]

        self.assertIn(p_except, t_b_targets)
        self.assertIn(p_except, t_c_targets)

    def test_except_handler_and_merge(self):
        net = walk_function(self.func_node)

        p_except = next(p for p in net.places if "except_entry" in p.label)

        # Except handler transition
        t_handler = next(t for t in net.transitions if t.label == "except")
        handler_inputs = [a.source for a in net.arcs if a.target == t_handler]
        self.assertEqual(handler_inputs, [p_except])

        # Body transition in handler (c = 0)
        t_c0 = next(t for t in net.transitions if "c = 0" in t.label)

        # Both normal try exit and handler body exit merge at the same place
        t_c = next(t for t in net.transitions if "c = b * 2" in t.label)
        t_c_exit = next(a.target for a in net.arcs if a.source == t_c and a.target != p_except)
        t_c0_exit = next(a.target for a in net.arcs if a.source == t_c0)
        self.assertEqual(t_c_exit, t_c0_exit)

        # The merge place flows into return c
        t_ret = next(t for t in net.transitions if "return c" in t.label)
        ret_inputs = [a.source for a in net.arcs if a.target == t_ret]
        self.assertEqual(ret_inputs, [t_c_exit])



class TestTryExceptFinally(unittest.TestCase):
    def setUp(self):
        self.fixture_path = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "petri_py",
            "try_except_finally.py",
        )
        self.tree = parse_file(self.fixture_path)
        self.func_node = find_function(self.tree, "try_except_finally_func")

    def test_fixture_loaded(self):
        self.assertIsNotNone(self.func_node)

    def test_try_except_finally_counts(self):
        net = walk_function(self.func_node)
        self.assertIsInstance(net, PetriNet)
        # 6 transitions: x = 10, x = x + 1, except Exception as e, x = -1, x = x * 2, return x
        self.assertEqual(len(net.transitions), 6)
        # 7 places: p0, p1, p_exc, p_h_entry, p_finally, p_try_exit, p_end
        self.assertEqual(len(net.places), 7)
        # 13 arcs
        self.assertEqual(len(net.arcs), 13)

    def test_finally_mandatory_convergence(self):
        net = walk_function(self.func_node)

        p_finally = next(p for p in net.places if "finally_entry" in p.label)
        p_except = next(p for p in net.places if "except_entry" in p.label)

        # Normal try body transition: x = x + 1
        t_try = next(t for t in net.transitions if "x = x + 1" in t.label)
        # Exception handler body transition: x = -1
        t_handler_body = next(t for t in net.transitions if "x = -1" in t.label)

        # Both normal try and handler body must have an outgoing arc to p_finally
        self.assertIn(p_finally, [a.target for a in net.arcs if a.source == t_try])
        self.assertIn(p_finally, [a.target for a in net.arcs if a.source == t_handler_body])

        # Finally block transition: x = x * 2
        t_finally = next(t for t in net.transitions if "x = x * 2" in t.label)
        self.assertEqual([a.source for a in net.arcs if a.target == t_finally], [p_finally])

        # The exit of the finally transition flows to try_exit which flows to return x
        t_ret = next(t for t in net.transitions if "return x" in t.label)
        t_finally_outputs = [a.target for a in net.arcs if a.source == t_finally]
        self.assertEqual(len(t_finally_outputs), 1)
        p_try_exit = t_finally_outputs[0]
        self.assertEqual([a.source for a in net.arcs if a.target == t_ret], [p_try_exit])



class TestTryMultiExcept(unittest.TestCase):
    def setUp(self):
        self.fixture_path = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "petri_py",
            "try_multi_except.py",
        )
        self.tree = parse_file(self.fixture_path)
        self.func_node = find_function(self.tree, "try_multi_except_func")

    def test_fixture_loaded(self):
        self.assertIsNotNone(self.func_node)

    def test_multi_except_counts(self):
        net = walk_function(self.func_node)
        self.assertIsInstance(net, PetriNet)
        # 9 transitions: val = 0, val = 1, except ValueError, val = 2, except TypeError, val = 3, except, val = 4, return val
        self.assertEqual(len(net.transitions), 9)
        # 8 places: p0, p1, p_exc, p_h1, p_h2, p_h3, p_try_exit, p_end
        self.assertEqual(len(net.places), 8)
        # 19 arcs
        self.assertEqual(len(net.arcs), 19)

    def test_parallel_except_paths(self):
        net = walk_function(self.func_node)

        p_except = next(p for p in net.places if "except_entry" in p.label)

        # Three competing handler transitions from except_entry
        handler_trans = [a.target for a in net.arcs if a.source == p_except]
        self.assertEqual(len(handler_trans), 3)

        labels = {t.label for t in handler_trans}
        self.assertIn("except ValueError", labels)
        self.assertIn("except TypeError", labels)
        self.assertIn("except", labels)

        # Body transitions
        t_v2 = next(t for t in net.transitions if "val = 2" in t.label)
        t_v3 = next(t for t in net.transitions if "val = 3" in t.label)
        t_v4 = next(t for t in net.transitions if "val = 4" in t.label)

        # Normal try exit
        t_v1 = next(t for t in net.transitions if "val = 1" in t.label)
        t_v1_exit = next(a.target for a in net.arcs if a.source == t_v1 and a.target != p_except)

        # All handlers and normal exit merge at the same exit place
        self.assertEqual(next(a.target for a in net.arcs if a.source == t_v2), t_v1_exit)
        self.assertEqual(next(a.target for a in net.arcs if a.source == t_v3), t_v1_exit)
        self.assertEqual(next(a.target for a in net.arcs if a.source == t_v4), t_v1_exit)



class TestTryElseAndNesting(unittest.TestCase):
    def setUp(self):
        self.fixture_path = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "petri_py",
            "try_else_finally.py",
        )
        self.tree = parse_file(self.fixture_path)
        self.func_node = find_function(self.tree, "try_else_finally_func")

    def test_fixture_loaded(self):
        self.assertIsNotNone(self.func_node)

    def test_try_else_flow(self):
        net = walk_function(self.func_node)

        p_else = next(p for p in net.places if "else_entry" in p.label)
        p_finally = next(p for p in net.places if "finally_entry" in p.label)

        # Normal try body transition (val = 1) outputs to else_entry
        t_v1 = next(t for t in net.transitions if "val = 1" in t.label)
        t_v1_outputs = [a.target for a in net.arcs if a.source == t_v1]
        self.assertIn(p_else, t_v1_outputs)

        # Else body transition (val = 3) has input else_entry and output finally_entry
        t_else = next(t for t in net.transitions if "val = 3" in t.label)
        self.assertEqual([a.source for a in net.arcs if a.target == t_else], [p_else])
        self.assertIn(p_finally, [a.target for a in net.arcs if a.source == t_else])

        # Exception handler body transition (val = 2) bypasses else_entry and outputs directly to finally_entry
        t_handler = next(t for t in net.transitions if "val = 2" in t.label)
        t_h_outputs = [a.target for a in net.arcs if a.source == t_handler]
        self.assertIn(p_finally, t_h_outputs)
        self.assertNotIn(p_else, t_h_outputs)

        # Finally body transition (val = 4) has input finally_entry
        t_finally = next(t for t in net.transitions if "val = 4" in t.label)
        self.assertEqual([a.source for a in net.arcs if a.target == t_finally], [p_finally])

    def test_nested_try(self):
        code = (
            "def nested_try_func():\n"
            "    try:\n"
            "        x = 1\n"
            "        try:\n"
            "            x = 2\n"
            "        except:\n"
            "            x = 3\n"
            "        x = 4\n"
            "    except:\n"
            "        x = 5\n"
            "    return x\n"
        )
        tree = ast.parse(code)
        func = tree.body[0]
        net = walk_function(func)

        # Identify the two except_entry places
        except_places = [p for p in net.places if "except_entry" in p.label]
        self.assertEqual(len(except_places), 2)

        p_outer_exc = except_places[0]
        p_inner_exc = except_places[1]

        t_x1 = next(t for t in net.transitions if "x = 1" in t.label)
        t_x2 = next(t for t in net.transitions if "x = 2" in t.label)
        t_x4 = next(t for t in net.transitions if "x = 4" in t.label)

        # x = 1 and x = 4 arc to outer except_entry
        self.assertIn(p_outer_exc, [a.target for a in net.arcs if a.source == t_x1])
        self.assertIn(p_outer_exc, [a.target for a in net.arcs if a.source == t_x4])

        # x = 2 arcs to inner except_entry, not outer
        self.assertIn(p_inner_exc, [a.target for a in net.arcs if a.source == t_x2])
        self.assertNotIn(p_outer_exc, [a.target for a in net.arcs if a.source == t_x2])

        # Inner handler entry transition (t_except) does not arc to outer except_entry
        t_inner_handler = next(t for t in net.transitions if t.label == "except" and any(a.source == p_inner_exc for a in net.arcs if a.target == t))
        self.assertNotIn(p_outer_exc, [a.target for a in net.arcs if a.source == t_inner_handler])

    def test_try_finally_without_except(self):
        code = (
            "def try_finally_func():\n"
            "    try:\n"
            "        a = 1\n"
            "    finally:\n"
            "        b = 2\n"
            "    return b\n"
        )
        tree = ast.parse(code)
        func = tree.body[0]
        net = walk_function(func)

        p_except = next(p for p in net.places if p.label == "except_entry")
        p_finally = next(p for p in net.places if p.label == "finally_entry")

        # Unhandled exception flows via 'exception' transition to finally_entry
        t_exc = next(t for t in net.transitions if t.label == "exception")
        self.assertIn(t_exc, [a.target for a in net.arcs if a.source == p_except])
        self.assertIn(p_finally, [a.target for a in net.arcs if a.source == t_exc])


if __name__ == '__main__':
    unittest.main()
