import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { FilterableListBox, selectionFromKeys } from "./FilterableListBox";

const ITEMS = [
	{ id: "dnd", name: "Dungeons & Dragons" },
	{ id: "pf", name: "Pathfinder" },
	{ id: "coc", name: "Call of Cthulhu" },
];

const baseProps = {
	label: "Systems",
	placeholder: "Filter systems...",
	items: ITEMS,
	getId: (item: (typeof ITEMS)[number]) => item.id,
	getLabel: (item: (typeof ITEMS)[number]) => item.name,
};

describe("selectionFromKeys", () => {
	it("converts a key set to string ids", () => {
		expect(selectionFromKeys(new Set(["dnd", "pf"]), ["dnd", "pf", "coc"])).toEqual([
			"dnd",
			"pf",
		]);
	});

	it("expands 'all' to every item id", () => {
		expect(selectionFromKeys("all", ["dnd", "pf", "coc"])).toEqual([
			"dnd",
			"pf",
			"coc",
		]);
	});
});

describe("FilterableListBox multiple mode", () => {
	it("keeps selections hidden by the filter when toggling a visible row", async () => {
		const onChange = vi.fn();
		render(
			<FilterableListBox
				{...baseProps}
				selectionMode="multiple"
				selectedIds={["dnd"]}
				onChange={onChange}
			/>,
		);

		await userEvent.type(screen.getByPlaceholderText("Filter systems..."), "path");
		// D&D is selected but filtered out of view.
		expect(screen.queryByRole("option", { name: /Dungeons/ })).not.toBeInTheDocument();

		await userEvent.click(screen.getByRole("option", { name: /Pathfinder/ }));
		expect(onChange).toHaveBeenLastCalledWith(["dnd", "pf"]);
	});

	it("keeps hidden selections when deselecting a visible row", async () => {
		const onChange = vi.fn();
		render(
			<FilterableListBox
				{...baseProps}
				selectionMode="multiple"
				selectedIds={["dnd", "pf"]}
				onChange={onChange}
			/>,
		);

		await userEvent.type(screen.getByPlaceholderText("Filter systems..."), "path");
		await userEvent.click(screen.getByRole("option", { name: /Pathfinder/ }));
		expect(onChange).toHaveBeenLastCalledWith(["dnd"]);
	});
});

describe("FilterableListBox", () => {
	it("does not submit an enclosing form when Enter is pressed in the filter", async () => {
		const onSubmit = vi.fn((event: { preventDefault: () => void }) =>
			event.preventDefault(),
		);
		render(
			<form onSubmit={onSubmit}>
				<FilterableListBox {...baseProps} selectedId={null} onChange={vi.fn()} />
				<button type="submit">Save</button>
			</form>,
		);

		await userEvent.type(
			screen.getByPlaceholderText("Filter systems..."),
			"path{Enter}",
		);
		expect(onSubmit).not.toHaveBeenCalled();
	});

	it("still reports a single selection in the default mode", async () => {
		const onChange = vi.fn();
		render(<FilterableListBox {...baseProps} selectedId={null} onChange={onChange} />);

		await userEvent.click(screen.getByRole("option", { name: /Call of Cthulhu/ }));
		expect(onChange).toHaveBeenCalledWith("coc");
	});
});
