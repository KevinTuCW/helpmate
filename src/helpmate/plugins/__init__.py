"""Conversation turn plugins.

A turn plugin can own one assistant turn and return text verbatim. This is
different from the existing tool path, where tool output is converted into
context and then rewritten by the RAG generator.
"""
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass(frozen=True)
class TurnContext:
    question: str
    tenant_id: str
    customer_id: Optional[str] = None
    session_id: Optional[str] = None
    ext_session_id: Optional[str] = None
    tool_args: dict = field(default_factory=dict)


@dataclass(frozen=True)
class PluginReply:
    handled: bool
    plugin_name: str = ""
    answer: str = ""
    ext_session_id: Optional[str] = None
    closed: bool = True
    offer: Optional[dict] = None
    escape_hatch: Optional[str] = None
    next_action: Optional[str] = None
    status: Optional[str] = None
    meta: dict = field(default_factory=dict)

    @classmethod
    def fallback(cls, reason: str) -> "PluginReply":
        return cls(handled=False, meta={"fallback_reason": reason})


@dataclass(frozen=True)
class TurnPlugin:
    name: str
    tool_schema: dict
    handle: Callable[[TurnContext], PluginReply]
    terminal: bool = True
    actions: dict = field(default_factory=dict)

    @property
    def tool_name(self) -> str:
        return self.tool_schema["function"]["name"]
