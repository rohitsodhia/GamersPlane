import type { CSSProperties } from "react";
import { Computed } from "./Computed";
import type { Expr } from "./formula";
import { StaticText } from "./StaticText";
import type { ComputedFormat } from "./types";

interface TextProps {
	text?: string;
	formula?: Expr;
	name?: string;
	format?: ComputedFormat;
	className?: string;
	style?: CSSProperties;
}

/**
 * Text the user never types — the renderer entry for the `text` element. Two
 * forms, discriminated by `formula`:
 *  - literal: `text` rendered as-is (grid header, note, row label); no store contact.
 *  - computed: `formula` evaluated against the value scope, recomputed on any
 *    referenced-field change, result written back under `name`.
 *
 * The two are separate impls (`StaticText` / `Computed`) behind this dispatcher
 * so the computed path — and the reactivity engine that will rewrite it — stays
 * isolated from the trivial literal one.
 */
export function Text({ text, formula, name, format, className, style }: TextProps) {
	if (formula != null) {
		if (import.meta.env.DEV && !name) {
			console.warn(
				'[sheet] text: "formula" is set without "name"; the computed result is not written back',
			);
		}
		return (
			<Computed
				name={name ?? ""}
				formula={formula}
				format={format}
				className={className}
				style={style}
			/>
		);
	}
	return <StaticText text={text ?? ""} className={className} style={style} />;
}
