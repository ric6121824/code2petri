import os
import sys
import tempfile
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

    def test_try_finally_return_routes_through_finally(self):
        code = (
            "function try_finally_return() {\n"
            "    try {\n"
            "        return 42;\n"
            "    } finally {\n"
            "        cleanup();\n"
            "    }\n"
            "}\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
            f.write(code)
            temp_path = f.name
        try:
            tree = self.walker.parse_file(temp_path)
            node = self.walker.find_function(tree, "try_finally_return")
            net = self.walker.walk_function(node)
            assert_valid_petri_net(self, net)
            assert_bipartite(self, net)

            ret_trans = next(t for t in net.transitions if "return" in t.label)
            cleanup_trans = next(t for t in net.transitions if "cleanup" in t.label)
            finally_entry = next(a.source for a in net.arcs if a.target == cleanup_trans)

            # return 42 inside try routes into finally_entry, NOT directly to end_place
            self.assertTrue(any(a.source == ret_trans and a.target == finally_entry for a in net.arcs))
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_try_finally_break_in_loop_routes_through_finally(self):
        code = (
            "function loop_try_finally_break() {\n"
            "    while (true) {\n"
            "        try {\n"
            "            break;\n"
            "        } finally {\n"
            "            cleanup();\n"
            "        }\n"
            "    }\n"
            "}\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
            f.write(code)
            temp_path = f.name
        try:
            tree = self.walker.parse_file(temp_path)
            node = self.walker.find_function(tree, "loop_try_finally_break")
            net = self.walker.walk_function(node)
            assert_valid_petri_net(self, net)
            assert_bipartite(self, net)

            break_trans = next(t for t in net.transitions if t.label == "break")
            cleanup_trans = next(t for t in net.transitions if "cleanup" in t.label)
            finally_entry = next(a.source for a in net.arcs if a.target == cleanup_trans)

            # break inside try in loop routes to finally_entry first
            self.assertTrue(any(a.source == break_trans and a.target == finally_entry for a in net.arcs))
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


class TestJavascriptSwitch(unittest.TestCase):
    def setUp(self):
        self.walker = JavascriptWalker()
        self.fixtures_dir = os.path.join(os.path.dirname(__file__), "test_code", "petri_js")

    def test_switch_with_default(self):
        tree = self.walker.parse_file(os.path.join(self.fixtures_dir, "switch_case.js"))
        node = self.walker.find_function(tree, "switch_func")
        net = self.walker.walk_function(node)
        assert_valid_petri_net(self, net)
        assert_bipartite(self, net)

        labels = [t.label for t in net.transitions]
        self.assertIn("case 1", labels)
        self.assertIn("case 2", labels)
        self.assertIn("default", labels)
        self.assertIn("result = 10", labels)
        self.assertIn("result = 20", labels)
        self.assertIn("result = -1", labels)

        # Decision place has 3 competing transitions
        t_c1 = next(t for t in net.transitions if t.label == "case 1")
        t_c2 = next(t for t in net.transitions if t.label == "case 2")
        t_def = next(t for t in net.transitions if t.label == "default")
        p_dec1 = next(a.source for a in net.arcs if a.target == t_c1)
        p_dec2 = next(a.source for a in net.arcs if a.target == t_c2)
        p_dec_def = next(a.source for a in net.arcs if a.target == t_def)
        self.assertIs(p_dec1, p_dec2)
        self.assertIs(p_dec2, p_dec_def)

        # Break transitions connect to switch_exit
        breaks = [t for t in net.transitions if t.label == "break"]
        self.assertEqual(len(breaks), 3)
        break_targets = [next(a.target for a in net.arcs if a.source == b) for b in breaks]
        self.assertEqual(len(set(break_targets)), 1)
        switch_exit = break_targets[0]

        # Switch exit leads to return result
        t_ret = next(t for t in net.transitions if t.label == "return result")
        self.assertTrue(any(a.source == switch_exit and a.target == t_ret for a in net.arcs))

    def test_switch_no_default(self):
        tree = self.walker.parse_file(os.path.join(self.fixtures_dir, "switch_case.js"))
        node = self.walker.find_function(tree, "switch_no_default")
        net = self.walker.walk_function(node)
        assert_valid_petri_net(self, net)
        assert_bipartite(self, net)

        # Has implicit default transition skipping directly to switch exit
        t_c1 = next(t for t in net.transitions if t.label == "case 1")
        t_def = next(t for t in net.transitions if t.label == "default")
        decision_place = next(a.source for a in net.arcs if a.target == t_c1)
        self.assertTrue(any(a.source == decision_place and a.target == t_def for a in net.arcs))

    def test_switch_fallthrough(self):
        code = (
            "function fallthrough_func(val) {\n"
            "    let x = 0;\n"
            "    switch (val) {\n"
            "        case 1:\n"
            "            x = 10;\n"
            "        case 2:\n"
            "            x = 20;\n"
            "            break;\n"
            "        default:\n"
            "            x = -1;\n"
            "    }\n"
            "    return x;\n"
            "}\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
            f.write(code)
            temp_path = f.name
        try:
            tree = self.walker.parse_file(temp_path)
            node = self.walker.find_function(tree, "fallthrough_func")
            net = self.walker.walk_function(node)
            assert_valid_petri_net(self, net)
            assert_bipartite(self, net)

            t_c1 = next(t for t in net.transitions if t.label == "case 1")
            t_x10 = next(t for t in net.transitions if "x = 10" in t.label)
            t_c2 = next(t for t in net.transitions if t.label == "case 2")
            t_x20 = next(t for t in net.transitions if "x = 20" in t.label)

            p_c1_entry = next(a.target for a in net.arcs if a.source == t_c1)
            p_c2_entry = next(a.target for a in net.arcs if a.source == t_c2)

            # case 1 leads to x = 10
            self.assertTrue(any(a.source == p_c1_entry and a.target == t_x10 for a in net.arcs))
            # x = 10 without break falls through to case 2's entry place
            self.assertTrue(any(a.source == t_x10 and a.target == p_c2_entry for a in net.arcs))
            # case 2 entry leads to x = 20
            self.assertTrue(any(a.source == p_c2_entry and a.target == t_x20 for a in net.arcs))
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


class TestJavascriptDoWhile(unittest.TestCase):
    def setUp(self):
        self.walker = JavascriptWalker()
        self.fixtures_dir = os.path.join(os.path.dirname(__file__), "test_code", "petri_js")

    def test_do_while_cycle(self):
        tree = self.walker.parse_file(os.path.join(self.fixtures_dir, "do_while.js"))
        node = self.walker.find_function(tree, "do_while_func")
        net = self.walker.walk_function(node)
        assert_valid_petri_net(self, net)
        assert_bipartite(self, net)

        # Body executes before condition check
        t_init = next(t for t in net.transitions if "let i = 0" in t.label)
        body_head = next(a.target for a in net.arcs if a.source == t_init)
        t_body = next(t for t in net.transitions if "i += 1" in t.label)
        self.assertTrue(any(a.source == body_head and a.target == t_body for a in net.arcs))

        # Body connects to condition check place
        check_place = next(a.target for a in net.arcs if a.source == t_body)
        cond_trans = next(t for t in net.transitions if "while" in t.label)
        exit_trans = next(t for t in net.transitions if t.label == "exit")

        # Condition check place branches to cond_trans (back-arc) and exit_trans
        self.assertTrue(any(a.source == check_place and a.target == cond_trans for a in net.arcs))
        self.assertTrue(any(a.source == check_place and a.target == exit_trans for a in net.arcs))
        self.assertTrue(any(a.source == cond_trans and a.target == body_head for a in net.arcs))

    def test_do_while_break_continue(self):
        tree = self.walker.parse_file(os.path.join(self.fixtures_dir, "do_while.js"))
        node = self.walker.find_function(tree, "do_while_break_continue")
        net = self.walker.walk_function(node)
        assert_valid_petri_net(self, net)
        assert_bipartite(self, net)

        t_continue = next(t for t in net.transitions if t.label == "continue")
        t_break = next(t for t in net.transitions if t.label == "break")
        cond_trans = next(t for t in net.transitions if "while" in t.label)
        check_place = next(a.source for a in net.arcs if a.target == cond_trans)
        exit_trans = next(t for t in net.transitions if t.label == "exit")
        loop_exit = next(a.target for a in net.arcs if a.source == exit_trans)

        # In do...while, continue jumps to check_place, and break jumps to loop_exit
        self.assertTrue(any(a.source == t_continue and a.target == check_place for a in net.arcs))
        self.assertTrue(any(a.source == t_break and a.target == loop_exit for a in net.arcs))


class TestJavascriptThrow(unittest.TestCase):
    def setUp(self):
        self.walker = JavascriptWalker()
        self.fixtures_dir = os.path.join(os.path.dirname(__file__), "test_code", "petri_js")

    def test_unhandled_throw(self):
        tree = self.walker.parse_file(os.path.join(self.fixtures_dir, "throw_exception.js"))
        node = self.walker.find_function(tree, "throw_func")
        net = self.walker.walk_function(node)
        assert_valid_petri_net(self, net)
        assert_bipartite(self, net)

        throw_trans = next(t for t in net.transitions if "throw" in t.label)
        _, end_place = assert_has_start_and_end(self, net)

        # Unhandled throw terminates function directly at end_place
        self.assertTrue(any(a.source == throw_trans and a.target == end_place for a in net.arcs))

    def test_throw_in_try(self):
        tree = self.walker.parse_file(os.path.join(self.fixtures_dir, "throw_exception.js"))
        node = self.walker.find_function(tree, "throw_in_try")
        net = self.walker.walk_function(node)
        assert_valid_petri_net(self, net)
        assert_bipartite(self, net)

        throw_trans = next(t for t in net.transitions if "throw" in t.label)
        catch_trans = next(t for t in net.transitions if "catch" in t.label)
        except_entry = next(a.source for a in net.arcs if a.target == catch_trans)

        # Throw inside try arcs to except_entry
        self.assertTrue(any(a.source == throw_trans and a.target == except_entry for a in net.arcs))


class TestJavascriptClassMethods(unittest.TestCase):
    def setUp(self):
        self.walker = JavascriptWalker()
        self.fixture_path = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "game_of_life",
            "webgl-engine.js",
        )

    def test_find_all_functions_includes_class_methods(self):
        tree = self.walker.parse_file(self.fixture_path)
        funcs = self.walker.find_all_functions(tree)
        expected = [
            "WebGLEngine.constructor",
            "WebGLEngine.initShaders",
            "WebGLEngine.createProgram",
            "WebGLEngine.createTexture",
            "WebGLEngine.initBuffers",
            "WebGLEngine.randomize",
            "WebGLEngine.step",
            "WebGLEngine.drawToScreen",
        ]
        for exp in expected:
            self.assertIn(exp, funcs)

    def test_find_function_qualified_and_bare(self):
        tree = self.walker.parse_file(self.fixture_path)
        node_qual = self.walker.find_function(tree, "WebGLEngine.step")
        self.assertIsNotNone(node_qual)

        node_bare = self.walker.find_function(tree, "step")
        self.assertIsNotNone(node_bare)
        self.assertIs(node_qual, node_bare)

    def test_walk_class_method(self):
        tree = self.walker.parse_file(self.fixture_path)
        node = self.walker.find_function(tree, "WebGLEngine.step")
        net = self.walker.walk_function(node)
        assert_valid_petri_net(self, net)
        assert_bipartite(self, net)

    def test_nested_scoped_class_method_qualification(self):
        code = (
            "function outerFactory() {\n"
            "    class InnerService {\n"
            "        performAction() {\n"
            "            return 42;\n"
            "        }\n"
            "    }\n"
            "}\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
            f.write(code)
            temp_path = f.name
        try:
            tree = self.walker.parse_file(temp_path)
            funcs = self.walker.find_all_functions(tree)
            self.assertIn("outerFactory.InnerService.performAction", funcs)
            node = self.walker.find_function(tree, "outerFactory.InnerService.performAction")
            self.assertIsNotNone(node)
            net = self.walker.walk_function(node)
            assert_valid_petri_net(self, net)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)



class TestJavascriptAnonymousCallbacks(unittest.TestCase):
    def setUp(self):
        self.walker = JavascriptWalker()
        self.fixture_path = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "game_of_life",
            "app.js",
        )

    def test_find_all_functions_discovers_callbacks(self):
        tree = self.walker.parse_file(self.fixture_path)
        funcs = self.walker.find_all_functions(tree)
        self.assertTrue(any("anonymous@151" in f for f in funcs))
        self.assertTrue(any("anonymous@160" in f for f in funcs))
        self.assertTrue(any("anonymous@165" in f for f in funcs))

    def test_find_function_anonymous_targetable(self):
        tree = self.walker.parse_file(self.fixture_path)
        node1 = self.walker.find_function(tree, "(anonymous@151)")
        self.assertIsNotNone(node1)

        node2 = self.walker.find_function(tree, "setupEventListeners.(anonymous@151)")
        self.assertIsNotNone(node2)
        self.assertIs(node1, node2)

    def test_walk_anonymous_callback(self):
        tree = self.walker.parse_file(self.fixture_path)
        node = self.walker.find_function(tree, "(anonymous@151)")
        net = self.walker.walk_function(node)
        assert_valid_petri_net(self, net)
        assert_bipartite(self, net)

        labels = [t.label for t in net.transitions]
        self.assertIn("call: stopSimulation()", labels)
        self.assertIn("if (mode === 'gpu')", labels)


class TestJavascriptGameLoopRAF(unittest.TestCase):
    def setUp(self):
        self.walker = JavascriptWalker()
        self.fixture_path = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "game_of_life",
            "app.js",
        )

    def test_loop_raf_cycle(self):
        tree = self.walker.parse_file(self.fixture_path)
        node = self.walker.find_function(tree, "loop")
        net = self.walker.walk_function(node)
        assert_valid_petri_net(self, net)
        assert_bipartite(self, net)

        start_place, _ = assert_has_start_and_end(self, net)
        raf_trans = next(t for t in net.transitions if "requestAnimationFrame" in t.label)

        # requestAnimationFrame(loop) produces a back-arc cycle to start_place
        self.assertTrue(
            any(a.source == raf_trans and a.target == start_place for a in net.arcs),
            "Expected requestAnimationFrame(loop) to have a back-arc cycle to start_place",
        )

    def test_loop_raf_with_trailing_statements(self):
        code = (
            "function gameLoop() {\n"
            "    requestAnimationFrame(gameLoop);\n"
            "    cleanupFrame();\n"
            "}\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
            f.write(code)
            temp_path = f.name
        try:
            tree = self.walker.parse_file(temp_path)
            node = self.walker.find_function(tree, "gameLoop")
            net = self.walker.walk_function(node)
            assert_valid_petri_net(self, net)
            assert_bipartite(self, net)

            start_place, end_place = assert_has_start_and_end(self, net)
            raf_trans = next(t for t in net.transitions if "requestAnimationFrame" in t.label)
            cleanup_trans = next(t for t in net.transitions if "cleanupFrame" in t.label)

            # RAF has a back-arc cycle to start_place
            self.assertTrue(any(a.source == raf_trans and a.target == start_place for a in net.arcs))

            # Forward flow continues from RAF to cleanupFrame and then to end_place
            cleanup_inflow_places = [a.source for a in net.arcs if a.target == cleanup_trans]
            self.assertTrue(any(a.source == raf_trans and a.target in cleanup_inflow_places for a in net.arcs))
            self.assertTrue(any(a.source == cleanup_trans and a.target == end_place for a in net.arcs))
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_loop_raf_return_statement(self):
        code = (
            "function gameLoop() {\n"
            "    return requestAnimationFrame(gameLoop);\n"
            "}\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
            f.write(code)
            temp_path = f.name
        try:
            tree = self.walker.parse_file(temp_path)
            node = self.walker.find_function(tree, "gameLoop")
            net = self.walker.walk_function(node)
            assert_valid_petri_net(self, net)
            assert_bipartite(self, net)

            start_place, end_place = assert_has_start_and_end(self, net)
            raf_trans = next(t for t in net.transitions if "requestAnimationFrame" in t.label)

            # RAF has a back-arc cycle to start_place
            self.assertTrue(any(a.source == raf_trans and a.target == start_place for a in net.arcs))

            # Since it is a return statement, it also arcs directly to end_place
            self.assertTrue(any(a.source == raf_trans and a.target == end_place for a in net.arcs))
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_loop_raf_class_method_this_step(self):
        code = (
            "class Engine {\n"
            "    step() {\n"
            "        requestAnimationFrame(this.step);\n"
            "    }\n"
            "}\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
            f.write(code)
            temp_path = f.name
        try:
            tree = self.walker.parse_file(temp_path)
            node = self.walker.find_function(tree, "Engine.step")
            net = self.walker.walk_function(node)
            assert_valid_petri_net(self, net)
            assert_bipartite(self, net)

            start_place, end_place = assert_has_start_and_end(self, net)
            raf_trans = next(t for t in net.transitions if "requestAnimationFrame" in t.label)

            # RAF calling this.step inside Engine.step produces a back-arc cycle to start_place
            self.assertTrue(any(a.source == raf_trans and a.target == start_place for a in net.arcs))
            self.assertTrue(any(a.source == raf_trans and a.target == end_place for a in net.arcs))
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)



class TestGameOfLifeSimulatorIntegration(unittest.TestCase):
    def setUp(self):
        self.app_js = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "game_of_life",
            "app.js",
        )
        self.webgl_js = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "game_of_life",
            "webgl-engine.js",
        )

    def test_engine_app_global(self):
        net = code2petri(self.app_js, output_file=None, target_function="(global)")
        self.assertIsNotNone(net)
        assert_valid_petri_net(self, net)
        labels = [t.label for t in net.transitions]
        self.assertIn("call: init()", labels)

    def test_engine_app_step_cpu(self):
        net = code2petri(self.app_js, output_file=None, target_function="stepCpu")
        self.assertIsNotNone(net)
        assert_valid_petri_net(self, net)

        # Assert nested loop cycles for i and j
        loop_transitions = [t for t in net.transitions if "for" in t.label]
        self.assertGreaterEqual(len(loop_transitions), 2)
        for lt in loop_transitions:
            head = next(a.source for a in net.arcs if a.target == lt)
            # Cycle back-arc exists targeting loop head
            back_arcs = [a for a in net.arcs if a.target == head and a.source != head]
            self.assertGreaterEqual(len(back_arcs), 1)

        # XOR-splits in stepCpu for cellular automaton rules:
        # false branch of if (state === 0) leads to the decision place for if (state === 1)
        t_state0 = next(t for t in net.transitions if "state === 0" in t.label)
        t_state1 = next(t for t in net.transitions if "state === 1" in t.label)
        p_dec = next(a.source for a in net.arcs if a.target == t_state0)
        t_else = next(t for t in net.transitions if t.label == "else" and any(a.source == p_dec and a.target == t for a in net.arcs))
        p_else = next(a.target for a in net.arcs if a.source == t_else)
        p_dec1 = next(a.source for a in net.arcs if a.target == t_state1)
        self.assertIs(p_else, p_dec1)

        # Both branches converge on the inner loop body merge
        t_assign0 = next(t for t in net.transitions if "nextGrid[i][j] = 1" in t.label)
        p_merge0 = next(a.target for a in net.arcs if a.source == t_assign0)
        t_assign_else = next(t for t in net.transitions if "nextGrid[i][j] = state" in t.label)
        p_merge_else = next(a.target for a in net.arcs if a.source == t_assign_else)
        self.assertIs(p_merge0, p_merge_else)

    def test_engine_app_loop(self):
        net = code2petri(self.app_js, output_file=None, target_function="loop")
        self.assertIsNotNone(net)
        assert_valid_petri_net(self, net)
        start_place, end_place = assert_has_start_and_end(self, net)
        raf_trans = next(t for t in net.transitions if "requestAnimationFrame" in t.label)
        self.assertTrue(any(a.source == raf_trans and a.target == start_place for a in net.arcs))

        # Early return when !isRunning reaches end_place
        ret_trans = next(t for t in net.transitions if t.label == "return")
        self.assertTrue(any(a.source == ret_trans and a.target == end_place for a in net.arcs))

    def test_engine_webgl_engine_step(self):
        net = code2petri(self.webgl_js, output_file=None, target_function="WebGLEngine.step")
        self.assertIsNotNone(net)
        start_place, end_place = assert_valid_petri_net(self, net)

        labels = [t.label for t in net.transitions]
        self.assertIn("call: this.drawToScreen()", labels)
        self.assertTrue(any("tempTex" in l for l in labels))

        # Sequential flow reaches drawToScreen and ends cleanly
        t_draw = next(t for t in net.transitions if "call: this.drawToScreen()" in t.label)
        self.assertTrue(any(a.source == t_draw and a.target == end_place for a in net.arcs))

    def test_engine_webgl_engine_init_shaders(self):
        net = code2petri(self.webgl_js, output_file=None, target_function="WebGLEngine.initShaders")
        self.assertIsNotNone(net)
        assert_valid_petri_net(self, net)

        labels = [t.label for t in net.transitions]
        self.assertTrue(any("call: this.createProgram()" in l for l in labels))

    def test_engine_app_setup_event_listeners(self):
        net = code2petri(self.app_js, output_file=None, target_function="setupEventListeners")
        self.assertIsNotNone(net)
        assert_valid_petri_net(self, net)

        # Contains loop over modeRadios
        labels = [t.label for t in net.transitions]
        self.assertTrue(any("modeRadios.forEach" in l or "addEventListener" in l for l in labels))


if __name__ == '__main__':
    unittest.main()

