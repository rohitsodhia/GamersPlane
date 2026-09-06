import { describe, expect, it } from "vitest";
import {
	isRepeaterRowAction,
	type RepeaterRowActions,
	shouldRenderRowAction,
	templatePlacesAddButton,
} from "./repeater-context";
import type { SheetElement } from "./types";

describe("isRepeaterRowAction", () => {
	it("is true for a row action, false for a set-value action", () => {
		expect(isRepeaterRowAction({ row: "add" })).toBe(true);
		expect(isRepeaterRowAction({ row: "remove" })).toBe(true);
		expect(isRepeaterRowAction({ set: "harm", to: 0 })).toBe(false);
	});
});

describe("shouldRenderRowAction", () => {
	const actions = (over: Partial<RepeaterRowActions>): RepeaterRowActions => ({
		addRow: () => {},
		removeRow: () => {},
		canAdd: true,
		canRemove: true,
		isLastRow: true,
		...over,
	});

	it("renders the add button only on the last row", () => {
		expect(shouldRenderRowAction("add", actions({ isLastRow: true }))).toBe(true);
		expect(shouldRenderRowAction("add", actions({ isLastRow: false }))).toBe(false);
	});

	it("hides the add button at max even on the last row", () => {
		expect(
			shouldRenderRowAction("add", actions({ isLastRow: true, canAdd: false })),
		).toBe(false);
	});

	it("renders the remove button on any row unless at min", () => {
		expect(shouldRenderRowAction("remove", actions({ isLastRow: false }))).toBe(true);
		expect(shouldRenderRowAction("remove", actions({ canRemove: false }))).toBe(false);
	});
});

describe("templatePlacesAddButton", () => {
	const addButton: SheetElement = {
		type: "button",
		label: "Add",
		on_click: { row: "add" },
	};

	it("finds an add button at the top level of the template", () => {
		expect(templatePlacesAddButton([{ type: "input", name: "x" }, addButton])).toBe(
			true,
		);
	});

	it("finds an add button nested inside a container's content", () => {
		const template: SheetElement[] = [
			{ type: "group", content: [{ type: "input", name: "x" }, addButton] },
		];
		expect(templatePlacesAddButton(template)).toBe(true);
	});

	it("ignores a remove button and a set-value button", () => {
		const template: SheetElement[] = [
			{ type: "button", label: "×", on_click: { row: "remove" } },
			{ type: "button", label: "Reset", on_click: { set: "harm", to: 0 } },
		];
		expect(templatePlacesAddButton(template)).toBe(false);
	});

	it("is false for a template with no button", () => {
		expect(
			templatePlacesAddButton([
				{ type: "input", name: "x" },
				{ type: "group", content: [{ type: "input", name: "y" }] },
			]),
		).toBe(false);
	});
});
