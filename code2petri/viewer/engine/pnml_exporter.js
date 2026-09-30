/**
 * Client-Side PNML Exporter for code2petri (ISO/IEC 15909-2 compliant).
 * Performs client-side export directly from in-memory Cytoscape graph state.
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
  function escapeXml(unsafe) {
    if (unsafe === undefined || unsafe === null) return '';
    return String(unsafe).replace(/[<>&'"]/g, function (c) {
      switch (c) {
        case '<': return '&lt;';
        case '>': return '&gt;';
        case '&': return '&amp;';
        case '\'': return '&apos;';
        case '"': return '&quot;';
      }
    });
  }

  function _resolvePlaceExportData(p) {
    const pId = p.id();
    const label = p.data('raw_label') || p.data('label') || pId;
    const tokens = parseInt(p.data('initial_tokens') || p.data('tokens') || 0, 10);
    return {
      id: pId,
      label: label,
      tokens: tokens
    };
  }

  function _resolveTransitionExportData(t, cy) {
    const tId = t.id();
    const parentId = t.data('parent');
    let parentCompound = null;
    const cyInstance = cy || (typeof t.cy === 'function' ? t.cy() : null);
    if (parentId && cyInstance) {
      parentCompound = cyInstance.getElementById(parentId);
    }
    const isInsideCollapsedCompound = Boolean(parentCompound && parentCompound.length > 0 &&
      (parentCompound.hasClass('collapsed-compound') || parentCompound.data('is_collapsed_compound') === true || Boolean(parentCompound.data('collapsed_opaque_id'))));
    const isOpaque = t.data('is_opaque') === true || t.hasClass('opaque') || Boolean(t.data('opaque'));

    let label;
    if (isInsideCollapsedCompound) {
      label = parentCompound.data('custom_name') || parentCompound.data('collapsed_label') || parentCompound.data('label');
    } else if (isOpaque) {
      label = t.data('custom_name') || t.data('label') || t.data('original_label') || t.data('raw_label') || tId;
    } else {
      label = t.data('custom_name') || t.data('raw_label') || t.data('label') || tId;
    }
    const rawTau = t.data('tau');
    const tauVal = (rawTau !== undefined && rawTau !== null) ? Number(rawTau) : 1.0;
    const tauStr = Number.isInteger(tauVal) ? tauVal.toFixed(1) : String(tauVal);

    return {
      id: tId,
      label: label,
      tau: tauStr,
      isOpaque: isOpaque
    };
  }

  function _resolveNodeExportData(node, cy) {
    if (!node) return null;
    if (node.hasClass('place')) {
      return _resolvePlaceExportData(node);
    } else if (node.hasClass('transition')) {
      return _resolveTransitionExportData(node, cy);
    }
    return null;
  }

  function serializeToPnml(cy, netName, options) {
    if (!netName) netName = 'LiveFoldPetriNet';
    const opts = (typeof options === 'boolean') ? { includeTools: options } : (options || {});
    let xml = '<?xml version="1.0" encoding="utf-8"?>\n';
    xml += '<pnml xmlns="http://www.pnml.org/version-2009/grammar/pnml">\n';
    xml += '  <net id="net0" type="http://www.pnml.org/version-2009/grammar/ptnet">\n';
    xml += '    <name>\n';
    xml += `      <text>${escapeXml(netName)}</text>\n`;
    xml += '    </name>\n';
    xml += '    <page id="page0">\n';

    // 1. Places (excluding compound container parent nodes)
    const places = cy.nodes('.place').filter(function(p) {
      return p.inside() && !p.hasClass('compound');
    });
    places.forEach(function(p) {
      const pData = _resolveNodeExportData(p, cy);
      xml += `      <place id="${escapeXml(pData.id)}">\n`;
      xml += '        <name>\n';
      xml += `          <text>${escapeXml(pData.label)}</text>\n`;
      xml += '        </name>\n';
      if (pData.tokens > 0) {
        xml += '        <initialMarking>\n';
        xml += `          <text>${pData.tokens}</text>\n`;
        xml += '        </initialMarking>\n';
      }
      xml += '      </place>\n';
    });

    // 2. Transitions
    const transitions = cy.nodes('.transition').filter(function(t) {
      return t.inside() && !t.hasClass('compound');
    });
    transitions.forEach(function(t) {
      const tData = _resolveNodeExportData(t, cy);
      xml += `      <transition id="${escapeXml(tData.id)}">\n`;
      xml += '        <name>\n';
      xml += `          <text>${escapeXml(tData.label)}</text>\n`;
      xml += '        </name>\n';
      if (opts.includeTools) {
        xml += '        <toolspecific tool="code2petri" version="1.0">\n';
        xml += `          <property name="tau" value="${escapeXml(tData.tau)}"/>\n`;
        if (tData.isOpaque) {
          xml += '          <property name="opaque" value="true"/>\n';
        }
        xml += '        </toolspecific>\n';
      }
      xml += '      </transition>\n';
    });

    // 3. Arcs
    const edges = cy.edges().filter(function(e) {
      if (!e.inside()) return false;
      const src = cy.getElementById(e.data('source'));
      const tgt = cy.getElementById(e.data('target'));
      return src && src.inside() && !src.hasClass('compound') &&
             tgt && tgt.inside() && !tgt.hasClass('compound');
    });
    edges.forEach(function(edge, index) {
      const arcId = edge.id() || ('a' + (index + 1));
      const sourceId = edge.data('source');
      const targetId = edge.data('target');
      const weight = parseInt(edge.data('weight') || 1, 10);

      xml += `      <arc id="${escapeXml(arcId)}" source="${escapeXml(sourceId)}" target="${escapeXml(targetId)}">\n`;
      if (weight !== 1) {
        xml += '        <inscription>\n';
        xml += `          <text>${weight}</text>\n`;
        xml += '        </inscription>\n';
      }
      xml += '      </arc>\n';
    });

    xml += '    </page>\n';
    xml += '  </net>\n';
    xml += '</pnml>\n';

    return xml;
  }

  function getExportFilename() {
    const infoEl = typeof document !== 'undefined' ? document.getElementById('info-filename') : null;
    const raw = (infoEl && infoEl.textContent) ? infoEl.textContent.trim() : '';
    if (raw && raw !== '—') {
      const base = raw.replace(/\.[^/.]+$/, '').replace(/[^a-zA-Z0-9_-]/g, '_');
      if (base) return `${base}.pnml`;
    }
    const titleEl = typeof document !== 'undefined' ? document.querySelector('.header-title') : null;
    const titleRaw = (titleEl && titleEl.textContent) ? titleEl.textContent.trim() : '';
    if (titleRaw && titleRaw !== '—') {
      const base = titleRaw.replace(/[^a-zA-Z0-9_-]/g, '_');
      if (base) return `${base}.pnml`;
    }
    return 'petri_net.pnml';
  }

  function _triggerBlobDownload(blob, filename) {
    if (typeof document === 'undefined' || typeof URL === 'undefined' || typeof URL.createObjectURL !== 'function') {
      return;
    }
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    if (document.body && typeof document.body.appendChild === 'function') {
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } else if (typeof a.click === 'function') {
      a.click();
    }
    if (typeof URL.revokeObjectURL === 'function') {
      setTimeout(function() {
        URL.revokeObjectURL(url);
      }, 100);
    }
  }

  /**
   * Triggers a client-side export of the current graph as a PNML file.
   * @param {cytoscape.Core} cy
   * @param {string} [filename]
   * @param {Object} [options]
   */
  function exportClientSidePnml(cy, filename, options) {
    if (!filename) filename = getExportFilename();
    const netName = filename.replace(/\.pnml$/i, '');
    const xmlContent = serializeToPnml(cy, netName, options);
    if (typeof Blob !== 'undefined') {
      const blob = new Blob([xmlContent], { type: 'application/xml;charset=utf-8' });
      _triggerBlobDownload(blob, filename);
    }
    return xmlContent;
  }

  const triggerClientSideExport = exportClientSidePnml;
  const exportPnml = exportClientSidePnml;
  const downloadPnmlFile = exportClientSidePnml; // Backwards-compatible alias

  return {
    escapeXml,
    _resolvePlaceExportData,
    _resolveTransitionExportData,
    _resolveNodeExportData,
    serializeToPnml,
    getExportFilename,
    _triggerBlobDownload,
    exportClientSidePnml,
    triggerClientSideExport,
    exportPnml,
    downloadPnmlFile
  };
});
