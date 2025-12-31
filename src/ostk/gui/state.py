"""Application state management for OSTK GUI."""

from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd


@dataclass
class QueryParams:
    """Parameters for trino.history() query."""

    icao24: Optional[str] = None
    start: Optional[str] = None
    stop: Optional[str] = None
    callsign: Optional[str] = None
    bounds: Optional[tuple] = None
    departure_airport: Optional[str] = None
    arrival_airport: Optional[str] = None
    airport: Optional[str] = None
    time_buffer: Optional[str] = None
    limit: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict, excluding None values."""
        return {k: v for k, v in self.__dict__.items() if v is not None}

    def clear(self) -> None:
        """Reset all parameters to None."""
        self.icao24 = None
        self.start = None
        self.stop = None
        self.callsign = None
        self.bounds = None
        self.departure_airport = None
        self.arrival_airport = None
        self.airport = None
        self.time_buffer = None
        self.limit = None

    def update_from_dict(self, params: dict) -> None:
        """Update parameters from a dictionary."""
        for key, value in params.items():
            if hasattr(self, key):
                setattr(self, key, value)


@dataclass
class Message:
    """A chat message."""

    role: str  # 'user' or 'assistant'
    content: str
    msg_type: str = "text"  # 'text', 'code', 'error'


@dataclass
class AppState:
    """Global application state."""

    messages: list[Message] = field(default_factory=list)
    current_params: QueryParams = field(default_factory=QueryParams)
    is_executing: bool = False
    last_result: Optional[pd.DataFrame] = None
    agent: Optional[Any] = None  # Will be Agent instance
    error_message: Optional[str] = None
    provider_name: Optional[str] = None
    model_name: Optional[str] = None

    def add_message(self, role: str, content: str, msg_type: str = "text") -> Message:
        """Add a message to the chat history."""
        msg = Message(role=role, content=content, msg_type=msg_type)
        self.messages.append(msg)
        return msg

    def clear_messages(self) -> None:
        """Clear chat history."""
        self.messages.clear()
