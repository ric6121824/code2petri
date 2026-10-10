import unittest
import sys
import os
import ast
import xml.etree.ElementTree as ET

# Ensure repo root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from code2petri.python_walker import PythonWalker  # noqa: E402
from code2petri.walker_protocol import WalkResult, CallSite  # noqa: E402
from code2petri.model import PetriNet, Place, Transition, Arc  # noqa: E402
from tests.petri_assertions import (  # noqa: E402
    assert_has_start_and_end,
    assert_bipartite,
    assert_valid_petri_net,
    walk_net,
)

walker = PythonWalker()
parse_file = walker.parse_file
find_function = walker.find_function
find_all_functions = walker.find_all_functions


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

    def test_walk_function_returns_walk_result(self):
        walk_res = walker.walk_function(self.func_node, "sequential_func")
        self.assertIsInstance(walk_res, WalkResult)
        self.assertIsInstance(walk_res.net, PetriNet)
        self.assertIsInstance(walk_res.call_sites, list)
        self.assertEqual(len(walk_res.call_sites), 1)
        self.assertEqual(walk_res.call_sites[0].callee_name, "print")
        assert_valid_petri_net(self, walk_res.net)

    def test_sequential_counts(self):
        walk_res = walker.walk_function(self.func_node)
        self.assertIsInstance(walk_res, WalkResult)
        self.assertEqual(len(walk_res.call_sites), 1)
        self.assertEqual(walk_res.call_sites[0].callee_name, "print")
        net = walk_res.net
        self.assertIsInstance(net, PetriNet)
        # 5 sequential statements + 1 return: 6 transitions, 7 places, 12 arcs
        self.assertEqual(len(net.transitions), 6)
        self.assertEqual(len(net.places), 7)
        self.assertEqual(len(net.arcs), 12)

    def test_walk_result_exposes_function_owned_python_return_evidence(self):
        """Python declarations and direct literals survive walking as separate evidence."""
        node = ast.parse(
            "def choose(flag) -> 'Result[Thing]':\n"
            "    if flag:\n"
            "        return True\n"
            "    return 1\n"
        ).body[0]
        result = walker.walk_function(node, "choose", "/src/sample.py")

        self.assertEqual(result.return_metadata["function_name"], "choose")
        self.assertEqual(result.return_metadata["source_file"], "/src/sample.py")
        self.assertEqual(result.return_metadata["declared"]["expression"], "'Result[Thing]'")
        self.assertEqual(result.return_metadata["analysis_status"], "complete")
        self.assertEqual(result.return_metadata["inferred_types"], ["bool", "int"])

    def test_direct_literal_return_has_type_and_return_site(self):
        """A simple direct literal is inferred at its return statement."""
        node = ast.parse("def answer():\n    return True\n").body[0]
        result = walker.walk_function(node, "answer", "/src/sample.py")

        self.assertEqual(result.return_metadata["analysis_status"], "complete")
        evidence = result.return_metadata["inferred"][0]
        self.assertEqual(evidence["expression"], "True")
        self.assertEqual(evidence["type"], "bool")
        self.assertEqual(evidence["role"], "call_result")
        self.assertEqual(evidence["source_location"]["line"], 2)
        self.assertEqual(result.net.to_dict()["return_metadata"], result.return_metadata)
        self.assertEqual(result.net.clone().to_dict()["return_metadata"], result.return_metadata)

    def test_returned_local_includes_assignment_evidence(self):
        node = ast.parse("def answer():\n    x = 1\n    return x\n").body[0]
        metadata = walker.walk_function(node, "answer", "/src/sample.py").return_metadata

        self.assertEqual(metadata["analysis_status"], "complete")
        evidence = metadata["inferred"][0]
        self.assertEqual(evidence["expression"], "x")
        self.assertEqual(evidence["type"], "int")
        self.assertEqual(evidence["source_location"], {"line": 3, "column": 4})
        self.assertEqual(evidence["expression_location"], {"line": 3, "column": 11})
        self.assertEqual(evidence["evidence"][0]["expression"], "x = 1")
        self.assertEqual(evidence["evidence"][0]["source_location"], {"line": 2, "column": 4})

    def test_returned_expression_infers_primitive_container_and_supported_operator(self):
        cases = [
            ("x = []; return x", "list"),
            ("x = [make()]; return x", "list"),
            ("x = [make()]; return x", "list"),
            ("x = {}; return x", "dict"),
            ("x = (); return x", "tuple"),
            ("x = {1}; return x", "set"),
            ("x = f'item:{1}'; return x", "str"),
            ("x = 1; return x + 2", "int"),
            ("x = 1; return -x / 2", "float"),
            ("x = True; return not x", "bool"),
            ("x = 'a'; return x + 'b'", "str"),
            ("x = 1; return x + 'b'", "unknown"),
            ("x = [1]; y = x; return y", "list"),
            ("x, y = (1, 2); return x", "unknown"),
            ("return values[0]", "unknown"),
            ("return value", "unknown"),
            ("return values[0]", "unknown"),
            ("return value", "unknown"),
        ]
        for body, expected_type in cases:
            with self.subTest(body=body):
                node = ast.parse("def answer():\n    " + body.replace("; ", "\n    ") + "\n").body[0]
                metadata = walker.walk_function(node, "answer", "/src/sample.py").return_metadata
                self.assertEqual(metadata["inferred"][0]["type"], expected_type)

    def test_local_reassignment_invalidates_stale_type_and_control_flow_stays_unknown(self):
        cases = [
            ("def answer():\n    x = 1\n    x = make_value()\n    return x\n", "unknown"),
            ("def answer():\n    x = 1\n    x = 'text'\n    return x\n", "str"),
            ("def answer(flag):\n    if flag:\n        x = 1\n    else:\n        x = 2\n    return x\n", None),
        ]
        for source, expected_type in cases:
            with self.subTest(source=source):
                node = ast.parse(source).body[0]
                metadata = walker.walk_function(node, "answer", "/src/sample.py").return_metadata
                if expected_type is None:
                    self.assertEqual(metadata["analysis_status"], "unknown")
                    self.assertEqual(metadata["inferred"][0]["type"], "unknown")
                else:
                    self.assertEqual(metadata["inferred"][0]["type"], expected_type)

    def test_python_global_scope_is_not_applicable(self):
        """A synthetic global wrapper does not gain artificial return metadata."""
        node = walker.find_function(ast.parse("print('hello')"), "(global)")
        result = walker.walk_function(node, "(global)", "/src/sample.py")

        self.assertEqual(result.return_metadata["analysis_status"], "not_applicable")
        self.assertEqual(result.return_metadata["function_name"], "Global Scope")

    def test_direct_literal_types_distinguish_bool_int_and_supported_primitives(self):
        """Literal type evidence preserves Python's bool/int distinction and supported values."""
        cases = [
            ("True", "bool"), ("1", "int"), ("1.5", "float"), ("1j", "complex"),
            ("'text'", "str"), ("b'bytes'", "bytes"), ("None", "NoneType"),
        ]
        for expression, expected_type in cases:
            with self.subTest(expression=expression):
                node = ast.parse(f"def value():\n    return {expression}\n").body[0]
                metadata = walker.walk_function(node, "value", "/src/literals.py").return_metadata
                self.assertEqual(metadata["analysis_status"], "complete")
                self.assertEqual(metadata["inferred"][0]["type"], expected_type)

    def test_nested_returns_and_async_or_generator_values_do_not_become_call_results(self):
        """Nested scopes and deferred async/generator roles are not treated as ordinary results."""
        cases = [
            ("def outer():\n    def inner():\n        return 4\n", "outer"),
            ("async def fetch() -> int:\n    return 4\n", "fetch"),
            ("def values() -> int:\n    yield 4\n", "values"),
        ]
        for source, name in cases:
            with self.subTest(name=name):
                node = ast.parse(source).body[0]
                metadata = walker.walk_function(node, name, "/src/scopes.py").return_metadata
                if name == "outer":
                    self.assertEqual(metadata["analysis_status"], "complete")
                    self.assertEqual(metadata["inferred_types"], ["NoneType"])
                    self.assertEqual(metadata["inferred"][0]["provenance"], "normal_fallthrough")
                else:
                    self.assertEqual(metadata["analysis_status"], "unknown")
                    self.assertEqual(metadata["inferred"], [])

    def test_generator_roles_separate_object_yields_completion_and_annotation(self):
        node = ast.parse(
            "from typing import Generator\n"
            "def values() -> Generator[int, None, str]:\n"
            "    yield 1\n"
            "    yield 'two'\n"
            "    return 'done'\n"
        ).body[1]
        metadata = walker.walk_function(node, "values", "/src/generator.py").return_metadata

        self.assertEqual(metadata["function_kind"], "generator")
        self.assertEqual(metadata["declared"]["expression"], "Generator[int, None, str]")
        self.assertEqual(metadata["roles"]["immediate"]["inferred_types"], ["generator"])
        self.assertEqual(metadata["roles"]["yielded"]["analysis_status"], "complete")
        self.assertEqual(metadata["roles"]["yielded"]["inferred_types"], ["int", "str"])
        self.assertEqual(metadata["roles"]["yielded"]["declared"]["expression"], "int")
        self.assertEqual(metadata["roles"]["completion"]["inferred_types"], ["str"])
        self.assertEqual(metadata["roles"]["completion"]["declared"]["expression"], "str")
        self.assertEqual(metadata["roles"]["yielded"]["inferred"][0]["role"], "yielded_item")

    def test_async_function_roles_remain_distinct_from_generator_roles(self):
        node = ast.parse("async def fetch() -> int:\n    return 1\n").body[0]
        metadata = walker.walk_function(node, "fetch", "/src/async.py").return_metadata

        self.assertEqual(metadata["function_kind"], "async_function")
        self.assertIsNone(metadata["declared"])
        self.assertEqual(metadata["roles"]["immediate"]["inferred_types"], ["coroutine"])
        self.assertEqual(metadata["roles"]["awaited"]["declared"]["expression"], "int")
        self.assertEqual(metadata["roles"]["awaited"]["inferred_types"], ["int"])

    def test_async_generator_roles_have_unknown_yields_and_inapplicable_completion(self):
        node = ast.parse(
            "async def values():\n"
            "    yield make_value()\n"
            "    async def nested():\n"
            "        yield 1\n"
            "        return 2\n"
            "    return\n"
        ).body[0]
        metadata = walker.walk_function(node, "values", "/src/generator.py").return_metadata

        self.assertEqual(metadata["function_kind"], "async_generator")
        self.assertEqual(metadata["roles"]["immediate"]["inferred_types"], ["async_generator"])
        self.assertEqual(metadata["roles"]["yielded"]["analysis_status"], "unknown")
        self.assertEqual(metadata["roles"]["yielded"]["observed_types"], [])
        self.assertEqual(metadata["roles"]["yielded"]["inferred"][0]["type"], "unknown")
        self.assertEqual(metadata["roles"]["completion"]["analysis_status"], "not_applicable")

    def test_generator_nested_yields_are_excluded_and_delegation_is_unknown(self):
        node = ast.parse(
            "def values():\n"
            "    yield 1\n"
            "    def nested():\n"
            "        yield 'wrong scope'\n"
            "    yield from source\n"
            "    return\n"
        ).body[0]
        metadata = walker.walk_function(node, "values", "/src/generator.py").return_metadata

        self.assertEqual(metadata["roles"]["yielded"]["analysis_status"], "unknown")
        self.assertEqual(metadata["roles"]["yielded"]["observed_types"], ["int"])
        self.assertEqual([item["type"] for item in metadata["roles"]["yielded"]["inferred"]], ["int", "unknown"])
        self.assertEqual(metadata["roles"]["completion"]["inferred_types"], ["NoneType"])

    def test_generator_yield_binding_after_branch_or_loop_does_not_reuse_stale_type(self):
        for mutation in (
            "if flag:\n        value = 'branch'",
            "for item in items:\n        value = 'loop'",
        ):
            source = "def values(flag, items):\n    value = 1\n    " + mutation + "\n    yield value\n"
            with self.subTest(mutation=mutation):
                metadata = walker.walk_function(ast.parse(source).body[0], "values", "/src/generator.py").return_metadata
                yielded = metadata["roles"]["yielded"]
                self.assertEqual(yielded["analysis_status"], "unknown")
                self.assertEqual(yielded["observed_types"], [])

    def test_generator_raise_only_completion_does_not_hide_generator_object(self):
        source = "def values():\n    yield 1\n    raise RuntimeError()\n"
        metadata = walker.walk_function(ast.parse(source).body[0], "values", "/src/generator.py").return_metadata
        self.assertEqual(metadata["roles"]["immediate"]["analysis_status"], "complete")
        self.assertEqual(metadata["roles"]["completion"]["analysis_status"], "no_normal_return")

    def test_supported_return_paths_report_complete_unions_and_partial_observations(self):
        cases = [
            ("def answer(flag):\n    if flag:\n        return 1\n    else:\n        return 'x'\n", "complete", ["int", "str"], []),
            ("def answer(flag):\n    if flag:\n        return 1\n    else:\n        return missing()\n", "unknown", [], ["int"]),
            ("def answer(flag):\n    if flag:\n        return 1\n", "complete", ["int", "NoneType"], []),
        ]
        for source, status, inferred_types, observed_types in cases:
            with self.subTest(source=source):
                metadata = walker.walk_function(ast.parse(source).body[0], "answer", "/src/paths.py").return_metadata
                self.assertEqual(metadata["analysis_status"], status)
                self.assertEqual(metadata.get("inferred_types", []), inferred_types)
                self.assertEqual(metadata.get("observed_types", []), observed_types)
                if status == "unknown":
                    self.assertEqual([item["type"] for item in metadata["observed"]], ["int"])

    def test_supported_completion_distinguishes_bare_returns_abnormal_only_and_unreachable(self):
        cases = [
            ("def answer(flag):\n    if flag:\n        return\n    return 1\n", "complete", ["NoneType", "int"], 2),
            ("def answer(flag):\n    if flag:\n        raise ValueError()\n    else:\n        raise RuntimeError()\n", "no_normal_return", [], 0),
            ("def answer():\n    return 1\n    return 'unreachable'\n", "complete", ["int"], 1),
            ("def answer(flag):\n    if flag:\n        x = 1\n    else:\n        x = 'x'\n    return x\n", "unknown", [], 1),
        ]
        for source, status, inferred_types, evidence_count in cases:
            with self.subTest(source=source):
                metadata = walker.walk_function(ast.parse(source).body[0], "answer", "/src/paths.py").return_metadata
                self.assertEqual(metadata["analysis_status"], status)
                self.assertEqual(metadata.get("inferred_types", []), inferred_types)
                self.assertEqual(len(metadata["inferred"]), evidence_count)

    def test_unsupported_control_flow_keeps_known_returns_as_partial_evidence(self):
        for source in (
            "def answer(flag):\n    if flag:\n        return 1\n    while other():\n        pass\n",
            "def answer():\n    try:\n        return 1\n    finally:\n        cleanup()\n",
        ):
            with self.subTest(source=source):
                metadata = walker.walk_function(ast.parse(source).body[0], "answer", "/src/paths.py").return_metadata
                self.assertEqual(metadata["analysis_status"], "unknown")
                self.assertEqual([item["type"] for item in metadata["observed"]], ["int"])

    def test_collect_variable_bindings_baseline(self):
        bindings = walker.collect_variable_bindings(self.tree)
        self.assertEqual(bindings, {})

    def test_start_and_end_places(self):
        net = walk_net(walker, self.func_node)
        start_place, end_place = assert_has_start_and_end(self, net)
        assert_bipartite(self, net)

        # The start place has an outgoing arc to the first transition
        outgoing_start = [a for a in net.arcs if a.source == start_place]
        self.assertEqual(outgoing_start[0].target, net.transitions[0])

        # End place is the target of the last transition (return statement)
        incoming_end = [a for a in net.arcs if a.target == end_place]
        self.assertEqual(incoming_end[0].source, net.transitions[-1])


    def test_linear_connectivity(self):
        net = walk_net(walker, self.func_node)
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
        net = walk_net(walker, self.func_node)
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
        net = walk_net(walker, func_node)
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
        net = walk_net(walker, self.func_node)
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
        net = walk_net(walker, self.func_node)
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
            walk_net(walker, invalid_node)  # type: ignore

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
        net = walk_net(walker, func_node)
        self.assertEqual(len(net.places), 3)  # p0, p1, p_end
        self.assertEqual(len(net.transitions), 2)  # await, return

    def test_find_all_functions(self):
        code = (
            "def alpha(): pass\n"
            "def beta(): pass\n"
            "async def gamma(): pass\n"
        )
        tree = ast.parse(code)
        func_names = find_all_functions(tree)
        self.assertEqual(func_names, ["alpha", "beta", "gamma"])

    def test_global_scope_discovery(self):
        code = (
            "x = 1\n"
            "y = 2\n"
            "def helper(): pass\n"
        )
        tree = ast.parse(code)
        func_names = find_all_functions(tree)
        self.assertEqual(func_names, ["(global)", "helper"])

    def test_find_function_global_synthetic_wrapper(self):
        code = (
            "a = 10\n"
            "b = 20\n"
            "print(a + b)\n"
        )
        tree = ast.parse(code)
        global_node = find_function(tree, "(global)")
        self.assertIsNotNone(global_node)
        self.assertIsInstance(global_node, ast.FunctionDef)
        self.assertEqual(global_node.name, "(global)")
        self.assertEqual(len(global_node.body), 3)

        net = walk_net(walker, global_node)
        assert_valid_petri_net(self, net)
        assert_bipartite(self, net)
        start_p, end_p = assert_has_start_and_end(self, net)
        self.assertIsNotNone(start_p)
        self.assertIsNotNone(end_p)

    def test_find_function_global_none_when_no_executable_statements(self):
        code = (
            "def func_a(): pass\n"
            "class ClassB: pass\n"
        )
        tree = ast.parse(code)
        self.assertIsNone(find_function(tree, "(global)"))

    def test_raise_statement_unhandled(self):
        code = (
            "def func_with_raise():\n"
            "    x = 1\n"
            "    raise ValueError('error')\n"
            "    y = 2\n"
        )
        tree = ast.parse(code)
        func_node = find_function(tree, "func_with_raise")
        net = walk_net(walker, func_node)
        assert_valid_petri_net(self, net)
        start_p, end_p = assert_has_start_and_end(self, net)

        raise_trans = next(t for t in net.transitions if "raise" in t.label)
        self.assertIsNotNone(raise_trans)
        # Unhandled raise arcs to end_place
        self.assertTrue(any(a.source == raise_trans and a.target == end_p for a in net.arcs))
        # Dead statement after raise is not present in net
        self.assertFalse(any("y = 2" in t.label for t in net.transitions))

    def test_raise_statement_in_try(self):
        code = (
            "def func_with_try_raise():\n"
            "    try:\n"
            "        raise RuntimeError('fail')\n"
            "    except RuntimeError:\n"
            "        pass\n"
        )
        tree = ast.parse(code)
        func_node = find_function(tree, "func_with_try_raise")
        net = walk_net(walker, func_node)
        assert_valid_petri_net(self, net)

        raise_trans = next(t for t in net.transitions if "raise" in t.label)
        except_place = next(p for p in net.places if p.label == "except_entry")
        self.assertTrue(any(a.source == raise_trans and a.target == except_place for a in net.arcs))


class TestPythonWalkerVariableBindings(unittest.TestCase):
    def setUp(self):
        self.walker = PythonWalker()

    def test_top_level_variable_bindings(self):
        code = (
            "x = Foo()\n"
            "self.engine = WebGLEngine(width=100)\n"
            "normal_var = 42\n"
            "func_call = get_data()\n"
        )
        tree = ast.parse(code)
        bindings = self.walker.collect_variable_bindings(tree)
        self.assertEqual(bindings, {"x": "Foo", "self.engine": "WebGLEngine"})

    def test_chained_and_annotated_assignments(self):
        code = (
            "a = b = Bar()\n"
            "typed_var: Service = Service('config')\n"
        )
        tree = ast.parse(code)
        bindings = self.walker.collect_variable_bindings(tree)
        self.assertEqual(bindings, {"a": "Bar", "b": "Bar", "typed_var": "Service"})

    def test_bindings_inside_classes_and_functions(self):
        code = (
            "class App:\n"
            "    def __init__(self):\n"
            "        self.model = Model()\n"
            "        temp = Controller(self.model)\n"
            "def worker():\n"
            "    runner = TaskRunner()\n"
        )
        tree = ast.parse(code)
        bindings = self.walker.collect_variable_bindings(tree)
        self.assertEqual(bindings, {
            "self.model": "Model",
            "temp": "Controller",
            "runner": "TaskRunner",
        })

    def test_module_qualified_constructor(self):
        code = "client = pkg.submodule.ApiClient()"
        tree = ast.parse(code)
        bindings = self.walker.collect_variable_bindings(tree)
        self.assertEqual(bindings, {"client": "ApiClient"})


class TestPythonWalkerCallSiteExtraction(unittest.TestCase):
    def setUp(self):
        self.walker = PythonWalker()

    def test_bare_function_call_site(self):
        code = (
            "def worker():\n"
            "    data = fetch_records()\n"
            "    process(data)\n"
        )
        tree = ast.parse(code)
        func_node = self.walker.find_function(tree, "worker")
        res = self.walker.walk_function(func_node, "worker", filepath="app.py")
        self.assertIsInstance(res, WalkResult)
        self.assertEqual(len(res.call_sites), 2)

        cs0 = res.call_sites[0]
        self.assertEqual(cs0.caller_function, "worker")
        self.assertEqual(cs0.caller_file, "app.py")
        self.assertEqual(cs0.callee_name, "fetch_records")
        self.assertIsNone(cs0.callee_owner)
        self.assertEqual(cs0.line_number, 2)
        # Verify transition_id points to an actual transition in the net
        t0 = next((t for t in res.net.transitions if t.id == cs0.transition_id), None)
        self.assertIsNotNone(t0)
        self.assertIn("fetch_records", t0.label)

        cs1 = res.call_sites[1]
        self.assertEqual(cs1.callee_name, "process")
        self.assertIsNone(cs1.callee_owner)
        self.assertEqual(cs1.line_number, 3)
        t1 = next((t for t in res.net.transitions if t.id == cs1.transition_id), None)
        self.assertIsNotNone(t1)
        self.assertIn("process", t1.label)

    def test_method_and_attribute_call_site(self):
        code = (
            "def update():\n"
            "    engine.step()\n"
            "    self.renderer.draw()\n"
        )
        tree = ast.parse(code)
        func_node = self.walker.find_function(tree, "update")
        res = self.walker.walk_function(func_node, "update", filepath="game.py")
        self.assertEqual(len(res.call_sites), 2)

        cs0 = res.call_sites[0]
        self.assertEqual(cs0.callee_name, "step")
        self.assertEqual(cs0.callee_owner, "engine")
        self.assertEqual(cs0.line_number, 2)

        cs1 = res.call_sites[1]
        self.assertEqual(cs1.callee_name, "draw")
        self.assertEqual(cs1.callee_owner, "self.renderer")
        self.assertEqual(cs1.line_number, 3)

    def test_calls_in_conditions_and_returns(self):
        code = (
            "def check_and_run():\n"
            "    if is_ready():\n"
            "        return compute()\n"
            "    return None\n"
        )
        tree = ast.parse(code)
        func_node = self.walker.find_function(tree, "check_and_run")
        res = self.walker.walk_function(func_node, "check_and_run", filepath="logic.py")
        callee_names = [cs.callee_name for cs in res.call_sites]
        self.assertIn("is_ready", callee_names)
        self.assertIn("compute", callee_names)


if __name__ == '__main__':
    unittest.main()

