import { Link } from "@tanstack/react-router";
import { Fragment } from "react";
import type { Forum } from "#/queries/forums";

export function Breadcrumbs({ forum }: { forum: Forum }) {
	if (!forum.heritage.length) return null;

	return (
		<div id="forums_breadcrumbs">
			{forum.heritage.map((heritageForum) => (
				<Fragment key={heritageForum.id}>
					<Link to="/forums/{-$forumId}" params={{ forumId: heritageForum.id }}>
						{heritageForum.title}
					</Link>{" "}
					{`> `}
				</Fragment>
			))}
			<Link to="/forums/{-$forumId}" params={{ forumId: forum.id }}>
				{forum.title}
			</Link>
		</div>
	);
}
