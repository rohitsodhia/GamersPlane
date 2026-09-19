import type { JSONContent } from "@tiptap/core";
import clsx from "clsx";
import type { CSSProperties } from "react";
import Editor, { emptyContent } from "#/components/Editor";
import { TiptapContent } from "#/components/TiptapContent";
import { useControlBinding } from "./sheet-values";

interface TextareaProps {
	name: string;
	/** Visible row count; forwarded to the `<textarea>`'s `rows`. */
	rows?: number;
	/** Forwarded to the `<textarea>`'s `maxLength`. */
	maxlength?: number;
	default?: string;
	/**
	 * When true, the edit control is the full rich-text `Editor` (Tiptap) instead
	 * of a plain `<textarea>`, and the value is stored as a Tiptap JSON document
	 * rather than a string. `rows` / `maxlength` / `default` are ignored in this
	 * mode; display mode renders the document as formatted HTML.
	 */
	richtext?: boolean;
	className?: string;
	style?: CSSProperties;
}

/**
 * A multi-line text field — just the control. Any label is a sibling `label`
 * element in the enclosing `group`, which wires the two together (see `Group`).
 *
 * The value is bound to the sheet value store by `name`, scoped to the field's
 * position in the tree (see `sheet-values`). In display mode it renders the
 * stored text with newlines preserved instead of a textarea. With `richtext` it
 * swaps the plain textarea for the shared rich-text `Editor` (see `RichTextarea`).
 */
export function Textarea(props: TextareaProps) {
	return props.richtext ? <RichTextarea {...props} /> : <PlainTextarea {...props} />;
}

function PlainTextarea({
	name,
	rows,
	maxlength,
	default: defaultValue,
	className,
	style,
}: TextareaProps) {
	const { domId, mode, ariaLabelledBy, value, setValue } = useControlBinding<
		string | undefined
	>(name, defaultValue);

	return mode === "display" ? (
		<span
			id={domId}
			className={clsx("char-sheet-value", "char-sheet-value--multiline", className)}
			style={style}
		>
			{value ?? ""}
		</span>
	) : (
		<textarea
			id={domId}
			name={name}
			className={clsx("char-sheet-textarea", className)}
			style={style}
			rows={rows}
			maxLength={maxlength}
			value={value ?? ""}
			onChange={(e) => setValue(e.target.value)}
			aria-labelledby={ariaLabelledBy}
		/>
	);
}

function RichTextarea({ name, className, style }: TextareaProps) {
	const { domId, mode, ariaLabelledBy, value, setValue } = useControlBinding<
		JSONContent | undefined
	>(name);

	return mode === "display" ? (
		<div
			id={domId}
			className={clsx("char-sheet-value", "char-sheet-value--richtext", className)}
			style={style}
		>
			<TiptapContent content={value ?? emptyContent} />
		</div>
	) : (
		<div className={clsx("char-sheet-textarea--richtext", className)} style={style}>
			<Editor
				id={domId}
				value={value}
				onChange={setValue}
				ariaLabelledBy={ariaLabelledBy}
			/>
		</div>
	);
}
