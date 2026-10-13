import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SheetRenderer } from "./SheetRenderer";
import { type ScopeValues, SheetValuesProvider } from "./sheet-values";
import type { RollSpec, SheetElement, SheetSchema } from "./types";

beforeEach(() => {
	vi.spyOn(console, "warn").mockImplementation(() => {});
});
afterEach(() => {
	vi.restoreAllMocks();
});

function renderSheet(
	elements: SheetElement[],
	opts: {
		mode?: "edit" | "display";
		values?: ScopeValues;
		onRoll?: (r: unknown) => void;
	} = {},
) {
	const schema: SheetSchema = { schema_version: 1, elements };
	return render(
		<SheetValuesProvider
			initialValues={opts.values ?? {}}
			mode={opts.mode ?? "display"}
		>
			<SheetRenderer schema={schema} onRoll={opts.onRoll} />
		</SheetValuesProvider>,
	);
}

const athletics = (roll: RollSpec): SheetElement => ({
	type: "text",
	text: "Athletics",
	roll,
});

describe("rollable elements", () => {
	it("renders no roll UI in edit mode", () => {
		renderSheet([athletics({ dice: "1d20" })], { mode: "edit" });
		expect(screen.getByText("Athletics")).toBeInTheDocument();
		expect(screen.queryByRole("button")).toBeNull();
		expect(screen.queryByRole("img")).toBeNull();
	});

	it("shows a named dice button and forwards a click on the element to onRoll", async () => {
		const onRoll = vi.fn();
		renderSheet(
			[{ type: "input", id: "f1", name: "mod" }, athletics({ dice: "1d20+${mod}" })],
			{ values: { f1: "5" }, onRoll },
		);
		expect(
			screen.getByRole("button", { name: "Roll Athletics: 1d20+5" }),
		).toBeInTheDocument();

		await userEvent.click(screen.getByText("Athletics"));
		expect(onRoll).toHaveBeenCalledWith({
			dice: "1d20+5",
			reason: "Athletics",
			mode: "new",
		});
	});

	it("rolls once when the icon button itself is pressed", async () => {
		const onRoll = vi.fn();
		renderSheet([athletics({ dice: "1d20", mode: "add" })], { onRoll });
		await userEvent.click(screen.getByRole("button", { name: /Roll Athletics/ }));
		expect(onRoll).toHaveBeenCalledTimes(1);
		expect(onRoll).toHaveBeenCalledWith(expect.objectContaining({ mode: "add" }));
	});

	it("shows the dice but is not a button when the host takes no rolls", () => {
		renderSheet([athletics({ dice: "1d20" })]);
		expect(screen.queryByRole("button")).toBeNull();
		expect(
			screen.getByRole("img", { name: "Roll Athletics: 1d20" }),
		).toBeInTheDocument();
	});

	it("shows an unclickable error icon for a roll that can't be built", async () => {
		const onRoll = vi.fn();
		renderSheet([athletics({ dice: "0d20" })], { onRoll });
		expect(screen.queryByRole("button")).toBeNull();
		expect(screen.getByRole("img", { name: /Can't roll/ })).toBeInTheDocument();
		await userEvent.click(screen.getByText("Athletics"));
		expect(onRoll).not.toHaveBeenCalled();
	});

	it("rolls a label's own text, even inside a group that wires it to a control", async () => {
		const onRoll = vi.fn();
		renderSheet(
			[
				{
					type: "group",
					content: [
						{ type: "label", text: "Perception", roll: { dice: "1d20" } },
						{ type: "input", id: "f", name: "p" },
					],
				},
			],
			{ onRoll },
		);
		await userEvent.click(screen.getByText("Perception"));
		expect(onRoll).toHaveBeenCalledWith({
			dice: "1d20",
			reason: "Perception",
			mode: "new",
		});
	});

	it("resolves $row refs in a group roll inside a repeater row", async () => {
		const onRoll = vi.fn();
		renderSheet(
			[
				{
					type: "repeater",
					id: "r",
					name: "skills",
					content: [
						{ type: "input", id: "n", name: "name" },
						{
							type: "group",
							roll: {
								dice: "1d20",
								reason: "${$row.name}",
							},
							content: [{ type: "label", text: "Row" }],
						},
					],
				},
			],
			{ values: { r: [{ n: "Stealth" }] }, onRoll },
		);
		await userEvent.click(screen.getByRole("button", { name: "Roll Stealth: 1d20" }));
		expect(onRoll).toHaveBeenCalledWith({
			dice: "1d20",
			reason: "Stealth",
			mode: "new",
		});
	});

	it("rolls from a group's row but not when an input inside it is clicked", async () => {
		const onRoll = vi.fn();
		renderSheet(
			[
				{
					type: "group",
					roll: { dice: "1d6" },
					content: [
						{ type: "label", text: "Damage" },
						{ type: "input", id: "f", name: "amount" },
						{ type: "button", label: "Bump", on_click: { set: "amount", to: 1 } },
					],
				},
			],
			{ onRoll },
		);
		await userEvent.click(screen.getByRole("button", { name: "Bump" }));
		expect(onRoll).not.toHaveBeenCalled();

		await userEvent.click(screen.getByText("Damage"));
		expect(onRoll).toHaveBeenCalledWith({ dice: "1d6", reason: "Damage", mode: "new" });
	});

	it("shows the host's refusal as an alert and clears it after five seconds", () => {
		vi.useFakeTimers();
		try {
			renderSheet([athletics({ dice: "1d20" })], {
				onRoll: () => "A post can have at most 10 rolls.",
			});

			// userEvent is awkward under fake timers; a plain click is enough here.
			act(() => {
				screen.getByText("Athletics").click();
			});
			expect(screen.getByRole("alert")).toHaveTextContent(
				"A post can have at most 10 rolls.",
			);

			act(() => {
				vi.advanceTimersByTime(4999);
			});
			expect(screen.getByRole("alert")).toBeInTheDocument();
			act(() => {
				vi.advanceTimersByTime(1);
			});
			expect(screen.queryByRole("alert")).toBeNull();
		} finally {
			vi.useRealTimers();
		}
	});

	it("asks advantage / normal / disadvantage and rolls the chosen form", async () => {
		const onRoll = vi.fn();
		renderSheet([athletics({ dice: "1d20+2", advantage: true })], { onRoll });

		await userEvent.click(screen.getByText("Athletics"));
		expect(onRoll).not.toHaveBeenCalled();
		await userEvent.click(screen.getByRole("button", { name: "Disadvantage" }));
		expect(onRoll).toHaveBeenCalledWith({
			dice: "2d20l1+2",
			reason: "Athletics",
			mode: "new",
		});

		await userEvent.click(screen.getByRole("button", { name: /Roll Athletics/ }));
		await userEvent.click(screen.getByRole("button", { name: "Advantage" }));
		expect(onRoll).toHaveBeenLastCalledWith(
			expect.objectContaining({ dice: "2d20h1+2" }),
		);
	});
});
