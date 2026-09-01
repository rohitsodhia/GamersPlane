import { useForm } from "@tanstack/react-form";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { z } from "zod";
import { UserAutocomplete, type UserRef } from "#/components/UserAutocomplete";
import { ApiError } from "#/lib/api";
import { useHbMargined } from "#/lib/use-hb-margined";
import { createRole, rolesQueryOptions } from "#/queries/rbac";
import styles from "./acp.module.css";

export const Route = createFileRoute("/acp/rbac")({
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
	const showingGameRoles = gameRoles ?? false;
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
			if (!owner.id) {
				setCreateErrors(["An owner is required."]);
				return;
			}
			try {
				const roleId = await createRole({ name: value.name, owner_id: owner.id });
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
						<UserAutocomplete
							id="create-role-owner"
							label="Owner"
							defaultUsername={owner.username}
							onChange={setOwner}
						/>
						<createForm.Subscribe selector={(state) => state.isSubmitting}>
							{(isSubmitting) => (
								<button type="submit" className="skew-btn" disabled={isSubmitting}>
									Create
								</button>
							)}
						</createForm.Subscribe>
					</form>
				</section>
			</div>
		</div>
	);
}
