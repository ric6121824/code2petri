from dataclasses import dataclass
import json
from typing import Optional, Union, List, Dict, Any, Set, Tuple
import xml.etree.ElementTree as ET


class RenderingConfig:
    """Central configuration for Petri net visualization and styling."""
    RESOLVED_COLOR: str = "#2e7d32"
    UNRESOLVED_COLOR: str = "#e65100"
    DEFAULT_FILLCOLOR: str = "black"
    DEFAULT_FONTCOLOR: str = "white"


def escape_dot(text: str) -> str:
    """Escapes special characters for Graphviz DOT string literals."""
    return (
        str(text)
        .replace('\\', '\\\\')
        .replace('"', '\\"')
        .replace('\n', '\\n')
        .replace('\r', '')
    )


@dataclass
class CompoundContainer:
    """Represents a compound node (container) for an inlined function subnet."""
    id: str
    label: str
    function_name: str
    file: str = ""
    parent: Optional[str] = None
    node_ids: Optional[Set[str]] = None
    function_ref: Optional[str] = None

    def __post_init__(self) -> None:
        if self.node_ids is None:
            self.node_ids = set()

    def to_dict(self) -> Dict[str, Any]:
        record = {
            "id": self.id,
            "label": self.label,
            "function_name": self.function_name,
            "file": self.file,
            "parent": self.parent,
        }
        if self.function_ref:
            record["function_ref"] = self.function_ref
        return record




class NodeBase:
    """Base class for Petri net nodes (Places and Transitions) carrying hierarchy and metadata."""

    def __init__(
        self,
        id: str,
        label: str = "",
        line_number: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        parent: Optional[str] = None,
        enclosing_function: Optional[str] = None,
    ) -> None:
        self.id = str(id)
        self.label = str(label)
        self.line_number = line_number
        self.metadata: Optional[Dict[str, Any]] = dict(metadata) if metadata is not None else None
        if parent is not None:
            if self.metadata is None:
                self.metadata = {}
            self.metadata["parent"] = parent
        if enclosing_function is not None:
            if self.metadata is None:
                self.metadata = {}
            self.metadata["enclosing_function"] = enclosing_function

    @property
    def parent(self) -> Optional[str]:
        """Returns the parent compound ID if this node is enclosed in a compound node."""
        return self.metadata.get("parent") if self.metadata else None

    @parent.setter
    def parent(self, value: Optional[str]) -> None:
        if self.metadata is None:
            self.metadata = {}
        self.metadata["parent"] = value

    @property
    def enclosing_function(self) -> Optional[str]:
        """Returns the name of the function enclosing this node."""
        return self.metadata.get("enclosing_function") if self.metadata else None

    @enclosing_function.setter
    def enclosing_function(self, value: Optional[str]) -> None:
        if self.metadata is None:
            self.metadata = {}
        self.metadata["enclosing_function"] = value

    def _serialize_base_dict(self) -> Dict[str, Any]:
        """Serializes base node fields and hierarchy metadata."""
        d: Dict[str, Any] = {
            "id": self.id,
            "label": self.label,
            "line_number": self.line_number,
        }
        if self.metadata is not None:
            d["metadata"] = dict(self.metadata)
            if "parent" in self.metadata:
                d["parent"] = self.metadata["parent"]
            if "enclosing_function" in self.metadata:
                d["enclosing_function"] = self.metadata["enclosing_function"]
        return d


class Place(NodeBase):
    """Represents a Petri net Place (control point where execution can rest)."""

    def __init__(
        self,
        id_: Optional[str] = None,
        label: str = "",
        line_number: Optional[int] = None,
        initial_tokens: int = 0,
        id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        parent: Optional[str] = None,
        enclosing_function: Optional[str] = None,
    ) -> None:
        node_id = id if id is not None else id_
        if node_id is None:
            raise ValueError("Place requires an id.")
        super().__init__(
            id=node_id,
            label=label,
            line_number=line_number,
            metadata=metadata,
            parent=parent,
            enclosing_function=enclosing_function,
        )
        self.initial_tokens = int(initial_tokens)

    def __repr__(self) -> str:
        meta_str = f", metadata={self.metadata!r}" if self.metadata is not None else ""
        return (
            f"Place(id={self.id!r}, label={self.label!r}, "
            f"line_number={self.line_number!r}, initial_tokens={self.initial_tokens!r}{meta_str})"
        )

    def to_dot_node(self) -> str:
        """Serializes the Place to a Graphviz DOT node statement."""
        label = self.label
        if self.initial_tokens > 0:
            label = f"{label} (tokens: {self.initial_tokens})"
        escaped_label = escape_dot(label)
        escaped_id = escape_dot(self.id)
        return f'    "{escaped_id}" [shape=circle, label="{escaped_label}"];'

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the Place into a dictionary."""
        d = self._serialize_base_dict()
        d["initial_tokens"] = self.initial_tokens
        return d

    @property
    def is_start(self) -> bool:
        """Returns True if this place functions as a start/source place."""
        return self.initial_tokens > 0 or self.label == "start"

    @property
    def is_end(self) -> bool:
        """Returns True if this place functions as an end/sink place."""
        return self.label == "end"



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


class Transition(NodeBase):
    """Represents a Petri net Transition (an action or statement execution)."""

    RESERVED_METADATA_KEYS: Set[str] = {
        "resolved", "resolved_to", "target_file", "status", "opaque", "inline_expansion"
    }

    def __init__(
        self,
        id_: Optional[str] = None,
        label: str = "",
        line_number: Optional[int] = None,
        id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        resolution: Optional[CallResolution] = None,
        parent: Optional[str] = None,
        enclosing_function: Optional[str] = None,
    ) -> None:
        node_id = id if id is not None else id_
        if node_id is None:
            raise ValueError("Transition requires an id.")
        super().__init__(
            id=node_id,
            label=label,
            line_number=line_number,
            metadata=metadata,
            parent=parent,
            enclosing_function=enclosing_function,
        )
        if resolution is not None:
            self.resolution: Optional[CallResolution] = resolution
        elif self.metadata is not None:
            self.resolution = CallResolution.from_metadata(self.metadata)
        else:
            self.resolution = None

    def __repr__(self) -> str:
        metadata_str = f", metadata={self.metadata!r}" if self.metadata is not None else ""
        res_str = f", resolution={self.resolution!r}" if self.resolution is not None else ""
        return (
            f"Transition(id={self.id!r}, label={self.label!r}, "
            f"line_number={self.line_number!r}{metadata_str}{res_str})"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the Transition into a dictionary."""
        d = self._serialize_base_dict()
        if self.resolution is not None:
            d["resolved"] = self.resolution.resolved
            if self.resolution.resolved_to is not None:
                d["resolved_to"] = self.resolution.resolved_to
            if self.resolution.target_file is not None:
                d["target_file"] = self.resolution.target_file
            if not self.resolution.resolved:
                d["status"] = "[unresolved]"
        return d

    @property
    def is_opaque(self) -> bool:
        """Returns True if this transition is an opaque transition (folded component or unexpanded call)."""
        return bool(self.metadata and self.metadata.get("opaque"))

    @property
    def is_inlined(self) -> bool:
        """Returns True if this transition was introduced via inline expansion."""
        return bool(self.metadata and self.metadata.get("inline_expansion"))

    def get_tau(self) -> float:
        """Returns the accumulated complexity weight tau for this transition (default 1.0)."""
        if self.metadata and "tau" in self.metadata:
            return float(self.metadata["tau"])
        return 1.0

    def add_pnml_toolspecific(self, parent_element: ET.Element) -> Optional[ET.Element]:
        """Appends <toolspecific> XML element with metadata properties to parent_element."""
        if not self.metadata and self.resolution is None:
            return None
        tool_el = ET.SubElement(parent_element, "toolspecific", tool="code2petri", version="1.0")
        if self.resolution is not None:
            if self.resolution.resolved:
                target = str(self.resolution.resolved_to or "")
                target_file = str(self.resolution.target_file or "")
                ET.SubElement(tool_el, "resolved", target=target, file=target_file)
            else:
                ET.SubElement(tool_el, "unresolved")

        # Emit any other custom properties
        if self.metadata:
            for k, v in self.metadata.items():
                if k not in self.RESERVED_METADATA_KEYS:
                    ET.SubElement(tool_el, "property", name=str(k), value=str(v))
        return tool_el

    def get_dot_attributes(self) -> Dict[str, str]:
        """Returns Graphviz DOT attributes specific to this transition based on resolution and metadata."""
        attrs: Dict[str, str] = {}
        if self.resolution is not None:
            if self.resolution.resolved:
                attrs["fillcolor"] = RenderingConfig.RESOLVED_COLOR
                target = self.resolution.resolved_to or ""
                target_file = self.resolution.target_file or ""
                tooltip_text = f"Resolved to {target} in {target_file}" if target_file else f"Resolved to {target}"
                attrs["tooltip"] = tooltip_text
            else:
                attrs["fillcolor"] = RenderingConfig.UNRESOLVED_COLOR
                attrs["tooltip"] = "Unresolved call"

        # Tooltip fallback for generic metadata if not already set by call resolution
        if "tooltip" not in attrs:
            if self.metadata and "tooltip" in self.metadata:
                attrs["tooltip"] = str(self.metadata["tooltip"])
            elif self.metadata:
                items = [f"{k}={v}" for k, v in self.metadata.items() if k not in self.RESERVED_METADATA_KEYS]
                if items:
                    attrs["tooltip"] = ", ".join(items)

        return attrs

    def to_dot_node(self) -> str:
        """Serializes the Transition to a Graphviz DOT node statement."""
        label = self.label
        if self.line_number is not None:
            label = f"{label} (line {self.line_number})"
        if self.is_opaque and self.metadata and "tau" in self.metadata:
            tau_val = self.get_tau()
            tau_str = f"{tau_val:.1f}" if isinstance(tau_val, float) and tau_val.is_integer() else f"{tau_val}"
            if "(tau=" not in label and "tau=" not in label:
                label = f"{label} (tau={tau_str})"
        escaped_label = escape_dot(label)
        escaped_id = escape_dot(self.id)
        dot_attrs = self.get_dot_attributes()
        fillcolor = dot_attrs.get("fillcolor", RenderingConfig.DEFAULT_FILLCOLOR)
        fillcolor_val = f'"{fillcolor}"' if fillcolor.startswith("#") else fillcolor
        style_val = '"filled,bold"' if self.is_opaque else "filled"
        extra_attrs = ""
        if dot_attrs:
            attrs_parts = []
            if "tooltip" in dot_attrs:
                attrs_parts.append(f'tooltip="{escape_dot(dot_attrs["tooltip"])}"')
            for k, v in dot_attrs.items():
                if k not in ("fillcolor", "tooltip"):
                    attrs_parts.append(f'{k}="{escape_dot(v)}"')
            if attrs_parts:
                extra_attrs = ", " + ", ".join(attrs_parts)
        return (
            f'    "{escaped_id}" [shape=rect, style={style_val}, fillcolor={fillcolor_val}, '
            f'fontcolor={RenderingConfig.DEFAULT_FONTCOLOR}, label="{escaped_label}"{extra_attrs}];'
        )

    def mark_recursive_cycle(self) -> None:
        """Marks this transition as an opaque transition halting a recursive cycle."""
        if self.metadata is None:
            self.metadata = {}
        self.metadata["recursive_cycle"] = True



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

    def to_dot_edge(self) -> str:
        """Serializes the Arc to a Graphviz DOT edge statement."""
        source_id = escape_dot(self.source.id)
        target_id = escape_dot(self.target.id)
        if self.weight > 1:
            return f'    "{source_id}" -> "{target_id}" [label="{self.weight}"];'
        return f'    "{source_id}" -> "{target_id}";'

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
        self.compounds: List[CompoundContainer] = []
        self.return_metadata: Optional[Dict[str, Any]] = None
        self.function_metadata_registry: Dict[str, Dict[str, Any]] = {}

    def add_place(
        self,
        id_: Optional[str] = None,
        label: str = "",
        line_number: Optional[int] = None,
        initial_tokens: int = 0,
        id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        parent: Optional[str] = None,
        enclosing_function: Optional[str] = None,
    ) -> Place:
        node_id = id if id is not None else id_
        place = Place(
            id=node_id,
            label=label,
            line_number=line_number,
            initial_tokens=initial_tokens,
            metadata=metadata,
            parent=parent,
            enclosing_function=enclosing_function,
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
        resolution: Optional[CallResolution] = None,
        parent: Optional[str] = None,
        enclosing_function: Optional[str] = None,
    ) -> Transition:
        node_id = id if id is not None else id_
        transition = Transition(
            id=node_id,
            label=label,
            line_number=line_number,
            metadata=metadata,
            resolution=resolution,
            parent=parent,
            enclosing_function=enclosing_function,
        )
        self.transitions.append(transition)
        return transition

    def add_compound(
        self,
        id: str,
        label: str,
        function_name: str,
        file: Optional[str] = None,
        parent: Optional[str] = None,
        node_ids: Optional[Set[str]] = None,
        function_ref: Optional[str] = None,
    ) -> CompoundContainer:
        """Registers a compound node representing an inlined function container."""
        for c in self.compounds:
            if c.id == id:
                return c
        compound = CompoundContainer(
            id=str(id),
            label=str(label),
            function_name=str(function_name),
            file=str(file or ""),
            parent=parent,
            node_ids=set(node_ids) if node_ids else set(),
            function_ref=function_ref,
        )
        self.compounds.append(compound)
        return compound

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

    def to_dot(self, title: Optional[str] = None) -> str:
        """Serializes the Petri net to Graphviz DOT format.

        :param title: Optional graph title/label to render at top of graph.
        """
        lines = [
            "digraph PetriNet {",
            "    rankdir=TB;",
        ]
        if title:
            lines.append('    labelloc="t";')
            lines.append(f'    label="{escape_dot(title)}";')
        lines.append("")
        lines.append("    // Places")
        for place in self.places:
            lines.append(place.to_dot_node())

        lines.append("")
        lines.append("    // Transitions")
        for transition in self.transitions:
            lines.append(transition.to_dot_node())

        lines.append("")
        lines.append("    // Arcs")
        for arc in self.arcs:
            lines.append(arc.to_dot_edge())

        lines.append("}")
        return "\n".join(lines) + "\n"

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the Petri net into a dictionary structure."""
        d: Dict[str, Any] = {
            "places": [p.to_dict() for p in self.places],
            "transitions": [t.to_dict() for t in self.transitions],
            "arcs": [a.to_dict() for a in self.arcs],
        }
        if self.compounds:
            d["compounds"] = [c.to_dict() for c in self.compounds]
        if self.return_metadata is not None:
            d["return_metadata"] = json.loads(json.dumps(self.return_metadata))
        if self.function_metadata_registry:
            d["function_metadata_registry"] = json.loads(json.dumps(self.function_metadata_registry))
        return d

    def to_json(self, indent: int = 2) -> str:
        """Serializes the Petri net into formatted JSON."""
        return json.dumps(self.to_dict(), indent=indent) + "\n"

    def get_node_map(self) -> Dict[str, Union[Place, Transition]]:
        """Returns a mapping of node IDs to Place and Transition instances."""
        nodes: Dict[str, Union[Place, Transition]] = {p.id: p for p in self.places}
        nodes.update({t.id: t for t in self.transitions})
        return nodes

    def clone(self) -> "PetriNet":
        """Creates a deep copy of the PetriNet including places, transitions, metadata, and arcs."""
        new_net = PetriNet()
        new_net.return_metadata = json.loads(json.dumps(self.return_metadata)) if self.return_metadata is not None else None
        new_net.function_metadata_registry = json.loads(json.dumps(self.function_metadata_registry))

        for p in self.places:
            new_p_meta = dict(p.metadata) if p.metadata else None
            new_net.add_place(
                id=p.id,
                label=p.label,
                line_number=p.line_number,
                initial_tokens=p.initial_tokens,
                metadata=new_p_meta,
            )

        for t in self.transitions:
            new_meta = dict(t.metadata) if t.metadata else None
            new_res = None
            if t.resolution is not None:
                new_res = CallResolution(
                    resolved=t.resolution.resolved,
                    resolved_to=t.resolution.resolved_to,
                    target_file=t.resolution.target_file,
                )
            new_net.add_transition(
                id=t.id,
                label=t.label,
                line_number=t.line_number,
                metadata=new_meta,
                resolution=new_res,
            )

        new_net.compounds = [
            CompoundContainer(
                id=c.id,
                label=c.label,
                function_name=c.function_name,
                file=c.file,
                parent=c.parent,
                node_ids=set(c.node_ids) if c.node_ids else set(),
                function_ref=c.function_ref,
            )
            for c in self.compounds
        ]

        node_map = new_net.get_node_map()
        for a in self.arcs:
            new_net.add_arc(
                source=node_map[a.source.id],
                target=node_map[a.target.id],
                weight=a.weight,
            )

        return new_net

    def remove_nodes(self, node_ids: Union[Set[str], List[str]]) -> None:
        """Removes places and transitions matching node_ids and any connected arcs."""
        ids_to_remove = set(node_ids)
        self.places = [p for p in self.places if p.id not in ids_to_remove]
        self.transitions = [t for t in self.transitions if t.id not in ids_to_remove]
        self.arcs = [
            a for a in self.arcs
            if a.source.id not in ids_to_remove and a.target.id not in ids_to_remove
        ]

    def find_boundary_places(self) -> Tuple[Optional[Place], Optional[Place]]:
        """Identifies the primary source (start) and sink (end) boundary places of the Petri net."""
        start_places = [p for p in self.places if p.is_start]
        source_place = start_places[0] if start_places else (self.places[0] if self.places else None)

        end_places = [p for p in self.places if p.is_end]
        sink_place = end_places[0] if end_places else (self.places[-1] if self.places else None)

        return source_place, sink_place


