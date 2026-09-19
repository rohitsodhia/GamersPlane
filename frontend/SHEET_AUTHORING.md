# Character Sheet Authoring Guide

How to build a GamersPlane character sheet definition as the renderer works
**today**. A sheet is a single JSON document. There is no visual builder yet —
you write the JSON by hand — so this guide is the reference for every element
type, its keys, and the rules the renderer enforces.

Everything here reflects the code in
`frontend/src/routes/characters/sheets/-components/`. The mock in
`-test-design.tsx` is a live example you can copy from.

---

## 1. The big picture

### 1.1 Document shape

```jsonc
{
  "schema_version": 1,
  "classes": {                // optional — reusable style bundles (§8.3)
    "bubble": { "position": "absolute", "width": "30px" }
  },
  "elements": [               // required — the sheet, top to bottom
    { "type": "section", "content": [ /* ... */ ] },
    { "type": "grid", "name": "stats", /* ... */ }
  ]
}
```

- `schema_version` — schema version number. Currently `1`.
- `classes` — named style bundles any element can pull in by name (see §8.3).
- `elements` — an ordered array of **element nodes**. Each node has a `type`
  discriminator that selects the component that renders it. Container nodes carry
  their children in `content`; the renderer walks that recursively.

### 1.2 How a sheet renders

The renderer (`SheetRenderer`) walks `elements` in order and maps each node's
`type` to a component. Unknown `type` values render nothing (with a dev-console
warning). The whole tree is rendered inside a **value store** provider that every
input binds to.

### 1.3 Edit mode vs. display mode

The sheet renders in one of two modes:

- **edit** — inputs are real form controls; the user types into them; computed
  fields and defaults are written back into the store.
- **display** — every control renders its stored value as static text
  (`input`/`textarea`/`select` → a `<span>`, `checkbox` → `✓` / `—`). Buttons
  render but do nothing. The store is never mutated.

You author one sheet; the mode is chosen at render time. You don't need to do
anything special for display mode, but keep it in mind: a sheet that only makes
sense while editing (e.g. a bare button with no visible result) will look empty
in display.

### 1.4 The value document and scope

What the user types is stored in a structure that mirrors the sheet's **scope**
nesting, not its visual nesting:

- A scalar control (`input`, `select`, `textarea`, `checkbox`, computed `text`)
  contributes **one key** to its current scope: `name → value`.
- `section`, `group`, `list`, `loop` are **transparent** — their children write
  into the parent scope. They add no nesting.
- A `repeater` contributes one key holding an **array**, one entry per row:
  `name → [ { ...row }, { ...row } ]`.
- A `grid` contributes one key holding an **object**, one entry per fixed row,
  keyed by the row's `key`: `name → { str: { ...row }, dex: { ...row } }`.

So a sheet with a top-level `name` input, a `classes` repeater, and a `stats`
grid produces:

```jsonc
{
  "name": "Gandalf",
  "classes": [ { "class": "Wizard", "level": "20" }, { "class": "Fighter", "level": "2" } ],
  "stats": { "str": { "score": "15", "mod": 2 }, "dex": { "score": "10", "mod": 0 } }
}
```

**Why scope matters:** formulas and conditional styles (§7) resolve field
references (`{ "ref": "score" }`) against the *current* scope. Inside a `grid`
row for `str`, `{ "ref": "score" }` reads `stats.str.score`. There is no
"reach outward to a parent scope" or "reach the sheet root" syntax today — a
reference resolves within the row/scope it sits in.

### 1.5 Keys every element can carry

Regardless of `type`, any node may include:

| Key | Type | Purpose |
|---|---|---|
| `id` | string | Stable identifier, used as the React key. Optional in hand-written JSON (the renderer falls back to the tree path). Give containers and repeated things an `id` when you can. |
| `class` | string | Space-separated class tokens. Each token is either a `char-sheet-*` utility class (§8.1) or `headerbar`, or the name of a `classes` bundle (§8.3); any other token is dropped (§8.1). Authored as `class`, not `className`. |
| `styles` | object | Inline style overrides, restricted to an allowlist of properties and value formats (§8.2). Authored kebab-case like CSS. |
| `class_when` | object | Conditional classes — `{ "token": <formula> }`. The token is added while its formula is truthy. Re-evaluated reactively. (§7.4) |
| `style_when` | array | Conditional inline styles — `[ { "when": <formula>, "styles": { ... } } ]`. Merged on while `when` is truthy. (§7.4) |
| `col` | number | 1-based grid column. Only meaningful on a cell inside a `grid` / `repeater` **header** — pins that header label over a specific column. Ignored elsewhere. |

---

## 2. Containers & layout

### 2.1 `section`

A plain grouping box with visual separation (border, padding) and a styling
hook. Transparent for values.

```jsonc
{ "type": "section", "content": [
  { "type": "header", "text": "Identity" },
  { "type": "group", "content": [
    { "type": "label", "text": "Name" },
    { "type": "input", "name": "name" }
  ] }
] }
```

Children stack (flex column) by default, like `group`. Add
`char-sheet-section--row` to lay them out on one row instead.

### 2.2 `group`

The label-wiring container. A `group`:

- mints one DOM id,
- gives it to the one bound control inside it (or, when there are several bound
  controls, the one flagged `attach_label: true`),
- and every `label` child points its `htmlFor` at that id.

Layout is a `class` on the group, **not** an enum:

- default — stacked (label above control),
- `char-sheet-group--inline` — label and control on one row, label pinned to a
  fixed-width column so a stack of inline groups lines up.

```jsonc
{ "type": "group", "class": "char-sheet-group--inline", "content": [
  { "type": "label", "text": "Class" },
  { "type": "input", "name": "class" }
] }
```

Multiple bound controls in one group:

```jsonc
{ "type": "group", "content": [
  { "type": "label", "text": "Speed" },
  { "type": "input", "name": "speed", "attach_label": true },
  { "type": "input", "name": "speed_unit" }
] }
```

Bound-control types that can own a group's label: `input`, `textarea`, `select`,
`checkbox`. A computed `text` cannot (it renders a read-only `<span>`, so a
label beside it is just literal `text`, not a `<label>`).

### 2.3 `list`

An `<ol>` or `<ul>` wrapper. Transparent for values. Typical use is a single
`loop` child that emits one `<li>` per iteration.

| Key | Type | Notes |
|---|---|---|
| `variant` | `"ordered"` \| `"unordered"` | Required. Picks `<ol>` / `<ul>`. |
| `marker` | string | Optional. Overrides `list-style-type`. One of: `disc`, `circle`, `square`, `decimal`, `decimal-leading-zero`, `lower-alpha`, `upper-alpha`, `lower-roman`, `upper-roman`, `none`. |
| `content` | array | Child elements. |

```jsonc
{ "type": "list", "variant": "ordered", "content": [
  { "type": "loop", "count": 5, "content": [ { "type": "text", "text": "Wound" } ] }
] }
```

---

## 3. Text & headings

### 3.1 `header`

A section heading — renders an `<h2>`. No value.

| Key | Type | Notes |
|---|---|---|
| `text` | string | Required. |
| `headerbar` | boolean | Adds the site-wide `headerbar` class (the orange ribbon heading). Without it, a plain `<h2>` you can style with `class`. |

```jsonc
{ "type": "header", "text": "Abilities", "headerbar": true }
```

### 3.2 `label`

A `<label>`. Only meaningful **inside a `group`** — it wires its `htmlFor` to
that group's bound control. Outside a group it renders with no association.
Carries no value.

```jsonc
{ "type": "label", "text": "Alignment" }
```

### 3.3 `text` — literal

Text the user never types: a column header, a note between fields, a row label.
No value, no store contact. Use `text` and **not** `formula`.

```jsonc
{ "type": "text", "text": "Modifiers apply after armour." }
```

### 3.4 `text` — computed

A read-only value derived from other fields. Use `formula` + `name` and **not**
`text`.

| Key | Type | Notes |
|---|---|---|
| `formula` | expression | Required. An expression tree (§7). Evaluated against the current scope; recomputed whenever a referenced field changes. |
| `name` | string | Required with `formula`. The result is written back into the store under this key (edit mode) so other formulas and the saved character can read it. |
| `format` | string | Optional. `"number"` (default) → the number as-is; `"signed"` → non-negatives get a leading `+`; `"text"` → stringified. Booleans render `yes` / `no`. |

```jsonc
{
  "type": "text",
  "name": "mod",
  "format": "signed",
  "formula": { "op": "floor", "args": [
    { "op": "/", "args": [ { "op": "-", "args": [ { "ref": "score" }, 10 ] }, 2 ] }
  ] }
}
```

---

## 4. Input controls

All four bind to the value store by `name`, scoped to the element's position in
the tree. None carries its own label — put a sibling `label` in the enclosing
`group` (§2.2). All accept `default` (§6).

### 4.1 `input`

Single-line text field.

| Key | Type | Notes |
|---|---|---|
| `name` | string | Required. Storage key. |
| `maxlength` | number | Optional. Forwarded to the input's `maxLength`. |
| `default` | string \| number | Optional. Coerced to a string. |
| `attach_label` | boolean | Optional. See §2.2. |

```jsonc
{ "type": "input", "name": "score", "maxlength": 2, "default": 10 }
```

### 4.2 `textarea`

Multi-line text field. Display mode preserves newlines.

| Key | Type | Notes |
|---|---|---|
| `name` | string | Required. |
| `rows` | number | Optional. Visible row count. Ignored when `richtext`. |
| `maxlength` | number | Optional. Ignored when `richtext`. |
| `default` | string | Optional. Ignored when `richtext`. |
| `richtext` | boolean | Optional. When `true`, the edit control is the full rich-text `Editor` instead of a plain `<textarea>`, and the value is stored as a Tiptap JSON document (not a string). Display mode renders it as formatted HTML. |
| `attach_label` | boolean | Optional. |

```jsonc
{ "type": "textarea", "name": "backstory", "rows": 4 }
{ "type": "textarea", "name": "bio", "richtext": true }
```

### 4.3 `select`

Single-choice dropdown (built on the shared React-Aria `Select`; the trigger
sizes to the widest option). A blank choice is offered unless `default` picks
one.

| Key | Type | Notes |
|---|---|---|
| `name` | string | Required. |
| `values` | array | Required. Each entry is a bare string (value === label) or a `{ "value", "label" }` pair (use the pair when the stored value differs from the visible text). |
| `default` | string | Optional. Must match one option's `value`. When set, no blank choice is offered. |
| `attach_label` | boolean | Optional. |

```jsonc
{
  "type": "select",
  "name": "alignment",
  "default": "tn",
  "values": [
    { "value": "lg", "label": "Lawful Good" },
    { "value": "tn", "label": "True Neutral" },
    { "value": "ce", "label": "Chaotic Evil" }
  ]
}
```

```jsonc
{ "type": "select", "name": "size", "values": [ "Small", "Medium", "Large" ] }
```

### 4.4 `checkbox`

Single boolean. Renders a box in edit mode, `✓` / `—` in display mode.

| Key | Type | Notes |
|---|---|---|
| `name` | string | Required. |
| `default` | boolean | Optional. |
| `attach_label` | boolean | Optional. See §2.2. |

```jsonc
{ "type": "checkbox", "name": "save_prof" }
```

---

## 5. Structured & repeating data

### 5.1 `repeater` — user-controlled rows

A repeatable group of fields with runtime **add / remove** controls. Its value
is an array of row records, each keyed by its child elements' own `name`s.

| Key | Type | Notes |
|---|---|---|
| `name` | string | Required. Storage key (holds the array). |
| `content` | array | Required. The **row template** — rendered once per row. |
| `header` | array | Optional. Column headers, rendered once above the rows. Use literal `text`, never `label` (a header describes a whole column, not one control). When `header` is set, put no `label`s in the row template. |
| `row_layout` | `"stack"` \| `"row"` | Optional. Field arrangement within a row. Default `"stack"`. |
| `columns` | string[] | Optional. Grid track list (§8.4). One entry per header cell **plus one for every non-header cell a row can render** (a `collapsible`, an add/remove `button`, a toggle), in template order. Only meaningful with `row_layout: "row"`. When present, header and rows lay out as aligned CSS-grid subgrids so headers sit over their inputs. |
| `row_class` | string | Optional. Extra class on each row wrapper. |
| `add_label` | string | Optional. Text for the auto-rendered add control. Default `"Add"`. |
| `add_class` | string | Optional. Extra class on the add control. |
| `add_button_pos` | string | Optional. `"top"`, `"bottom"` (default), `"header"` (needs `header`), `"row-end"` (trailing the last row). Ignored when the template places its own add button (§5.2). |
| `min` | number | Optional. Minimum rows; remove is hidden at this floor. Default `0`. |
| `max` | number | Optional. Maximum rows; add is hidden at this ceiling. |

**Which template cells get a header column:** `group`, `input`, `textarea`,
`select`, `checkbox`, `text`. An add/remove `button` (§5.2),
`collapsible-toggle`, and `collapsible` consume no header slot and don't shift
column alignment.

```jsonc
{
  "type": "repeater",
  "name": "classes",
  "row_layout": "row",
  "columns": [ "10rem", "5rem", "max-content", "1fr", "max-content" ],
  "header": [
    { "type": "text", "text": "Class" },
    { "type": "text", "text": "Level" }
  ],
  "content": [
    { "type": "group", "content": [ { "type": "input", "name": "class" } ] },
    { "type": "group", "content": [ { "type": "input", "name": "level" } ] },
    { "type": "collapsible-toggle", "target": "note", "label": "Note" },
    { "type": "collapsible", "name": "note", "collapsed": true, "content": [
      { "type": "textarea", "name": "note", "rows": 2 }
    ] },
    { "type": "button", "label": "[ Add Class ]", "on_click": { "row": "add" } }
  ]
}
```

### 5.2 Add / remove controls

The add / remove controls are owned by the repeater — never authorable elements.
By default the add control auto-renders (position via `add_button_pos`,
text via `add_label`) and there is no remove control.

To place either precisely, drop a `button` into the row template with an
`on_click` of `{ "row": "add" }` or `{ "row": "remove" }`. It binds to the
enclosing repeater **by position** — no `name` reference — and the repeater still
owns it:

- `{ "row": "add" }` — rendered once, on the last row, at the button's spot.
  Suppresses the auto-rendered add control and `add_button_pos`. Hidden at `max`.
- `{ "row": "remove" }` — rendered on every row at the button's spot. Hidden at
  `min`.

Because it is a real `button` (§9.1) it takes `label`, `class`, `class_when`,
`style_when`, and is inert in display mode. A `row` action outside a repeater is
a no-op (DEV-warned).

```jsonc
{ "type": "button", "label": "×", "on_click": { "row": "remove" } }
```

### 5.3 `grid` — fixed table

A fixed-layout table on CSS-grid tracks, with each row a subgrid so cells line
up. A grid **never changes its row count** — "repeat" here is author-time
template expansion, not a runtime control. Value doc:
`name → { <key>: { <field>: value } }`.

Common keys:

| Key | Type | Notes |
|---|---|---|
| `name` | string | Required. Storage key (holds the object). |
| `columns` | string[] | Optional. Grid track list (§8.4), one entry per column. Falls back to a label column + one flexible column. |
| `row_class` | string | Optional. Extra class on every row wrapper. |

There are **two authoring forms**, and setting both is an error:

**Compact form** — `items` + `row`:

| Key | Type | Notes |
|---|---|---|
| `items` | array | `[ { "key", "label" } ]`. Each becomes a row: first cell is a literal `text` of `label`, remaining cells are `row`, scoped under `name[key]`. |
| `row` | array | The row template. Child `name`s are row-relative. |
| `header` | array | Optional. Rendered once on the tracks. A child may carry `col` to pin it over a column. |

```jsonc
{
  "type": "grid",
  "name": "stats",
  "columns": [ "var(--char-sheet-label-col)", "3rem", "2.5rem", "max-content" ],
  "items": [
    { "key": "str", "label": "Strength" },
    { "key": "dex", "label": "Dexterity" },
    { "key": "con", "label": "Constitution" }
  ],
  "header": [ { "type": "text", "text": "Save Prof?", "col": 4 } ],
  "row": [
    { "type": "input", "name": "score", "maxlength": 2, "default": 10 },
    { "type": "text", "name": "mod", "format": "signed", "formula": {
      "op": "floor", "args": [ { "op": "/", "args": [
        { "op": "-", "args": [ { "ref": "score" }, 10 ] }, 2 ] } ] } },
    { "type": "checkbox", "name": "save_prof" }
  ]
}
```

**Explicit form** — `content`: an optional leading `grid_header`, then one
`grid_row` per row.

- `grid_row` — `{ "key", "content": [ ...cells ] }`. The row label is just an
  ordinary first cell you write (`label` or `text`). Accepts `class`.
- `grid_header` — `{ "content": [ ...cells ] }`. Rendered once on the tracks.
  Each child may carry `col`.

```jsonc
{
  "type": "grid",
  "name": "defenses",
  "columns": [ "var(--char-sheet-label-col)", "1fr" ],
  "content": [
    { "type": "grid_header", "content": [
      { "type": "text", "text": "" },
      { "type": "text", "text": "Value" }
    ] },
    { "type": "grid_row", "key": "ac", "content": [
      { "type": "text", "text": "Armour Class" },
      { "type": "input", "name": "value" }
    ] },
    { "type": "grid_row", "key": "fort", "content": [
      { "type": "text", "text": "Fortitude" },
      { "type": "input", "name": "value" }
    ] }
  ]
}
```

### 5.4 `grid` vs. `repeater` vs. `loop`

| | Row count | Per-row value scope |
|---|---|---|
| `repeater` | Runtime (user add/remove) | Yes — array entries |
| `grid` | Fixed by author | Yes — object keyed by `key` |
| `loop` | Fixed by author (or a formula) | **No** — see §6 |

---

## 6. Presentational repetition — `loop`

Repeats its `content` template. **Presentational only:** a `loop` adds no value
scope, so a bound or computed field inside a loop writes **one shared key** every
iteration. Use `grid` when each iteration needs its own values; use `loop` for
segmented visuals (clocks, tracks, wound rows) and click-to-set patterns.

Two forms, discriminated by `items`:

| Key | Type | Notes |
|---|---|---|
| `items` | array | Explicit form: one iteration per entry. Each entry's own keys resolve as refs in the body (e.g. `{ "ref": "label" }`). Excludes `count`. |
| `count` | number \| expression | Compact form: iteration count — a literal integer, or a formula over the enclosing scope. Floored, clamped to 200. Excludes `items`. |
| `content` | array | The template, rendered once per iteration. |

The body can read `$index` — the 0-based iteration number — as a ref:
`{ "ref": "$index" }`. Setting both `items` and `count` ignores `count`; setting
neither renders nothing.

A `loop` has no wrapper of its own — its `class` / `styles` / `class_when` /
`style_when` apply to **each iteration**. Wrap it in a `section` / `group` /
`list` for layout. Inside a `list`, each iteration is an `<li>`.

```jsonc
{
  "type": "list",
  "variant": "ordered",
  "content": [
    {
      "type": "loop",
      "count": 5,
      "style_when": [
        { "when": { "op": "<=", "args": [
            { "op": "+", "args": [ { "ref": "$index" }, 1 ] },
            { "ref": "wounds_taken" }
          ] },
          "styles": { "color": "#b5342a" } }
      ],
      "content": [ { "type": "text", "text": "Dramatic Wound" } ]
    }
  ]
}
```

---

## 7. Formulas (expression trees)

A formula is a small **expression tree** authored directly as JSON. There is no
string syntax — you write the tree. It appears in: computed `text` (`formula`),
`class_when` / `style_when` conditions (`when`), a `loop`'s `count`, and a
`button`'s `on_click.to`.

### 7.1 Node forms

```
Expr :=
  | number                          e.g. 10, -2, 1.5
  | boolean                         true / false
  | { "ref": "<name>" }             read a field's value from the current scope
  | { "op": "<name>", "args": [ Expr, ... ] }
```

### 7.2 References

- `{ "ref": "score" }` — reads `score` from the **current scope** (the
  repeater/grid row you're in, or the sheet otherwise). No parent-scope or
  sheet-root reach today.
- `{ "ref": "$index" }` — the nearest enclosing `loop`'s 0-based iteration index
  (`0` when not inside a loop).
- Inside a `loop`'s `items` form, `{ "ref": "<key>" }` reads that key from the
  current entry.

Resolution order: `$index` → current `loop` `items` entry key → value store at
`[...scope, name]`.

### 7.3 Operators

| Category | `op` values | Arity |
|---|---|---|
| Arithmetic | `+` `-` `*` `/` `%` | 2 |
| Negate | `neg` | 1 |
| Compare (→ boolean) | `==` `!=` `<` `<=` `>` `>=` | 2 |
| Logical (→ boolean) | `&&` `\|\|` | 2 |
| Not | `!` | 1 |
| Conditional | `if` — `if(cond, then, else)` | 3 |
| Rounding | `floor` `ceil` `round` `abs` | 1 |
| Multi-arg | `min` `max` | 1+ |
| `clamp` — `clamp(value, lo, hi)` | | 3 |
| `sum` | | 0+ |

### 7.4 Coercion (lenient by design)

- A ref that is missing, empty, or non-numeric → `0`.
- Booleans act as `0` / `1` in arithmetic, and as themselves in conditionals.
- Division / modulo by zero → `0`.
- A truthy check treats `0` and `NaN` as false, everything else true.

A **malformed tree** (unknown `op`, wrong arg count, a node that is neither
literal/ref/op) is the only error case. In a computed field it yields `0`; in a
`when` condition it counts as false; in `on_click.to` the click becomes a no-op.
All are dev-console-warned.

### 7.5 `class_when` and `style_when`

Reactive visual state driven by values.

```jsonc
{
  "type": "input",
  "name": "score",
  "style_when": [
    { "when": { "op": ">=", "args": [ { "ref": "score" }, 16 ] },
      "styles": { "background-color": "#e6f5e6" } }
  ],
  "class_when": {
    "char-sheet-value--multiline": { "op": ">", "args": [ { "ref": "score" }, 20 ] }
  }
}
```

- `style_when` entries merge in order (later wins per property), layered on top
  of the static `styles`.
- `class_when` keys are class tokens (space-separated allowed) added while their
  formula is truthy. Each token must be a `char-sheet-*` utility or `headerbar`
  (§8.1) — bundle names are not resolved here, and any other token is dropped.
- Both re-evaluate whenever a referenced field changes.

---

## 8. Styling

### 8.1 Utility classes (`class`)

Use these `char-sheet-*` classes as `class` tokens (plus `headerbar` for the
orange ribbon heading). This is the curated vocabulary sheets may reference:

| Class | Use |
|---|---|
| `char-sheet-group--inline` | Lay a `group` out as label + control on one row, label in a fixed column. |
| `char-sheet-section` | Applied automatically to `section`; available for re-use. |
| `char-sheet-section--row` | Lay a `section`'s children out on one row instead of stacked. |
| `char-sheet-label` | Applied automatically to `label`. |
| `char-sheet-field` | The bare wrapper around label-less controls (`checkbox`, computed `text`). |
| `char-sheet-textarea` | Applied automatically to `textarea` (full width, vertical resize). |
| `char-sheet-textarea--richtext` | Wraps a `richtext` `textarea`'s `Editor` in edit mode. |
| `char-sheet-select` | Applied automatically to `select`. |
| `char-sheet-value--multiline` | Preserve newlines in a display-mode value. |
| `char-sheet-value--richtext` | Wraps a `richtext` `textarea`'s formatted HTML in display mode. |
| `char-sheet-button` | Applied automatically to `button` (generic; compose a clock look with `styles` + `style_when`). |
| `char-sheet-collapsible-toggle` | Applied automatically to `collapsible-toggle` (link styling). |
| `char-sheet-list` | Applied automatically to `list`. |
| `char-sheet-loop-item` | Applied automatically to a `loop` iteration outside a `list`. |
| `char-sheet-repeater*`, `char-sheet-grid*` | Structural classes applied automatically by those components. |

A `class` token that isn't one of these is treated as the name of a `classes`
bundle (§8.3). If it's neither — not a `char-sheet-*` utility (or `headerbar`),
and not a defined bundle name — it is **dropped** with a dev warning and never
reaches the DOM. The `char-sheet-*` check is by shape (`char-sheet-` + lowercase
letters, digits, hyphens), so a misspelled utility class is silently inert
rather than rejected, same as an unknown class has always been. The same rule
applies to `class_when` keys (§7.5) and to `row_class` / `add_class` on
`repeater` / `grid`.

### 8.2 Inline `styles` allowlist

`styles` is authored kebab-case, like CSS, but only these properties are
accepted and each value is format-checked. Anything unlisted or malformed is
dropped (dev-warned), never sent to the DOM.

| Property | Accepted values |
|---|---|
| `position` | `absolute` \| `relative` |
| `left` `right` `top` `bottom` | a length: `<n>px`/`rem`/`em`/`%`/`ch`/`vh`/`vw`/`ex`, or `0` |
| `width` `height` | a length, or `auto` |
| `padding` | 1–4 space-separated lengths |
| `margin` | 1–4 space-separated lengths (each may be `auto`) |
| `background-color` `color` `border-color` | `#rgb`–`#rrggbbaa` hex, `rgb()/rgba()`, `hsl()/hsla()`, or a bare CSS color name. **No `var()` / `oklch()`.** |
| `background-image` | `url(...)` — **https:// or a root-relative `/path` only**. No `data:` / other schemes. |
| `background-size` | 1–2 tokens of `cover` \| `contain` \| `auto` \| length |
| `background-position` | 1–2 tokens of `left` \| `right` \| `center` \| `top` \| `bottom` \| length |
| `background-repeat` | `repeat` \| `repeat-x` \| `repeat-y` \| `no-repeat` \| `space` \| `round` |
| `border-width` `border-radius` | 1–4 space-separated lengths |
| `border-style` | 1–4 tokens of `none`/`solid`/`dashed`/`dotted`/`double`/`groove`/`ridge`/`inset`/`outset` |

Notes:

- `z-index` is not settable. Setting `position: "absolute"` automatically stamps
  `z-index: 5` — enough to overlay fields on a `background-image` without manual
  stacking fights.
- Per-property precedence: `classes` bundle (earlier token) < `classes` bundle
  (later token) < the element's own `styles` < active `style_when` entries.

### 8.3 Reusable bundles (`classes`)

Define named `styles` bundles at the top of the schema; reference one (or
several, space-separated) by putting the name in an element's `class`.

```jsonc
{
  "classes": {
    "bubble": {
      "position": "absolute",
      "width": "30px", "height": "30px",
      "border-radius": "15px",
      "border-width": "2px", "border-style": "solid", "border-color": "#8b3a3a"
    }
  },
  "elements": [
    { "type": "checkbox", "name": "wound_1", "class": "bubble",
      "styles": { "top": "104px", "left": "9px" } }
  ]
}
```

A bundle is the same allowlist as `styles` — inline style only, no selectors,
pseudo-classes, or media queries.

### 8.4 Grid track lists (`columns`)

On `grid` and `repeater`, `columns` is an **array where each entry is one whole
track token** (not a space-separated string). Each entry is validated against a
closed vocabulary; a bad entry is dropped (dev-warned).

Allowed per entry:

- a non-negative length (`3rem`, `120px`, `0`)
- `<n>fr` (`1fr`, `2.5fr`)
- `auto` \| `min-content` \| `max-content`
- `var(--char-sheet-*)` — notably `var(--char-sheet-label-col)`, the shared
  label-column width (default `11rem`) that inline `group`s also use, so a stack
  of grids and inline groups lines up
- `minmax(<size>, <size>)`
- `repeat(<1–50 | auto-fill | auto-fit>, <size|minmax> ...)`

`calc()` and nested `repeat()` are rejected.

```jsonc
"columns": [ "var(--char-sheet-label-col)", "3rem", "2.5rem", "max-content" ]
```

---

## 9. Interaction

### 9.1 `button`

A button with one declarative `on_click`. Carries no value of its own. Inert in
display mode.

| Key | Type | Notes |
|---|---|---|
| `label` | string | Required. Button text (may be `""` for a bare segment). |
| `on_click` | object | Required. One of the two shapes below. |

**`{ "set": "<sibling name>", "to": <formula> }`** — write one sibling scalar in
the current scope. The schema's only "an element changes another element's value"
interaction, and the basis of clocks / stress tracks. `to` is evaluated at click
time, so it can read `$index`, the target's current value, and siblings.

```jsonc
{ "type": "button", "label": "Reset", "on_click": { "set": "harm", "to": 0 } }
```

**`{ "row": "add" | "remove" }`** — add / remove a row of the enclosing
`repeater`. Valid only inside a repeater's row template; see §5.2 for placement
and `min` / `max` gating.

```jsonc
{ "type": "button", "label": "[ Add Row ]", "on_click": { "row": "add" } }
```

**Clock / track pattern** — a `loop` of buttons, each setting a shared counter to
its 1-based position, with `style_when` filling every segment at or below it:

```jsonc
{
  "type": "loop",
  "count": 6,
  "content": [
    {
      "type": "button",
      "label": "",
      "styles": {
        "width": "22px", "height": "22px", "border-radius": "11px",
        "border-width": "2px", "border-style": "solid", "border-color": "#8b3a3a",
        "background-color": "#ffffff"
      },
      "style_when": [
        { "when": { "op": "<=", "args": [
            { "op": "+", "args": [ { "ref": "$index" }, 1 ] },
            { "ref": "harm" }
          ] },
          "styles": { "background-color": "#b5342a", "border-color": "#b5342a" } }
      ],
      "on_click": {
        "set": "harm",
        "to": { "op": "if", "args": [
          { "op": "==", "args": [ { "ref": "harm" }, { "op": "+", "args": [ { "ref": "$index" }, 1 ] } ] },
          { "ref": "$index" },
          { "op": "+", "args": [ { "ref": "$index" }, 1 ] }
        ] }
      }
    }
  ]
}
```

(Clicking the current top segment clears back down to it; clicking any other
segment fills up to it.)

### 9.2 `collapsible` + `collapsible-toggle`

A region that shows/hides. The region has **no trigger of its own** — a separate
`collapsible-toggle` drives it by name, kept outside so it stays visible when
the region is closed.

`collapsible`:

| Key | Type | Notes |
|---|---|---|
| `name` | string | Required. The id a toggle points its `target` at. |
| `collapsed` | boolean | Optional. Start collapsed. Default `false` (open). |
| `content` | array | The hidden/shown content. |

`collapsible-toggle`:

| Key | Type | Notes |
|---|---|---|
| `target` | string | Required. The `name` of the `collapsible` it toggles. |
| `label` | string | Required. Button text. |

The two are matched within the **nearest disclosure scope**: one is minted at
the sheet root, and one per `repeater` / `grid` row. So a `collapsible` named
`note` and its toggle can appear in every repeater row and each pair toggles
independently.

```jsonc
{ "type": "section", "content": [
  { "type": "collapsible-toggle", "target": "gm_notes", "label": "GM Notes" },
  { "type": "collapsible", "name": "gm_notes", "collapsed": true, "content": [
    { "type": "group", "content": [
      { "type": "label", "text": "Secret" },
      { "type": "textarea", "name": "gm_notes_text", "rows": 3 }
    ] }
  ] }
] }
```

---

## 10. Defaults and seeding

`default` (on `input`, `textarea`, `select`, `checkbox`) is used while nothing is
stored. In **edit mode**, on first mount, the default is also written into the
value document so an untouched-but-defaulted field still round-trips on save. An
explicit stored `null` or `""` is left alone. `select`'s `default` must match one
option's `value`; when set, the blank choice is not offered.

A computed `text` writes its result under `name` on every recompute (edit mode
only), so downstream formulas and the saved character can read it.

---

## 11. Element quick reference

| `type` | Value? | Container? | Key required keys |
|---|---|---|---|
| `section` | — | yes (transparent) | `content` |
| `group` | — | yes (transparent) | `content` |
| `label` | — | — | `text` |
| `header` | — | — | `text` |
| `text` (literal) | — | — | `text` |
| `text` (computed) | writes `name` | — | `formula`, `name` |
| `input` | `name → string` | — | `name` |
| `textarea` | `name → string` (Tiptap JSON doc when `richtext`) | — | `name` |
| `select` | `name → string` | — | `name`, `values` |
| `checkbox` | `name → boolean` | — | `name` |
| `repeater` | `name → array` | yes | `name`, `content` |
| `grid` | `name → object` | yes | `name` + (`items`+`row`) or `content` |
| `grid_row` | — | yes | `key`, `content` (grid-only) |
| `grid_header` | — | yes | `content` (grid-only) |
| `list` | — | yes (transparent) | `variant`, `content` |
| `loop` | — (no scope) | yes (transparent) | `content` + (`items` or `count`) |
| `button` | — | — | `label`, `on_click` (`{set,to}` or `{row}`) |
| `collapsible` | — | yes (transparent) | `name`, `content` |
| `collapsible-toggle` | — | — | `target`, `label` |

---

## 12. Worked example

A compact d20-style sheet: identity, an ability grid with live modifiers, a
skills repeater, a harm clock, and notes with a GM-only collapsible.

```jsonc
{
  "schema_version": 1,
  "elements": [
    {
      "type": "section",
      "content": [
        { "type": "header", "text": "Identity", "headerbar": true },
        { "type": "group", "content": [
          { "type": "label", "text": "Name" },
          { "type": "input", "name": "name" }
        ] },
        { "type": "group", "class": "char-sheet-group--inline", "content": [
          { "type": "label", "text": "Ancestry" },
          { "type": "input", "name": "ancestry" }
        ] },
        { "type": "group", "class": "char-sheet-group--inline", "content": [
          { "type": "label", "text": "Alignment" },
          { "type": "select", "name": "alignment", "default": "tn", "values": [
            { "value": "lg", "label": "Lawful Good" },
            { "value": "tn", "label": "True Neutral" },
            { "value": "ce", "label": "Chaotic Evil" }
          ] }
        ] }
      ]
    },

    {
      "type": "section",
      "content": [
        { "type": "header", "text": "Abilities" },
        {
          "type": "grid",
          "name": "abilities",
          "columns": [ "var(--char-sheet-label-col)", "3rem", "2.5rem", "max-content" ],
          "items": [
            { "key": "str", "label": "Strength" },
            { "key": "dex", "label": "Dexterity" },
            { "key": "con", "label": "Constitution" },
            { "key": "int", "label": "Intelligence" },
            { "key": "wis", "label": "Wisdom" },
            { "key": "cha", "label": "Charisma" }
          ],
          "header": [
            { "type": "text", "text": "Score", "col": 2 },
            { "type": "text", "text": "Mod", "col": 3 },
            { "type": "text", "text": "Save?", "col": 4 }
          ],
          "row": [
            { "type": "input", "name": "score", "maxlength": 2, "default": 10,
              "style_when": [
                { "when": { "op": ">=", "args": [ { "ref": "score" }, 16 ] },
                  "styles": { "background-color": "#e6f5e6" } }
              ] },
            { "type": "text", "name": "mod", "format": "signed",
              "formula": { "op": "floor", "args": [
                { "op": "/", "args": [
                  { "op": "-", "args": [ { "ref": "score" }, 10 ] }, 2 ] } ] },
              "style_when": [
                { "when": { "op": "<", "args": [ { "ref": "mod" }, 0 ] },
                  "styles": { "color": "#b5342a" } }
              ] },
            { "type": "checkbox", "name": "save_prof" }
          ]
        }
      ]
    },

    {
      "type": "section",
      "content": [
        { "type": "header", "text": "Skills" },
        {
          "type": "repeater",
          "name": "skills",
          "row_layout": "row",
          "columns": [ "12rem", "4rem", "max-content" ],
          "header": [
            { "type": "text", "text": "Skill" },
            { "type": "text", "text": "Bonus" }
          ],
          "add_label": "[ Add Skill ]",
          "content": [
            { "type": "group", "content": [ { "type": "input", "name": "skill" } ] },
            { "type": "group", "content": [ { "type": "input", "name": "bonus", "maxlength": 3 } ] },
            { "type": "button", "label": "×", "on_click": { "row": "remove" } }
          ]
        }
      ]
    },

    {
      "type": "section",
      "content": [
        { "type": "header", "text": "Harm" },
        { "type": "group", "class": "char-sheet-group--inline", "content": [
          {
            "type": "loop",
            "count": 6,
            "content": [
              {
                "type": "button",
                "label": "",
                "styles": {
                  "width": "22px", "height": "22px", "border-radius": "11px",
                  "border-width": "2px", "border-style": "solid",
                  "border-color": "#8b3a3a", "background-color": "#ffffff"
                },
                "style_when": [
                  { "when": { "op": "<=", "args": [
                      { "op": "+", "args": [ { "ref": "$index" }, 1 ] },
                      { "ref": "harm" } ] },
                    "styles": { "background-color": "#b5342a", "border-color": "#b5342a" } }
                ],
                "on_click": {
                  "set": "harm",
                  "to": { "op": "if", "args": [
                    { "op": "==", "args": [ { "ref": "harm" },
                      { "op": "+", "args": [ { "ref": "$index" }, 1 ] } ] },
                    { "ref": "$index" },
                    { "op": "+", "args": [ { "ref": "$index" }, 1 ] }
                  ] }
                }
              }
            ]
          }
        ] },
        { "type": "group", "class": "char-sheet-group--inline", "content": [
          { "type": "label", "text": "Harm" },
          { "type": "text", "name": "harm_readout", "formula": { "ref": "harm" } },
          { "type": "button", "label": "Reset", "on_click": { "set": "harm", "to": 0 } }
        ] }
      ]
    },

    {
      "type": "section",
      "content": [
        { "type": "header", "text": "Notes" },
        { "type": "group", "content": [
          { "type": "label", "text": "Player Notes" },
          { "type": "textarea", "name": "notes", "rows": 4 }
        ] },
        { "type": "collapsible-toggle", "target": "gm", "label": "GM Notes" },
        { "type": "collapsible", "name": "gm", "collapsed": true, "content": [
          { "type": "group", "content": [
            { "type": "label", "text": "Secret" },
            { "type": "textarea", "name": "gm_notes", "rows": 3 }
          ] }
        ] }
      ]
    }
  ]
}
```

Resulting value document (after some editing):

```jsonc
{
  "name": "Vex",
  "ancestry": "Elf",
  "alignment": "tn",
  "abilities": {
    "str": { "score": "12", "mod": 1, "save_prof": false },
    "dex": { "score": "17", "mod": 3, "save_prof": true }
    // con, int, wis, cha ...
  },
  "skills": [
    { "skill": "Stealth", "bonus": "+7" },
    { "skill": "Arcana", "bonus": "+4" }
  ],
  "harm": 2,
  "harm_readout": 2,
  "notes": "Owes the guild a favour.",
  "gm_notes": "Secretly the baron's heir."
}
```

---

## 13. Appendix: full CSS class whitelist

Every class defined in `-components/char-sheet.css`. This is the complete
`char-sheet-*` vocabulary a sheet's `class` may reference (plus `headerbar`, the
site-wide orange-ribbon heading class from outside this file). A `class` token
that matches the `char-sheet-*` shape but is not on this list is inert — no
styling behind it. A token that is neither `char-sheet-*`/`headerbar` nor a
`classes` bundle name is dropped entirely (dev-warned) and never written to the
DOM.

Most are **auto-applied** by their component — you'd only name one explicitly to
attach it to a *different* element (e.g. `char-sheet-value--multiline` on a
display value, or `char-sheet-field` around your own control). The ones you
actually reach for while authoring are marked **author knob**.

### Root

| Class | Applied to | Notes |
|---|---|---|
| `char-sheet` | the renderer's outer `<div>` | Sets `--char-sheet-label-col` (default `11rem`), flex column, `gap: 1rem`, baseline `z-index: 1`. Not author-usable. |

### Section / group / label

| Class | Applied to | Notes |
|---|---|---|
| `char-sheet-section` | `section` (auto) | Border, padding, `gap: 0.75rem`, flex column. |
| `char-sheet-section--row` | `section` — **author knob** | Switches the section to a row (`align-items: flex-start`). |
| `char-sheet-group` | `group` (auto) | Inline-flex column, `align-items: flex-start`, `gap: 0.35rem`. |
| `char-sheet-group--inline` | `group` — **author knob** | Switches the group to a row: label + control on one line, label pinned to `--char-sheet-label-col`. |
| `char-sheet-label` | `label` (auto) | `font-weight: 600`, small font. |
| `char-sheet-field` | wrapper around label-less controls — `checkbox`, computed `text` (auto); **author knob** if you wrap your own | Inline-flex, `gap: 0.35rem`. |

### Controls

| Class | Applied to | Notes |
|---|---|---|
| `char-sheet-select` | `select` (auto) | `max-width: 100%`; the dropdown itself is styled globally. |
| `char-sheet-textarea` | `textarea` (auto) | Full width, `resize: vertical`, inherits font. |
| `char-sheet-textarea--richtext` | `richtext` `textarea` edit-mode wrapper (auto) | Full width; the shared `Editor` supplies its own chrome. |
| `char-sheet-value--multiline` | display-mode `textarea` value (auto); **author knob** elsewhere | `white-space: pre-wrap` so newlines survive in display mode. |
| `char-sheet-value--richtext` | `richtext` `textarea` display-mode wrapper (auto) | Full width; wraps the formatted HTML rendered from the stored Tiptap document. |
| `char-sheet-text-value` | computed `text` result `<span>` (auto) | Muted colour, `tabular-nums`. |

### Collapsible

| Class | Applied to | Notes |
|---|---|---|
| `char-sheet-collapsible` | `collapsible` region (auto) | Carries `data-open` for the transition. |
| `char-sheet-collapsible-body` | inner body wrapper (auto) | Height animates via the grid-rows `0fr`/`1fr` trick. |
| `char-sheet-collapsible-body-inner` | innermost clip wrapper (auto) | `overflow: hidden`, `min-height: 0`. |
| `char-sheet-collapsible-toggle` | `collapsible-toggle` (auto) | Renders as a link (orange, underline on hover). |

### Button

| Class | Applied to | Notes |
|---|---|---|
| `char-sheet-button` | `button` (auto) | Generic hook only — inherits font, `cursor: pointer`. A clock / track look is composed per-button from `styles` + `style_when`, not from a class. |

### Repeater

| Class | Applied to | Notes |
|---|---|---|
| `char-sheet-repeater` | repeater container (auto) | Flex column, `gap: 0.5rem`. |
| `char-sheet-repeater--grid` | repeater container when `columns` is set (auto) | Switches to CSS grid with those tracks. |
| `char-sheet-repeater-header` | header region (auto) | Flex row, space-between. |
| `char-sheet-repeater-header--grid` | header region in grid mode (auto) | Subgrid of the repeater's tracks. |
| `char-sheet-repeater-header-cell` | each header cell (auto) | `font-weight: 600`, small font. |
| `char-sheet-repeater-rows` | rows wrapper (auto) | Flex column, `gap: 0.5rem`. |
| `char-sheet-repeater-rows--grid` | rows wrapper in grid mode (auto) | `display: contents` so each row is a direct grid item. |
| `char-sheet-repeater-row` | each row (auto) | Flex, `gap: 0.75rem`. |
| `char-sheet-repeater-row--stack` | each row when `row_layout: "stack"` (auto) | Column, `align-items: flex-start`. |
| `char-sheet-repeater-row--row` | each row when `row_layout: "row"` (auto) | Row, `align-items: flex-end`, wraps. |
| `char-sheet-repeater-row--grid` | each row in grid mode (auto) | Subgrid of the repeater's tracks. |
| `char-sheet-repeater-add-cell` | inline add-control wrapper (auto) | Keeps a `row-end` add control aligned to the inputs. |
| `char-sheet-repeater-add-wrap` | standalone add-control wrapper (auto) | Used for `top` / `bottom` placement. |
| `char-sheet-repeater-add` | the add control — auto-rendered, or a template `button` with `on_click: { "row": "add" }` | Link styling (orange). |
| `char-sheet-repeater-remove` | the remove control — a template `button` with `on_click: { "row": "remove" }` | Link styling (red, small). |

### Grid

| Class | Applied to | Notes |
|---|---|---|
| `char-sheet-grid` | grid container (auto) | CSS grid; default tracks `var(--char-sheet-label-col) 1fr` unless `columns` overrides. |
| `char-sheet-grid-header` | header row (auto) | Subgrid, `font-weight: 600`, small font. |
| `char-sheet-grid-header-cell` | each header cell (auto) | `text-align: center`; auto-flows from column 1 unless the cell carries `col`. |
| `char-sheet-grid-row` | each data row (auto) | Subgrid; row-cell inputs/checkboxes are centred and fill their track. |
| `char-sheet-grid-row-label` | the synthesised first cell in the compact form (auto) | `font-weight: 600`, small font. |

### List / loop

| Class | Applied to | Notes |
|---|---|---|
| `char-sheet-list` | `list` (auto) | Small vertical margin, `padding-left: 1.5rem`. |
| `char-sheet-loop-item` | each `loop` iteration **not** inside a `list` (auto) | `display: block` so iterations stack. Inside a `list` each iteration is an `<li>` and this is not applied. |

### Display-mode value hooks

| Class | Applied to | Notes |
|---|---|---|
| `char-sheet-value` | the `<span>` a control renders in display mode (auto) | No rules of its own in the stylesheet today — a stable hook for display-mode styling. |

### From outside `char-sheet.css`

| Class | Notes |
|---|---|
| `headerbar` | Site-wide orange-ribbon heading style. Opt in via `"headerbar": true` on a `header` (which adds the class), or name it directly in `class`. |
