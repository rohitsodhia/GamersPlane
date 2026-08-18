import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, notFound } from "@tanstack/react-router";
import { formatDate } from "#/lib/format-date";
import { useHbMargined } from "#/lib/use-hb-margined";
import { lastActivityText } from "#/lib/users";
import { userQueryOptions } from "#/queries/users";

export const Route = createFileRoute("/user/$userId")({
	params: {
		parse: (params) => ({ userId: Number(params.userId) }),
	},
	beforeLoad: ({ params }) => {
		if (!Number.isInteger(params.userId) || params.userId < 1) throw notFound();
	},
	loader: async ({ context, params }) => {
		try {
			await context.queryClient.ensureQueryData(userQueryOptions(params.userId));
		} catch {
			throw notFound();
		}
	},
	component: RouteComponent,
});

function RouteComponent() {
	const { userId } = Route.useParams();
	const { data: user } = useSuspenseQuery(userQueryOptions(userId));

	const allowBan = true;
	const banState = 0;

	const charCount = user.characters.count;
	const gameCount = user.gmStats.count;

	const hbMaginedMain = useHbMargined<HTMLHeadingElement>();
	const hbMaginedSub = useHbMargined<HTMLHeadingElement>();

	return (
		<div>
			<h1 className="headerbar" ref={hbMaginedMain.ref}>
				{user.username}
			</h1>
			<div
				id="user-profile-struct"
				style={{ marginInline: `${hbMaginedMain.margin}px` }}
			>
				<div className="avatar-wrapper">
					<img src={user.avatar} className="avatar" alt={`${user.username} Avatar`} />
					<div>
						<a href={`/pms/send/?userID=${user.id}`}>Send Private Message</a>
					</div>
				</div>
				<div id="user-profile-info">
					{allowBan && (
						<div className="align-right">
							<button type="button" onClick={() => {}} className="skew-btn">
								{banState === 1 ? "Unban" : "Ban"} User
							</button>
						</div>
					)}

					<h2 className="headerbar hb-dark" ref={hbMaginedSub.ref}>
						User Information
					</h2>
					<div
						className="section-info"
						style={{ marginInline: `${hbMaginedSub.margin}px` }}
					>
						<div>
							<strong>Member Since</strong>
							<div>{formatDate(user.joinDate)}</div>
						</div>
						{user.lastActivity && (
							<div>
								<strong>Last activity</strong>
								<div>{lastActivityText(user.lastActivity)}</div>
							</div>
						)}
						{user.pronouns && (
							<div>
								<strong>Pronouns</strong>
								<div>{user.pronouns}</div>
							</div>
						)}
						{user.showAge && (
							<div>
								<strong>Age</strong>
								<div>{user.age}</div>
							</div>
						)}
						{user.location && (
							<div>
								<strong>Location</strong>
								<div>{user.location}</div>
							</div>
						)}
					</div>

					<h2 className="headerbar hb-dark">My game interests</h2>
					<div style={{ marginInline: `${hbMaginedSub.margin}px` }}></div>

					<h2 className="headerbar hb-dark">Forum Stats</h2>
					<div
						className="section-info"
						style={{ marginInline: `${hbMaginedSub.margin}px` }}
					>
						<div>
							<strong>Total Posts:</strong>
							<div>{user.postCount}</div>
						</div>
						<div>
							<strong>Community Posts:</strong>
							<div>{user.communityPostCount}</div>
						</div>
						<div>
							<strong>Game Posts:</strong>
							<div>{user.gamePostCount}</div>
						</div>
					</div>

					{user.activeGames.length > 0 && (
						<div className="activeGames userInfoBox">
							<h2 className="headerbar hb-dark">Active Games</h2>
							<p>Game activity this week</p>
							<ul>
								{user.activeGames.map((activeGame) => (
									<li key={activeGame.id}>
										{activeGame.isGM && (
											<img src="/images/gm_icon.png" className="ag-isGM" alt="GM" />
										)}
										<a href={`/games/${activeGame.id}`} className="ag-title">
											{activeGame.name}
										</a>
										<span className="ag-system">{activeGame.system}</span>
										{activeGame.forumId && (
											<a
												className="ag-forum badge badge-gamePublic"
												href={`/forums/${activeGame.forumId}`}
											>
												Public
											</a>
										)}
									</li>
								))}
							</ul>
						</div>
					)}

					<div id="charStats" className="userInfoBox">
						<h2 className="headerbar hb-dark">Characters Stats</h2>
						{charCount > 0 && (
							<p>
								{user.username} has made {charCount} character{charCount > 1 ? "s" : ""}{" "}
								so far.
							</p>
						)}
						<div
							className="section-info"
							style={{ marginInline: `${hbMaginedSub.margin}px` }}
						>
							{user.characters.systems.map((system, index) => (
								<div
									key={system.system.id}
									className={`game${index % 3 === 2 ? " third" : ""}`}
								>
									<div className="gameInfo">
										<p>{system.system.name}</p>
										<p>
											{system.count} char{system.count > 1 ? "s" : ""} -{" "}
											{charCount > 0 ? Math.round((system.count / charCount) * 100) : 0}
											%
										</p>
									</div>
								</div>
							))}
							{user.characters.systems.length === 0 && (
								<div className="no-items">
									{user.username} has not yet made any characters.
								</div>
							)}
						</div>
					</div>

					<div id="gameStats" className="userInfoBox">
						<h2 className="headerbar hb-dark">GM Stats</h2>
						{user.gmStats.systems.length > 0 && (
							<p>
								{user.username} has run {gameCount} game{gameCount > 1 ? "s" : ""} so
								far.
							</p>
						)}
						<div
							className="section-info"
							style={{ marginInline: `${hbMaginedSub.margin}px` }}
						>
							{user.gmStats.systems.map((system, index) => (
								<div
									key={system.system.id}
									className={`game${index % 3 === 2 ? " third" : ""}`}
								>
									<div className="gameInfo">
										<p>{system.system.name}</p>
										<p>
											{system.count} game{system.count > 1 ? "s" : ""} -{" "}
											{gameCount > 0 ? Math.round((system.count / gameCount) * 100) : 0}
											%
										</p>
									</div>
								</div>
							))}
							{user.gmStats.systems.length === 0 && (
								<div className="no-items">
									{user.username} has not yet run any games.
								</div>
							)}
						</div>
					</div>
				</div>
			</div>
		</div>
	);
}
