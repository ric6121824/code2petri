import json
import os
import subprocess
import tempfile
import unittest

from code2petri.engine import code2petri, discover_context_files
from code2petri.inline import precompute_callee_nets
from code2petri.model import PetriNet, Place, Transition
from code2petri.symbol_table import SymbolTable
from code2petri.viewer import generate_html
from code2petri.walker_protocol import CallSite


class TestPrecomputeCalleeNets(unittest.TestCase):
    def setUp(self):
        self.game_of_life_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "test_code", "game_of_life")
        )
        self.app_js = os.path.join(self.game_of_life_dir, "app.js")
        self.webgl_js = os.path.join(self.game_of_life_dir, "webgl-engine.js")

        self.symbol_table = SymbolTable()
        self.symbol_table.index_file(self.app_js)
        self.symbol_table.index_file(self.webgl_js)

    def test_precompute_depth_1(self):
        """Validates that depth=1 precomputes top-level resolved callees."""
        call_sites = [
            CallSite(
                caller_file=self.app_js,
                caller_function="loop",
                callee_name="step",
                callee_owner="gpuEngine",
                line_number=120,
                transition_id="t_step",
            ),
            CallSite(
                caller_file=self.app_js,
                caller_function="loop",
                callee_name="stepCpu",
                callee_owner=None,
                line_number=122,
                transition_id="t_step_cpu",
            ),
        ]
        caller_net = PetriNet()
        caller_net.add_place("p0", "start", initial_tokens=1)
        caller_net.add_transition("t_step", "gpuEngine.step()")
        caller_net.add_transition("t_step_cpu", "stepCpu()")
        caller_net.add_place("p1", "end")

        callee_nets = precompute_callee_nets(
            call_sites=call_sites,
            symbol_table=self.symbol_table,
            max_depth=1,
        )

        self.assertIn("WebGLEngine.step", callee_nets)
        self.assertIn("stepCpu", callee_nets)

        # Check structure of WebGLEngine.step
        step_net = callee_nets["WebGLEngine.step"]
        self.assertIn("places", step_net)
        self.assertIn("transitions", step_net)
        self.assertIn("arcs", step_net)
        self.assertGreater(len(step_net["transitions"]), 0)

        # Bare name should also be keyed for easy lookup
        self.assertIn("step", callee_nets)

    def test_precompute_depth_2_nested_calls(self):
        """Validates that depth=2 resolves and precomputes callees called inside callee subnets."""
        # In Game of Life, randomizeBoth calls WebGLEngine.randomize and randomizeCpu (or init calls initShaders)
        call_sites = [
            CallSite(
                caller_file=self.app_js,
                caller_function="init",
                callee_name="initShaders",
                callee_owner="gpuEngine",
                line_number=45,
                transition_id="t_init_shaders",
            ),
        ]
        caller_net = PetriNet()
        caller_net.add_place("p0", "start", initial_tokens=1)
        caller_net.add_transition("t_init_shaders", "gpuEngine.initShaders()")
        caller_net.add_place("p1", "end")

        callee_nets = precompute_callee_nets(
            call_sites=call_sites,
            symbol_table=self.symbol_table,
            max_depth=2,
        )

        self.assertIn("WebGLEngine.initShaders", callee_nets)

    def test_precompute_recursion_guard(self):
        """Validates that recursive functions do not cause an infinite recursion loop."""
        tmp_file = tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False)
        try:
            tmp_file.write(
                "def rec_a(n):\n"
                "    if n > 0:\n"
                "        rec_a(n - 1)\n"
            )
            tmp_file.close()

            st = SymbolTable()
            st.index_file(tmp_file.name)

            caller_net = PetriNet()
            caller_net.add_place("p0", "start", initial_tokens=1)
            caller_net.add_transition("t_rec", "rec_a(10)")
            caller_net.add_place("p1", "end")

            call_sites = [
                CallSite(
                    caller_file=tmp_file.name,
                    caller_function="main",
                    callee_name="rec_a",
                    callee_owner=None,
                    line_number=3,
                    transition_id="t_rec",
                )
            ]

            callee_nets = precompute_callee_nets(
                call_sites=call_sites,
                symbol_table=st,
                max_depth=5,
            )
            self.assertIn("rec_a", callee_nets)
        finally:
            if os.path.exists(tmp_file.name):
                os.remove(tmp_file.name)


def _get_viewer_functions() -> str:
    """Extracts findBoundaryPlaces and netToElements directly from template.html."""
    import re
    template_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "code2petri", "viewer", "template.html")
    )
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    m1 = re.search(r"(function findBoundaryPlaces\(calleeNet\) \{[\s\S]*?\n      \})", html)
    m2 = re.search(r"(function netToElements\(net\) \{[\s\S]*?\n      \})", html)
    if not m1 or not m2:
        raise ValueError("Could not extract findBoundaryPlaces or netToElements from template.html")
    return f"{m1.group(1)}\n{m2.group(1)}\n"


class TestCytoscapeClientSideExpansion(unittest.TestCase):
    """Verifies Cytoscape compound node expansion, rewiring, and collapse via Node.js."""

    def test_headless_cytoscape_compound_expansion_and_collapse(self):
        """Simulates client-side tap events, compound node mutation, boundary unification, and collapse."""
        viewer_fns = _get_viewer_functions()
        node_script = f"""
const cytoscape = require('./code2petri/viewer/vendor/cytoscape.min.js');

{viewer_fns}

const initialNet = {{
  places: [{{ id: 'p0', initial_tokens: 1, label: 'start' }}, {{ id: 'p1', label: 'mid' }}, {{ id: 'p2', label: 'end' }}],
  transitions: [
    {{ id: 't0', label: 'setup()' }},
    {{ id: 't1', label: 'gpuEngine.step()', resolved: true, resolved_to: 'WebGLEngine.step' }}
  ],
  arcs: [
    {{ source: 'p0', target: 't0' }},
    {{ source: 't0', target: 'p1' }},
    {{ source: 'p1', target: 't1' }},
    {{ source: 't1', target: 'p2' }}
  ]
}};

const calleeNetsMap = {{
  'WebGLEngine.step': {{
    places: [
      {{ id: 'cp_in', initial_tokens: 1, label: 'start' }},
      {{ id: 'cp_mid', label: 'intermediate' }},
      {{ id: 'cp_out', label: 'end' }}
    ],
    transitions: [
      {{ id: 'ct1', label: 'compute_step' }},
      {{ id: 'ct2', label: 'swap_buffers' }}
    ],
    arcs: [
      {{ source: 'cp_in', target: 'ct1' }},
      {{ source: 'ct1', target: 'cp_mid' }},
      {{ source: 'cp_mid', target: 'ct2' }},
      {{ source: 'ct2', target: 'cp_out' }}
    ]
  }}
}};

const expandedNodes = new Map();

// 1. Initial graph before expansion
const cy1 = cytoscape({{ headless: true, elements: netToElements(initialNet) }});
if (cy1.nodes().length !== 5) throw new Error('Expected 5 nodes initially, got ' + cy1.nodes().length);
if (cy1.$('#t1').isParent()) throw new Error('t1 should not be parent initially');

// 2. Expand t1
expandedNodes.set('t1', {{ calleeName: 'WebGLEngine.step' }});
const cy2 = cytoscape({{ headless: true, elements: netToElements(initialNet) }});

if (!cy2.$('#t1').isParent()) throw new Error('t1 should be parent after expansion');
// With boundary place unification (ADR-0002), cp_in and cp_out are unified away, leaving 3 children (1 place + 2 transitions)
if (cy2.$('#t1').children().length !== 3) throw new Error('t1 should have 3 children, got ' + cy2.$('#t1').children().length);
if (!cy2.$('#t1').hasClass('compound')) throw new Error('t1 should have compound class');

// Assert boundary places are unified and not rendered as orphan places
if (cy2.$('#t1__cp_in').length !== 0) throw new Error('Boundary place t1__cp_in must be unified');
if (cy2.$('#t1__cp_out').length !== 0) throw new Error('Boundary place t1__cp_out must be unified');

// Assert strict bipartite graph integrity (ADR-0002): No Place-to-Place or Transition-to-Transition arcs
cy2.edges().forEach(e => {{
  const srcIsPlace = e.source().hasClass('place');
  const tgtIsPlace = e.target().hasClass('place');
  if (srcIsPlace === tgtIsPlace) {{
    throw new Error('Bipartite net violation: edge ' + e.source().id() + ' -> ' + e.target().id() + ' connects identical types');
  }}
}});

// Check boundary place unification: preset place p1 connects directly to callee entrance transition (t1__ct1)
const inEdge = cy2.edges('[source = "p1"]');
if (inEdge.target().id() !== 't1__ct1') throw new Error('Incoming arc should target callee entrance transition t1__ct1, got ' + inEdge.target().id());

// Check boundary place unification: callee exit transition (t1__ct2) connects directly to postset place p2
const outEdge = cy2.edges('[target = "p2"]');
if (outEdge.source().id() !== 't1__ct2') throw new Error('Outgoing arc should source from callee exit transition t1__ct2, got ' + outEdge.source().id());

// 3. Collapse t1
expandedNodes.delete('t1');
const cy3 = cytoscape({{ headless: true, elements: netToElements(initialNet) }});

if (cy3.$('#t1').isParent()) throw new Error('t1 should not be parent after collapse');
if (cy3.nodes().length !== 5) throw new Error('Expected 5 nodes after collapse, got ' + cy3.nodes().length);

// Arcs should be restored to connect directly to t1
if (cy3.edges('[source = "p1"]').target().id() !== 't1') throw new Error('Incoming arc should be restored to target t1');
if (cy3.edges('[target = "p2"]').source().id() !== 't1') throw new Error('Outgoing arc should be restored to source t1');

console.log('PASS');
"""
        proc = subprocess.run(
            ["node", "-e", node_script],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_fold_slider_independence_with_active_expansion(self):
        """Verifies that the fold slider operates independently of expanded compound nodes."""
        viewer_fns = _get_viewer_functions()
        node_script = f"""
const cytoscape = require('./code2petri/viewer/vendor/cytoscape.min.js');

{viewer_fns}

// Step 0: Unfolded net
const step0 = {{
  places: [{{ id: 'p0', label: 'start' }}, {{ id: 'p1', label: 'mid' }}, {{ id: 'p2', label: 'end' }}],
  transitions: [
    {{ id: 't0', label: 'stmt1' }},
    {{ id: 't1', label: 'call()', resolved: true, resolved_to: 'callee' }}
  ],
  arcs: [
    {{ source: 'p0', target: 't0' }},
    {{ source: 't0', target: 'p1' }},
    {{ source: 'p1', target: 't1' }},
    {{ source: 't1', target: 'p2' }}
  ]
}};

// Step 1: Sequence fold collapsed p0 -> t0 -> p1 into t_C1 -> p1
const step1 = {{
  places: [{{ id: 'p1', label: 'mid' }}, {{ id: 'p2', label: 'end' }}],
  transitions: [
    {{ id: 't_C1', label: 'folded_t0', metadata: {{ opaque: true, tau: 1.0 }} }},
    {{ id: 't1', label: 'call()', resolved: true, resolved_to: 'callee' }}
  ],
  arcs: [
    {{ source: 't_C1', target: 'p1' }},
    {{ source: 'p1', target: 't1' }},
    {{ source: 't1', target: 'p2' }}
  ]
}};

const calleeNetsMap = {{
  'callee': {{
    places: [{{ id: 'cp0', label: 'start' }}, {{ id: 'cp1', label: 'end' }}],
    transitions: [{{ id: 'ct0', label: 'raw_callee_stmt' }}],
    arcs: [
      {{ source: 'cp0', target: 'ct0' }},
      {{ source: 'ct0', target: 'cp1' }}
    ]
  }}
}};

const expandedNodes = new Map();
expandedNodes.set('t1', {{ calleeName: 'callee' }});

// Check at Step 0: outer net unreduced, t1 expanded with raw callee (boundary places cp0/cp1 unified)
const cy0 = cytoscape({{ headless: true, elements: netToElements(step0) }});
if (!cy0.$('#t1').isParent()) throw new Error('t1 should be parent at step 0');
if (cy0.$('#t1').children().length !== 1) throw new Error('t1 should have 1 raw child (ct0) at step 0');
if (cy0.edges('[source = "p1"]').target().id() !== 't1__ct0') throw new Error('p1 should target t1__ct0');

// Check at Step 1: outer net folded (t_C1 exists), but t1 REMAINS expanded with raw callee!
const cy1 = cytoscape({{ headless: true, elements: netToElements(step1) }});
if (!cy1.$('#t1').isParent()) throw new Error('t1 should remain parent at step 1');
if (cy1.$('#t1').children().length !== 1) throw new Error('t1 should have 1 raw child at step 1');
if (cy1.$('#t_C1').length === 0) throw new Error('Outer fold transition t_C1 should exist at step 1');
if (cy1.edges('[source = "p1"]').target().id() !== 't1__ct0') throw new Error('p1 should target t1__ct0 at step 1');

console.log('PASS');
"""
        proc = subprocess.run(
            ["node", "-e", node_script],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)


if __name__ == "__main__":
    unittest.main()

