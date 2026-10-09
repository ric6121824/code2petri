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


def _load_engine_scripts() -> str:
    viewer_dir = _get_viewer_dir()
    engine_dir = os.path.join(viewer_dir, "engine")
    pnml_path = os.path.join(engine_dir, "pnml_exporter.js")
    engine_path = os.path.join(engine_dir, "reduction_engine.js")
    viewport_path = os.path.join(engine_dir, "viewport.js")
    with open(pnml_path, "r", encoding="utf-8") as f:
        pnml_content = f.read()
    with open(engine_path, "r", encoding="utf-8") as f:
        engine_content = f.read()
    with open(viewport_path, "r", encoding="utf-8") as f:
        viewport_content = f.read()
    return f"{pnml_content}\n\n{engine_content}\n\n{viewport_content}"


def _load_template() -> str:
    global _CACHED_TEMPLATE
    if _CACHED_TEMPLATE is not None:
        return _CACHED_TEMPLATE

    template_path = os.path.join(_get_viewer_dir(), "template.html")
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Missing HTML viewer template: {template_path}")
    with open(template_path, "r", encoding="utf-8") as f:
        raw_template = f.read()
    _CACHED_TEMPLATE = raw_template.replace("/* {{ENGINE_SCRIPTS}} */", _load_engine_scripts())
    return _CACHED_TEMPLATE


def generate_html(
    net_or_fold: Union[PetriNet, FoldResult],
    title: Optional[str] = None,
    callee_nets: Optional[Dict[str, Any]] = None,
    source_file: Optional[str] = None,
    function_name: Optional[str] = None,
) -> str:
    """Generates a 100% self-contained offline HTML viewer for a PetriNet or FoldResult.

    :param net_or_fold: A PetriNet instance (for static --no-fold view or composite view)
                        or a FoldResult instance (for interactive fold playback).
    :param title: Optional title to display in the header.
    :param callee_nets: Optional dictionary of pre-computed raw callee nets keyed by symbol name.
    :param source_file: Optional source file path or name being visualized.
    :param function_name: Optional root-function identity for the active document.
    :return: Complete HTML document string with inlined Cytoscape, Dagre, and graph data.
    """
    template = _load_template()
    vendor_scripts = _load_vendor_scripts()
    callee_dict = callee_nets if callee_nets is not None else {}

    full_source_path = source_file or ""
    file_display = os.path.basename(source_file) if source_file else ""
    root_function_name = (
        "Global Scope" if function_name == "(global)" else function_name or "Unavailable"
    )

    if isinstance(net_or_fold, PetriNet) and bool(net_or_fold.compounds):
        comp_dict = net_or_fold.to_dict()
        compounds = [c.to_dict() for c in net_or_fold.compounds]

        display_title = title if title is not None else "Composite Petri Net"
        mode_label = "Composite Petri Net View"
        mode_desc = "Fully expanded composite Petri net with inlined function subnets."
        payload: Dict[str, Any] = {
            "mode": "composite",
            "title": display_title,
            "initial_net": comp_dict,
            "composite_net": comp_dict,
            "compounds": compounds,
            "fold_steps": [],
            "final_sm": 0.0,
            "fully_reducible": False,
        }
    elif isinstance(net_or_fold, FoldResult):
        fold_dict = net_or_fold.to_dict()
        display_title = title if title is not None else f"SM Score = {net_or_fold.final_sm}"
        mode_label = "Fold Reduction View"
        mode_desc = "Interactive step playback of ProM-aligned structural reductions."
        payload = {
            "mode": "fold",
            "title": display_title,
            **fold_dict,
        }
    elif isinstance(net_or_fold, PetriNet):
        net_dict = net_or_fold.to_dict()
        display_title = title if title is not None else "Petri Net"
        mode_label = "Petri Net View"
        mode_desc = "Interactive Petri net graph representation."
        payload = {
            "mode": "no-fold",
            "title": display_title,
            "initial_net": net_dict,
            "fold_steps": [],
            "final_sm": 0.0,
            "fully_reducible": False,
        }
    else:
        raise TypeError(f"Expected PetriNet or FoldResult, got {type(net_or_fold).__name__}")

    payload["source_file"] = full_source_path
    payload["filename"] = file_display
    payload["document"] = {
        "source_file": full_source_path,
        "filename": file_display,
        "function_name": root_function_name,
    }

    escaped_title = html.escape(display_title)
    escaped_source_file = html.escape(full_source_path)
    escaped_filename = html.escape(file_display)
    escaped_function_name = html.escape(root_function_name)
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
    rendered = rendered.replace("{{FUNCTION_NAME}}", escaped_function_name)
    rendered = rendered.replace("{{FILE_BOX_STYLE}}", file_box_style)
    rendered = rendered.replace("{{MODE_LABEL}}", html.escape(mode_label))
    rendered = rendered.replace("{{MODE_DESC}}", html.escape(mode_desc))

    return rendered

