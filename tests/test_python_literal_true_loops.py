import json
import os
import re
import tempfile
import unittest

from code2petri.engine import code2petri


def _embedded_net(html_content):
    match = re.search(
        r'<script id="code2petri-data" type="application/json">\s*(\{.*?\})\s*</script>',
        html_content,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError("Generated HTML is missing its embedded graph data")
    return json.loads(match.group(1))["initial_net"]


def _has_path(net, source_id, target_id):
    adjacency = {}
    for arc in net["arcs"]:
        adjacency.setdefault(arc["source"], []).append(arc["target"])
    pending = [source_id]
    visited = set()
    while pending:
        current = pending.pop()
        if current == target_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        pending.extend(adjacency.get(current, []))
    return False


class TestLiteralTrueLoopHtmlExport(unittest.TestCase):
    def _export_function(self, target_function):
        fixture = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "petri_py",
            "literal_true_global.py",
        )
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        html_path = os.path.join(temp_dir.name, f"{target_function}.html")
        code2petri(
            source_path=fixture,
            output_file=html_path,
            target_function=target_function,
            no_fold=target_function != "(global)",
        )
        with open(html_path, encoding="utf-8") as html_file:
            return _embedded_net(html_file.read())

    def test_global_literal_true_enters_body_without_head_exit_or_exception(self):
        net = self._export_function("(global)")

        loop = next(
            transition
            for transition in net["transitions"]
            if transition["label"] == "while True"
        )
        self.assertEqual(loop["line_number"], 2)
        head = next(
            arc["source"]
            for arc in net["arcs"]
            if arc["target"] == loop["id"]
        )
        head_choices = [
            arc["target"]
            for arc in net["arcs"]
            if arc["source"] == head
        ]
        self.assertEqual(head_choices, [loop["id"]])

        body_call = next(
            transition
            for transition in net["transitions"]
            if transition["label"] == "call: win.update()"
        )
        self.assertEqual(body_call["line_number"], 3)
        body_exception = next(
            transition
            for transition in net["transitions"]
            if (transition.get("metadata") or {}).get("exception_alternative_of")
            == body_call["id"]
        )
        body_call_inputs = [
            arc["source"]
            for arc in net["arcs"]
            if arc["target"] == body_call["id"]
        ]
        body_exception_inputs = [
            arc["source"]
            for arc in net["arcs"]
            if arc["target"] == body_exception["id"]
        ]
        self.assertEqual(body_exception_inputs, body_call_inputs)
        self.assertIn(
            head,
            [
                arc["target"]
                for arc in net["arcs"]
                if arc["source"] == body_call["id"]
            ],
        )
        handler = next(
            transition
            for transition in net["transitions"]
            if transition["label"] == "except Exception"
        )
        self.assertEqual(handler["line_number"], 4)
        self.assertTrue(_has_path(net, body_exception["id"], handler["id"]))

    def test_loop_without_break_does_not_reach_following_statement(self):
        net = self._export_function("no_break")
        start = next(
            place["id"]
            for place in net["places"]
            if place.get("initial_tokens", 0) == 1
        )
        after_loop = [
            transition
            for transition in net["transitions"]
            if transition["label"] == "call: after_loop()"
        ]
        self.assertFalse(
            any(_has_path(net, start, transition["id"]) for transition in after_loop)
        )

    def test_break_leaves_loop_continue_repeats_and_true_loop_skips_else(self):
        net = self._export_function("break_and_continue")
        loop = next(
            transition
            for transition in net["transitions"]
            if transition["label"] == "while True"
        )
        head = next(
            arc["source"]
            for arc in net["arcs"]
            if arc["target"] == loop["id"]
        )
        continue_transition = next(
            transition
            for transition in net["transitions"]
            if transition["label"] == "continue"
        )
        break_transition = next(
            transition
            for transition in net["transitions"]
            if transition["label"] == "break"
        )
        after_loop = next(
            transition
            for transition in net["transitions"]
            if transition["label"] == "call: after_loop()"
        )

        self.assertTrue(_has_path(net, continue_transition["id"], head))
        self.assertTrue(_has_path(net, break_transition["id"], after_loop["id"]))
        self.assertFalse(
            any(
                transition["label"] == "call: on_exhaustion()"
                for transition in net["transitions"]
            )
        )

    def test_return_and_raise_keep_their_function_destinations(self):
        net = self._export_function("return_or_raise")
        return_transition = next(
            transition
            for transition in net["transitions"]
            if transition["label"] == "return"
        )
        raise_transition = next(
            transition
            for transition in net["transitions"]
            if transition["label"] == "raise ValueError()"
        )
        normal_end = next(
            place["id"]
            for place in net["places"]
            if place["label"] == "end"
        )
        exception_end = next(
            place["id"]
            for place in net["places"]
            if place["label"] == "exception_end"
        )

        self.assertTrue(_has_path(net, return_transition["id"], normal_end))
        self.assertTrue(_has_path(net, raise_transition["id"], exception_end))

    def test_ordinary_condition_keeps_false_and_exception_outcomes(self):
        net = self._export_function("ordinary_condition")
        loop = next(
            transition
            for transition in net["transitions"]
            if transition["label"] == "while ready()"
        )
        head = next(
            arc["source"]
            for arc in net["arcs"]
            if arc["target"] == loop["id"]
        )
        head_choices = [
            next(
                transition
                for transition in net["transitions"]
                if transition["id"] == arc["target"]
            )["label"]
            for arc in net["arcs"]
            if arc["source"] == head
        ]
        loop_exception = next(
            transition
            for transition in net["transitions"]
            if (transition.get("metadata") or {}).get("exception_alternative_of")
            == loop["id"]
        )
        handler = next(
            transition
            for transition in net["transitions"]
            if transition["label"] == "except Exception"
        )

        self.assertIn("exit", head_choices)
        self.assertIn("while ready()", head_choices)
        self.assertTrue(_has_path(net, loop_exception["id"], handler["id"]))
