import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import clsx from "clsx";
import { useEffect, useState } from "react";
import { Autocomplete } from "#/components/Autocomplete";
import LoadingSpinner from "#/components/LoadingSpinner";
import { useHbMargined } from "#/lib/use-hb-margined";
import { latestGamesQueryOptions } from "#/queries/game";
import { type BasicSystem, systemsQueryOptions } from "#/queries/systems";
import { useLayoutStore } from "#/stores/layout";
import styles from "./-landing.module.css";

const SYSTEM_LOGOS = [
	{ id: "dnd5", alt: "Dungeons & Dragons 5th Edition" },
	{ id: "thestrange", alt: "The Strange" },
	{ id: "pathfinder", alt: "Pathfinder" },
	{ id: "starwarsffg", alt: "Star Wars (FFG)" },
	{ id: "13thage", alt: "13th Age" },
	{ id: "numenera", alt: "Numenera" },
	{ id: "shadowrun5", alt: "Shadowrun 5th Edition" },
	{ id: "fate", alt: "Fate" },
	{ id: "savageworlds", alt: "Savage Worlds" },
];

function LatestGames({ systemId }: { systemId: string | null }) {
	const { data: games, isPending } = useQuery(latestGamesQueryOptions(systemId));

	if (isPending) {
		return (
			<div className={styles["games-loading"]}>
				<LoadingSpinner />
			</div>
		);
	}
	if (!games?.length) {
		return (
			<div className={styles["no-games"]}>
				{systemId ? (
					<>
						<p>No games found for this system.</p>
						<p>Join and start one!</p>
					</>
				) : (
					"No games found."
				)}
			</div>
		);
	}

	return games.map((game, index) => (
		<div key={game.id} className={clsx(styles["game"], index === 0 && styles["first"])}>
			<div className={styles["title"]}>
				<Link to="/games/$gameId" params={{ gameId: game.id }}>
					{game.title}
				</Link>{" "}
				({game.player_count} / {game.num_players})
			</div>
			<div className={styles["info"]}>
				<span className={styles["system"]}>{game.system}</span> run by{" "}
				<Link to="/user/$userId" params={{ userId: game.gm.id }} className="username">
					{game.gm.username}
				</Link>
			</div>
		</div>
	));
}

function Landing() {
	const hbMargined = useHbMargined<HTMLHeadingElement>();
	const setNoGap = useLayoutStore((state) => state.setNoGap);
	// Preloaded by the "/" loader whenever it picks Landing.
	const { data: systems } = useSuspenseQuery(systemsQueryOptions({ basic: true }));
	const [systemId, setSystemId] = useState<string | null>(null);

	useEffect(() => {
		setNoGap(true);
		return () => setNoGap(false);
	}, [setNoGap]);

	return (
		<div className={`page-wrap full-width ${styles["landing-page"]}`}>
			<div className={`full-width ${styles["landing-top"]}`}>
				<header className={styles.hero}>
					<h1>Scratch that RPG itch</h1>
					<h2>
						Talk and play <strong>RPGs</strong> with{" "}
						<strong>hundreds of players</strong>!
					</h2>
				</header>
				<div className={styles["landing-top-content"]}>
					<div className={styles["white-box"]}>
						<div className={styles["latest-games"]}>
							<h2
								className={`headerbar ${styles["games-header"]}`}
								ref={hbMargined.ref}
							>
								Latest Games
							</h2>
							<div style={{ marginInline: hbMargined.margin }}>
								<div className={styles["system-search"]}>
									<Autocomplete
										id="landing-system-search"
										items={systems}
										getId={(system: BasicSystem) => system.id}
										getLabel={(system: BasicSystem) => system.name}
										onAction={(id) => setSystemId(id)}
										onClear={() => setSystemId(null)}
										placeholder="Search systems..."
									/>
								</div>

								<LatestGames systemId={systemId} />
							</div>
						</div>
						<div className={styles.signup}>
							<p>
								<Link to="/register" className={`skew-btn ${styles.register}`}>
									Sign up!
								</Link>
							</p>
							<p>or if you're already a member...</p>
							<p>
								<Link to="/login" className={`skew-btn ${styles.login}`}>
									Log in
								</Link>
							</p>
						</div>
					</div>
				</div>
			</div>
			<div className={styles["what-is"]}>
				<div className={styles["what-is-logos"]}>
					{SYSTEM_LOGOS.map((system) => (
						<img
							key={system.id}
							className={styles[`logo-${system.id}`]}
							src={`/images/logos/${system.id}.png`}
							alt={system.alt}
						/>
					))}
				</div>
				<div className={styles["what-is-text"]}>
					<h2>What is Play-by-Post?</h2>
					<p>
						Play-By-Post is a different way to experience tabletop RPGs. Rather than
						dedicating a few hours at a time to sit together around a table, you can
						play at your own convenience. Log in and respond to other players and the GM
						whenever you have a few minutes to spare.
					</p>

					<p>
						Gamers' Plane offers you a PbP experience you won't get anywhere else,
						focused around a community of gamers, with tools to make the experience as
						smooth as possible. You can play with old friends, or make new ones around
						the world!
					</p>
				</div>
			</div>
			<div className={`full-width ${styles.features}`}>
				<div className={styles["features-list"]}>
					<div>
						<div className={styles.icon}>
							<i className="ra ra-three-keys" />
						</div>
						<h3>Any RPG</h3>
						<p>
							Support for <em>all</em> table top RPGs - mainstream favorites, old
							classics, indie, small press and home-brew games.
						</p>
					</div>
					<div>
						<div className={styles.icon}>
							<i className="ra ra-perspective-dice-six" />
						</div>
						<h3>Integrated tools</h3>
						<p>
							Dedicated game forums, post as your character, integrated character
							sheets, dice rollers and playing cards.
						</p>
					</div>
					<div>
						<div className={styles.icon}>
							<i className="ra ra-double-team" />
						</div>
						<h3>Community</h3>
						<p>
							A diverse and friendly community that welcomes RPG veterans and newcomers
							alike to the wonderful world of playing RPGs by Post.
						</p>
					</div>
				</div>
			</div>
		</div>
	);
}
export default Landing;
