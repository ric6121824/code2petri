/**
 * Phase 2.7 Live Fold Reduction Engine
 * Client-side JavaScript implementation of ProM Single-Place Contraction,
 * Transition Weight (tau) tracking, Component Penalty (omega),
 * Collapsed Compound States, and Component-Local Unfold.
 */

class LiveFoldReductionEngine {
  constructor(cy, options = {}) {
    this.cy = cy;
    this.stepCounter = 0;
    this.history = [];
    this.cfg = {
      sequence: 1.0,
      choice: 1.0,
      loop: 3.0
    };
    this.onStateChange = options.onStateChange || null;
  }

  /**
   * Calculates the overall Structuredness Metric (SM) score from current visible transitions.
   */
  calculateSMScore() {
    let sm = 0.0;
    this.cy.nodes('.transition').forEach(t => {
      const tau = parseFloat(t.data('tau'));
      sm += isNaN(tau) ? 1.0 : tau;
    });
    return parseFloat(sm.toFixed(2));
  }

  /**
   * Returns true if the function compound container has been folded down to a single component node.
   * @param {string} compoundId
   * @returns {boolean}
   */
  isFunctionFoldedIntoSingleComponent(compoundIdOrNode) {
    if (!compoundIdOrNode) return false;
    const compoundId = typeof compoundIdOrNode === 'string' ? compoundIdOrNode : (compoundIdOrNode.id ? compoundIdOrNode.id() : null);
    if (!compoundId) return false;
    const compoundNode = this.cy.getElementById(compoundId);
    if (!compoundNode || compoundNode.length === 0) return false;

    // Check if explicitly in collapsed-compound state
    if (compoundNode.hasClass('collapsed-compound') || compoundNode.data('collapsed_opaque_id')) {
      return true;
    }

    // Otherwise check remaining children inside this compound
    const children = this.cy.nodes().filter(n => n.data('parent') === compoundId);
    if (children.length === 1) {
      const child = children[0];
      // Must be an opaque transition (component)
      if (child.data('opaque') === true || child.hasClass('component')) {
        return true;
      }
    }

    return false;
  }

  /**
   * Checks if an intermediate place satisfies ProM Single-Place Contraction (1 -> 1 -> 1).
   * @param {cytoscape.NodeSingular} placeNode
   * @returns {{ ok: boolean, reason?: string, t_src?: any, t_snk?: any }}
   */
  canContractPlace(placeNode) {
    if (!placeNode || !placeNode.hasClass('place')) {
      return { ok: false, reason: "Target is not a Petri net place." };
    }

    const tokens = parseInt(placeNode.data('initial_tokens') || 0, 10);
    if (tokens > 0) {
      return { ok: false, reason: "Cannot contract marked start/source places (tokens > 0)." };
    }

    const inArcs = placeNode.incomers('edge');
    const outArcs = placeNode.outgoers('edge');

    if (inArcs.length !== 1 || outArcs.length !== 1) {
      return {
        ok: false,
        reason: `Single-Place Contraction requires exactly 1 input and 1 output arc (has ${inArcs.length} in, ${outArcs.length} out).`
      };
    }

    const t_src = inArcs[0].source();
    const t_snk = outArcs[0].target();

    if (!t_src.hasClass('transition') || !t_snk.hasClass('transition')) {
      return { ok: false, reason: "Connected nodes must both be transitions to preserve bipartite structure." };
    }

    if (t_src.id() === t_snk.id()) {
      return { ok: false, reason: "Self-loop transition detected; requires loop reduction rule." };
    }

    // Source transition must only output to this place
    const t_src_out = t_src.outgoers('edge');
    if (t_src_out.length !== 1) {
      return {
        ok: false,
        reason: `Preceding transition '${t_src.data('label')}' branches to multiple places (${t_src_out.length}).`
      };
    }

    // Sink transition must only input from this place
    const t_snk_in = t_snk.incomers('edge');
    if (t_snk_in.length !== 1) {
      return {
        ok: false,
        reason: `Succeeding transition '${t_snk.data('label')}' has multiple inputs (${t_snk_in.length}).`
      };
    }

    // Function boundary constraint:
    // Do not allow a place to fold when one of its neighbor transitions belongs to another function
    // unless that function is folded into a single component node.
    const parentPlace = placeNode.data('parent') || null;
    const parentSrc = t_src.data('parent') || null;
    const parentSnk = t_snk.data('parent') || null;

    if (parentSrc !== parentSnk || (parentPlace !== null && (parentPlace !== parentSrc || parentPlace !== parentSnk))) {
      // Check if t_src belongs to another function
      if (parentSrc !== null && (parentSrc !== parentSnk || parentSrc !== parentPlace)) {
        if (!this.isFunctionFoldedIntoSingleComponent(parentSrc)) {
          const fnNode = this.cy.getElementById(parentSrc);
          const fnName = (fnNode && fnNode.length > 0)
            ? (fnNode.data('function_name') || fnNode.data('label') || parentSrc)
            : parentSrc;
          return {
            ok: false,
            reason: `Preceding transition '${t_src.data('label')}' belongs to function '${fnName}', which is not yet folded into a single component node.`
          };
        }
      }

      // Check if t_snk belongs to another function
      if (parentSnk !== null && (parentSnk !== parentSrc || parentSnk !== parentPlace)) {
        if (!this.isFunctionFoldedIntoSingleComponent(parentSnk)) {
          const fnNode = this.cy.getElementById(parentSnk);
          const fnName = (fnNode && fnNode.length > 0)
            ? (fnNode.data('function_name') || fnNode.data('label') || parentSnk)
            : parentSnk;
          return {
            ok: false,
            reason: `Succeeding transition '${t_snk.data('label')}' belongs to function '${fnName}', which is not yet folded into a single component node.`
          };
        }
      }
    }

    return { ok: true, t_src, t_snk, inArc: inArcs[0], outArc: outArcs[0] };
  }

  /**
   * Executes a Single-Place Contraction on the given place node.
   * @param {cytoscape.NodeSingular} placeNode
   * @returns {{ success: boolean, message: string, step?: any }}
   */
  executeSinglePlaceContraction(placeNode) {
    const check = this.canContractPlace(placeNode);
    if (!check.ok) {
      return { success: false, message: check.reason };
    }

    const { t_src, t_snk, inArc, outArc } = check;
    this.stepCounter++;
    const stepNum = this.stepCounter;
    const opaqueId = 'c_' + String(stepNum).padStart(2, '0');

    // 1. Calculate weights
    const tauSrc = parseFloat(t_src.data('tau') !== undefined ? t_src.data('tau') : 1.0);
    const tauSnk = parseFloat(t_snk.data('tau') !== undefined ? t_snk.data('tau') : 1.0);
    const omega = this.cfg.sequence; // 1.0
    const accumulatedTau = parseFloat((omega + tauSrc + tauSnk).toFixed(2));

    // 2. Discover parent compound container
    const parentSrc = t_src.data('parent') || null;
    const parentSnk = t_snk.data('parent') || null;
    let parentId = null;
    if (parentSrc && parentSnk && parentSrc === parentSnk) {
      parentId = parentSrc;
    } else {
      parentId = null; // Cross-boundary fold merges into outer scope
    }

    // 3. Serialize boundary arcs and consumed subgraph BEFORE any mutations occur
    const boundaryInArcs = t_src.incomers('edge').map(edge => ({
      sourceId: edge.source().id(),
      targetId: opaqueId,
      originalTargetId: t_src.id(),
      weight: edge.data('weight') || 1,
      classes: edge.classes().join(' ')
    }));

    const boundaryOutArcs = t_snk.outgoers('edge').map(edge => ({
      sourceId: opaqueId,
      originalSourceId: t_snk.id(),
      targetId: edge.target().id(),
      weight: edge.data('weight') || 1,
      classes: edge.classes().join(' ')
    }));

    const consumedNodes = [
      { group: 'nodes', data: Object.assign({}, placeNode.data()), classes: placeNode.classes().join(' '), position: Object.assign({}, placeNode.position()) },
      { group: 'nodes', data: Object.assign({}, t_src.data()), classes: t_src.classes().join(' '), position: Object.assign({}, t_src.position()) },
      { group: 'nodes', data: Object.assign({}, t_snk.data()), classes: t_snk.classes().join(' '), position: Object.assign({}, t_snk.position()) }
    ];

    const consumedInternalEdges = [
      { group: 'edges', data: Object.assign({}, inArc.data()), classes: inArc.classes().join(' ') },
      { group: 'edges', data: Object.assign({}, outArc.data()), classes: outArc.classes().join(' ') }
    ];

    // Check if any compound container has all its children consumed by this cross-boundary fold
    const consumedCompounds = [];
    [parentSrc, parentSnk].forEach(pCompId => {
      if (pCompId && pCompId !== parentId) {
        const pNode = this.cy.getElementById(pCompId);
        const remaining = this.cy.nodes().filter(n =>
          n.data('parent') === pCompId &&
          n.id() !== t_src.id() &&
          n.id() !== t_snk.id() &&
          n.id() !== placeNode.id()
        );
        if (remaining.length === 0 && pNode.length > 0) {
          consumedCompounds.push({
            group: 'nodes',
            data: Object.assign({}, pNode.data()),
            classes: pNode.classes().join(' '),
            position: Object.assign({}, pNode.position())
          });
        }
      }
    });

    const consumedSubgraph = {
      stepNumber: stepNum,
      opaqueId: opaqueId,
      componentType: 'sequence',
      omega: omega,
      tau: accumulatedTau,
      consumedPlaceId: placeNode.id(),
      consumedTransIds: [t_src.id(), t_snk.id()],
      parentCompound: parentId,
      consumedCompounds: consumedCompounds,
      nodes: consumedNodes,
      internalEdges: consumedInternalEdges,
      boundaryInArcs: boundaryInArcs,
      boundaryOutArcs: boundaryOutArcs
    };

    // 4. Remove consumed elements and emptied compound containers
    consumedCompounds.forEach(c => {
      const pNode = this.cy.getElementById(c.data.id);
      if (pNode.inside()) this.cy.remove(pNode);
    });
    if (inArc.inside()) this.cy.remove(inArc);
    if (outArc.inside()) this.cy.remove(outArc);
    if (placeNode.inside()) this.cy.remove(placeNode);
    if (t_src.inside()) this.cy.remove(t_src);
    if (t_snk.inside()) this.cy.remove(t_snk);

    // 5. Create new opaque transition node
    const newNodeData = {
      id: opaqueId,
      label: opaqueId,
      raw_label: `${t_src.data('label')} ; ${t_snk.data('label')}`,
      type: 'Opaque Transition (Sequence)',
      component_type: 'sequence',
      opaque: true,
      step_number: stepNum,
      tau: accumulatedTau,
      omega: omega,
      consumedSubgraph: consumedSubgraph
    };
    if (parentId) {
      newNodeData.parent = parentId;
    }

    const opaqueNode = this.cy.add({
      group: 'nodes',
      data: newNodeData,
      classes: 'transition opaque component'
    });

    // 6. Connect boundary arcs to new opaque transition
    boundaryInArcs.forEach((bArc, idx) => {
      this.cy.add({
        group: 'edges',
        data: {
          id: `arc_in_${opaqueId}_${idx}`,
          source: bArc.sourceId,
          target: opaqueId,
          weight: bArc.weight
        },
        classes: 'arc'
      });
    });

    boundaryOutArcs.forEach((bArc, idx) => {
      this.cy.add({
        group: 'edges',
        data: {
          id: `arc_out_${opaqueId}_${idx}`,
          source: opaqueId,
          target: bArc.targetId,
          weight: bArc.weight
        },
        classes: 'arc'
      });
    });

    // 7. Check if parent compound node has now reached Collapsed Compound State
    let collapsedCompound = null;
    if (parentId) {
      const parentNode = this.cy.getElementById(parentId);
      if (parentNode && parentNode.length > 0) {
        const remainingChildren = this.cy.nodes().filter(n => n.data('parent') === parentId);
        // If the only child is this newly created opaque transition
        if (remainingChildren.length === 1 && remainingChildren[0].id() === opaqueId) {
          parentNode.addClass('collapsed-compound');
          const fnName = parentNode.data('function_name') || parentNode.data('label') || 'function';
          parentNode.data('collapsed_label', `${fnName} (${opaqueId})`);
          parentNode.data('collapsed_opaque_id', opaqueId);
          collapsedCompound = parentNode;
        }
      }
    }

    const runningSm = this.calculateSMScore();

    const stepRecord = {
      stepNumber: stepNum,
      opaqueId: opaqueId,
      componentType: 'Single-Place Contraction',
      consumedPlaceId: placeNode.id(),
      consumedTransLabels: [t_src.data('label'), t_snk.data('label')],
      omega: omega,
      tau: accumulatedTau,
      runningSm: runningSm,
      parentCompoundId: parentId,
      isCompoundCollapsed: Boolean(collapsedCompound),
      timestamp: new Date().toLocaleTimeString()
    };

    this.history.push(stepRecord);

    if (this.onStateChange) {
      this.onStateChange({
        action: 'fold',
        step: stepRecord,
        smScore: runningSm,
        nodeCount: this.cy.nodes().length,
        edgeCount: this.cy.edges().length
      });
    }

    return {
      success: true,
      message: `Folded place '${placeNode.id()}' into opaque transition '${opaqueId}' (ω=${omega}, τ=${accumulatedTau}).`,
      step: stepRecord,
      node: opaqueNode
    };
  }

  /**
   * Detects parallel choice candidate transitions originating from this place.
   * A valid choice bundle consists of >= 2 transitions that:
   *   - Have in-degree 1 (only from placeNode)
   *   - Have out-degree 1 (each targeting the exact same sink place p_snk)
   *   - p_snk !== placeNode (no self-loops)
   *   - Respect function boundary encapsulation
   * @param {cytoscape.NodeSingular} placeNode
   * @returns {{ ok: boolean, reason?: string, bundles?: Array<{ targetPlace: any, targetPlaceId: string, transitions: any[] }> }}
   */
  detectChoiceCandidates(placeNode) {
    if (!placeNode || !placeNode.hasClass('place')) {
      return { ok: false, reason: "Target is not a Petri net place." };
    }

    const tokens = parseInt(placeNode.data('initial_tokens') || 0, 10);
    if (tokens > 0) {
      return { ok: false, reason: "Cannot contract marked start/source places (tokens > 0)." };
    }

    const outArcs = placeNode.outgoers('edge');
    if (outArcs.length < 2) {
      return { ok: false, reason: `Choice reduction requires >= 2 outgoing branches (has ${outArcs.length}).` };
    }

    // Group outgoing transitions by their unique target place
    const targetGroups = new Map(); // targetPlaceId -> { targetPlace, targetPlaceId, transitions: [] }

    outArcs.forEach(edge => {
      const t = edge.target();
      if (!t.hasClass('transition')) return;

      // Transition must have exactly 1 input (from this place) and 1 output
      const inArcs = t.incomers('edge');
      const outArcsT = t.outgoers('edge');
      if (inArcs.length !== 1 || outArcsT.length !== 1) return;

      const p_snk = outArcsT[0].target();
      if (!p_snk.hasClass('place')) return;
      if (p_snk.id() === placeNode.id()) return; // skip self-loops

      // Function boundary encapsulation check:
      const parentT = t.data('parent') || null;
      const parentPlace = placeNode.data('parent') || null;
      if (parentT && parentT !== parentPlace) {
        if (!this.isFunctionFoldedIntoSingleComponent(parentT)) {
          return;
        }
      }

      const pSnkParent = p_snk.data('parent') || null;
      if (parentT && parentT !== pSnkParent) {
        if (!this.isFunctionFoldedIntoSingleComponent(parentT)) {
          return;
        }
      }

      const targetId = p_snk.id();
      if (!targetGroups.has(targetId)) {
        targetGroups.set(targetId, {
          targetPlace: p_snk,
          targetPlaceId: targetId,
          transitions: []
        });
      }
      targetGroups.get(targetId).transitions.push(t);
    });

    const validBundles = [];
    for (const group of targetGroups.values()) {
      if (group.transitions.length >= 2) {
        validBundles.push(group);
      }
    }

    if (validBundles.length === 0) {
      return { ok: false, reason: "No parallel transitions converging on a shared sink place." };
    }

    return { ok: true, bundles: validBundles };
  }

  /**
   * Executes a Choice Contraction on the given place node, fusing parallel outgoing transitions.
   * @param {cytoscape.NodeSingular} placeNode
   * @param {number} [bundleIndex=0]
   * @returns {{ success: boolean, message: string, step?: any, node?: any }}
   */
  executeChoiceContraction(placeNode, bundleIndex = 0) {
    const check = this.detectChoiceCandidates(placeNode);
    if (!check.ok) {
      return { success: false, message: check.reason };
    }

    const bundle = check.bundles[bundleIndex || 0];
    const targetPlace = bundle.targetPlace;
    const transitions = bundle.transitions;

    this.stepCounter++;
    const stepNum = this.stepCounter;
    const opaqueId = 'c_' + String(stepNum).padStart(2, '0');

    // 1. Calculate weights per ProM Choice rule:
    // sum_tau = sum of all branches
    // tau_new = 1.5 * sum_tau
    // omega = cfg.choice * (sum_tau * 0.5)
    let sumTau = 0.0;
    transitions.forEach(t => {
      const val = parseFloat(t.data('tau') !== undefined ? t.data('tau') : 1.0);
      sumTau += val;
    });

    const omega = parseFloat((this.cfg.choice * (sumTau * 0.5)).toFixed(2));
    const accumulatedTau = parseFloat((1.5 * sumTau).toFixed(2));

    // 2. Discover parent compound container
    const firstParent = transitions[0].data('parent') || null;
    const allSameParent = transitions.every(t => (t.data('parent') || null) === firstParent);
    let parentId = null;
    if (allSameParent && firstParent) {
      parentId = firstParent;
    } else if (placeNode.data('parent') && placeNode.data('parent') === targetPlace.data('parent')) {
      parentId = placeNode.data('parent');
    }

    // 3. Serialize consumed elements for Component-Local Unfold
    const consumedNodes = transitions.map(t => ({
      group: 'nodes',
      data: Object.assign({}, t.data()),
      classes: t.classes().join(' '),
      position: Object.assign({}, t.position())
    }));

    const consumedInternalEdges = [];
    transitions.forEach(t => {
      const inEdge = t.incomers('edge')[0];
      const outEdge = t.outgoers('edge')[0];
      consumedInternalEdges.push({
        group: 'edges',
        data: Object.assign({}, inEdge.data()),
        classes: inEdge.classes().join(' ')
      });
      consumedInternalEdges.push({
        group: 'edges',
        data: Object.assign({}, outEdge.data()),
        classes: outEdge.classes().join(' ')
      });
    });

    const transLabels = transitions.map(t => t.data('label') || t.id()).join(' ⊕ ');

    const consumedSubgraph = {
      stepNumber: stepNum,
      opaqueId: opaqueId,
      componentType: 'choice',
      omega: omega,
      tau: accumulatedTau,
      consumedPlaceId: null, // placeNode is preserved in choice fold
      sourcePlaceId: placeNode.id(),
      targetPlaceId: targetPlace.id(),
      consumedTransIds: transitions.map(t => t.id()),
      parentCompound: parentId,
      nodes: consumedNodes,
      internalEdges: consumedInternalEdges,
      boundaryInArcs: [],
      boundaryOutArcs: []
    };

    // 4. Remove consumed transitions and their incident edges
    transitions.forEach(t => {
      t.connectedEdges().forEach(e => {
        if (e.inside()) this.cy.remove(e);
      });
      if (t.inside()) this.cy.remove(t);
    });

    // 5. Create new opaque transition node
    const newNodeData = {
      id: opaqueId,
      label: opaqueId,
      raw_label: transLabels,
      type: 'Opaque Transition (Choice)',
      component_type: 'choice',
      opaque: true,
      step_number: stepNum,
      tau: accumulatedTau,
      omega: omega,
      consumedSubgraph: consumedSubgraph
    };
    if (parentId) {
      newNodeData.parent = parentId;
    }

    const opaqueNode = this.cy.add({
      group: 'nodes',
      data: newNodeData,
      classes: 'transition opaque component'
    });

    // 6. Connect source place -> opaque transition -> target place
    this.cy.add({
      group: 'edges',
      data: {
        id: `arc_choice_in_${opaqueId}`,
        source: placeNode.id(),
        target: opaqueId,
        weight: 1
      },
      classes: 'arc'
    });

    this.cy.add({
      group: 'edges',
      data: {
        id: `arc_choice_out_${opaqueId}`,
        source: opaqueId,
        target: targetPlace.id(),
        weight: 1
      },
      classes: 'arc'
    });

    // 7. Check if parent compound node has reached Collapsed Compound State
    let collapsedCompound = null;
    if (parentId) {
      const parentNode = this.cy.getElementById(parentId);
      if (parentNode && parentNode.length > 0) {
        const remainingChildren = this.cy.nodes().filter(n => n.data('parent') === parentId);
        if (remainingChildren.length === 1 && remainingChildren[0].id() === opaqueId) {
          parentNode.addClass('collapsed-compound');
          const fnName = parentNode.data('function_name') || parentNode.data('label') || 'function';
          parentNode.data('collapsed_label', `${fnName} (${opaqueId})`);
          parentNode.data('collapsed_opaque_id', opaqueId);
          collapsedCompound = parentNode;
        }
      }
    }

    const runningSm = this.calculateSMScore();

    const stepRecord = {
      stepNumber: stepNum,
      opaqueId: opaqueId,
      componentType: 'Choice Reduction',
      sourcePlaceId: placeNode.id(),
      targetPlaceId: targetPlace.id(),
      consumedTransLabels: transitions.map(t => t.data('label')),
      omega: omega,
      tau: accumulatedTau,
      runningSm: runningSm,
      parentCompoundId: parentId,
      isCompoundCollapsed: Boolean(collapsedCompound),
      timestamp: new Date().toLocaleTimeString()
    };

    this.history.push(stepRecord);

    if (this.onStateChange) {
      this.onStateChange({
        action: 'fold',
        step: stepRecord,
        smScore: runningSm,
        nodeCount: this.cy.nodes().length,
        edgeCount: this.cy.edges().length
      });
    }

    return {
      success: true,
      message: `Folded choice transitions [${transLabels}] into '${opaqueId}' (ω=${omega}, τ=${accumulatedTau}).`,
      step: stepRecord,
      node: opaqueNode
    };
  }

  /**
   * Evaluates if a place node is eligible for While Loop Reduction (ProM foldWhile).
   * A valid while loop candidate is an intermediate place p with:
   *   - in_degree == 2 and out_degree == 2, initial_tokens == 0
   *   - exactly 1 shared transition t_loop in presets(p) and postsets(p) (self-loop)
   *   - in_degree(t_loop) == 1 and out_degree(t_loop) == 1
   *   - remaining source transition t_src with out_degree(t_src) == 1
   *   - remaining sink transition t_snk with in_degree(t_snk) == 1
   * @param {cytoscape.NodeSingular} placeNode
   * @returns {{ ok: boolean, reason?: string, place?: any, t_loop?: any, t_src?: any, t_snk?: any, tau_loop?: number, tau_src?: number, tau_snk?: number, omega?: number, tau_new?: number }}
   */
  detectWhileCandidates(placeNode) {
    if (!placeNode || !placeNode.inside || !placeNode.inside()) {
      return { ok: false, reason: "Invalid place node." };
    }
    if (!placeNode.hasClass('place')) {
      return { ok: false, reason: "Target node is not a place." };
    }
    if ((placeNode.data('initial_tokens') || 0) > 0) {
      return { ok: false, reason: "Cannot fold marked place with initial tokens." };
    }

    const inEdges = placeNode.incomers('edge');
    const outEdges = placeNode.outgoers('edge');

    if (inEdges.length !== 2 || outEdges.length !== 2) {
      return {
        ok: false,
        reason: `While Loop Reduction requires a 2-in/2-out place (has ${inEdges.length} in, ${outEdges.length} out).`
      };
    }

    const inTransitions = inEdges.sources('node.transition');
    const outTransitions = outEdges.targets('node.transition');

    if (inTransitions.length !== 2 || outTransitions.length !== 2) {
      return { ok: false, reason: "Connected nodes must all be transitions." };
    }

    // Shared transition: the self-looping transition in both inTransitions and outTransitions
    const inIds = new Set(inTransitions.map(t => t.id()));
    const sharedTransitions = outTransitions.filter(t => inIds.has(t.id()));

    if (sharedTransitions.length !== 1) {
      return {
        ok: false,
        reason: `While Loop requires exactly 1 self-looping transition (found ${sharedTransitions.length}).`
      };
    }

    const t_loop = sharedTransitions[0];
    const t_src = inTransitions.filter(t => t.id() !== t_loop.id())[0];
    const t_snk = outTransitions.filter(t => t.id() !== t_loop.id())[0];

    if (!t_src || !t_snk) {
      return { ok: false, reason: "Could not identify distinct source and sink transitions." };
    }

    // Linearity checks per ProM foldWhile()
    if (t_loop.incomers('edge').length !== 1 || t_loop.outgoers('edge').length !== 1) {
      return { ok: false, reason: `Loop transition '${t_loop.data('label')}' has extra incoming or outgoing arcs.` };
    }
    if (t_src.outgoers('edge').length !== 1) {
      return { ok: false, reason: `Source transition '${t_src.data('label')}' branches to multiple places (${t_src.outgoers('edge').length}).` };
    }
    if (t_snk.incomers('edge').length !== 1) {
      return { ok: false, reason: `Sink transition '${t_snk.data('label')}' has multiple inputs (${t_snk.incomers('edge').length}).` };
    }

    // Function boundary encapsulation check
    const parentPlace = placeNode.data('parent') || null;
    const parentLoop = t_loop.data('parent') || null;
    const parentSrc = t_src.data('parent') || null;
    const parentSnk = t_snk.data('parent') || null;

    const parents = [parentPlace, parentLoop, parentSrc, parentSnk].filter(p => p !== null);
    const uniqueParents = Array.from(new Set(parents));

    if (uniqueParents.length > 1 || (parentPlace !== null && uniqueParents.length > 0)) {
      for (const pId of uniqueParents) {
        if (!this.isFunctionFoldedIntoSingleComponent(pId)) {
          const fnNode = this.cy.getElementById(pId);
          const fnName = (fnNode && fnNode.length > 0)
            ? (fnNode.data('function_name') || fnNode.data('label') || pId)
            : pId;
          return {
            ok: false,
            reason: `Loop involves function '${fnName}', which is not yet folded into a single component node.`
          };
        }
      }
    }

    const tau_loop = parseFloat(t_loop.data('tau') !== undefined ? t_loop.data('tau') : 1.0);
    const tau_src = parseFloat(t_src.data('tau') !== undefined ? t_src.data('tau') : 1.0);
    const tau_snk = parseFloat(t_snk.data('tau') !== undefined ? t_snk.data('tau') : 1.0);

    // ProM Loop penalty:
    // omega = (cfg.loop / 3.0) * tau_loop (when cfg.loop = 3.0, omega = 1.0 * tau_loop)
    // tau_new = tau_src + tau_snk + 2.0 * tau_loop
    const omega = parseFloat(((this.cfg.loop / 3.0) * tau_loop).toFixed(2));
    const tau_new = parseFloat((tau_src + tau_snk + 2.0 * tau_loop).toFixed(2));

    return {
      ok: true,
      place: placeNode,
      t_loop: t_loop,
      t_src: t_src,
      t_snk: t_snk,
      tau_loop: tau_loop,
      tau_src: tau_src,
      tau_snk: tau_snk,
      omega: omega,
      tau_new: tau_new
    };
  }

  /**
   * Detects if a place node acts as a loop head whose internal body is not yet collapsed into a self-loop.
   * @param {cytoscape.NodeSingular} placeNode
   * @returns {boolean}
   */
  isPendingLoopHead(placeNode) {
    if (!placeNode || !placeNode.inside || !placeNode.inside()) return false;
    if (!placeNode.hasClass('place')) return false;

    // Check if there is a multi-hop directed cycle starting from placeNode that returns to placeNode
    const visited = new Set();
    const queue = [];
    placeNode.outgoers('node.transition').forEach(t => {
      const targets = t.outgoers('node.place');
      targets.forEach(p => {
        if (p.id() !== placeNode.id() && !visited.has(p.id())) {
          visited.add(p.id());
          queue.push(p);
        }
      });
    });

    while (queue.length > 0) {
      const current = queue.shift();
      const nextTransitions = current.outgoers('node.transition');
      for (let i = 0; i < nextTransitions.length; i++) {
        const nextPlaces = nextTransitions[i].outgoers('node.place');
        for (let j = 0; j < nextPlaces.length; j++) {
          const np = nextPlaces[j];
          if (np.id() === placeNode.id()) {
            return true;
          }
          if (!visited.has(np.id())) {
            visited.add(np.id());
            queue.push(np);
          }
        }
      }
    }
    return false;
  }

  /**
   * Executes While Loop Reduction on the given place node.
   * @param {cytoscape.NodeSingular} placeNode
   * @returns {{ success: boolean, message: string, step?: any, node?: any }}
   */
  executeWhileContraction(placeNode) {
    const check = this.detectWhileCandidates(placeNode);
    if (!check.ok) {
      return { success: false, message: check.reason };
    }

    const { t_loop, t_src, t_snk, omega, tau_new } = check;

    this.stepCounter++;
    const stepNum = this.stepCounter;
    const opaqueId = 'c_' + String(stepNum).padStart(2, '0');

    // 1. Discover parent compound container
    const parentId = placeNode.data('parent') || t_loop.data('parent') || t_src.data('parent') || t_snk.data('parent') || null;

    // 2. Collect boundary incoming arcs to t_src and boundary outgoing arcs from t_snk
    const boundaryInArcs = [];
    t_src.incomers('edge').forEach(edge => {
      const srcNode = edge.source();
      if (srcNode.id() !== placeNode.id() && srcNode.id() !== t_loop.id()) {
        boundaryInArcs.push({
          edgeId: edge.id(),
          sourceId: srcNode.id(),
          originalTargetId: t_src.id(),
          weight: edge.data('weight') || 1,
          classes: edge.classes().join(' ')
        });
      }
    });

    const boundaryOutArcs = [];
    t_snk.outgoers('edge').forEach(edge => {
      const tgtNode = edge.target();
      if (tgtNode.id() !== placeNode.id() && tgtNode.id() !== t_loop.id()) {
        boundaryOutArcs.push({
          edgeId: edge.id(),
          originalSourceId: t_snk.id(),
          targetId: tgtNode.id(),
          weight: edge.data('weight') || 1,
          classes: edge.classes().join(' ')
        });
      }
    });

    // 3. Serialize consumed elements for Component-Local Unfold
    const consumedNodes = [placeNode, t_loop, t_src, t_snk].map(n => ({
      group: 'nodes',
      data: Object.assign({}, n.data()),
      classes: n.classes().join(' '),
      position: Object.assign({}, n.position())
    }));

    // Internal edges among the 4 consumed nodes
    const consumedInternalEdges = [];
    const consumedNodeIdSet = new Set([placeNode.id(), t_loop.id(), t_src.id(), t_snk.id()]);
    [placeNode, t_loop, t_src, t_snk].forEach(n => {
      n.connectedEdges().forEach(e => {
        if (consumedNodeIdSet.has(e.source().id()) && consumedNodeIdSet.has(e.target().id())) {
          if (!consumedInternalEdges.some(x => x.data.id === e.id())) {
            consumedInternalEdges.push({
              group: 'edges',
              data: Object.assign({}, e.data()),
              classes: e.classes().join(' ')
            });
          }
        }
      });
    });

    const loopLabel = t_loop.data('label') || t_loop.id();
    const rawLabel = `while (${loopLabel})`;

    const consumedSubgraph = {
      stepNumber: stepNum,
      opaqueId: opaqueId,
      componentType: 'while',
      omega: omega,
      tau: tau_new,
      consumedPlaceId: placeNode.id(),
      t_loop_id: t_loop.id(),
      t_src_id: t_src.id(),
      t_snk_id: t_snk.id(),
      parentCompound: parentId,
      nodes: consumedNodes,
      internalEdges: consumedInternalEdges,
      boundaryInArcs: boundaryInArcs,
      boundaryOutArcs: boundaryOutArcs
    };

    // 4. Remove consumed nodes and their connected edges
    [placeNode, t_loop, t_src, t_snk].forEach(n => {
      n.connectedEdges().forEach(e => {
        if (e.inside()) this.cy.remove(e);
      });
      if (n.inside()) this.cy.remove(n);
    });

    // 5. Create new opaque transition node
    const newNodeData = {
      id: opaqueId,
      label: opaqueId,
      raw_label: rawLabel,
      type: 'Opaque Transition (While Loop)',
      component_type: 'while',
      opaque: true,
      step_number: stepNum,
      tau: tau_new,
      omega: omega,
      consumedSubgraph: consumedSubgraph
    };
    if (parentId) {
      newNodeData.parent = parentId;
    }

    const opaqueNode = this.cy.add({
      group: 'nodes',
      data: newNodeData,
      classes: 'transition opaque component'
    });

    // 6. Connect boundary arcs to new opaque transition
    boundaryInArcs.forEach(bArc => {
      this.cy.add({
        group: 'edges',
        data: {
          id: `arc_while_in_${bArc.sourceId}_${opaqueId}`,
          source: bArc.sourceId,
          target: opaqueId,
          weight: bArc.weight
        },
        classes: bArc.classes || 'arc'
      });
    });

    boundaryOutArcs.forEach(bArc => {
      this.cy.add({
        group: 'edges',
        data: {
          id: `arc_while_out_${opaqueId}_${bArc.targetId}`,
          source: opaqueId,
          target: bArc.targetId,
          weight: bArc.weight
        },
        classes: bArc.classes || 'arc'
      });
    });

    // 7. Check collapsed compound state
    let collapsedCompound = null;
    if (parentId) {
      const parentNode = this.cy.getElementById(parentId);
      if (parentNode && parentNode.length > 0) {
        const remainingChildren = this.cy.nodes().filter(n => n.data('parent') === parentId);
        if (remainingChildren.length === 1 && remainingChildren[0].id() === opaqueId) {
          parentNode.addClass('collapsed-compound');
          const fnName = parentNode.data('function_name') || parentNode.data('label') || 'function';
          parentNode.data('collapsed_label', `${fnName} (${opaqueId})`);
          parentNode.data('collapsed_opaque_id', opaqueId);
          collapsedCompound = parentNode;
        }
      }
    }

    const runningSm = this.calculateSMScore();

    const stepRecord = {
      stepNumber: stepNum,
      opaqueId: opaqueId,
      componentType: 'While Loop Reduction',
      placeId: placeNode.id(),
      tLoopLabel: loopLabel,
      tSrcLabel: t_src.data('label') || t_src.id(),
      tSnkLabel: t_snk.data('label') || t_snk.id(),
      omega: omega,
      tau: tau_new,
      runningSm: runningSm,
      parentCompoundId: parentId,
      isCompoundCollapsed: Boolean(collapsedCompound),
      timestamp: new Date().toLocaleTimeString()
    };

    this.history.push(stepRecord);

    if (this.onStateChange) {
      this.onStateChange({
        action: 'fold',
        step: stepRecord,
        smScore: runningSm,
        nodeCount: this.cy.nodes().length,
        edgeCount: this.cy.edges().length
      });
    }

    return {
      success: true,
      message: `Folded while loop around '${placeNode.data('label') || placeNode.id()}' into '${opaqueId}' (ω=${omega}, τ=${tau_new}).`,
      step: stepRecord,
      node: opaqueNode
    };
  }

  /**
   * Restores a folded component locally via Component-Local Unfold.
   * @param {cytoscape.NodeSingular} targetNode
   * @returns {{ success: boolean, message: string }}
   */
  executeComponentLocalUnfold(targetNode) {
    if (!targetNode) {
      return { success: false, message: "No target selected for unfold." };
    }

    let opaqueNode = targetNode;
    let compoundNode = null;

    // If a collapsed compound node was clicked, find its associated opaque transition
    if (targetNode.hasClass('collapsed-compound') || targetNode.data('collapsed_opaque_id')) {
      compoundNode = targetNode;
      const childOpaqueId = targetNode.data('collapsed_opaque_id');
      opaqueNode = this.cy.getElementById(childOpaqueId);
    }

    const consumedSubgraph = opaqueNode.data('consumedSubgraph');
    if (!consumedSubgraph) {
      return { success: false, message: `Node '${opaqueNode.id()}' is not a folded component (no serialized subgraph).` };
    }

    const opaqueId = opaqueNode.id();
    const parentId = consumedSubgraph.parentCompound;

    // 1. Remove incident boundary arcs and the opaque node itself
    opaqueNode.connectedEdges().forEach(edge => this.cy.remove(edge));
    this.cy.remove(opaqueNode);

    // 2. If parent compound was collapsed, un-collapse it
    if (parentId) {
      const parentNode = this.cy.getElementById(parentId);
      if (parentNode && parentNode.length > 0) {
        parentNode.removeClass('collapsed-compound');
        parentNode.removeData('collapsed_opaque_id');
        parentNode.removeData('collapsed_label');
      }
    }

    // 2.5 Re-inject any consumed compound container nodes first
    if (consumedSubgraph.consumedCompounds) {
      consumedSubgraph.consumedCompounds.forEach(cSpec => {
        if (this.cy.getElementById(cSpec.data.id).length === 0) {
          this.cy.add({
            group: 'nodes',
            data: cSpec.data,
            classes: cSpec.classes,
            position: cSpec.position
          });
        }
      });
    }

    // 3. Re-inject consumed nodes
    consumedSubgraph.nodes.forEach(nodeSpec => {
      this.cy.add({
        group: 'nodes',
        data: nodeSpec.data,
        classes: nodeSpec.classes,
        position: nodeSpec.position
      });
    });

    // 4. Re-inject internal arcs
    consumedSubgraph.internalEdges.forEach(edgeSpec => {
      this.cy.add({
        group: 'edges',
        data: edgeSpec.data,
        classes: edgeSpec.classes
      });
    });

    // 5. Re-inject boundary arcs
    consumedSubgraph.boundaryInArcs.forEach(bArc => {
      this.cy.add({
        group: 'edges',
        data: {
          id: `restored_in_${bArc.sourceId}_${bArc.originalTargetId}`,
          source: bArc.sourceId,
          target: bArc.originalTargetId,
          weight: bArc.weight
        },
        classes: bArc.classes || 'arc'
      });
    });

    consumedSubgraph.boundaryOutArcs.forEach(bArc => {
      this.cy.add({
        group: 'edges',
        data: {
          id: `restored_out_${bArc.originalSourceId}_${bArc.targetId}`,
          source: bArc.originalSourceId,
          target: bArc.targetId,
          weight: bArc.weight
        },
        classes: bArc.classes || 'arc'
      });
    });

    // 6. Update step history
    this.history = this.history.filter(h => h.opaqueId !== opaqueId);
    const runningSm = this.calculateSMScore();

    if (this.onStateChange) {
      this.onStateChange({
        action: 'unfold',
        opaqueId: opaqueId,
        smScore: runningSm,
        nodeCount: this.cy.nodes().length,
        edgeCount: this.cy.edges().length
      });
    }

    return {
      success: true,
      message: `Restored sub-net from '${opaqueId}' (Component-Local Unfold).`
    };
  }

  /**
   * Renames a component or transition node directly in Cytoscape.
   */
  renameNode(nodeId, newLabel) {
    const node = this.cy.getElementById(nodeId);
    if (!node || node.length === 0) return false;

    const trimmed = String(newLabel).trim();
    if (!trimmed) return false;

    node.data('label', trimmed);
    node.data('custom_name', trimmed);

    // If inside a collapsed compound, update its banner
    const parentId = node.data('parent');
    if (parentId) {
      const parentNode = this.cy.getElementById(parentId);
      if (parentNode && parentNode.hasClass('collapsed-compound')) {
        const fnName = parentNode.data('function_name') || parentNode.data('label') || 'function';
        parentNode.data('collapsed_label', `${fnName} (${trimmed})`);
      }
    }

    if (this.onStateChange) {
      this.onStateChange({
        action: 'rename',
        nodeId: nodeId,
        newLabel: trimmed
      });
    }

    return true;
  }
}

// Export for browser or node
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { LiveFoldReductionEngine };
} else {
  window.LiveFoldReductionEngine = LiveFoldReductionEngine;
}
