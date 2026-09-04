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


class Transition:
    """Represents a Petri net Transition (an action or statement execution)."""

    def __init__(
        self,
        id_: Optional[str] = None,
        label: str = "",
        line_number: Optional[int] = None,
        id: Optional[str] = None,
    ) -> None:
        node_id = id if id is not None else id_
        if node_id is None:
            raise ValueError("Transition requires an id.")
        self.id = str(node_id)
        self.label = str(label)
        self.line_number = line_number

    def __repr__(self) -> str:
        return (
            f"Transition(id={self.id!r}, label={self.label!r}, "
            f"line_number={self.line_number!r})"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the Transition into a dictionary."""
        return {
            "id": self.id,
            "label": self.label,
            "line_number": self.line_number,
        }


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
    ) -> Transition:
        node_id = id if id is not None else id_
        transition = Transition(
            id=node_id,
            label=label,
            line_number=line_number,
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
            lines.append(
                f'    "{escaped_id}" [shape=rect, style=filled, fillcolor=black, '
                f'fontcolor=white, label="{escaped_label}"];'
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
