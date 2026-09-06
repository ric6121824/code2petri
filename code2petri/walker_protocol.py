from abc import ABC, abstractmethod
from typing import Any, List, Optional

from code2petri.model import PetriNet


class WalkerProtocol(ABC):
    """Abstract base class establishing the contract for language-specific AST walkers."""

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
    def walk_function(self, ast_node: Any) -> PetriNet:
        """Walks a function/method AST node and constructs a PetriNet model."""
        ...
