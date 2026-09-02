import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link, Outlet, redirect } from "@tanstack/react-router";
import { requireAuth } from "#/lib/auth-route";
import { useHbMargined } from "#/lib/use-hb-margined";
import { hasPermission, meQueryOptions } from "#/queries/me";
import styles from "./acp.module.css";

export const Route = createFileRoute("/acp")({
	beforeLoad: requireAuth,
	loader: async ({ context }) => {
		const me = await context.queryClient
			.ensureQueryData(meQueryOptions)
			.catch(() => null);
		if (!me?.acp) {
			throw redirect({ to: "/" });
		}
	},
	component: RouteComponent,
});

function RouteComponent() {
	const hbMargined = useHbMargined<HTMLHeadingElement>();
	const { data: me } = useSuspenseQuery(meQueryOptions);

	return (
		<div>
			<h1 className="headerbar" ref={hbMargined.ref}>
				Admin Control Panel
			</h1>

			<div
				className={styles["acp-wrapper"]}
				style={{ marginInline: `${hbMargined.margin}px` }}
			>
				<nav className={styles.sidebar}>
					<h2>Menu</h2>
					<ul>
						{hasPermission(me, "admin") && (
							<li>
								<Link to="/acp/rbac">RBAC</Link>
							</li>
						)}
						{hasPermission(me, "manage_users") && (
							<li>
								<Link to="/acp/users">Users</Link>
							</li>
						)}
					</ul>
				</nav>
				<Outlet />
			</div>
		</div>
	);
}
