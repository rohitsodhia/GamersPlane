import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { BasicRollResult } from "#/queries/dice";
import CardsMenu from "./GameBarCards";
import DiceMenu from "./GameBarDice";

vi.mock("@tanstack/react-router", () => ({
	Link: ({ children, to }: { children: ReactNode; to: string }) => (
		<a href={to}>{children}</a>
	),
	useLocation: ({ select }: { select: (location: { href: string }) => unknown }) =>
		select({ href: "/games/5" }),
}));

const apiFetch = vi.fn();
vi.mock("#/lib/api", async (importOriginal) => ({
	...(await importOriginal<typeof import("#/lib/api")>()),
	apiFetch: (path: string) => apiFetch(path),
}));

afterEach(() => {
	apiFetch.mockReset();
	localStorage.clear();
});

function renderTool(ui: ReactNode) {
	const queryClient = new QueryClient({
		defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
	});
	return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

const rollResult = (total: number): BasicRollResult => ({
	total,
	groups: [
		{
			expression: "1d20",
			terms: [
				{
					count: 1,
					sides: 20,
					sign: 1,
					keep_high: null,
					keep_count: null,
					rolls: [total],
					dropped: [],
					subtotal: total,
				},
			],
			modifier: 0,
			total,
		},
	],
});

const rollsOk = (...totals: number[]) => {
	for (const total of totals) {
		apiFetch.mockResolvedValueOnce({ ok: true, json: async () => rollResult(total) });
	}
};

describe("popover toggle", () => {
	it("closes on a second click of the trigger", async () => {
		renderTool(<DiceMenu />);
		const trigger = screen.getByRole("button", { name: "Dice" });

		await userEvent.click(trigger);
		expect(screen.getByRole("dialog", { name: "Dice" })).toBeInTheDocument();

		await userEvent.click(trigger);
		expect(screen.queryByRole("dialog")).toBeNull();
	});
});

describe("DiceMenu", () => {
	async function openDice() {
		renderTool(<DiceMenu />);
		await userEvent.click(screen.getByRole("button", { name: "Dice" }));
	}

	it("rolls a quick die as 1dN through the basic dice API", async () => {
		rollsOk(14);
		await openDice();

		await userEvent.click(screen.getByRole("button", { name: "d20" }));

		const list = await screen.findByRole("list", { name: "Recent rolls" });
		expect(within(list).getAllByRole("listitem")).toHaveLength(1);
		const url = new URL(apiFetch.mock.calls[0][0], "http://x");
		expect(url.pathname).toBe("/tools/dice");
		expect(url.searchParams.get("system")).toBe("basic");
		expect(url.searchParams.get("roll")).toBe("1d20");
	});

	it("rolls the custom expression on Enter", async () => {
		rollsOk(9);
		await openDice();

		await userEvent.type(
			screen.getByRole("textbox", { name: "Custom roll" }),
			"2d6+3{Enter}",
		);

		await screen.findByRole("list", { name: "Recent rolls" });
		expect(
			new URL(apiFetch.mock.calls[0][0], "http://x").searchParams.get("roll"),
		).toBe("2d6+3");
	});

	it("shows the newest roll first and keeps only the last 10", async () => {
		rollsOk(...Array.from({ length: 12 }, (_, i) => 100 + i));
		await openDice();
		const d20 = screen.getByRole("button", { name: "d20" });

		for (let i = 0; i < 12; i++) {
			await userEvent.click(d20);
			await vi.waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(i + 1));
		}

		const items = await vi.waitFor(() => {
			const found = within(
				screen.getByRole("list", { name: "Recent rolls" }),
			).getAllByRole("listitem");
			expect(found).toHaveLength(10);
			expect(found[0]).toHaveTextContent("111");
			return found;
		});
		expect(items[9]).toHaveTextContent("102");
	});

	it("shows the API's message for a bad expression", async () => {
		apiFetch.mockResolvedValueOnce({
			ok: false,
			status: 400,
			json: async () => ({ errors: [{ detail: "Bad dice expression" }] }),
		});
		await openDice();

		await userEvent.type(
			screen.getByRole("textbox", { name: "Custom roll" }),
			"zzz{Enter}",
		);

		expect(await screen.findByRole("alert")).toHaveTextContent("Bad dice expression");
	});
});

describe("CardsMenu", () => {
	async function openCards(gameId = 5) {
		const view = renderTool(<CardsMenu key={gameId} gameId={gameId} />);
		await userEvent.click(screen.getByRole("button", { name: "Cards" }));
		return view;
	}

	it("starts a deck, draws N cards and counts them off", async () => {
		await openCards();
		await userEvent.click(
			screen.getByRole("button", { name: "Playing Cards w/o Jokers" }),
		);
		expect(screen.getByText("52")).toBeInTheDocument();

		const count = screen.getByRole("textbox", { name: "Cards to draw" });
		await userEvent.clear(count);
		await userEvent.type(count, "3x");
		expect(count).toHaveValue("3");
		await userEvent.click(screen.getByRole("button", { name: "Draw Cards" }));

		expect(screen.getByText("49")).toBeInTheDocument();
		expect(screen.getAllByRole("img")).toHaveLength(3);
	});

	it("New Deck goes back to picking a deck", async () => {
		await openCards();
		await userEvent.click(
			screen.getByRole("button", { name: "Playing Cards w/ Jokers" }),
		);
		expect(screen.getByText("54")).toBeInTheDocument();

		await userEvent.click(screen.getByRole("button", { name: "New Deck" }));

		expect(
			screen.getByRole("button", { name: "Playing Cards w/o Jokers" }),
		).toBeInTheDocument();
		expect(localStorage.getItem("game-bar:deck:5")).toBeNull();
	});

	it("restores the deck and drawn cards after a remount", async () => {
		const { unmount } = await openCards();
		await userEvent.click(
			screen.getByRole("button", { name: "Playing Cards w/o Jokers" }),
		);
		await userEvent.click(screen.getByRole("button", { name: "Draw Cards" }));
		unmount();

		await openCards();

		expect(await screen.findByText("51")).toBeInTheDocument();
		expect(screen.getAllByRole("img")).toHaveLength(1);
	});
});
