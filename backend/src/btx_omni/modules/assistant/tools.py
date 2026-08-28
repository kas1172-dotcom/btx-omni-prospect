"""Allow-listed, read-only Omni query execution."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass


class GovernedToolError(ValueError):
    pass


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: Mapping[str, object]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    required_arguments: tuple[str, ...]
    read_only: bool = True


class GovernedReadTools:
    """Executes a tiny explicit registry; it cannot discover code, SQL, URLs, or writes."""

    definitions = (
        ToolDefinition(
            "resolve_governed_context",
            "Resolve Customer, Intelligence, Map, Relationship, Action, and screen context through canonical application reads.",
            ("question",),
        ),
    )

    def __init__(
        self, handler: Callable[[Mapping[str, object]], object], *, max_calls: int = 1
    ) -> None:
        self._handler = handler
        self.max_calls = max_calls

    def execute(self, calls: tuple[ToolCall, ...]) -> tuple[object, ...]:
        if len(calls) > self.max_calls:
            raise GovernedToolError("Omni read-tool call limit exceeded.")
        results: list[object] = []
        for call in calls:
            definition = next(
                (item for item in self.definitions if item.name == call.name), None
            )
            if definition is None:
                raise GovernedToolError("Unknown Omni read tool.")
            if set(definition.required_arguments) - set(call.arguments):
                raise GovernedToolError("Omni read-tool arguments are incomplete.")
            if not isinstance(call.arguments.get("question"), str):
                raise GovernedToolError("Omni read-tool question must be text.")
            results.append(self._handler(call.arguments))
        return tuple(results)
