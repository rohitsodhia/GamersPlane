import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import type { GameListItem } from "#/queries/game";
import styles from "./-game-row.module.css";

type Favorite = {
	favorited: boolean;
	onToggle: () => void;
	pending: boolean;
};

export function GameRow({
	game,
	favorite,
	end,
}: {
	game: GameListItem;
	favorite?: Favorite;
	end?: ReactNode;
}) {
	return (
		<li>
			<span className={styles["game-title"]}>
				{favorite && (
					<button
						type="button"
						className={styles.favorite}
						onClick={favorite.onToggle}
						disabled={favorite.pending}
						title={favorite.favorited ? "Unfavorite" : "Favorite"}
					>
						<img
							src={
								favorite.favorited
									? "/images/icons/bookmark_on.png"
									: "/images/icons/bookmark_off.png"
							}
							alt={favorite.favorited ? "Unfavorite" : "Favorite"}
						/>
					</button>
				)}
				<Link to="/games/$gameId" params={{ gameId: game.id }}>
					{game.title}
				</Link>
			</span>
			<div className={styles["system-type"]}>{game.system}</div>
			<div className={styles["gm-info"]}>
				<Link to="/user/$userId" params={{ userId: game.gm.id }} className="username">
					{game.gm.username}
				</Link>
			</div>
			{end}
		</li>
	);
}
