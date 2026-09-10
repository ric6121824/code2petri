from dataclasses import dataclass
import json
from typing import Optional, Union, List, Dict, Any
import xml.etree.ElementTree as ET


class Place:
    """Represents a Petri net Place (control point where execution can rest)."""

    def __init__(
        self,
        id_: Optional[str] = None,
        label: str = "",
        line_number: Optional[int] = None,
        initial_tokens: int = 0,
        id: Optional[str] = None,
    ) -> None:
        node_id = id if id is not None else id_
        if node_id is None:
            raise ValueError("Place requires an id.")
        self.id = str(node_id)
        self.label = str(label)
        self.line_number = line_number
        self.initial_tokens = int(initial_tokens)

    def __repr__(self) -> str:
        return (
            f"Place(id={self.id!r}, label={self.label!r}, "
            f"line_number={self.line_number!r}, initial_tokens={self.initial_tokens!r})"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the Place into a dictionary."""
        return {
            "id": self.id,
            "label": self.label,
            "line_number": self.line_number,
            "initial_tokens": self.initial_tokens,
        }


@dataclass(frozen=True)
class CallResolution:
    """Encapsulates call resolution metadata for a Transition."""
    resolved: bool
    resolved_to: Optional[str] = None
    target_file: Optional[str] = None

    @classmethod
    def from_metadata(cls, metadata: Optional[Dict[str, Any]]) -> Optional["CallResolution"]:
        """Constructs a CallResolution from a transition metadata mapping if resolution keys exist."""
        if not metadata or "resolved" not in metadata:
            return None
        return cls(
            resolved=bool(metadata["resolved"]),
            resolved_to=metadata.get("resolved_to"),
            target_file=metadata.get("target_file"),
        )


class Transition:
    """Represents a Petri net Transition (an action or statement execution)."""

    def __init__(
        self,
        id_: Optional[str] = None,
        label: str = "",
        line_number: Optional[int] = None,
        id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        node_id = id if id is not None else id_
        if node_id is None:
            raise ValueError("Transition requires an id.")
        self.id = str(node_id)
        self.label = str(label)
        self.line_number = line_number
        self.metadata: Optional[Dict[str, Any]] = dict(metadata) if metadata is not None else None

    @property
    def call_resolution(self) -> Optional[CallResolution]:
        """Returns typed CallResolution if call resolution metadata is present."""
        return CallResolution.from_metadata(self.metadata)

    def __repr__(self) -> str:
        metadata_str = f", metadata={self.metadata!r}" if self.metadata is not None else ""
        return (
            f"Transition(id={self.id!r}, label={self.label!r}, "
            f"line_number={self.line_number!r}{metadata_str})"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the Transition into a dictionary."""
        d: Dict[str, Any] = {
            "id": self.id,
            "label": self.label,
            "line_number": self.line_number,
        }
        if self.metadata is not None:
            d["metadata"] = dict(self.metadata)
            res = self.call_resolution
            if res is not None:
                d["resolved"] = res.resolved
                if res.resolved_to is not None:
                    d["resolved_to"] = res.resolved_to
                if res.target_file is not None:
                    d["target_file"] = res.target_file
            else:
                if "resolved_to" in self.metadata:
                    d["resolved_to"] = self.metadata["resolved_to"]
                if "target_file" in self.metadata:
                    d["target_file"] = self.metadata["target_file"]
        return d

    def add_pnml_toolspecific(self, parent_element: ET.Element) -> Optional[ET.Element]:
        """Appends <toolspecific> XML element with metadata properties to parent_element."""
        if not self.metadata:
            return None
        tool_el = ET.SubElement(parent_element, "toolspecific", tool="code2petri", version="1.0")
        res = self.call_resolution
        if res is not None:
            if res.resolved:
                target = str(res.resolved_to or "")
                target_file = str(res.target_file or "")
                ET.SubElement(tool_el, "resolved", target=target, file=target_file)
            else:
                ET.SubElement(tool_el, "unresolved")

        # Emit any other custom properties
        skip_keys = {"resolved", "resolved_to", "target_file"}
        for k, v in self.metadata.items():
            if k not in skip_keys:
                ET.SubElement(tool_el, "property", name=str(k), value=str(v))
        return tool_el

    def get_dot_attributes(self) -> Dict[str, str]:
        """Returns Graphviz DOT attributes specific to this transition based on metadata."""
        attrs: Dict[str, str] = {}
        if not self.metadata:
            return attrs

        res = self.call_resolution
        if res is not None:
            if res.resolved:
                attrs["color"] = "#2e7d32"
                target = res.resolved_to or ""
                target_file = res.target_file or ""
                tooltip_text = f"Resolved to {target} in {target_file}" if target_file else f"Resolved to {target}"
                attrs["tooltip"] = tooltip_text
            else:
                attrs["color"] = "#e65100"
                attrs["tooltip"] = "Unresolved call"

        # Tooltip fallback for generic metadata if not already set by call resolution
        if "tooltip" not in attrs:
            if "tooltip" in self.metadata:
                attrs["tooltip"] = str(self.metadata["tooltip"])
            elif self.metadata:
                items_str = ", ".join(f"{k}={v}" for k, v in self.metadata.items())
                attrs["tooltip"] = items_str

        return attrs


class Arc:
    """Represents a directed Arc connecting a Place to a Transition or vice versa.

    Enforces the Petri net bipartite graph constraint:
    arcs can only connect Place -> Transition or Transition -> Place.
    """

    def __init__(
        self,
        source: Union[Place, Transition],
        target: Union[Place, Transition],
        weight: int = 1,
    ) -> None:
        is_place_to_trans = isinstance(source, Place) and isinstance(target, Transition)
        is_trans_to_place = isinstance(source, Transition) and isinstance(target, Place)

        if not (is_place_to_trans or is_trans_to_place):
            source_type = type(source).__name__
            target_type = type(target).__name__
            raise ValueError(
                f"Bipartite constraint violation: Arcs must connect Place -> Transition "
                f"or Transition -> Place. Got {source_type} -> {target_type}."
            )

        self.source = source
        self.target = target
        self.weight = int(weight)

    def __repr__(self) -> str:
        return (
            f"Arc(source={self.source.id!r}, target={self.target.id!r}, "
            f"weight={self.weight!r})"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the Arc into a dictionary."""
        return {
            "source": self.source.id,
            "target": self.target.id,
            "weight": self.weight,
        }


class PetriNet:
    """Container for Petri net components (places, transitions, arcs)."""

    def __init__(self) -> None:
        self.places: List[Place] = []
        self.transitions: List[Transition] = []
        self.arcs: List[Arc] = []

    def add_place(
        self,
        id_: Optional[str] = None,
        label: str = "",
        line_number: Optional[int] = None,
        initial_tokens: int = 0,
        id: Optional[str] = None,
    ) -> Place:
        node_id = id if id is not None else id_
        place = Place(
            id=node_id,
            label=label,
            line_number=line_number,
            initial_tokens=initial_tokens,
        )
        self.places.append(place)
        return place

    def add_transition(
        self,
        id_: Optional[str] = None,
        label: str = "",
        line_number: Optional[int] = None,
        id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Transition:
        node_id = id if id is not None else id_
        transition = Transition(
            id=node_id,
            label=label,
            line_number=line_number,
            metadata=metadata,
        )
        self.transitions.append(transition)
        return transition

    def add_arc(
        self,
        source: Union[Place, Transition],
        target: Union[Place, Transition],
        weight: int = 1,
    ) -> Arc:
        arc = Arc(source=source, target=target, weight=weight)
        self.arcs.append(arc)
        return arc

    def to_pnml(self) -> str:
        """Serializes the Petri net to ISO/IEC 15909-2 compliant PNML XML."""
        pnml = ET.Element("pnml", xmlns="http://www.pnml.org/version-2009/grammar/pnml")
        net = ET.SubElement(
            pnml,
            "net",
            id="net0",
            type="http://www.pnml.org/version-2009/grammar/ptnet",
        )

        name = ET.SubElement(net, "name")
        text = ET.SubElement(name, "text")
        text.text = "PetriNet"

        page = ET.SubElement(net, "page", id="page0")

        for place in self.places:
            p_el = ET.SubElement(page, "place", id=place.id)
            p_name = ET.SubElement(p_el, "name")
            p_text = ET.SubElement(p_name, "text")
            p_text.text = place.label
            if place.initial_tokens > 0:
                init_mark = ET.SubElement(p_el, "initialMarking")
                init_text = ET.SubElement(init_mark, "text")
                init_text.text = str(place.initial_tokens)

        for transition in self.transitions:
            t_el = ET.SubElement(page, "transition", id=transition.id)
            t_name = ET.SubElement(t_el, "name")
            t_text = ET.SubElement(t_name, "text")
            t_text.text = transition.label
            transition.add_pnml_toolspecific(t_el)

        for i, arc in enumerate(self.arcs):
            arc_id = f"a{i+1}"
            a_el = ET.SubElement(
                page,
                "arc",
                id=arc_id,
                source=arc.source.id,
                target=arc.target.id,
            )
            if arc.weight != 1:
                inscription = ET.SubElement(a_el, "inscription")
                ins_text = ET.SubElement(inscription, "text")
                ins_text.text = str(arc.weight)

        ET.indent(pnml, space="  ", level=0)
        return ET.tostring(pnml, encoding="utf-8", xml_declaration=True).decode("utf-8")

    def to_dot(self) -> str:
        """Serializes the Petri net to Graphviz DOT format."""
        def escape_dot(text: str) -> str:
            return (
                text.replace('\\', '\\\\')
                .replace('"', '\\"')
                .replace('\n', '\\n')
                .replace('\r', '')
            )

        lines = [
            "digraph PetriNet {",
            "    rankdir=TB;",
            "",
            "    // Places",
        ]

        for place in self.places:
            label = place.label
            if place.initial_tokens > 0:
                label = f"{label} (tokens: {place.initial_tokens})"
            escaped_label = escape_dot(label)
            escaped_id = escape_dot(place.id)
            lines.append(f'    "{escaped_id}" [shape=circle, label="{escaped_label}"];')

        lines.append("")
        lines.append("    // Transitions")
        for transition in self.transitions:
            label = transition.label
            if transition.line_number is not None:
                label = f"{label} (line {transition.line_number})"
            escaped_label = escape_dot(label)
            escaped_id = escape_dot(transition.id)
            extra_attrs = ""
            dot_attrs = transition.get_dot_attributes()
            if dot_attrs:
                attrs_parts = []
                if "color" in dot_attrs:
                    attrs_parts.append(f'color="{dot_attrs["color"]}"')
                if "tooltip" in dot_attrs:
                    attrs_parts.append(f'tooltip="{escape_dot(dot_attrs["tooltip"])}"')
                for k, v in dot_attrs.items():
                    if k not in ("color", "tooltip"):
                        attrs_parts.append(f'{k}="{escape_dot(v)}"')
                if attrs_parts:
                    extra_attrs = ", " + ", ".join(attrs_parts)
            lines.append(
                f'    "{escaped_id}" [shape=rect, style=filled, fillcolor=black, '
                f'fontcolor=white, label="{escaped_label}"{extra_attrs}];'
            )

        lines.append("")
        lines.append("    // Arcs")
        for arc in self.arcs:
            source_id = escape_dot(arc.source.id)
            target_id = escape_dot(arc.target.id)
            if arc.weight > 1:
                lines.append(f'    "{source_id}" -> "{target_id}" [label="{arc.weight}"];')
            else:
                lines.append(f'    "{source_id}" -> "{target_id}";')

        lines.append("}")
        return "\n".join(lines) + "\n"

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the Petri net into a dictionary structure."""
        return {
            "places": [p.to_dict() for p in self.places],
            "transitions": [t.to_dict() for t in self.transitions],
            "arcs": [a.to_dict() for a in self.arcs],
        }

    def to_json(self, indent: int = 2) -> str:
        """Serializes the Petri net into formatted JSON."""
        return json.dumps(self.to_dict(), indent=indent) + "\n"
