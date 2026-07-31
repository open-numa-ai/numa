"""Tool extension point."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict


class ToolInput(BaseModel):
    """Base model that rejects undeclared tool arguments."""

    model_config = ConfigDict(extra="forbid")


class EmptyToolInput(ToolInput):
    """Input model for tools that accept no arguments."""


class ToolSchema(ABC):
    """Shared schema contract for synchronous and asynchronous Tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique tool name used for lookup."""

    @property
    def description(self) -> str:
        """Return a human-readable description of the tool."""
        return ""

    @property
    def input_model(self) -> type[BaseModel]:
        """Return the Pydantic model used to validate tool arguments."""
        return EmptyToolInput

    @property
    def output_model(self) -> type[BaseModel] | None:
        """Return the optional Pydantic model used to validate tool output."""
        return None

    @property
    def input_schema(self) -> dict[str, Any]:
        """Return the tool input contract as JSON Schema."""
        return self.input_model.model_json_schema()

    @property
    def output_schema(self) -> dict[str, Any] | None:
        """Return the tool output contract as JSON Schema when declared."""
        if self.output_model is None:
            return None
        return self.output_model.model_json_schema()

class Tool(ToolSchema):
    """A capability that can be registered with a synchronous Runtime."""

    @abstractmethod
    def execute(self, **arguments: Any) -> Any:
        """Execute the Tool with validated implementation-specific arguments."""
