/**
 * Fold State Snapshot serialization for the self-contained code2petri viewer.
 */

(function(root, factory) {
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = factory(require('./viewport.js'), require('./viewer_transient_classes.js'));
  } else {
    const exports = factory(root, root);
    if (typeof window !== 'undefined') {
      Object.assign(window, exports);
    } else if (typeof globalThis !== 'undefined') {
      Object.assign(globalThis, exports);
    }
  }
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this), function(viewportModule, viewerClassUtils) {
  const SCHEMA_VERSION = 1;
  const SNAPSHOT_TYPE = 'code2petri-fold-state';
  const stripTransientSearchClasses = viewerClassUtils.stripTransientSearchClasses;

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
      if (isNodeRecord && key === 'classes' && typeof value.classes === 'string') {
        clone.classes = stripTransientSearchClasses(value.classes);
      } else if (hasRestoration && key === 'data') {
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

  function getFoldStateSnapshotFilename(htmlFilename) {
    const raw = String(htmlFilename || '').trim();
    let basename = raw.replace(/\\/g, '/').split('/').pop();
    try {
      basename = decodeURIComponent(basename);
    } catch (_) {
      // Keep the literal filename when the URL contains malformed escapes.
    }
    const htmlStem = basename.replace(/\.html?$/i, '');
    const safeStem = htmlStem
      .replace(/[<>:"/\\|?*\u0000-\u001f]/g, '_')
      .replace(/[. ]+$/g, '');
    return (safeStem || 'petri_net') + '_session_save.json';
  }

  function _invalidSnapshot(reason) {
    throw new Error('Invalid Fold State Snapshot: ' + reason);
  }

  function _migrateLegacyInlineCallResultIds(snapshot) {
    const visited = new WeakSet();

    function migrateRecords(records, ownerId) {
      if (!Array.isArray(records) || typeof ownerId !== 'string' || !ownerId.startsWith('inline_')) return;
      const separator = ownerId.lastIndexOf('__');
      if (separator <= 'inline_'.length || separator + 2 >= ownerId.length) return;
      const localTransitionId = ownerId.slice(separator + 2);
      records.forEach(function(record) {
        if (_isObject(record) && record.transition_id === localTransitionId) {
          record.transition_id = ownerId;
        }
      });
    }

    function visit(value, parentKey) {
      if (Array.isArray(value)) {
        value.forEach(function(item) { visit(item, parentKey); });
        return;
      }
      if (!_isObject(value) || visited.has(value)) return;
      visited.add(value);

      if (value.group === 'nodes' && _isObject(value.data)) {
        migrateRecords(value.data.call_results, value.data.id);
      }
      if (parentKey === 'transitions' && typeof value.id === 'string' && _isObject(value.metadata)) {
        migrateRecords(value.metadata.call_results, value.id);
      }
      Object.keys(value).forEach(function(key) { visit(value[key], key); });
    }

    visit(snapshot, null);
  }

  function _isObject(value) {
    return value !== null && typeof value === 'object' && !Array.isArray(value);
  }

  function _requireString(value, description) {
    if (typeof value !== 'string') _invalidSnapshot(description + ' must be a string');
  }

  function _validateFunctionReturnEvidence(evidence, description) {
    if (!_isObject(evidence) || typeof evidence.expression !== 'string' || typeof evidence.type !== 'string' ||
        typeof evidence.provenance !== 'string') {
      _invalidSnapshot(description + ' is invalid');
    }
  }

  function _validateCallRefoldingRecord(record, description) {
    if (!_isObject(record) || record.version !== 1) {
      _invalidSnapshot(description + ' must be a version 1 call-refolding record');
    }
    const call = record.call_transition;
    if (!_isObject(call)) _invalidSnapshot(description + '.call_transition must be an object');
    _requireString(call.id, description + '.call_transition.id');
    _requireString(call.label, description + '.call_transition.label');
    if (call.metadata !== undefined && !_isObject(call.metadata)) {
      _invalidSnapshot(description + '.call_transition.metadata must be an object');
    }
    if (call.metadata && call.metadata.call_results !== undefined) {
      _validateCallResultRecords(call.metadata.call_results, description + '.call_transition.metadata.call_results', call.id);
    }
    if (call.metadata && call.metadata.function_return_evidence !== undefined) {
      _validateFunctionReturnEvidence(
        call.metadata.function_return_evidence,
        description + '.call_transition.metadata.function_return_evidence'
      );
    }
    if (!Array.isArray(record.exception_transitions)) {
      _invalidSnapshot(description + '.exception_transitions must be an array');
    }
    const alternativeIds = new Set();
    record.exception_transitions.forEach(function(transition, index) {
      const path = description + '.exception_transitions[' + index + ']';
      if (!_isObject(transition)) _invalidSnapshot(path + ' must be an object');
      _requireString(transition.id, path + '.id');
      _requireString(transition.label, path + '.label');
      if (transition.id === call.id || alternativeIds.has(transition.id)) {
        _invalidSnapshot(path + '.id duplicates another call transition');
      }
      alternativeIds.add(transition.id);
      const metadata = transition.metadata;
      if (!_isObject(metadata) || metadata.exception_alternative !== true ||
          metadata.exception_alternative_of !== call.id) {
        _invalidSnapshot(path + '.metadata does not identify the call alternative');
      }
    });
    [
      ['call_input_arcs', call.id, 'target'],
      ['call_output_arcs', call.id, 'source'],
      ['exception_input_arcs', alternativeIds, 'target'],
      ['exception_output_arcs', alternativeIds, 'source']
    ].forEach(function(specification) {
      const key = specification[0];
      const expectedNode = specification[1];
      const role = specification[2];
      const arcs = record[key];
      if (!Array.isArray(arcs)) _invalidSnapshot(description + '.' + key + ' must be an array');
      arcs.forEach(function(arc, index) {
        const path = description + '.' + key + '[' + index + ']';
        if (!_isObject(arc)) _invalidSnapshot(path + ' must be an object');
        _requireString(arc.source, path + '.source');
        _requireString(arc.target, path + '.target');
        if (arc[role] !== expectedNode &&
            !(expectedNode instanceof Set && expectedNode.has(arc[role]))) {
          _invalidSnapshot(path + ' is connected to the wrong call outcome');
        }
        if (arc.weight !== undefined && arc.weight !== null && !Number.isFinite(Number(arc.weight))) {
          _invalidSnapshot(path + '.weight must be numeric');
        }
      });
    });
    return { callId: call.id, alternativeIds: alternativeIds };
  }

  function _requireFiniteNumber(value, description, positive) {
    if (typeof value !== 'number' || !Number.isFinite(value) || (positive && value <= 0)) {
      _invalidSnapshot(description + ' must be a finite ' + (positive ? 'positive ' : '') + 'number');
    }
  }

  function _validateCallResultRecords(records, description, expectedTransitionId) {
    if (!Array.isArray(records)) _invalidSnapshot(description + ' must be an array');
    const resultTypes = {
      range: 'range', len: 'int', str: 'str', int: 'int', float: 'float',
      bool: 'bool', list: 'list', tuple: 'tuple', dict: 'dict', set: 'set'
    };
    records.forEach(function(record, index) {
      const path = description + '[' + index + ']';
      if (!_isObject(record)) _invalidSnapshot(path + ' must be an object');
      ['expression', 'transition_id', 'call_site_id', 'caller_function', 'caller_file'].forEach(function(key) {
        _requireString(record[key], path + '.' + key);
      });
      if (expectedTransitionId !== undefined && record.transition_id !== expectedTransitionId) {
        _invalidSnapshot(path + '.transition_id does not match its owning transition');
      }
      if (!record.source_location || !_isObject(record.source_location) ||
          !Number.isInteger(record.source_location.line) || record.source_location.line < 1 ||
          !Number.isInteger(record.source_location.column) || record.source_location.column < 0) {
        _invalidSnapshot(path + '.source_location is invalid');
      }
      if (record.state === 'known') {
        const canonical = typeof record.canonical_builtin === 'string'
          ? record.canonical_builtin.replace(/^builtins\./, '') : '';
        if (!Object.prototype.hasOwnProperty.call(resultTypes, canonical) ||
            record.canonical_builtin !== 'builtins.' + canonical || record.type !== resultTypes[canonical] ||
            record.provenance !== 'python_builtin_static_contract' || record.unknown_reason !== null) {
          _invalidSnapshot(path + ' has invalid known built-in evidence');
        }
      } else if (record.state === 'unknown') {
        if (record.type !== 'unknown' || record.canonical_builtin !== null || record.provenance !== null ||
            !['no_available_contract', 'unsupported_builtin', 'unsupported_alias_form',
              'shadowed_or_uncertain_binding'].includes(record.unknown_reason)) {
          _invalidSnapshot(path + ' has invalid unknown call evidence');
        }
      } else {
        _invalidSnapshot(path + '.state is invalid');
      }
    });
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
    if (record.data.call_results !== undefined) {
      _validateCallResultRecords(record.data.call_results, description + '.call_results', record.data.id);
    }
    if (record.data.function_return_evidence !== undefined) {
      _validateFunctionReturnEvidence(record.data.function_return_evidence, description + '.function_return_evidence');
    }
    if (record.data.call_refolding !== undefined) {
      _validateCallRefoldingRecord(record.data.call_refolding, description + '.call_refolding');
    }
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
    if (_isObject(consumed) && !visited.has(consumed)) {
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

    if (data.call_refolding !== undefined) {
      const callRefolding = _validateCallRefoldingRecord(
        data.call_refolding, 'restoration node call_refolding'
      );
      const endpointRoles = [
        ['call_input_arcs', 'source'],
        ['call_output_arcs', 'target'],
        ['exception_input_arcs', 'source'],
        ['exception_output_arcs', 'target']
      ];
      endpointRoles.forEach(function(specification) {
        (data.call_refolding[specification[0]] || []).forEach(function(arc) {
          const endpoint = arc[specification[1]];
          if (endpoint !== callRefolding.callId && !callRefolding.alternativeIds.has(endpoint)) {
            edgeReferences.push(endpoint);
          }
        });
      });
    }

    const functionRestoration = data.function_restoration;
    if (functionRestoration !== undefined) {
      if (!_isObject(functionRestoration) || functionRestoration.version !== 1 ||
          !Array.isArray(functionRestoration.elements) ||
          !Array.isArray(functionRestoration.removeNodeIds) ||
          !Array.isArray(functionRestoration.expandedNodes)) {
        _invalidSnapshot('function_restoration has an unsupported or invalid shape');
      }
      const localNodeIds = new Set();
      functionRestoration.elements.forEach(function(element) {
        _validateElementRecord(element, null, 'function restoration element');
        if (element.group === 'nodes') {
          if (localNodeIds.has(element.data.id)) {
            _invalidSnapshot('function_restoration contains duplicate node IDs');
          }
          localNodeIds.add(element.data.id);
          _collectRestorableNodes(
            element, nodeIds, componentIds, edgeReferences, visited, element.data.id === data.id
          );
        } else {
          edgeReferences.push(element.data.source, element.data.target);
        }
      });
      const removalIds = new Set();
      functionRestoration.removeNodeIds.forEach(function(id) {
        _requireString(id, 'function_restoration.removeNodeIds entry');
        if (removalIds.has(id)) _invalidSnapshot('function_restoration repeats a removal node ID');
        removalIds.add(id);
      });
      functionRestoration.expandedNodes.forEach(function(entry, index) {
        const path = 'function_restoration.expandedNodes[' + index + ']';
        if (!Array.isArray(entry) || entry.length !== 2 || typeof entry[0] !== 'string' || !_isObject(entry[1])) {
          _invalidSnapshot(path + ' is invalid');
        }
        if (entry[1].restoreElements !== undefined) {
          if (!Array.isArray(entry[1].restoreElements)) {
            _invalidSnapshot(path + '.restoreElements must be an array');
          }
          entry[1].restoreElements.forEach(function(element) {
            _validateElementRecord(element, null, path + '.restoreElements element');
            if (element.group === 'edges') edgeReferences.push(element.data.source, element.data.target);
          });
        }
      });
      if (functionRestoration.analysis !== undefined && functionRestoration.analysis !== null) {
        const analysis = functionRestoration.analysis;
        if (!_isObject(analysis) ||
            (analysis.reductionOutcome !== null && analysis.reductionOutcome !== undefined &&
             !['completed_structured', 'completed_unstructured', 'incomplete', 'unknown']
               .includes(analysis.reductionOutcome))) {
          _invalidSnapshot('function_restoration.analysis is invalid');
        }
      }
    }
  }

  function _validateDocumentContext(documentContext) {
    if (!_isObject(documentContext)) _invalidSnapshot('document context is missing');
    ['title', 'sourceFile', 'filename', 'functionName', 'mode'].forEach(function(key) {
      _requireString(documentContext[key], 'document.' + key);
    });
    if (Object.prototype.hasOwnProperty.call(documentContext, 'projectTitle')) {
      _requireString(documentContext.projectTitle, 'document.projectTitle');
    }
    if (Object.prototype.hasOwnProperty.call(documentContext, 'sidebarVisible') &&
        typeof documentContext.sidebarVisible !== 'boolean') {
      _invalidSnapshot('document.sidebarVisible must be a boolean');
    }
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
          if (metadata.call_results !== undefined) {
            _validateCallResultRecords(metadata.call_results, recordDescription + '.metadata.call_results', record.id);
          }
          if (metadata.function_return_evidence !== undefined) {
            _validateFunctionReturnEvidence(
              metadata.function_return_evidence,
              recordDescription + '.metadata.function_return_evidence'
            );
          }
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
    const hasReductionOutcome = Object.prototype.hasOwnProperty.call(documentContext, 'reductionOutcome');
    if (hasReductionOutcome) {
      if (!['completed_structured', 'completed_unstructured', 'incomplete', 'unknown']
        .includes(documentContext.reductionOutcome)) {
        _invalidSnapshot('document.reductionOutcome is invalid');
      }
      if (typeof documentContext.finalSmAvailable !== 'boolean') {
        _invalidSnapshot('document.finalSmAvailable must be a boolean');
      }
      _requireFiniteNumber(
        documentContext.accumulatedReductionWeight,
        'document.accumulatedReductionWeight'
      );
      if (documentContext.incompleteReason !== undefined &&
          documentContext.incompleteReason !== null &&
          typeof documentContext.incompleteReason !== 'string') {
        _invalidSnapshot('document.incompleteReason must be a string or null');
      }
      if (documentContext.reductionOutcome === 'incomplete') {
        if (documentContext.finalSmAvailable ||
            (documentContext.finalSm !== undefined && documentContext.finalSm !== null)) {
          _invalidSnapshot('incomplete reduction cannot include a final SM');
        }
        if (typeof documentContext.incompleteReason !== 'string' || !documentContext.incompleteReason) {
          _invalidSnapshot('incomplete reduction requires an explanation');
        }
      } else if (documentContext.reductionOutcome === 'unknown') {
        if (documentContext.finalSmAvailable ||
            (documentContext.finalSm !== undefined && documentContext.finalSm !== null)) {
          _invalidSnapshot('unknown reduction status cannot claim a final SM');
        }
      } else if (!documentContext.finalSmAvailable ||
                 typeof documentContext.finalSm !== 'number' ||
                 !Number.isFinite(documentContext.finalSm)) {
        _invalidSnapshot('completed reduction must include its final SM');
      }
    }
    if (documentContext.finalSm !== undefined && documentContext.finalSm !== null) {
      _requireFiniteNumber(documentContext.finalSm, 'document.finalSm');
    } else if (documentContext.finalSm === null && !hasReductionOutcome) {
      _invalidSnapshot('document.finalSm cannot be null without a Reduction Outcome');
    }
    if (documentContext.finalSmAvailable !== undefined &&
        typeof documentContext.finalSmAvailable !== 'boolean') {
      _invalidSnapshot('document.finalSmAvailable must be a boolean');
    }
    if (documentContext.fullyReducible !== undefined && typeof documentContext.fullyReducible !== 'boolean') {
      _invalidSnapshot('document.fullyReducible must be a boolean');
    }
  }

  function _validateFunctionReferences(snapshot) {
    const functionRecords = new Map();
    const references = [];
    const visited = new WeakSet();

    function visit(value, path) {
      if (Array.isArray(value)) {
        value.forEach(function(item, index) { visit(item, path + '[' + index + ']'); });
        return;
      }
      if (!_isObject(value) || visited.has(value)) return;
      visited.add(value);
      if (Object.prototype.hasOwnProperty.call(value, 'function_ref')) {
        const reference = value.function_ref;
        if (typeof reference !== 'string' || reference.length === 0) {
          _invalidSnapshot(path + '.function_ref must be a non-empty string');
        }
        references.push({ reference: reference, path: path + '.function_ref' });
      }
      if (Object.prototype.hasOwnProperty.call(value, 'function_metadata_registry')) {
        const registry = value.function_metadata_registry;
        if (!_isObject(registry)) _invalidSnapshot(path + '.function_metadata_registry must be an object');
        Object.keys(registry).forEach(function(reference) {
          const record = registry[reference];
          const recordPath = path + '.function_metadata_registry.' + reference;
          if (!reference) _invalidSnapshot(path + '.function_metadata_registry contains an empty reference');
          if (!_isObject(record)) _invalidSnapshot(recordPath + ' must be an object');
          ['function_name', 'source_file', 'qualified_name'].forEach(function(key) {
            _requireString(record[key], recordPath + '.' + key);
          });
          const definition = record.definition_location;
          if (!_isObject(definition) || !Number.isInteger(definition.line) || definition.line < 1 ||
              (definition.column !== null && definition.column !== undefined &&
               (!Number.isInteger(definition.column) || definition.column < 0))) {
            _invalidSnapshot(recordPath + '.definition_location is invalid');
          }
          if (!['complete', 'unknown', 'no_normal_return', 'not_applicable'].includes(record.analysis_status)) {
            _invalidSnapshot(recordPath + '.analysis_status is invalid');
          }
          if (!['generator', 'async_generator', 'async_function'].includes(record.function_kind) &&
              record.function_kind !== undefined) {
            _invalidSnapshot(recordPath + '.function_kind is invalid');
          }
          if (!Array.isArray(record.inferred) || !Array.isArray(record.inferred_types) ||
              !Array.isArray(record.observed) || !Array.isArray(record.observed_types)) {
            _invalidSnapshot(recordPath + ' has invalid return metadata');
          }
          ['inferred_types', 'observed_types'].forEach(function(key) {
            if (record[key].some(function(value) { return typeof value !== 'string'; })) {
              _invalidSnapshot(recordPath + '.' + key + ' must contain strings');
            }
          });
          if (record.declared !== null && record.declared !== undefined &&
              (!_isObject(record.declared) || typeof record.declared.expression !== 'string' ||
               typeof record.declared.provenance !== 'string')) {
            _invalidSnapshot(recordPath + '.declared is invalid');
          }
          if (record.function_kind !== undefined) {
            if (!_isObject(record.roles)) _invalidSnapshot(recordPath + '.roles must be an object');
            const requiredRoles = record.function_kind === 'async_function'
              ? ['immediate', 'awaited'] : ['immediate', 'yielded', 'completion'];
            requiredRoles.forEach(function(roleName) {
              const role = record.roles[roleName];
              const rolePath = recordPath + '.roles.' + roleName;
              if (!_isObject(role) ||
                  !['complete', 'unknown', 'no_normal_return', 'not_applicable'].includes(role.analysis_status) ||
                  !Array.isArray(role.inferred) || !Array.isArray(role.observed) ||
                  !Array.isArray(role.inferred_types) || !Array.isArray(role.observed_types) ||
                  role.inferred_types.some(function(value) { return typeof value !== 'string'; }) ||
                  role.observed_types.some(function(value) { return typeof value !== 'string'; })) {
                _invalidSnapshot(rolePath + ' is invalid');
              }
              if (role.declared !== null && role.declared !== undefined &&
                  (!_isObject(role.declared) || typeof role.declared.expression !== 'string' ||
                   typeof role.declared.provenance !== 'string')) {
                _invalidSnapshot(rolePath + '.declared is invalid');
              }
            });
          } else if (record.roles !== undefined) {
            _invalidSnapshot(recordPath + '.roles requires function_kind');
          }
          functionRecords.set(reference, record);
          visit(record, recordPath);
        });
      }
      Object.keys(value).forEach(function(key) { visit(value[key], path + '.' + key); });
    }

    visit(snapshot, 'snapshot');
    references.forEach(function(item) {
      if (!functionRecords.has(item.reference)) {
        _invalidSnapshot(item.path + ' does not resolve to a function metadata record');
      }
    });
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

    // Older viewers saved callee-local call-result IDs on cloned inline transitions.
    // Repair only an exact local-suffix match; unrelated ownership mismatches stay invalid.
    _migrateLegacyInlineCallResultIds(snapshot);

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
    _validateFunctionReferences(snapshot);

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
    const htmlFilename = opts.htmlFilename || (opts.document && opts.document.htmlFilename) || title;
    const filename = opts.filename || getFoldStateSnapshotFilename(htmlFilename);
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
