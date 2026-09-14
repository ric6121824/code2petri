import html
import json
import os
from typing import Any, Dict, Optional, Union

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
    target: Any,
    title: Optional[str] = None,
) -> str:
    """Generates a 100% self-contained offline HTML viewer for a PetriNet or FoldResult.

    :param target: A PetriNet instance (for static --no-fold view) or a FoldResult
                   instance (for interactive fold playback).
    :param title: Optional title to display in the header.
    :return: Complete HTML document string with inlined Cytoscape, Dagre, and graph data.
    """
    template = _load_template()
    vendor_scripts = _load_vendor_scripts()

    is_fold_result = hasattr(target, "initial_net") and hasattr(target, "steps")
    if is_fold_result:
        initial_net_dict = target.initial_net.to_dict()
        steps_dict = [s.to_dict() for s in target.steps]
        final_sm = float(target.final_sm) if hasattr(target, "final_sm") else 0.0
        display_title = title if title is not None else f"SM Score = {final_sm}"
        payload: Dict[str, Any] = {
            "mode": "fold",
            "title": display_title,
            "initial_net": initial_net_dict,
            "fold_steps": steps_dict,
            "final_sm": final_sm,
            "fully_reducible": bool(getattr(target, "fully_reducible", True)),
        }
    else:
        net_dict = target.to_dict() if hasattr(target, "to_dict") else {}
        display_title = title if title is not None else "Petri Net"
        payload = {
            "mode": "no-fold",
            "title": display_title,
            "initial_net": net_dict,
            "fold_steps": [],
            "final_sm": 0.0,
            "fully_reducible": False,
        }

    escaped_title = html.escape(display_title)
    json_data = json.dumps(payload, indent=2)

    rendered = template.replace("{{TITLE}}", escaped_title)
    rendered = rendered.replace("{{VENDOR_SCRIPTS}}", vendor_scripts)
    rendered = rendered.replace("{{DATA_JSON}}", json_data)

    return rendered
