// Types for the character-sheet element tree.
//
// The sheet is stored as JSON (see `-test-design.tsx` for a mock). Each node has
// a `type` discriminator; the renderer maps that to a component. Container nodes
// carry their children in `content`; the renderer walks that recursively and
// hands the result to the component as `children`.

import type { Expr } from "./formula";

/** How a repeater arranges the fields inside a single row. */
export type RowLayout = "stack" | "row";

/**
 * Where a repeater's "add" control sits when the row template does NOT place its
 * own add button (`on_click: { "row": "add" }`, which always wins over this).
 * - "top" / "bottom": its own line, before / after the rows
 * - "header": inside the repeater's header region (needs `header` content)
 * - "row-end": trailing the last row's fields, aligned to the row
 */
export type AddButtonPos = "top" | "bottom" | "header" | "row-end";

/**
 * CSS properties an element's `styles` may set, authored kebab-case (matching
 * the property name) so the JSON reads like CSS. This is a real allowlist, not
 * "any string reaches the DOM" — see `style-allowlist.ts` for the per-property
 * value rules and how each maps to a real inline style.
 *
 * `z-index` is deliberately absent: it's not author-settable. Every sheet
 * element sits at a baseline `z-index: 1` (see `char-sheet.css`); setting
 * `position: "absolute"` here automatically stamps `z-index: 5`, which is
 * enough for the one supported use (fields overlaid on a `background-image`)
 * without opening up manual stacking-order fights between elements.
 */
export type StyleProp =
	| "position"
	| "left"
	| "right"
	| "top"
	| "bottom"
	| "width"
	| "height"
	| "padding"
	| "margin"
	| "background-color"
	| "background-image"
	| "background-size"
	| "background-position"
	| "background-repeat"
	| "border-width"
	| "border-style"
	| "border-color"
	| "border-radius"
	| "color";

/**
 * A named, reusable set of `styles`. Same allowlist and validation as an
 * element's own `styles` — a bundle is *not* arbitrary CSS and defines no real
 * CSS class, selector, pseudo-class, or media query. See `SheetSchema.classes`.
 */
export type StyleBundle = Partial<Record<StyleProp, string>>;

/**
 * One conditional-style rule (an entry of `style_when`): while `when` — a
 * formula (see `formula.ts`) evaluated against the current value scope — is
 * truthy, `styles` is merged onto the element. Same `StyleProp` allowlist as a
 * static `styles`.
 */
export interface StyleWhen {
	when: Expr;
	styles: StyleBundle;
}

/** Keys every element may carry, regardless of `type`. */
export interface BaseElement {
	/**
	 * Stable, builder-generated id. Used as the React key and (later) as the
	 * handle for builder operations. Optional here so hand-written mocks work;
	 * the renderer falls back to the tree path for keys.
	 */
	id?: string;
	/**
	 * Author-supplied CSS classes (authored as `class`, not `className`, so the
	 * JSON reads like HTML). The renderer forwards it to the component as
	 * `className`. MUST be validated against the `char-sheet-` allowlist in the
	 * parse layer before it reaches here — the renderer trusts it.
	 */
	class?: string;
	/**
	 * Inline CSS overrides. Restricted to `StyleProp` — like `class`, this is
	 * user-authored content reaching the DOM directly, so an unlisted property or
	 * a value that fails its rule is dropped (DEV-warned), never forwarded. See
	 * `style-allowlist.ts`. A `class` token naming a `SheetSchema.classes` bundle
	 * seeds the same set of properties; anything here wins over a bundle
	 * per-property.
	 */
	styles?: StyleBundle;
	/**
	 * 1-based grid column. Only meaningful for an element sitting in a `grid`'s
	 * header (the compact form's `header` array, or a `grid_header`'s `content`):
	 * it pins that header cell over the given column (e.g. "Save Prof?" over the
	 * checkbox column). Read generically off any header child; ignored elsewhere.
	 */
	col?: number;
	/**
	 * Conditional classes: each key is a class token (space-separated tokens
	 * allowed) added to the element only while its value — a formula (see
	 * `formula.ts`) evaluated against the current value scope — is truthy.
	 * Re-evaluated reactively. For value-driven visual state: a checkbox row
	 * greying out, a "filled" marker, a negative modifier turning red.
	 */
	class_when?: Record<string, Expr>;
	/**
	 * Conditional inline styles: each entry's `styles` bundle is merged onto the
	 * element while its `when` formula is truthy — after the static `styles`,
	 * later entries winning per-property. Re-evaluated reactively.
	 */
	style_when?: StyleWhen[];
}

export interface SectionElement extends BaseElement {
	type: "section";
	content: SheetElement[];
}

/**
 * A generic grouping container. This is where label wiring lives now that it is
 * off the input itself: a `group` mints one DOM id, the bound control inside it
 * claims that id (automatically when it is the only one, or the one flagged
 * `attach_label` when there are several), and every `label` child points its
 * `htmlFor` at it. Layout — stacked, inline, gapped — is a `class` on the group
 * (`char-sheet-group--inline`, …), not an enum.
 */
export interface GroupElement extends BaseElement {
	type: "group";
	content: SheetElement[];
}

/**
 * A `<label>`. Only meaningful inside a `group`: it wires its `htmlFor` to that
 * group's bound control. Carries no value.
 */
export interface LabelElement extends BaseElement {
	type: "label";
	text: string;
}

export interface InputElement extends BaseElement {
	type: "input";
	/** Form-field name; the key this field's value lives under in sheet state. */
	name: string;
	/** Forwarded to the `<input>`'s `maxLength` (e.g. a 2-char ability score). */
	maxlength?: number;
	/**
	 * Seed value used while nothing is stored (and written into the value
	 * document on first mount, in edit mode). Coerced to a string.
	 */
	default?: string | number;
	/**
	 * When the enclosing `group` holds more than one bound control, marks this
	 * one as the target of the group's `label`(s). Ignored when it is the only
	 * bound control (that case wires automatically).
	 */
	attach_label?: boolean;
}

/**
 * A multi-line text field. Label wiring is the same as `input`: no label of its
 * own — a sibling `label` in the enclosing `group` binds to it. Value doc:
 * `name -> "<text>"`.
 */
export interface TextareaElement extends BaseElement {
	type: "textarea";
	/** Form-field name; the key this field's value lives under in sheet state. */
	name: string;
	/** Visible row count; forwarded to the `<textarea>`'s `rows`. */
	rows?: number;
	/** Forwarded to the `<textarea>`'s `maxLength`. */
	maxlength?: number;
	/**
	 * Seed value used while nothing is stored (and written into the value
	 * document on first mount, in edit mode).
	 */
	default?: string;
	/**
	 * When the enclosing `group` holds more than one bound control, marks this
	 * one as the target of the group's `label`(s). Ignored when it is the only
	 * bound control (that case wires automatically).
	 */
	attach_label?: boolean;
}

export interface RepeaterElement extends BaseElement {
	type: "repeater";
	/**
	 * Form-field name; the key this repeater's row data lives under. Each row
	 * collects into a record keyed by its child elements' own `name`s, so the
	 * repeater's value is an array of those records.
	 */
	name: string;
	/**
	 * The row template: rendered once per row. Drop a `button` with an
	 * `on_click` of `{ "row": "add" }` / `{ "row": "remove" }` anywhere inside it
	 * to place the add / remove controls precisely (see `RepeaterRowAction`); the
	 * repeater still owns them (positioning, `min`/`max` gating) — the button only
	 * marks the spot.
	 */
	content: SheetElement[];
	/**
	 * Rendered once, above the rows: column headers (usually literal `text`).
	 * Never a real `label` element — a header describes a whole column across
	 * every row, and `htmlFor`/`group` can only ever wire to one control, so
	 * associating it with a control is done via `aria-labelledby` (see
	 * `Repeater`'s header/row id matching), not label-for-control wiring. The
	 * row template itself should carry no `label`s when `header` is set — the
	 * header is now the only place column labels are authored, never inferred
	 * from a row's own fields.
	 */
	header?: SheetElement[];
	/** Field arrangement within a row. Default "stack". */
	row_layout?: RowLayout;
	/**
	 * Column tracks, one entry per track (one whole track token each — not
	 * whitespace-split), one per header cell plus one for every non-header cell a
	 * row can render (`collapsible`, markers, etc., in template order) — same
	 * idea as `grid`'s `columns`. Each entry is validated against a closed
	 * vocabulary (length · `<n>fr` · `auto`/`min-content`/`max-content` ·
	 * `var(--char-sheet-*)` · `minmax(…)` · `repeat(…)`; see `validateColumns`);
	 * a bad entry is dropped with a DEV warning. Only meaningful with
	 * `row_layout: "row"`. When any entry survives, `header` and every row lay
	 * out as CSS-grid subgrids of these tracks (see `Grid`) instead of flexing,
	 * so header text actually sits over its column's inputs. Omit to keep the
	 * plain flex row layout (fine when there's no `header` to line up against).
	 */
	columns?: string[];
	/** Extra allowlisted class applied to each row wrapper. */
	row_class?: string;
	/** Text for the auto-rendered add control. Default "Add". */
	add_label?: string;
	/** Extra allowlisted class for the add control. */
	add_class?: string;
	/**
	 * Placement of the auto-rendered add control. Ignored when the template
	 * places its own add button (`on_click: { "row": "add" }`). Default "bottom".
	 */
	add_button_pos?: AddButtonPos;
	/** Minimum row count; the remove control is hidden at this floor. Default 0. */
	min?: number;
	/** Maximum row count; the add control is hidden at this ceiling. */
	max?: number;
}

/** How a computed `text` value is rendered. `"number"` is the default. */
export type ComputedFormat = "signed" | "number" | "text";

/**
 * Text the user never types. Two mutually exclusive forms, discriminated by
 * `formula`:
 *  - **literal** — `text` is rendered as-is: a column header inside a `grid`
 *    header, a note between fields, a row label. Carries no value, touches no
 *    store.
 *  - **computed** — `formula` (an AST, see `formula.ts`) is evaluated against
 *    the current value scope, recomputed whenever a referenced field changes,
 *    and the result is written back to the store under `name` so other formulas
 *    (and the saved character) can read it. `format` shapes the rendered result.
 *
 * `name` and `format` are only meaningful in the computed form; `name` is
 * required there (the write-back key). The validation layer enforces the
 * `text` xor `formula` / `name` iff `formula` rules — the renderer trusts them.
 */
export interface TextElement extends BaseElement {
	type: "text";
	/** Literal content. Mutually exclusive with `formula`. */
	text?: string;
	/** Expression tree evaluated against the current value scope. Mutually exclusive with `text`. */
	formula?: Expr;
	/** Write-back key for a computed result. Required with `formula`, unused with `text`. */
	name?: string;
	/**
	 * Presentation of a computed result. `"signed"` prefixes non-negatives with
	 * `+`. Ignored for a literal.
	 */
	format?: ComputedFormat;
}

/**
 * CSS `list-style-type` values a `list` may set via `marker`. Closed set;
 * `"none"` is for a list whose items draw their own bullet / number.
 */
export type ListMarker =
	| "disc"
	| "circle"
	| "square"
	| "decimal"
	| "decimal-leading-zero"
	| "lower-alpha"
	| "upper-alpha"
	| "lower-roman"
	| "upper-roman"
	| "none";

/**
 * An `<ol>` / `<ul>`. `variant` picks the tag (kept off `type`, which is the
 * discriminator). Typical use is a single `loop` child, which emits one `<li>`
 * per iteration; the loop's `class` / `class_when` / `styles` land on each `<li>`.
 * Transparent for value binding, like `section`.
 */
export interface ListElement extends BaseElement {
	type: "list";
	/** `"ordered"` → `<ol>`, `"unordered"` → `<ul>`. */
	variant: "ordered" | "unordered";
	/** Overrides the CSS `list-style-type`. Omit for the tag's default. */
	marker?: ListMarker;
	content: SheetElement[];
}

/**
 * Repeats its `content` template. Presentational only — unlike `repeater`
 * (runtime add / remove) and `grid` (per-row value scope), a `loop` adds NO
 * value scope: body fields share the enclosing scope, so a bound / computed
 * field inside a loop writes one shared key every iteration (use `grid` when
 * each iteration needs its own values).
 *
 * Two forms, discriminated by `items`:
 *  - **items** — one iteration per author-fixed entry; the entry's own keys
 *    resolve as refs in the body (e.g. `{ ref: "label" }`).
 *  - **count** — a literal integer, or a formula over the enclosing scope
 *    (e.g. death-spiral crosses counted up to a stored value). Floored and
 *    clamped to `MAX_LOOP_ITERATIONS`.
 *
 * The body can read `$index` (0-based iteration number) as a ref. Setting both
 * `items` and `count` ignores `count` (DEV warn); neither renders nothing.
 */
export interface LoopElement extends BaseElement {
	type: "loop";
	/** Explicit form: one iteration per entry. Excludes `count`. */
	items?: Record<string, string | number | boolean | null>[];
	/** Compact form: iteration count, literal or a formula. Excludes `items`. */
	count?: number | Expr;
	content: SheetElement[];
}

/**
 * On click, write the scalar that `to` evaluates to into the field named `set`,
 * in the button's own value scope. `to` is a formula (see `formula.ts`)
 * evaluated at click time — so it can read `$index` (inside a `loop`), the
 * target field's current value, and sibling fields. It is data, not code: no
 * statement list, no second target, no JS.
 */
export interface SetValueAction {
	/** `name` of the sibling scalar field to write. */
	set: string;
	/** Formula for the value to write, evaluated when the button is clicked. */
	to: Expr;
}

/**
 * On click, add or remove a row of the enclosing `repeater`. Valid only inside a
 * repeater's row template — it binds to that repeater by position, no `name`
 * reference (the old `repeater_add` / `repeater_remove` markers, re-spelled as a
 * `button` so they pick up `class_when` / `style_when` / display-inertness). The
 * repeater still owns the control: an `"add"` button renders once (on the last
 * row) and is hidden at `max`; a `"remove"` button renders on every row and is
 * hidden at `min`.
 */
export interface RepeaterRowAction {
	row: "add" | "remove";
}

/** One declarative click action for a `button`. Data, never code. */
export type ClickAction = SetValueAction | RepeaterRowAction;

/**
 * A button with one declarative `on_click`:
 *  - `{ set, to }` — write a sibling scalar in the current scope. The schema's
 *    only "an element changes another element's value" interaction, and the
 *    basis of clocks / tracks: put a `button` in a `loop` with an `on_click.to`
 *    of `$index + 1`, and clicking segment N sets a shared counter to N while
 *    the segments render "filled" via `class_when` / `style_when` comparing
 *    `$index` to that counter. A `clock` is this composition, not its own type.
 *  - `{ row: "add" | "remove" }` — add / remove a row of the enclosing
 *    `repeater` (see `RepeaterRowAction`).
 *
 * Carries no value of its own. In display mode it renders inert.
 */
export interface ButtonElement extends BaseElement {
	type: "button";
	/** Button text. */
	label: string;
	on_click: ClickAction;
}

/**
 * A section heading — renders an `<h2>`. Carries no value and reads nothing
 * from the store.
 */
export interface HeaderElement extends BaseElement {
	type: "header";
	text: string;
	/** Adds the site-wide `headerbar` class (the orange ribbon heading style). */
	headerbar?: boolean;
}

export interface CheckboxElement extends BaseElement {
	type: "checkbox";
	/** Form-field name; the key this checkbox's boolean lives under. */
	name: string;
	/**
	 * Seed value used while nothing is stored (and written into the value
	 * document on first mount, in edit mode).
	 */
	default?: boolean;
	/**
	 * When the enclosing `group` holds more than one bound control, marks this
	 * one as the target of the group's `label`(s). Ignored when it is the only
	 * bound control (that case wires automatically).
	 */
	attach_label?: boolean;
}

/**
 * One choice in a `select`. A bare string is shorthand for `{ value, label }`
 * with the two equal; the pair form is for when the stored value differs from
 * the visible text (a code, an id, an abbreviation).
 */
export type SelectOption = string | { value: string; label: string };

/**
 * A single-choice dropdown. Built on the shared React-Aria `Select`. Label
 * wiring is the same as `input`: no label of its own — a sibling `label` in the
 * enclosing `group` binds to it. A blank choice is offered unless `default`
 * picks one. Value doc: `name -> "<chosen value>"`.
 */
export interface SelectElement extends BaseElement {
	type: "select";
	/** Form-field name; the key this field's value lives under in sheet state. */
	name: string;
	/** The choices, in menu order. */
	values: SelectOption[];
	/**
	 * Seed value used while nothing is stored (and written into the value
	 * document on first mount, in edit mode). Must match one option's `value`;
	 * when set, no blank choice is offered.
	 */
	default?: string;
	/**
	 * When the enclosing `group` holds more than one bound control, marks this
	 * one as the target of the group's `label`(s). Ignored when it is the only
	 * bound control (that case wires automatically).
	 */
	attach_label?: boolean;
}

/**
 * A region that collapses/expands. Has NO trigger of its own — a
 * `collapsible-toggle` elsewhere in the same scope (a sibling, or another cell
 * in the same repeater / grid row) drives it by `name`. The trigger is kept
 * outside so it stays visible while the region is closed. Carries no value.
 */
export interface CollapsibleElement extends BaseElement {
	type: "collapsible";
	/** Scope-local id a `collapsible-toggle` points its `target` at. Required. */
	name: string;
	/** Start collapsed. Default false (open). */
	collapsed?: boolean;
	content: SheetElement[];
}

/**
 * The external trigger for a `collapsible`: a text button (link styling by
 * default) that toggles the `collapsible` whose `name` equals `target` in the
 * nearest shared scope. Carries no value.
 */
export interface CollapsibleToggleElement extends BaseElement {
	type: "collapsible-toggle";
	/** `name` of the `collapsible` this toggles. */
	target: string;
	/** Button text. */
	label: string;
}

/** One fixed row of a `grid`'s compact form: a sub-scope key plus its label. */
export interface GridItem {
	/** Sub-scope key this row's values nest under (`stats.str.*`). */
	key: string;
	/** Row label, emitted as the row's first cell. */
	label: string;
}

/**
 * A fixed-layout table: CSS-grid column tracks with each row a subgrid so cells
 * line up. Unlike a `repeater`, a grid NEVER changes its row count — "repeat"
 * here is author-time expansion of a template, not a runtime control.
 *
 * Two authoring forms, discriminated by `items`:
 *  - **compact** — `items` + `row` (a single template; child `name`s are
 *    row-relative). Each item becomes a row whose first cell is a literal `text`
 *    of `item.label` and whose remaining cells are `row`, scoped under
 *    `name[item.key]`. `header` is rendered once on the tracks.
 *  - **explicit** — `content`: an optional leading `grid_header` then one
 *    `grid_row` per row (each carrying its own `key`). The row label is just an
 *    ordinary first cell the author writes.
 *
 * Setting both `items` and `content` is a validation error. The value doc is
 * `name: { <key>: { <field>: value, … }, … }`.
 */
export interface GridElement extends BaseElement {
	type: "grid";
	/** Form-field name; the key this grid's value object lives under. */
	name: string;
	/** Compact form: the fixed rows, in render order. Excludes `content`. */
	items?: GridItem[];
	/** Compact form: the row template, rendered once per item. Excludes `content`. */
	row?: SheetElement[];
	/**
	 * Compact form: rendered once above the rows, on the same tracks. A child may
	 * carry `col` to pin it over a specific column. (Explicit form uses a
	 * `grid_header` inside `content` instead.)
	 */
	header?: SheetElement[];
	/** Explicit form: an optional `grid_header` then the `grid_row`s. Excludes `items`/`row`. */
	content?: (GridHeaderElement | GridRowElement)[];
	/**
	 * Grid track sizes, one entry per column (one whole track token each — not
	 * whitespace-split), e.g. `["var(--char-sheet-label-col)", "3rem",
	 * "max-content"]`. Each entry is validated against a closed vocabulary
	 * (length · `<n>fr` · `auto`/`min-content`/`max-content` ·
	 * `var(--char-sheet-*)` · `minmax(…)` · `repeat(…)`; see `validateColumns`);
	 * a bad entry is dropped with a DEV warning. Omit to fall back to the
	 * `.char-sheet-grid` default tracks, or (if the vocab ever grows one from real
	 * demand) a `char-sheet-grid--*` helper class; a valid `columns` wins over
	 * either, applied as inline style.
	 */
	columns?: string[];
	/** Extra allowlisted class applied to every row wrapper. */
	row_class?: string;
}

/**
 * One row of a `grid`'s explicit `content`. `key` is the sub-scope coordinate
 * (`stats.str.*`); `content` is the row's cells in column order — the first is
 * usually a `label` / `text` acting as the row header. Consumed by the
 * grid renderer; meaningless outside a `grid`.
 */
export interface GridRowElement extends BaseElement {
	type: "grid_row";
	/** Sub-scope key this row's fields nest under. */
	key: string;
	content: SheetElement[];
}

/**
 * The optional header row of a `grid`'s explicit `content`, rendered once on the
 * grid's tracks. Each child cell may carry `col` to pin it over a specific
 * column. Consumed by the grid renderer; meaningless outside a `grid`.
 */
export interface GridHeaderElement extends BaseElement {
	type: "grid_header";
	content: SheetElement[];
}

export type SheetElement =
	| SectionElement
	| GroupElement
	| LabelElement
	| InputElement
	| TextareaElement
	| RepeaterElement
	| TextElement
	| ListElement
	| LoopElement
	| ButtonElement
	| HeaderElement
	| CheckboxElement
	| SelectElement
	| CollapsibleElement
	| CollapsibleToggleElement
	| GridElement
	| GridRowElement
	| GridHeaderElement;

export interface SheetSchema {
	version: number;
	/**
	 * Named, reusable `styles` bundles, keyed by name. An element references one
	 * (or several, space-separated) by putting the name in its `class` alongside
	 * any `char-sheet-*` utility classes; the renderer expands the bundle's
	 * properties inline (see `commonDomProps`). Later class tokens win over
	 * earlier ones, and the element's own `styles` wins over all of them, all
	 * per-property. Deliberately narrow: a bundle is the same `StyleBundle`
	 * allowlist as `styles`, produces inline style only, and can't carry a
	 * selector, pseudo-class, or media query — broaden the allowlist first if
	 * that's ever needed.
	 */
	classes?: Record<string, StyleBundle>;
	elements: SheetElement[];
}
