/**
 * Live Fold Reduction Engine for code2petri.
 * Implements client-side Petri net reductions and SESE macro folds.
 */

(function(root, factory) {
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = factory();
  } else {
    const exports = factory();
    if (typeof window !== 'undefined') {
      Object.assign(window, exports);
    } else if (typeof globalThis !== 'undefined') {
      Object.assign(globalThis, exports);
    }
  }
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this), function() {
      class SESEInfrastructure {
        constructor(cy) {
          this.cy = cy;
        }

        _reachability(startNodeId, boundaryNodeId, getNeighbors) {
          const queue = [startNodeId];
          const nodes = new Set([startNodeId]);
          if (boundaryNodeId !== null && boundaryNodeId !== undefined) {
            nodes.add(boundaryNodeId);
          }
          while (queue.length > 0) {
            const currId = queue.shift();
            const neighbors = getNeighbors(currId);
            for (let i = 0; i < neighbors.length; i++) {
              const neighborId = neighbors[i];
              if (!nodes.has(neighborId)) {
                nodes.add(neighborId);
                queue.push(neighborId);
              }
            }
          }
          return nodes;
        }

        _forwardNeighbors(currId) {
          const node = this.cy.getElementById(currId);
          if (!node || node.length === 0) return [];
          return node.outgoers('edge').map(function(edge) {
            return edge.target().id();
          });
        }

        _backwardNeighbors(currId) {
          const node = this.cy.getElementById(currId);
          if (!node || node.length === 0) return [];
          return node.incomers('edge').map(function(edge) {
            return edge.source().id();
          });
        }

        forwardReachability(sourceId, sinkId) {
          const self = this;
          return this._reachability(sourceId, sinkId, function(currId) {
            return self._forwardNeighbors(currId);
          });
        }

        backwardReachability(sinkId, sourceId) {
          const self = this;
          return this._reachability(sinkId, sourceId, function(currId) {
            return self._backwardNeighbors(currId);
          });
        }

        isReachable(sourceId, sinkId) {
          if (sourceId === sinkId) return true;
          const self = this;
          return this._reachability(sourceId, null, function(currId) {
            return self._forwardNeighbors(currId);
          }).has(sinkId);
        }

        findSESENodes(sourceId, sinkId, minTransitions = 2) {
          if (sourceId === sinkId) return null;
          const srcNode = this.cy.getElementById(sourceId);
          const snkNode = this.cy.getElementById(sinkId);
          if (!srcNode || srcNode.length === 0 || !snkNode || snkNode.length === 0) {
            return null;
          }

          if (!this.isReachable(sourceId, sinkId)) {
            return null;
          }

          const fwd = this.forwardReachability(sourceId, sinkId);
          const bwd = this.backwardReachability(sinkId, sourceId);

          if (fwd.size !== bwd.size) return null;
          for (const nid of fwd) {
            if (!bwd.has(nid)) return null;
          }

          let transCount = 0;
          for (const nid of fwd) {
            const n = this.cy.getElementById(nid);
            if (n && n.length > 0 && n.hasClass('transition')) {
              transCount++;
            }
          }

          if (transCount >= minTransitions) {
            return fwd;
          }
          return null;
        }

        calculateSymmetryMultiplier(componentNodeIds, targetNodeIds = null, useSubnetDegrees = true) {
          const compSet = new Set(componentNodeIds);
          const targetSet = targetNodeIds ? new Set(targetNodeIds) : compSet;

          let splits = 0;
          let joins = 0;

          if (useSubnetDegrees) {
            const subnetOut = new Map();
            const subnetIn = new Map();

            compSet.forEach(function(sourceId) {
              const srcNode = this.cy.getElementById(sourceId);
              if (srcNode && srcNode.length > 0) {
                srcNode.outgoers('edge').forEach(function(edge) {
                  const tgtId = edge.target().id();
                  if (compSet.has(tgtId)) {
                    subnetOut.set(sourceId, (subnetOut.get(sourceId) || 0) + 1);
                    subnetIn.set(tgtId, (subnetIn.get(tgtId) || 0) + 1);
                  }
                });
              }
            }, this);

            targetSet.forEach(function(nid) {
              if ((subnetOut.get(nid) || 0) > 1) splits++;
              if ((subnetIn.get(nid) || 0) > 1) joins++;
            });
          } else {
            targetSet.forEach(function(nid) {
              const node = this.cy.getElementById(nid);
              if (node && node.length > 0) {
                if (node.outgoers('edge').length > 1) splits++;
                if (node.incomers('edge').length > 1) joins++;
              }
            }, this);
          }

          return Math.abs(splits - joins) + 1;
        }

        calculateSubnetSymmetry(componentNodeIds, useSubnetDegrees = true) {
          const compSet = new Set(componentNodeIds);
          const placeIds = [];
          const transIds = [];

          compSet.forEach(function(nid) {
            const node = this.cy.getElementById(nid);
            if (node && node.length > 0) {
              if (node.hasClass('place')) {
                placeIds.push(nid);
              } else if (node.hasClass('transition')) {
                transIds.push(nid);
              }
            }
          }, this);

          const diffP = this.calculateSymmetryMultiplier(compSet, placeIds, useSubnetDegrees);
          const diffT = this.calculateSymmetryMultiplier(compSet, transIds, useSubnetDegrees);

          return { diffP: diffP, diffT: diffT };
        }

        findAllSESECandidates(boundaryIds = null, minTransitions = 2) {
          let candidates;
          if (boundaryIds) {
            candidates = Array.from(boundaryIds);
          } else {
            candidates = this.cy.nodes('.place').map(function(n) { return n.id(); });
          }
          candidates.sort();

          const results = [];
          for (let i = 0; i < candidates.length; i++) {
            for (let j = 0; j < candidates.length; j++) {
              if (i === j) continue;
              const src = candidates[i];
              const snk = candidates[j];
              const sese = this.findSESENodes(src, snk, minTransitions);
              if (sese) {
                results.push({
                  sourceId: src,
                  sinkId: snk,
                  nodes: sese
                });
              }
            }
          }
          return results;
        }
      }

      // Phase 2.7 Live Fold Reduction Engine
      class LiveFoldReductionEngine {
        constructor(cy, options = {}) {
          this.cy = cy;
          this.stepCounter = 0;
          this.history = [];
          this.cfg = {
            sequence: options.sequence !== undefined ? options.sequence : 0.0,
            choice: options.choice !== undefined ? options.choice : 1.0,
            loop: options.loop !== undefined ? options.loop : 3.0,
            marked_graph: options.marked_graph !== undefined ? options.marked_graph : 2.0,
            state_machine: options.state_machine !== undefined ? options.state_machine : 2.0,
            well_structured: options.well_structured !== undefined ? options.well_structured : 2.0,
            unstructured: options.unstructured !== undefined ? options.unstructured : 7.0
          };
          this.sese = new SESEInfrastructure(cy);
          this.rememberedCustomNames = new Map();
        }

        _getNodeAncestors(nodeId) {
          const ancestors = [];
          let curr = nodeId;
          const visited = new Set();
          while (curr && !visited.has(curr)) {
            visited.add(curr);
            ancestors.push(curr);
            const node = this.cy.getElementById(curr);
            if (!node || node.length === 0) break;
            curr = node.data('parent') || null;
          }
          return ancestors;
        }

        _findLowestCommonAncestor(parent1Id, parent2Id) {
          if (!parent1Id || !parent2Id) return null;
          if (parent1Id === parent2Id) return parent1Id;
          const ancestors1 = this._getNodeAncestors(parent1Id);
          const ancestors2 = new Set(this._getNodeAncestors(parent2Id));
          for (const anc of ancestors1) {
            if (ancestors2.has(anc)) {
              return anc;
            }
          }
          return null;
        }

        _findLowestCommonAncestorMultiple(parentIds) {
          if (!parentIds || !Array.isArray(parentIds)) return null;
          const valid = parentIds.filter(Boolean);
          if (valid.length === 0) return null;
          let lca = valid[0];
          for (let i = 1; i < valid.length; i++) {
            lca = this._findLowestCommonAncestor(lca, valid[i]);
            if (!lca) return null;
          }
          return lca;
        }


        _consumedSubnetKey(consumedSubnet) {
          if (!consumedSubnet) return null;
          if (consumedSubnet.consumedPlaceId) {
            const consumedPlaceKey = String(consumedSubnet.consumedPlaceId);
            return `place::${consumedPlaceKey}`;
          }
          if (consumedSubnet.componentType === 'Choice') {
            const consumedTransKey = Array.isArray(consumedSubnet.consumedTransIds)
              ? consumedSubnet.consumedTransIds.slice().sort().join('+')
              : '';
            const consumedPlaceKey = `${consumedSubnet.sourcePlaceId}::${consumedSubnet.targetPlaceId}`;
            return `choice::${consumedPlaceKey}::${consumedTransKey}`;
          }
          if (Array.isArray(consumedSubnet.consumedTransIds) && consumedSubnet.consumedTransIds.length > 0) {
            const consumedTransKey = consumedSubnet.consumedTransIds.slice().sort().join('+');
            return `${consumedSubnet.componentType || 'subnet'}::${consumedTransKey}`;
          }
          if (consumedSubnet.opaqueId) {
            return `opaque::${consumedSubnet.opaqueId}`;
          }
          return null;
        }

        static generateTauBadgeSvg(tau) {
          if (tau === undefined || tau === null) return '';
          const tauVal = Number(tau);
          const tauStr = Number.isInteger(tauVal) ? tauVal.toFixed(1) : String(tauVal);
          const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="50" height="18" viewBox="0 0 50 18">' +
            '<rect x="1" y="1" width="48" height="16" rx="8" fill="#24292e" stroke="#61afef" stroke-width="1.5"/>' +
            '<text x="25" y="12.5" font-family="ui-monospace, monospace" font-size="10" font-weight="bold" fill="#ffffff" text-anchor="middle">τ=' + tauStr + '</text>' +
            '</svg>';
          return 'data:image/svg+xml;utf8,' + encodeURIComponent(svg);
        }

        _createOpaqueComponentNode(optionsOrId, ...legacyArgs) {
          let opts = {};
          if (typeof optionsOrId === 'object' && optionsOrId !== null) {
            opts = optionsOrId;
          } else {
            opts = {
              opaqueId: optionsOrId,
              label: legacyArgs[0],
              rawLabel: legacyArgs[1],
              tau: legacyArgs[2],
              omega: legacyArgs[3],
              componentType: legacyArgs[4],
              parentId: legacyArgs[5],
              consumedSubnet: legacyArgs[6],
              position: legacyArgs[7] || null
            };
          }
          const consumedSubnet = opts.consumedSubnet || {};
          const opaqueId = opts.opaqueId || consumedSubnet.opaqueId;
          const tau = opts.tau !== undefined ? opts.tau : consumedSubnet.tau;
          const omega = opts.omega !== undefined ? opts.omega : consumedSubnet.omega;
          const componentType = opts.componentType || consumedSubnet.componentType;
          const parentId = opts.parentId !== undefined ? opts.parentId : (consumedSubnet.parentCompound || null);
          const rawLabel = opts.rawLabel || opts.label || opaqueId;
          let label = opts.label || opaqueId;
          const position = opts.position || null;

          // Check if there is a remembered custom name from a previous rename
          let customName = opts.customName || null;
          if (!customName && consumedSubnet) {
            if (consumedSubnet.custom_name) {
              customName = consumedSubnet.custom_name;
            }
            if (!customName) {
              const subnetKey = this._consumedSubnetKey(consumedSubnet);
              if (subnetKey && this.rememberedCustomNames.has(subnetKey)) {
                customName = this.rememberedCustomNames.get(subnetKey);
              }
            }
          }
          if (!customName && this.rememberedCustomNames.has(opaqueId)) {
            customName = this.rememberedCustomNames.get(opaqueId);
          }

          if (customName) {
            label = customName;
          }

          let minLine = null;
          let maxLine = null;
          if (Array.isArray(consumedSubnet.nodes)) {
            consumedSubnet.nodes.forEach(function(n) {
              if (n && n.data) {
                const rawLine = n.data.source_line !== undefined && n.data.source_line !== null
                  ? n.data.source_line
                  : (n.data.line_number !== undefined && n.data.line_number !== null ? n.data.line_number : null);
                if (rawLine !== null && rawLine !== '') {
                  const line = Number(rawLine);
                  if (!isNaN(line) && line > 0) {
                    if (minLine === null || line < minLine) minLine = line;
                    if (maxLine === null || line > maxLine) maxLine = line;
                  }
                }
              }
            });
          }

          let sourceLine = null;
          if (minLine !== null) {
            sourceLine = minLine === maxLine ? String(minLine) : `${minLine}–${maxLine}`;
          }

          const newNodeData = {
            id: opaqueId,
            label: label,
            raw_label: customName || rawLabel,
            type: 'Opaque Transition',
            component_type: componentType,
            is_opaque: true,
            opaque: true,
            step_number: this.stepCounter,
            tau: tau,
            omega: omega,
            source_line: sourceLine,
            line_number: minLine !== null ? String(minLine) : null,
            badge_svg: LiveFoldReductionEngine.generateTauBadgeSvg(tau),
            consumedSubnet: consumedSubnet,
            consumedSubgraph: consumedSubnet
          };
          if (customName) {
            newNodeData.custom_name = customName;
          }
          if (parentId) {
            newNodeData.parent = parentId;
          }

          const nodeDef = {
            group: 'nodes',
            data: newNodeData,
            classes: 'transition opaque component'
          };
          if (position) {
            nodeDef.position = Object.assign({}, position);
          }

          const addedNode = this.cy.add(nodeDef);
          this._updateCollapsedCompoundStates();
          return addedNode;
        }

        calculateSMScore() {
          let sm = 0.0;
          this.cy.nodes('.transition').forEach(function(t) {
            const tau = parseFloat(t.data('tau'));
            sm += isNaN(tau) ? 1.0 : tau;
          });
          return parseFloat(sm.toFixed(2));
        }

        isCollapsedCompound(node) {
          if (!node || typeof node.hasClass !== 'function') return false;
          return node.hasClass('collapsed-compound') ||
            node.data('is_collapsed_compound') === true ||
            Boolean(node.data('collapsed_opaque_id'));
        }

        isOpaqueTransition(node) {
          if (!node || typeof node.hasClass !== 'function') return false;
          return node.data('is_opaque') === true ||
            node.data('opaque') === true ||
            node.hasClass('component') ||
            node.hasClass('opaque');
        }

        isCollapsedChild(node) {
          if (!node || typeof node.hasClass !== 'function') return false;
          return node.hasClass('collapsed-child') || node.data('is_collapsed_child') === true;
        }

        _getCompoundFunctionName(compoundNode) {
          if (!compoundNode) return '';
          let fnName = compoundNode.data('function_name');
          if (!fnName) {
            fnName = compoundNode.data('label') || compoundNode.id();
          }
          fnName = String(fnName).replace(/\(\)$/, '').trim();
          if (fnName.startsWith('compound_')) {
            fnName = fnName.replace(/^compound_/, '');
          }
          return fnName;
        }

        _updateCollapsedCompoundStates(specificParentId = null) {
          const self = this;
          let targetCompounds;
          if (specificParentId) {
            const specificNode = this.cy.getElementById(specificParentId);
            targetCompounds = (specificNode && specificNode.length > 0) ? specificNode : this.cy.collection();
          } else {
            targetCompounds = this.cy.nodes('.compound');
          }

          targetCompounds.forEach(function(compoundNode) {
            const cId = compoundNode.id();
            const children = self.cy.nodes().filter(function(n) {
              return n.data('parent') === cId && n.inside();
            });

            if (children.length === 1) {
              const onlyChild = children[0];
              if (self.isOpaqueTransition(onlyChild)) {
                // Transition to Collapsed Compound State automatically
                compoundNode.addClass('collapsed-compound');
                const opaqueId = onlyChild.id();
                const fnName = self._getCompoundFunctionName(compoundNode);

                if (!compoundNode.data('original_label')) {
                  compoundNode.data('original_label', compoundNode.data('label') || compoundNode.id());
                }

                const compoundCustom = compoundNode.data('custom_name');
                const childCustom = onlyChild.data('custom_name') || (self.rememberedCustomNames && self.rememberedCustomNames.get(opaqueId));
                const labelSuffix = childCustom || opaqueId;
                const collapsedLabel = compoundCustom || `${fnName} (${labelSuffix})`;
                compoundNode.data('collapsed_label', collapsedLabel);
                compoundNode.data('label', collapsedLabel);
                compoundNode.data('collapsed_opaque_id', opaqueId);
                compoundNode.data('is_collapsed_compound', true);

                // Hide internal child node
                onlyChild.addClass('collapsed-child');
                onlyChild.data('is_collapsed_child', true);
                if (!onlyChild.data('original_label')) {
                  onlyChild.data('original_label', onlyChild.data('label') || onlyChild.id());
                }
                onlyChild.data('label', '');
                return;
              }
            }

            // If not meeting criteria and was collapsed, uncollapse (e.g. after unfold or reset)
            if (self.isCollapsedCompound(compoundNode)) {
              compoundNode.removeClass('collapsed-compound');
              compoundNode.removeData('collapsed_opaque_id');
              compoundNode.removeData('is_collapsed_compound');
              compoundNode.removeData('collapsed_label');
              if (compoundNode.data('original_label')) {
                compoundNode.data('label', compoundNode.data('original_label'));
                compoundNode.removeData('original_label');
              } else {
                const origFn = compoundNode.data('function_name');
                if (origFn) {
                  compoundNode.data('label', origFn.endsWith('()') ? origFn : (origFn + '()'));
                }
              }
            }

            // Restore any children that might have collapsed-child class if > 1 children
            if (children.length > 1) {
              children.forEach(function(child) {
                if (self.isCollapsedChild(child)) {
                  child.removeClass('collapsed-child');
                  child.removeData('is_collapsed_child');
                  if (child.data('original_label')) {
                    child.data('label', child.data('original_label'));
                    child.removeData('original_label');
                  }
                }
              });
            }
          });
        }

        renameNode(nodeOrId, newName) {
          const node = typeof nodeOrId === 'string' ? this.cy.getElementById(nodeOrId) : nodeOrId;
          if (!node || node.length === 0) return false;
          const trimmed = (newName || '').trim();
          if (!trimmed) return false;

          node.data('label', trimmed);
          node.data('raw_label', trimmed);
          node.data('custom_name', trimmed);

          // If node itself is a collapsed compound, also update collapsed_label and internal opaque child
          if (this.isCollapsedCompound(node)) {
            node.data('collapsed_label', trimmed);
            const childId = node.data('collapsed_opaque_id');
            if (childId) {
              const childNode = this.cy.getElementById(childId);
              if (childNode && childNode.length > 0) {
                childNode.data('custom_name', trimmed);
                childNode.data('raw_label', trimmed);
                this._rememberCustomName(childNode, trimmed);
              }
            }
          }

          // Remember custom name in engine registry and on consumed elements
          this._rememberCustomName(node, trimmed);

          // If inside a collapsed compound, update its banner
          const parentId = node.data('parent');
          if (parentId) {
            const parentNode = this.cy.getElementById(parentId);
            if (parentNode && parentNode.length > 0 && this.isCollapsedCompound(parentNode)) {
              const fnName = this._getCompoundFunctionName(parentNode);
              const newCollapsedLabel = `${fnName} (${trimmed})`;
              parentNode.data('collapsed_label', newCollapsedLabel);
              parentNode.data('label', newCollapsedLabel);
            }
          }
          return true;
        }

        _rememberCustomName(node, customName) {
          if (!node || !customName) return;
          const nodeId = typeof node.id === 'function' ? node.id() : String(node);
          this.rememberedCustomNames.set(nodeId, customName);

          const consumedSubnet = typeof node.data === 'function' ? (node.data('consumedSubnet') || node.data('consumedSubgraph')) : null;
          if (consumedSubnet) {
            consumedSubnet.custom_name = customName;
            const subnetKey = this._consumedSubnetKey(consumedSubnet);
            if (subnetKey) {
              this.rememberedCustomNames.set(subnetKey, customName);
            }
          }
        }

        isFunctionFoldedIntoSingleComponent(compoundIdOrNode) {
          if (!compoundIdOrNode) return false;
          const compoundId = typeof compoundIdOrNode === 'string'
            ? compoundIdOrNode
            : (compoundIdOrNode.id ? compoundIdOrNode.id() : null);
          if (!compoundId) return false;
          const compoundNode = this.cy.getElementById(compoundId);
          if (!compoundNode || compoundNode.length === 0) return false;

          if (this.isCollapsedCompound(compoundNode)) {
            return true;
          }

          const self = this;
          const children = this.cy.nodes().filter(function(n) {
            return n.data('parent') === compoundId;
          });
          if (children.length === 1) {
            const child = children[0];
            if (self.isOpaqueTransition(child)) {
              return true;
            }
          }

          return false;
        }

        _findInternalOpaqueChild(compoundId) {
          const self = this;
          const directOpaqueChildren = this.cy.nodes().filter(function(n) {
            return n.data('parent') === compoundId && self.isOpaqueTransition(n);
          });
          return directOpaqueChildren.length > 0 ? directOpaqueChildren[0] : null;
        }

        _reinjectBoundaryArc(sourceId, targetId, bArc, idx) {
          const src = this.cy.getElementById(sourceId);
          const tgt = this.cy.getElementById(targetId);
          if (src.length === 0 || tgt.length === 0) return;

          const baseEdgeId = bArc.edgeId || bArc.id || `arc_restore_${sourceId}_${targetId}_${idx}`;
          let edgeId = baseEdgeId;
          let counter = 0;
          while (this.cy.getElementById(edgeId).length > 0) {
            edgeId = `${baseEdgeId}_${++counter}`;
          }

          this.cy.add({
            group: 'edges',
            data: {
              id: edgeId,
              source: sourceId,
              target: targetId,
              weight: bArc.weight || 1
            },
            classes: bArc.classes || 'arc'
          });
        }

        _unfoldSingleOpaqueTransition(opaqueNodeOrId) {
          const opaqueNode = typeof opaqueNodeOrId === 'string'
            ? this.cy.getElementById(opaqueNodeOrId)
            : opaqueNodeOrId;

          if (!opaqueNode || opaqueNode.length === 0) return null;
          const consumedSubnet = opaqueNode.data('consumedSubnet') || opaqueNode.data('consumedSubgraph');
          if (!consumedSubnet) return null;
          const opaqueId = opaqueNode.id();
          const self = this;

          const customName = opaqueNode.data('custom_name') ||
            (consumedSubnet && consumedSubnet.custom_name) ||
            (this.rememberedCustomNames && this.rememberedCustomNames.get(opaqueId));

          if (customName) {
            this._rememberCustomName(opaqueNode, customName);
          }

          // 1. Remove all incident boundary edges connected to the opaque transition
          const incidentEdges = opaqueNode.connectedEdges();
          incidentEdges.forEach(function(e) {
            if (e.inside()) self.cy.remove(e);
          });

          // 2. Remove the opaque transition itself
          if (opaqueNode.inside()) {
            self.cy.remove(opaqueNode);
          }

          // 3. Re-inject consumed compound containers (if any were pruned during cross-boundary fold)
          if (Array.isArray(consumedSubnet.consumedCompounds)) {
            consumedSubnet.consumedCompounds.forEach(function(cDef) {
              if (self.cy.getElementById(cDef.data.id).length === 0) {
                self.cy.add(cDef);
              }
            });
          }

          // 4. Re-inject consumed nodes
          if (Array.isArray(consumedSubnet.nodes)) {
            consumedSubnet.nodes.forEach(function(nDef) {
              if (self.cy.getElementById(nDef.data.id).length === 0) {
                const nodeCopy = JSON.parse(JSON.stringify(nDef));
                if (nodeCopy.classes) {
                  nodeCopy.classes = nodeCopy.classes.replace(/\bcollapsed-child\b/g, '').trim();
                }
                if (nodeCopy.data) {
                  delete nodeCopy.data.is_collapsed_child;
                  if (nodeCopy.data.original_label) {
                    nodeCopy.data.label = nodeCopy.data.original_label;
                  }
                }
                self.cy.add(nodeCopy);
              }
            });
          }

          // 5. Re-inject consumed internal edges
          if (Array.isArray(consumedSubnet.internalEdges)) {
            consumedSubnet.internalEdges.forEach(function(eDef) {
              if (self.cy.getElementById(eDef.data.id).length === 0) {
                const src = self.cy.getElementById(eDef.data.source);
                const tgt = self.cy.getElementById(eDef.data.target);
                if (src.length > 0 && tgt.length > 0) {
                  self.cy.add(eDef);
                }
              }
            });
          }

          // 6. Re-inject boundary in arcs (skip if targetId was opaqueId and no originalTargetId)
          if (Array.isArray(consumedSubnet.boundaryInArcs)) {
            consumedSubnet.boundaryInArcs.forEach(function(bArc, idx) {
              const origTarget = bArc.originalTargetId || (bArc.targetId !== opaqueId ? bArc.targetId : null);
              if (!origTarget) return;
              self._reinjectBoundaryArc(bArc.sourceId, origTarget, bArc, idx);
            });
          }

          // 7. Re-inject boundary out arcs (skip if sourceId was opaqueId and no originalSourceId)
          if (Array.isArray(consumedSubnet.boundaryOutArcs)) {
            consumedSubnet.boundaryOutArcs.forEach(function(bArc, idx) {
              const origSource = bArc.originalSourceId || (bArc.sourceId !== opaqueId ? bArc.sourceId : null);
              if (!origSource) return;
              self._reinjectBoundaryArc(origSource, bArc.targetId, bArc, idx);
            });
          }

          return { opaqueId: opaqueId, restoredSubnet: consumedSubnet };
        }

        _unfoldSingleComponent(opaqueNodeOrId) {
          return this._unfoldSingleOpaqueTransition(opaqueNodeOrId);
        }

        executeComponentLocalUnfold(targetNodeOrId) {
          const targetNode = typeof targetNodeOrId === 'string'
            ? this.cy.getElementById(targetNodeOrId)
            : targetNodeOrId;

          if (!targetNode || targetNode.length === 0) {
            return { success: false, reason: "Target node not found." };
          }

          // Case A: Target is a Collapsed Compound State (or the collapsed child of one)
          let targetCompoundNode = null;
          if (this.isCollapsedCompound(targetNode)) {
            targetCompoundNode = targetNode;
          } else if (this.isCollapsedChild(targetNode)) {
            const pId = targetNode.data('parent');
            if (pId) {
              const pNode = this.cy.getElementById(pId);
              if (pNode && pNode.length > 0 && this.isCollapsedCompound(pNode)) {
                targetCompoundNode = pNode;
              }
            }
          }

          if (targetCompoundNode) {
            const compoundId = targetCompoundNode.id();
            let internalOpaque = this._findInternalOpaqueChild(compoundId);
            let unfoldedCount = 0;
            while (internalOpaque) {
              const res = this._unfoldSingleOpaqueTransition(internalOpaque);
              if (!res) {
                return {
                  success: false,
                  reason: `Failed to unfold internal opaque transition '${internalOpaque.id()}'.`
                };
              }
              unfoldedCount++;
              internalOpaque = this._findInternalOpaqueChild(compoundId);
            }
            this._updateCollapsedCompoundStates();
            const newSM = this.calculateSMScore();
            return {
              success: true,
              type: 'collapsed_compound',
              compoundId: compoundId,
              unfoldedCount: unfoldedCount,
              sm_score: newSM
            };
          }

          // Case B: Target is an opaque transition node
          if (this.isOpaqueTransition(targetNode)) {
            const opaqueId = targetNode.id();
            const res = this._unfoldSingleOpaqueTransition(targetNode);
            if (!res) {
              return { success: false, reason: "Failed to unfold opaque transition." };
            }
            this._updateCollapsedCompoundStates();
            const newSM = this.calculateSMScore();
            return {
              success: true,
              type: 'opaque_transition',
              opaqueId: opaqueId,
              unfoldedOpaqueId: opaqueId,
              sm_score: newSM
            };
          }

          return { success: false, reason: "Target is neither an opaque transition nor a collapsed compound." };
        }

        canSinglePlaceContract(placeNode) {
          if (!placeNode || typeof placeNode.hasClass !== 'function' || !placeNode.hasClass('place')) {
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
            if (parentSrc !== null && (parentSrc !== parentSnk || parentSrc !== parentPlace)) {
              if (!this.isFunctionFoldedIntoSingleComponent(parentSrc)) {
                return {
                  ok: false,
                  reason: `Preceding transition belongs to function container '${parentSrc}', which is not yet folded into a single component node.`
                };
              }
            }
            if (parentSnk !== null && (parentSnk !== parentSrc || parentSnk !== parentPlace)) {
              if (!this.isFunctionFoldedIntoSingleComponent(parentSnk)) {
                return {
                  ok: false,
                  reason: `Succeeding transition belongs to function container '${parentSnk}', which is not yet folded into a single component node.`
                };
              }
            }
          }

          return { ok: true, t_src: t_src, t_snk: t_snk, inArc: inArcs[0], outArc: outArcs[0] };
        }

        canContractPlace(placeNode) {
          return this.canSinglePlaceContract(placeNode);
        }

        executeSinglePlaceContraction(placeNode) {
          const check = this.canSinglePlaceContract(placeNode);
          if (!check.ok) {
            return { success: false, message: check.reason };
          }

          const t_src = check.t_src;
          const t_snk = check.t_snk;
          const inArc = check.inArc;
          const outArc = check.outArc;

          this.stepCounter++;
          const stepNum = this.stepCounter;
          const opaqueId = 'c_' + String(stepNum).padStart(2, '0');

          // 1. Calculate weights per ProM / Lassen Definition 21 (default omega = 0.0)
          const tauSrc = parseFloat(t_src.data('tau') !== undefined ? t_src.data('tau') : 1.0);
          const tauSnk = parseFloat(t_snk.data('tau') !== undefined ? t_snk.data('tau') : 1.0);
          const omega = this.cfg.sequence;
          const accumulatedTau = parseFloat((omega + tauSrc + tauSnk).toFixed(2));

          // 2. Discover parent compound container via Lowest Common Ancestor (P4)
          const parentPlace = placeNode.data('parent') || null;
          const parentSrc = t_src.data('parent') || null;
          const parentSnk = t_snk.data('parent') || null;
          const parentId = this._findLowestCommonAncestor(parentSrc, parentSnk);

          // 3. Serialize boundary arcs and consumed subnet BEFORE any mutations occur
          const boundaryInArcs = t_src.incomers('edge').map(function(edge) {
            return {
              edgeId: edge.id(),
              sourceId: edge.source().id(),
              targetId: opaqueId,
              originalTargetId: t_src.id(),
              weight: edge.data('weight') || 1,
              classes: edge.classes().join(' ')
            };
          });

          const boundaryOutArcs = t_snk.outgoers('edge').map(function(edge) {
            return {
              edgeId: edge.id(),
              sourceId: opaqueId,
              originalSourceId: t_snk.id(),
              targetId: edge.target().id(),
              weight: edge.data('weight') || 1,
              classes: edge.classes().join(' ')
            };
          });

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
          const self = this;
          [parentSrc, parentSnk, parentPlace].forEach(function(pCompId) {
            if (pCompId && pCompId !== parentId && !consumedCompounds.some(function(c) { return c.data.id === pCompId; })) {
              const pNode = self.cy.getElementById(pCompId);
              const remaining = self.cy.nodes().filter(function(n) {
                return n.data('parent') === pCompId &&
                  n.id() !== t_src.id() &&
                  n.id() !== t_snk.id() &&
                  n.id() !== placeNode.id();
              });
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

          const consumedSubnet = {
            stepNumber: stepNum,
            opaqueId: opaqueId,
            componentType: 'Sequence',
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
          consumedCompounds.forEach(function(c) {
            const pNode = self.cy.getElementById(c.data.id);
            if (pNode.inside()) self.cy.remove(pNode);
          });
          if (inArc.inside()) this.cy.remove(inArc);
          if (outArc.inside()) this.cy.remove(outArc);
          if (placeNode.inside()) this.cy.remove(placeNode);
          if (t_src.inside()) this.cy.remove(t_src);
          if (t_snk.inside()) this.cy.remove(t_snk);

          // 5. Create new opaque transition node
          const rawSrc = t_src.data('raw_label') || t_src.data('label') || t_src.id();
          const rawSnk = t_snk.data('raw_label') || t_snk.data('label') || t_snk.id();
          const opaqueNode = this._createOpaqueComponentNode(
            opaqueId, opaqueId, `${rawSrc} ; ${rawSnk}`, accumulatedTau, omega, 'Sequence', parentId, consumedSubnet
          );

          // 6. Connect boundary arcs to new opaque transition
          boundaryInArcs.forEach(function(bArc, idx) {
            self.cy.add({
              group: 'edges',
              data: {
                id: `arc_in_${opaqueId}_${idx}`,
                source: bArc.sourceId,
                target: opaqueId,
                weight: bArc.weight
              },
              classes: bArc.classes || 'arc'
            });
          });

          boundaryOutArcs.forEach(function(bArc, idx) {
            self.cy.add({
              group: 'edges',
              data: {
                id: `arc_out_${opaqueId}_${idx}`,
                source: opaqueId,
                target: bArc.targetId,
                weight: bArc.weight
              },
              classes: bArc.classes || 'arc'
            });
          });

          const isCollapsed = parentId ? Boolean(this.cy.getElementById(parentId).hasClass('collapsed-compound')) : false;
          consumedSubnet.isCompoundCollapsed = isCollapsed;

          return {
            success: true,
            message: `Folded sequence into '${opaqueId}'`,
            step: consumedSubnet,
            node: opaqueNode,
            isCompoundCollapsed: isCollapsed
          };
        }

        detectChoiceCandidates(placeNode) {
          if (!placeNode || !placeNode.hasClass('place')) {
            return { ok: false, reason: "Target is not a Petri net place." };
          }

          const tokens = parseInt(placeNode.data('initial_tokens') || 0, 10);
          if (tokens > 0) {
            return { ok: false, reason: "Cannot contract marked start/source places (tokens > 0)." };
          }

          const self = this;
          const validBundles = [];

          function addBundle(sourcePlace, targetPlace, transitions) {
            if (!sourcePlace || !targetPlace || !Array.isArray(transitions) || transitions.length < 2) {
              return;
            }

            const sourceId = sourcePlace.id();
            const targetId = targetPlace.id();
            const sourceKey = `${sourceId}::${targetId}`;
            const existing = validBundles.find(function(bundle) {
              return bundle.sourcePlaceId === sourceId && bundle.targetPlaceId === targetId;
            });
            if (existing) {
              existing.transitions.push.apply(existing.transitions, transitions);
              existing.transitions = Array.from(new Set(existing.transitions.map(function(t) { return t.id(); }))).map(function(id) {
                return self.cy.getElementById(id);
              }).filter(Boolean);
              return;
            }

            validBundles.push({
              sourcePlace: sourcePlace,
              sourcePlaceId: sourceId,
              targetPlace: targetPlace,
              targetPlaceId: targetId,
              transitions: transitions.slice()
            });
          }

          const outArcs = placeNode.outgoers('edge');
          if (outArcs.length >= 2) {
            const splitGroups = new Map();
            outArcs.forEach(function(edge) {
              const t = edge.target();
              if (!t.hasClass('transition')) return;

              const inArcs = t.incomers('edge');
              const outArcsT = t.outgoers('edge');
              if (inArcs.length !== 1 || outArcsT.length !== 1) return;

              const p_snk = outArcsT[0].target();
              if (!p_snk.hasClass('place')) return;
              if (p_snk.id() === placeNode.id()) return;

              const choiceParents = [
                placeNode.data('parent') || null,
                t.data('parent') || null,
                p_snk.data('parent') || null
              ].filter(function(parentId) { return parentId !== null; });
              if (choiceParents.length > 0) {
                const baseParent = choiceParents[0];
                for (let i = 1; i < choiceParents.length; i++) {
                  const candidateParent = choiceParents[i];
                  if (candidateParent !== baseParent && !self.isFunctionFoldedIntoSingleComponent(candidateParent)) {
                    return;
                  }
                }
              }

              const key = p_snk.id();
              if (!splitGroups.has(key)) {
                splitGroups.set(key, {
                  sourcePlace: placeNode,
                  targetPlace: p_snk,
                  transitions: []
                });
              }
              splitGroups.get(key).transitions.push(t);
            });

            splitGroups.forEach(function(group) {
              if (group.transitions.length >= 2) {
                addBundle(group.sourcePlace, group.targetPlace, group.transitions);
              }
            });
          }

          const inArcs = placeNode.incomers('edge');
          if (inArcs.length >= 2) {
            const mergeGroups = new Map();
            inArcs.forEach(function(edge) {
              const t = edge.source();
              if (!t.hasClass('transition')) return;

              const inArcsT = t.incomers('edge');
              const outArcsT = t.outgoers('edge');
              if (inArcsT.length !== 1 || outArcsT.length !== 1) return;

              const p_src = inArcsT[0].source();
              if (!p_src.hasClass('place')) return;
              if (p_src.id() === placeNode.id()) return;

              const choiceParents = [
                p_src.data('parent') || null,
                t.data('parent') || null,
                placeNode.data('parent') || null
              ].filter(function(parentId) { return parentId !== null; });
              if (choiceParents.length > 0) {
                const baseParent = choiceParents[0];
                for (let i = 1; i < choiceParents.length; i++) {
                  const candidateParent = choiceParents[i];
                  if (candidateParent !== baseParent && !self.isFunctionFoldedIntoSingleComponent(candidateParent)) {
                    return;
                  }
                }
              }

              const key = p_src.id();
              if (!mergeGroups.has(key)) {
                mergeGroups.set(key, {
                  sourcePlace: p_src,
                  targetPlace: placeNode,
                  transitions: []
                });
              }
              mergeGroups.get(key).transitions.push(t);
            });

            mergeGroups.forEach(function(group) {
              if (group.transitions.length >= 2) {
                addBundle(group.sourcePlace, group.targetPlace, group.transitions);
              }
            });
          }

          validBundles.sort(function(a, b) {
            const leftKey = `${a.sourcePlaceId}::${a.targetPlaceId}`;
            const rightKey = `${b.sourcePlaceId}::${b.targetPlaceId}`;
            return leftKey.localeCompare(rightKey);
          });

          if (validBundles.length === 0) {
            const reason = outArcs.length >= 2
              ? "No parallel transitions converging on a shared sink place."
              : inArcs.length >= 2
                ? "No parallel transitions diverging from a shared source place."
                : "Choice reduction requires at least two parallel branches.";
            return { ok: false, reason: reason };
          }

          return { ok: true, bundles: validBundles };
        }

        // Adheres to Lassen & van der Aalst (2008) Definition 21 (Order of Reductions):
        // Elementary reductions (Sequence -> Choice -> Loop) take precedence and must be
        // exhausted before evaluating SESE structural fold reductions.
        hasElementaryReductions() {
          const self = this;
          let found = false;
          const places = this.cy.nodes('.place');
          for (let i = 0; i < places.length; i++) {
            const p = places[i];
            if (self.canSinglePlaceContract(p).ok) return true;
            if (self.detectChoiceCandidates(p).ok) return true;
            if (self.detectWhileCandidates(p).ok) return true;
          }
          return false;
        }

        static get STRUCTURAL_DETECTORS() {
          return [
            {
              foldTypes: ['marked_graph', 'state_machine'],
              run: function(engine) {
                return {
                  marked_graph: engine.detectMarkedGraphs(),
                  state_machine: engine.detectStateMachines()
                };
              }
            },
            {
              foldTypes: ['well_structured'],
              run: function(engine) {
                return {
                  well_structured: engine.detectWellStructured()
                };
              }
            },
            {
              foldTypes: ['unstructured'],
              run: function(engine) {
                return {
                  unstructured: engine.detectUnstructured()
                };
              }
            }
          ];
        }

        getActiveStructuralCandidates() {
          if (this.hasElementaryReductions()) {
            return {};
          }
          for (const tier of LiveFoldReductionEngine.STRUCTURAL_DETECTORS) {
            const results = tier.run(this);
            const totalCount = Object.values(results).reduce(function(sum, cands) {
              return sum + (cands ? cands.length : 0);
            }, 0);
            if (totalCount > 0) {
              return results;
            }
          }
          return {};
        }

        getFoldType(node) {
          if (!node || typeof node.hasClass !== 'function') return null;

          if (node.hasClass('place')) {
            if (this.canSinglePlaceContract(node).ok) return 'sequence';
            if (this.detectChoiceCandidates(node).ok) return 'choice';
            if (this.detectWhileCandidates(node).ok) return 'while';
          }

          // SESE structural reductions are gated behind exhaustion of elementary reductions
          // per Lassen & van der Aalst (2008) Def. 21 to prevent premature structural folding.
          const activeStructural = this.getActiveStructuralCandidates();
          const targetGroup = node.hasClass('place') ? 'place' : 'transition';
          const nodeId = node.id();

          for (const [foldType, candidates] of Object.entries(activeStructural)) {
            const meta = LiveFoldReductionEngine.FOLD_TYPE_REGISTRY[foldType];
            if (meta && meta.targetGroup === targetGroup) {
              if (candidates.some(function(c) { return c.sourceId === nodeId || c.sinkId === nodeId; })) {
                return foldType;
              }
            }
          }

          return null;
        }

        executeBatchFold(placeIds) {
          const requestedIds = Array.isArray(placeIds) ? placeIds.slice() : [];
          const folded = [];
          const skipped = [];
          const evaluatedIds = new Set();

          requestedIds.forEach((placeId) => {
            const id = String(placeId);
            if (evaluatedIds.has(id)) {
              skipped.push({ placeId: id, reason: 'Place ID was already included in this batch.' });
              return;
            }
            evaluatedIds.add(id);

            const place = this.cy.getElementById(id);
            if (!place || place.length === 0 || !place.inside()) {
              skipped.push({ placeId: id, reason: 'Place no longer exists.' });
              return;
            }
            if (!place.hasClass('place')) {
              skipped.push({ placeId: id, reason: 'Selected node is not a place.' });
              return;
            }

            const foldType = this.getFoldType(place);
            const foldMeta = foldType && LiveFoldReductionEngine.FOLD_TYPE_REGISTRY[foldType];
            if (!foldMeta || foldMeta.targetGroup !== 'place' || typeof foldMeta.execute !== 'function') {
              skipped.push({ placeId: id, reason: 'No eligible place-targeted reduction.' });
              return;
            }

            const reduction = foldMeta.execute(this, place);
            if (reduction && reduction.success) {
              folded.push({ placeId: id, foldType: foldType, componentId: reduction.step && reduction.step.opaqueId });
            } else {
              skipped.push({
                placeId: id,
                reason: reduction && reduction.message ? reduction.message : 'Reduction was not successful.'
              });
            }
          });

          return {
            success: folded.length > 0,
            folded: folded,
            skipped: skipped,
            message: folded.length > 0
              ? `Folded ${folded.length} place${folded.length === 1 ? '' : 's'}; skipped ${skipped.length}.`
              : `No places folded; skipped ${skipped.length}.`
          };
        }

        executeFoldEntireFunction(compoundIdOrNode) {
          const compoundId = typeof compoundIdOrNode === 'string'
            ? compoundIdOrNode
            : (compoundIdOrNode && typeof compoundIdOrNode.id === 'function' ? compoundIdOrNode.id() : null);
          const folded = [];
          const skipped = [];
          let passes = 0;
          const compound = compoundId ? this.cy.getElementById(compoundId) : null;

          if (!compound || compound.length === 0 || !compound.hasClass('compound')) {
            return {
              success: false,
              complete: false,
              passes: passes,
              folded: folded,
              skipped: skipped,
              message: 'The selected function compound no longer exists.'
            };
          }

          if (this.isFunctionFoldedIntoSingleComponent(compound)) {
            return {
              success: false,
              complete: true,
              passes: passes,
              folded: folded,
              skipped: skipped,
              message: 'This function is already fully collapsed.'
            };
          }

          while (compound.inside() && !this.isFunctionFoldedIntoSingleComponent(compound)) {
            const descendantPlaces = compound.descendants().filter(function(node) {
              return node.hasClass('place');
            });
            if (descendantPlaces.length === 0) break;

            const passResult = this.executeBatchFold(descendantPlaces.map(function(place) {
              return place.id();
            }));
            passes++;
            folded.push.apply(folded, passResult.folded);
            skipped.push.apply(skipped, passResult.skipped);

            if (this.isFunctionFoldedIntoSingleComponent(compound) || !passResult.success) break;
          }

          const complete = compound.inside() && this.isFunctionFoldedIntoSingleComponent(compound);
          const success = folded.length > 0;
          return {
            success: success,
            complete: complete,
            passes: passes,
            folded: folded,
            skipped: skipped,
            message: complete
              ? `Function '${compoundId}' is fully collapsed after ${folded.length} reduction${folded.length === 1 ? '' : 's'}.`
              : success
                ? `Function '${compoundId}' remains partially folded after ${folded.length} reduction${folded.length === 1 ? '' : 's'}; no further eligible places were found.`
                : `No progress folding function '${compoundId}'; no eligible descendant places were found.`
          };
        }

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

        detectWhileCandidates(placeNode) {
          if (!placeNode || !placeNode.hasClass('place')) {
            return { ok: false, reason: "Target is not a Petri net place." };
          }

          const tokens = parseInt(placeNode.data('initial_tokens') || 0, 10);
          if (tokens > 0) {
            return { ok: false, reason: "Cannot contract marked start/source places (tokens > 0)." };
          }

          const inEdges = placeNode.incomers('edge');
          const outEdges = placeNode.outgoers('edge');

          if (inEdges.length !== 2 || outEdges.length !== 2) {
            return {
              ok: false,
              reason: `While Loop Reduction requires a 2-in/2-out place (has ${inEdges.length} in, ${outEdges.length} out).`
            };
          }

          const inTransitions = inEdges.sources().filter(function(n) { return n.hasClass('transition'); });
          const outTransitions = outEdges.targets().filter(function(n) { return n.hasClass('transition'); });

          if (inTransitions.length !== 2 || outTransitions.length !== 2) {
            return { ok: false, reason: "Connected nodes must all be transitions." };
          }

          const inIds = new Set(inTransitions.map(function(t) { return t.id(); }));
          const sharedTransitions = outTransitions.filter(function(t) { return inIds.has(t.id()); });

          if (sharedTransitions.length !== 1) {
            return {
              ok: false,
              reason: `While Loop requires exactly 1 self-looping transition (found ${sharedTransitions.length}).`
            };
          }

          const t_loop = sharedTransitions[0];
          const t_src = inTransitions.filter(function(t) { return t.id() !== t_loop.id(); })[0];
          const t_snk = outTransitions.filter(function(t) { return t.id() !== t_loop.id(); })[0];

          if (!t_src || !t_snk) {
            return { ok: false, reason: "Could not identify distinct source and sink transitions." };
          }

          if (t_loop.incomers('edge').length !== 1 || t_loop.outgoers('edge').length !== 1) {
            return { ok: false, reason: `Loop transition '${t_loop.data('label')}' has extra incoming or outgoing arcs.` };
          }
          if (t_src.outgoers('edge').length !== 1) {
            return { ok: false, reason: `Source transition '${t_src.data('label')}' branches to multiple places (${t_src.outgoers('edge').length}).` };
          }
          if (t_snk.incomers('edge').length !== 1) {
            return { ok: false, reason: `Sink transition '${t_snk.data('label')}' has multiple inputs (${t_snk.incomers('edge').length}).` };
          }

          const parentPlace = placeNode.data('parent') || null;
          const parentLoop = t_loop.data('parent') || null;
          const parentSrc = t_src.data('parent') || null;
          const parentSnk = t_snk.data('parent') || null;

          const parents = [parentPlace, parentLoop, parentSrc, parentSnk].filter(function(p) { return p !== null; });
          const uniqueParents = Array.from(new Set(parents));

          const self = this;
          if (uniqueParents.length > 1 || (parentPlace === null && uniqueParents.length > 0) || (parentPlace !== null && uniqueParents.some(function(p) { return p !== parentPlace; }))) {
            for (let i = 0; i < uniqueParents.length; i++) {
              const pId = uniqueParents[i];
              if (pId !== parentPlace && !self.isFunctionFoldedIntoSingleComponent(pId)) {
                const fnNode = self.cy.getElementById(pId);
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

          const omega = parseFloat(((this.cfg.loop / 3.0) * tau_loop).toFixed(2));
          const tau_new = parseFloat((omega + tau_src + tau_snk + tau_loop).toFixed(2));

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

        executeWhileContraction(placeNode) {
          const check = this.detectWhileCandidates(placeNode);
          if (!check.ok) {
            return { success: false, message: check.reason };
          }

          const t_loop = check.t_loop;
          const t_src = check.t_src;
          const t_snk = check.t_snk;
          const omega = check.omega;
          const tau_new = check.tau_new;

          this.stepCounter++;
          const stepNum = this.stepCounter;
          const opaqueId = 'c_' + String(stepNum).padStart(2, '0');

          const parentPlace = placeNode.data('parent') || null;
          const parentLoop = t_loop.data('parent') || null;
          const parentSrc = t_src.data('parent') || null;
          const parentSnk = t_snk.data('parent') || null;

          let parentId = this._findLowestCommonAncestorMultiple([parentPlace, parentLoop, parentSrc, parentSnk]);
          if (!parentId && (parentSrc || parentSnk)) {
            parentId = this._findLowestCommonAncestor(parentSrc, parentSnk);
          }

          const boundaryInArcs = [];
          t_src.incomers('edge').forEach(function(edge) {
            const srcNode = edge.source();
            if (srcNode.id() !== placeNode.id() && srcNode.id() !== t_loop.id()) {
              boundaryInArcs.push({
                edgeId: edge.id(),
                sourceId: srcNode.id(),
                targetId: opaqueId,
                originalTargetId: t_src.id(),
                weight: edge.data('weight') || 1,
                classes: edge.classes().join(' ')
              });
            }
          });

          const boundaryOutArcs = [];
          t_snk.outgoers('edge').forEach(function(edge) {
            const tgtNode = edge.target();
            if (tgtNode.id() !== placeNode.id() && tgtNode.id() !== t_loop.id()) {
              boundaryOutArcs.push({
                edgeId: edge.id(),
                sourceId: opaqueId,
                originalSourceId: t_snk.id(),
                targetId: tgtNode.id(),
                weight: edge.data('weight') || 1,
                classes: edge.classes().join(' ')
              });
            }
          });

          const consumedNodes = [
            { group: 'nodes', data: Object.assign({}, placeNode.data()), classes: placeNode.classes().join(' '), position: Object.assign({}, placeNode.position()) },
            { group: 'nodes', data: Object.assign({}, t_loop.data()), classes: t_loop.classes().join(' '), position: Object.assign({}, t_loop.position()) },
            { group: 'nodes', data: Object.assign({}, t_src.data()), classes: t_src.classes().join(' '), position: Object.assign({}, t_src.position()) },
            { group: 'nodes', data: Object.assign({}, t_snk.data()), classes: t_snk.classes().join(' '), position: Object.assign({}, t_snk.position()) }
          ];

          const consumedInternalEdges = [];
          const consumedNodeIdSet = new Set([placeNode.id(), t_loop.id(), t_src.id(), t_snk.id()]);
          [placeNode, t_loop, t_src, t_snk].forEach(function(n) {
            n.connectedEdges().forEach(function(e) {
              if (consumedNodeIdSet.has(e.source().id()) && consumedNodeIdSet.has(e.target().id())) {
                if (!consumedInternalEdges.some(function(x) { return x.data.id === e.id(); })) {
                  consumedInternalEdges.push({
                    group: 'edges',
                    data: Object.assign({}, e.data()),
                    classes: e.classes().join(' ')
                  });
                }
              }
            });
          });

          const consumedCompounds = [];
          const self = this;
          [parentSrc, parentSnk, parentLoop, parentPlace].forEach(function(pCompId) {
            if (pCompId && pCompId !== parentId && !consumedCompounds.some(function(c) { return c.data.id === pCompId; })) {
              const pNode = self.cy.getElementById(pCompId);
              const remaining = self.cy.nodes().filter(function(n) {
                return n.data('parent') === pCompId && !consumedNodeIdSet.has(n.id());
              });
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

          const loopLabel = t_loop.data('raw_label') || t_loop.data('label') || t_loop.id();
          const rawLabel = `while (${loopLabel})`;

          const consumedSubnet = {
            stepNumber: stepNum,
            opaqueId: opaqueId,
            componentType: 'While',
            omega: omega,
            tau: tau_new,
            consumedPlaceId: placeNode.id(),
            consumedTransIds: [t_src.id(), t_loop.id(), t_snk.id()],
            t_loop_id: t_loop.id(),
            t_src_id: t_src.id(),
            t_snk_id: t_snk.id(),
            parentCompound: parentId,
            consumedCompounds: consumedCompounds,
            nodes: consumedNodes,
            internalEdges: consumedInternalEdges,
            boundaryInArcs: boundaryInArcs,
            boundaryOutArcs: boundaryOutArcs
          };

          consumedCompounds.forEach(function(c) {
            const pNode = self.cy.getElementById(c.data.id);
            if (pNode.inside()) self.cy.remove(pNode);
          });
          [placeNode, t_loop, t_src, t_snk].forEach(function(n) {
            n.connectedEdges().forEach(function(e) {
              if (e.inside()) self.cy.remove(e);
            });
            if (n.inside()) self.cy.remove(n);
          });

          const entryPos = (consumedNodes.find(function(n) { return n.data.id === t_src.id(); }) || {}).position;
          const opaqueNode = this._createOpaqueComponentNode(
            opaqueId,
            opaqueId,
            rawLabel,
            tau_new,
            omega,
            'While',
            parentId,
            consumedSubnet,
            entryPos
          );

          boundaryInArcs.forEach(function(bArc, idx) {
            self.cy.add({
              group: 'edges',
              data: {
                id: `arc_while_in_${opaqueId}_${idx}`,
                source: bArc.sourceId,
                target: opaqueId,
                weight: bArc.weight
              },
              classes: bArc.classes || 'arc'
            });
          });

          boundaryOutArcs.forEach(function(bArc, idx) {
            self.cy.add({
              group: 'edges',
              data: {
                id: `arc_while_out_${opaqueId}_${idx}`,
                source: opaqueId,
                target: bArc.targetId,
                weight: bArc.weight
              },
              classes: bArc.classes || 'arc'
            });
          });

          const isCollapsed = parentId ? Boolean(this.cy.getElementById(parentId).hasClass('collapsed-compound')) : false;
          consumedSubnet.isCompoundCollapsed = isCollapsed;

          return {
            success: true,
            message: `Folded while loop around '${placeNode.data('label') || placeNode.id()}' into '${opaqueId}' (ω=${omega}, τ=${tau_new}).`,
            step: consumedSubnet,
            node: opaqueNode,
            isCompoundCollapsed: isCollapsed
          };
        }

        executeChoiceContraction(placeNode, bundleIndex = 0) {
          const check = this.detectChoiceCandidates(placeNode);
          if (!check.ok) {
            return { success: false, message: check.reason };
          }

          const bundle = check.bundles[bundleIndex || 0];
          const sourcePlace = bundle.sourcePlace || this.cy.getElementById(bundle.sourcePlaceId);
          const targetPlace = bundle.targetPlace || this.cy.getElementById(bundle.targetPlaceId);
          const transitions = bundle.transitions;

          if (!sourcePlace || !targetPlace || sourcePlace.length === 0 || targetPlace.length === 0) {
            return { success: false, message: 'Choice bundle is missing its source or target place.' };
          }

          this.stepCounter++;
          const stepNum = this.stepCounter;
          const opaqueId = 'c_' + String(stepNum).padStart(2, '0');

          let sumTau = 0.0;
          transitions.forEach(function(t) {
            const val = parseFloat(t.data('tau') !== undefined ? t.data('tau') : 1.0);
            sumTau += isNaN(val) ? 1.0 : val;
          });

          const omega = parseFloat((this.cfg.choice * (sumTau * 0.5)).toFixed(2));
          const accumulatedTau = parseFloat((1.5 * sumTau).toFixed(2));

          const transParents = transitions.map(function(t) { return t.data('parent') || null; });
          let parentId = this._findLowestCommonAncestorMultiple(transParents);
          if (!parentId && sourcePlace.data('parent') && targetPlace.data('parent')) {
            parentId = this._findLowestCommonAncestor(sourcePlace.data('parent'), targetPlace.data('parent'));
          }
          if (!parentId && placeNode && placeNode.data && placeNode.data('parent')) {
            parentId = placeNode.data('parent');
          }

          const consumedNodes = transitions.map(function(t) {
            return {
              group: 'nodes',
              data: Object.assign({}, t.data()),
              classes: t.classes().join(' '),
              position: Object.assign({}, t.position())
            };
          });

          const consumedInternalEdges = [];
          transitions.forEach(function(t) {
            const inEdge = t.incomers('edge')[0];
            const outEdge = t.outgoers('edge')[0];
            if (inEdge) {
              consumedInternalEdges.push({
                group: 'edges',
                data: Object.assign({}, inEdge.data()),
                classes: inEdge.classes().join(' ')
              });
            }
            if (outEdge) {
              consumedInternalEdges.push({
                group: 'edges',
                data: Object.assign({}, outEdge.data()),
                classes: outEdge.classes().join(' ')
              });
            }
          });

          const transLabels = transitions.map(function(t) {
            return t.data('raw_label') || t.data('label') || t.id();
          }).join(' ⊕ ');

          const consumedSubnet = {
            stepNumber: stepNum,
            opaqueId: opaqueId,
            componentType: 'Choice',
            omega: omega,
            tau: accumulatedTau,
            consumedPlaceId: null,
            sourcePlaceId: placeNode.id(),
            targetPlaceId: targetPlace.id(),
            consumedTransIds: transitions.map(function(t) { return t.id(); }),
            parentCompound: parentId,
            nodes: consumedNodes,
            internalEdges: consumedInternalEdges,
            boundaryInArcs: [],
            boundaryOutArcs: []
          };

          const self = this;
          transitions.forEach(function(t) {
            t.connectedEdges().forEach(function(e) {
              if (e.inside()) self.cy.remove(e);
            });
            if (t.inside()) self.cy.remove(t);
          });

          const opaqueNode = this._createOpaqueComponentNode(
            opaqueId, opaqueId, transLabels, accumulatedTau, omega, 'Choice', parentId, consumedSubnet
          );

          this.cy.add({
            group: 'edges',
            data: {
              id: `arc_in_${opaqueId}`,
              source: sourcePlace.id(),
              target: opaqueId,
              weight: 1
            },
            classes: 'arc'
          });

          this.cy.add({
            group: 'edges',
            data: {
              id: `arc_out_${opaqueId}`,
              source: opaqueId,
              target: targetPlace.id(),
              weight: 1
            },
            classes: 'arc'
          });

          const isCollapsed = parentId ? Boolean(this.cy.getElementById(parentId).hasClass('collapsed-compound')) : false;
          consumedSubnet.isCompoundCollapsed = isCollapsed;

          return {
            success: true,
            message: `Folded choice transitions [${transLabels}] into '${opaqueId}' (ω=${omega}, τ=${accumulatedTau}).`,
            step: consumedSubnet,
            node: opaqueNode,
            isCompoundCollapsed: isCollapsed
          };
        }

        _pruneConsumedCompounds(consumedNodeIdSet, parentCandidateIds, targetParentId) {
          const consumedCompounds = [];
          const self = this;
          const seen = new Set();
          const idSet = consumedNodeIdSet instanceof Set ? consumedNodeIdSet : new Set(consumedNodeIdSet);

          parentCandidateIds.forEach(function(pCompId) {
            if (pCompId && pCompId !== targetParentId && !seen.has(pCompId)) {
              seen.add(pCompId);
              const pNode = self.cy.getElementById(pCompId);
              if (pNode && pNode.length > 0) {
                const remaining = self.cy.nodes().filter(function(n) {
                  return n.data('parent') === pCompId && !idSet.has(n.id());
                });
                if (remaining.length === 0) {
                  consumedCompounds.push({
                    group: 'nodes',
                    data: Object.assign({}, pNode.data()),
                    classes: pNode.classes().join(' '),
                    position: Object.assign({}, pNode.position())
                  });
                }
              }
            }
          });
          return consumedCompounds;
        }

        _validateSESEFunctionBoundaries(nodesSet) {
          const self = this;
          const compoundChildrenCount = new Map();
          const compoundInternalCount = new Map();

          for (const nid of nodesSet) {
            const node = this.cy.getElementById(nid);
            if (!node || node.length === 0) continue;
            const parentId = node.data('parent') || null;
            if (parentId) {
              if (!compoundChildrenCount.has(parentId)) {
                const totalChildren = this.cy.nodes().filter(function(n) {
                  return n.data('parent') === parentId;
                }).length;
                compoundChildrenCount.set(parentId, totalChildren);
                compoundInternalCount.set(parentId, 0);
              }
              compoundInternalCount.set(parentId, compoundInternalCount.get(parentId) + 1);
            }
          }

          for (const [parentId, internalCount] of compoundInternalCount.entries()) {
            const totalCount = compoundChildrenCount.get(parentId);
            if (internalCount < totalCount) {
              if (!self.isFunctionFoldedIntoSingleComponent(parentId)) {
                return false;
              }
            }
          }
          return true;
        }

        _discoverSESESubnets(options) {
          const boundaryElements = this.cy.nodes(options.boundarySelector);
          const boundaryIds = boundaryElements.map(function(n) { return n.id(); });
          boundaryIds.sort();

          const candidates = [];
          const seseCandidates = this.sese.findAllSESECandidates(boundaryIds, 2);
          const self = this;

          seseCandidates.forEach(function(cand) {
            let valid = true;
            for (const nid of cand.nodes) {
              const node = self.cy.getElementById(nid);
              if (!node || node.length === 0) {
                valid = false;
                break;
              }
              if (options.validateNode && !options.validateNode(node, cand)) {
                valid = false;
                break;
              }
            }
            if (!valid) return;

            if (options.validateSubnet && !options.validateSubnet(cand)) {
              return;
            }

            if (!self._validateSESEFunctionBoundaries(cand.nodes)) {
              return;
            }

            const compTrans = [];
            cand.nodes.forEach(function(nid) {
              const n = self.cy.getElementById(nid);
              if (n && n.length > 0 && n.hasClass('transition')) {
                compTrans.push(n);
              }
            });

            const tauSum = compTrans.reduce(function(sum, t) {
              const tau = parseFloat(t.data('tau'));
              return sum + (isNaN(tau) ? 1.0 : tau);
            }, 0.0);

            const multData = options.calculateMultiplier(cand, compTrans);
            const tauNew = parseFloat((compTrans.reduce(function(sum, t) {
              const tau = parseFloat(t.data('tau'));
              const tVal = isNaN(tau) ? 1.0 : tau;
              return sum + multData.multiplier * tVal;
            }, 0.0) * multData.symmetryProduct).toFixed(2));
            const omega = parseFloat((tauNew - tauSum).toFixed(2));

            const candidateObj = Object.assign({
              componentType: options.componentType,
              sourceId: cand.sourceId,
              sinkId: cand.sinkId,
              nodes: cand.nodes,
              compTrans: compTrans,
              tauSum: tauSum,
              tauNew: tauNew,
              omega: omega
            }, multData.extraProperties || {});

            candidates.push(candidateObj);
          });

          candidates.sort(function(a, b) {
            const sizeDiff = options.sortMinimal
              ? a.nodes.size - b.nodes.size
              : b.nodes.size - a.nodes.size;
            if (sizeDiff !== 0) {
              return sizeDiff;
            }
            if (a.sourceId !== b.sourceId) {
              return a.sourceId.localeCompare(b.sourceId);
            }
            return a.sinkId.localeCompare(b.sinkId);
          });

          return options.filterMaximal ? this._filterMaximalCandidates(candidates) : candidates;
        }

        // Detects SESE Subnets for structural folding (Marked Graph or State Machine).
        // Internal places must have initial_tokens === 0 to preserve workflow net
        // token conservation during live SESE structural folding.
        _detectSESESubnetCandidates(isMarkedGraph) {
          const self = this;
          return this._discoverSESESubnets({
            boundarySelector: isMarkedGraph ? '.transition' : '.place',
            componentType: isMarkedGraph ? 'MarkedGraph' : 'StateMachine',
            filterMaximal: false,
            validateNode: function(node, cand) {
              if (isMarkedGraph) {
                if (node.hasClass('place')) {
                  if (node.incomers('edge').length !== 1 || node.outgoers('edge').length !== 1) {
                    return false;
                  }
                  if (parseInt(node.data('initial_tokens') || 0, 10) > 0) {
                    return false;
                  }
                }
              } else {
                if (node.hasClass('transition')) {
                  if (node.incomers('edge').length !== 1 || node.outgoers('edge').length !== 1) {
                    return false;
                  }
                } else if (node.hasClass('place')) {
                  if (node.id() !== cand.sourceId && node.id() !== cand.sinkId) {
                    if (parseInt(node.data('initial_tokens') || 0, 10) > 0) {
                      return false;
                    }
                  }
                }
              }
              return true;
            },
            calculateMultiplier: function(cand, compTrans) {
              const diff = self.sese.calculateSymmetryMultiplier(cand.nodes, null, false);
              const multiplier = isMarkedGraph
                ? (self.cfg.marked_graph !== undefined ? self.cfg.marked_graph : 2.0)
                : (self.cfg.state_machine !== undefined ? self.cfg.state_machine : 2.0);
              return {
                multiplier: multiplier,
                symmetryProduct: diff,
                extraProperties: { diff: diff }
              };
            }
          });
        }

        detectMarkedGraphs() {
          return this._detectSESESubnetCandidates(true);
        }

        detectStateMachines() {
          return this._detectSESESubnetCandidates(false);
        }

        detectWellStructured() {
          const self = this;
          return this._discoverSESESubnets({
            boundarySelector: '.place',
            componentType: 'WellStructured',
            filterMaximal: true,
            validateNode: function(node, cand) {
              if (node.hasClass('place')) {
                if (node.id() !== cand.sourceId && node.id() !== cand.sinkId) {
                  if (parseInt(node.data('initial_tokens') || 0, 10) > 0) {
                    return false;
                  }
                }
              }
              return true;
            },
            validateSubnet: function(cand) {
              for (const nid of cand.nodes) {
                if (nid !== cand.sinkId) {
                  const node = self.cy.getElementById(nid);
                  if (node && node.hasClass('place')) {
                    const outEdges = node.outgoers('edge');
                    for (let i = 0; i < outEdges.length; i++) {
                      const tNode = outEdges[i].target();
                      if (!tNode || !tNode.hasClass('transition')) continue;
                      const tid = tNode.id();

                      if (node.outgoers('edge').length > 1 && tNode.incomers('edge').length > 1) {
                        return false;
                      }
                      if (node.incomers('edge').length > 1 && tNode.incomers('edge').length > 1) {
                        return false;
                      }
                      if (self.sese.forwardReachability(tid, cand.sinkId).has(nid)) {
                        return false;
                      }
                    }
                  }
                }
              }
              return true;
            },
            calculateMultiplier: function(cand, compTrans) {
              const sym = self.sese.calculateSubnetSymmetry(cand.nodes, false);
              const multiplier = (self.cfg.well_structured !== undefined ? self.cfg.well_structured : 2.0);
              return {
                multiplier: multiplier,
                symmetryProduct: sym.diffP * sym.diffT,
                extraProperties: {
                  diffP: sym.diffP,
                  diffT: sym.diffT
                }
              };
            }
          });
        }

        _calculateUnstructuredOmega(nodeIds, compTrans) {
          const nodeSet = nodeIds instanceof Set ? nodeIds : new Set(nodeIds);
          let arcCount = 0;
          this.cy.edges().forEach(function(e) {
            if (nodeSet.has(e.source().id()) && nodeSet.has(e.target().id())) {
              arcCount++;
            }
          });
          const nodeCount = nodeSet.size;
          let weight = 5 * (Math.abs(arcCount - nodeCount) + 1);
          if (this.cfg.unstructured !== undefined && this.cfg.unstructured !== 7.0) {
            weight = (this.cfg.unstructured / 7.0) * weight;
          }
          const sym = this.sese.calculateSubnetSymmetry(nodeSet, false);
          const diffP = sym.diffP;
          const diffT = sym.diffT;
          const symmetryProduct = diffP * diffT;

          const tauSum = compTrans.reduce(function(sum, t) {
            const tau = parseFloat(t.data('tau'));
            return sum + (isNaN(tau) ? 1.0 : tau);
          }, 0.0);

          const tauNew = parseFloat((compTrans.reduce(function(sum, t) {
            const tau = parseFloat(t.data('tau'));
            const tVal = isNaN(tau) ? 1.0 : tau;
            return sum + weight * tVal;
          }, 0.0) * symmetryProduct).toFixed(2));
          const omega = parseFloat((tauNew - tauSum).toFixed(2));

          return {
            multiplier: weight,
            symmetryProduct: symmetryProduct,
            diffP: diffP,
            diffT: diffT,
            arcCount: arcCount,
            nodeCount: nodeCount,
            weight: weight,
            tauSum: tauSum,
            tauNew: tauNew,
            omega: omega
          };
        }

        detectUnstructured() {
          const self = this;
          const knotCandidates = this._discoverSESESubnets({
            boundarySelector: '.place',
            componentType: 'Unstructured',
            filterMaximal: false,
            sortMinimal: true,
            validateNode: function(node, cand) {
              if (node.hasClass('place')) {
                if (node.id() !== cand.sourceId && node.id() !== cand.sinkId) {
                  if (parseInt(node.data('initial_tokens') || 0, 10) > 0) {
                    return false;
                  }
                }
              }
              return true;
            },
            calculateMultiplier: function(cand, compTrans) {
              const calc = self._calculateUnstructuredOmega(cand.nodes, compTrans);
              return {
                multiplier: calc.multiplier,
                symmetryProduct: calc.symmetryProduct,
                extraProperties: {
                  diffP: calc.diffP,
                  diffT: calc.diffT,
                  arcCount: calc.arcCount,
                  nodeCount: calc.nodeCount,
                  weight: calc.weight
                }
              };
            }
          });

          if (knotCandidates.length > 0) {
            return [knotCandidates[0]];
          }

          // Global fallback: if no internal SESE pair exists and more than one transition remains
          const transNodes = this.cy.nodes('.transition');
          if (transNodes.length <= 1) {
            return [];
          }

          const placeNodes = this.cy.nodes('.place');
          if (placeNodes.length === 0) {
            return [];
          }

          const sourceCandidates = placeNodes.filter(function(p) {
            return p.incomers('edge').length === 0 || parseInt(p.data('initial_tokens') || 0, 10) > 0;
          });
          const sinkCandidates = placeNodes.filter(function(p) {
            return p.outgoers('edge').length === 0;
          });

          const p_src = sourceCandidates.length > 0 ? sourceCandidates[0] : placeNodes[0];
          let p_snk = sinkCandidates.length > 0 ? sinkCandidates[0] : placeNodes[placeNodes.length - 1];
          if (p_src.id() === p_snk.id() && placeNodes.length > 1) {
            const otherPlaces = placeNodes.filter(function(p) { return p.id() !== p_src.id(); });
            if (otherPlaces.length > 0) {
              p_snk = otherPlaces[otherPlaces.length - 1];
            }
          }

          const allNodeIds = new Set();
          placeNodes.forEach(function(p) { allNodeIds.add(p.id()); });
          transNodes.forEach(function(t) { allNodeIds.add(t.id()); });

          const compTrans = transNodes.toArray();
          const calc = this._calculateUnstructuredOmega(allNodeIds, compTrans);

          return [{
            componentType: 'Unstructured',
            sourceId: p_src.id(),
            sinkId: p_snk.id(),
            nodes: allNodeIds,
            compTrans: compTrans,
            diffP: calc.diffP,
            diffT: calc.diffT,
            arcCount: calc.arcCount,
            nodeCount: calc.nodeCount,
            weight: calc.weight,
            tauSum: calc.tauSum,
            tauNew: calc.tauNew,
            omega: calc.omega,
            isGlobalFallback: true
          }];
        }

        // ProM selects maximal SESE components per Lassen Def. 18
        _filterMaximalCandidates(candidates) {
          const maximalCandidates = [];
          for (let i = 0; i < candidates.length; i++) {
            const c = candidates[i];
            let isSubset = false;
            for (let j = 0; j < maximalCandidates.length; j++) {
              const m = maximalCandidates[j];
              let allInM = true;
              for (const nid of c.nodes) {
                if (!m.nodes.has(nid)) {
                  allInM = false;
                  break;
                }
              }
              if (allInM) {
                isSubset = true;
                break;
              }
            }
            if (!isSubset) {
              maximalCandidates.push(c);
            }
          }
          return maximalCandidates;
        }

        _findCandidateForNode(candidates, nodeOrSrc, snk = null) {
          if (!nodeOrSrc) return null;
          if (nodeOrSrc.sourceId && nodeOrSrc.sinkId && nodeOrSrc.nodes) {
            return nodeOrSrc;
          }
          const srcId = typeof nodeOrSrc === 'string' ? nodeOrSrc : (nodeOrSrc.id ? nodeOrSrc.id() : null);
          const snkId = snk ? (typeof snk === 'string' ? snk : (snk.id ? snk.id() : null)) : null;

          if (srcId && snkId) {
            return candidates.find(function(c) {
              return c.sourceId === srcId && c.sinkId === snkId;
            }) || null;
          }
          if (srcId) {
            return candidates.find(function(c) {
              return c.sourceId === srcId || c.sinkId === srcId;
            }) || null;
          }
          return null;
        }

        _executeSESEReduction(candidate, boundaryConfigFn) {
          this.stepCounter++;
          const stepNum = this.stepCounter;
          const opaqueId = 'c_' + String(stepNum).padStart(2, '0');

          const config = boundaryConfigFn(candidate, opaqueId);

          const consumedNodes = [];
          config.consumedNodeIds.forEach(function(nid) {
            const n = this.cy.getElementById(nid);
            if (n && n.length > 0) {
              consumedNodes.push({
                group: 'nodes',
                data: Object.assign({}, n.data()),
                classes: n.classes().join(' '),
                position: Object.assign({}, n.position())
              });
            }
          }, this);

          const consumedInternalEdges = [];
          config.consumedNodeIds.forEach(function(nid) {
            const n = this.cy.getElementById(nid);
            if (n && n.length > 0) {
              n.connectedEdges().forEach(function(e) {
                if (config.isInternalEdge(e)) {
                  if (!consumedInternalEdges.some(function(x) { return x.data.id === e.id(); })) {
                    consumedInternalEdges.push({
                      group: 'edges',
                      data: Object.assign({}, e.data()),
                      classes: e.classes().join(' ')
                    });
                  }
                }
              });
            }
          }, this);

          const consumedCompounds = this._pruneConsumedCompounds(
            config.consumedNodeIds,
            config.parentCandidateIds,
            config.parentId
          );

          const consumedSubnet = {
            stepNumber: stepNum,
            opaqueId: opaqueId,
            componentType: candidate.componentType,
            omega: candidate.omega,
            tau: candidate.tauNew,
            sourceId: candidate.sourceId,
            sinkId: candidate.sinkId,
            consumedNodeIds: Array.from(config.consumedNodeIds),
            parentCompound: config.parentId,
            consumedCompounds: consumedCompounds,
            nodes: consumedNodes,
            internalEdges: consumedInternalEdges,
            boundaryInArcs: config.boundaryInArcs,
            boundaryOutArcs: config.boundaryOutArcs
          };

          const self = this;
          consumedCompounds.forEach(function(c) {
            const pNode = self.cy.getElementById(c.data.id);
            if (pNode.inside()) self.cy.remove(pNode);
          });
          config.consumedNodeIds.forEach(function(nid) {
            const n = self.cy.getElementById(nid);
            if (n && n.inside()) {
              n.connectedEdges().forEach(function(e) {
                if (e.inside()) self.cy.remove(e);
              });
              self.cy.remove(n);
            }
          });

          const entryPos = config.entryPos || (consumedNodes.find(function(n) { return n.data.id === candidate.sourceId; }) || consumedNodes[0] || {}).position;
          const opaqueNode = this._createOpaqueComponentNode({
            opaqueId: opaqueId,
            label: opaqueId,
            rawLabel: config.rawLabel,
            tau: candidate.tauNew,
            omega: candidate.omega,
            componentType: candidate.componentType,
            parentId: config.parentId,
            consumedSubnet: consumedSubnet,
            position: entryPos
          });

          if (typeof config.addBoundaryArcs === 'function') {
            config.addBoundaryArcs(opaqueId, self.cy);
          }

          const isCollapsed = config.parentId ? Boolean(this.cy.getElementById(config.parentId).hasClass('collapsed-compound')) : false;
          consumedSubnet.isCompoundCollapsed = isCollapsed;

          return {
            success: true,
            message: `Folded ${candidate.componentType} (${config.rawSrc}..${config.rawSnk}) into '${opaqueId}' (ω=${candidate.omega}, τ=${candidate.tauNew}).`,
            step: consumedSubnet,
            node: opaqueNode,
            isCompoundCollapsed: isCollapsed
          };
        }

        executeMarkedGraphContraction(nodeOrSrc, snk = null) {
          const candidates = this.detectMarkedGraphs();
          const cand = this._findCandidateForNode(candidates, nodeOrSrc, snk);
          if (!cand) {
            return { success: false, message: "No eligible Marked Graph candidate found for the specified node." };
          }

          const t_src = this.cy.getElementById(cand.sourceId);
          const t_snk = this.cy.getElementById(cand.sinkId);
          if (!t_src || t_src.length === 0 || !t_snk || t_snk.length === 0) {
            return { success: false, message: "Marked Graph boundary transitions not found on canvas." };
          }

          const self = this;
          return this._executeSESEReduction(cand, function(candidate, opaqueId) {
            const parentCandidateIds = [];
            candidate.nodes.forEach(function(nid) {
              const n = self.cy.getElementById(nid);
              if (n && n.length > 0) {
                const p = n.data('parent') || null;
                if (p && !parentCandidateIds.includes(p)) parentCandidateIds.push(p);
              }
            });
            const parentId = self._findLowestCommonAncestorMultiple(parentCandidateIds);

            const boundaryInArcs = [];
            t_src.incomers('edge').forEach(function(edge) {
              const srcNode = edge.source();
              if (!candidate.nodes.has(srcNode.id())) {
                boundaryInArcs.push({
                  edgeId: edge.id(),
                  sourceId: srcNode.id(),
                  targetId: opaqueId,
                  originalTargetId: t_src.id(),
                  weight: edge.data('weight') || 1,
                  classes: edge.classes().join(' ')
                });
              }
            });

            const boundaryOutArcs = [];
            t_snk.outgoers('edge').forEach(function(edge) {
              const tgtNode = edge.target();
              if (!candidate.nodes.has(tgtNode.id())) {
                boundaryOutArcs.push({
                  edgeId: edge.id(),
                  sourceId: opaqueId,
                  originalSourceId: t_snk.id(),
                  targetId: tgtNode.id(),
                  weight: edge.data('weight') || 1,
                  classes: edge.classes().join(' ')
                });
              }
            });

            const rawSrc = t_src.data('raw_label') || t_src.data('label') || t_src.id();
            const rawSnk = t_snk.data('raw_label') || t_snk.data('label') || t_snk.id();
            const rawLabel = `MarkedGraph(${rawSrc}..${rawSnk})`;
            const srcNode = self.cy.getElementById(candidate.sourceId);
            const entryPos = srcNode && srcNode.length > 0 ? Object.assign({}, srcNode.position()) : null;

            return {
              consumedNodeIds: candidate.nodes,
              parentCandidateIds: parentCandidateIds,
              parentId: parentId,
              boundaryInArcs: boundaryInArcs,
              boundaryOutArcs: boundaryOutArcs,
              rawSrc: rawSrc,
              rawSnk: rawSnk,
              rawLabel: rawLabel,
              entryPos: entryPos,
              isInternalEdge: function(e) {
                return candidate.nodes.has(e.source().id()) && candidate.nodes.has(e.target().id());
              },
              addBoundaryArcs: function(newId, cy) {
                boundaryInArcs.forEach(function(bArc, idx) {
                  cy.add({
                    group: 'edges',
                    data: {
                      id: `arc_mg_in_${newId}_${idx}`,
                      source: bArc.sourceId,
                      target: newId,
                      weight: bArc.weight
                    },
                    classes: bArc.classes || 'arc'
                  });
                });
                boundaryOutArcs.forEach(function(bArc, idx) {
                  cy.add({
                    group: 'edges',
                    data: {
                      id: `arc_mg_out_${newId}_${idx}`,
                      source: newId,
                      target: bArc.targetId,
                      weight: bArc.weight
                    },
                    classes: bArc.classes || 'arc'
                  });
                });
              }
            };
          });
        }

        _executePlaceSESEReduction(candidate) {
          const p_src = this.cy.getElementById(candidate.sourceId);
          const p_snk = this.cy.getElementById(candidate.sinkId);
          if (!p_src || p_src.length === 0 || !p_snk || p_snk.length === 0) {
            return { success: false, message: `${candidate.componentType} boundary places not found on canvas.` };
          }

          const prefixMap = {
            StateMachine: 'sm',
            WellStructured: 'ws',
            Unstructured: 'un'
          };
          const prefix = prefixMap[candidate.componentType] || candidate.componentType.toLowerCase();

          const self = this;
          return this._executeSESEReduction(candidate, function(cand, opaqueId) {
            const internalNodeIds = new Set();
            cand.nodes.forEach(function(nid) {
              if (nid !== cand.sourceId && nid !== cand.sinkId) {
                internalNodeIds.add(nid);
              }
            });

            const parentCandidateIds = [];
            internalNodeIds.forEach(function(nid) {
              const n = self.cy.getElementById(nid);
              if (n && n.length > 0) {
                const p = n.data('parent') || null;
                if (p && !parentCandidateIds.includes(p)) parentCandidateIds.push(p);
              }
            });

            const srcParent = p_src.data('parent') || null;
            const snkParent = p_snk.data('parent') || null;
            let parentId = self._findLowestCommonAncestorMultiple([srcParent, snkParent, ...parentCandidateIds]);
            if (!parentId && srcParent && snkParent) {
              parentId = self._findLowestCommonAncestor(srcParent, snkParent);
            }

            const boundaryInArcs = [{
              sourceId: cand.sourceId,
              targetId: opaqueId,
              weight: 1,
              classes: 'arc'
            }];
            const boundaryOutArcs = [{
              sourceId: opaqueId,
              targetId: cand.sinkId,
              weight: 1,
              classes: 'arc'
            }];

            const rawSrc = p_src.data('raw_label') || p_src.data('label') || p_src.id();
            const rawSnk = p_snk.data('raw_label') || p_snk.data('label') || p_snk.id();
            const rawLabel = `${cand.componentType}(${rawSrc}..${rawSnk})`;
            const firstInternalId = Array.from(internalNodeIds)[0];
            const firstInternalNode = firstInternalId ? self.cy.getElementById(firstInternalId) : null;
            const entryPos = firstInternalNode && firstInternalNode.length > 0 ? Object.assign({}, firstInternalNode.position()) : null;

            return {
              consumedNodeIds: internalNodeIds,
              parentCandidateIds: parentCandidateIds,
              parentId: parentId,
              boundaryInArcs: boundaryInArcs,
              boundaryOutArcs: boundaryOutArcs,
              rawSrc: rawSrc,
              rawSnk: rawSnk,
              rawLabel: rawLabel,
              entryPos: entryPos,
              isInternalEdge: function(e) {
                return true;
              },
              addBoundaryArcs: function(newId, cy) {
                cy.add({
                  group: 'edges',
                  data: {
                    id: `arc_${prefix}_in_${newId}`,
                    source: cand.sourceId,
                    target: newId,
                    weight: 1
                  },
                  classes: 'arc'
                });
                cy.add({
                  group: 'edges',
                  data: {
                    id: `arc_${prefix}_out_${newId}`,
                    source: newId,
                    target: cand.sinkId,
                    weight: 1
                  },
                  classes: 'arc'
                });
              }
            };
          });
        }

        executeStateMachineContraction(nodeOrSrc, snk = null) {
          const candidates = this.detectStateMachines();
          const cand = this._findCandidateForNode(candidates, nodeOrSrc, snk);
          if (!cand) {
            return { success: false, message: "No eligible State Machine candidate found for the specified node." };
          }
          return this._executePlaceSESEReduction(cand);
        }

        executeWellStructuredContraction(nodeOrSrc, snk = null) {
          const candidates = this.detectWellStructured();
          const cand = this._findCandidateForNode(candidates, nodeOrSrc, snk);
          if (!cand) {
            return { success: false, message: "No eligible Well-Structured candidate found for the specified node." };
          }
          return this._executePlaceSESEReduction(cand);
        }

        executeUnstructuredContraction(nodeOrSrc, snk = null) {
          const candidates = this.detectUnstructured();
          const cand = this._findCandidateForNode(candidates, nodeOrSrc, snk);
          if (!cand) {
            return { success: false, message: "No eligible Unstructured candidate found for the specified node." };
          }
          return this._executePlaceSESEReduction(cand);
        }

        static get FOLD_TYPE_REGISTRY() {
          return {
            sequence: {
              targetGroup: 'place',
              className: 'contractible-sequence',
              execute: function(engine, node) { return engine.executeSinglePlaceContraction(node); }
            },
            choice: {
              targetGroup: 'place',
              className: 'contractible-choice',
              execute: function(engine, node) { return engine.executeChoiceContraction(node); }
            },
            while: {
              targetGroup: 'place',
              className: 'contractible-while',
              execute: function(engine, node) { return engine.executeWhileContraction(node); }
            },
            state_machine: {
              targetGroup: 'place',
              className: 'contractible-state-machine',
              execute: function(engine, node) { return engine.executeStateMachineContraction(node); }
            },
            marked_graph: {
              targetGroup: 'transition',
              className: 'contractible-marked-graph',
              execute: function(engine, node) { return engine.executeMarkedGraphContraction(node); }
            },
            well_structured: {
              targetGroup: 'place',
              className: 'contractible-well-structured',
              execute: function(engine, node) { return engine.executeWellStructuredContraction(node); }
            },
            unstructured: {
              targetGroup: 'place',
              className: 'contractible-unstructured',
              execute: function(engine, node) { return engine.executeUnstructuredContraction(node); }
            }
          };
        }

        static get ALL_PLACE_CONTRACTIBLE_CLASSES() {
          return Object.values(LiveFoldReductionEngine.FOLD_TYPE_REGISTRY)
            .filter(function(def) { return def.targetGroup === 'place'; })
            .map(function(def) { return def.className; });
        }

        static getMatchingFoldType(node) {
          if (!node || typeof node.hasClass !== 'function') return null;
          const registry = LiveFoldReductionEngine.FOLD_TYPE_REGISTRY;
          for (const [key, meta] of Object.entries(registry)) {
            if (node.hasClass(meta.className)) {
              return key;
            }
          }
          return null;
        }
      }

      const FOLD_TYPE_REGISTRY = LiveFoldReductionEngine.FOLD_TYPE_REGISTRY;
      const ALL_PLACE_CONTRACTIBLE_CLASSES = LiveFoldReductionEngine.ALL_PLACE_CONTRACTIBLE_CLASSES;


  return {
    SESEInfrastructure,
    LiveFoldReductionEngine,
    FOLD_TYPE_REGISTRY,
    ALL_PLACE_CONTRACTIBLE_CLASSES
  };
});
