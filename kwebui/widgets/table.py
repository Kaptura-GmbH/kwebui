"""Table widget: a read-only, dataframe-style grid.

Accepts whichever of these shapes ``data`` happens to be in -- no pandas
dependency required to use any of them:

    self.table([{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}])
    self.table({"name": ["Alice", "Bob"], "age": [30, 25]})
    self.table([[30, "Alice"], [25, "Bob"]], columns=["age", "name"])

A real ``pandas.DataFrame`` (or anything else exposing the same
``.columns``/``.values`` shape, e.g. polars via ``.to_pandas()``-free duck
typing) also works, detected structurally rather than by importing
pandas -- this widget never adds pandas as a dependency, it just accepts
one if the caller already has it.
"""

from __future__ import annotations

from typing import Any

from ..plugin import WidgetPlugin
from ..widget import Widget


def _cell(value: Any) -> str:
    return "" if value is None else str(value)


def _normalize_table_data(data: Any, columns: list[Any] | None) -> tuple[list[str], list[list[str]]]:
    """Turn any supported ``data`` shape into (headers, rows) of strings."""
    if data is None:
        return [str(c) for c in columns] if columns else [], []

    if isinstance(data, dict):
        headers = list(columns) if columns is not None else list(data.keys())
        column_values = [data.get(h, []) for h in headers]
        row_count = max((len(col) for col in column_values), default=0)
        rows = [
            [_cell(column_values[ci][ri]) if ri < len(column_values[ci]) else "" for ci in range(len(headers))]
            for ri in range(row_count)
        ]
        return [str(h) for h in headers], rows

    if isinstance(data, (list, tuple)):
        if not data:
            return [str(c) for c in columns] if columns else [], []
        if isinstance(data[0], dict):
            headers = list(columns) if columns is not None else list(data[0].keys())
            rows = [[_cell(row.get(h)) for h in headers] for row in data]
            return [str(h) for h in headers], rows
        headers = [str(c) for c in columns] if columns is not None else [str(i) for i in range(len(data[0]))]
        rows = [[_cell(v) for v in row] for row in data]
        return headers, rows

    if hasattr(data, "columns") and hasattr(data, "values"):
        # Duck-typed DataFrame-like object (pandas, ...) -- never imported.
        headers = [str(c) for c in columns] if columns is not None else [str(c) for c in data.columns]
        rows = [[_cell(v) for v in row] for row in data.values.tolist()]
        return headers, rows

    raise TypeError(f"Unsupported table data type: {type(data)!r}")


class TableWidget(Widget):
    def set_data(self, data: Any, *, columns: list[Any] | None = None) -> "TableWidget":
        """Replace the table's content. ``columns`` overrides inferred headers."""
        headers, rows = _normalize_table_data(data, columns)
        self.update(columns=headers, rows=rows)
        return self

    def set_width(self, width: float) -> "TableWidget":
        """Resize the table. -1 or 0 falls back to sizing to its content.
        Ignored while ``stretch`` is True."""
        self.update(width=width)
        return self

    def set_stretch(self, stretch: bool) -> "TableWidget":
        """Toggle whether the table fills its parent's width."""
        self.update(stretch=stretch)
        return self

    def set_border(self, border: bool) -> "TableWidget":
        """Toggle the border drawn around the table and between cells."""
        self.update(border=border)
        return self

    def set_hide_header(self, hide_header: bool) -> "TableWidget":
        """Toggle whether the header row is shown."""
        self.update(hide_header=hide_header)
        return self


class TablePlugin(WidgetPlugin):
    """
    Example:
        app.table([{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}])
        app.table({"name": ["Alice", "Bob"], "age": [30, 25]}, hide_header=True)
        app.table(rows, columns=["age", "name"], stretch=True, border=False)
    """

    widget_name = "table"

    def create(
        self,
        widget_id: str,
        data: Any = None,
        *,
        columns: list[Any] | None = None,
        width: float = -1,
        stretch: bool = False,
        border: bool = True,
        hide_header: bool = False,
    ) -> TableWidget:
        headers, rows = _normalize_table_data(data, columns)
        props = {
            "columns": headers,
            "rows": rows,
            "width": width,
            "stretch": stretch,
            "border": border,
            "hide_header": hide_header,
        }
        return TableWidget(widget_id, self.widget_name, props)
