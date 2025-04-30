from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict

from rasa.dialogue_understanding.commands import CancelFlowCommand

@dataclass
class ModifiedCancelFlowCommand(CancelFlowCommand):
    """A command to cancel the current flow."""

    @classmethod
    def command(cls) -> str:
        """Returns the command type."""
        return "modified cancel flow"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ModifiedCancelFlowCommand:
        """Converts the dictionary to a command.

        Returns:
            The converted dictionary.
        """
        return ModifiedCancelFlowCommand()
    
    def __eq__(self, other: object) -> bool:
        return isinstance(other, ModifiedCancelFlowCommand)

    def to_dsl(self) -> str:
        """Converts the command to a DSL string."""
        return "cancel"

    @classmethod
    def from_dsl(cls, match: re.Match, **kwargs: Any) -> ModifiedCancelFlowCommand:
        """Converts a DSL string to a command."""
        return ModifiedCancelFlowCommand()

    @staticmethod
    def regex_pattern() -> str:
        return r"""^[\s\W\d]*cancel['"`]*$"""
