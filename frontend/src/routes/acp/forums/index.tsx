import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { requireForumModerator } from "#/lib/auth-route";
import { useHbMargined } from "#/lib/use-hb-margined";
import { type ModeratedForum, moderatedForumsQueryOptions } from "#/queries/forums";
import styles from "../acp.module.css";

export const Route = createFileRoute("/acp/forums/")({
	loader: async ({ context }) => {
		await requireForumModerator({ context });
		await context.queryClient.ensureQueryData(moderatedForumsQueryOptions);
	},
	component: RouteComponent,
});

function ForumNode({ forum }: { forum: ModeratedForum }) {
	const title = forum.moderate ? (
		<Link to="/acp/forums/$forumId" params={{ forumId: forum.id }}>
			{forum.title}
		</Link>
	) : (
		<span>{forum.title}</span>
	);

	if (forum.children.length === 0) {
		return <li>{title}</li>;
	}
	return (
		<li>
			<details open>
				<summary>{title}</summary>
				<ForumList forums={forum.children} />
			</details>
		</li>
	);
}

function ForumList({ forums }: { forums: ModeratedForum[] }) {
	return (
		<ul>
			{forums.map((forum) => (
				<ForumNode key={forum.id} forum={forum} />
			))}
		</ul>
	);
}

function RouteComponent() {
	const hbMargined = useHbMargined<HTMLHeadingElement>();
	const { data: forums } = useSuspenseQuery(moderatedForumsQueryOptions);

	return (
		<div>
			<h2 className="headerbar" ref={hbMargined.ref}>
				Manage Forums
			</h2>
			<div
				className={styles["forum-tree"]}
				style={{ marginInline: `${hbMargined.margin}px` }}
			>
				<ForumList forums={forums} />
			</div>
		</div>
	);
}
