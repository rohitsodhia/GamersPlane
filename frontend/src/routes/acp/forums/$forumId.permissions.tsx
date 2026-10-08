import { useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
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
	onPick,
}: {
	forumId: number;
	exclude: number[];
	onPick: (role: SiteRole) => void;
}) {
	const [results, setResults] = useState<SiteRole[]>([]);
	const searchTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

	const onInput = (value: string) => {
		clearTimeout(searchTimer.current);
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
		}, DEBOUNCE_MS);
	};

	return (
		<div>
			<label htmlFor="permission-role-search">Add a role</label>
			<Autocomplete
				id="permission-role-search"
				placeholder="Search roles"
				items={results.filter((role) => !exclude.includes(role.id))}
				getId={(role) => String(role.id)}
				getLabel={(role) => role.name}
				onInputChange={onInput}
				onAction={(pickedId, controls) => {
					const picked = results.find((role) => String(role.id) === pickedId);
					if (picked) onPick(picked);
					controls.clear();
				}}
			/>
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
	const [errors, setErrors] = useState<string[]>([]);
	const [saving, setSaving] = useState(false);
	const [saved, flashSaved] = useFlash();

	const roles = [
		...data.roles,
		...added.filter((role) => !data.roles.some((existing) => existing.id === role.id)),
	];

	const choiceFor = (role: PermissionRole, verb: string): Choice =>
		edits[`${role.id}:${verb}`] ?? role.grants[verb] ?? "inherit";

	const setChoice = (role: PermissionRole, verb: string, choice: Choice) =>
		setEdits((current) => ({ ...current, [`${role.id}:${verb}`]: choice }));

	const addRole = (picked: SiteRole) =>
		setAdded((current) => [
			...current,
			{ id: picked.id, name: picked.name, kind: "site", grants: {}, inherited: {} },
		]);

	const save = async () => {
		setErrors([]);
		setSaving(true);
		try {
			await setForumPermissions(
				forumId,
				roles.map((role) => {
					const grants: Record<string, PermissionEffect> = {};
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
			{roles.length === 0 && <p>No roles have permissions set on this forum.</p>}
			{roles.map((role) => (
				<section key={role.id} className={styles["role-section"]}>
					<h3>{roleDisplayName(role)}</h3>
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
				</section>
			))}

			<p className={styles["permission-note"]}>
				Each role works on its own. A user gets a permission if any of their roles
				allows it. Inherit takes the nearest parent forum's setting for that role. A
				role saved with every option on Inherit drops off this list.
			</p>

			{forum.game_id == null && (
				<div className={styles["role-form"]}>
					<RoleSearch
						forumId={forumId}
						exclude={roles.map((role) => role.id)}
						onPick={addRole}
					/>
				</div>
			)}

			<div className={styles["save-row"]}>
				<button type="button" className="skew-btn" disabled={saving} onClick={save}>
					Save
				</button>
				<FadeOut active={saved}>Saved</FadeOut>
			</div>
		</div>
	);
}
