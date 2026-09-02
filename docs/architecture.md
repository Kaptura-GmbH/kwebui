# Architecture

kwebui has six kinds of moving parts. Everything else is a widget
plugin built on top of them.

```
Browser  <──WebSocket (JSON)──>  websocket.py  <──>  KApp (page + registry)
   │                                                        │
   └── GET / , /static/*, /themes/*.css, /media/*, /stream/* │
                              router.py  <───────────────────┘
```

## 1. Widgets are data, not HTML

A `Widget` (`widget.py`) is a plain object: `id`, `widget_type`, a `props`
dict, and a `children` list. The core never generates HTML. The browser
renders everything from the JSON produced by `renderer.py`. This is why
"rendering" in a plugin means *building/updating Python state*, not
producing markup -- see `plugin.py`'s `create()`/`serialize()`.

## 2. The plugin system

`registry.py` walks every module in `kwebui/widgets/`, finds classes
that subclass `WidgetPlugin` (`plugin.py`) and are defined in that module,
and instantiates one of each. `KApp` never imports a widget module by
name. Concretely: delete `kwebui/widgets/button.py` and `app.button`
stops existing, with zero changes anywhere else.

A plugin implements:

| Hook | Purpose |
|---|---|
| `create(widget_id, ...)` | Build a `Widget` from the arguments passed to `app.<name>(...)` |
| `serialize(widget)` | Widget → JSON dict sent to the browser (callables and `_private` props are stripped automatically) |
| `handle_event(widget, event)` | React to a browser event (click, change, ...) |
| `default_style()` | Inline CSS defaults applied before the widget's own JS mounts it |
| `register_routes(fastapi_app, app)` | Optional: mount extra HTTP routes (used by `image` for `/media/{id}` and `imagestream` for `/stream/{id}`) |

`KApp.__getattr__` is what makes `app.text(...)` / `app.button(...)` work
without the core knowing those names exist: it looks the name up in the
registry and, if found, returns a factory that calls `create()`, wires
the new widget to the app, and appends it to the page.

## 3. Rendering pipeline

1. `KApp.__init__` calls the subclass's `build()` once, which builds the
   tree via `self.<widget>(...)` calls (`page.py` holds it).
2. `app.run()` starts FastAPI/uvicorn (`router.py`).
3. Each browser that connects to `/ws` gets the current tree serialized in
   one `{"op": "init", "widgets": [...]}` message (`renderer.py` walks the
   tree, asking the registry for each widget's plugin).
4. From then on, whenever a widget's Python state changes (a callback
   calls `widget.update(...)` or a typed setter like `text.set_text(...)`),
   exactly one `{"op": "update", "widget": {...}}` patch goes out for that
   widget's subtree. **The rest of the page is never touched.**

The frontend mirrors this in `frontend/static/js/`: it's Vue 3, loaded as
a single vendored `vue.global.js` file rather than Single File
Components -- this keeps `pip install -e .` free of any Node.js/npm
step. `core.js` holds one
`Vue.reactive({ widgets: [] })` tree plus `registerWidget(type,
componentDefinition)`, which widget JS files call into to register
themselves as Vue components; `renderer.js` defines a single recursive
`widget-node` component that resolves each widget's `type` to its
component and passes recursively-rendered children through as its
default slot; `websocket.js` owns the connection and mutates the
reactive tree on "init"/"update" (Vue's own diffing does the rest --
there is no manual DOM patching anywhere). Each file under `js/widgets/`
is the frontend half of one plugin. `index.html` includes every file in
`js/widgets/` automatically (`router.py` lists the directory) -- a new
widget's JS file needs no template change either.

## 4. Events

Browser → `{"widget_id", "type", "payload"}` over the WebSocket →
`KApp._dispatch_event` looks the widget up in the page tree, asks the
registry for its plugin, and calls `plugin.handle_event(widget, event)`.
The plugin decides what "click" or "change" means for that widget type;
the core only routes.

## 5. Sessions

Every WebSocket connection gets a `Session` (`session.py`): an id, the
raw connection, and a free-form `state` scratchpad (`state.py`) for
advanced use. **The widget tree itself is shared across all sessions** --
kwebui broadcasts updates to every connected browser, it does not
clone the tree per connection the way Streamlit reruns the script per
session. This is a deliberate simplification: true per-session isolation
would mean cloning the tree per connection and re-binding every callback
closure to the clone -- a lot of machinery for a library meant to be
readable in an afternoon, and it wouldn't match the plain
`on_click=lambda: ...` style the examples use throughout. `Session`
stays a distinct class specifically so per-session isolation could be
added later without an API break. See the README for what this means in
practice (single-operator tools and dashboards, not isolated
multi-tenant apps).

`app.session` (a `contextvars.ContextVar`, the one intentional global in
this codebase) is only set while an event is being dispatched, so a
callback can read `app.session.state` but code outside a callback sees
`None`.

## 6. Themes

Themes are just CSS files in `kwebui/themes/*.css`, each defining the
same set of `--sg-*` custom properties (`theme.py` lists what's available
by scanning that directory). `kwebui/frontend/static/css/base.css` is
all structural CSS and only ever *references* those variables, never
hardcodes a color -- that's what makes `app.set_theme("dark")` a matter
of swapping one `<link>` tag's `href`, no widget changes required.

## Adding a new widget

1. Create `kwebui/widgets/<name>.py` with a `Widget` subclass (only if
   you need typed convenience methods) and a `WidgetPlugin` subclass.
2. Create `kwebui/frontend/static/js/widgets/<name>.js` calling
   `registerWidget("<name>", { props: ["data"], template: \`...\`, ... })`
   -- a plain Vue component definition.
3. That's it -- no other file changes. `tests/test_registry.py` will pick
   it up automatically if you add it to the expected-names list.
