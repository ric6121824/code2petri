/**
 * Fold State Snapshot serialization for the self-contained code2petri viewer.
 */

(function(root, factory) {
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = factory(require('./viewport.js'));
  } else {
    const exports = factory(root);
    if (typeof window !== 'undefined') {
      Object.assign(window, exports);
    } else if (typeof globalThis !== 'undefined') {
      Object.assign(globalThis, exports);
    }
  }
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this), function(viewportModule) {
  const SCHEMA_VERSION = 1;
  const SNAPSHOT_TYPE = 'code2petri-fold-state';

  function _cloneJson(value) {
    if (value === undefined) return null;
    return JSON.parse(JSON.stringify(value));
  }

  function _rememberedCustomNameEntries(engine) {
    if (!engine || !(engine.rememberedCustomNames instanceof Map)) return [];
    return Array.from(engine.rememberedCustomNames.entries()).map(function(entry) {
      return [String(entry[0]), entry[1]];
    });
  }

  /**
   * Captures a versioned Fold State Snapshot without changing graph or UI state.
   *
   * @param {{cy: Object, engine: Object, document: Object}} options
   * @returns {Object}
   */
  function serializeFoldStateSnapshot(options) {
    const opts = options || {};
    const cy = opts.cy;
    const engine = opts.engine;
    if (!cy || !cy.elements || !engine) {
      throw new Error('A Cytoscape graph and Live Fold Reduction engine are required');
    }

    const capture = viewportModule && viewportModule.captureViewport;
    const viewport = typeof capture === 'function'
      ? capture(cy)
      : {
          zoom: typeof cy.zoom === 'function' ? cy.zoom() : 1,
          pan: typeof cy.pan === 'function' ? Object.assign({}, cy.pan()) : { x: 0, y: 0 }
        };

    return {
      schemaVersion: SCHEMA_VERSION,
      snapshotType: SNAPSHOT_TYPE,
      elements: _cloneJson(cy.elements().jsons()),
      engine: {
        stepCounter: Number(engine.stepCounter) || 0,
        cfg: _cloneJson(engine.cfg || {}),
        rememberedCustomNames: _cloneJson(_rememberedCustomNameEntries(engine))
      },
      viewport: _cloneJson(viewport),
      document: _cloneJson(opts.document || {})
    };
  }

  function getFoldStateSnapshotFilename(netTitle) {
    const raw = String(netTitle || '').trim();
    const safeTitle = raw
      .replace(/[<>:"/\\|?*\u0000-\u001f]/g, '_')
      .replace(/[. ]+$/g, '');
    return (safeTitle || 'petri_net') + '_session.json';
  }

  function _invalidSnapshot(reason) {
    throw new Error('Invalid Fold State Snapshot: ' + reason);
  }

  function _isObject(value) {
    return value !== null && typeof value === 'object' && !Array.isArray(value);
  }

  function _requireString(value, description) {
    if (typeof value !== 'string') _invalidSnapshot(description + ' must be a string');
  }

  function _requireFiniteNumber(value, description, positive) {
    if (typeof value !== 'number' || !Number.isFinite(value) || (positive && value <= 0)) {
      _invalidSnapshot(description + ' must be a finite ' + (positive ? 'positive ' : '') + 'number');
    }
  }

  function _validateElementRecord(record, expectedGroup, description) {
    if (!_isObject(record) || (record.group !== 'nodes' && record.group !== 'edges')) {
      _invalidSnapshot(description + ' must be a Cytoscape node or edge record');
    }
    if (expectedGroup && record.group !== expectedGroup) {
      _invalidSnapshot(description + ' has the wrong graph element type');
    }
    if (!_isObject(record.data)) _invalidSnapshot(description + ' has no data object');
    _requireString(record.data.id, description + ' ID');
    if (record.group === 'edges') {
      _requireString(record.data.source, description + ' source');
      _requireString(record.data.target, description + ' target');
    }
  }

  function _collectRestorableNodes(nodeRecord, nodeIds, componentIds, edgeReferences, visited, isLiveRoot) {
    if (!_isObject(nodeRecord) || !_isObject(nodeRecord.data)) return;
    const data = nodeRecord.data;
    if (typeof data.id === 'string') {
      if (!isLiveRoot) {
        if (nodeIds.has(data.id)) _invalidSnapshot('graph or restoration data contains a duplicate node ID');
        nodeIds.add(data.id);
        const componentMatch = /^c_(\d+)$/i.exec(data.id);
        if (componentMatch) componentIds.push(Number(componentMatch[1]));
      }
    }
    if (data.parent !== undefined && data.parent !== null) {
      _requireString(data.parent, 'restoration node parent');
      edgeReferences.push(data.parent);
    }

    const consumed = data.consumedSubnet || data.consumedSubgraph;
    if (!_isObject(consumed) || visited.has(consumed)) return;
    visited.add(consumed);
    ['nodes', 'consumedCompounds'].forEach(function(key) {
      if (consumed[key] === undefined) return;
      if (!Array.isArray(consumed[key])) _invalidSnapshot('restoration ' + key + ' must be an array');
      consumed[key].forEach(function(child) {
        _validateElementRecord(child, 'nodes', 'restoration node');
        _collectRestorableNodes(child, nodeIds, componentIds, edgeReferences, visited, false);
      });
    });
    if (consumed.internalEdges !== undefined) {
      if (!Array.isArray(consumed.internalEdges)) _invalidSnapshot('restoration internalEdges must be an array');
      consumed.internalEdges.forEach(function(edge) {
        _validateElementRecord(edge, 'edges', 'restoration edge');
        edgeReferences.push(edge.data.source, edge.data.target);
      });
    }
    ['boundaryInArcs', 'boundaryOutArcs'].forEach(function(key) {
      (consumed[key] || []).forEach(function(arc) {
        if (!_isObject(arc)) _invalidSnapshot('restoration boundary arc must be an object');
        ['sourceId', 'targetId'].forEach(function(field) {
          _requireString(arc[field], 'restoration boundary arc ' + field);
          edgeReferences.push(arc[field]);
        });
        ['originalSourceId', 'originalTargetId'].forEach(function(field) {
          if (arc[field] !== undefined && arc[field] !== null) {
            _requireString(arc[field], 'restoration boundary arc ' + field);
            edgeReferences.push(arc[field]);
          }
        });
      });
    });
  }

  function _validateDocumentContext(documentContext) {
    if (!_isObject(documentContext)) _invalidSnapshot('document context is missing');
    ['title', 'sourceFile', 'filename', 'functionName', 'mode'].forEach(function(key) {
      _requireString(documentContext[key], 'document.' + key);
    });
    const originalNet = documentContext.originalNet;
    if (!_isObject(originalNet) || !Array.isArray(originalNet.places) ||
        !Array.isArray(originalNet.transitions) || !Array.isArray(originalNet.arcs)) {
      _invalidSnapshot('document.originalNet must contain places, transitions, and arcs arrays');
    }
    if (documentContext.compounds !== undefined && !Array.isArray(documentContext.compounds)) {
      _invalidSnapshot('document.compounds must be an array');
    }
    if (!Array.isArray(documentContext.foldSteps)) _invalidSnapshot('document.foldSteps must be an array');
    if (!_isObject(documentContext.calleeNets)) _invalidSnapshot('document.calleeNets must be an object');
    if (!Array.isArray(documentContext.expandedNodes)) _invalidSnapshot('document.expandedNodes must be an array');
    documentContext.expandedNodes.forEach(function(entry) {
      if (!Array.isArray(entry) || entry.length !== 2 || typeof entry[0] !== 'string' || !_isObject(entry[1])) {
        _invalidSnapshot('document.expandedNodes contains an invalid entry');
      }
    });
    const playback = documentContext.playback;
    if (!_isObject(playback) || !Number.isInteger(playback.currentStep) || playback.currentStep < 0 ||
        !Number.isInteger(playback.totalSteps) || playback.totalSteps !== documentContext.foldSteps.length ||
        playback.totalSteps < playback.currentStep) {
      _invalidSnapshot('document.playback is invalid');
    }
    if (documentContext.finalSm !== undefined) _requireFiniteNumber(documentContext.finalSm, 'document.finalSm');
    if (documentContext.fullyReducible !== undefined && typeof documentContext.fullyReducible !== 'boolean') {
      _invalidSnapshot('document.fullyReducible must be a boolean');
    }
  }

  /**
   * Parses and validates a saved session before a viewer replaces its active graph.
   * Component IDs found anywhere in restoration records raise the allocation counter.
   * @param {string|Object} input
   * @returns {Object}
   */
  function parseFoldStateSnapshot(input) {
    let snapshot;
    try {
      snapshot = typeof input === 'string' ? JSON.parse(input) : _cloneJson(input);
    } catch (error) {
      _invalidSnapshot('file is not valid JSON');
    }
    if (!_isObject(snapshot)) _invalidSnapshot('root must be an object');
    if (snapshot.schemaVersion !== SCHEMA_VERSION) _invalidSnapshot('unsupported schema version');
    if (snapshot.snapshotType !== SNAPSHOT_TYPE) _invalidSnapshot('snapshot type is not supported');

    if (!Array.isArray(snapshot.elements)) _invalidSnapshot('elements must be an array');
    const liveNodeIds = new Set();
    const allNodeIds = new Set();
    const componentIds = [];
    const restorationReferences = [];
    const visitedSubnets = new WeakSet();
    snapshot.elements.forEach(function(element) {
      _validateElementRecord(element, null, 'graph element');
      if (element.group === 'nodes') {
        if (liveNodeIds.has(element.data.id)) _invalidSnapshot('graph contains a duplicate node ID');
        liveNodeIds.add(element.data.id);
        allNodeIds.add(element.data.id);
        const componentMatch = /^c_(\d+)$/i.exec(element.data.id);
        if (componentMatch) componentIds.push(Number(componentMatch[1]));
      }
    });
    snapshot.elements.forEach(function(element) {
      if (element.group === 'nodes') {
        const id = element.data.id;
        // The live node ID has already been recorded; recursion adds only hidden descendants.
        _collectRestorableNodes(element, allNodeIds, componentIds, restorationReferences, visitedSubnets, true);
      }
    });
    const liveElementIds = new Set();
    snapshot.elements.forEach(function(element) {
      if (liveElementIds.has(element.data.id)) _invalidSnapshot('graph contains a duplicate element ID');
      liveElementIds.add(element.data.id);
      if (element.group === 'edges' &&
          (!liveNodeIds.has(element.data.source) || !liveNodeIds.has(element.data.target))) {
        _invalidSnapshot('graph edge references a missing node');
      }
      if (element.group === 'nodes' && element.data.parent && !liveNodeIds.has(element.data.parent)) {
        _invalidSnapshot('graph node references a missing parent');
      }
    });
    restorationReferences.forEach(function(id) {
      if (!allNodeIds.has(id)) _invalidSnapshot('restoration record references a missing node');
    });

    const engine = snapshot.engine;
    if (!_isObject(engine) || !Number.isInteger(engine.stepCounter) || engine.stepCounter < 0) {
      _invalidSnapshot('engine.stepCounter is invalid');
    }
    if (!_isObject(engine.cfg)) _invalidSnapshot('engine.cfg must be an object');
    Object.keys(engine.cfg).forEach(function(key) {
      _requireFiniteNumber(engine.cfg[key], 'engine.cfg.' + key);
    });
    if (!Array.isArray(engine.rememberedCustomNames)) _invalidSnapshot('engine.rememberedCustomNames must be an array');
    engine.rememberedCustomNames.forEach(function(entry) {
      if (!Array.isArray(entry) || entry.length !== 2 || typeof entry[0] !== 'string' || typeof entry[1] !== 'string') {
        _invalidSnapshot('engine.rememberedCustomNames contains an invalid entry');
      }
    });

    const viewport = snapshot.viewport;
    if (!_isObject(viewport) || !_isObject(viewport.pan)) _invalidSnapshot('viewport is invalid');
    _requireFiniteNumber(viewport.zoom, 'viewport.zoom', true);
    _requireFiniteNumber(viewport.pan.x, 'viewport.pan.x');
    _requireFiniteNumber(viewport.pan.y, 'viewport.pan.y');
    _validateDocumentContext(snapshot.document);

    if (componentIds.length > 0) {
      engine.stepCounter = Math.max(engine.stepCounter, Math.max.apply(null, componentIds));
    }
    return snapshot;
  }

  function _downloadBlob(blob, filename) {
    if (typeof document === 'undefined' || typeof URL === 'undefined' || typeof URL.createObjectURL !== 'function') return;
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    if (document.body && typeof document.body.appendChild === 'function') {
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
    } else if (typeof anchor.click === 'function') {
      anchor.click();
    }
    if (typeof URL.revokeObjectURL === 'function') {
      setTimeout(function() { URL.revokeObjectURL(url); }, 100);
    }
  }

  /**
   * Serializes and downloads the active viewer as JSON session data.
   * Returns the serialized result so generated-viewer tests can inspect it.
   */
  function downloadFoldStateSnapshot(options) {
    const opts = options || {};
    const snapshot = serializeFoldStateSnapshot(opts);
    const json = JSON.stringify(snapshot, null, 2);
    const title = opts.document && opts.document.title;
    const filename = opts.filename || getFoldStateSnapshotFilename(title);
    const blob = new Blob([json], { type: 'application/json;charset=utf-8' });
    const downloadBlob = opts.downloadBlob || _downloadBlob;
    downloadBlob(blob, filename);
    return { snapshot: snapshot, json: json, filename: filename };
  }

  return {
    FOLD_STATE_SNAPSHOT_SCHEMA_VERSION: SCHEMA_VERSION,
    FOLD_STATE_SNAPSHOT_TYPE: SNAPSHOT_TYPE,
    serializeFoldStateSnapshot,
    parseFoldStateSnapshot,
    getFoldStateSnapshotFilename,
    downloadFoldStateSnapshot
  };
});
