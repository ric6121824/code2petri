import html
import json
import os
from typing import Any, Dict, Optional, Union

from code2petri.fold import FoldResult
from code2petri.model import PetriNet


_CACHED_VENDOR_SCRIPTS: Optional[str] = None
_CACHED_TEMPLATE: Optional[str] = None


def _get_viewer_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def _load_vendor_scripts() -> str:
    global _CACHED_VENDOR_SCRIPTS
    if _CACHED_VENDOR_SCRIPTS is not None:
        return _CACHED_VENDOR_SCRIPTS

    viewer_dir = _get_viewer_dir()
    vendor_dir = os.path.join(viewer_dir, "vendor")

    # Order matters: dagre must precede cytoscape-dagre
    script_files = ["dagre.min.js", "cytoscape.min.js", "cytoscape-dagre.js"]
    scripts = []
    for sf in script_files:
        path = os.path.join(vendor_dir, sf)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Missing required vendor library: {path}")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        scripts.append(f"<script>\n/* {sf} */\n{content}\n</script>")

    _CACHED_VENDOR_SCRIPTS = "\n".join(scripts)
    return _CACHED_VENDOR_SCRIPTS


def _load_template() -> str:
    global _CACHED_TEMPLATE
    if _CACHED_TEMPLATE is not None:
        return _CACHED_TEMPLATE

    template_path = os.path.join(_get_viewer_dir(), "template.html")
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Missing HTML viewer template: {template_path}")
    with open(template_path, "r", encoding="utf-8") as f:
        _CACHED_TEMPLATE = f.read()
    return _CACHED_TEMPLATE


def generate_html(
    net_or_fold: Union[PetriNet, FoldResult, Any],
    title: Optional[str] = None,
    callee_nets: Optional[Dict[str, Any]] = None,
    source_file: Optional[str] = None,
) -> str:
    """Generates a 100% self-contained offline HTML viewer for a PetriNet or FoldResult.

    :param net_or_fold: A PetriNet instance (for static --no-fold view) or a FoldResult
                        instance (for interactive fold playback).
    :param title: Optional title to display in the header.
    :param callee_nets: Optional dictionary of pre-computed raw callee nets keyed by symbol name.
    :param source_file: Optional source file path or name being visualized.
    :return: Complete HTML document string with inlined Cytoscape, Dagre, and graph data.
    """
    template = _load_template()
    vendor_scripts = _load_vendor_scripts()
    callee_dict = callee_nets if callee_nets is not None else {}

    full_source_path = source_file or ""
    file_display = os.path.basename(source_file) if source_file else ""

    if isinstance(net_or_fold, FoldResult):
        fold_dict = net_or_fold.to_dict()
        display_title = title if title is not None else f"SM Score = {net_or_fold.final_sm}"
        payload: Dict[str, Any] = {
            "mode": "fold",
            "title": display_title,
            **fold_dict,
        }
    else:
        net_dict = net_or_fold.to_dict() if isinstance(net_or_fold, PetriNet) else {}
        display_title = title if title is not None else "Petri Net"
        payload = {
            "mode": "no-fold",
            "title": display_title,
            "initial_net": net_dict,
            "fold_steps": [],
            "final_sm": 0.0,
            "fully_reducible": False,
        }

    payload["source_file"] = full_source_path
    payload["filename"] = file_display

    escaped_title = html.escape(display_title)
    escaped_source_file = html.escape(full_source_path)
    escaped_filename = html.escape(file_display)
    file_box_style = "display: flex;" if file_display else "display: none;"
    json_data = json.dumps(payload, indent=2)
    callee_nets_json = json.dumps(callee_dict, indent=2)

    rendered = template.replace("{{TITLE}}", escaped_title)
    rendered = rendered.replace("{{VENDOR_SCRIPTS}}", vendor_scripts)
    rendered = rendered.replace("{{DATA_JSON}}", json_data)
    rendered = rendered.replace("{{CALLEE_NETS_JSON}}", callee_nets_json)
    rendered = rendered.replace("{{callee_nets_json}}", callee_nets_json)
    rendered = rendered.replace("{{SOURCE_FILE}}", escaped_source_file)
    rendered = rendered.replace("{{FILENAME}}", escaped_filename)
    rendered = rendered.replace("{{FILE_BOX_STYLE}}", file_box_style)

    return rendered

