import json
import os
import sys
import unittest
import xml.etree.ElementTree as ET

# Ensure repo root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from code2petri.model import Place, Transition, Arc, PetriNet  # noqa: E402



class TestPetriModelBasics(unittest.TestCase):
    def test_place_attributes(self):
        p = Place(id="p1", label="start", line_number=10, initial_tokens=1)
        self.assertEqual(p.id, "p1")
        self.assertEqual(p.label, "start")
        self.assertEqual(p.line_number, 10)
        self.assertEqual(p.initial_tokens, 1)

    def test_place_defaults(self):
        p = Place(id="p2", label="step")
        self.assertIsNone(p.line_number)
        self.assertEqual(p.initial_tokens, 0)

    def test_transition_attributes(self):
        t = Transition(id="t1", label="execute()", line_number=12)
        self.assertEqual(t.id, "t1")
        self.assertEqual(t.label, "execute()")
        self.assertEqual(t.line_number, 12)

    def test_transition_defaults(self):
        t = Transition(id="t2", label="noop")
        self.assertIsNone(t.line_number)

    def test_arc_place_to_transition(self):
        p = Place(id="p1", label="p1")
        t = Transition(id="t1", label="t1")
        arc = Arc(source=p, target=t, weight=2)
        self.assertEqual(arc.source, p)
        self.assertEqual(arc.target, t)
        self.assertEqual(arc.weight, 2)

    def test_arc_transition_to_place(self):
        p = Place(id="p1", label="p1")
        t = Transition(id="t1", label="t1")
        arc = Arc(source=t, target=p)
        self.assertEqual(arc.source, t)
        self.assertEqual(arc.target, p)
        self.assertEqual(arc.weight, 1)

    def test_arc_bipartite_place_to_place_raises_error(self):
        p1 = Place(id="p1", label="p1")
        p2 = Place(id="p2", label="p2")
        with self.assertRaises(ValueError) as ctx:
            Arc(source=p1, target=p2)
        self.assertIn("bipartite", str(ctx.exception).lower())

    def test_arc_bipartite_transition_to_transition_raises_error(self):
        t1 = Transition(id="t1", label="t1")
        t2 = Transition(id="t2", label="t2")
        with self.assertRaises(ValueError) as ctx:
            Arc(source=t1, target=t2)
        self.assertIn("bipartite", str(ctx.exception).lower())


class TestPetriNetContainer(unittest.TestCase):
    def test_empty_net(self):
        net = PetriNet()
        self.assertEqual(len(net.places), 0)
        self.assertEqual(len(net.transitions), 0)
        self.assertEqual(len(net.arcs), 0)

    def test_add_place(self):
        net = PetriNet()
        p = net.add_place(id="p1", label="start", line_number=1, initial_tokens=1)
        self.assertIsInstance(p, Place)
        self.assertEqual(len(net.places), 1)
        self.assertIs(net.places[0], p)

    def test_add_transition(self):
        net = PetriNet()
        t = net.add_transition(id="t1", label="do_something()", line_number=2)
        self.assertIsInstance(t, Transition)
        self.assertEqual(len(net.transitions), 1)
        self.assertIs(net.transitions[0], t)

    def test_add_arc(self):
        net = PetriNet()
        p = net.add_place("p1", "start")
        t = net.add_transition("t1", "action")
        arc = net.add_arc(source=p, target=t, weight=1)
        self.assertIsInstance(arc, Arc)
        self.assertEqual(len(net.arcs), 1)
        self.assertIs(net.arcs[0], arc)

    def test_handbuilt_small_net(self):
        # 3 places, 2 transitions, 4 arcs
        net = PetriNet()
        p_start = net.add_place("p_start", "start", initial_tokens=1)
        p_mid = net.add_place("p_mid", "mid")
        p_end = net.add_place("p_end", "end")

        t1 = net.add_transition("t1", "step 1", line_number=10)
        t2 = net.add_transition("t2", "step 2", line_number=11)

        net.add_arc(p_start, t1)
        net.add_arc(t1, p_mid)
        net.add_arc(p_mid, t2)
        net.add_arc(t2, p_end)

        self.assertEqual(len(net.places), 3)
        self.assertEqual(len(net.transitions), 2)
        self.assertEqual(len(net.arcs), 4)

        # Assert PNML is valid XML
        pnml_str = net.to_pnml()
        root = ET.fromstring(pnml_str)
        self.assertIsNotNone(root)
        self.assertTrue(root.tag.endswith("pnml"))

        # Assert DOT has correct structure
        dot_str = net.to_dot()
        self.assertTrue(dot_str.strip().startswith("digraph"))
        self.assertTrue(dot_str.strip().endswith("}"))
        self.assertIn('"p_start" -> "t1";', dot_str)
        self.assertIn('"t2" -> "p_end";', dot_str)



class TestPNMLSerialization(unittest.TestCase):
    def setUp(self):
        self.net = PetriNet()
        self.p_start = self.net.add_place("p_start", "start_flow", line_number=1, initial_tokens=1)
        self.p_mid = self.net.add_place("p_mid", "mid_flow", line_number=2, initial_tokens=0)
        self.p_end = self.net.add_place("p_end", "end_flow", line_number=3)

        self.t1 = self.net.add_transition("t1", "x = 1", line_number=1)
        self.t2 = self.net.add_transition("t2", "return x", line_number=3)

        self.a1 = self.net.add_arc(self.p_start, self.t1)
        self.a2 = self.net.add_arc(self.t1, self.p_mid)
        self.a3 = self.net.add_arc(self.p_mid, self.t2)
        self.a4 = self.net.add_arc(self.t2, self.p_end)

    def test_to_pnml_valid_xml(self):
        pnml_str = self.net.to_pnml()
        self.assertIsInstance(pnml_str, str)
        root = ET.fromstring(pnml_str)
        # Verify root tag ends with pnml
        self.assertTrue(root.tag.endswith("pnml"))

    def test_pnml_places_and_markings(self):
        pnml_str = self.net.to_pnml()
        root = ET.fromstring(pnml_str)

        # Look up places anywhere in the tree
        places = [el for el in root.iter() if el.tag.endswith("place")]
        self.assertEqual(len(places), 3)

        place_ids = {p.attrib.get("id") for p in places}
        self.assertEqual(place_ids, {"p_start", "p_mid", "p_end"})

        # p_start should have initialMarking = 1
        p_start_el = next(p for p in places if p.attrib.get("id") == "p_start")
        marking_el = [el for el in p_start_el.iter() if el.tag.endswith("initialMarking")]
        self.assertEqual(len(marking_el), 1)
        text_el = [el for el in marking_el[0].iter() if el.tag.endswith("text")]
        self.assertEqual(len(text_el), 1)
        self.assertEqual(text_el[0].text, "1")

        # p_mid has initial_tokens = 0, so no initialMarking
        p_mid_el = next(p for p in places if p.attrib.get("id") == "p_mid")
        marking_mid = [el for el in p_mid_el.iter() if el.tag.endswith("initialMarking")]
        self.assertEqual(len(marking_mid), 0)

    def test_pnml_transitions(self):
        pnml_str = self.net.to_pnml()
        root = ET.fromstring(pnml_str)

        transitions = [el for el in root.iter() if el.tag.endswith("transition")]
        self.assertEqual(len(transitions), 2)
        t_ids = {t.attrib.get("id") for t in transitions}
        self.assertEqual(t_ids, {"t1", "t2"})

    def test_pnml_arcs(self):
        pnml_str = self.net.to_pnml()
        root = ET.fromstring(pnml_str)

        arcs = [el for el in root.iter() if el.tag.endswith("arc")]
        self.assertEqual(len(arcs), 4)

        arc_pairs = {(a.attrib.get("source"), a.attrib.get("target")) for a in arcs}
        expected_pairs = {
            ("p_start", "t1"),
            ("t1", "p_mid"),
            ("p_mid", "t2"),
            ("t2", "p_end"),
        }
        self.assertEqual(arc_pairs, expected_pairs)


class TestDOTSerialization(unittest.TestCase):
    def setUp(self):
        self.net = PetriNet()
        self.p_start = self.net.add_place("p_start", "start_flow", line_number=1, initial_tokens=1)
        self.p_mid = self.net.add_place("p_mid", "mid_flow", line_number=2, initial_tokens=0)
        self.p_end = self.net.add_place("p_end", "end_flow", line_number=3)

        self.t1 = self.net.add_transition("t1", 'x = "hello"', line_number=1)
        self.t2 = self.net.add_transition("t2", "return x", line_number=3)

        self.a1 = self.net.add_arc(self.p_start, self.t1)
        self.a2 = self.net.add_arc(self.t1, self.p_mid)
        self.a3 = self.net.add_arc(self.p_mid, self.t2)
        self.a4 = self.net.add_arc(self.t2, self.p_end, weight=2)

    def test_to_dot_header_and_rankdir(self):
        dot = self.net.to_dot()
        self.assertIn("digraph", dot)
        self.assertIn("rankdir=TB", dot)

    def test_to_dot_places_styling(self):
        dot = self.net.to_dot()
        self.assertIn('"p_start"', dot)
        self.assertIn("shape=circle", dot)

    def test_to_dot_transitions_styling(self):
        dot = self.net.to_dot()
        self.assertIn('"t1"', dot)
        self.assertIn("shape=rect", dot)
        self.assertIn("style=filled", dot)
        self.assertIn("fillcolor=black", dot)
        self.assertIn("fontcolor=white", dot)

    def test_to_dot_arc_connections(self):
        dot = self.net.to_dot()
        self.assertIn('"p_start" -> "t1"', dot)
        self.assertIn('"t1" -> "p_mid"', dot)
        self.assertIn('"p_mid" -> "t2"', dot)
        self.assertIn('"t2" -> "p_end"', dot)
        # Weight 2 on arc a4
        self.assertIn('label="2"', dot)

    def test_to_dot_label_escaping(self):
        dot = self.net.to_dot()
        # 'x = "hello"' should have quotes escaped in DOT label
        self.assertIn(r'\"hello\"', dot)

        # Test newline escaping
        net2 = PetriNet()
        net2.add_transition("t_multi", "line1\nline2")
        dot2 = net2.to_dot()
        self.assertIn(r"line1\nline2", dot2)
        self.assertNotIn("line1\nline2", dot2)


class TestPetriJsonSerialization(unittest.TestCase):
    def setUp(self):
        self.net = PetriNet()
        p0 = self.net.add_place(id="p0", label="start", line_number=1, initial_tokens=1)
        p1 = self.net.add_place(id="p1", label="end", line_number=2, initial_tokens=0)
        t0 = self.net.add_transition(id="t0", label="x = 1", line_number=1)
        self.net.add_arc(source=p0, target=t0, weight=1)
        self.net.add_arc(source=t0, target=p1, weight=1)

    def test_to_dict_structure(self):
        d = self.net.to_dict()
        self.assertEqual(len(d["places"]), 2)
        self.assertEqual(len(d["transitions"]), 1)
        self.assertEqual(len(d["arcs"]), 2)
        self.assertEqual(d["places"][0]["id"], "p0")
        self.assertEqual(d["places"][0]["initial_tokens"], 1)
        self.assertEqual(d["transitions"][0]["label"], "x = 1")
        self.assertEqual(d["arcs"][0]["source"], "p0")
        self.assertEqual(d["arcs"][0]["target"], "t0")

    def test_to_json_valid(self):
        raw_json = self.net.to_json()
        parsed = json.loads(raw_json)
        self.assertEqual(parsed, self.net.to_dict())


class TestTransitionMetadataAndSerialization(unittest.TestCase):
    def test_transition_metadata_default_is_none(self):
        t = Transition(id="t1", label="run()")
        self.assertIsNone(t.metadata)
        d = t.to_dict()
        self.assertNotIn("metadata", d)
        self.assertNotIn("resolved", d)

    def test_transition_metadata_explicit(self):
        meta = {"resolved": True, "resolved_to": "Worker.process", "target_file": "worker.py"}
        t = Transition(id="t1", label="worker.process()", line_number=5, metadata=meta)
        self.assertEqual(t.metadata, meta)
        d = t.to_dict()
        self.assertEqual(d["metadata"], meta)
        self.assertTrue(d["resolved"])
        self.assertEqual(d["resolved_to"], "Worker.process")
        self.assertEqual(d["target_file"], "worker.py")

    def test_petri_net_add_transition_forwards_metadata(self):
        net = PetriNet()
        meta = {"resolved": False}
        t = net.add_transition(id="t0", label="external()", line_number=3, metadata=meta)
        self.assertEqual(t.metadata, meta)
        self.assertEqual(len(net.transitions), 1)
        self.assertIs(net.transitions[0], t)

    def test_pnml_serialization_with_resolved_and_unresolved_metadata(self):
        net = PetriNet()
        p0 = net.add_place("p0", "start", initial_tokens=1)
        p1 = net.add_place("p1", "mid")
        p2 = net.add_place("p2", "end")

        t_res = net.add_transition(
            id="t1",
            label="call: gpuEngine.step()",
            metadata={"resolved": True, "resolved_to": "WebGLEngine.step", "target_file": "webgl-engine.js"},
        )
        t_unres = net.add_transition(
            id="t2",
            label="call: document.getElementById()",
            metadata={"resolved": False},
        )
        net.add_arc(p0, t_res)
        net.add_arc(t_res, p1)
        net.add_arc(p1, t_unres)
        net.add_arc(t_unres, p2)

        pnml_xml = net.to_pnml()
        root = ET.fromstring(pnml_xml)

        transitions = {t.attrib["id"]: t for t in root.iter() if t.tag.endswith("transition")}
        self.assertIn("t1", transitions)
        self.assertIn("t2", transitions)

        # t1: resolved
        tool_t1 = [el for el in transitions["t1"].iter() if el.tag.endswith("toolspecific")]
        self.assertEqual(len(tool_t1), 1)
        self.assertEqual(tool_t1[0].attrib.get("tool"), "code2petri")
        self.assertEqual(tool_t1[0].attrib.get("version"), "1.0")
        resolved_el = [el for el in tool_t1[0].iter() if el.tag.endswith("resolved")]
        self.assertEqual(len(resolved_el), 1)
        self.assertEqual(resolved_el[0].attrib.get("target"), "WebGLEngine.step")
        self.assertEqual(resolved_el[0].attrib.get("file"), "webgl-engine.js")

        # t2: unresolved
        tool_t2 = [el for el in transitions["t2"].iter() if el.tag.endswith("toolspecific")]
        self.assertEqual(len(tool_t2), 1)
        unresolved_el = [el for el in tool_t2[0].iter() if el.tag.endswith("unresolved")]
        self.assertEqual(len(unresolved_el), 1)

    def test_dot_serialization_with_resolved_and_unresolved_metadata(self):
        net = PetriNet()
        p0 = net.add_place("p0", "start", initial_tokens=1)
        p1 = net.add_place("p1", "end")

        t_res = net.add_transition(
            id="t1",
            label="call: foo()",
            metadata={"resolved": True, "resolved_to": "Foo.foo", "target_file": "foo.py"},
        )
        t_unres = net.add_transition(
            id="t2",
            label="call: bar()",
            metadata={"resolved": False},
        )
        net.add_arc(p0, t_res)
        net.add_arc(t_res, p1)
        net.add_arc(p1, t_unres)

        dot = net.to_dot()
        self.assertIn('color="#2e7d32"', dot)
        self.assertIn('tooltip="Resolved to Foo.foo in foo.py"', dot)
        self.assertIn('color="#e65100"', dot)
        self.assertIn('tooltip="Unresolved call"', dot)

    def test_json_serialization_preserves_metadata(self):
        net = PetriNet()
        meta = {"resolved": True, "resolved_to": "App.start", "target_file": "app.js"}
        net.add_transition(id="t0", label="start()", metadata=meta)

        data = json.loads(net.to_json())
        t0_data = data["transitions"][0]
        self.assertEqual(t0_data["metadata"], meta)
        self.assertTrue(t0_data["resolved"])
        self.assertEqual(t0_data["resolved_to"], "App.start")
        self.assertEqual(t0_data["target_file"], "app.js")

    def test_generic_metadata_serialization(self):
        net = PetriNet()
        p0 = net.add_place("p0", "start", initial_tokens=1)
        p1 = net.add_place("p1", "end")
        t = net.add_transition(
            id="t0",
            label="custom_op()",
            metadata={"tag": "critical", "cost": 42, "tooltip": "Custom Cost Op"},
        )
        net.add_arc(p0, t)
        net.add_arc(t, p1)

        # Dict / JSON
        d = t.to_dict()
        self.assertEqual(d["metadata"]["tag"], "critical")
        self.assertEqual(d["metadata"]["cost"], 42)
        json_data = json.loads(net.to_json())
        self.assertEqual(json_data["transitions"][0]["metadata"]["tag"], "critical")

        # PNML
        pnml_xml = net.to_pnml()
        root = ET.fromstring(pnml_xml)
        props = {
            el.attrib["name"]: el.attrib["value"]
            for el in root.iter()
            if el.tag.endswith("property")
        }
        self.assertEqual(props.get("tag"), "critical")
        self.assertEqual(props.get("cost"), "42")

        # DOT
        dot = net.to_dot()
        self.assertIn('tooltip="Custom Cost Op"', dot)


if __name__ == '__main__':
    unittest.main()
