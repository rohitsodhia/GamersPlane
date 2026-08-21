import { Link } from "@tanstack/react-router";
import { useEffect } from "react";
import { useHbMargined } from "#/lib/use-hb-margined";
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

// Placeholder entries: there's no games-list query/route in the rebuilt
// frontend yet, so this section isn't wired to live data.
const PLACEHOLDER_GAMES = [
	{ title: "The Sunless Citadel", players: "4 / 6", system: "D&D 5e", gm: "Alaric" },
	{ title: "Voidrunners", players: "3 / 5", system: "Star Wars (FFG)", gm: "Nyx" },
	{ title: "Embers of the Fate", players: "5 / 5", system: "Fate Core", gm: "Cass" },
];

function Landing() {
	const hbMargined = useHbMargined<HTMLHeadingElement>();
	const setNoGap = useLayoutStore((state) => state.setNoGap);

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
									<input type="text" placeholder="Search systems..." />
								</div>

								{PLACEHOLDER_GAMES.map((game, index) => (
									<div
										key={game.title}
										className={`${styles.game} ${index === 0 ? styles.first : ""}`}
									>
										<div className={styles.title}>
											<strong>{game.title}</strong> ({game.players})
										</div>
										<div className={styles.info}>
											<span className={styles.system}>{game.system}</span> run by{" "}
											{game.gm}
										</div>
									</div>
								))}
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
