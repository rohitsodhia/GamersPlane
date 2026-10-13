import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SheetRenderer } from "./SheetRenderer";
import { type LiveSave, type ScopeValues, SheetValuesProvider } from "./sheet-values";
import type { SheetSchema } from "./types";

const schema: SheetSchema = {
	schema_version: 1,
	elements: [
		{ type: "input", id: "hp1", name: "hp", live: true },
		{ type: "input", id: "ac1", name: "ac" },
		{ type: "checkbox", id: "ins1", name: "inspired", live: true },
		{
			type: "grid",
			id: "g1",
			name: "skills",
			items: [{ key: "stealth", id: "r1", label: "Stealth" }],
			row: [{ type: "input", id: "c1", name: "rank", live: true }],
		},
	],
};

const values: ScopeValues = { hp1: "10", ac1: "15" };

function renderSheet({
	onLiveSave,
	canEditLive = true,
}: {
	onLiveSave?: LiveSave;
	canEditLive?: boolean;
}) {
	return render(
		<SheetValuesProvider
			mode="display"
			initialValues={values}
			onLiveSave={onLiveSave}
			canEditLive={canEditLive}
		>
			<SheetRenderer schema={schema} />
		</SheetValuesProvider>,
	);
}

describe("live fields in display mode", () => {
	it("render as controls, while a non-live field stays text", () => {
		renderSheet({ onLiveSave: vi.fn() });

		// Only hp and the grid's rank are live inputs; ac is text.
		expect(screen.getAllByRole("textbox")).toHaveLength(2);
		expect(screen.getByText("15")).toBeInTheDocument();
		expect(screen.getByRole("checkbox")).toBeInTheDocument();
	});

	it.each([
		["no save handler", { canEditLive: true }],
		["a viewer who can't edit", { onLiveSave: vi.fn(), canEditLive: false }],
	])("render as text with %s", (_label, props) => {
		renderSheet(props);

		expect(screen.queryByRole("textbox")).toBeNull();
		expect(screen.queryByRole("checkbox")).toBeNull();
		expect(screen.getByText("10")).toBeInTheDocument();
	});

	it.each([
		["input", "hp1", 0],
		["textarea", "notes1", 2],
	])("save the %s on blur only when it changed", async (_type, id, index) => {
		// Textboxes in document order: hp, the grid's rank, then the notes textarea.
		const onLiveSave = vi.fn<LiveSave>().mockResolvedValue();
		render(
			<SheetValuesProvider
				mode="display"
				initialValues={{ ...values, notes1: "old" }}
				onLiveSave={onLiveSave}
				canEditLive
			>
				<SheetRenderer
					schema={{
						schema_version: 1,
						elements: [
							...schema.elements,
							{ type: "textarea", id: "notes1", name: "notes", live: true },
						],
					}}
				/>
			</SheetValuesProvider>,
		);
		const field = screen.getAllByRole("textbox")[index];

		await userEvent.click(field);
		await userEvent.tab();
		expect(onLiveSave).not.toHaveBeenCalled();

		await userEvent.clear(field);
		await userEvent.type(field, "7");
		await userEvent.tab();
		expect(onLiveSave).toHaveBeenCalledTimes(1);
		expect(onLiveSave).toHaveBeenCalledWith([id], "7");
	});

	it("save an input once on Enter, not again on the blur after it", async () => {
		const onLiveSave = vi.fn<LiveSave>().mockResolvedValue();
		renderSheet({ onLiveSave });
		const [hp] = screen.getAllByRole("textbox");

		await userEvent.clear(hp);
		await userEvent.type(hp, "7{Enter}");
		await userEvent.tab();

		await waitFor(() => expect(onLiveSave).toHaveBeenCalledTimes(1));
	});

	it("save a checkbox as soon as it changes", async () => {
		const onLiveSave = vi.fn<LiveSave>().mockResolvedValue();
		renderSheet({ onLiveSave });

		await userEvent.click(screen.getByRole("checkbox"));

		expect(onLiveSave).toHaveBeenCalledWith(["ins1"], true);
	});

	it("save a select as soon as an option is chosen", async () => {
		const onLiveSave = vi.fn<LiveSave>().mockResolvedValue();
		render(
			<SheetValuesProvider mode="display" onLiveSave={onLiveSave} canEditLive>
				<SheetRenderer
					schema={{
						schema_version: 1,
						elements: [
							{
								type: "select",
								id: "s1",
								name: "mood",
								live: true,
								values: ["calm", "angry"],
							},
						],
					}}
				/>
			</SheetValuesProvider>,
		);

		await userEvent.click(screen.getByRole("button"));
		await userEvent.click(await screen.findByRole("option", { name: "angry" }));

		expect(onLiveSave).toHaveBeenCalledWith(["s1"], "angry");
	});

	it("save a grid row's field under its row id", async () => {
		const onLiveSave = vi.fn<LiveSave>().mockResolvedValue();
		renderSheet({ onLiveSave });
		const [, rank] = screen.getAllByRole("textbox");

		await userEvent.type(rank, "3");
		await userEvent.tab();

		expect(onLiveSave).toHaveBeenCalledWith(["g1", "r1", "c1"], "3");
	});

	it("show the error and go back to the last saved value when a save fails", async () => {
		const onLiveSave = vi.fn<LiveSave>().mockRejectedValue(new Error("Not allowed"));
		renderSheet({ onLiveSave });
		const [hp] = screen.getAllByRole("textbox");

		await userEvent.clear(hp);
		await userEvent.type(hp, "99");
		await userEvent.tab();

		expect(await screen.findByRole("alert")).toHaveTextContent("Not allowed");
		expect(hp).toHaveValue("10");
	});

	it("clear the error once the field is edited again", async () => {
		const onLiveSave = vi
			.fn<LiveSave>()
			.mockRejectedValueOnce(new Error("Not allowed"))
			.mockResolvedValue();
		renderSheet({ onLiveSave });
		const [hp] = screen.getAllByRole("textbox");

		await userEvent.type(hp, "1");
		await userEvent.tab();
		await screen.findByRole("alert");

		await userEvent.type(hp, "2");

		expect(screen.queryByRole("alert")).toBeNull();
	});
});
