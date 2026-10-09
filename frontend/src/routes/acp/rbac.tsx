import { useForm } from "@tanstack/react-form";
import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { z } from "zod";
import { UserAutocomplete, type UserRef } from "#/components/UserAutocomplete";
import { ApiError } from "#/lib/api";
import { requireRoleAdmin } from "#/lib/auth-route";
import { useHbMargined } from "#/lib/use-hb-margined";
import { hasPermission, meQueryOptions } from "#/queries/me";
import { createRole, rolesQueryOptions } from "#/queries/rbac";
import styles from "./acp.module.css";

export const Route = createFileRoute("/acp/rbac")({
	loader: requireRoleAdmin,
	component: RouteComponent,
	validateSearch: z.object({
		gameRoles: z.boolean().optional().catch(undefined),
	}),
});

const emptyOwner: UserRef = { username: "", id: null };

function errorList(exception: unknown): string[] {
	if (exception instanceof ApiError) return exception.errors.map((e) => e.detail);
	return ["Something went wrong."];
}

function RouteComponent() {
	const hbMargined = useHbMargined<HTMLHeadingElement>();
	const navigate = useNavigate();
	const { gameRoles } = Route.useSearch();
	const { data: me } = useSuspenseQuery(meQueryOptions);
	// Admins and site moderators create roles; owners and role admins just manage
	// theirs. Only admins pick the owner, everyone else owns what they make.
	const siteModerate = me.siteModerate;
	const admin = hasPermission(me, "admin");
	// The game roles list is an admin overview; GMs manage theirs from the game
	// forum's Roles tab.
	const showingGameRoles = admin && (gameRoles ?? false);
	const {
		data: roles,
		isPending,
		isError,
		refetch,
	} = useQuery(rolesQueryOptions(undefined, showingGameRoles));

	const [owner, setOwner] = useState<UserRef>(emptyOwner);
	const [createErrors, setCreateErrors] = useState<string[]>([]);
	const createForm = useForm({
		defaultValues: { name: "" },
		onSubmit: async ({ value }) => {
			setCreateErrors([]);
			if (admin && !owner.id) {
				setCreateErrors(["An owner is required."]);
				return;
			}
			try {
				const roleId = await createRole({
					name: value.name,
					...(admin && owner.id && { owner_id: owner.id }),
				});
				createForm.reset();
				setOwner(emptyOwner);
				await refetch();
				await navigate({ to: "/acp/role/$roleId", params: { roleId } });
			} catch (exception) {
				setCreateErrors(errorList(exception));
			}
		},
	});

	return (
		<div>
			<h2 className="headerbar" ref={hbMargined.ref}>
				Roles
			</h2>
			<div style={{ marginInline: `${hbMargined.margin}px` }}>
				{admin && (
					<button
						type="button"
						className={styles["roles-switch-btn"]}
						onClick={() =>
							navigate({
								to: "/acp/rbac",
								search: showingGameRoles ? {} : { gameRoles: true },
							})
						}
					>
						{showingGameRoles ? "Switch to non-Game roles" : "Switch to Game roles"}
					</button>
				)}
				{isPending && <div className="loading">Loading...</div>}
				{isError && <div>Failed to load roles.</div>}
				{roles && roles.length === 0 && <div>No roles</div>}
				{roles && roles.length > 0 && (
					<ul className={styles["role-list"]}>
						{roles.map((role) => (
							<li key={role.id}>
								<div>
									<Link to="/acp/role/$roleId" params={{ roleId: role.id }}>
										{role.name}
									</Link>
									<span>
										Owner:{" "}
										<Link to="/user/$userId" params={{ userId: role.owner.id }}>
											{role.owner.username}
										</Link>
									</span>
								</div>
								<div>
									<span>
										{role.user_count} user{role.user_count === 1 ? "" : "s"}
									</span>
									<span>
										{role.grant_count} grant{role.grant_count === 1 ? "" : "s"}
									</span>
								</div>
							</li>
						))}
					</ul>
				)}

				{siteModerate && (
					<section className={styles["role-section"]}>
						<h3>Create role</h3>
						{createErrors.length > 0 && (
							<div className="banner error-banner">
								<ul>
									{createErrors.map((error) => (
										<li key={error}>{error}</li>
									))}
								</ul>
							</div>
						)}
						<form
							className={styles["role-form"]}
							onSubmit={(e) => {
								e.preventDefault();
								createForm.handleSubmit();
							}}
						>
							<createForm.Field name="name">
								{(field) => (
									<div>
										<label htmlFor={field.name}>Name</label>
										<input
											id={field.name}
											name={field.name}
											type="text"
											maxLength={48}
											value={field.state.value}
											onBlur={field.handleBlur}
											onChange={(e) => field.handleChange(e.target.value)}
										/>
									</div>
								)}
							</createForm.Field>
							{admin && (
								<UserAutocomplete
									id="create-role-owner"
									label="Owner"
									defaultUsername={owner.username}
									onChange={setOwner}
								/>
							)}
							<createForm.Subscribe selector={(state) => state.isSubmitting}>
								{(isSubmitting) => (
									<button type="submit" className="skew-btn" disabled={isSubmitting}>
										Create
									</button>
								)}
							</createForm.Subscribe>
						</form>
					</section>
				)}
			</div>
		</div>
	);
}
