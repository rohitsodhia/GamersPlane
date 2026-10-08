import { useSuspenseQuery } from "@tanstack/react-query";
import {
	createFileRoute,
	Link,
	notFound,
	Outlet,
	redirect,
} from "@tanstack/react-router";
import { Fragment } from "react";
import { requireForumModerator } from "#/lib/auth-route";
import { useHbMargined } from "#/lib/use-hb-margined";
import {
	forumQueryOptions,
	hasEditableDetails,
	isGameRootForum,
} from "#/queries/forums";
import styles from "../acp.module.css";

export const Route = createFileRoute("/acp/forums/$forumId")({
	params: {
		parse: ({ forumId }) => ({ forumId: Number(forumId) }),
		stringify: ({ forumId }) => ({ forumId: String(forumId) }),
	},
	beforeLoad: ({ params }) => {
		if (Number.isNaN(params.forumId)) throw notFound();
	},
	loader: async ({ context, params }) => {
		await requireForumModerator({ context });
		const forum = await context.queryClient
			.ensureQueryData(forumQueryOptions(params.forumId))
			.catch(() => {
				throw notFound();
			});
		if (!forum.permissions.includes("forum_moderate")) {
			throw redirect({ to: "/acp/forums" });
		}
	},
	component: RouteComponent,
});

function RouteComponent() {
	const hbMargined = useHbMargined<HTMLHeadingElement>();
	const { forumId } = Route.useParams();
	const { data: forum } = useSuspenseQuery(forumQueryOptions(forumId));

	return (
		<div>
			<h2 className="headerbar" ref={hbMargined.ref}>
				{forum.id ? forum.title : "Forums"}
			</h2>
			<div style={{ marginInline: `${hbMargined.margin}px` }}>
				<div className={styles["forum-acp-breadcrumbs"]}>
					{forum.heritage.map((ancestor) => (
						<Fragment key={ancestor.id}>
							{ancestor.moderate ? (
								<Link to="/acp/forums/$forumId" params={{ forumId: ancestor.id }}>
									{ancestor.id ? ancestor.title : "Forums"}
								</Link>
							) : (
								<span>{ancestor.id ? ancestor.title : "Forums"}</span>
							)}{" "}
							{`> `}
						</Fragment>
					))}
					<span>{forum.id ? forum.title : "Forums"}</span>
				</div>
				<div className={styles["forum-acp-nav"]}>
					<nav className={styles["forum-acp-tabs"]}>
						{hasEditableDetails(forum) && (
							<Link to="/acp/forums/$forumId/details" params={{ forumId }}>
								Details
							</Link>
						)}
						<Link to="/acp/forums/$forumId/subforums" params={{ forumId }}>
							Subforums
						</Link>
						{isGameRootForum(forum) && (
							<Link to="/acp/forums/$forumId/roles" params={{ forumId }}>
								Roles
							</Link>
						)}
						<Link to="/acp/forums/$forumId/permissions" params={{ forumId }}>
							Permissions
						</Link>
					</nav>
					<div>
						<Link to="/forums/{-$forumId}" params={{ forumId }}>
							Return to forum
						</Link>
						{" | "}
						<Link to="/acp/forums">All forums</Link>
					</div>
				</div>
				<Outlet />
			</div>
		</div>
	);
}
