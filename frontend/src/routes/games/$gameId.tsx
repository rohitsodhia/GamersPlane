import { useMutation, useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { useState } from "react";
import GMBadge from "#/components/GMBadge";
import { TiptapContent } from "#/components/TiptapContent";
import { ApiError } from "#/lib/api";
import { formatDate } from "#/lib/format-date";
import { useHbMargined } from "#/lib/use-hb-margined";
import {
	favoriteGame,
	type GamePlayer,
	gameDetailsQueryOptions,
	invitePlayer,
} from "#/queries/game";
import { meQueryOptions } from "#/queries/me";
import { type BasicSystem, systemsQueryOptions } from "#/queries/systems";
import { searchUserByUsername } from "#/queries/users";
import { useAuthStore } from "#/stores/auth";
import styles from "./$gameId.module.css";

export const Route = createFileRoute("/games/$gameId")({
	params: {
		parse: (params) => ({ gameId: Number(params.gameId) }),
	},
	beforeLoad: ({ params }) => {
		if (!Number.isInteger(params.gameId) || params.gameId < 1) throw notFound();
	},
	loader: async ({ context, params }) => {
		try {
			await Promise.all([
				context.queryClient.ensureQueryData(gameDetailsQueryOptions(params.gameId)),
				context.queryClient.ensureQueryData(systemsQueryOptions({ basic: true })),
			]);
		} catch {
			throw notFound();
		}
	},
	component: RouteComponent,
});

function systemName(systems: BasicSystem[], id: string) {
	return systems.find((system) => system.id === id)?.name ?? id;
}

function RouteComponent() {
	const { gameId } = Route.useParams();
	const { data: game } = useSuspenseQuery(gameDetailsQueryOptions(gameId));
	const { data: systems } = useSuspenseQuery(systemsQueryOptions({ basic: true }));
	const token = useAuthStore((state) => state.token);
	const { data: me } = useQuery({ ...meQueryOptions, enabled: !!token });
	const loggedIn = !!me;

	const hbMarginedH1 = useHbMargined<HTMLHeadingElement>();
	const hbMarginedH2 = useHbMargined<HTMLHeadingElement>();

	// --- Everything below this point that mutates state is a UI-only mock:
	// the backend only exposes GET /games/{id} and POST /games/ today. Each
	// action is marked with a TODO pointing at the endpoint it's standing in
	// for, and none of it persists past a page refresh.

	const [favorited, setFavorited] = useState(false);
	const favoriteMutation = useMutation({
		mutationFn: () => favoriteGame(gameId),
		onSuccess: (data) => setFavorited(data.favorite),
	});

	// TODO: no PATCH endpoint to toggle a game's open/closed status yet.
	const [status, setStatus] = useState(game.status);

	// TODO: no PATCH endpoint to toggle a game's forum public/private yet.
	const [isPublic, setIsPublic] = useState(game.public);

	// TODO: no retire/unretire endpoint yet.
	const [retired, setRetired] = useState(game.retired);
	const [displayRetireConfirm, setDisplayRetireConfirm] = useState(false);

	// TODO: local copy of the player list so the mock GM actions below (remove,
	// toggle GM, approve, reject, leave) can be demoed without a real endpoint.
	const [players, setPlayers] = useState<GamePlayer[]>(game.players);

	// TODO: no apply-to-game endpoint yet.
	const [hasApplied, setHasApplied] = useState(false);

	const [inviteUsername, setInviteUsername] = useState("");
	const [inviteError, setInviteError] = useState<string | null>(null);
	const inviteMutation = useMutation({
		mutationFn: async (username: string) => {
			const user = await searchUserByUsername(username);
			if (!user)
				throw new ApiError(404, [{ code: "not_found", detail: "Invalid user" }]);
			await invitePlayer(gameId, username);
			return user;
		},
		onSuccess: (user) => {
			setPlayers((prev) => [
				...prev,
				{ id: user.id, username: user.username, is_gm: false, state: "invited" },
			]);
			setInviteUsername("");
		},
		onError: (error: unknown) => {
			if (error instanceof ApiError && error.errors[0]?.detail) {
				setInviteError(error.errors[0].detail);
			} else {
				setInviteError("Failed to invite player");
			}
		},
	});

	// TODO: decks aren't modeled on the backend at all yet.
	const decks: { id: number; label: string; cardsRemaining: number }[] = [];

	const isPrimaryGM = me?.id === game.gm.id;
	// Excludes "invited" players: an invite alone doesn't make someone a
	// player in the game, so this shouldn't count toward inGame/approved.
	const currentPlayer = me
		? players.find((player) => player.id === me.id && player.state !== "invited")
		: undefined;
	const isGM = currentPlayer?.is_gm ?? isPrimaryGM;
	const inGame = !!currentPlayer;
	const approved = currentPlayer?.state === "accepted";

	const playersInGame = players.filter((player) => player.state === "accepted");
	const playersInvited = players.filter((player) => player.state === "invited");
	const pendingInvite = !!me && playersInvited.some((player) => player.id === me.id);
	const playersAwaitingApproval = players.filter(
		(player) => player.state === "applied",
	);

	const toggleGameStatus = () => setStatus((s) => (s === "open" ? "closed" : "open"));
	const toggleForum = () => setIsPublic((p) => !p);
	const confirmRetire = () => {
		setRetired(new Date().toISOString());
		setDisplayRetireConfirm(false);
	};
	const confirmUnretire = () => setRetired(null);

	const removePlayer = (userId: number) =>
		setPlayers((prev) => prev.filter((player) => player.id !== userId));
	const approvePlayer = (userId: number) =>
		setPlayers((prev) =>
			prev.map((player) =>
				player.id === userId ? { ...player, state: "accepted" } : player,
			),
		);
	const rejectPlayer = (userId: number) =>
		setPlayers((prev) => prev.filter((player) => player.id !== userId));
	const toggleGMStatus = (userId: number) =>
		setPlayers((prev) =>
			prev.map((player) =>
				player.id === userId ? { ...player, is_gm: !player.is_gm } : player,
			),
		);
	const leaveGame = () => {
		if (!me) return;
		setPlayers((prev) => prev.filter((player) => player.id !== me.id));
	};

	const submitInvite = (e: React.FormEvent) => {
		e.preventDefault();
		setInviteError(null);
		const username = inviteUsername.trim();
		if (!username) return;
		inviteMutation.mutate(username);
	};
	const withdrawInvite = (userId: number) =>
		setPlayers((prev) => prev.filter((player) => player.id !== userId));
	const acceptInvite = () => {
		if (!me) return;
		setPlayers((prev) =>
			prev.map((player) =>
				player.id === me.id ? { ...player, state: "accepted" } : player,
			),
		);
	};
	const declineInvite = () => {
		if (!me) return;
		setPlayers((prev) => prev.filter((player) => player.id !== me.id));
	};

	return (
		<div>
			<div className="hb-topper">
				<div className="trapezoid">
					<button
						type="button"
						className={`${styles.favorite}`}
						onClick={() => favoriteMutation.mutate()}
						disabled={favoriteMutation.isPending}
						title={favorited ? "Unfavorite" : "Favorite"}
					>
						{favorited ? (
							<>
								<img src="/images/icons/bookmark_on.png" alt="" /> Favorited
							</>
						) : (
							<>
								<img src="/images/icons/bookmark_off.png" alt="" /> Favorite
							</>
						)}
					</button>
					{isGM && (
						<Link to="/games/$gameId/edit" params={{ gameId: String(game.id) }}>
							Edit
						</Link>
					)}
				</div>
			</div>
			<h1 className="headerbar has-topper" ref={hbMarginedH1.ref}>
				<i className="ra ra-d6" /> {game.title}
			</h1>

			<div style={{ marginInline: `${hbMarginedH1.margin}px` }}>
				{retired && (
					<div className="banner error-banner">
						This game has been retired! That means it's no longer being run.
					</div>
				)}

				<div className={styles.details}>
					{game.description && (
						<>
							<TiptapContent
								content={game.description}
								className={styles["full-width"]}
							/>
							<hr />
						</>
					)}

					<DetailRow label="Game Status">
						{status === "open"
							? "Open for game applications"
							: "Closed for applications"}
						{isGM && (
							<button
								type="button"
								className={styles["inline-action"]}
								onClick={toggleGameStatus}
							>
								[{" "}
								{status === "open" ? "Close for applications" : "Open to applications"}{" "}
								]
							</button>
						)}
					</DetailRow>
					<DetailRow label="Game Title">{game.title}</DetailRow>
					<DetailRow label="System">{systemName(systems, game.system)}</DetailRow>
					<DetailRow label="Allowed Character Sheets">
						{game.allowed_char_sheets.map((id) => systemName(systems, id)).join(", ")}
					</DetailRow>
					<DetailRow label="Game Master">
						<Link
							to="/user/$userId"
							params={{ userId: game.gm.id }}
							className="username"
						>
							{game.gm.username}
						</Link>
					</DetailRow>
					<DetailRow label="Created">{formatDate(game.created)}</DetailRow>
					<DetailRow label="Post Frequency">
						{game.post_frequency.times_per} post
						{game.post_frequency.times_per > 1 ? "s" : ""} per{" "}
						{game.post_frequency.per_period === "d" ? "day" : "week"}
					</DetailRow>
					<DetailRow label="Number of Players">
						{playersInGame.length} / {game.num_players}
					</DetailRow>
					<DetailRow label="Number of Characters per Player">
						{game.chars_per_player}
					</DetailRow>
					<DetailRow label="Game Forums are">
						{isPublic ? "Public" : "Private"}{" "}
						{isGM && (
							<button
								type="button"
								className={styles["inline-action"]}
								onClick={toggleForum}
							>
								[ Make game {!isPublic ? "Public" : "Private"} ]
							</button>
						)}
						{!isGM && isPublic && (
							<>
								{" "}
								<Link to="/forums/{-$forumId}" params={{ forumId: game.root_forum_id }}>
									(Read the forum)
								</Link>
							</>
						)}
					</DetailRow>
					{game.recruitment_thread_id && (
						<DetailRow label="Games Tavern">
							<Link
								to="/forums/thread/$threadId"
								params={{ threadId: game.recruitment_thread_id }}
							>
								Recruitment thread
							</Link>
						</DetailRow>
					)}
					{isPrimaryGM && !retired && (
						<DetailRow label="Retire Game">
							<button
								type="button"
								className={styles["inline-action"]}
								onClick={() => setDisplayRetireConfirm((d) => !d)}
							>
								I want to close and retire this game!
							</button>
						</DetailRow>
					)}
					{isPrimaryGM && !retired && displayRetireConfirm && (
						<div className={`${styles["retire-confirm"]} ${styles["full-width"]}`}>
							Are you sure you want to retire this game?
							<br />
							It will be moved to the Retired Games drawer at the bottom of your{" "}
							<Link to="/games">Games list</Link>. You can come back here and unretire
							it later, if needed.
							<br />
							Any future posts in this game will not show up in the normal notification
							systems and will only be visible by manually checking the game's threads.
							<p>
								<button type="button" className="skew-btn" onClick={confirmRetire}>
									Retire
								</button>{" "}
								<button
									type="button"
									className="skew-btn"
									onClick={() => setDisplayRetireConfirm(false)}
								>
									Cancel
								</button>
							</p>
						</div>
					)}
					{isPrimaryGM && retired && (
						<DetailRow label="Restore Game">
							<button
								type="button"
								className={styles["inline-action"]}
								onClick={confirmUnretire}
							>
								I want to restore this retired game
							</button>
						</DetailRow>
					)}
					{game.char_gen_info && (
						<>
							<hr />
							<DetailRow label="Character Generation Info">
								<TiptapContent content={game.char_gen_info} />
							</DetailRow>
						</>
					)}
				</div>

				<div className={styles.columns}>
					<div className={styles["left-col"]}>
						<h2 className="headerbar hb-dark" ref={hbMarginedH2.ref}>
							<i className="ra ra-double-team" /> Players in Game
						</h2>
						<ul
							className={styles["player-list"]}
							style={{ marginInline: hbMarginedH2.margin }}
						>
							{playersInGame.map((player) => (
								<li key={player.id}>
									<div className={styles["player-info"]}>
										<div>
											<Link
												to="/user/$userId"
												params={{ userId: player.id }}
												className="username"
											>
												{player.username}
											</Link>{" "}
											{player.is_gm && <GMBadge />}
										</div>
										<div className={styles["action-links"]}>
											{me &&
												player.id !== me.id &&
												isGM &&
												!(player.id === game.gm.id) && (
													<button
														type="button"
														className={styles["inline-action"]}
														onClick={() => removePlayer(player.id)}
													>
														Remove player
													</button>
												)}
											{isPrimaryGM && player.id !== game.gm.id && (
												<button
													type="button"
													className={styles["inline-action"]}
													onClick={() => toggleGMStatus(player.id)}
												>
													{player.is_gm ? "Remove as" : "Make"} GM
												</button>
											)}
											{me && player.id === me.id && player.id !== game.gm.id && (
												<button
													type="button"
													className={styles["inline-action"]}
													onClick={leaveGame}
												>
													Leave Game
												</button>
											)}
										</div>
									</div>
									{/* TODO: character submission isn't wired to a real endpoint yet, so
									    there's no per-player character list to render here. */}
								</li>
							))}
							{playersInGame.length === 0 && (
								<li className={styles.notice}>No players have joined yet.</li>
							)}
						</ul>

						{!retired && isGM && playersAwaitingApproval.length > 0 && (
							<>
								<h2 className="headerbar hb-dark">Players Pending Approval</h2>
								<ul className={styles["player-list"]}>
									{playersAwaitingApproval.map((player) => (
										<li key={player.id}>
											<div className={styles["player-info"]}>
												<div>
													<Link to="/user/$userId" params={{ userId: player.id }}>
														{player.username}
													</Link>
												</div>
												<div className={styles["action-links"]}>
													<button
														type="button"
														className={styles["inline-action"]}
														onClick={() => approvePlayer(player.id)}
													>
														Approve
													</button>
													<button
														type="button"
														className={styles["inline-action"]}
														onClick={() => rejectPlayer(player.id)}
													>
														Reject
													</button>
												</div>
											</div>
										</li>
									))}
								</ul>
							</>
						)}

						{!retired && (
							<>
								<h2 className="headerbar hb-dark">
									<i className="ra ra-hourglass" /> Invited
								</h2>
								<div style={{ marginInline: hbMarginedH2.margin }}>
									<ul className={styles["player-list"]}>
										{playersInvited.map((player) => (
											<li key={player.id}>
												<div className={styles["player-info"]}>
													<div>{player.username}</div>
													{isGM && (
														<div className={styles["action-links"]}>
															<button
																type="button"
																className={styles["inline-action"]}
																onClick={() => withdrawInvite(player.id)}
															>
																Withdraw Invite
															</button>
														</div>
													)}
												</div>
											</li>
										))}
										{playersInvited.length === 0 && (
											<li className={styles.notice}>No pending invites.</li>
										)}
									</ul>
									{isGM && (
										<>
											<form className={styles["invite-form"]} onSubmit={submitInvite}>
												<label htmlFor="invite-username">Invite player:</label>
												<input
													id="invite-username"
													type="text"
													value={inviteUsername}
													onChange={(e) => setInviteUsername(e.target.value)}
													placeholder="Username"
													disabled={inviteMutation.isPending}
												/>
												<button
													type="submit"
													className="skew-btn"
													disabled={inviteMutation.isPending}
												>
													Invite
												</button>
											</form>
											{inviteError && <div className="error">{inviteError}</div>}
										</>
									)}
								</div>
							</>
						)}

						<div className={styles.decks}>
							{!retired && isGM && (
								<div style={{ marginLeft: hbMarginedH2.margin }}>
									{/* TODO: no decks backend yet — button is inert */}
									<button
										type="button"
										className="skew-btn"
										disabled
										title="Coming soon"
									>
										New Deck
									</button>
								</div>
							)}
							<h2 className="headerbar hb-dark has-topper">
								<i className="ra ra-spades-card" /> Decks
							</h2>
							<div
								className={styles["decks-body"]}
								style={{ marginInline: hbMarginedH2.margin }}
							>
								{decks.length === 0 && (
									<p className={styles.notice}>
										There are no decks available at this time
									</p>
								)}
							</div>
						</div>
					</div>

					<div className={styles["right-col"]}>
						{!retired && status !== "open" && !pendingInvite && !inGame && (
							<div className={styles["right-panel"]}>
								<h2 className="headerbar hb-dark">
									<i className="ra ra-round-shield" /> Game Closed
								</h2>
								<p className={styles.notice}>This game is closed for applications</p>
							</div>
						)}
						{!retired && status === "open" && !loggedIn && (
							<div className={styles["right-panel"]}>
								<h2 className="headerbar hb-dark">
									<i className="ra ra-player-teleport" /> Join Game
								</h2>
								<p className="align-center">Interested in this game?</p>
								<p className="align-center">
									<Link to="/login" search={{ redirect: `/games/${game.id}` }}>
										Login
									</Link>{" "}
									or <Link to="/register">Register</Link> to join!
								</p>
							</div>
						)}
						{!retired &&
							status === "open" &&
							loggedIn &&
							!pendingInvite &&
							!inGame &&
							game.num_players <= playersInGame.length && (
								<div className={styles["right-panel"]}>
									<h2 className="headerbar hb-dark">
										<i className="ra ra-round-shield" /> Game Full
									</h2>
									<p className={styles.notice}>This game is currently full</p>
								</div>
							)}
						{!retired &&
							status === "open" &&
							loggedIn &&
							!pendingInvite &&
							!inGame &&
							game.num_players > playersInGame.length &&
							!hasApplied && (
								<div className={styles["right-panel"]}>
									<h2 className="headerbar hb-dark">
										<i className="ra ra-player-teleport" /> Join Game
									</h2>
									{game.recruitment_thread_id && (
										<>
											<p>
												<Link
													to="/forums/thread/$threadId"
													params={{ threadId: game.recruitment_thread_id }}
													className="skew-btn"
												>
													<i className="ra ra-beer" /> Apply in Games Tavern
												</Link>
											</p>
											<p>
												<a
													href={`/pms/send/?userID=${game.gm.id}`}
													className="skew-btn"
												>
													<i className="ra ra-quill-ink" /> Message the GM
												</a>
											</p>
										</>
									)}
									{/* TODO: no apply-to-game endpoint yet, this just flips local state */}
									{!game.recruitment_thread_id ? (
										<p className="align-center">
											<button
												type="button"
												className="skew-btn"
												onClick={() => setHasApplied(true)}
											>
												Apply to Game
											</button>
										</p>
									) : (
										<p className="align-right">
											<hr />
											<button
												type="button"
												className={styles["inline-action"]}
												onClick={() => setHasApplied(true)}
											>
												Apply to game
											</button>
										</p>
									)}
								</div>
							)}
						{!retired && loggedIn && !pendingInvite && inGame && !approved && (
							<div className={styles["right-panel"]}>
								<h2 className="headerbar hb-dark">
									<i className="ra ra-player-teleport" /> Join Game
								</h2>
								<p className={styles.notice}>
									Your request to join this game is awaiting approval
								</p>
								<p>
									{/* TODO: no withdraw endpoint yet */}
									<button
										type="button"
										className={styles["inline-action"]}
										onClick={leaveGame}
									>
										withdraw
									</button>{" "}
									from the game if you're tired of waiting.
								</p>
							</div>
						)}
						{!retired && loggedIn && hasApplied && !inGame && (
							<div className={styles["right-panel"]}>
								<h2 className="headerbar hb-dark">
									<i className="ra ra-player-teleport" /> Join Game
								</h2>
								<p className={styles.notice}>
									Your request to join this game is awaiting approval
								</p>
							</div>
						)}
						{!retired && loggedIn && pendingInvite && (
							<div className={styles["right-panel"]}>
								<h2 className="headerbar hb-dark">
									<i className="ra ra-hourglass" /> Invite Pending
								</h2>
								<p>You've been invited to join this game!</p>
								<p>
									<button type="button" className="skew-btn" onClick={acceptInvite}>
										Join
									</button>{" "}
									<button type="button" className="skew-btn" onClick={declineInvite}>
										Decline
									</button>
								</p>
							</div>
						)}
						{!retired && loggedIn && inGame && approved && (
							<div className={styles["right-panel"]}>
								<h2 className="headerbar hb-dark">
									<i className="ra ra-player-teleport" /> Submit a Character
								</h2>
								{/* TODO: game <-> character submission isn't wired up yet */}
								<div className={styles.notice}>
									Character submission isn't available yet.
								</div>
							</div>
						)}
					</div>
				</div>
			</div>
		</div>
	);
}

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
	return (
		<div>
			<div>{label}</div>
			<div>{children}</div>
		</div>
	);
}
