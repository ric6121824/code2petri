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

  // Detach snapshot values while normalizing restoration aliases before they can
  // multiply through recursive JSON cloning. On disk, consumedSubnet is canonical.
  function _cloneSnapshotValue(value) {
    if (Array.isArray(value)) return value.map(_cloneSnapshotValue);
    if (!_isObject(value)) return value;

    const isNodeRecord = value.group === 'nodes' && _isObject(value.data);
    const hasRestoration = isNodeRecord &&
      (Object.prototype.hasOwnProperty.call(value.data, 'consumedSubnet') ||
       Object.prototype.hasOwnProperty.call(value.data, 'consumedSubgraph'));
    const clone = {};
    Object.keys(value).forEach(function(key) {
      if (hasRestoration && key === 'data') {
        const data = {};
        Object.keys(value.data).forEach(function(dataKey) {
          if (dataKey === 'consumedSubgraph') return;
          if (dataKey === 'consumedSubnet') {
            data.consumedSubnet = _cloneSnapshotValue(value.data.consumedSubnet);
          } else {
            data[dataKey] = _cloneSnapshotValue(value.data[dataKey]);
          }
        });
        if (!Object.prototype.hasOwnProperty.call(value.data, 'consumedSubnet') &&
            Object.prototype.hasOwnProperty.call(value.data, 'consumedSubgraph')) {
          data.consumedSubnet = _cloneSnapshotValue(value.data.consumedSubgraph);
        }
        clone.data = data;
      } else {
        clone[key] = _cloneSnapshotValue(value[key]);
      }
    });
    return clone;
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
      elements: _cloneSnapshotValue(cy.elements().jsons()),
      engine: {
        stepCounter: Number(engine.stepCounter) || 0,
        cfg: _cloneJson(engine.cfg || {}),
        rememberedCustomNames: _cloneJson(_rememberedCustomNameEntries(engine))
      },
      viewport: _cloneJson(viewport),
      document: _cloneSnapshotValue(opts.document || {})
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

    const hasCanonicalRestoration = Object.prototype.hasOwnProperty.call(data, 'consumedSubnet');
    const hasLegacyRestoration = Object.prototype.hasOwnProperty.call(data, 'consumedSubgraph');
    const consumed = hasCanonicalRestoration
      ? data.consumedSubnet
      : data.consumedSubgraph;
    if ((hasCanonicalRestoration || hasLegacyRestoration) && !_isObject(consumed)) {
      _invalidSnapshot('restoration record must be an object');
    }
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
    if (documentContext.returnMetadata !== undefined && documentContext.returnMetadata !== null) {
      const metadata = documentContext.returnMetadata;
      if (!_isObject(metadata)) _invalidSnapshot('document.returnMetadata must be an object');
      _requireString(metadata.function_name, 'document.returnMetadata.function_name');
      _requireString(metadata.source_file, 'document.returnMetadata.source_file');
      _requireString(metadata.qualified_name, 'document.returnMetadata.qualified_name');
      if (!_isObject(metadata.definition_location) ||
          !Number.isInteger(metadata.definition_location.line) ||
          (metadata.definition_location.column !== null &&
           !Number.isInteger(metadata.definition_location.column))) {
        _invalidSnapshot('document.returnMetadata.definition_location is invalid');
      }
      if (!['complete', 'unknown', 'no_normal_return', 'not_applicable'].includes(metadata.analysis_status)) {
        _invalidSnapshot('document.returnMetadata.analysis_status is invalid');
      }
      if (metadata.declared !== null) {
        if (!_isObject(metadata.declared)) _invalidSnapshot('document.returnMetadata.declared is invalid');
        _requireString(metadata.declared.expression, 'document.returnMetadata.declared.expression');
        _requireString(metadata.declared.provenance, 'document.returnMetadata.declared.provenance');
      }
      if (!Array.isArray(metadata.inferred)) _invalidSnapshot('document.returnMetadata.inferred must be an array');
      metadata.inferred.forEach(function(evidence, index) {
        const description = 'document.returnMetadata.inferred[' + index + ']';
        if (!_isObject(evidence)) _invalidSnapshot(description + ' must be an object');
        ['expression', 'type', 'provenance', 'role'].forEach(function(key) {
          _requireString(evidence[key], description + '.' + key);
        });
        if (!_isObject(evidence.source_location) || !Number.isInteger(evidence.source_location.line)) {
          _invalidSnapshot(description + '.source_location is invalid');
        }
        if (evidence.expression_location !== undefined &&
            (!_isObject(evidence.expression_location) ||
             !Number.isInteger(evidence.expression_location.line) ||
             (evidence.expression_location.column !== null &&
              !Number.isInteger(evidence.expression_location.column)))) {
          _invalidSnapshot(description + '.expression_location is invalid');
        }
        if (evidence.evidence !== undefined) {
          if (!Array.isArray(evidence.evidence)) _invalidSnapshot(description + '.evidence must be an array');
          evidence.evidence.forEach(function(assignment, evidenceIndex) {
            const assignmentDescription = description + '.evidence[' + evidenceIndex + ']';
            if (!_isObject(assignment)) _invalidSnapshot(assignmentDescription + ' must be an object');
            ['expression', 'type', 'provenance'].forEach(function(key) {
              _requireString(assignment[key], assignmentDescription + '.' + key);
            });
            if (!_isObject(assignment.source_location) || !Number.isInteger(assignment.source_location.line)) {
              _invalidSnapshot(assignmentDescription + '.source_location is invalid');
            }
          });
        }
      });
      ['inferred_types', 'observed_types'].forEach(function(key) {
        if (metadata[key] !== undefined && (!Array.isArray(metadata[key]) ||
            metadata[key].some(function(value) { return typeof value !== 'string'; }))) {
          _invalidSnapshot('document.returnMetadata.' + key + ' must be an array of strings');
        }
      });
      if (metadata.observed !== undefined) {
        if (!Array.isArray(metadata.observed)) _invalidSnapshot('document.returnMetadata.observed must be an array');
        metadata.observed.forEach(function(evidence, index) {
          const description = 'document.returnMetadata.observed[' + index + ']';
          if (!_isObject(evidence)) _invalidSnapshot(description + ' must be an object');
          ['expression', 'type', 'provenance', 'role'].forEach(function(key) {
            _requireString(evidence[key], description + '.' + key);
          });
          if (!_isObject(evidence.source_location) || !Number.isInteger(evidence.source_location.line)) {
            _invalidSnapshot(description + '.source_location is invalid');
          }
        });
      }
      if (metadata.function_kind !== undefined) {
        if (!['generator', 'async_generator', 'async_function'].includes(metadata.function_kind)) {
          _invalidSnapshot('document.returnMetadata.function_kind is invalid');
        }
        const roles = metadata.roles;
        if (!_isObject(roles)) _invalidSnapshot('document.returnMetadata.roles must be an object');
        const requiredRoles = metadata.function_kind === 'async_function'
          ? ['immediate', 'awaited'] : ['immediate', 'yielded', 'completion'];
        requiredRoles.forEach(function(roleName) {
          const role = roles[roleName];
          const description = 'document.returnMetadata.roles.' + roleName;
          if (!_isObject(role)) _invalidSnapshot(description + ' must be an object');
          if (!['complete', 'unknown', 'no_normal_return', 'not_applicable'].includes(role.analysis_status)) {
            _invalidSnapshot(description + '.analysis_status is invalid');
          }
          if (role.declared !== null && role.declared !== undefined) {
            if (!_isObject(role.declared)) _invalidSnapshot(description + '.declared is invalid');
            _requireString(role.declared.expression, description + '.declared.expression');
            _requireString(role.declared.provenance, description + '.declared.provenance');
            if (role.declared.source_location !== undefined &&
                (!_isObject(role.declared.source_location) ||
                 !Number.isInteger(role.declared.source_location.line) ||
                 (role.declared.source_location.column !== null &&
                  !Number.isInteger(role.declared.source_location.column)))) {
              _invalidSnapshot(description + '.declared.source_location is invalid');
            }
          }
          ['inferred', 'observed'].forEach(function(key) {
            if (!Array.isArray(role[key])) _invalidSnapshot(description + '.' + key + ' must be an array');
            role[key].forEach(function(evidence, index) {
              const itemDescription = description + '.' + key + '[' + index + ']';
              if (!_isObject(evidence)) _invalidSnapshot(itemDescription + ' must be an object');
              ['expression', 'type', 'provenance', 'role'].forEach(function(field) {
                _requireString(evidence[field], itemDescription + '.' + field);
              });
              if (!_isObject(evidence.source_location) ||
                  !Number.isInteger(evidence.source_location.line) ||
                  (evidence.source_location.column !== null &&
                   !Number.isInteger(evidence.source_location.column))) {
                _invalidSnapshot(itemDescription + '.source_location is invalid');
              }
              if (evidence.expression_location !== undefined &&
                  (!_isObject(evidence.expression_location) ||
                   !Number.isInteger(evidence.expression_location.line) ||
                   (evidence.expression_location.column !== null &&
                    !Number.isInteger(evidence.expression_location.column)))) {
                _invalidSnapshot(itemDescription + '.expression_location is invalid');
              }
            });
          });
          ['inferred_types', 'observed_types'].forEach(function(key) {
            if (!Array.isArray(role[key]) || role[key].some(function(value) { return typeof value !== 'string'; })) {
              _invalidSnapshot(description + '.' + key + ' must be an array of strings');
            }
          });
        });
      } else if (metadata.roles !== undefined) {
        _invalidSnapshot('document.returnMetadata.roles requires function_kind');
      }
    }
    function validateCompounds(compounds, description, nodeIds) {
      if (!Array.isArray(compounds)) _invalidSnapshot(description + ' must be an array');
      compounds.forEach(function(compound, index) {
        const compoundDescription = description + '[' + index + ']';
        if (!_isObject(compound)) _invalidSnapshot(compoundDescription + ' must be an object');
        _requireString(compound.id, compoundDescription + '.id');
        if (nodeIds && nodeIds.has(compound.id)) {
          _invalidSnapshot(description + ' contains duplicate node ID ' + compound.id);
        }
        if (nodeIds) nodeIds.add(compound.id);
        if (compound.parent !== undefined && compound.parent !== null) {
          _requireString(compound.parent, compoundDescription + '.parent');
        }
        ['label', 'function_name', 'file'].forEach(function(key) {
          if (compound[key] !== undefined && compound[key] !== null) {
            _requireString(compound[key], compoundDescription + '.' + key);
          }
        });
      });
    }

    function validateNet(net, description) {
      if (!_isObject(net) || !Array.isArray(net.places) ||
          !Array.isArray(net.transitions) || !Array.isArray(net.arcs)) {
        _invalidSnapshot(description + ' must contain places, transitions, and arcs arrays');
      }
      const nodeIds = new Set();
      const edgeIds = new Set();
      function validateNodeRecord(record, group, index) {
        const recordDescription = description + '.' + group + '[' + index + ']';
        if (!_isObject(record)) _invalidSnapshot(recordDescription + ' must be an object');
        _requireString(record.id, recordDescription + '.id');
        if (nodeIds.has(record.id)) _invalidSnapshot(description + ' contains duplicate node ID ' + record.id);
        nodeIds.add(record.id);
        ['label', 'parent', 'enclosing_function'].forEach(function(key) {
          if (record[key] !== undefined && record[key] !== null) {
            _requireString(record[key], recordDescription + '.' + key);
          }
        });
        if (record.metadata !== undefined && record.metadata !== null && !_isObject(record.metadata)) {
          _invalidSnapshot(recordDescription + '.metadata must be an object');
        }
        if (group === 'transitions') {
          const metadata = record.metadata || {};
          ['tau', 'omega'].forEach(function(key) {
            [record[key], metadata[key]].forEach(function(value) {
              if (value !== undefined && value !== null && !Number.isFinite(Number(value))) {
                _invalidSnapshot(recordDescription + '.' + key + ' must be numeric');
              }
            });
          });
        } else if (record.initial_tokens !== undefined && record.initial_tokens !== null &&
                   !Number.isFinite(Number(record.initial_tokens))) {
          _invalidSnapshot(recordDescription + '.initial_tokens must be numeric');
        }
      }
      net.places.forEach(function(record, index) { validateNodeRecord(record, 'places', index); });
      net.transitions.forEach(function(record, index) { validateNodeRecord(record, 'transitions', index); });
      if (net.compounds !== undefined) validateCompounds(net.compounds, description + '.compounds', nodeIds);
      function endpointId(endpoint, arcDescription, name) {
        const id = typeof endpoint === 'string'
          ? endpoint
          : (_isObject(endpoint) ? endpoint.id : null);
        _requireString(id, arcDescription + '.' + name);
        if (!nodeIds.has(id)) _invalidSnapshot(arcDescription + '.' + name + ' references a missing node');
        return id;
      }
      net.arcs.forEach(function(arc, index) {
        const arcDescription = description + '.arcs[' + index + ']';
        if (!_isObject(arc)) _invalidSnapshot(arcDescription + ' must be an object');
        const sourceId = endpointId(arc.source, arcDescription, 'source');
        const targetId = endpointId(arc.target, arcDescription, 'target');
        const edgeId = arc.id === undefined || arc.id === null
          ? 'arc_' + index + '_' + sourceId + '_' + targetId
          : arc.id;
        _requireString(edgeId, arcDescription + '.id');
        if (edgeIds.has(edgeId)) _invalidSnapshot(description + ' contains duplicate arc ID ' + edgeId);
        edgeIds.add(edgeId);
        if (arc.weight !== undefined && arc.weight !== null && !Number.isFinite(Number(arc.weight))) {
          _invalidSnapshot(arcDescription + '.weight must be numeric');
        }
      });
    }
    validateNet(documentContext.originalNet, 'document.originalNet');
    if (documentContext.compounds !== undefined) {
      // These containers may be supplied separately from the net, so validate their shape here.
      validateCompounds(documentContext.compounds, 'document.compounds');
    }
    if (!Array.isArray(documentContext.foldSteps)) _invalidSnapshot('document.foldSteps must be an array');
    documentContext.foldSteps.forEach(function(step, index) {
      const description = 'document.foldSteps[' + index + ']';
      if (!_isObject(step)) _invalidSnapshot(description + ' must be an object');
      if (step.net !== undefined) validateNet(step.net, description + '.net');
      ['component_type', 'opaque_transition'].forEach(function(key) {
        if (step[key] !== undefined && step[key] !== null) _requireString(step[key], description + '.' + key);
      });
      ['sm_score', 'omega', 'tau'].forEach(function(key) {
        if (step[key] !== undefined && step[key] !== null) _requireFiniteNumber(step[key], description + '.' + key);
      });
    });
    if (!_isObject(documentContext.calleeNets)) _invalidSnapshot('document.calleeNets must be an object');
    Object.keys(documentContext.calleeNets).forEach(function(name) {
      validateNet(documentContext.calleeNets[name], 'document.calleeNets.' + name);
    });
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
    if (typeof document === 'undefined' || typeof URL === 'undefined' ||
        typeof URL.createObjectURL !== 'function' || typeof URL.revokeObjectURL !== 'function') {
      throw new Error('This browser cannot create a session download');
    }

    // Browsers do not expose a completion event for an anchor download. Keep
    // each URL alive independently for a conservative, bounded grace period;
    // this is an initiation safeguard, not proof that the file was written.
    const URL_GRACE_PERIOD_MS = 30000;
    const url = URL.createObjectURL(blob);
    let anchor = null;
    let attached = false;
    let released = false;
    function releaseUrl() {
      if (released) return;
      released = true;
      URL.revokeObjectURL(url);
    }
    function removeAnchor() {
      if (!attached || !document.body || typeof document.body.removeChild !== 'function') return;
      attached = false;
      document.body.removeChild(anchor);
    }

    try {
      anchor = document.createElement('a');
      if (!anchor || typeof anchor.click !== 'function') {
        throw new Error('This browser cannot initiate a session download');
      }
      anchor.href = url;
      anchor.download = filename;
      if (document.body && typeof document.body.appendChild === 'function') {
        attached = true;
        document.body.appendChild(anchor);
      }
      anchor.click();
      removeAnchor();
      setTimeout(releaseUrl, URL_GRACE_PERIOD_MS);
    } catch (error) {
      try { removeAnchor(); } catch (_) { /* Keep the initiating error visible. */ }
      try { releaseUrl(); } catch (_) { /* Best-effort cleanup after a failed initiation. */ }
      throw error;
    }
  }

  /**
   * Serializes and downloads the active viewer as JSON session data.
   * Returns the serialized result so generated-viewer tests can inspect it.
   */
  function downloadFoldStateSnapshot(options) {
    const opts = options || {};
    const snapshot = serializeFoldStateSnapshot(opts);
    const json = JSON.stringify(snapshot);
    const title = opts.document && opts.document.title;
    const filename = opts.filename || getFoldStateSnapshotFilename(title);
    if (typeof Blob !== 'function') throw new Error('This browser cannot create a session download');
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
