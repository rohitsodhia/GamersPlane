import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { GameDetails, GamePlayer } from "#/queries/game";
import { useGameBarStore } from "#/stores/game-bar";
import GameBar from "./GameBar";

let pathname = "/characters/1";
vi.mock("@tanstack/react-router", () => ({
	Link: ({ children, className, title }: Record<string, unknown>) => (
		<a href="/x" className={className as string} title={title as string}>
			{children as ReactNode}
		</a>
	),
	useLocation: ({ select }: { select: (location: { pathname: string }) => unknown }) =>
		select({ pathname }),
}));

const apiFetch = vi.fn();
vi.mock("#/lib/api", () => ({
	apiFetch: (path: string) => apiFetch(path),
}));

const player = (overrides: Partial<GamePlayer>): GamePlayer => ({
	id: 1,
	username: "alice",
	is_gm: false,
	state: "accepted",
	characters: [],
	...overrides,
});

const game = (overrides: Partial<GameDetails> = {}): GameDetails =>
	({
		id: 5,
		title: "Lost Mines",
		root_forum_id: 9,
		public: true,
		viewer_state: null,
		players: [],
		...overrides,
	}) as GameDetails;

function respondWith(details: GameDetails | null) {
	apiFetch.mockImplementation(async () =>
		details
			? { ok: true, json: async () => details }
			: { ok: false, json: async () => ({}) },
	);
}

function renderBar() {
	const queryClient = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	return render(
		<QueryClientProvider client={queryClient}>
			<GameBar />
		</QueryClientProvider>,
	);
}

beforeEach(() => {
	useGameBarStore.setState({ gameId: 5 });
});
afterEach(() => {
	apiFetch.mockReset();
	useGameBarStore.setState({ gameId: null });
	pathname = "/characters/1";
});

describe("GameBar", () => {
	it("renders nothing when the page declares no game", () => {
		useGameBarStore.setState({ gameId: null });
		const { container } = renderBar();

		expect(container).toBeEmptyDOMElement();
		expect(apiFetch).not.toHaveBeenCalled();
	});

	it("renders nothing when the game can't be loaded", async () => {
		respondWith(null);
		const { container } = renderBar();

		await vi.waitFor(() => expect(apiFetch).toHaveBeenCalled());
		expect(container).toBeEmptyDOMElement();
	});

	it("shows the game details and forum links", async () => {
		respondWith(game({ public: false, viewer_state: "accepted" }));
		renderBar();

		expect(await screen.findByText("Game Details")).toBeInTheDocument();
		expect(screen.getByText("Forums")).toBeInTheDocument();
	});

	it.each([
		["/games/5", "Game Details", "Forums"],
		["/forums/42", "Forums", "Game Details"],
		["/forums", "Forums", "Game Details"],
	])("drops the link to where it's on (%s)", async (path, hidden, shown) => {
		pathname = path;
		respondWith(game());
		renderBar();

		expect(await screen.findByText(shown)).toBeInTheDocument();
		expect(screen.queryByText(hidden)).toBeNull();
	});

	it("keeps Game Details on another game whose id starts the same", async () => {
		pathname = "/games/50";
		respondWith(game());
		renderBar();

		expect(await screen.findByText("Game Details")).toBeInTheDocument();
	});

	it("hides the Characters menu when no character is approved", async () => {
		respondWith(
			game({
				players: [
					player({
						characters: [
							{ id: 1, label: "Pending", type: "pc", approved: false, can_view: true },
						],
					}),
				],
			}),
		);
		renderBar();

		await screen.findByText("Game Details");
		expect(screen.queryByRole("button", { name: "Characters" })).toBeNull();
	});

	it("lists approved characters, linking only the ones the viewer can open", async () => {
		respondWith(
			game({
				players: [
					player({
						characters: [
							{ id: 1, label: "Visible", type: "pc", approved: true, can_view: true },
							{ id: 2, label: "Hidden", type: "npc", approved: true, can_view: false },
						],
					}),
				],
			}),
		);
		renderBar();

		await userEvent.click(await screen.findByRole("button", { name: "Characters" }));

		expect(screen.getByRole("link", { name: "Visible" })).toBeInTheDocument();
		expect(screen.getByText("Hidden")).toBeInTheDocument();
		expect(screen.queryByRole("link", { name: "Hidden" })).toBeNull();
		expect(screen.getByText("NPC")).toBeInTheDocument();
	});
});
