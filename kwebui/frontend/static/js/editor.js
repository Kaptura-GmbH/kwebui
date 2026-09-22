// Visual edit mode overlay -- only loaded for KApp(edit_mode=True) (see
// index.html and editor.py). Deliberately NOT a widget: it is a layer
// *over* the page, so it registers nothing with registerWidget, adds
// nothing to the widget tree, and a normal app never loads this file at
// all.
//
// It talks to the server over plain HTTP (`/_edit/*`) rather than the
// WebSocket, because an edit is a request that can *fail* -- a duplicate
// id, an unparseable value -- and the socket protocol is one-way
// fire-and-forget with no way to answer "no, and here's why". The server
// answers each call with the new document and then re-broadcasts the
// whole tree as an `init`, which the existing client already treats as
// "replace everything" -- so the live page updates through machinery that
// was already there, with no new socket ops.
"use strict";

const kweState = {
  schema: {},          // widget type -> {params, container, ...}
  doc: { widgets: [] },
  owned: new Set(),    // ids the layout file owns, i.e. the editable ones
  selectedId: null,
  path: "",
  containerTypes: new Set(),
  pageSchema: [],
  pageValues: {},
};

// --- server API -------------------------------------------------------------

async function kweGet(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(await kweErrorText(response));
  return response.json();
}

async function kwePost(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(await kweErrorText(response));
  return response.json();
}

async function kweErrorText(response) {
  try {
    const body = await response.json();
    return body.detail || `Request failed (${response.status})`;
  } catch (err) {
    return `Request failed (${response.status})`;
  }
}

/** Fold a mutation response back into local state. The server has already
 *  re-broadcast the tree by the time this resolves, so all that is left is
 *  to re-derive what the overlay itself tracks. */
function kweAbsorb(result) {
  kweState.doc = result.doc;
  kweState.owned = new Set(kweCollectIds(result.doc.widgets));
  if (result.page_values) kweState.pageValues = result.page_values;
  kweRenderPanel();
  kweDecorate();
  kweLayoutResizers();
}

function kweCollectIds(nodes, out = []) {
  for (const node of nodes || []) {
    out.push(node.id);
    kweCollectIds(node.children, out);
  }
  return out;
}

function kweFindNode(nodes, id) {
  for (const node of nodes || []) {
    if (node.id === id) return node;
    const hit = kweFindNode(node.children, id);
    if (hit) return hit;
  }
  return null;
}

/** The chain of nodes from the top level down to `id`, inclusive.
 *
 *  This is what makes every widget reachable regardless of whether it has
 *  any clickable area of its own. A `columns` in particular is covered
 *  edge to edge by its own columns, so clicking "it" always lands on a
 *  column instead -- without a breadcrumb there would be no way back up to
 *  it to change how many columns it has. */
function kweAncestry(nodes, id, trail = []) {
  for (const node of nodes || []) {
    const here = [...trail, node];
    if (node.id === id) return here;
    const hit = kweAncestry(node.children, id, here);
    if (hit) return hit;
  }
  return null;
}

function kweSelect(id) {
  kweState.selectedId = id;
  kweRenderPanel();
  kweDecorate();
  const element = id && kweWidgetElement(id);
  if (element) element.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

// --- DOM <-> widget mapping -------------------------------------------------

function kweWidgetElement(id) {
  return document.querySelector(`[data-widget-id="${CSS.escape(id)}"]`);
}

/** The nearest *editable container* at or above an element -- where a
 *  right-clicked insert should go. Returns null for "the page itself",
 *  which is a legitimate target (top level of the layout). */
function kweContainerAt(element) {
  let node = element && element.closest ? element.closest("[data-widget-id]") : null;
  while (node) {
    const id = node.getAttribute("data-widget-id");
    const type = node.getAttribute("data-widget-type");
    if (kweState.containerTypes.has(type) && kweState.owned.has(id)) return id;
    const parent = node.parentElement;
    node = parent ? parent.closest("[data-widget-id]") : null;
  }
  return null;
}

/** The nearest *selectable* widget -- one the layout owns. Widgets built
 *  by the app's Python are visible but cannot be edited, since there is
 *  nowhere in the JSON to write them back to. */
function kweSelectableAt(element) {
  let node = element && element.closest ? element.closest("[data-widget-id]") : null;
  while (node) {
    const id = node.getAttribute("data-widget-id");
    if (kweState.owned.has(id)) return id;
    const parent = node.parentElement;
    node = parent ? parent.closest("[data-widget-id]") : null;
  }
  return null;
}

/** Re-apply the overlay's own DOM marks. Vue rebuilds the tree from
 *  scratch on every `init`, wiping these, so this runs again after each
 *  mutation and from a MutationObserver. */
function kweDecorate() {
  document.querySelectorAll("[data-widget-id]").forEach((element) => {
    const id = element.getAttribute("data-widget-id");
    const owned = kweState.owned.has(id);
    element.setAttribute("data-kwe-owner", owned ? "layout" : "code");
    if (id === kweState.selectedId) element.setAttribute("data-kwe-selected", "true");
    else element.removeAttribute("data-kwe-selected");
  });
}

// --- palette (the right-click menu) -----------------------------------------

let kwePaletteTargetId = null;

function kwePaletteElement() {
  return document.getElementById("kwe-palette");
}

function kweOpenPalette(x, y, containerId) {
  kwePaletteTargetId = containerId;
  const palette = kwePaletteElement();
  const target = document.getElementById("kwe-palette-target");
  target.textContent = containerId ? `Insert into ${containerId}` : "Insert at page level";

  palette.hidden = false;
  // Positioned after unhiding so the measured size is real, then clamped
  // so a right-click near the viewport edge doesn't open a menu that is
  // half off-screen and unreachable.
  const rect = palette.getBoundingClientRect();
  palette.style.left = `${Math.min(x, window.innerWidth - rect.width - 8)}px`;
  palette.style.top = `${Math.min(y, window.innerHeight - rect.height - 8)}px`;

  const search = document.getElementById("kwe-palette-search");
  search.value = "";
  kweRenderPaletteList("");
  search.focus();
}

function kweClosePalette() {
  kwePaletteElement().hidden = true;
  kwePaletteTargetId = null;
}

function kweRenderPaletteList(query) {
  const list = document.getElementById("kwe-palette-list");
  const needle = query.trim().toLowerCase();
  // Every widget type is in the schema (a column needs a property panel
  // even though you never insert one yourself), so the palette filters on
  // the server's `palette` flag rather than on schema membership.
  const matches = Object.keys(kweState.schema)
    .filter((type) => kweState.schema[type].palette && type.includes(needle))
    .sort();

  list.innerHTML = "";
  if (matches.length === 0) {
    const empty = document.createElement("div");
    empty.className = "kwe-palette-empty";
    empty.textContent = `No widget matches "${query}"`;
    list.appendChild(empty);
    return;
  }
  matches.forEach((type, index) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "kwe-palette-item" + (index === 0 ? " kwe-active" : "");
    item.textContent = type;
    item.dataset.type = type;
    item.addEventListener("click", () => kweInsert(type));
    list.appendChild(item);
  });
}

function kweMovePaletteActive(delta) {
  const items = [...document.querySelectorAll(".kwe-palette-item")];
  if (items.length === 0) return;
  const current = items.findIndex((item) => item.classList.contains("kwe-active"));
  const next = Math.max(0, Math.min(items.length - 1, (current < 0 ? 0 : current) + delta));
  items.forEach((item) => item.classList.remove("kwe-active"));
  items[next].classList.add("kwe-active");
  items[next].scrollIntoView({ block: "nearest" });
}

async function kweInsert(type) {
  const parentId = kwePaletteTargetId;
  kweClosePalette();
  try {
    const result = await kwePost("/_edit/insert", { parent_id: parentId, type });
    kweState.selectedId = result.id;
    kweAbsorb(result);
  } catch (err) {
    kweShowError(err.message);
  }
}

// --- property panel ---------------------------------------------------------

function kweShowError(message) {
  const body = document.getElementById("kwe-panel-body");
  const box = document.createElement("div");
  box.className = "kwe-error";
  box.textContent = message;
  body.prepend(box);
  setTimeout(() => box.remove(), 6000);
}

function kweRenderPanel() {
  const title = document.getElementById("kwe-panel-title");
  const body = document.getElementById("kwe-panel-body");
  body.innerHTML = "";

  const id = kweState.selectedId;
  const node = id ? kweFindNode(kweState.doc.widgets, id) : null;
  if (!node) {
    // Nothing selected is not a dead end: it is how you get at the page
    // itself, which owns settings no widget does (its width cap, the
    // theme). Same panel, one level up.
    title.textContent = "Page";

    const heading = document.createElement("div");
    heading.className = "kwe-section";
    heading.textContent = "Main panel";
    body.appendChild(heading);
    for (const param of kweState.pageSchema) body.appendChild(kwePageField(param));

    const hint = document.createElement("div");
    hint.className = "kwe-hint";
    hint.innerHTML =
      "<p>Right-click a container to add a widget.</p>" +
      "<p>Click a widget to edit it here.</p>" +
      "<p>Dimmed widgets come from your Python code, so they can't be edited " +
      "here -- only widgets in the layout file can.</p>";
    body.appendChild(hint);
    return;
  }

  title.textContent = node.type;
  const schema = kweState.schema[node.type] || { params: [] };

  body.appendChild(kweBreadcrumb(node));

  // The id first, and on its own: it is the handle the user's Python code
  // uses (ui["save_button"]), not just another property.
  body.appendChild(kweIdField(node));

  const propsHeading = document.createElement("div");
  propsHeading.className = "kwe-section";
  propsHeading.textContent = "Properties";
  body.appendChild(propsHeading);

  for (const param of schema.params) {
    if (param.kind === "handler") continue;
    body.appendChild(kwePropField(node, param));
  }

  const handlerParams = schema.params.filter((param) => param.kind === "handler");
  if (handlerParams.length > 0) {
    const heading = document.createElement("div");
    heading.className = "kwe-section";
    heading.textContent = "Handlers (method name on your app)";
    body.appendChild(heading);
    for (const param of handlerParams) body.appendChild(kweHandlerField(node, param));
  }

  body.appendChild(kweActions(node));
}

/** Clickable ancestor trail: page › columns_1 › column_2 › badge_1.
 *  The only way to select a widget whose own area is fully covered by its
 *  children -- see kweAncestry. */
function kweBreadcrumb(node) {
  const wrapper = document.createElement("div");
  wrapper.className = "kwe-breadcrumb";

  const root = document.createElement("button");
  root.type = "button";
  root.className = "kwe-crumb";
  root.textContent = "page";
  root.title = "Deselect";
  root.addEventListener("click", () => kweSelect(null));
  wrapper.appendChild(root);

  const trail = kweAncestry(kweState.doc.widgets, node.id) || [];
  for (const step of trail) {
    const sep = document.createElement("span");
    sep.className = "kwe-crumb-sep";
    sep.textContent = "›";
    wrapper.appendChild(sep);

    const crumb = document.createElement("button");
    crumb.type = "button";
    crumb.className = "kwe-crumb" + (step.id === node.id ? " kwe-crumb-current" : "");
    crumb.textContent = step.id;
    crumb.title = `${step.type} -- click to select`;
    crumb.addEventListener("click", () => kweSelect(step.id));
    wrapper.appendChild(crumb);
  }
  return wrapper;
}

function kweField(labelText) {
  const wrapper = document.createElement("div");
  wrapper.className = "kwe-field";
  const label = document.createElement("label");
  label.textContent = labelText;
  wrapper.appendChild(label);
  return wrapper;
}

function kweIdField(node) {
  const wrapper = kweField("id -- use this from Python");
  wrapper.id = "kwe-field-id";
  const input = document.createElement("input");
  input.type = "text";
  input.value = node.id;
  // Committed on blur/Enter rather than on every keystroke: a rename
  // rebuilds the whole tree, and doing that per character would fight the
  // user for the caret and litter the layout with half-typed ids.
  const commit = async () => {
    const newId = input.value.trim();
    if (!newId || newId === node.id) return;
    try {
      const result = await kwePost("/_edit/rename", { id: node.id, new_id: newId });
      kweState.selectedId = newId;
      kweAbsorb(result);
    } catch (err) {
      input.value = node.id;
      kweShowError(err.message);
    }
  };
  input.addEventListener("blur", commit);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") input.blur();
  });
  wrapper.appendChild(input);
  return wrapper;
}

function kweCurrentValue(node, param) {
  const props = node.props || {};
  return Object.prototype.hasOwnProperty.call(props, param.name) ? props[param.name] : param.default;
}

function kwePropField(node, param) {
  const value = kweCurrentValue(node, param);
  const wrapper = kweField((param.label || param.name) + (param.required ? " *" : ""));

  let input;
  if (param.kind === "bool") {
    wrapper.classList.add("kwe-field-row");
    input = document.createElement("input");
    input.type = "checkbox";
    input.checked = Boolean(value);
    input.addEventListener("change", () => kweSetProp(node, param, input.checked));
    wrapper.prepend(input);
    return wrapper;
  }

  if (param.kind === "enum") {
    input = document.createElement("select");
    // A nullable enum keeps an explicit empty choice, so "no alignment"
    // stays reachable once something has been picked.
    if (!param.required) input.appendChild(new Option("(default)", ""));
    for (const choice of param.choices) input.appendChild(new Option(choice, choice));
    input.value = value === null || value === undefined ? "" : String(value);
    input.addEventListener("change", () =>
      kweSetProp(node, param, input.value === "" ? null : input.value)
    );
    wrapper.appendChild(input);
    return wrapper;
  }

  if (param.kind === "int" || param.kind === "float") {
    input = document.createElement("input");
    input.type = "number";
    if (param.kind === "float") input.step = "any";
    input.value = value === null || value === undefined ? "" : String(value);
    input.addEventListener("change", () => {
      if (input.value === "") return kweSetProp(node, param, null);
      const parsed = param.kind === "int" ? parseInt(input.value, 10) : parseFloat(input.value);
      if (Number.isNaN(parsed)) return kweShowError(`${param.name} must be a number.`);
      kweSetProp(node, param, parsed);
    });
    wrapper.appendChild(input);
    return wrapper;
  }

  if (param.kind === "json") {
    input = document.createElement("input");
    input.type = "text";
    input.value = value === undefined ? "" : JSON.stringify(value);
    input.addEventListener("change", () => {
      try {
        kweSetProp(node, param, input.value.trim() === "" ? null : JSON.parse(input.value));
      } catch (err) {
        kweShowError(`${param.name} must be valid JSON (e.g. ["a", "b"]).`);
      }
    });
    wrapper.appendChild(input);
    return wrapper;
  }

  // kind === "str"
  input = document.createElement("input");
  input.type = "text";
  input.value = value === null || value === undefined ? "" : String(value);
  input.addEventListener("change", () => {
    // Empty means "unset" for an optional string whose default is null,
    // so clearing `color` goes back to the theme rather than setting an
    // empty colour the browser would then ignore in a confusing way.
    const next = input.value === "" && param.default === null ? null : input.value;
    kweSetProp(node, param, next);
  });
  wrapper.appendChild(input);
  return wrapper;
}

/** A page-level setting (width, theme). Same controls as a widget prop,
 *  but posted to /_edit/page and applied without touching the tree. */
function kwePageField(param) {
  const current = kweState.pageValues[param.name];
  const wrapper = kweField(param.label || param.name);

  let input;
  if (param.kind === "enum") {
    input = document.createElement("select");
    for (const choice of param.choices) input.appendChild(new Option(choice, choice));
    input.value = current == null ? "" : String(current);
    input.addEventListener("change", () => kweSetPage(param.name, input.value));
  } else {
    input = document.createElement("input");
    input.type = "number";
    input.value = current == null ? "" : String(current);
    input.addEventListener("change", () =>
      kweSetPage(param.name, input.value === "" ? null : parseFloat(input.value))
    );
  }
  wrapper.appendChild(input);

  if (param.help) {
    const help = document.createElement("div");
    help.className = "kwe-hint";
    help.textContent = param.help;
    wrapper.appendChild(help);
  }
  return wrapper;
}

async function kweSetPage(name, value) {
  try {
    const result = await kwePost("/_edit/page", { name, value });
    kweState.pageValues = result.page_values;
    // Width is baked into the page's HTML at render time, so the server
    // changing it does not move anything already on screen -- apply it
    // here too, or the panel would report a width the page isn't using
    // until the next reload.
    if (name === "width") {
      const root = document.getElementById("app-root");
      if (root) {
        if (value == null) root.style.removeProperty("--sg-app-width");
        else root.style.setProperty("--sg-app-width", `${value}px`);
      }
    }
    kweAbsorb(result);
  } catch (err) {
    kweShowError(err.message);
  }
}

function kweHandlerField(node, param) {
  const wrapper = kweField(param.label || param.name);
  const input = document.createElement("input");
  input.type = "text";
  input.placeholder = "e.g. on_save";
  input.value = (node.handlers || {})[param.name] || "";
  input.addEventListener("change", async () => {
    try {
      kweAbsorb(
        await kwePost("/_edit/handler", { id: node.id, event: param.name, name: input.value })
      );
    } catch (err) {
      kweShowError(err.message);
    }
  });
  wrapper.appendChild(input);
  return wrapper;
}

async function kweSetProp(node, param, value) {
  try {
    kweAbsorb(await kwePost("/_edit/prop", { id: node.id, name: param.name, value }));
  } catch (err) {
    kweShowError(err.message);
  }
}

function kweActions(node) {
  const heading = document.createElement("div");
  heading.className = "kwe-section";
  heading.textContent = "Actions";

  const row = document.createElement("div");
  row.className = "kwe-actions";

  const up = document.createElement("button");
  up.type = "button";
  up.textContent = "Move up";
  up.addEventListener("click", () => kweMove(node.id, -1));

  const down = document.createElement("button");
  down.type = "button";
  down.textContent = "Move down";
  down.addEventListener("click", () => kweMove(node.id, 1));

  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "kwe-danger";
  remove.textContent = "Delete";
  remove.addEventListener("click", async () => {
    try {
      kweState.selectedId = null;
      kweAbsorb(await kwePost("/_edit/delete", { id: node.id }));
    } catch (err) {
      kweShowError(err.message);
    }
  });

  row.append(up, down, remove);

  const fragment = document.createDocumentFragment();
  fragment.append(heading, row);
  return fragment;
}

async function kweMove(id, delta) {
  try {
    kweAbsorb(await kwePost("/_edit/move", { id, delta }));
  } catch (err) {
    kweShowError(err.message);
  }
}

// --- column resizing --------------------------------------------------------

/** Put a drag handle between each pair of columns of every `columns` the
 *  layout owns, and keep them positioned over the real gaps.
 *
 *  Handles are absolutely positioned siblings rather than elements
 *  injected between the columns: the widget tree is Vue's, and anything
 *  this overlay puts *inside* it would be wiped on the next re-render
 *  (and would change the flex layout it is trying to measure). They live
 *  in one container appended to <body> and are repositioned from the
 *  columns' own bounding boxes whenever the tree changes. */
function kweLayoutResizers() {
  const layer = document.getElementById("kwe-resizers");
  if (!layer) return;
  layer.innerHTML = "";

  for (const node of kweCollectColumnsNodes(kweState.doc.widgets)) {
    const element = kweWidgetElement(node.id);
    if (!element) continue;
    const columns = (node.children || [])
      .map((child) => kweWidgetElement(child.id))
      .filter(Boolean);
    if (columns.length < 2) continue;

    for (let index = 0; index < columns.length - 1; index++) {
      const left = columns[index].getBoundingClientRect();
      const right = columns[index + 1].getBoundingClientRect();
      if (left.width === 0 && right.width === 0) continue;

      const handle = document.createElement("div");
      handle.className = "kwe-resizer";
      handle.title = "Drag to set the column widths";
      // Centred on the gap between the two columns, in page coordinates
      // so it stays put while the page scrolls.
      handle.style.left = `${(left.right + right.left) / 2 + window.scrollX}px`;
      handle.style.top = `${Math.min(left.top, right.top) + window.scrollY}px`;
      handle.style.height = `${Math.max(left.height, right.height)}px`;
      handle.addEventListener("mousedown", (event) =>
        kweBeginResize(event, node, columns, index)
      );
      layer.appendChild(handle);
    }
  }
}

function kweCollectColumnsNodes(nodes, out = []) {
  for (const node of nodes || []) {
    if (node.type === "columns") out.push(node);
    kweCollectColumnsNodes(node.children, out);
  }
  return out;
}

function kweBeginResize(event, node, columns, index) {
  event.preventDefault();
  event.stopPropagation();

  // Only the two columns either side of this handle move; every other
  // column keeps the width it already has, which is what makes dragging
  // one divider feel local instead of reflowing the whole row.
  const widths = columns.map((column) => column.getBoundingClientRect().width);
  const startX = event.clientX;
  const pairTotal = widths[index] + widths[index + 1];
  const total = widths.reduce((sum, width) => sum + width, 0) || 1;
  const minimum = 24;

  document.body.classList.add("kwe-resizing");

  const onMove = (moveEvent) => {
    const delta = moveEvent.clientX - startX;
    const leftWidth = Math.max(minimum, Math.min(pairTotal - minimum, widths[index] + delta));
    const next = [...widths];
    next[index] = leftWidth;
    next[index + 1] = pairTotal - leftWidth;
    // Live preview straight on the DOM -- a round trip per mouse-move
    // would both lag and write hundreds of intermediate values to the
    // layout file. The real value is sent once, on mouseup.
    columns.forEach((column, i) => (column.style.flex = String(next[i] / total)));
    kweLayoutResizers();
  };

  const onUp = async () => {
    document.removeEventListener("mousemove", onMove, true);
    document.removeEventListener("mouseup", onUp, true);
    document.body.classList.remove("kwe-resizing");

    const finals = columns.map((column) => column.getBoundingClientRect().width);
    const sum = finals.reduce((a, b) => a + b, 0) || 1;
    const weights = kweNormalizeWeights(finals.map((width) => width / sum));
    try {
      kweAbsorb(await kwePost("/_edit/prop", { id: node.id, name: "n", value: weights }));
    } catch (err) {
      kweShowError(err.message);
    }
  };

  document.addEventListener("mousemove", onMove, true);
  document.addEventListener("mouseup", onUp, true);
}

/** Round to whole percent and make the result sum to exactly 1.
 *
 *  columns() rejects weights that don't sum to 1 (within 1e-6), and
 *  rounding each one independently is exactly how you end up at 0.99 or
 *  1.01 -- so the rounding error is pushed onto the largest weight,
 *  where it is least visible. */
function kweNormalizeWeights(raw) {
  const rounded = raw.map((weight) => Math.max(0.01, Math.round(weight * 100) / 100));
  const drift = Math.round((1 - rounded.reduce((a, b) => a + b, 0)) * 100) / 100;
  if (drift !== 0) {
    let largest = 0;
    for (let i = 1; i < rounded.length; i++) if (rounded[i] > rounded[largest]) largest = i;
    rounded[largest] = Math.round((rounded[largest] + drift) * 100) / 100;
  }
  return rounded;
}

// --- drag-and-drop reparenting ----------------------------------------------

//: The widget currently being dragged (mouse button down and moved past
//: the threshold -- see kweBeginWidgetDrag below), or null.
let kweDragId = null;
let kweDropTarget = null; // {parentId, index} while hovering a valid target

function kweContainerChildrenIds(containerId) {
  const node = containerId ? kweFindNode(kweState.doc.widgets, containerId) : null;
  const children = node ? node.children || [] : kweState.doc.widgets;
  return children.map((child) => child.id);
}

/** Whether `containerId`'s children lay out left-to-right rather than
 *  top-to-bottom, so a drop position can be judged on the right axis.
 *  `columns` itself is never a drop target (see kweContainerAt), so this
 *  only ever needs to ask a `container`/`column`'s own `direction` prop. */
function kweIsHorizontalContainer(containerId) {
  if (containerId === null) return false;
  const node = kweFindNode(kweState.doc.widgets, containerId);
  return Boolean(node && node.props && node.props.direction === "horizontal");
}

function kweIsDescendantOf(ancestorId, maybeDescendantId) {
  const ancestor = kweFindNode(kweState.doc.widgets, ancestorId);
  if (!ancestor) return false;
  const search = (node) => {
    if (node.id === maybeDescendantId) return true;
    return (node.children || []).some(search);
  };
  return search(ancestor);
}

/** Where, among `containerId`'s current children, the pointer at (x, y)
 *  says to insert -- as an index into that list with `excludeId` (the
 *  widget being dragged, if it's already one of these children) removed
 *  first. Removing it first is what keeps this index directly usable as
 *  the server's `move_to` index: the server detaches the dragged node
 *  before inserting it too (see EditSession.move_to), so both sides are
 *  always counting the same, already-detached list. */
function kweComputeDropIndex(containerId, x, y, excludeId) {
  const ids = kweContainerChildrenIds(containerId).filter((id) => id !== excludeId);
  const horizontal = kweIsHorizontalContainer(containerId);
  for (let i = 0; i < ids.length; i++) {
    const element = kweWidgetElement(ids[i]);
    if (!element) continue;
    const rect = element.getBoundingClientRect();
    const midpoint = horizontal ? rect.left + rect.width / 2 : rect.top + rect.height / 2;
    if ((horizontal ? x : y) < midpoint) return i;
  }
  return ids.length;
}

function kweDropIndicatorElement() {
  return document.getElementById("kwe-drop-indicator");
}

/** A thin bar at the exact boundary the drop would land on, plus an
 *  outline around the container it would land in -- so "this container"
 *  and "at this position within it" are both visible while dragging,
 *  not just inferred from the cursor. */
function kweShowDropIndicator(containerId, index, excludeId) {
  const indicator = kweDropIndicatorElement();
  if (!indicator) return;
  document.querySelectorAll(".kwe-drop-target-container").forEach((el) => el.classList.remove("kwe-drop-target-container"));

  const containerElement = containerId ? kweWidgetElement(containerId) : document.getElementById("app-root");
  if (containerElement) containerElement.classList.add("kwe-drop-target-container");

  const ids = kweContainerChildrenIds(containerId).filter((id) => id !== excludeId);
  const horizontal = kweIsHorizontalContainer(containerId);
  let rect = null;

  if (ids.length === 0) {
    if (containerElement) {
      const box = containerElement.getBoundingClientRect();
      rect = { left: box.left + 4, top: box.top + 4, width: box.width - 8, height: 3 };
    }
  } else {
    const referenceId = ids[Math.min(index, ids.length - 1)];
    const element = kweWidgetElement(referenceId);
    if (element) {
      const box = element.getBoundingClientRect();
      const before = index < ids.length;
      rect = horizontal
        ? { left: (before ? box.left : box.right) - 1, top: box.top, width: 3, height: box.height }
        : { left: box.left, top: (before ? box.top : box.bottom) - 1, width: box.width, height: 3 };
    }
  }

  if (!rect) {
    indicator.hidden = true;
    return;
  }
  indicator.hidden = false;
  indicator.style.left = `${rect.left + window.scrollX}px`;
  indicator.style.top = `${rect.top + window.scrollY}px`;
  indicator.style.width = `${Math.max(rect.width, 2)}px`;
  indicator.style.height = `${Math.max(rect.height, 2)}px`;
}

function kweHideDropIndicator() {
  const indicator = kweDropIndicatorElement();
  if (indicator) indicator.hidden = true;
  document.querySelectorAll(".kwe-drop-target-container").forEach((el) => el.classList.remove("kwe-drop-target-container"));
}

function kweEndDrag() {
  if (kweDragId) {
    const element = kweWidgetElement(kweDragId);
    if (element) element.classList.remove("kwe-dragging");
  }
  kweDragId = null;
  kweDropTarget = null;
  kweHideDropIndicator();
}

//: Set to true once a mousedown-tracked drag has moved past the
//: threshold, so the click that follows mouseup (browsers fire one
//: regardless of how far the pointer travelled in between -- that
//: cancellation is a native *HTML5 drag* behaviour, not a plain mouse
//: one) can be told apart from an actual click and ignored.
let kweSuppressNextClick = false;

/** Track a potential drag from mousedown, using plain mouse events
 *  rather than the native HTML5 Drag and Drop API.
 *
 *  Native `draggable`/dragstart/dragover/drop was the first approach
 *  here, and it does not work: synthetic pointer input (anything driven
 *  through a debugger/automation protocol, which is exactly how this was
 *  verified) cannot trigger a real browser's native OS-level drag
 *  gesture, only genuine hardware mouse input can -- so it was both
 *  unverifiable and, per Chromium's own documented behaviour, exactly as
 *  unreliable for a real user. This reuses the same mousedown/mousemove/
 *  mouseup pattern already proven to work for the column-resize handles
 *  (kweBeginResize) instead. */
function kweBeginWidgetDrag(startEvent, id) {
  const startX = startEvent.clientX;
  const startY = startEvent.clientY;
  const threshold = 6; // px of movement before this counts as a drag, not a click
  let dragging = false;

  const onMove = (moveEvent) => {
    if (!dragging) {
      if (Math.hypot(moveEvent.clientX - startX, moveEvent.clientY - startY) < threshold) return;
      dragging = true;
      kweDragId = id;
      kweClosePalette();
      const element = kweWidgetElement(id);
      if (element) element.classList.add("kwe-dragging");
    }

    // elementFromPoint, not moveEvent.target: with the mouse button held
    // down, the target of a mousemove stays pinned to whatever element
    // the drag started on (standard mouse-capture behaviour) rather than
    // following the cursor -- kweContainerAt needs the element actually
    // under the pointer right now.
    const hovered = document.elementFromPoint(moveEvent.clientX, moveEvent.clientY);
    const containerId = kweContainerAt(hovered);
    if (containerId === id || kweIsDescendantOf(id, containerId)) {
      // Dropping a widget into itself or its own descendant would splice
      // it into a subtree that is about to be removed out from under it
      // -- refuse rather than let the server's own guard turn this into
      // a visible error on every such hover.
      kweDropTarget = null;
      kweHideDropIndicator();
      return;
    }
    const index = kweComputeDropIndex(containerId, moveEvent.clientX, moveEvent.clientY, id);
    kweDropTarget = { parentId: containerId, index };
    kweShowDropIndicator(containerId, index, id);
  };

  const onUp = async () => {
    document.removeEventListener("mousemove", onMove, true);
    document.removeEventListener("mouseup", onUp, true);
    if (!dragging) return; // a plain click -- the existing click handler selects it

    const target = kweDropTarget;
    kweEndDrag();
    kweSuppressNextClick = true;
    if (!target) return;
    try {
      kweAbsorb(await kwePost("/_edit/move_to", { id, parent_id: target.parentId, index: target.index }));
      kweSelect(id);
    } catch (err) {
      kweShowError(err.message);
    }
  };

  document.addEventListener("mousemove", onMove, true);
  document.addEventListener("mouseup", onUp, true);
}

// --- keeping every widget inside the main panel -----------------------------

//: Set while a fit-correction is in flight, so the DOM mutation it causes
//: (widening #app-root) doesn't re-enter this function from the same
//: MutationObserver callback that is already in the middle of handling it.
let kweFitInProgress = false;

/** If anything on the page is wider than the main panel, widen the panel
 *  to fit instead of leaving it clipped or overflowing. Only ever grows:
 *  a widget shrinking back down does not shrink a width the user (or an
 *  earlier auto-fit) already set, since that's indistinguishable here
 *  from a deliberately chosen wide page.
 *
 *  Compares against the current `max-width` *setting*, not against
 *  `clientWidth` (#app-root's actual rendered width). Those two are not
 *  the same thing while editing: `body.kwe-edit`'s own `padding-right`
 *  reserves real screen space for the property panel (see editor.css),
 *  so `clientWidth` is capped at "viewport minus panel" the moment
 *  `max-width` exceeds that -- growing `max-width` further then does
 *  nothing to `clientWidth` at all, so comparing against it can never
 *  converge; it would just grow without bound. `scrollWidth`, in
 *  contrast, reflects the content's true intrinsic need regardless of
 *  how much of it the panel currently leaves room to actually show --
 *  and, like `max-width` itself under this codebase's `box-sizing:
 *  border-box` (base.css), it is already padding-inclusive, so the two
 *  are directly comparable with no padding arithmetic of its own
 *  (adding it a second time was an earlier, measured bug here: it made
 *  every single trigger -- including completely harmless ones, e.g. a
 *  drag's hover-class toggling -- look like a fresh overflow, growing
 *  the panel by one padding's worth forever, never converging). */
function kweEnsureMainPanelFits() {
  if (kweFitInProgress) return;
  const root = document.getElementById("app-root");
  if (!root) return;

  const currentMaxWidth = parseFloat(getComputedStyle(root).maxWidth) || 720;
  const neededMaxWidth = root.scrollWidth;

  if (neededMaxWidth <= currentMaxWidth + 2) return; // fits already (rounding slack)

  kweFitInProgress = true;
  kweSetPage("width", Math.ceil(neededMaxWidth) + 4).finally(() => {
    kweFitInProgress = false;
  });
}

// --- chrome construction ----------------------------------------------------

function kweBuildChrome() {
  const palette = document.createElement("div");
  palette.id = "kwe-palette";
  palette.className = "kwe-ui";
  palette.hidden = true;
  palette.innerHTML =
    '<div id="kwe-palette-target"></div>' +
    '<input id="kwe-palette-search" type="text" placeholder="Search widgets…" autocomplete="off">' +
    '<div id="kwe-palette-list"></div>';

  const panel = document.createElement("aside");
  panel.id = "kwe-panel";
  panel.className = "kwe-ui";
  panel.innerHTML =
    '<div id="kwe-panel-head">' +
    '<div id="kwe-panel-title">Nothing selected</div>' +
    '<div id="kwe-panel-path"></div>' +
    "</div>" +
    '<div id="kwe-panel-body"></div>';

  const resizers = document.createElement("div");
  resizers.id = "kwe-resizers";
  resizers.className = "kwe-ui";

  const dropIndicator = document.createElement("div");
  dropIndicator.id = "kwe-drop-indicator";
  dropIndicator.className = "kwe-ui";
  dropIndicator.hidden = true;

  const banner = document.createElement("div");
  banner.id = "kwe-banner";
  banner.className = "kwe-ui";
  banner.textContent = "EDIT MODE";

  document.body.append(palette, panel, resizers, dropIndicator, banner);

  const search = document.getElementById("kwe-palette-search");
  search.addEventListener("input", () => kweRenderPaletteList(search.value));
  search.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      kweMovePaletteActive(1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      kweMovePaletteActive(-1);
    } else if (event.key === "Enter") {
      event.preventDefault();
      const active = document.querySelector(".kwe-palette-item.kwe-active");
      if (active) kweInsert(active.dataset.type);
    } else if (event.key === "Escape") {
      event.preventDefault();
      kweClosePalette();
    }
  });
}

// --- input handling ---------------------------------------------------------

function kweInsideEditorUI(target) {
  return Boolean(target && target.closest && target.closest(".kwe-ui"));
}

function kweBindInput() {
  // All capture phase, all on document, for two reasons: widgets that are
  // disabled carry `pointer-events: none` (renderer.js) so their events
  // never bubble at all, and sidebar/topbar are teleported *outside*
  // #app-root, so anything scoped to the app root would miss them.
  document.addEventListener(
    "contextmenu",
    (event) => {
      if (kweInsideEditorUI(event.target)) return;
      event.preventDefault();
      kweOpenPalette(event.clientX, event.clientY, kweContainerAt(event.target));
    },
    true
  );

  document.addEventListener(
    "click",
    (event) => {
      if (kweInsideEditorUI(event.target)) return;
      // Edit mode is design mode: a click selects a widget, it does not
      // press it. Suppressing here (rather than letting the app's own
      // handler run first) is what stops "click a button to select it"
      // from also firing that button's callback.
      event.preventDefault();
      event.stopPropagation();
      // A click always fires after mouseup, however far the pointer
      // travelled getting there -- if that movement just completed a
      // drag-and-drop, this is that same gesture's trailing click, not a
      // separate one, and selection was already handled at drop time.
      if (kweSuppressNextClick) {
        kweSuppressNextClick = false;
        return;
      }
      kweClosePalette();
      kweSelect(kweSelectableAt(event.target));
    },
    true
  );

  // mousedown is also where a potential drag starts (see
  // kweBeginWidgetDrag) -- both share the same "is this an owned
  // widget" check, so it isn't duplicated in a second listener.
  document.addEventListener(
    "mousedown",
    (event) => {
      if (kweInsideEditorUI(event.target)) return;
      event.preventDefault();
      event.stopPropagation();
      if (event.button === 0) {
        const id = kweSelectableAt(event.target);
        if (id) kweBeginWidgetDrag(event, id);
      }
    },
    true
  );

  // Same reasoning as mousedown above for the remaining input events the
  // form-ish widgets emit -- a slider or checkbox in edit mode is a
  // thing being laid out, not a control being operated.
  for (const type of ["change", "input", "submit"]) {
    document.addEventListener(
      type,
      (event) => {
        if (kweInsideEditorUI(event.target)) return;
        event.preventDefault();
        event.stopPropagation();
      },
      true
    );
  }

  document.addEventListener(
    "keydown",
    (event) => {
      if (kweInsideEditorUI(event.target)) return;
      if (event.key === "Escape") kweClosePalette();
      // Stop here so the app's own global shortkey listener
      // (shortkeys.js, bubble phase on document) never fires while
      // designing -- pressing the app's Ctrl+S should not trigger its save
      // button when you are only trying to lay the page out.
      event.stopPropagation();
    },
    true
  );
}

// --- boot -------------------------------------------------------------------

async function kweBoot() {
  document.body.classList.add("kwe-edit");
  kweBuildChrome();
  kweBindInput();

  try {
    const state = await kweGet("/_edit/state");
    kweState.schema = state.schema;
    kweState.path = state.path;
    kweState.containerTypes = new Set(
      Object.keys(state.schema).filter((type) => state.schema[type].container)
    );
    kweState.pageSchema = state.page_schema || [];
    document.getElementById("kwe-panel-path").textContent = state.path;
    kweAbsorb(state);
    for (const message of state.errors || []) kweShowError(message);
  } catch (err) {
    kweShowError(`Could not load the editor: ${err.message}`);
  }

  // Vue re-renders the entire tree on every `init` the server sends after
  // a mutation, which drops the overlay's own data-kwe-* marks with it.
  // Re-applying them from an observer keeps them correct without the
  // editor having to know when Vue decided to re-render.
  //
  // Watches attributes/characterData as well as childList: a prop change
  // that could cause the main-panel overflow kweEnsureMainPanelFits()
  // corrects for -- a container's own `width` growing, an image's, a
  // text widget's content getting longer -- lands on the DOM as a plain
  // `style` or text-node update, not a child being added or removed, so
  // childList alone would miss most of the real cases this exists for.
  const KWE_OWN_ATTRS = new Set([
    "data-kwe-owner", "data-kwe-selected", // written by kweDecorate()
    "class", // toggled by kweShowDropIndicator()/kweHideDropIndicator()
  ]);
  const observer = new MutationObserver((records) => {
    // Ignore records that are either the overlay's own chrome (anything
    // under .kwe-ui, e.g. #kwe-resizers being rebuilt) or the overlay's
    // own bookkeeping attributes on real widgets (above) -- without this
    // the broadened watch below re-triggers on marks this same callback
    // just made, spinning forever and never letting the page settle.
    const meaningful = records.some((record) => {
      if (record.target.closest && record.target.closest(".kwe-ui")) return false;
      if (record.type === "attributes" && KWE_OWN_ATTRS.has(record.attributeName)) return false;
      return true;
    });
    if (!meaningful) return;
    kweDecorate();
    kweLayoutResizers();
    // Only here, not after every kweAbsorb: the real, rendered DOM (what
    // scrollWidth actually measures) only exists once Vue has processed
    // the "init" the server just broadcast, which is exactly what this
    // observer callback is reacting to. Measuring any earlier would see
    // the tree as it was before the change that might have caused the
    // overflow.
    kweEnsureMainPanelFits();
  });
  observer.observe(document.body, { childList: true, subtree: true, attributes: true, characterData: true });
  // The handles are positioned from measured boxes, so anything that
  // moves those boxes has to reposition them.
  window.addEventListener("resize", kweLayoutResizers);
  window.addEventListener("scroll", kweLayoutResizers, true);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", kweBoot);
} else {
  kweBoot();
}
