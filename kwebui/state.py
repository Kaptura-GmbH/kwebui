"""A small dict-with-attribute-access container used as ``Session.state``.

Kept separate from ``session.py`` because it has exactly one job: give
advanced users a scratchpad that feels like a plain object
(``app.session.state.count = 0``) while still behaving like a dict.
"""

from __future__ import annotations

from collections.abc import Iterator, MutableMapping
from typing import Any


class SessionState(MutableMapping[str, Any]):
    """Per-session scratch storage for advanced use cases.

    Most widgets already keep their own state (a checkbox remembers
    whether it is checked); this is for arbitrary extra data a developer
    wants to associate with one browser connection.
    """

    def __init__(self) -> None:
        object.__setattr__(self, "_data", {})

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    def __delitem__(self, key: str) -> None:
        del self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __getattr__(self, name: str) -> Any:
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(name) from None

    def __setattr__(self, name: str, value: Any) -> None:
        self._data[name] = value

    def __repr__(self) -> str:
        return f"SessionState({self._data!r})"
