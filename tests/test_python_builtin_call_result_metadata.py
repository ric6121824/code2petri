import os
import tempfile
import unittest

from code2petri.engine import code2petri


class TestPythonBuiltinCallResultMetadata(unittest.TestCase):
    def _net_for(self, source, function_name):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = os.path.join(temp_dir, "builtins_case.py")
            output_path = os.path.join(temp_dir, "builtins_case.html")
            with open(source_path, "w", encoding="utf-8") as source_file:
                source_file.write(source)
            result = code2petri(
                source_path, output_file=output_path, target_function=function_name, fold=False
            )
        return result.initial_net.to_dict()

    def test_catalog_calls_keep_independent_result_records_and_import_aliases(self):
        source = '''
from builtins import range as span, len as size
import builtins as pybuiltins

def inspect_calls():
    return [range(2), span(2), pybuiltins.len(size([str(1)])), list(), tuple(), dict(), set(), float(), int(), bool()]
'''
        net = self._net_for(source, "inspect_calls")
        records = [
            record
            for transition in net["transitions"]
            for record in (transition.get("metadata") or {}).get("call_results", [])
        ]
        by_expression = {record["expression"]: record for record in records}
        expected = {
            "range(2)": ("range", "builtins.range"),
            "span(2)": ("range", "builtins.range"),
            "pybuiltins.len(size([str(1)]))": ("int", "builtins.len"),
            "size([str(1)])": ("int", "builtins.len"),
            "str(1)": ("str", "builtins.str"),
            "list()": ("list", "builtins.list"),
            "tuple()": ("tuple", "builtins.tuple"),
            "dict()": ("dict", "builtins.dict"),
            "set()": ("set", "builtins.set"),
            "float()": ("float", "builtins.float"),
            "int()": ("int", "builtins.int"),
            "bool()": ("bool", "builtins.bool"),
        }
        self.assertEqual(set(by_expression), set(expected))
        for expression, (result_type, canonical_name) in expected.items():
            record = by_expression[expression]
            self.assertEqual(record["state"], "known", expression)
            self.assertEqual(record["type"], result_type, expression)
            self.assertEqual(record["canonical_builtin"], canonical_name, expression)
            self.assertEqual(record["provenance"], "python_builtin_static_contract", expression)
            self.assertEqual(record["transition_id"], next(
                transition["id"] for transition in net["transitions"]
                if record in (transition.get("metadata") or {}).get("call_results", [])
            ))
            self.assertIsInstance(record["source_location"]["line"], int)
            self.assertIsInstance(record["source_location"]["column"], int)

    def test_unknown_outer_and_shadowed_calls_do_not_borrow_inner_or_builtin_evidence(self):
        source = '''
def cases(len, range):
    known_outer_unknown_inner = list(make_items())
    unknown_outer_known_inner = custom(range(2))
    shadowed = len([])
    return known_outer_unknown_inner, unknown_outer_known_inner, shadowed
'''
        net = self._net_for(source, "cases")
        records = [
            record
            for transition in net["transitions"]
            for record in (transition.get("metadata") or {}).get("call_results", [])
        ]
        by_expression = {record["expression"]: record for record in records}
        self.assertEqual(by_expression["list(make_items())"]["type"], "list")
        self.assertEqual(by_expression["make_items()"]["state"], "unknown")
        self.assertEqual(by_expression["custom(range(2))"]["state"], "unknown")
        self.assertEqual(by_expression["range(2)"]["type"], "unknown")
        self.assertEqual(by_expression["len([])"]["type"], "unknown")
        self.assertEqual(by_expression["len([])"]["unknown_reason"], "shadowed_or_uncertain_binding")
        self.assertEqual(by_expression["make_items()"]["unknown_reason"], "no_available_contract")

    def test_create_board_keeps_enclosing_list_result_separate_from_range_call(self):
        source = "def create_board():\n    return ['|'] + [' ' for _ in range(9)]\n"
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = os.path.join(temp_dir, "board.py")
            output_path = os.path.join(temp_dir, "board.html")
            with open(source_path, "w", encoding="utf-8") as source_file:
                source_file.write(source)
            result = code2petri(
                source_path, output_file=output_path, target_function="create_board", fold=False
            )
            with open(output_path, encoding="utf-8") as html_file:
                html = html_file.read()

        net = result.initial_net.to_dict()
        returned = next(
            transition for transition in net["transitions"]
            if (transition.get("metadata") or {}).get("call_results")
        )
        call_record = returned["metadata"]["call_results"][0]
        enclosing = returned["metadata"]["function_return_evidence"]
        self.assertEqual(call_record["expression"], "range(9)")
        self.assertEqual(call_record["type"], "range")
        self.assertEqual(enclosing["expression"], "['|'] + [' ' for _ in range(9)]")
        self.assertEqual(enclosing["type"], "list")
        self.assertIn('id="inspector-call-results"', html)
        self.assertIn('id="inspector-return-expression"', html)
        self.assertIn("formatCallResultInspection(node.data('call_results'))", html)
        self.assertIn("formatEnclosingReturnEvidence(node.data('function_return_evidence'))", html)
        self.assertIn("call_site_id", html)

    def test_supported_contract_flows_through_locals_and_binding_uncertainty_stays_unknown(self):
        source = '''
import builtins

def local_flow():
    values = builtins.range(3)
    copied = values
    return copied

def rebound(len):
    return len([])

def late_local():
    return len([])
    len = custom

def unsupported_builtin():
    return zip()
'''
        net = self._net_for(source, "local_flow")
        self.assertEqual(net["return_metadata"]["analysis_status"], "complete")
        self.assertEqual(net["return_metadata"]["inferred_types"], ["range"])
        self.assertEqual(net["return_metadata"]["inferred"][0]["type"], "range")

        rebound_net = self._net_for(source, "rebound")
        rebound = next(
            record for transition in rebound_net["transitions"]
            for record in (transition.get("metadata") or {}).get("call_results", [])
        )
        self.assertEqual(rebound["state"], "unknown")
        self.assertEqual(rebound["unknown_reason"], "shadowed_or_uncertain_binding")

        late_net = self._net_for(source, "late_local")
        late = next(
            record for transition in late_net["transitions"]
            for record in (transition.get("metadata") or {}).get("call_results", [])
        )
        self.assertEqual(late["state"], "unknown")
        self.assertEqual(late["unknown_reason"], "shadowed_or_uncertain_binding")

        unsupported_net = self._net_for(source, "unsupported_builtin")
        unsupported = next(
            record for transition in unsupported_net["transitions"]
            for record in (transition.get("metadata") or {}).get("call_results", [])
        )
        self.assertEqual(unsupported["state"], "unknown")
        self.assertEqual(unsupported["unknown_reason"], "unsupported_builtin")

    def test_call_result_metadata_round_trips_offline_and_malformed_records_are_rejected(self):
        source = "def answer():\n    return range(2)\n"
        net = self._net_for(source, "answer")
        call_record = next(
            record for transition in net["transitions"]
            for record in (transition.get("metadata") or {}).get("call_results", [])
        )
        import json
        from tests.test_html_viewer import _run_node_script

        script = f"""
const cytoscape = require('./code2petri/viewer/vendor/cytoscape.min.js');
const {{ LiveFoldReductionEngine }} = require('./code2petri/viewer/engine/reduction_engine.js');
const {{ serializeFoldStateSnapshot, parseFoldStateSnapshot }} = require('./code2petri/viewer/engine/session_snapshot.js');
const callRecord = {json.dumps(call_record)};
const transitionId = callRecord.transition_id;
const originalNet = {json.dumps(net)};
const cy = cytoscape({{ elements: [
  {{ group: 'nodes', data: {{ id: 'p0' }} }},
  {{ group: 'nodes', data: {{ id: transitionId, call_results: [callRecord] }} }}
] }});
const document = {{
  title: 'Answer', projectTitle: '', sourceFile: '/offline/answer.py', filename: 'answer.html',
  functionName: 'answer', mode: 'no-fold', sidebarVisible: true, returnMetadata: originalNet.return_metadata,
  originalNet, compounds: [], foldSteps: [], calleeNets: {{}}, expandedNodes: [], finalSm: 0,
  fullyReducible: false, playback: {{ currentStep: 0, totalSteps: 0 }}
}};
const engine = new LiveFoldReductionEngine(cy);
const snapshot = parseFoldStateSnapshot(serializeFoldStateSnapshot({{ cy, engine, document }}));
const reopenedCall = snapshot.elements.find(element => element.data.id === transitionId).data.call_results[0];
if (JSON.stringify(reopenedCall) !== JSON.stringify(callRecord)) throw new Error('Call result did not survive offline snapshot round trip');
const malformed = JSON.parse(JSON.stringify(snapshot));
malformed.document.originalNet.transitions.find(item => item.metadata && item.metadata.call_results).metadata.call_results[0].state = 'maybe';
let rejected = false;
try {{ parseFoldStateSnapshot(malformed); }} catch (error) {{ rejected = error.message.includes('call_results'); }}
if (!rejected) throw new Error('Malformed call-result state was accepted');
        const mismatched = JSON.parse(JSON.stringify(snapshot));
        mismatched.document.originalNet.transitions.find(item => item.metadata && item.metadata.call_results).metadata.call_results[0].transition_id = 'other-transition';
        rejected = false;
        try {{ parseFoldStateSnapshot(mismatched); }} catch (error) {{ rejected = error.message.includes('transition_id'); }}
        if (!rejected) throw new Error('Mismatched call-result association was accepted');
console.log('PASS');
"""
        proc = _run_node_script(script)
        self.assertEqual(proc.returncode, 0, f"Call-result snapshot validation failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_nonlocal_global_and_wildcard_bindings_do_not_claim_builtin_contracts(self):
        source = '''
def outer(len):
    def inner():
        nonlocal len
        return len([])
    return inner

def global_rebind():
    global range
    range = custom
    return range(2)

def pattern_shadow(value):
    match value:
        case {"len": len}:
            pass
    return len([])

def reflective_rebind():
    import builtins as b
    setattr(b, "len", custom)
    return b.len([])

def imported_reflective_rebind():
    import builtins as b
    b.len = custom
    return size([])

def mutate_global_builtin():
    global len
    len = custom

def use_rebound_global_builtin():
    global len
    return len([])

import builtins as pybuiltins
def mutate_global_module_alias():
    global pybuiltins
    pybuiltins = custom

def use_rebound_global_module_alias():
    global pybuiltins
    return pybuiltins.range(2)
'''
        inner_net = self._net_for(source, "outer.inner")
        inner_call = next(
            record for transition in inner_net["transitions"]
            for record in (transition.get("metadata") or {}).get("call_results", [])
        )
        self.assertEqual(inner_call["state"], "unknown")
        self.assertEqual(inner_call["unknown_reason"], "shadowed_or_uncertain_binding")

        global_net = self._net_for(source, "global_rebind")
        global_call = next(
            record for transition in global_net["transitions"]
            for record in (transition.get("metadata") or {}).get("call_results", [])
        )
        self.assertEqual(global_call["state"], "unknown")
        self.assertEqual(global_call["unknown_reason"], "shadowed_or_uncertain_binding")

        pattern_net = self._net_for(source, "pattern_shadow")
        pattern_call = next(
            record for transition in pattern_net["transitions"]
            for record in (transition.get("metadata") or {}).get("call_results", [])
        )
        self.assertEqual(pattern_call["state"], "unknown")
        self.assertEqual(pattern_call["unknown_reason"], "shadowed_or_uncertain_binding")

        reflective_net = self._net_for(source, "reflective_rebind")
        reflective_call = next(
            record for transition in reflective_net["transitions"]
            for record in (transition.get("metadata") or {}).get("call_results", [])
            if record["expression"] == "b.len([])"
        )
        self.assertEqual(reflective_call["state"], "unknown")
        self.assertEqual(reflective_call["unknown_reason"], "shadowed_or_uncertain_binding")

        imported_source = "from builtins import len as size\n" + source
        imported_net = self._net_for(imported_source, "imported_reflective_rebind")
        imported_call = next(
            record for transition in imported_net["transitions"]
            for record in (transition.get("metadata") or {}).get("call_results", [])
            if record["expression"] == "size([])"
        )
        self.assertEqual(imported_call["state"], "unknown")
        self.assertEqual(imported_call["unknown_reason"], "shadowed_or_uncertain_binding")

        rebound_global_net = self._net_for(source, "use_rebound_global_builtin")
        rebound_global_call = next(
            record for transition in rebound_global_net["transitions"]
            for record in (transition.get("metadata") or {}).get("call_results", [])
        )
        self.assertEqual(rebound_global_call["state"], "unknown")
        self.assertEqual(rebound_global_call["unknown_reason"], "shadowed_or_uncertain_binding")

        rebound_module_net = self._net_for(source, "use_rebound_global_module_alias")
        rebound_module_call = next(
            record for transition in rebound_module_net["transitions"]
            for record in (transition.get("metadata") or {}).get("call_results", [])
        )
        self.assertEqual(rebound_module_call["state"], "unknown")
        self.assertEqual(rebound_module_call["unknown_reason"], "shadowed_or_uncertain_binding")

    def test_comprehension_and_nested_function_bindings_stay_in_their_own_scope(self):
        source = '''
def comprehension_target(values):
    copied = [len for len in values]
    return len([])

def outer_global_with_nested_local():
    global len
    def inner():
        len = custom
        return len([])
    return len([])
'''
        for function_name in ("comprehension_target", "outer_global_with_nested_local"):
            net = self._net_for(source, function_name)
            call = next(
                record for transition in net["transitions"]
                for record in (transition.get("metadata") or {}).get("call_results", [])
                if record["expression"] == "len([])"
            )
            self.assertEqual(call["state"], "known", function_name)
            self.assertEqual(call["type"], "int", function_name)

        wildcard_source = """from custom_module import *
def run():
    return len([])
"""
        wildcard_net = self._net_for(wildcard_source, "run")
        wildcard_call = next(
            record for transition in wildcard_net["transitions"]
            for record in (transition.get("metadata") or {}).get("call_results", [])
        )
        self.assertEqual(wildcard_call["state"], "unknown")
        self.assertEqual(wildcard_call["unknown_reason"], "shadowed_or_uncertain_binding")

        conflicting_imports = """from builtins import len
from custom_module import len
def run():
    return len([])
"""
        conflicting_net = self._net_for(conflicting_imports, "run")
        conflicting_call = next(
            record for transition in conflicting_net["transitions"]
            for record in (transition.get("metadata") or {}).get("call_results", [])
        )
        self.assertEqual(conflicting_call["state"], "unknown")
        self.assertEqual(conflicting_call["unknown_reason"], "shadowed_or_uncertain_binding")


if __name__ == "__main__":
    unittest.main()
