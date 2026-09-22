"""Visual edit mode and JSON layouts -- ``KApp(edit_mode=True)``.

Two halves, both living here so the rest of the package stays untouched
apart from one constructor kwarg and a three-line hook in ``KApp.run()``
(see ``app.py``):

* **Layouts.** A page can be described as JSON and loaded with
  ``load_layout(self, "my_app.layout.json")``, which returns a
  ``dict[id -> Widget]`` so an app reaches its widgets by a *stable,
  human-chosen* id (``ui["save_button"]``) instead of the framework's
  positional ``w1``/``w2``.
* **The editor.** With ``edit_mode=True``, the same app serves an editing
  overlay: container borders become visible, right-click opens a
  searchable widget palette that inserts into that container, clicking
  selects a widget and shows its properties on the right, and every
  change is written straight back to the JSON file.

Why the saved format is *not* just ``serialize_page()``'s output, which
would have been the obvious choice: that shape is the **wire** format,
and it is lossy in exactly the ways a source file cannot afford.
``WidgetPlugin.serialize()`` drops every callable (so ``on_click`` can
never round-trip), and several plugins transform their arguments at
construction -- ``image``'s ``source`` becomes ``src`` plus a private
``_local_path``, ``table``'s ``data``/``columns`` become ``headers``/
``rows``, ``alert`` gains ``level``/``icon``, ``spinner`` gains
``active``/``elapsed`` -- so feeding serialized props back into
``create()`` would raise ``TypeError`` for those widgets. The layout file
therefore stores **constructor keyword arguments**, which is what
``create()`` actually accepts, plus a separate ``handlers`` map holding
method *names* (a JSON file cannot hold a Python function). Structurally
it still mirrors the wire shape -- ``type``/``id``/``props``/``children``
-- so it stays trivially readable by the Vue frontend's own conventions.
"""

from __future__ import annotations

import inspect
import json
import os
import tempfile
import typing
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from .renderer import serialize_page
from .widget import Widget

if TYPE_CHECKING:
    from fastapi import FastAPI

    from .app import KApp
    from .registry import WidgetRegistry

#: Bumped only if the on-disk shape changes incompatibly. Written into
#: every file so a future loader can tell old files apart rather than
#: guessing from which keys happen to be present.
LAYOUT_VERSION = 1

#: Widgets the palette deliberately does not offer.
#:
#: ``popup``/``toast`` remove themselves the moment they are answered or
#: time out, and ``spinner`` is only meaningful as a ``with`` block -- all
#: three are *events* an app fires at runtime, not page structure, so a
#: persisted layout containing one would either vanish on sight or sit
#: there inert. ``column`` is left out for the opposite reason: you never
#: add one yourself, because ``columns`` creates exactly ``n`` of them (see
#: ``_build_columns``) -- but you can right-click *into* a column, and it
#: still gets a full property panel, so it stays in the schema.
_PALETTE_EXCLUDED = frozenset({"popup", "toast", "spinner", "column"})

#: Widgets that accept children, i.e. that right-clicking offers to insert
#: into. ``columns`` is absent on purpose: its children are always exactly
#: its columns, never arbitrary widgets -- you insert into a *column*.
_CONTAINER_TYPES = frozenset({"container", "sidebar", "topbar", "empty", "column"})

#: Refused outright by the loader, with an explanation.
_REJECTED_TYPES = {
    "column": (
        "A column only exists inside a columns widget, which creates its own. "
        "Put the column inside a 'columns' node's children instead of at the top level."
    ),
}

#: Enum-valued parameters are plain ``str`` in every ``create()``
#: signature -- the allowed values are validated *inside* ``create()``
#: against a module constant, so ``inspect.signature`` cannot see them.
#: Where such a constant exists it is read at import time below (so the
#: palette can never drift from the validation); the rest are documented
#: only in prose in their widget's docstring and are listed here.
_ENUM_CHOICES: dict[tuple[str, str], list[str]] = {
    ("text", "align"): ["left", "center", "right"],
    ("container", "horizontal_alignment"): ["left", "center", "right"],
    ("container", "vertical_alignment"): ["top", "center", "bottom"],
    # A column takes the same layout options as a container (see
    # columns.py's ColumnPlugin), so it takes the same vocabulary too.
    ("column", "horizontal_alignment"): ["left", "center", "right"],
    ("column", "vertical_alignment"): ["top", "center", "bottom"],
}


def _load_enum_choices_from_modules() -> None:
    """Fill ``_ENUM_CHOICES`` from the widget modules' own constants.

    Read rather than duplicated, so adding a direction/level/kind in a
    widget module shows up in the property panel automatically instead of
    silently offering a stale list.
    """
    try:
        from .widgets.badge import _LEVELS as badge_levels

        _ENUM_CHOICES[("badge", "color")] = list(badge_levels)
    except Exception:  # pragma: no cover - a widget module may be absent
        pass
    try:
        from .widgets.container import _DIRECTIONS as container_directions

        _ENUM_CHOICES[("container", "direction")] = list(container_directions)
    except Exception:  # pragma: no cover
        pass
    try:
        from .widgets.columns import _DIRECTIONS as column_directions

        _ENUM_CHOICES[("column", "direction")] = list(column_directions)
    except Exception:  # pragma: no cover
        pass
    try:
        from .widgets.workflow_tracker import _ORIENTATIONS as wt_orientations

        _ENUM_CHOICES[("workflow_tracker", "orientation")] = sorted(wt_orientations)
    except Exception:  # pragma: no cover
        pass
    try:
        from .widgets.toast import _ICONS as toast_icons

        _ENUM_CHOICES[("toast", "level")] = list(toast_icons)
    except Exception:  # pragma: no cover
        pass
    try:
        from .widgets.popup import _BUTTON_SETS as popup_kinds

        _ENUM_CHOICES[("popup", "kind")] = list(popup_kinds)
    except Exception:  # pragma: no cover
        pass


_load_enum_choices_from_modules()

#: Friendlier labels for parameters whose real name is too terse to be
#: obvious in a property panel. The parameter name itself is unchanged --
#: this is only what the panel prints above the field.
_PARAM_LABELS: dict[tuple[str, str], str] = {
    ("columns", "n"): "number of columns",
    ("columns", "gap"): "gap between columns",
}

#: Placeholder values for required parameters, so picking a widget from
#: the palette produces something visible immediately rather than an
#: error dialog asking for arguments first. Keyed by (type, param); the
#: annotation-based fallback in ``_placeholder_for`` handles the rest.
_PLACEHOLDERS: dict[tuple[str, str], Any] = {
    ("columns", "n"): 2,
    ("listbox", "items"): ["Item 1", "Item 2", "Item 3"],
    ("json", "data"): {"key": "value"},
    ("table", "data"): [{"column": "value"}],
    ("html", "html"): "<strong>HTML</strong>",
    ("image", "source"): "",
    ("workflow_tracker", "tasks"): [
        {"id": 1, "title": "Step 1", "status": "in-progress"},
        {"id": 2, "title": "Step 2", "status": "pending"},
    ],
}


# -- layout documents ------------------------------------------------------


#: Page-level settings the editor can change, i.e. the ones that belong
#: to the page itself rather than to any widget in it. Kept deliberately
#: small: these are the KApp options that a *layout* can meaningfully
#: own. `title` is excluded -- it is the browser tab's name and usually
#: comes from the app's own code or its branding, not its layout.
PAGE_SETTINGS = ("width", "theme")


def _empty_doc() -> dict[str, Any]:
    return {"kwebui_layout": LAYOUT_VERSION, "page": {}, "widgets": []}


def page_schema(app: "KApp") -> list[dict[str, Any]]:
    """The property panel's fields for the page itself, shown when
    nothing is selected -- the main content column's width cap and the
    theme. Hand-written rather than reflected like widget_schema: these
    are two specific KApp options, not a plugin signature."""
    from .theme import available_themes

    return [
        {
            "name": "width",
            "label": "page width (px)",
            "kind": "int",
            "required": False,
            "default": None,
            "help": "Caps the main content column. Empty means the default 720px.",
        },
        {
            "name": "theme",
            "label": "theme",
            "kind": "enum",
            "required": False,
            "default": app.theme,
            "choices": sorted(set(available_themes()) | set(app._custom_themes)),
        },
    ]


def apply_page_settings(app: "KApp", page: dict[str, Any]) -> None:
    """Push a layout's page settings onto the app.

    ``width`` is read by the template at render time (see router.py), so
    setting it here works for a normal run precisely because
    ``load_layout()`` is called from ``build()``, which runs before the
    server ever renders a page. ``theme`` goes through ``set_theme`` so
    it also broadcasts to anything already connected, which is what makes
    it change live in the editor.
    """
    if "width" in page:
        app.width = page["width"]
    theme = page.get("theme")
    if theme:
        try:
            app.set_theme(theme)
        except ValueError:
            # A layout naming a theme this app doesn't have must not stop
            # the page loading -- it just keeps the current one.
            pass


def read_layout(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Read a layout file, or return an empty document if it doesn't exist
    yet -- the editor opens a not-yet-created path as a blank canvas
    rather than refusing to start."""
    file_path = Path(path)
    if not file_path.is_file():
        return _empty_doc()
    with file_path.open(encoding="utf-8") as handle:
        doc = json.load(handle)
    if not isinstance(doc, dict) or "widgets" not in doc:
        raise ValueError(
            f"{file_path} is not a kwebui layout file "
            f"(expected a JSON object with a 'widgets' key)."
        )
    return doc


def write_layout(path: str | os.PathLike[str], doc: dict[str, Any]) -> None:
    """Write a layout file atomically.

    Via a temp file in the same directory plus ``os.replace`` rather than
    a plain open-and-write: the editor saves on *every* keystroke in the
    property panel, so a crash or a full disk mid-write would otherwise
    be able to leave a truncated, unparseable layout behind -- losing the
    user's page. ``os.replace`` is atomic on POSIX and Windows alike.
    """
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=file_path.parent, prefix=file_path.name, suffix=".tmp", delete=False
    )
    try:
        with handle:
            json.dump(doc, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(handle.name, file_path)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise


def _contains_id(node: dict[str, Any], widget_id: str) -> bool:
    """Whether `widget_id` names `node` itself or anything inside it."""
    if node.get("id") == widget_id:
        return True
    return any(_contains_id(child, widget_id) for child in node.get("children") or [])


def _walk(nodes: list[dict[str, Any]]):
    """Yield every (node, parent_list) pair depth-first."""
    for node in nodes:
        yield node, nodes
        yield from _walk(node.get("children") or [])


def find_node(doc: dict[str, Any], widget_id: str) -> dict[str, Any] | None:
    for node, _ in _walk(doc["widgets"]):
        if node.get("id") == widget_id:
            return node
    return None


def all_ids(doc: dict[str, Any]) -> list[str]:
    return [node.get("id", "") for node, _ in _walk(doc["widgets"])]


# -- loading a layout into a live page --------------------------------------


def load_layout(
    parent: "KApp | Widget",
    path: str | os.PathLike[str],
    *,
    handlers: object | None = None,
) -> dict[str, Widget]:
    """Build the widgets described by a layout file and return them keyed
    by id.

        class MyApp(KApp):
            def build(self) -> None:
                self.ui = load_layout(self, "my_app.layout.json")
                self.ui["save_button"].update(on_click=self.on_save)

            def on_save(self) -> None:
                ...

    ``parent`` is the app (widgets land on the page) or any container-like
    widget (they land inside it), so a layout can be dropped into one
    panel of an otherwise hand-written page.

    Any ``handlers`` recorded in the file are resolved as attribute names
    on ``handlers`` (defaulting to ``parent``, i.e. usually the app), so
    ``"on_click": "on_save"`` binds ``self.on_save`` with no Python needed
    at all. A name that doesn't resolve raises ``ValueError`` here, at
    load time, rather than failing silently on the first click.
    """
    app = parent if _is_app(parent) else parent._app
    if app is None:
        raise ValueError(
            "load_layout() needs a parent that is attached to an app -- "
            "call it on the app itself, or on a widget already added to a page."
        )
    doc = read_layout(path)
    target = handlers if handlers is not None else parent
    apply_page_settings(app, doc.get("page") or {})

    built: dict[str, Widget] = {}
    for node in doc["widgets"]:
        _build_node(app, parent, node, built, target)

    # Remembered so edit_mode knows which file this app is actually made
    # of, instead of guessing from the script name.
    app._layout_path = str(Path(path))  # type: ignore[attr-defined]
    return built


def _is_app(candidate: object) -> bool:
    # Duck-typed rather than isinstance(KApp) to avoid importing app.py at
    # module scope (app.py imports this module inside run(), and a
    # top-level import here would close that cycle).
    return hasattr(candidate, "page") and hasattr(candidate, "registry")


def _build_node(
    app: "KApp",
    parent: "KApp | Widget",
    node: dict[str, Any],
    built: dict[str, Widget],
    handler_target: object,
    strict: bool = True,
) -> Widget:
    """Build one node and its subtree.

    ``strict=False`` is used by the editor: while you are still designing
    a page, naming a handler the app doesn't implement yet is a perfectly
    ordinary intermediate state, and refusing to render the page over it
    would make the editor unusable. At real ``load_layout()`` time the
    same situation is a genuine bug worth failing loudly on.
    """
    widget_type = node.get("type")
    widget_id = node.get("id")
    if not widget_type or not widget_id:
        raise ValueError(f"Layout node is missing 'type' or 'id': {node!r}")
    if widget_type in _REJECTED_TYPES:
        raise ValueError(f"Cannot load widget type {widget_type!r}: {_REJECTED_TYPES[widget_type]}")
    if widget_id in built:
        raise ValueError(
            f"Duplicate widget id {widget_id!r} in the layout -- ids are the "
            f"handle your Python code uses, so they must be unique."
        )

    plugin = app.registry.get(widget_type)  # raises ValueError listing available names
    props = dict(node.get("props") or {})
    for event, handler_name in (node.get("handlers") or {}).items():
        handler = _resolve_handler(handler_target, event, handler_name, widget_id, strict)
        if handler is not None:
            props[event] = handler

    widget = plugin.create(widget_id, **props)
    if widget_type == "columns":
        return _build_columns(app, parent, node, widget, built, handler_target, strict)

    _attach(app, parent, widget)
    built[widget_id] = widget

    for child in node.get("children") or []:
        _build_node(app, widget, child, built, handler_target, strict)
    return widget


def _build_columns(
    app: "KApp",
    parent: "KApp | Widget",
    node: dict[str, Any],
    widget: Widget,
    built: dict[str, Widget],
    handler_target: object,
    strict: bool,
) -> Widget:
    """Load a ``columns`` node, whose children are its columns.

    ``columns`` is the one widget that creates its own children:
    ``create()`` returns it already holding exactly ``n`` ``ColumnWidget``s
    named ``<id>-c0``, ``<id>-c1``, ... So the layout's child nodes are not
    *built*, they are **mapped onto** those existing columns -- and their
    ids are applied to them, which is what makes a column addressable from
    Python as ``ui["left_column"]`` rather than the opaque ``w4-c0``.

    Renaming happens before ``_attach`` so nothing is ever broadcast under
    the generated id first.
    """
    doc_columns = node.get("children") or []
    if len(doc_columns) > len(widget.children):
        raise ValueError(
            f"columns {node['id']!r} has n={len(widget.children)} but the layout "
            f"describes {len(doc_columns)} columns -- raise n, or remove the extras."
        )
    for index, column_node in enumerate(doc_columns):
        if column_node.get("type") != "column":
            raise ValueError(
                f"A columns widget's children must all be 'column' nodes; "
                f"{node['id']!r} has a {column_node.get('type')!r}."
            )
        column = widget.children[index]
        column_id = column_node.get("id")
        if column_id:
            column.id = column_id
        # A column carries container-like options of its own. `weight` is
        # pointedly not among them: it is set by the parent's `n`, and
        # letting a column node also carry one would give the same number
        # two homes that could disagree.
        column_props = {k: v for k, v in (column_node.get("props") or {}).items() if k != "weight"}
        column.props.update(column_props)

    _attach(app, parent, widget)
    built[node["id"]] = widget

    for index, column_node in enumerate(doc_columns):
        column = widget.children[index]
        built[column.id] = column
        for child in column_node.get("children") or []:
            _build_node(app, column, child, built, handler_target, strict)
    return widget


def _resolve_handler(
    target: object, event: str, name: str, widget_id: str, strict: bool = True
) -> Callable[..., Any] | None:
    handler = getattr(target, name, None)
    if callable(handler):
        return handler
    if strict:
        raise ValueError(
            f"Layout widget {widget_id!r} wants {event}={name!r}, but "
            f"{type(target).__name__} has no callable attribute {name!r}."
        )
    return None


def _attach(app: "KApp", parent: "KApp | Widget", widget: Widget) -> None:
    """Parent a freshly built widget, matching what the framework's own
    factories do -- including their asymmetry.

    Top-level widgets get ``_app`` first (``KApp.__getattr__``), but every
    *nested* factory deliberately appends to the parent and broadcasts the
    parent **before** wiring ``_app``, because widgets that self-broadcast
    on ``_app`` assignment (alert/toast/popup/columns) would otherwise
    announce themselves unparented and get mounted twice as top-level
    nodes. See ``empty.py``'s factory for the full explanation.
    """
    if _is_app(parent):
        widget._app = app
        app.page.add(widget)
        app._on_widget_changed(widget)
        return

    from .widgets.empty import EmptyWidget

    if isinstance(parent, EmptyWidget):
        parent.set(widget)
    else:
        parent.children.append(widget)
        if parent._app is not None:
            parent._app._on_widget_changed(parent)
    widget._app = app


# -- property schema (derived, not hand-maintained) -------------------------


def _resolved_hints(plugin: object) -> dict[str, Any]:
    """Resolve ``create()``'s annotations to real types.

    Every widget module uses ``from __future__ import annotations``, so
    ``inspect.signature`` hands back *strings* (``'str | None'``). Real
    objects are needed to decide which editor control a parameter gets.
    """
    try:
        return typing.get_type_hints(type(plugin).create)
    except Exception:
        return {}


def _unwrap_optional(annotation: Any) -> tuple[Any, bool]:
    """``str | None`` -> ``(str, True)``; anything else -> ``(it, False)``.

    Both spellings have to be handled: ``typing.Optional[str]`` reports
    ``typing.Union`` as its origin, while the PEP 604 ``str | None`` used
    throughout this codebase reports ``types.UnionType`` -- a different
    object, so one check cannot cover both.
    """
    import types

    origin = typing.get_origin(annotation)
    if origin is typing.Union or origin is types.UnionType:
        args = [arg for arg in typing.get_args(annotation) if arg is not type(None)]
        if len(args) == 1:
            return args[0], True
        return (args[0] if args else Any), True
    return annotation, False


def _kind_for(widget_type: str, name: str, annotation: Any) -> str:
    """Which editor control a parameter gets.

    ``handler`` is the interesting one: a ``Callable`` parameter can't be
    given a value in JSON at all, so the panel offers a *method name* for
    ``load_layout()`` to resolve later, not a value.
    """
    import collections.abc

    if (widget_type, name) in _ENUM_CHOICES:
        return "enum"
    base, _ = _unwrap_optional(annotation)
    if base is bool:
        return "bool"
    if base is int:
        return "int"
    if base is float:
        return "float"
    if base is str:
        return "str"
    if base is Callable or typing.get_origin(base) is collections.abc.Callable:
        return "handler"
    # Sequence[str], list[Any], dict[str, str], Any, ... -- nothing a
    # single-line control can express, so it's edited as raw JSON.
    return "json"


def _placeholder_for(widget_type: str, name: str, annotation: Any) -> Any:
    if (widget_type, name) in _PLACEHOLDERS:
        return _PLACEHOLDERS[(widget_type, name)]
    base, _ = _unwrap_optional(annotation)
    if base is bool:
        return False
    if base in (int, float):
        return 0
    if base is str:
        return widget_type.replace("_", " ").title()
    return None


def widget_schema(registry: "WidgetRegistry") -> dict[str, Any]:
    """Describe every palette-able widget: its editable parameters, their
    kinds, defaults and (where known) allowed values.

    Derived by reflecting over each plugin's ``create()`` signature rather
    than hand-maintained, so a newly added widget appears in the editor
    with a working property panel and no edit here at all -- the same
    "drop a file in and it works" promise the rest of the plugin system
    makes.
    """
    schema: dict[str, Any] = {}
    for name in sorted(set(registry.names())):
        plugin = registry.get(name)
        signature = inspect.signature(plugin.create)
        hints = _resolved_hints(plugin)

        params: list[dict[str, Any]] = []
        for param_name, param in signature.parameters.items():
            if param_name == "widget_id" or param.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue
            annotation = hints.get(param_name, Any)
            kind = _kind_for(name, param_name, annotation)
            required = param.default is inspect.Parameter.empty
            entry: dict[str, Any] = {
                "name": param_name,
                "label": _PARAM_LABELS.get((name, param_name), param_name),
                "kind": kind,
                "required": required,
                "default": None if required else param.default,
            }
            if kind == "enum":
                entry["choices"] = _ENUM_CHOICES[(name, param_name)]
            params.append(entry)

        schema[name] = {
            "type": name,
            "params": params,
            # Whether right-clicking it offers "insert inside".
            "container": name in _CONTAINER_TYPES,
            # Whether the palette offers it. Every type is described --
            # a column still needs a property panel even though you never
            # insert one yourself -- so this is a flag rather than an
            # omission from the schema.
            "palette": name not in _PALETTE_EXCLUDED and name not in _REJECTED_TYPES,
            "doc": (inspect.getdoc(type(plugin)) or "").strip().splitlines()[:1],
        }
    return schema


def default_props_for(registry: "WidgetRegistry", widget_type: str) -> dict[str, Any]:
    """Constructor kwargs that make a newly inserted widget render as
    something visible, filling in every required parameter."""
    plugin = registry.get(widget_type)
    signature = inspect.signature(plugin.create)
    hints = _resolved_hints(plugin)
    props: dict[str, Any] = {}
    for param_name, param in signature.parameters.items():
        if param_name == "widget_id" or param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        if param.default is inspect.Parameter.empty:
            props[param_name] = _placeholder_for(widget_type, param_name, hints.get(param_name, Any))
    return props


# -- the live editing session ----------------------------------------------


class EditSession:
    """Owns the layout document while ``edit_mode=True`` is running.

    The document is the source of truth; the live kwebui page is a
    *preview* rebuilt from it. That direction matters: trying to edit the
    live widget tree and serialize it back out would run straight into the
    lossy-wire-format problem this module's docstring describes, and would
    also make ids un-renameable (a widget's id is baked into every browser
    that already rendered it).

    Structural edits therefore mutate the document, rebuild the widgets it
    owns, and re-broadcast the whole tree as a fresh ``init`` message.
    That op already exists and already means "replace everything you have"
    on the client (see ``websocket.js``), and since ``run_id`` is unchanged
    the browser treats it as a resync rather than a reload -- so no new
    client-side protocol was needed for any of this.
    """

    def __init__(self, app: "KApp", path: str | os.PathLike[str]) -> None:
        self.app = app
        self.path = Path(path)
        self.doc = read_layout(self.path)
        self.doc.setdefault("page", {})
        self.widgets: dict[str, Widget] = {}
        # Whatever a load_layout() call in build() already put on the page
        # carries exactly these ids, so the first remount clears them
        # instead of leaving a duplicate set behind.
        self._mounted_ids: list[str] = [node.get("id", "") for node in self.doc["widgets"]]
        self.errors: list[str] = []

    # -- mounting ----------------------------------------------------------

    def remount(self) -> None:
        apply_page_settings(self.app, self.doc.get("page") or {})
        for widget_id in self._mounted_ids:
            self.app.page.remove(widget_id)
        self._mounted_ids = []
        self.widgets = {}
        self.errors = []
        for node in self.doc["widgets"]:
            try:
                widget = _build_node(self.app, self.app, node, self.widgets, self.app, strict=False)
            except Exception as exc:
                # A layout hand-edited into an invalid state must not take
                # the editor down with it -- surface it in the UI instead,
                # which is the only place the user can fix it.
                self.errors.append(str(exc))
                continue
            self._mounted_ids.append(widget.id)
        self.broadcast_tree()

    def broadcast_tree(self) -> None:
        self.app._broadcast(
            {
                "op": "init",
                "theme": self.app.theme,
                "run_id": self.app.run_id,
                "widgets": serialize_page(self.app.page, self.app.registry),
            }
        )

    def save(self) -> None:
        write_layout(self.path, self.doc)

    def set_page_setting(self, name: str, value: Any) -> None:
        if name not in PAGE_SETTINGS:
            raise ValueError(
                f"Unknown page setting {name!r}. Available: {', '.join(PAGE_SETTINGS)}."
            )
        self.doc.setdefault("page", {})[name] = value
        apply_page_settings(self.app, {name: value})
        # No remount: neither width nor theme is part of the widget tree,
        # so rebuilding it would be pure churn. Saving is still required.
        self.save()

    # -- editing operations -------------------------------------------------

    def unique_id(self, widget_type: str, reserved: set[str] | None = None) -> str:
        """A free ``<type>_<n>`` id.

        ``reserved`` covers ids allocated for a node that is still being
        assembled and so isn't in the document yet -- without it, creating
        several children at once (a columns and its columns) hands out the
        same id to all of them, which then fails to load.
        """
        taken = set(all_ids(self.doc)) | {w.id for w in _iter_page(self.app)} | (reserved or set())
        index = 1
        while f"{widget_type}_{index}" in taken:
            index += 1
        return f"{widget_type}_{index}"

    def insert(self, parent_id: str | None, widget_type: str) -> str:
        if widget_type in _REJECTED_TYPES:
            raise ValueError(_REJECTED_TYPES[widget_type])
        self.app.registry.get(widget_type)  # validates, raises with the available list
        node = {
            "type": widget_type,
            "id": self.unique_id(widget_type),
            "props": default_props_for(self.app.registry, widget_type),
            "handlers": {},
            "children": [],
        }
        if widget_type == "columns":
            # A columns with no column nodes would render as n empty
            # columns you cannot right-click into, because the document
            # has nowhere to put what you insert. Create them up front so
            # it is usable the moment it appears.
            self._sync_columns(node)
        siblings = self._children_list(parent_id)
        siblings.append(node)
        self._commit()
        return node["id"]

    def _sync_columns(self, node: dict[str, Any]) -> None:
        """Make a ``columns`` node hold exactly as many column children as
        its ``n`` says -- adding empties, or dropping the trailing ones
        (and whatever was in them) when ``n`` shrinks."""
        n = node.get("props", {}).get("n", 2)
        wanted = len(n) if isinstance(n, (list, tuple)) else int(n or 0)
        children = node.setdefault("children", [])
        while len(children) > wanted:
            children.pop()
        while len(children) < wanted:
            children.append(
                {
                    "type": "column",
                    "id": self.unique_id("column", {child["id"] for child in children}),
                    "props": {},
                    "handlers": {},
                    "children": [],
                }
            )

    def delete(self, widget_id: str) -> None:
        for node, siblings in _walk(self.doc["widgets"]):
            if node.get("id") == widget_id:
                siblings.remove(node)
                self._commit()
                return
        raise ValueError(f"No widget {widget_id!r} in this layout.")

    def rename(self, widget_id: str, new_id: str) -> None:
        new_id = (new_id or "").strip()
        if not new_id:
            raise ValueError("A widget id cannot be empty.")
        if new_id == widget_id:
            return
        if new_id in set(all_ids(self.doc)):
            raise ValueError(f"Another widget already uses the id {new_id!r}.")
        node = find_node(self.doc, widget_id)
        if node is None:
            raise ValueError(f"No widget {widget_id!r} in this layout.")
        node["id"] = new_id
        self._commit()

    def set_prop(self, widget_id: str, name: str, value: Any) -> None:
        node = find_node(self.doc, widget_id)
        if node is None:
            raise ValueError(f"No widget {widget_id!r} in this layout.")
        node.setdefault("props", {})[name] = value
        # Changing how many columns there are has to change the document's
        # column nodes too, or the next load would raise on a mismatch
        # between n and the children describing it.
        if node.get("type") == "columns" and name == "n":
            self._sync_columns(node)
        self._commit()

    def set_handler(self, widget_id: str, event: str, handler_name: str) -> None:
        node = find_node(self.doc, widget_id)
        if node is None:
            raise ValueError(f"No widget {widget_id!r} in this layout.")
        handlers = node.setdefault("handlers", {})
        if handler_name.strip():
            handlers[event] = handler_name.strip()
        else:
            handlers.pop(event, None)
        self._commit()

    def move_to(self, widget_id: str, parent_id: str | None, index: int) -> None:
        """Reparent a widget -- what a drag-and-drop lands on.

        Moving *within* the same parent is a reorder and falls out of the
        same code: the node is detached first, so the insertion index is
        always an index into the list as it will actually be.
        """
        located = self._locate(widget_id)
        if located is None:
            raise ValueError(f"No widget {widget_id!r} in this layout.")
        node, siblings = located

        if parent_id is not None:
            if parent_id == widget_id:
                raise ValueError("A widget cannot be dropped into itself.")
            if _contains_id(node, parent_id):
                # Without this the moved subtree would be spliced into
                # its own descendant and vanish from the document -- the
                # classic way a tree editor eats someone's work.
                raise ValueError(
                    f"Cannot move {widget_id!r} into {parent_id!r}: that would put it inside itself."
                )
            parent_node = find_node(self.doc, parent_id)
            if parent_node is not None and parent_node.get("type") == "columns":
                raise ValueError(
                    "A columns holds only its own columns -- drop into one of its columns instead."
                )

        target = self._children_list(parent_id)
        siblings.remove(node)
        target.insert(max(0, min(len(target), index)), node)
        self._commit()

    def _locate(self, widget_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
        for node, siblings in _walk(self.doc["widgets"]):
            if node.get("id") == widget_id:
                return node, siblings
        return None

    def move(self, widget_id: str, delta: int) -> None:
        for node, siblings in _walk(self.doc["widgets"]):
            if node.get("id") == widget_id:
                index = siblings.index(node)
                target = max(0, min(len(siblings) - 1, index + delta))
                if target != index:
                    siblings.insert(target, siblings.pop(index))
                    self._commit()
                return
        raise ValueError(f"No widget {widget_id!r} in this layout.")

    # -- internals ---------------------------------------------------------

    def _children_list(self, parent_id: str | None) -> list[dict[str, Any]]:
        if parent_id is None:
            return self.doc["widgets"]
        node = find_node(self.doc, parent_id)
        if node is None:
            # Right-clicked a widget that belongs to the app's Python code
            # rather than the layout -- there is nowhere in the document to
            # put a child, so it goes to the top level instead of failing.
            return self.doc["widgets"]
        return node.setdefault("children", [])

    def _commit(self) -> None:
        """Every mutation goes through here: save first, then rebuild.

        Saving first is deliberate -- if rebuilding throws (a bad prop
        value, say), the user's edit is still on disk and recoverable
        rather than lost along with the exception.
        """
        self.save()
        self.remount()


def _iter_page(app: "KApp"):
    def walk(widgets):
        for widget in widgets:
            yield widget
            yield from walk(widget.children)

    return walk(app.page.children)


# -- wiring it into a running app ------------------------------------------


def default_layout_path(app: "KApp", explicit: str | None = None) -> Path:
    """Which file this editing session reads and writes.

    An explicit path wins; then whatever ``load_layout()`` already read
    during ``build()`` -- so an app that loads a layout is edited in
    place, with nothing to configure; then a file named after the script,
    for an app that has no layout yet and is being designed from blank.
    """
    if explicit:
        return Path(explicit)
    recorded = getattr(app, "_layout_path", None)
    if recorded:
        return Path(recorded)
    import sys

    script = Path(sys.argv[0]) if sys.argv and sys.argv[0] else Path("app.py")
    return script.with_name(script.stem + ".layout.json")


def install_editor(fastapi_app: "FastAPI", app: "KApp", layout_path: str | os.PathLike[str]) -> EditSession:
    """Mount the layout and add the ``/_edit/*`` API the overlay talks to.

    Routes rather than new WebSocket ops: an editor message is a
    request/response with an error path (a duplicate id, an unknown
    widget), and the existing socket protocol is deliberately one-way
    fire-and-forget with no way to answer "no, that failed, because...".
    """
    from fastapi import Body, HTTPException

    session = EditSession(app, layout_path)
    session.remount()

    def _state(extra: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {
            "ok": True,
            "doc": session.doc,
            "errors": session.errors,
            # Live values, which may differ from the document when the
            # app set them in its own code rather than the layout.
            "page_values": {"width": app.width, "theme": app.theme},
        }
        payload.update(extra or {})
        return payload

    def _guard(operation) -> dict[str, Any]:
        try:
            return _state(operation())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @fastapi_app.get("/_edit/state")
    async def edit_state() -> dict[str, Any]:
        return _state(
            {
                "schema": widget_schema(app.registry),
                "page_schema": page_schema(app),
                "path": str(session.path),
                # Ids the layout owns; everything else on the page came
                # from the app's Python and is shown but not editable.
                "owned": all_ids(session.doc),
            }
        )

    @fastapi_app.post("/_edit/insert")
    async def edit_insert(payload: dict = Body(...)) -> dict[str, Any]:
        return _guard(lambda: {"id": session.insert(payload.get("parent_id"), payload["type"])})

    @fastapi_app.post("/_edit/delete")
    async def edit_delete(payload: dict = Body(...)) -> dict[str, Any]:
        return _guard(lambda: session.delete(payload["id"]) or {})

    @fastapi_app.post("/_edit/rename")
    async def edit_rename(payload: dict = Body(...)) -> dict[str, Any]:
        return _guard(lambda: session.rename(payload["id"], payload["new_id"]) or {"id": payload["new_id"]})

    @fastapi_app.post("/_edit/prop")
    async def edit_prop(payload: dict = Body(...)) -> dict[str, Any]:
        return _guard(lambda: session.set_prop(payload["id"], payload["name"], payload["value"]) or {})

    @fastapi_app.post("/_edit/handler")
    async def edit_handler(payload: dict = Body(...)) -> dict[str, Any]:
        return _guard(lambda: session.set_handler(payload["id"], payload["event"], payload["name"]) or {})

    @fastapi_app.post("/_edit/page")
    async def edit_page(payload: dict = Body(...)) -> dict[str, Any]:
        return _guard(lambda: session.set_page_setting(payload["name"], payload["value"]) or {})

    @fastapi_app.post("/_edit/move")
    async def edit_move(payload: dict = Body(...)) -> dict[str, Any]:
        return _guard(lambda: session.move(payload["id"], int(payload["delta"])) or {})

    @fastapi_app.post("/_edit/move_to")
    async def edit_move_to(payload: dict = Body(...)) -> dict[str, Any]:
        return _guard(
            lambda: session.move_to(payload["id"], payload.get("parent_id"), int(payload["index"])) or {}
        )

    print(f"kwebui edit mode -- layout file: {session.path}", flush=True)
    return session
