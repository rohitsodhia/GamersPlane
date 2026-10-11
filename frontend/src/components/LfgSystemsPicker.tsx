import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Checkbox } from "#/components/Checkbox";
import { FilterableListBox } from "#/components/FilterableListBox";
import { ApiError } from "#/lib/api";
import {
	lfgSystemsQueryOptions,
	meFullQueryOptions,
	refreshMe,
	updateLfgSystems,
	updateUserSettings,
} from "#/queries/me";
import { type BasicSystem, systemsQueryOptions } from "#/queries/systems";
import styles from "./LfgSystemsPicker.module.css";

/**
 * Edits the systems the user wants new-game notifications for, with the
 * `newGameMail` toggle beside it. Every instance shares one query, so a save in
 * one updates the rest. Pass `showMailToggle={false}` where `newGameMail` is
 * already a field of the surrounding form.
 */
export function LfgSystemsPicker({
	idPrefix,
	showMailToggle = true,
}: {
	idPrefix: string;
	showMailToggle?: boolean;
}) {
	const queryClient = useQueryClient();
	const { data: lfg, isError: lfgError } = useQuery(lfgSystemsQueryOptions);
	const { data: systems } = useQuery(systemsQueryOptions({ basic: true }));
	const { data: me } = useQuery(meFullQueryOptions);

	// null while reading; while editing, the draft system ids and the item order
	// (fixed when edit mode opens).
	const [editing, setEditing] = useState<{
		ids: string[];
		items: BasicSystem[];
	} | null>(null);
	const draft = editing?.ids ?? [];
	const [errors, setErrors] = useState<string[]>([]);

	const saveMutation = useMutation({
		mutationFn: updateLfgSystems,
		onSuccess: (data) => {
			queryClient.setQueryData(lfgSystemsQueryOptions.queryKey, data);
			setEditing(null);
		},
		onError: (exception) => {
			setErrors(
				exception instanceof ApiError
					? exception.errors.map((error) => error.detail)
					: ["Couldn't save your systems. Please try again."],
			);
		},
	});

	const mailMutation = useMutation({
		mutationFn: (newGameMail: boolean) => updateUserSettings({ newGameMail }),
		onSuccess: () => refreshMe(queryClient),
	});

	const selected = lfg?.systems ?? [];
	const startEditing = () => {
		setErrors([]);
		// A system disabled since it was picked would fail the API's validation, so
		// leave it out of the editable set.
		const all = systems ?? [];
		const enabled = new Set(all.map((system) => system.id));
		const ids = selected.map((system) => system.id).filter((id) => enabled.has(id));
		// Selected systems first, fixed for this edit session so rows don't jump
		// as they're toggled.
		const chosen = new Set(ids);
		setEditing({
			ids,
			items: [
				...all.filter((system) => chosen.has(system.id)),
				...all.filter((system) => !chosen.has(system.id)),
			],
		});
	};

	const cancel = () => {
		setErrors([]);
		setEditing(null);
	};

	const mailToggle = showMailToggle && (
		<div className={styles["mail-toggle"]}>
			<Checkbox
				id={`${idPrefix}-new-game-mail`}
				checked={me?.newGameMail === true}
				disabled={me === undefined || mailMutation.isPending}
				onChange={(checked) => mailMutation.mutate(checked)}
			/>
			<label htmlFor={`${idPrefix}-new-game-mail`}>
				Email me when a game opens in these systems
			</label>
			{mailMutation.isError && (
				<div className="error">Couldn't update your email preference.</div>
			)}
		</div>
	);

	if (editing === null) {
		return (
			<div className={styles["picker"]}>
				{lfgError ? (
					<div className="error">Couldn't load your systems.</div>
				) : selected.length === 0 ? (
					<p className={styles["nudge"]}>
						Get notified when a game opens in systems you like.
					</p>
				) : (
					<ul className={styles["systems"]}>
						{selected.map((system) => (
							<li key={system.id}>{system.name}</li>
						))}
					</ul>
				)}
				<button type="button" className="skew-btn" onClick={startEditing}>
					Edit
				</button>
				{mailToggle}
			</div>
		);
	}

	return (
		<div className={styles["picker"]}>
			{errors.length > 0 && (
				<div className="banner error-banner">
					<ul>
						{errors.map((error) => (
							<li key={error}>{error}</li>
						))}
					</ul>
				</div>
			)}
			<FilterableListBox
				selectionMode="multiple"
				id={`${idPrefix}-lfg-systems`}
				label="Systems"
				placeholder="Filter systems..."
				items={editing.items}
				getId={(system: BasicSystem) => system.id}
				getLabel={(system: BasicSystem) => system.name}
				selectedIds={draft}
				onChange={(ids) => setEditing((prev) => (prev ? { ...prev, ids } : prev))}
				maxVisibleItems={8}
			/>
			<div className={styles["count"]} aria-live="polite">
				{draft.length} selected
			</div>
			<div className={styles["actions"]}>
				<button
					type="button"
					className="skew-btn"
					disabled={saveMutation.isPending}
					onClick={() => {
						setErrors([]);
						saveMutation.mutate(draft);
					}}
				>
					Save
				</button>
				<button
					type="button"
					className="skew-btn"
					disabled={saveMutation.isPending}
					onClick={cancel}
				>
					Cancel
				</button>
			</div>
			{mailToggle}
		</div>
	);
}
