import { indentWithTab } from "@codemirror/commands";
import { json, jsonParseLinter } from "@codemirror/lang-json";
import { HighlightStyle, indentUnit, syntaxHighlighting } from "@codemirror/language";
import { linter, lintGutter } from "@codemirror/lint";
import { Compartment, EditorState } from "@codemirror/state";
import { keymap } from "@codemirror/view";
import { tags } from "@lezer/highlight";
import { basicSetup, EditorView } from "codemirror";
import { useEffect, useRef } from "react";

// `light-dark()` follows the site's `color-scheme`, so the editor tracks the
// theme toggle without being reconfigured.
const highlightStyle = HighlightStyle.define([
	{ tag: tags.propertyName, color: "light-dark(#a11, #f88)" },
	{ tag: tags.string, color: "light-dark(#070, #8c8)" },
	{ tag: tags.number, color: "light-dark(#05a, #7bf)" },
	{ tag: [tags.bool, tags.null], color: "light-dark(#708, #c9f)" },
]);

const theme = EditorView.theme({
	"&": {
		height: "100%",
		backgroundColor: "var(--bg)",
		color: "var(--text)",
	},
	".cm-scroller": {
		fontFamily: "var(--font-mono, ui-monospace, monospace)",
	},
	".cm-content": {
		caretColor: "var(--text)",
	},
	".cm-gutters": {
		backgroundColor: "light-dark(#f3f3f3, #2a2a2a)",
		color: "light-dark(#888, #999)",
		borderRight: "1px solid light-dark(#ddd, #444)",
	},
	".cm-activeLine": {
		backgroundColor: "light-dark(#0000000a, #ffffff0d)",
	},
	".cm-activeLineGutter": {
		backgroundColor: "light-dark(#e6e6e6, #353535)",
	},
});

/**
 * JSON code editor (CodeMirror) with line numbers, highlighting, and a
 * parse-error lint. CodeMirror needs the DOM, so it's built in an effect (SSR
 * renders the empty host) — import this lazily so its bundle only loads when
 * shown.
 */
export default function JsonEditor({
	value,
	onChange,
	readOnly = false,
	initialCursor,
	className,
}: {
	value: string;
	onChange: (value: string) => void;
	readOnly?: boolean;
	// Offset to focus and scroll to when the editor mounts.
	initialCursor?: number;
	className?: string;
}) {
	const hostRef = useRef<HTMLDivElement>(null);
	const viewRef = useRef<EditorView | null>(null);
	const readOnlyCompartment = useRef(new Compartment());
	// The listener is registered once, so read the latest callback through a ref.
	const onChangeRef = useRef(onChange);
	useEffect(() => {
		onChangeRef.current = onChange;
	});

	// biome-ignore lint/correctness/useExhaustiveDependencies: built once; `value` and `readOnly` are synced by the effects below, and `initialCursor` only applies on mount.
	useEffect(() => {
		if (!hostRef.current) return;
		const view = new EditorView({
			parent: hostRef.current,
			state: EditorState.create({
				doc: value,
				extensions: [
					basicSetup,
					keymap.of([indentWithTab]),
					indentUnit.of("    "),
					json(),
					linter(jsonParseLinter()),
					lintGutter(),
					syntaxHighlighting(highlightStyle),
					theme,
					readOnlyCompartment.current.of(EditorState.readOnly.of(readOnly)),
					EditorView.updateListener.of((update) => {
						if (update.docChanged) onChangeRef.current(update.state.doc.toString());
					}),
				],
			}),
		});
		viewRef.current = view;
		if (initialCursor !== undefined) {
			const anchor = Math.min(initialCursor, view.state.doc.length);
			view.dispatch({
				selection: { anchor },
				effects: EditorView.scrollIntoView(anchor, { y: "center" }),
			});
			view.focus();
		}
		return () => {
			view.destroy();
			viewRef.current = null;
		};
	}, []);

	// Push outside changes (e.g. the server's minted ids after a save) into the
	// editor. Typing round-trips through `onChange`, so it already matches.
	useEffect(() => {
		const view = viewRef.current;
		if (!view) return;
		const current = view.state.doc.toString();
		if (value !== current) {
			view.dispatch({ changes: { from: 0, to: current.length, insert: value } });
		}
	}, [value]);

	useEffect(() => {
		viewRef.current?.dispatch({
			effects: readOnlyCompartment.current.reconfigure(
				EditorState.readOnly.of(readOnly),
			),
		});
	}, [readOnly]);

	return <div ref={hostRef} className={className} />;
}
