import {
	type ComponentType,
	type CSSProperties,
	cloneElement,
	type ReactElement,
} from "react";
import "./char-sheet.css";
import { Button } from "./Button";
import { Checkbox } from "./Checkbox";
import { Collapsible } from "./Collapsible";
import { CollapsibleToggle } from "./CollapsibleToggle";
import { CollapsibleScopeProvider } from "./collapsible-scope";
import { Grid, type GridHeader, type GridRow } from "./Grid";
import { Group } from "./Group";
import { Header } from "./Header";
import { Input } from "./Input";
import { Label } from "./Label";
import { List } from "./List";
import { Loop } from "./Loop";
import { Repeater } from "./Repeater";
import { Section } from "./Section";
import { Select } from "./Select";
import { resolveElementStyles, validateColumns } from "./style-allowlist";
import { Text } from "./Text";
import { Textarea } from "./Textarea";
import type {
	BaseElement,
	GridElement,
	GridRowElement,
	SheetElement,
	SheetSchema,
	StyleBundle,
} from "./types";
import { WhenStyled } from "./when-styling";

/** Schema `classes` map, threaded through `renderNode` so any element can expand a bundle. */
type StyleBundles = Record<string, StyleBundle> | undefined;

// Maps a node's `type` to the component that renders it. Add new element types
// here. Components receive the node's remaining keys as props (with `class`
// forwarded as `className`); container output from `content` arrives as
// `children`.
// biome-ignore lint/suspicious/noExplicitAny: registry is heterogeneous by design
const REGISTRY: Record<string, ComponentType<any>> = {
	section: Section,
	label: Label,
	input: Input,
	textarea: Textarea,
	text: Text,
	list: List,
	header: Header,
	checkbox: Checkbox,
	select: Select,
	button: Button,
	collapsible: Collapsible,
	"collapsible-toggle": CollapsibleToggle,
};

/**
 * Keys the renderer consumes itself and does not forward to components. `col` is
 * layout metadata read by `grid` off its header cells; `attach_label` is read
 * here to wire a `group`'s label. Neither is ever a component prop.
 */
const RESERVED_KEYS = new Set([
	"type",
	"id",
	"content",
	"class",
	"styles",
	"class_when",
	"style_when",
	"col",
	"attach_label",
]);

/**
 * `className` + `style` for a node, shared by the generic `REGISTRY` path and
 * the three manually-wired containers (`Repeater`/`Group`/`Grid`) below, so a
 * new common prop only needs to be taught here once instead of at every call
 * site. `bundles` is the schema's `classes` map (a `class` token naming one
 * expands to inline style); `path` is only for DEV warnings.
 */
function commonDomProps(
	node: BaseElement,
	path: string,
	bundles: StyleBundles,
): { className?: string; style?: CSSProperties } {
	const { className, style } = resolveElementStyles(
		node.class,
		node.styles,
		bundles,
		path,
	);
	const props: { className?: string; style?: CSSProperties } = {};
	if (className != null) props.className = className;
	if (style != null) props.style = style;
	return props;
}

/**
 * Wraps `element` in `<WhenStyled>` when the node carries `class_when` /
 * `style_when`, so its conditions are evaluated reactively against the value
 * scope and the merged `className` / `style` are cloned onto it. `base` is the
 * static `className` / `style` from `commonDomProps` (the conditional set layers
 * on top). A no-op — returns `element` untouched — when neither key is present.
 */
function maybeWrapWhen(
	node: BaseElement,
	context: string,
	base: { className?: string; style?: CSSProperties },
	key: string,
	element: ReactElement,
): ReactElement {
	if (node.class_when == null && node.style_when == null) return element;
	return (
		<WhenStyled
			key={key}
			classWhen={node.class_when}
			styleWhen={node.style_when}
			base={base}
			context={context}
		>
			{(merged) => cloneElement(element, merged)}
		</WhenStyled>
	);
}

/**
 * The bound-control types that can own a `group`'s label id — i.e. that render a
 * real labelable element for a `<label htmlFor>` to point at. A computed `text`
 * is deliberately absent: it's a read-only `<span>`, so a label sitting beside it
 * is a plain literal `text` block, not a semantic `<label>`.
 */
const LABEL_TARGET_TYPES = new Set(["input", "textarea", "select", "checkbox"]);

/**
 * The `name` of the control a `group`'s `label`(s) should wire to: the one
 * flagged `attach_label`, else the sole bound control, else undefined (labels
 * render unassociated).
 */
function groupLabelTarget(content: SheetElement[]): string | undefined {
	const named = content.filter(
		(c): c is SheetElement & { name: string } =>
			typeof (c as { name?: unknown }).name === "string",
	);
	const explicit = named.find(
		(c) => (c as { attach_label?: unknown }).attach_label === true,
	);
	if (explicit) return explicit.name;
	const bound = named.filter((c) => LABEL_TARGET_TYPES.has(c.type));
	return bound.length === 1 ? bound[0].name : undefined;
}

/**
 * Flattens a `grid`'s two authoring forms into one header + row list for `Grid`.
 * Compact (`items` + `row`) synthesises a leading literal `text` label cell per
 * row; explicit (`content`) reads `grid_header` / `grid_row` straight through.
 */
function normalizeGrid(node: GridElement): {
	header?: GridHeader;
	rows: GridRow[];
} {
	if (node.items != null && node.content != null && import.meta.env.DEV) {
		console.warn(
			`[sheet] grid "${node.name}": both "items" and "content" set; ignoring "content"`,
		);
	}

	if (node.items != null) {
		const rowTemplate = node.row ?? [];
		return {
			header:
				node.header != null && node.header.length > 0
					? { cells: node.header }
					: undefined,
			rows: node.items.map((item) => ({
				key: item.key,
				cells: [
					{
						type: "text",
						text: item.label,
						class: "char-sheet-grid-row-label",
					} as SheetElement,
					...rowTemplate,
				],
			})),
		};
	}

	const content = node.content ?? [];
	const headerNode = content.find((c) => c.type === "grid_header");
	const rowNodes = content.filter((c): c is GridRowElement => c.type === "grid_row");
	return {
		header: headerNode ? { cells: headerNode.content } : undefined,
		rows: rowNodes.map((r) => ({
			key: r.key,
			cells: r.content,
			rowClass: r.class,
		})),
	};
}

function renderNode(node: SheetElement, path: string, bundles: StyleBundles) {
	const key = node.id ?? path;
	const dom = commonDomProps(node, path, bundles);

	// The repeater renders its template dynamically (N rows, runtime state) and
	// owns its own add/remove controls, so it can't go through the static
	// REGISTRY path. This is the one sanctioned place a container gets handed a
	// render callback instead of pre-rendered `children`; recursion and keying
	// still live here.
	if (node.type === "repeater") {
		return maybeWrapWhen(
			node,
			path,
			dom,
			key,
			<Repeater
				key={key}
				name={node.name}
				template={node.content}
				header={node.header}
				rowLayout={node.row_layout}
				gridTemplateColumns={validateColumns(node.columns, `repeater "${node.name}"`)}
				rowClass={node.row_class}
				addLabel={node.add_label}
				addClass={node.add_class}
				addButtonPos={node.add_button_pos}
				min={node.min}
				max={node.max}
				{...dom}
				renderCell={(cell, rowKey, cellIndex) =>
					renderNode(cell, `${path}/row/${rowKey}/${cellIndex}`, bundles)
				}
				renderHeaderCell={(cell, i) => renderNode(cell, `${path}/header/${i}`, bundles)}
			/>,
		);
	}

	// A group provides the DOM id that ties its `label` children to its bound
	// control. The renderer picks which control owns that id (schema knowledge);
	// recursion and keying still live here.
	if (node.type === "group") {
		return maybeWrapWhen(
			node,
			path,
			dom,
			key,
			<Group key={key} {...dom} labelFor={groupLabelTarget(node.content)}>
				{node.content.map((child, i) => renderNode(child, `${path}/${i}`, bundles))}
			</Group>,
		);
	}

	// grid renders a fixed set of author-named rows, each into its own
	// string-keyed sub-scope, on a shared CSS grid. Like the repeater it needs
	// render callbacks rather than pre-rendered children; recursion and keying
	// still live here. Both authoring forms are flattened by `normalizeGrid`.
	if (node.type === "grid") {
		const { header, rows } = normalizeGrid(node);
		return maybeWrapWhen(
			node,
			path,
			dom,
			key,
			<Grid
				key={key}
				name={node.name}
				gridTemplateColumns={validateColumns(node.columns, `grid "${node.name}"`)}
				rowClass={node.row_class}
				{...dom}
				header={header}
				rows={rows}
				renderCell={(cell, rowKey, cellIndex) =>
					renderNode(cell, `${path}/row/${rowKey}/${cellIndex}`, bundles)
				}
				renderHeaderCell={(cell, i) => renderNode(cell, `${path}/header/${i}`, bundles)}
			/>,
		);
	}

	// loop repeats its template per iteration and needs render callbacks +
	// per-iteration `LoopIterationProvider` wrapping, so it can't go through the
	// static REGISTRY path. Its `class` / `styles` / `class_when` / `style_when`
	// apply per iteration (a condition can key off `$index`), so they are handed
	// to `Loop` rather than wrapped here via `maybeWrapWhen`.
	if (node.type === "loop") {
		return (
			<Loop
				key={key}
				items={node.items}
				count={node.count}
				template={node.content}
				itemClassName={dom.className}
				itemStyle={dom.style}
				classWhen={node.class_when}
				styleWhen={node.style_when}
				context={path}
				renderBody={(cell, index, cellIndex) =>
					renderNode(cell, `${path}/${index}/${cellIndex}`, bundles)
				}
			/>
		);
	}

	const Component = REGISTRY[node.type];
	if (!Component) {
		if (import.meta.env.DEV) {
			console.warn(`[sheet] unknown element type "${node.type}" at ${path}`);
		}
		return null;
	}

	const props: Record<string, unknown> = {};
	for (const [k, value] of Object.entries(node)) {
		if (!RESERVED_KEYS.has(k)) props[k] = value;
	}
	Object.assign(props, dom);

	const content = "content" in node ? node.content : undefined;
	const children = Array.isArray(content)
		? content.map((child, i) => renderNode(child, `${path}/${i}`, bundles))
		: undefined;

	return maybeWrapWhen(
		node,
		path,
		dom,
		key,
		<Component key={key} {...props}>
			{children}
		</Component>,
	);
}

/**
 * Renders a parsed character-sheet schema into its component tree. Must be
 * rendered inside a `<SheetValuesProvider>` (see `sheet-values`): element
 * components bind their values through it and read the edit/display mode from it.
 */
export function SheetRenderer({ schema }: { schema: SheetSchema }) {
	return (
		<div className="char-sheet">
			<CollapsibleScopeProvider>
				{schema.elements.map((node, i) => renderNode(node, `${i}`, schema.classes))}
			</CollapsibleScopeProvider>
		</div>
	);
}
