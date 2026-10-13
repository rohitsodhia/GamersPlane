import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { GameDetails, GamePlayer } from "#/queries/game";
import { useAuthStore } from "#/stores/auth";
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

vi.mock("#/routes/characters/sheets/-components/SheetRenderer", () => ({
	SheetRenderer: () => <div>sheet body</div>,
}));

// `character: "error"` makes the character fetch fail.
function respondWith(details: GameDetails | null, character: object | "error" = {}) {
	apiFetch.mockImplementation(async (path: string) => {
		if (path === "/me") return { ok: true, json: async () => ({ id: viewerId }) };
		if (path.startsWith("/characters/")) {
			return character === "error"
				? { ok: false, status: 500, json: async () => ({ errors: [] }) }
				: {
						ok: true,
						json: async () => ({
							id: 1,
							label: "Visible",
							name: null,
							user_id: 1,
							values: {},
							layout: {},
							...character,
						}),
					};
		}
		return details
			? { ok: true, json: async () => details }
			: { ok: false, json: async () => ({}) };
	});
}

const visibleCharacterGame = () =>
	game({
		players: [
			player({
				characters: [
					{
						id: 1,
						label: "Visible",
						name: null,
						type: "pc",
						approved: true,
						can_view: true,
					},
					{
						id: 2,
						label: "Hidden",
						name: null,
						type: "npc",
						approved: true,
						can_view: false,
					},
				],
			}),
		],
	});

// The id `GET /me` reports for the logged-in viewer; the characters belong to user 1.
let viewerId = 1;

async function openVisibleSheet(buttonName = "Visible") {
	renderBar();
	await userEvent.click(await screen.findByRole("button", { name: "Characters" }));
	await userEvent.click(screen.getByRole("button", { name: buttonName }));
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
	localStorage.clear();
	useGameBarStore.setState({ gameId: null, panel: null, panelHeight: null });
	useAuthStore.setState({ token: null });
	viewerId = 1;
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
							{
								id: 1,
								label: "Pending",
								name: null,
								type: "pc",
								approved: false,
								can_view: true,
							},
						],
					}),
				],
			}),
		);
		renderBar();

		await screen.findByText("Game Details");
		expect(screen.queryByRole("button", { name: "Characters" })).toBeNull();
	});

	it("lists a character by its name, falling back to the label without one", async () => {
		respondWith(
			game({
				players: [
					player({
						characters: [
							{
								id: 1,
								label: "Private handle",
								name: "Aragorn",
								type: "pc",
								approved: true,
								can_view: true,
							},
							{
								id: 2,
								label: "Old label",
								name: null,
								type: "pc",
								approved: true,
								can_view: false,
							},
						],
					}),
				],
			}),
		);
		renderBar();

		await userEvent.click(await screen.findByRole("button", { name: "Characters" }));

		expect(screen.getByRole("button", { name: "Aragorn" })).toBeInTheDocument();
		expect(screen.queryByText("Private handle")).toBeNull();
		expect(screen.getByText("Old label")).toBeInTheDocument();
	});

	it("lists approved characters, making only the ones the viewer can open clickable", async () => {
		respondWith(visibleCharacterGame());
		renderBar();

		await userEvent.click(await screen.findByRole("button", { name: "Characters" }));

		expect(screen.getByRole("button", { name: "Visible" })).toBeInTheDocument();
		expect(screen.getByText("Hidden")).toBeInTheDocument();
		expect(screen.queryByRole("button", { name: "Hidden" })).toBeNull();
		expect(screen.getByText("NPC")).toBeInTheDocument();
	});
});

describe("GameBar sheet panel", () => {
	it("opens the picked character's sheet and marks it in the menu", async () => {
		respondWith(visibleCharacterGame());
		await openVisibleSheet();

		expect(
			await screen.findByRole("region", { name: "Visible sheet" }),
		).toBeInTheDocument();
		expect(await screen.findByText("sheet body")).toBeInTheDocument();
		// No name, so the label is the title.
		expect(screen.getByRole("heading", { name: "Visible" })).toBeInTheDocument();
		expect(screen.getByRole("link", { name: "Open full page" })).toBeInTheDocument();

		await userEvent.click(screen.getByRole("button", { name: "Characters" }));
		expect(screen.getByRole("button", { name: "Visible" })).toHaveAttribute(
			"aria-current",
			"true",
		);
	});

	describe("header title", () => {
		const namedGame = () =>
			game({
				players: [
					player({
						characters: [
							{
								id: 1,
								label: "Visible",
								name: "Aragorn",
								type: "pc",
								approved: true,
								can_view: true,
							},
						],
					}),
				],
			});

		it("shows the name as the title and the label as muted text to the owner", async () => {
			viewerId = 1;
			useAuthStore.setState({ token: "t" });
			respondWith(namedGame(), { name: "Aragorn" });
			await openVisibleSheet("Aragorn");

			const region = await screen.findByRole("region", { name: "Aragorn sheet" });
			expect(
				within(region).getByRole("heading", { name: "Aragorn" }),
			).toBeInTheDocument();
			expect(await within(region).findByText("Visible")).toBeInTheDocument();
		});

		it("hides the label from other viewers", async () => {
			viewerId = 99;
			useAuthStore.setState({ token: "t" });
			respondWith(namedGame(), { name: "Aragorn" });
			await openVisibleSheet("Aragorn");

			const region = await screen.findByRole("region", { name: "Aragorn sheet" });
			await screen.findByText("sheet body");
			expect(within(region).queryByText("Visible")).toBeNull();
		});
	});

	it("closes with the X button", async () => {
		respondWith(visibleCharacterGame());
		await openVisibleSheet();
		await screen.findByRole("region", { name: "Visible sheet" });

		await userEvent.click(screen.getByRole("button", { name: "Close" }));

		expect(screen.queryByRole("region", { name: "Visible sheet" })).toBeNull();
		expect(useGameBarStore.getState().panel).toBeNull();
	});

	it("grows the page-end spacer by the panel's height", async () => {
		respondWith(visibleCharacterGame());
		const { container } = renderBar();
		await screen.findByText("Game Details");
		const spacer = container.firstElementChild as HTMLElement;
		expect(spacer.style.height).toBe("");

		useGameBarStore.getState().openPanel(5, 1);
		useGameBarStore.getState().setPanelHeight(400);

		await vi.waitFor(() =>
			expect(spacer.style.height).toBe(
				"calc(var(--game-bar-height) + min(400px, 80dvh))",
			),
		);
	});

	it("stays hidden when it was opened for another game", async () => {
		respondWith(visibleCharacterGame());
		useGameBarStore.setState({ panel: { gameId: 6, characterId: 1 } });
		renderBar();

		await screen.findByText("Game Details");
		expect(screen.queryByRole("region")).toBeNull();
	});

	it("shows an error when the sheet can't be loaded", async () => {
		respondWith(visibleCharacterGame(), "error");
		await openVisibleSheet();

		expect(await screen.findByRole("alert")).toHaveTextContent(/couldn't load/i);
	});

	it("resizes with the arrow keys and remembers the height", async () => {
		respondWith(visibleCharacterGame());
		await openVisibleSheet();
		const handle = await screen.findByRole("separator");
		const before = Number(handle.getAttribute("aria-valuenow"));

		handle.focus();
		await userEvent.keyboard("{ArrowUp}");

		expect(handle).toHaveAttribute("aria-valuenow", String(before + 24));
		expect(localStorage.getItem("game-bar:sheet-panel-height")).toBe(
			String(before + 24),
		);
	});

	it("resizes by dragging the handle up, saving only once it moved", async () => {
		respondWith(visibleCharacterGame());
		await openVisibleSheet();
		const handle = await screen.findByRole("separator");
		handle.setPointerCapture = vi.fn();
		handle.releasePointerCapture = vi.fn();
		const before = Number(handle.getAttribute("aria-valuenow"));

		// A press and release without moving doesn't store the default.
		fireEvent.pointerDown(handle, { pointerId: 1, clientY: 500 });
		fireEvent.pointerUp(handle, { pointerId: 1, clientY: 500 });
		expect(localStorage.getItem("game-bar:sheet-panel-height")).toBeNull();

		fireEvent.pointerDown(handle, { pointerId: 1, clientY: 500 });
		fireEvent.pointerMove(handle, { pointerId: 1, clientY: 450 });
		expect(handle).toHaveAttribute("aria-valuenow", String(before + 50));
		fireEvent.pointerUp(handle, { pointerId: 1, clientY: 450 });
		expect(localStorage.getItem("game-bar:sheet-panel-height")).toBe(
			String(before + 50),
		);
	});

	it("starts from the remembered height", async () => {
		localStorage.setItem("game-bar:sheet-panel-height", "333");
		respondWith(visibleCharacterGame());
		await openVisibleSheet();

		await vi.waitFor(() => expect(useGameBarStore.getState().panelHeight).toBe(333));
		expect(screen.getByRole("separator")).toHaveAttribute("aria-valuenow", "333");
	});
});
