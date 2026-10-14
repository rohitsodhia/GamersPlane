import { createFileRoute } from "@tanstack/react-router";
import { useHbMargined } from "#/lib/use-hb-margined";
import styles from "./about.module.css";

export const Route = createFileRoute("/about")({
	component: RouteComponent,
});

function RouteComponent() {
	const hbMargined = useHbMargined<HTMLHeadingElement>();

	return (
		<div className={styles["about-page"]}>
			<h1 className="headerbar" ref={hbMargined.ref}>
				About Gamers' Plane
			</h1>
			<div style={{ marginInline: `${hbMargined.margin}px` }}>
				<p>
					I played my first RPG back in high school (2000 or 2001, not sure). I don't
					remember exactly how it happened, but basically, a friend was already setting
					up character generation for a D&amp;D 3e game during lunch, and somehow I was
					invited in. I remember creating some sort of ranger, and had a blast. That
					first game led to many more over the next 3-4 years, starting with D&amp;D 3e
					and going to D&amp;D 3.5, Cthulhu, and a small variety of games. I looked
					forward to the games, to the characters, to the story.
				</p>
				<p>
					When I got to college, to game more, I decided to join a game though the RPG
					club on campus. Someone was running a Legend of the Five Rings game, and doing
					character generation at the campus center. As I found the GM, he fell right
					within the geek stereotype: heavy-set, awash with body odor, generally
					unhygienic; I was surprised to find the stereotype true. Though I had made it
					clear I didn't know the game, the GM was annoyed at my lack of knowledge. I
					also didn't own dice at the time, and though the GM had a bucket of dice
					(enough that he could have been rolling one a minute and not been through them
					by the time the game ended), he was annoyed at having to lend me a set. The
					whole experience soured me, and 20 minutes in, I excused myself to the
					bathroom and left.
				</p>
				<p>
					I decided to see what options I had for online gaming. A friend recommended
					trying play-by-post gaming through a website he was on. I found the idea neat,
					but quickly got annoyed at the lack of community on the site, and how bland it
					felt. I wasn't impressed and decided to do something about it.
				</p>
				<p>
					After many iterations and years and failures, I finally got Gamers' Plane off
					the ground at the end of 2013. Since then we've been going strong, gaining new
					players every day, and new games all the time. I'm excited to bring players
					together from around the world, and hope to keep making great tools to let
					people get into RPG gaming.
				</p>
				<p className={styles["signature"]}>Rohit</p>
				<p className={styles["signature-title"]}>Gamers' Plane's Developer</p>
			</div>
		</div>
	);
}
