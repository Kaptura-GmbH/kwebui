"""The event value object passed from the WebSocket layer to plugins."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Event:
    """A single browser-originated event addressed to one widget.

    ``type`` is widget-defined (e.g. "click", "change", "select") -- the
    core never inspects it, only routes it to the target widget's plugin.
    """

    widget_id: str
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
