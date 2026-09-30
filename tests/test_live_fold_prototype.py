import os
import shutil
import subprocess
import unittest

from run_prototype import run_check, REPO_ROOT, PROTOTYPE_DIR, VENDOR_DIR


class TestLiveFoldPrototype(unittest.TestCase):
    def test_prototype_runner_check(self):
        """Verifies prototype files and asset check pass cleanly."""
        res = run_check(port=8095)
        self.assertEqual(res, 0, "run_check failed to find files or bind test port")

    def test_prototype_node_reduction_engine(self):
        """Runs the headless Node.js verification test for Live Fold reduction math and PNML export."""
        node_bin = shutil.which("node")
        if not node_bin:
            self.skipTest("node binary not found on PATH")

        test_script = """
const cytoscape = require("./code2petri/viewer/vendor/cytoscape.min.js");
const { LiveFoldReductionEngine } = require("./code2petri/viewer/prototype/reduction_engine.js");
const { serializeToPnml } = require("./code2petri/viewer/prototype/pnml_exporter.js");

global.window = {};
require("./code2petri/viewer/prototype/sample_data.js");
const sample = window.PROTOTYPE_SAMPLES["ecommerce_workflow"];

const elements = [];
(sample.compounds || []).forEach(c => {
  elements.push({ group: "nodes", data: { id: c.id, label: c.label, is_compound: true }, classes: "compound" });
});
sample.places.forEach(p => {
  elements.push({ group: "nodes", data: { id: p.id, label: p.label, initial_tokens: p.initial_tokens || 0, parent: p.parent }, classes: "place" });
});
sample.transitions.forEach(t => {
  elements.push({ group: "nodes", data: { id: t.id, label: t.label, tau: t.tau || 1.0, parent: t.parent }, classes: "transition" });
});
sample.arcs.forEach((a, i) => {
  elements.push({ group: "edges", data: { id: "a" + i, source: a.source, target: a.target, weight: a.weight || 1 }, classes: "arc" });
});

const cy = cytoscape({ elements: elements });
const engine = new LiveFoldReductionEngine(cy, { sequence: 1.0 });

// 1. Initial SM score
if (engine.calculateSMScore() !== 8.0) {
  throw new Error("Expected initial SM score 8.0, got " + engine.calculateSMScore());
}

// 2. Single-Place Contraction on p_auth_mid
const pAuth = cy.getElementById("p_auth_mid");
const checkAuth = engine.canContractPlace(pAuth);
if (!checkAuth.ok) {
  throw new Error("p_auth_mid should be contractible: " + checkAuth.reason);
}

const foldRes = engine.executeSinglePlaceContraction(pAuth);
if (!foldRes.success) {
  throw new Error("Fold failed: " + foldRes.message);
}

// Check weights: tau = 1 + 1 + 1 = 3.0, running SM = 8 + 1 = 9.0
const c01 = cy.getElementById("c_01");
if (c01.length === 0 || c01.data("tau") !== 3.0 || c01.data("omega") !== 1.0) {
  throw new Error("c_01 tau or omega incorrect");
}
if (engine.calculateSMScore() !== 9.0) {
  throw new Error("Expected running SM 9.0, got " + engine.calculateSMScore());
}

// 3. Node Renaming
const renamed = engine.renameNode("c_01", "check_and_fetch");
if (!renamed || c01.data("label") !== "check_and_fetch") {
  throw new Error("Renaming failed");
}

// 4. Component-Local Unfold
const unfoldRes = engine.executeComponentLocalUnfold(c01);
if (!unfoldRes.success) {
  throw new Error("Unfold failed: " + unfoldRes.message);
}
if (engine.calculateSMScore() !== 8.0) {
  throw new Error("Unfold did not restore SM to 8.0, got " + engine.calculateSMScore());
}
if (cy.getElementById("p_auth_mid").length === 0) {
  throw new Error("Unfold did not restore p_auth_mid place");
}

// 5. Test Collapsed Compound State and Function Boundary Constraint
// Before validate_user is fully folded, boundary place p_routed_0 must NOT be contractible
const pRouted0 = cy.getElementById("p_routed_0");
if (engine.canContractPlace(pRouted0).ok) {
  throw new Error("p_routed_0 should NOT be contractible before validate_user is folded into a single component");
}

engine.executeSinglePlaceContraction(cy.getElementById("p_auth_mid"));

// Even after 1 fold, validate_user still has c_02 and t_v3, so p_routed_0 must still be blocked
if (engine.canContractPlace(pRouted0).ok) {
  throw new Error("p_routed_0 should STILL be blocked while validate_user has >1 node");
}

engine.executeSinglePlaceContraction(cy.getElementById("p_profile_mid"));
const comp = cy.getElementById("compound_validate_user");
if (!comp.hasClass("collapsed-compound")) {
  throw new Error("compound_validate_user should be in collapsed-compound state");
}

// Now that validate_user is folded into a single component node, p_routed_0 CAN fold
if (!engine.canContractPlace(pRouted0).ok) {
  throw new Error("p_routed_0 should now be contractible after validate_user is folded into single component");
}
const foldRouted = engine.executeSinglePlaceContraction(pRouted0);
if (!foldRouted.success) {
  throw new Error("Failed to fold p_routed_0 after validate_user collapsed");
}

// Verify continuous process line: the newly created component MUST have both incoming from p_start and outgoing to p_user_valid
const cNew = cy.getElementById(foldRouted.step.opaqueId);
if (cNew.incomers("edge").length === 0 || cNew.outgoers("edge").length === 0) {
  throw new Error("Process line broke! " + foldRouted.step.opaqueId + " has missing incoming or outgoing arcs");
}
if (cNew.outgoers("edge")[0].target().id() !== "p_user_valid") {
  throw new Error(foldRouted.step.opaqueId + " outgoing edge targets wrong place: " + cNew.outgoers("edge")[0].target().id());
}

// 6. PNML Serialization
const pnml = serializeToPnml(cy, "TestExport", { includeTools: true });
if (!pnml.includes("<pnml") || !pnml.includes("toolspecific")) {
  throw new Error("PNML export missing required elements");
}

console.log("ALL_ECOMMERCE_CHECKS_PASSED");
"""
        proc = subprocess.run(
            [node_bin, "-e", test_script],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            proc.returncode,
            0,
            f"Node verification failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}",
        )
        self.assertIn("ALL_ECOMMERCE_CHECKS_PASSED", proc.stdout)

    def test_bipartite_petri_net_invariants_and_python_pipeline(self):
        """Verifies strict bipartite Petri Net structure (Place <-> Transition only) and AST sample reduction."""
        node_bin = shutil.which("node")
        if not node_bin:
            self.skipTest("node binary not found on PATH")

        test_script = """
const cytoscape = require("./code2petri/viewer/vendor/cytoscape.min.js");
const { LiveFoldReductionEngine } = require("./code2petri/viewer/prototype/reduction_engine.js");

global.window = {};
require("./code2petri/viewer/prototype/sample_data.js");

// 1. Verify Bipartite Invariants across all samples
for (const [key, sample] of Object.entries(window.PROTOTYPE_SAMPLES)) {
  const placeIds = new Set(sample.places.map(p => p.id));
  const transitionIds = new Set(sample.transitions.map(t => t.id));

  // Check disjointness
  for (const pid of placeIds) {
    if (transitionIds.has(pid)) {
      throw new Error(`Sample ${key}: ID ${pid} exists in both places and transitions!`);
    }
  }

  // Check every arc is strictly P -> T or T -> P
  sample.arcs.forEach((arc, i) => {
    const sIsP = placeIds.has(arc.source);
    const sIsT = transitionIds.has(arc.source);
    const tIsP = placeIds.has(arc.target);
    const tIsT = transitionIds.has(arc.target);

    if (!sIsP && !sIsT) throw new Error(`Sample ${key} arc ${i}: Unknown source ${arc.source}`);
    if (!tIsP && !tIsT) throw new Error(`Sample ${key} arc ${i}: Unknown target ${arc.target}`);

    if (sIsP && tIsP) {
      throw new Error(`Sample ${key} arc ${i}: Place -> Place violation: ${arc.source} -> ${arc.target}`);
    }
    if (sIsT && tIsT) {
      throw new Error(`Sample ${key} arc ${i}: Transition -> Transition violation: ${arc.source} -> ${arc.target}`);
    }
  });
}

// 2. Specific checks on python_mixed_pipeline AST sample
const pySample = window.PROTOTYPE_SAMPLES["python_mixed_pipeline"];
const elements = [];
(pySample.compounds || []).forEach(c => {
  elements.push({ group: "nodes", data: { id: c.id, label: c.label, is_compound: true }, classes: "compound" });
});
pySample.places.forEach(p => {
  elements.push({ group: "nodes", data: { id: p.id, label: p.label, initial_tokens: p.initial_tokens || 0, parent: p.parent }, classes: "place" });
});
pySample.transitions.forEach(t => {
  elements.push({ group: "nodes", data: { id: t.id, label: t.label, tau: t.tau || 1.0, parent: t.parent }, classes: "transition" });
});
pySample.arcs.forEach((a, i) => {
  elements.push({ group: "edges", data: { id: "a" + i, source: a.source, target: a.target, weight: a.weight || 1 }, classes: "arc" });
});

const cy = cytoscape({ elements: elements });
const engine = new LiveFoldReductionEngine(cy);

// Check node types and connectivity
const pFinally = cy.getElementById("p9");
if (!pFinally.hasClass("place") || pFinally.data("label") !== "finally_entry") {
  throw new Error("p9 must be a place with label finally_entry");
}
// Incoming to finally_entry must be transitions
pFinally.incomers("edge").forEach(e => {
  if (!e.source().hasClass("transition")) {
    throw new Error(`Incoming to finally_entry must be transition, got: ${e.source().id()}`);
  }
});
// Outgoing from finally_entry must be transitions
pFinally.outgoers("edge").forEach(e => {
  if (!e.target().hasClass("transition")) {
    throw new Error(`Outgoing from finally_entry must be transition, got: ${e.target().id()}`);
  }
});

const t12 = cy.getElementById("t12");
if (!t12.hasClass("transition") || t12.data("label") !== "final_res += 10") {
  throw new Error("t12 must be a transition with label final_res += 10");
}
t12.incomers("edge").forEach(e => {
  if (!e.source().hasClass("place")) throw new Error(`Incoming to t12 must be place, got: ${e.source().id()}`);
});
t12.outgoers("edge").forEach(e => {
  if (!e.target().hasClass("place")) throw new Error(`Outgoing from t12 must be place, got: ${e.target().id()}`);
});

const t5 = cy.getElementById("t5");
if (!t5.hasClass("transition") || t5.data("label") !== "if item > 1") {
  throw new Error("t5 must be a transition with label if item > 1");
}
t5.incomers("edge").forEach(e => {
  if (!e.source().hasClass("place")) throw new Error(`Incoming to t5 must be place, got: ${e.source().id()}`);
});
t5.outgoers("edge").forEach(e => {
  if (!e.target().hasClass("place")) throw new Error(`Outgoing from t5 must be place, got: ${e.target().id()}`);
});

// 3. Boundary folding behavior in python_mixed_pipeline
const p5 = cy.getElementById("p5");
// Before helper_calc is collapsed, p5 cannot contract
if (engine.canContractPlace(p5).ok) {
  throw new Error("p5 should NOT contract before helper_calc is collapsed into single component");
}

// Fold internal place of helper_calc
const pHelper = cy.getElementById("p_helper_mid");
const foldHelper = engine.executeSinglePlaceContraction(pHelper);
if (!foldHelper.success) {
  throw new Error("Failed to fold p_helper_mid inside helper_calc");
}
const compHelper = cy.getElementById("compound_helper_calc");
if (!compHelper.hasClass("collapsed-compound")) {
  throw new Error("compound_helper_calc should be collapsed-compound");
}

// Now p5 CAN contract
if (!engine.canContractPlace(p5).ok) {
  throw new Error("p5 should now be contractible after helper_calc collapsed");
}
const foldP5 = engine.executeSinglePlaceContraction(p5);
if (!foldP5.success) {
  throw new Error("Failed to fold p5: " + foldP5.message);
}

const cP5 = cy.getElementById(foldP5.step.opaqueId);
if (cP5.incomers("edge").length === 0 || cP5.outgoers("edge").length === 0) {
  throw new Error("Continuous process line broke after folding p5!");
}
if (cP5.incomers("edge")[0].source().id() !== "p4" || cP5.outgoers("edge")[0].target().id() !== "p2") {
  throw new Error("Folded p5 component node not connected between p4 and p2");
}

console.log("ALL_BIPARTITE_AND_PYTHON_CHECKS_PASSED");
"""
        proc = subprocess.run(
            [node_bin, "-e", test_script],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            proc.returncode,
            0,
            f"Node verification failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}",
        )
        self.assertIn("ALL_BIPARTITE_AND_PYTHON_CHECKS_PASSED", proc.stdout)

    def test_choice_reduction_on_split_place(self):
        """Verifies Idea B Choice Reduction on split places, ProM weights, and component-local unfold."""
        node_bin = shutil.which("node")
        if not node_bin:
            self.skipTest("node binary not found on PATH")

        test_script = """
const cytoscape = require("./code2petri/viewer/vendor/cytoscape.min.js");
const { LiveFoldReductionEngine } = require("./code2petri/viewer/prototype/reduction_engine.js");

global.window = {};
require("./code2petri/viewer/prototype/sample_data.js");

// 1. Synthetic Atomic Choice Test Net
const elements = [
  { group: "nodes", data: { id: "p_split", label: "p_split", initial_tokens: 0 }, classes: "place" },
  { group: "nodes", data: { id: "p_join", label: "p_join", initial_tokens: 0 }, classes: "place" },
  { group: "nodes", data: { id: "t_a", label: "branch_A", tau: 2.0 }, classes: "transition" },
  { group: "nodes", data: { id: "t_b", label: "branch_B", tau: 3.0 }, classes: "transition" },
  { group: "edges", data: { id: "e1", source: "p_split", target: "t_a" }, classes: "arc" },
  { group: "edges", data: { id: "e2", source: "t_a", target: "p_join" }, classes: "arc" },
  { group: "edges", data: { id: "e3", source: "p_split", target: "t_b" }, classes: "arc" },
  { group: "edges", data: { id: "e4", source: "t_b", target: "p_join" }, classes: "arc" }
];

const cy = cytoscape({ elements });
const engine = new LiveFoldReductionEngine(cy);

if (engine.calculateSMScore() !== 5.0) {
  throw new Error("Initial SM score should be 5.0, got " + engine.calculateSMScore());
}

const pSplit = cy.getElementById("p_split");
const choiceCheck = engine.detectChoiceCandidates(pSplit);
if (!choiceCheck.ok || choiceCheck.bundles.length !== 1) {
  throw new Error("Choice detection failed on p_split: " + choiceCheck.reason);
}

// Execute Choice Fold on p_split:
// sum_tau = 2.0 + 3.0 = 5.0
// tau_new = 1.5 * 5.0 = 7.5
// omega = 1.0 * (5.0 * 0.5) = 2.5
// New SM score = 5.0 + 2.5 = 7.5
const foldRes = engine.executeChoiceContraction(pSplit);
if (!foldRes.success) {
  throw new Error("Choice contraction failed: " + foldRes.message);
}

if (engine.calculateSMScore() !== 7.5) {
  throw new Error("Expected SM score 7.5 after choice fold, got " + engine.calculateSMScore());
}

const cNode = cy.getElementById(foldRes.step.opaqueId);
if (cNode.data("tau") !== 7.5 || cNode.data("omega") !== 2.5) {
  throw new Error("cNode weights incorrect: tau=" + cNode.data("tau") + " omega=" + cNode.data("omega"));
}

if (cNode.incomers("edge")[0].source().id() !== "p_split" || cNode.outgoers("edge")[0].target().id() !== "p_join") {
  throw new Error("cNode arcs not properly routed between p_split and p_join");
}

// Test Component-Local Unfold on Choice Component
const unfoldRes = engine.executeComponentLocalUnfold(cNode);
if (!unfoldRes.success) {
  throw new Error("Component-Local Unfold failed: " + unfoldRes.message);
}

if (engine.calculateSMScore() !== 5.0) {
  throw new Error("SM score not restored to 5.0 after unfold, got " + engine.calculateSMScore());
}

if (cy.getElementById("t_a").length === 0 || cy.getElementById("t_b").length === 0) {
  throw new Error("Parallel transitions t_a / t_b not restored after unfold");
}

// 2. Choice Reduction in real python_mixed_pipeline AST sample
const pySample = window.PROTOTYPE_SAMPLES["python_mixed_pipeline"];
const pyElements = [];
(pySample.compounds || []).forEach(c => {
  pyElements.push({ group: "nodes", data: { id: c.id, label: c.label, is_compound: true }, classes: "compound" });
});
pySample.places.forEach(p => {
  pyElements.push({ group: "nodes", data: { id: p.id, label: p.label, initial_tokens: p.initial_tokens || 0, parent: p.parent }, classes: "place" });
});
pySample.transitions.forEach(t => {
  pyElements.push({ group: "nodes", data: { id: t.id, label: t.label, tau: t.tau || 1.0, parent: t.parent }, classes: "transition" });
});
pySample.arcs.forEach((a, i) => {
  pyElements.push({ group: "edges", data: { id: "a" + i, source: a.source, target: a.target, weight: a.weight || 1 }, classes: "arc" });
});

const pyCy = cytoscape({ elements: pyElements });
const pyEngine = new LiveFoldReductionEngine(pyCy);

// Collapse helper_calc internal place
pyEngine.executeSinglePlaceContraction(pyCy.getElementById("p_helper_mid"));
// Collapse if-branch entry place p5
pyEngine.executeSinglePlaceContraction(pyCy.getElementById("p5"));
// Collapse else-branch entry place p6
pyEngine.executeSinglePlaceContraction(pyCy.getElementById("p6"));

// Now p4 has two parallel branches (c_02 and c_03) both targeting p2!
const p4 = pyCy.getElementById("p4");
const p4Choice = pyEngine.detectChoiceCandidates(p4);
if (!p4Choice.ok) {
  throw new Error("p4 should be choice contractible after collapsing both branches: " + p4Choice.reason);
}

const p4Fold = pyEngine.executeChoiceContraction(p4);
if (!p4Fold.success) {
  throw new Error("Failed to fold choice on p4: " + p4Fold.message);
}

const cChoice = pyCy.getElementById(p4Fold.step.opaqueId);
if (cChoice.incomers("edge")[0].source().id() !== "p4" || cChoice.outgoers("edge")[0].target().id() !== "p2") {
  throw new Error("Choice component cChoice not connected between p4 and p2");
}

// Verify that after choice contraction, p4 immediately becomes Sequence Foldable
const p4SeqCheck = pyEngine.canContractPlace(p4);
if (!p4SeqCheck.ok) {
  throw new Error("p4 must become sequence foldable after choice fold, got: " + p4SeqCheck.reason);
}

// Execute single-place contraction on p4
const p4SeqFold = pyEngine.executeSinglePlaceContraction(p4);
if (!p4SeqFold.success) {
  throw new Error("Failed to contract p4 after choice fold: " + p4SeqFold.message);
}

console.log("ALL_CHOICE_REDUCTION_CHECKS_PASSED");
"""
        proc = subprocess.run(
            [node_bin, "-e", test_script],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            proc.returncode,
            0,
            f"Node verification failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}",
        )
        self.assertIn("ALL_CHOICE_REDUCTION_CHECKS_PASSED", proc.stdout)

    def test_while_loop_reduction(self):
        """Verifies While Loop Reduction (ProM foldWhile), ProM weights, local unfold, and AST pipeline reduction."""
        node_bin = shutil.which("node")
        if not node_bin:
            self.skipTest("node binary not found on PATH")

        test_script = """
const cytoscape = require("./code2petri/viewer/vendor/cytoscape.min.js");
const { LiveFoldReductionEngine } = require("./code2petri/viewer/prototype/reduction_engine.js");

global.window = {};
require("./code2petri/viewer/prototype/sample_data.js");

// 1. Synthetic Atomic While Loop Test Net
// p_in -> t_src -> p_loop -> t_snk -> p_out
//                  p_loop -> t_loop -> p_loop
const elements = [
  { group: "nodes", data: { id: "p_in", label: "p_in", initial_tokens: 1 }, classes: "place" },
  { group: "nodes", data: { id: "p_loop", label: "p_loop", initial_tokens: 0 }, classes: "place" },
  { group: "nodes", data: { id: "p_out", label: "p_out", initial_tokens: 0 }, classes: "place" },
  { group: "nodes", data: { id: "t_src", label: "t_src", tau: 2.0 }, classes: "transition" },
  { group: "nodes", data: { id: "t_loop", label: "t_loop", tau: 3.0 }, classes: "transition" },
  { group: "nodes", data: { id: "t_snk", label: "t_snk", tau: 1.0 }, classes: "transition" },
  { group: "edges", data: { id: "e1", source: "p_in", target: "t_src" }, classes: "arc" },
  { group: "edges", data: { id: "e2", source: "t_src", target: "p_loop" }, classes: "arc" },
  { group: "edges", data: { id: "e3", source: "p_loop", target: "t_loop" }, classes: "arc" },
  { group: "edges", data: { id: "e4", source: "t_loop", target: "p_loop" }, classes: "arc" },
  { group: "edges", data: { id: "e5", source: "p_loop", target: "t_snk" }, classes: "arc" },
  { group: "edges", data: { id: "e6", source: "t_snk", target: "p_out" }, classes: "arc" }
];

const cy = cytoscape({ elements });
const engine = new LiveFoldReductionEngine(cy);

// Initial SM: tau(t_src) + tau(t_loop) + tau(t_snk) = 2.0 + 3.0 + 1.0 = 6.0
if (engine.calculateSMScore() !== 6.0) {
  throw new Error("Expected initial SM score 6.0, got " + engine.calculateSMScore());
}

const pLoop = cy.getElementById("p_loop");
const whileCheck = engine.detectWhileCandidates(pLoop);
if (!whileCheck.ok) {
  throw new Error("While detection failed on p_loop: " + whileCheck.reason);
}

// ProM formula:
// tau_new = tau(t_src) + tau(t_snk) + 2.0 * tau(t_loop) = 2.0 + 1.0 + 2.0 * 3.0 = 9.0
// omega = 1.0 * tau(t_loop) = 3.0
if (whileCheck.tau_new !== 9.0 || whileCheck.omega !== 3.0) {
  throw new Error(`Weights mismatch: tau_new=${whileCheck.tau_new} (expected 9.0), omega=${whileCheck.omega} (expected 3.0)`);
}

const foldRes = engine.executeWhileContraction(pLoop);
if (!foldRes.success) {
  throw new Error("While contraction failed: " + foldRes.message);
}

if (engine.calculateSMScore() !== 9.0) {
  throw new Error("Expected SM score 9.0 after while fold, got " + engine.calculateSMScore());
}

const cNode = cy.getElementById(foldRes.step.opaqueId);
if (cNode.data("tau") !== 9.0 || cNode.data("omega") !== 3.0) {
  throw new Error("cNode weights incorrect: tau=" + cNode.data("tau") + " omega=" + cNode.data("omega"));
}

if (cNode.incomers("edge")[0].source().id() !== "p_in" || cNode.outgoers("edge")[0].target().id() !== "p_out") {
  throw new Error("cNode arcs not properly routed between p_in and p_out");
}

// Test Component-Local Unfold on While Component
const unfoldRes = engine.executeComponentLocalUnfold(cNode);
if (!unfoldRes.success) {
  throw new Error("Component-Local Unfold on while failed: " + unfoldRes.message);
}

if (engine.calculateSMScore() !== 6.0) {
  throw new Error("SM score not restored to 6.0 after unfold, got " + engine.calculateSMScore());
}

if (cy.getElementById("p_loop").length === 0 || cy.getElementById("t_loop").length === 0 ||
    cy.getElementById("t_src").length === 0 || cy.getElementById("t_snk").length === 0) {
  throw new Error("Nodes p_loop / t_loop / t_src / t_snk not restored after unfold");
}

// 2. Real python_mixed_pipeline AST sample end-to-end reduction
const pySample = window.PROTOTYPE_SAMPLES["python_mixed_pipeline"];
const pyElements = [];
(pySample.compounds || []).forEach(c => {
  pyElements.push({ group: "nodes", data: { id: c.id, label: c.label, is_compound: true }, classes: "compound" });
});
pySample.places.forEach(p => {
  pyElements.push({ group: "nodes", data: { id: p.id, label: p.label, initial_tokens: p.initial_tokens || 0, parent: p.parent }, classes: "place" });
});
pySample.transitions.forEach(t => {
  pyElements.push({ group: "nodes", data: { id: t.id, label: t.label, tau: t.tau || 1.0, parent: t.parent }, classes: "transition" });
});
pySample.arcs.forEach((a, i) => {
  pyElements.push({ group: "edges", data: { id: "a" + i, source: a.source, target: a.target, weight: a.weight || 1 }, classes: "arc" });
});

const pyCy = cytoscape({ elements: pyElements });
const pyEngine = new LiveFoldReductionEngine(pyCy);

// Before collapsing loop body, p2 is a pending loop head
const p2 = pyCy.getElementById("p2");
if (!pyEngine.isPendingLoopHead(p2)) {
  throw new Error("p2 should be detected as a pending loop head before body is reduced");
}
if (pyEngine.detectWhileCandidates(p2).ok) {
  throw new Error("p2 should NOT be while contractible before body is collapsed");
}

// Collapse helper_calc internal place
pyEngine.executeSinglePlaceContraction(pyCy.getElementById("p_helper_mid"));
// Collapse if-branch entry place p5
pyEngine.executeSinglePlaceContraction(pyCy.getElementById("p5"));
// Collapse else-branch entry place p6
pyEngine.executeSinglePlaceContraction(pyCy.getElementById("p6"));
// Collapse choice branches on p4
pyEngine.executeChoiceContraction(pyCy.getElementById("p4"));
// Collapse sequence on p4 into atomic self-loop on p2!
pyEngine.executeSinglePlaceContraction(pyCy.getElementById("p4"));

// Now p2 has an atomic self-loop and MUST be while contractible!
const p2WhileCheck = pyEngine.detectWhileCandidates(p2);
if (!p2WhileCheck.ok) {
  throw new Error("p2 should now be while contractible after loop body collapsed: " + p2WhileCheck.reason);
}

const p2Fold = pyEngine.executeWhileContraction(p2);
if (!p2Fold.success) {
  throw new Error("Failed to fold while loop on p2: " + p2Fold.message);
}

const cWhile = pyCy.getElementById(p2Fold.step.opaqueId);
if (cWhile.incomers("edge")[0].source().id() !== "p1" || cWhile.outgoers("edge")[0].target().id() !== "p3") {
  throw new Error("cWhile not connected between p1 and p3");
}

// Now p1 is sequence contractible!
const p1 = pyCy.getElementById("p1");
const p1SeqCheck = pyEngine.canContractPlace(p1);
if (!p1SeqCheck.ok) {
  throw new Error("p1 should be sequence contractible after while loop folded: " + p1SeqCheck.reason);
}

const p1Fold = pyEngine.executeSinglePlaceContraction(p1);
if (!p1Fold.success) {
  throw new Error("Failed to fold sequence on p1: " + p1Fold.message);
}

console.log("ALL_WHILE_LOOP_CHECKS_PASSED");
"""
        proc = subprocess.run(
            [node_bin, "-e", test_script],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            proc.returncode,
            0,
            f"Node verification failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}",
        )
        self.assertIn("ALL_WHILE_LOOP_CHECKS_PASSED", proc.stdout)


if __name__ == "__main__":
    unittest.main()


