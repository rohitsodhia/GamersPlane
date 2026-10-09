import { useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useBlocker } from "@tanstack/react-router";
import { useRef, useState } from "react";
import { Autocomplete } from "#/components/Autocomplete";
import { FadeOut } from "#/components/FadeOut";
import { DEBOUNCE_MS } from "#/lib/constants";
import { useFlash } from "#/lib/use-flash";
import {
	forumPermissionsQueryOptions,
	type PermissionEffect,
	type PermissionRole,
	type SiteRole,
	searchPermissionRoles,
	setForumPermissions,
} from "#/queries/forum-acp";
import { forumQueryOptions } from "#/queries/forums";
import styles from "../acp.module.css";
import { ErrorBanner, errorList } from "./-acp-shared";

export const Route = createFileRoute("/acp/forums/$forumId/permissions")({
	loader: async ({ context, params }) => {
		await Promise.all([
			context.queryClient.ensureQueryData(forumQueryOptions(params.forumId)),
			context.queryClient.ensureQueryData(forumPermissionsQueryOptions(params.forumId)),
		]);
	},
	component: RouteComponent,
});

type Choice = PermissionEffect | "inherit";

const MODERATE_VERB = "forum_moderate";

const CHOICES: { value: Choice; label: string }[] = [
	{ value: "allow", label: "Yes" },
	{ value: "inherit", label: "Inherit" },
	{ value: "deny", label: "No" },
];

const roleDisplayName = (role: PermissionRole) =>
	role.kind === "player" ? "Players" : role.name;

function RoleSearch({
	forumId,
	exclude,
	canCreateRoles,
	onPick,
}: {
	forumId: number;
	exclude: number[];
	canCreateRoles: boolean;
	onPick: (role: SiteRole) => void;
}) {
	const [results, setResults] = useState<SiteRole[]>([]);
	// Whether the last search finished, so an empty result can say so.
	const [searched, setSearched] = useState(false);
	const searchTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

	const onInput = (value: string) => {
		clearTimeout(searchTimer.current);
		setSearched(false);
		const query = value.trim();
		if (!query) {
			setResults([]);
			return;
		}
		searchTimer.current = setTimeout(async () => {
			try {
				setResults(await searchPermissionRoles(forumId, query));
			} catch {
				setResults([]);
			}
			setSearched(true);
		}, DEBOUNCE_MS);
	};

	const candidates = results.filter((role) => !exclude.includes(role.id));

	return (
		<div>
			<label htmlFor="permission-role-search">Add a role</label>
			<Autocomplete
				id="permission-role-search"
				placeholder="Search roles"
				items={candidates}
				getId={(role) => String(role.id)}
				getLabel={(role) => role.name}
				onInputChange={onInput}
				onAction={(pickedId, controls) => {
					const picked = results.find((role) => String(role.id) === pickedId);
					if (picked) onPick(picked);
					controls.clear();
				}}
			/>
			{searched && candidates.length === 0 && (
				<p className={styles["permission-note"]}>No matching roles.</p>
			)}
			<p className={styles["permission-note"]}>
				This adds an existing role.{" "}
				{canCreateRoles ? (
					<>
						New roles are created in the <Link to="/acp/rbac">Roles ACP</Link>.
					</>
				) : (
					"New roles are created by administrators."
				)}
			</p>
		</div>
	);
}

function RouteComponent() {
	const { forumId } = Route.useParams();
	const { data: forum } = useSuspenseQuery(forumQueryOptions(forumId));
	const { data } = useSuspenseQuery(forumPermissionsQueryOptions(forumId));
	const queryClient = useQueryClient();

	// Changed choices keyed by `${roleId}:${verb}`; anything absent shows what
	// the server holds. Roles picked from the search live in `added` until saved.
	const [edits, setEdits] = useState<Record<string, Choice>>({});
	const [added, setAdded] = useState<PermissionRole[]>([]);
	// Saved site roles marked for removal: hidden here, and saved with every
	// option on Inherit, which drops them off the list.
	const [removed, setRemoved] = useState<number[]>([]);
	const [errors, setErrors] = useState<string[]>([]);
	const [saving, setSaving] = useState(false);
	const [saved, flashSaved] = useFlash();

	const roles = [
		...data.roles,
		...added.filter((role) => !data.roles.some((existing) => existing.id === role.id)),
	];
	const shownRoles = roles.filter((role) => !removed.includes(role.id));

	// An edit set back to what the server holds isn't a change.
	const hasEdits = (role: PermissionRole) =>
		Object.entries(edits).some(([key, choice]) => {
			const [roleId, verb] = key.split(":");
			return (
				roleId === String(role.id) &&
				choice !== (data.roles.find((r) => r.id === role.id)?.grants[verb] ?? "inherit")
			);
		});
	const roleUnsaved = (role: PermissionRole) =>
		added.some((pending) => pending.id === role.id) || hasEdits(role);

	const dirty = removed.length > 0 || roles.some(roleUnsaved);

	// Role ids whose permissions are expanded; everything starts collapsed.
	const [openRoles, setOpenRoles] = useState<number[]>([]);
	const toggleRole = (roleId: number) =>
		setOpenRoles((current) =>
			current.includes(roleId)
				? current.filter((id) => id !== roleId)
				: [...current, roleId],
		);

	useBlocker({
		shouldBlockFn: () =>
			dirty && !window.confirm("You have unsaved permission changes. Leave anyway?"),
		enableBeforeUnload: () => dirty,
	});

	const choiceFor = (role: PermissionRole, verb: string): Choice =>
		edits[`${role.id}:${verb}`] ?? role.grants[verb] ?? "inherit";

	const setChoice = (role: PermissionRole, verb: string, choice: Choice) =>
		setEdits((current) => ({ ...current, [`${role.id}:${verb}`]: choice }));

	const addRole = (picked: SiteRole) => {
		if (removed.includes(picked.id)) {
			setRemoved((current) => current.filter((id) => id !== picked.id));
			return;
		}
		setAdded((current) => [
			...current,
			{ id: picked.id, name: picked.name, kind: "site", grants: {}, inherited: {} },
		]);
		setOpenRoles((current) => [...current, picked.id]);
	};

	const removeRole = (role: PermissionRole) => {
		if (added.some((pending) => pending.id === role.id)) {
			setAdded((current) => current.filter((pending) => pending.id !== role.id));
			return;
		}
		setRemoved((current) => [...current, role.id]);
	};

	const save = async () => {
		setErrors([]);
		setSaving(true);
		try {
			await setForumPermissions(
				forumId,
				roles.map((role) => {
					const grants: Record<string, PermissionEffect> = {};
					if (removed.includes(role.id)) return { role_id: role.id, grants };
					for (const { value: verb } of data.verbs) {
						const choice = choiceFor(role, verb);
						if (choice !== "inherit") grants[verb] = choice;
					}
					return { role_id: role.id, grants };
				}),
			);
			await queryClient.invalidateQueries({ queryKey: ["forums"] });
			// The reloaded data now holds everything that was saved; roles left on
			// Inherit throughout have dropped off it.
			setEdits({});
			setAdded([]);
			setRemoved([]);
			flashSaved();
		} catch (exception) {
			setErrors(errorList(exception));
		} finally {
			setSaving(false);
		}
	};

	return (
		<div>
			<ErrorBanner errors={errors} />
			{shownRoles.length === 0 && <p>No roles have permissions set on this forum.</p>}
			{shownRoles.map((role) => {
				const open = openRoles.includes(role.id);
				const panelId = `perm-${role.id}-panel`;
				return (
					<section key={role.id} className={styles["role-section"]}>
						<div className={styles["role-heading"]}>
							<h3>
								<button
									type="button"
									className={styles["role-toggle"]}
									aria-expanded={open}
									aria-controls={panelId}
									onClick={() => toggleRole(role.id)}
								>
									<span className={styles["role-chevron"]} aria-hidden="true" />
									{roleDisplayName(role)}
								</button>
							</h3>
							{roleUnsaved(role) && (
								<span className={styles["role-unsaved"]}>• unsaved</span>
							)}
							{/* Registered/Guest and game roles are always listed. Clearing a
						    moderate grant is admin-only, so others can't remove a
						    moderating role. */}
							{role.kind === "site" &&
								(data.can_grant_moderate ||
									role.grants[MODERATE_VERB] === undefined) && (
									<button type="button" onClick={() => removeRole(role)}>
										Remove
									</button>
								)}
						</div>
						<div id={panelId} hidden={!open}>
							{role.kind === "guest" && (
								<p className={styles["permission-note"]}>
									Guests can only ever read, since they can't post while logged out.
								</p>
							)}
							{data.verbs.map(({ value: verb, label }) => {
								const lockedOut = verb === MODERATE_VERB && !data.can_grant_moderate;
								const inherited = role.inherited[verb];
								return (
									<div key={verb}>
										<div
											className={styles["permission-row"]}
											role="radiogroup"
											aria-labelledby={`perm-${role.id}-${verb}-label`}
										>
											<span id={`perm-${role.id}-${verb}-label`}>{label}</span>
											{CHOICES.map(({ value, label: choiceLabel }) => {
												const inputId = `perm-${role.id}-${verb}-${value}`;
												return (
													<label key={value} htmlFor={inputId}>
														<input
															id={inputId}
															type="radio"
															name={`perm-${role.id}-${verb}`}
															value={value}
															checked={choiceFor(role, verb) === value}
															disabled={lockedOut}
															onChange={() => setChoice(role, verb, value)}
														/>
														{value === "inherit" && inherited !== undefined
															? `Inherit (${inherited ? "Yes" : "No"})`
															: choiceLabel}
													</label>
												);
											})}
										</div>
										{lockedOut && (
											<p className={styles["permission-note"]}>
												Only administrators can change who moderates.
											</p>
										)}
									</div>
								);
							})}
						</div>
					</section>
				);
			})}

			{forum.game_id == null && (
				<div className={styles["role-form"]}>
					<RoleSearch
						forumId={forumId}
						exclude={shownRoles.map((role) => role.id)}
						// Only admins may grant moderate, so this doubles as the admin check.
						canCreateRoles={data.can_grant_moderate}
						onPick={addRole}
					/>
				</div>
			)}

			<div className={styles["page-save"]}>
				<p className={styles["permission-note"]}>
					Each role works on its own. A user gets a permission if any of their roles
					allows it. Inherit takes the nearest parent forum's setting for that role. A
					role saved with every option on Inherit drops off this list.
				</p>
				{dirty && (
					<p className={styles["unsaved-note"]}>
						You have unsaved changes. Save to apply them.
					</p>
				)}
				<div className={styles["save-row"]}>
					<button type="button" className="skew-btn" disabled={saving} onClick={save}>
						Save permissions
					</button>
					<FadeOut active={saved}>Saved</FadeOut>
				</div>
			</div>
		</div>
	);
}
