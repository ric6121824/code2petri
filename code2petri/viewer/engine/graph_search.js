/**
 * Search the live graph and the exact interiors retained by its Folded Components.
 * Occurrences carry node identity separately from the restoration-owner path so
 * callers can re-resolve a result after the Cytoscape graph has been rebuilt.
 */
(function(root, factory) {
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = factory();
  } else if (root) {
    Object.assign(root, factory());
  }
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this), function() {
  const MATCH_CLASS = 'search-match';
  const ACTIVE_CLASS = 'search-active';

  function hasOwn(object, key) {
    return Boolean(object && Object.prototype.hasOwnProperty.call(object, key));
  }

  function restorationRecord(data) {
    if (!data || typeof data !== 'object') return null;
    const record = hasOwn(data, 'consumedSubnet') ? data.consumedSubnet :
      (hasOwn(data, 'consumedSubgraph') ? data.consumedSubgraph : null);
    return record && typeof record === 'object' && !Array.isArray(record) ? record : null;
  }

  function definitionData(definition) {
    return definition && definition.group === 'nodes' && definition.data &&
      typeof definition.data === 'object' ? definition.data : null;
  }

  function definitionClasses(definition) {
    if (!definition) return '';
    return Array.isArray(definition.classes) ? definition.classes.join(' ') : String(definition.classes || '');
  }

  function nodeDisplayName(data, id) {
    if (!data) return String(id || '');
    const value = data.custom_name || data.label || data.original_label || data.raw_label ||
      data.function_name || id;
    return String(value || id || '');
  }

  function lineNumber(data) {
    if (!data || typeof data !== 'object') return null;
    const line = data.source_line !== undefined && data.source_line !== null && data.source_line !== ''
      ? data.source_line
      : data.line_number;
    return line === undefined || line === null || line === '' ? null : line;
  }

  function sourceLocation(data) {
    const line = lineNumber(data);
    const file = data && typeof data.file === 'string' && data.file ? data.file : null;
    if (line === null && file === null) return null;
    return { file: file, line: line };
  }

  function isOpaqueDefinition(data, classes) {
    return Boolean(data && (data.is_opaque === true || data.opaque === true)) ||
      /(?:^|\s)(?:component|opaque)(?:\s|$)/.test(String(classes || ''));
  }

  function occurrenceKey(ownerPath, nodeId) {
    return JSON.stringify([ownerPath, String(nodeId)]);
  }

  class ViewerGraphSearch {
    constructor(options) {
      const opts = options || {};
      if (!opts.cy || typeof opts.cy.nodes !== 'function') {
        throw new Error('Viewer Graph Search requires a Cytoscape instance');
      }
      this.cy = opts.cy;
      this.engine = opts.engine || null;
      this.unfoldComponent = typeof opts.unfoldComponent === 'function' ? opts.unfoldComponent : null;
    }

    _liveNode(id) {
      if (typeof id !== 'string' || typeof this.cy.getElementById !== 'function') return null;
      const node = this.cy.getElementById(id);
      return node && node.length > 0 && node.isNode() ? node : null;
    }

    _isCollapsedChild(node) {
      return Boolean(node && typeof node.hasClass === 'function' &&
        (node.hasClass('collapsed-child') || node.data('is_collapsed_child') === true));
    }

    _visibleRepresentative(nodeId, ownerPath) {
      const candidates = [nodeId].concat(ownerPath || []);
      const visited = new Set();
      for (let candidateIndex = 0; candidateIndex < candidates.length; candidateIndex++) {
        let node = this._liveNode(candidates[candidateIndex]);
        while (node && !visited.has(node.id())) {
          visited.add(node.id());
          if (this._isCollapsedChild(node)) {
            const parentId = node.data('parent');
            const parent = parentId ? this._liveNode(String(parentId)) : null;
            if (parent && parent.visible() &&
                (parent.hasClass('collapsed-compound') || parent.data('is_collapsed_compound') === true)) {
              return parent.id();
            }
          } else if (typeof node.visible !== 'function' || node.visible()) {
            return node.id();
          }
          const parentId = node.data('parent');
          node = parentId ? this._liveNode(String(parentId)) : null;
        }
      }
      return null;
    }

    _makeOccurrence(data, classes, ownerPath, ownerNames, liveNode) {
      const nodeId = data && data.id !== undefined && data.id !== null ? String(data.id) : '';
      if (!nodeId) return null;
      const isCollapsedChild = this._isCollapsedChild(liveNode);
      const visible = ownerPath.length === 0 && Boolean(liveNode) &&
        (!isCollapsedChild && (typeof liveNode.visible !== 'function' || liveNode.visible()) ||
         isCollapsedChild && Boolean(this._visibleRepresentative(nodeId, [])));
      const visibleNodeId = visible
        ? (isCollapsedChild ? this._visibleRepresentative(nodeId, []) : nodeId)
        : this._visibleRepresentative(nodeId, ownerPath);
      const names = ownerNames.slice();
      const enclosingFunction = data.enclosing_function || data.function_name;
      if (enclosingFunction && names[names.length - 1] !== String(enclosingFunction)) {
        names.push(String(enclosingFunction));
      }
      return {
        occurrenceId: occurrenceKey(ownerPath, nodeId),
        nodeId: nodeId,
        ownerPath: ownerPath.slice(),
        visible: visible,
        visibleNodeId: visibleNodeId,
        canReveal: ownerPath.length > 0 && Boolean(visibleNodeId) && this._canRestorePath(nodeId, ownerPath),
        label: nodeDisplayName(data, nodeId),
        contextPath: names,
        sourceLocation: sourceLocation(data),
        classes: classes || '',
        searchText: [
          data.label, data.original_label, data.raw_label, data.function_name, data.custom_name,
          data.resolved_to, data.id
        ].filter(function(value) { return value !== undefined && value !== null; }).map(String)
      };
    }

    _canRestorePath(nodeId, ownerPath) {
      if (!this.engine || typeof this.engine._unfoldSingleOpaqueTransition !== 'function' ||
          !Array.isArray(ownerPath) || ownerPath.length === 0) return false;
      const firstOwner = this._liveNode(ownerPath[0]);
      let ownerData = firstOwner ? firstOwner.data() : null;
      let ownerClasses = firstOwner ? firstOwner.classes().join(' ') : '';
      for (let index = 0; index < ownerPath.length; index++) {
        if (!ownerData || String(ownerData.id) !== String(ownerPath[index]) ||
            !isOpaqueDefinition(ownerData, ownerClasses)) return false;
        const record = restorationRecord(ownerData);
        if (!record || this._recordChildren(record).length === 0) return false;
        const nextId = index + 1 < ownerPath.length ? ownerPath[index + 1] : nodeId;
        const nextDefinition = this._findDefinition(record, nextId);
        if (!nextDefinition) return false;
        ownerData = definitionData(nextDefinition);
        ownerClasses = definitionClasses(nextDefinition);
      }
      return true;
    }

    _recordChildren(record) {
      if (!record || typeof record !== 'object') return [];
      const children = [];
      const byId = new Map();
      ['consumedCompounds', 'nodes'].forEach(function(key) {
        const values = record[key];
        if (!Array.isArray(values)) return;
        values.forEach(function(definition) {
          const data = definitionData(definition);
          if (!data || data.id === undefined || data.id === null) return;
          const id = String(data.id);
          if (!byId.has(id)) {
            byId.set(id, definition);
            children.push(definition);
          }
        });
      });
      return children;
    }

    getOccurrences() {
      const occurrences = new Map();
      const add = (data, classes, ownerPath, ownerNames, liveNode) => {
        const occurrence = this._makeOccurrence(data, classes, ownerPath, ownerNames, liveNode);
        if (!occurrence) return;
        // Snapshot validation gives node IDs document-wide uniqueness. The full
        // owner path remains part of the occurrence identity as an integrity check.
        if (!occurrences.has(occurrence.occurrenceId)) occurrences.set(occurrence.occurrenceId, occurrence);
      };

      const visitRecord = (data, nodeId, ownerPath, ownerNames, ancestry) => {
        const record = restorationRecord(data);
        if (!record || ancestry.has(record)) return;
        const nextAncestry = new Set(ancestry);
        nextAncestry.add(record);
        const nextOwnerPath = ownerPath.concat(String(nodeId));
        const nextOwnerNames = ownerNames.concat(nodeDisplayName(data, nodeId));
        this._recordChildren(record).forEach((definition) => {
          const childData = definitionData(definition);
          const childId = String(childData.id);
          add(childData, definitionClasses(definition), nextOwnerPath, nextOwnerNames, null);
          visitRecord(childData, childId, nextOwnerPath, nextOwnerNames, nextAncestry);
        });
      };

      this.cy.nodes().forEach((node) => {
        const data = node.data();
        const ownerPath = [];
        add(data, node.classes().join(' '), ownerPath, [], node);
        visitRecord(data, node.id(), ownerPath, [], new Set());
      });

      return Array.from(occurrences.values()).sort(function(a, b) {
        return a.occurrenceId.localeCompare(b.occurrenceId);
      });
    }

    findMatches(query) {
      const needle = String(query === undefined || query === null ? '' : query).toLowerCase();
      if (!needle) return [];
      return this.getOccurrences().filter(function(occurrence) {
        return occurrence.searchText.some(function(value) {
          return value.toLowerCase().includes(needle);
        });
      }).map(function(occurrence) {
        const result = Object.assign({}, occurrence);
        delete result.searchText;
        return result;
      });
    }

    resolveOccurrence(occurrenceId) {
      if (typeof occurrenceId !== 'string') return null;
      return this.getOccurrences().find(function(item) { return item.occurrenceId === occurrenceId; }) || null;
    }

    applyHighlights(occurrences, activeOccurrenceId) {
      this.cy.nodes('.' + MATCH_CLASS + ', .' + ACTIVE_CLASS).forEach(function(node) {
        node.removeClass(MATCH_CLASS + ' ' + ACTIVE_CLASS);
      });
      const active = (occurrences || []).find(function(item) { return item.occurrenceId === activeOccurrenceId; });
      (occurrences || []).forEach((item) => {
        const node = item.visibleNodeId ? this._liveNode(item.visibleNodeId) : null;
        if (!node) return;
        node.addClass(MATCH_CLASS);
        if (active && active.visibleNodeId === item.visibleNodeId) node.addClass(ACTIVE_CLASS);
      });
    }

    locate(occurrenceId) {
      const occurrence = this.resolveOccurrence(occurrenceId);
      if (!occurrence) return { success: false, reason: 'This search result is no longer available in the current graph.' };
      const visibleNode = occurrence.visibleNodeId ? this._liveNode(occurrence.visibleNodeId) : null;
      if (!visibleNode || (typeof visibleNode.visible === 'function' && !visibleNode.visible() &&
          !this._isCollapsedChild(visibleNode))) {
        return { success: false, reason: 'No visible graph node represents this search result.' };
      }
      const zoom = typeof this.cy.zoom === 'function' ? this.cy.zoom() : null;
      visibleNode.addClass(MATCH_CLASS + ' ' + ACTIVE_CLASS);
      this.cy.center(visibleNode);
      if (zoom !== null && typeof this.cy.zoom === 'function' && this.cy.zoom() !== zoom) this.cy.zoom(zoom);
      return { success: true, occurrenceId: occurrence.occurrenceId, nodeId: occurrence.nodeId, visibleNodeId: visibleNode.id() };
    }

    _findDefinition(record, nodeId) {
      return this._recordChildren(record).find(function(definition) {
        const data = definitionData(definition);
        return data && String(data.id) === String(nodeId);
      }) || null;
    }

    _validateRestoration(record, ownerId) {
      if (!record || typeof record !== 'object') {
        throw new Error('Folded Component ' + ownerId + ' no longer retains a restorable interior.');
      }
      const children = this._recordChildren(record);
      if (children.length === 0) {
        throw new Error('Folded Component ' + ownerId + ' has no retained nodes to reveal.');
      }
      return children;
    }

    _validateRestoredContents(record, ownerId) {
      this._recordChildren(record).forEach((definition) => {
        const data = definitionData(definition);
        if (!data || !this._liveNode(String(data.id))) {
          throw new Error('Reveal could not restore node ' + (data && data.id ? data.id : 'from ' + ownerId) + '.');
        }
      });
      (Array.isArray(record.internalEdges) ? record.internalEdges : []).forEach((edge) => {
        if (!edge || !edge.data || !edge.data.id) return;
        const restored = this.cy.getElementById(String(edge.data.id));
        if (!restored.length || restored.source().id() !== String(edge.data.source) ||
            restored.target().id() !== String(edge.data.target)) {
          throw new Error('Reveal could not restore arc ' + edge.data.id + ' from ' + ownerId + '.');
        }
      });
      const expectedBoundaryArcs = [];
      (Array.isArray(record.boundaryInArcs) ? record.boundaryInArcs : []).forEach(function(arc, index) {
        const targetId = arc && (arc.originalTargetId || (arc.targetId !== ownerId ? arc.targetId : null));
        if (arc && targetId) expectedBoundaryArcs.push({
          arc: arc, index: index, sourceId: arc.sourceId, targetId: targetId
        });
      });
      (Array.isArray(record.boundaryOutArcs) ? record.boundaryOutArcs : []).forEach(function(arc, index) {
        const sourceId = arc && (arc.originalSourceId || (arc.sourceId !== ownerId ? arc.sourceId : null));
        if (arc && sourceId) expectedBoundaryArcs.push({
          arc: arc, index: index, sourceId: sourceId, targetId: arc.targetId
        });
      });
      expectedBoundaryArcs.forEach((expected) => {
        if (!this._liveNode(String(expected.sourceId)) || !this._liveNode(String(expected.targetId))) {
          throw new Error('Reveal could not reconnect a boundary arc from ' + ownerId + ' because an endpoint is missing.');
        }
        const arc = expected.arc;
        const baseId = String(arc.edgeId || arc.id ||
          ('arc_restore_' + expected.sourceId + '_' + expected.targetId + '_' + expected.index));
        const restored = this.cy.edges().filter(function(edge) {
          const edgeId = edge.id();
          return edge.source().id() === String(expected.sourceId) &&
            edge.target().id() === String(expected.targetId) &&
            (edgeId === baseId || edgeId.indexOf(baseId + '_') === 0);
        });
        if (restored.length === 0) {
          throw new Error('Reveal could not reconnect boundary arc ' + baseId + ' from ' + ownerId + '.');
        }
      });
    }

    reveal(occurrenceId) {
      const occurrence = this.resolveOccurrence(occurrenceId);
      if (!occurrence) throw new Error('This search result is stale; search the current graph again before revealing it.');
      if (occurrence.visible || !occurrence.canReveal || occurrence.ownerPath.length === 0) {
        throw new Error('This search result has no hidden retained interior to reveal.');
      }
      if (!this.engine || typeof this.engine._unfoldSingleOpaqueTransition !== 'function') {
        throw new Error('Component-local restoration is unavailable for this viewer.');
      }

      // Re-resolve the complete current owner chain before the first mutation.
      let expectedOwner = null;
      for (let index = 0; index < occurrence.ownerPath.length; index++) {
        const ownerId = occurrence.ownerPath[index];
        const liveOwner = this._liveNode(ownerId);
        const data = liveOwner ? liveOwner.data() : (expectedOwner && expectedOwner.data);
        if (!data || String(data.id) !== ownerId) {
          throw new Error('Reveal owner ' + ownerId + ' is no longer present on this occurrence path.');
        }
        const record = restorationRecord(data);
        const children = this._validateRestoration(record, ownerId);
        const nextId = index + 1 < occurrence.ownerPath.length ? occurrence.ownerPath[index + 1] : occurrence.nodeId;
        const nextDefinition = this._findDefinition(record, nextId);
        if (!nextDefinition) {
          throw new Error('Folded Component ' + ownerId + ' no longer contains ' + nextId + ' on this result path.');
        }
        expectedOwner = { data: definitionData(nextDefinition), record: record, children: children };
      }

      for (let index = 0; index < occurrence.ownerPath.length; index++) {
        const ownerId = occurrence.ownerPath[index];
        const ownerNode = this._liveNode(ownerId);
        if (!ownerNode) throw new Error('Reveal owner ' + ownerId + ' was not restored from its parent Folded Component.');
        const record = restorationRecord(ownerNode.data());
        this._validateRestoration(record, ownerId);
        const result = this.unfoldComponent
          ? this.unfoldComponent(ownerNode)
          : this.engine._unfoldSingleOpaqueTransition(ownerNode);
        if (!result || result.success === false) throw new Error('Failed to restore Folded Component ' + ownerId + '.');
        if (!this.unfoldComponent && typeof this.engine._updateCollapsedCompoundStates === 'function') {
          this.engine._updateCollapsedCompoundStates();
        }
        this._validateRestoredContents(record, ownerId);

        const remainingOwners = occurrence.ownerPath.slice(index + 1);
        const stillReachable = this.getOccurrences().some((item) => item.nodeId === occurrence.nodeId &&
          JSON.stringify(item.ownerPath) === JSON.stringify(remainingOwners));
        if (!stillReachable) {
          const targetNode = this._liveNode(occurrence.nodeId);
          if (!(remainingOwners.length === 0 && targetNode)) {
            throw new Error('Reveal lost the exact search result after restoring ' + ownerId + '.');
          }
        }
      }

      const target = this._liveNode(occurrence.nodeId);
      const visibleNodeId = this._visibleRepresentative(occurrence.nodeId, []);
      const visibleNode = visibleNodeId ? this._liveNode(visibleNodeId) : null;
      if (!target || !visibleNode) throw new Error('Reveal did not make the exact result visibly available.');
      const currentOccurrence = this.getOccurrences().find(function(item) {
        return item.nodeId === occurrence.nodeId && item.visible;
      });
      if (!currentOccurrence || !this.locate(currentOccurrence.occurrenceId).success) {
        throw new Error('Reveal could not center the exact visible result.');
      }
      return { success: true, nodeId: occurrence.nodeId, visibleNodeId: visibleNodeId };
    }
  }

  return {
    ViewerGraphSearch: ViewerGraphSearch,
    SEARCH_MATCH_CLASS: MATCH_CLASS,
    SEARCH_ACTIVE_CLASS: ACTIVE_CLASS
  };
});
