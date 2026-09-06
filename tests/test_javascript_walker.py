import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from code2petri.javascript_walker import JavascriptWalker
from code2petri.walker_protocol import WalkerProtocol
from code2petri.engine import code2petri, WALKERS
from tests.petri_assertions import assert_valid_petri_net, assert_has_start_and_end, assert_bipartite


class TestJavascriptWalkerSkeleton(unittest.TestCase):
    def setUp(self):
        self.walker = JavascriptWalker()
        self.seq_fixture = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "petri_js",
            "sequential.js",
        )
        self.global_fixture = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "petri_js",
            "global_script.js",
        )

    def test_implements_walker_protocol(self):
        self.assertIsInstance(self.walker, WalkerProtocol)

    def test_parse_file_and_caching(self):
        tree = self.walker.parse_file(self.seq_fixture)
        self.assertIsInstance(tree, dict)
        self.assertEqual(tree.get("type"), "Program")
        self.assertIsNotNone(self.walker.raw_source)
        self.assertIn("function sequential_func()", self.walker.raw_source)

    def test_find_all_functions_in_file(self):
        tree = self.walker.parse_file(self.seq_fixture)
        funcs = self.walker.find_all_functions(tree)
        self.assertIn("sequential_func", funcs)

    def test_global_scope_discovery(self):
        tree = self.walker.parse_file(self.global_fixture)
        funcs = self.walker.find_all_functions(tree)
        self.assertEqual(funcs, ["(global)", "init"])

    def test_find_function_regular(self):
        tree = self.walker.parse_file(self.seq_fixture)
        node = self.walker.find_function(tree, "sequential_func")
        self.assertIsNotNone(node)
        self.assertEqual(node.get("type"), "FunctionDeclaration")
        self.assertEqual(node["id"]["name"], "sequential_func")

    def test_find_function_global(self):
        tree = self.walker.parse_file(self.global_fixture)
        global_node = self.walker.find_function(tree, "(global)")
        self.assertIsNotNone(global_node)
        self.assertEqual(global_node.get("type"), "FunctionDeclaration")
        self.assertEqual(global_node["id"]["name"], "(global)")
        # Body contains the 3 executable statements (let x, let y, init()), not function init
        body_stmts = global_node["body"]["body"]
        self.assertEqual(len(body_stmts), 3)

    def test_find_function_global_returns_none_when_no_executable_statements(self):
        tree = self.walker.parse_file(self.seq_fixture)
        # sequential.js only contains function sequential_func()
        global_node = self.walker.find_function(tree, "(global)")
        self.assertIsNone(global_node)

    def test_walk_assignment_with_call_expression(self):
        fixture_path = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "petri_js",
            "assign_call.js",
        )
        tree = self.walker.parse_file(fixture_path)
        node = self.walker.find_function(tree, "calc_caller")
        net = self.walker.walk_function(node)
        labels = [t.label for t in net.transitions]
        self.assertEqual(labels, ["let res = call: calculate()", "return res"])

    def test_walk_sequential_function(self):
        tree = self.walker.parse_file(self.seq_fixture)
        node = self.walker.find_function(tree, "sequential_func")
        net = self.walker.walk_function(node)

        # 5 sequential statements + 1 return -> 6 transitions, 7 places, 12 arcs
        assert_valid_petri_net(self, net)
        self.assertEqual(len(net.transitions), 6)
        self.assertEqual(len(net.places), 7)
        self.assertEqual(len(net.arcs), 12)

        # Sliced transition labels
        labels = [t.label for t in net.transitions]
        expected_labels = [
            "let a = 1",
            "let b = 2",
            "let c = a + b",
            "let d = c * 2",
            "call: print()",
            "return d",
        ]
        self.assertEqual(labels, expected_labels)

        # Line numbers
        lines = [t.line_number for t in net.transitions]
        self.assertEqual(lines, [2, 3, 4, 5, 6, 7])

    def test_walk_global_scope(self):
        tree = self.walker.parse_file(self.global_fixture)
        global_node = self.walker.find_function(tree, "(global)")
        net = self.walker.walk_function(global_node)

        # 3 sequential statements, no return -> 3 transitions, 4 places, 6 arcs
        assert_valid_petri_net(self, net)
        self.assertEqual(len(net.transitions), 3)
        self.assertEqual(len(net.places), 4)
        self.assertEqual(len(net.arcs), 6)

        labels = [t.label for t in net.transitions]
        expected_labels = [
            "let x = 10",
            "let y = 20",
            "call: init()",
        ]
        self.assertEqual(labels, expected_labels)


class TestEngineJavascriptIntegration(unittest.TestCase):
    def setUp(self):
        self.seq_fixture = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "petri_js",
            "sequential.js",
        )
        self.global_fixture = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "petri_js",
            "global_script.js",
        )

    def test_walkers_registry_has_javascript(self):
        self.assertIn(".js", WALKERS)
        self.assertEqual(WALKERS[".js"], JavascriptWalker)

    def test_engine_end_to_end_sequential_js(self):
        net = code2petri(self.seq_fixture, output_file=None, target_function="sequential_func")
        self.assertIsNotNone(net)
        assert_valid_petri_net(self, net)
        self.assertEqual(len(net.transitions), 6)

    def test_engine_end_to_end_global_js(self):
        net = code2petri(self.global_fixture, output_file=None, target_function="(global)")
        self.assertIsNotNone(net)
        assert_valid_petri_net(self, net)
        self.assertEqual(len(net.transitions), 3)


class TestJavascriptIfBranching(unittest.TestCase):
    def setUp(self):
        self.walker = JavascriptWalker()
        self.fixtures_dir = os.path.join(os.path.dirname(__file__), "test_code", "petri_js")

    def test_if_else(self):
        tree = self.walker.parse_file(os.path.join(self.fixtures_dir, "if_else.js"))
        node = self.walker.find_function(tree, "if_else_func")
        net = self.walker.walk_function(node)
        assert_valid_petri_net(self, net)
        assert_has_start_and_end(self, net)
        assert_bipartite(self, net)

        # Decision place (XOR-split): 1 place with 2 outgoing arcs
        branch_places = [p for p in net.places if len([a for a in net.arcs if a.source == p]) == 2]
        self.assertEqual(len(branch_places), 1)
        decision_place = branch_places[0]
        decision_outgoing = [a.target for a in net.arcs if a.source == decision_place]
        self.assertEqual(set(t.label for t in decision_outgoing), {"if (x > 0)", "else"})

        # Convergence: both branches reach the same merge place before return
        t_true_body = next(t for t in net.transitions if t.label == "result = 1")
        t_false_body = next(t for t in net.transitions if t.label == "result = -1")
        true_exit_places = [a.target for a in net.arcs if a.source == t_true_body]
        false_exit_places = [a.target for a in net.arcs if a.source == t_false_body]
        self.assertEqual(len(true_exit_places), 1)
        self.assertEqual(len(false_exit_places), 1)
        self.assertIs(true_exit_places[0], false_exit_places[0])
        merge_place = true_exit_places[0]

        # Merge place flows into return
        t_ret = next(t for t in net.transitions if t.label == "return result")
        self.assertTrue(any(a.source == merge_place and a.target == t_ret for a in net.arcs))

    def test_if_elif_else(self):
        tree = self.walker.parse_file(os.path.join(self.fixtures_dir, "if_elif_else.js"))
        node = self.walker.find_function(tree, "if_elif_else_func")
        net = self.walker.walk_function(node)
        assert_valid_petri_net(self, net)
        assert_bipartite(self, net)

        # Both outer and inner if statements have decision places (2 outgoing arcs)
        branch_places = [p for p in net.places if len([a for a in net.arcs if a.source == p]) == 2]
        self.assertEqual(len(branch_places), 2)

        # All three branches converge to the same merge place
        t_b1 = next(t for t in net.transitions if t.label == "result = 1")
        t_b2 = next(t for t in net.transitions if t.label == "result = 2")
        t_b3 = next(t for t in net.transitions if t.label == "result = 3")
        exit_b1 = next(a.target for a in net.arcs if a.source == t_b1)
        exit_b2 = next(a.target for a in net.arcs if a.source == t_b2)
        exit_b3 = next(a.target for a in net.arcs if a.source == t_b3)
        self.assertIs(exit_b1, exit_b2)
        self.assertIs(exit_b2, exit_b3)

    def test_if_no_else(self):
        tree = self.walker.parse_file(os.path.join(self.fixtures_dir, "if_no_else.js"))
        node = self.walker.find_function(tree, "if_no_else_func")
        net = self.walker.walk_function(node)
        assert_valid_petri_net(self, net)
        assert_bipartite(self, net)

        # False transition (else) skips directly to the merge place of true branch
        t_if_body = next(t for t in net.transitions if t.label == "result = 1")
        merge_place = next(a.target for a in net.arcs if a.source == t_if_body)
        t_else = next(t for t in net.transitions if t.label == "else")
        self.assertTrue(any(a.source == t_else and a.target == merge_place for a in net.arcs))


class TestJavascriptLoops(unittest.TestCase):
    def setUp(self):
        self.walker = JavascriptWalker()
        self.fixtures_dir = os.path.join(os.path.dirname(__file__), "test_code", "petri_js")

    def test_while_loop(self):
        tree = self.walker.parse_file(os.path.join(self.fixtures_dir, "while_loop.js"))
        node = self.walker.find_function(tree, "while_loop_func")
        net = self.walker.walk_function(node)
        assert_valid_petri_net(self, net)
        assert_bipartite(self, net)

        loop_trans = next(t for t in net.transitions if "while" in t.label)
        head_place = next(a.source for a in net.arcs if a.target == loop_trans)

        # Loop body terminal transition (count += 1) arcs back to head_place, creating a cycle
        t_body = next(t for t in net.transitions if "count += 1" in t.label)
        self.assertTrue(any(a.source == t_body and a.target == head_place for a in net.arcs))

        # Exit transition leads out of the loop
        exit_trans = next(t for t in net.transitions if t.label == "exit")
        self.assertTrue(any(a.source == head_place and a.target == exit_trans for a in net.arcs))

    def test_for_loop(self):
        tree = self.walker.parse_file(os.path.join(self.fixtures_dir, "for_loop.js"))
        node = self.walker.find_function(tree, "for_loop_func")
        net = self.walker.walk_function(node)
        assert_valid_petri_net(self, net)
        assert_bipartite(self, net)

        loop_trans = next(t for t in net.transitions if "for" in t.label)
        head_place = next(a.source for a in net.arcs if a.target == loop_trans)

        # Loop body terminal transition (sum += i) arcs back to head_place
        t_body = next(t for t in net.transitions if "sum += i" in t.label)
        self.assertTrue(any(a.source == t_body and a.target == head_place for a in net.arcs))

    def test_for_in_of_loops(self):
        tree = self.walker.parse_file(os.path.join(self.fixtures_dir, "for_in_of.js"))
        node = self.walker.find_function(tree, "for_in_of_func")
        net = self.walker.walk_function(node)
        assert_valid_petri_net(self, net)
        assert_bipartite(self, net)

        for_in_trans = next(t for t in net.transitions if "for" in t.label and "in" in t.label)
        for_of_trans = next(t for t in net.transitions if "for" in t.label and "of" in t.label)

        # Both loops have head places with back-arcs
        head_in = next(a.source for a in net.arcs if a.target == for_in_trans)
        head_of = next(a.source for a in net.arcs if a.target == for_of_trans)
        back_arcs_in = [a for a in net.arcs if a.target == head_in and "print" in getattr(a.source, "label", "")]
        back_arcs_of = [a for a in net.arcs if a.target == head_of and "print" in getattr(a.source, "label", "")]
        self.assertEqual(len(back_arcs_in), 1)
        self.assertEqual(len(back_arcs_of), 1)

    def test_loop_break_continue(self):
        tree = self.walker.parse_file(os.path.join(self.fixtures_dir, "loop_break_continue.js"))
        node = self.walker.find_function(tree, "loop_break_continue_func")
        net = self.walker.walk_function(node)
        assert_valid_petri_net(self, net)
        assert_bipartite(self, net)

        while_trans = next(t for t in net.transitions if "while" in t.label)
        head_place = next(a.source for a in net.arcs if a.target == while_trans)
        exit_trans = next(t for t in net.transitions if t.label == "exit")
        exit_place = next(a.target for a in net.arcs if a.source == exit_trans)

        t_continue = next(t for t in net.transitions if t.label == "continue")
        t_break = next(t for t in net.transitions if t.label == "break")

        # Continue arcs back to head_place
        self.assertTrue(any(a.source == t_continue and a.target == head_place for a in net.arcs))

        # Break arcs directly to exit_place
        self.assertTrue(any(a.source == t_break and a.target == exit_place for a in net.arcs))

    def test_break_outside_loop_raises_syntax_error(self):
        stmt = {"type": "BreakStatement", "loc": {"start": {"line": 1, "column": 0}}}
        func = {
            "type": "FunctionDeclaration",
            "id": {"type": "Identifier", "name": "bad"},
            "loc": {"start": {"line": 1, "column": 0}},
            "body": {"type": "BlockStatement", "body": [stmt]},
        }
        with self.assertRaises(SyntaxError):
            self.walker.walk_function(func)


class TestJavascriptTryCatch(unittest.TestCase):
    def setUp(self):
        self.walker = JavascriptWalker()
        self.fixtures_dir = os.path.join(os.path.dirname(__file__), "test_code", "petri_js")

    def test_try_catch(self):
        tree = self.walker.parse_file(os.path.join(self.fixtures_dir, "try_catch.js"))
        node = self.walker.find_function(tree, "try_catch_func")
        net = self.walker.walk_function(node)
        assert_valid_petri_net(self, net)
        assert_bipartite(self, net)

        risky_trans = next(t for t in net.transitions if "riskyOperation" in t.label)
        catch_trans = next(t for t in net.transitions if "catch" in t.label)
        except_entry = next(a.source for a in net.arcs if a.target == catch_trans)
        exc_arc = next(a for a in net.arcs if a.source == risky_trans and a.target == except_entry)
        self.assertIsNotNone(exc_arc)

        # Both try normal exit and catch handler exit converge on the same try_exit place
        t_catch_body = next(t for t in net.transitions if t.label == "val = -1")
        try_exit_from_normal = next(a.target for a in net.arcs if a.source == risky_trans and a.target != except_entry)
        try_exit_from_catch = next(a.target for a in net.arcs if a.source == t_catch_body)
        self.assertIs(try_exit_from_normal, try_exit_from_catch)

    def test_try_catch_finally(self):
        tree = self.walker.parse_file(os.path.join(self.fixtures_dir, "try_catch_finally.js"))
        node = self.walker.find_function(tree, "try_catch_finally_func")
        net = self.walker.walk_function(node)
        assert_valid_petri_net(self, net)
        assert_bipartite(self, net)

        risky_trans = next(t for t in net.transitions if "riskyOperation" in t.label)
        catch_body_trans = next(t for t in net.transitions if t.label == "val = -1")
        cleanup_trans = next(t for t in net.transitions if "cleanup" in t.label)
        finally_entry = next(a.source for a in net.arcs if a.target == cleanup_trans)

        # Both normal try flow and catch handler converge into finally_entry
        catch_parent = next(a.source for a in net.arcs if a.target == cleanup_trans)
        self.assertIs(finally_entry, catch_parent)
        self.assertTrue(any(a.source == risky_trans and a.target == finally_entry for a in net.arcs))
        self.assertTrue(any(a.source == catch_body_trans and a.target == finally_entry for a in net.arcs))

    def test_try_finally(self):
        tree = self.walker.parse_file(os.path.join(self.fixtures_dir, "try_finally.js"))
        node = self.walker.find_function(tree, "try_finally_func")
        net = self.walker.walk_function(node)
        assert_valid_petri_net(self, net)
        assert_bipartite(self, net)

        cleanup_trans = next(t for t in net.transitions if "cleanup" in t.label)
        finally_entry = next(a.source for a in net.arcs if a.target == cleanup_trans)
        exc_trans = next(t for t in net.transitions if t.label == "exception")

        # Unhandled exception flows into finally_entry
        self.assertTrue(any(a.source == exc_trans and a.target == finally_entry for a in net.arcs))


if __name__ == '__main__':
    unittest.main()

