from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, NamedTuple, Optional

from code2petri.model import PetriNet, Place, Transition, Arc


@dataclass
class CallSite:
    """Represents an extracted function call site within an analyzed function."""
    caller_function: str
    caller_file: str
    callee_name: str
    callee_owner: Optional[str]
    line_number: int
    transition_id: str


class WalkResult(NamedTuple):
    """Container packaging the generated PetriNet and extracted CallSite records."""
    net: PetriNet
    call_sites: List[CallSite]


class WalkerProtocol(ABC):
    """Walker protocol establishing the contract for language-specific AST walkers."""

    @abstractmethod
    def parse_file(self, filepath: str) -> Any:
        """Parses a source file into an AST."""
        ...

    @abstractmethod
    def find_function(self, tree: Any, func_name: str) -> Optional[Any]:
        """Locates a function or method AST node by name within an AST."""
        ...

    @abstractmethod
    def find_all_functions(self, tree: Any) -> List[str]:
        """Finds all discoverable function and method names within an AST."""
        ...

    @abstractmethod
    def walk_function(
        self,
        ast_node: Any,
        func_name: str = "",
        filepath: Optional[str] = None,
    ) -> WalkResult:
        """Walks a function/method AST node and constructs a PetriNet model packaged in a WalkResult."""
        ...

    @abstractmethod
    def collect_variable_bindings(self, tree: Any) -> Dict[str, str]:
        """Scans the complete file AST and returns a mapping of variable names to class names."""
        ...

    @abstractmethod
    def get_node_lineno(self, ast_node: Any) -> int:
        """Returns the start line number for an AST node, defaulting to 0."""
        ...

