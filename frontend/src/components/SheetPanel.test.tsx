import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useGameBarStore } from "#/stores/game-bar";
import { type RollTarget, useRollTargetStore } from "#/stores/roll-target";
import SheetPanel from "./SheetPanel";

vi.mock("@tanstack/react-router", () => ({
	Link: ({ children }: { children: ReactNode }) => <a href="/x">{children}</a>,
}));

const apiFetch = vi.fn();
vi.mock("#/lib/api", () => ({
	apiFetch: (path: string) => apiFetch(path),
}));

const layout = {
	schema_version: 1,
	elements: [{ type: "text", text: "Athletics", roll: { dice: "1d20+2" } }],
};

beforeEach(() => {
	apiFetch.mockImplementation(async () => ({
		ok: true,
		json: async () => ({
			id: 1,
			label: "Hero",
			name: null,
			user_id: 1,
			values: {},
			layout,
			can_edit_live: false,
		}),
	}));
	useGameBarStore.setState({ panel: { gameId: 5, characterId: 1 } });
});
afterEach(() => {
	apiFetch.mockReset();
	useGameBarStore.setState({ panel: null });
	useRollTargetStore.setState({ targets: [] });
});

function renderPanel() {
	const queryClient = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	return render(
		<QueryClientProvider client={queryClient}>
			<SheetPanel gameId={5} />
		</QueryClientProvider>,
	);
}

function register(overrides: Partial<RollTarget> = {}) {
	const addRoll = vi.fn<RollTarget["addRoll"]>();
	useRollTargetStore.getState().register({
		id: "composer",
		addRoll,
		blockedReason: null,
		...overrides,
	});
	return addRoll;
}

describe("SheetPanel rolls", () => {
	it("sends a click to the registered composer, prefilled and unrolled", async () => {
		const addRoll = register();
		renderPanel();

		await userEvent.click(await screen.findByText("Athletics"));

		expect(addRoll).toHaveBeenCalledWith({
			dice: "1d20+2",
			reason: "Athletics",
			mode: "new",
		});
	});

	it("stops taking clicks once the composer goes away", async () => {
		const addRoll = register();
		renderPanel();
		await screen.findByRole("button", { name: /Roll Athletics/ });

		useRollTargetStore.getState().unregister("composer");

		expect(
			await screen.findByRole("img", { name: "Roll Athletics: 1d20+2" }),
		).toBeInTheDocument();
		expect(screen.queryByRole("button", { name: /Roll Athletics/ })).toBeNull();
		await userEvent.click(screen.getByText("Athletics"));
		expect(addRoll).not.toHaveBeenCalled();
	});

	it("explains why rolls are blocked instead of taking the click", async () => {
		const addRoll = register({ blockedReason: "Rolls are turned off in this thread." });
		renderPanel();

		const icon = await screen.findByRole("img", {
			name: "Roll Athletics: 1d20+2. Rolls are turned off in this thread.",
		});
		await userEvent.click(icon);

		expect(screen.queryByRole("button", { name: /Roll Athletics/ })).toBeNull();
		expect(addRoll).not.toHaveBeenCalled();
	});

	it("shows the composer's refusal beside the icon", async () => {
		register({ addRoll: () => "A post can have at most 10 rolls." });
		renderPanel();

		await userEvent.click(await screen.findByText("Athletics"));

		expect(await screen.findByRole("alert")).toHaveTextContent(
			"A post can have at most 10 rolls.",
		);
	});
});
