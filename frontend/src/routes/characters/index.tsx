import { useForm } from "@tanstack/react-form";
import { useMutation, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { FilterableListBox } from "#/components/FilterableListBox";
import { Select } from "#/components/Select";
import { ApiError } from "#/lib/api";
import { redirectToLoginOnAuthFailure, requireAuth } from "#/lib/auth-route";
import { useHbMargined } from "#/lib/use-hb-margined";
import { type CharacterType, createCharacter } from "#/queries/character";
import { myCharacterSheetsQueryOptions } from "#/queries/characterSheet";
import styles from "./index.module.css";

export const Route = createFileRoute("/characters/")({
	beforeLoad: requireAuth,
	loader: ({ context, location }) =>
		redirectToLoginOnAuthFailure(
			context.queryClient.ensureQueryData(myCharacterSheetsQueryOptions),
			location,
		),
	component: RouteComponent,
});

const TYPE_OPTIONS: { id: CharacterType; name: string }[] = [
	{ id: "pc", name: "PC" },
	{ id: "npc", name: "NPC" },
];

function RouteComponent() {
	const hbMarginedH1 = useHbMargined<HTMLHeadingElement>();
	const hbMarginedH2 = useHbMargined<HTMLHeadingElement>();
	const { data: sheets } = useSuspenseQuery(myCharacterSheetsQueryOptions);

	const [selectedSystem, setSelectedSystem] = useState<string | null>(null);
	const [apiErrors, setApiErrors] = useState<string[]>([]);
	const [createdId, setCreatedId] = useState<number | null>(null);

	const mutation = useMutation({ mutationFn: createCharacter });

	const navigate = useNavigate();

	const form = useForm({
		defaultValues: {
			label: "",
			characterSheetId: "",
			type: "pc" as CharacterType,
		},
		onSubmit: async ({ value }) => {
			setApiErrors([]);
			setCreatedId(null);
			try {
				const result = await mutation.mutateAsync({
					label: value.label,
					character_sheet_id: Number(value.characterSheetId),
					type: value.type,
				});
				navigate({
					to: "/characters/$characterId",
					params: { characterId: result.id },
				});
			} catch (exception) {
				if (exception instanceof ApiError) {
					setApiErrors(exception.errors.map((e) => e.detail));
				}
			}
		},
	});

	// Deduped systems drawn from the user's sheets, sorted by name.
	const systems = [
		...new Map(sheets.map((sheet) => [sheet.system.id, sheet.system])).values(),
	].sort((a, b) => a.name.localeCompare(b.name));

	// Second listbox: every sheet when no system is picked, otherwise just the
	// chosen system's.
	const visibleSheets = sheets.filter(
		(sheet) => selectedSystem === null || sheet.system.id === selectedSystem,
	);

	const handleSystemChange = (systemId: string | null) => {
		setSelectedSystem(systemId);
		// Drop the sheet selection if it no longer belongs to the chosen system.
		const currentSheetId = form.getFieldValue("characterSheetId");
		const stillVisible = sheets.some(
			(sheet) =>
				String(sheet.id) === currentSheetId &&
				(systemId === null || sheet.system.id === systemId),
		);
		if (!stillVisible) {
			// Clearing the sheet here is our doing, not the user's — skip the
			// touched/validate side effects so the "pick a sheet" error doesn't
			// fire just because they chose a system. It still surfaces on submit,
			// or if the user clears a sheet themselves in the sheet list.
			form.setFieldValue("characterSheetId", "", {
				dontUpdateMeta: true,
				dontValidate: true,
			});
		}
	};

	return (
		<div className={styles["my-characters"]}>
			<h1 className="headerbar" ref={hbMarginedH1.ref}>
				My Characters
			</h1>

			<h2 className="headerbar" ref={hbMarginedH2.ref}>
				New Character
			</h2>
			<div style={{ marginInline: `${hbMarginedH2.margin}px` }}>
				{apiErrors.length > 0 && (
					<div className="banner error-banner">
						<ul>
							{apiErrors.map((error) => (
								<li key={error}>{error}</li>
							))}
						</ul>
					</div>
				)}
				{createdId !== null && <div className="banner">Character created.</div>}
				<form
					onSubmit={(e) => {
						e.preventDefault();
						form.handleSubmit();
					}}
					className="grid-layout"
				>
					<form.Field
						name="label"
						validators={{
							onBlur: ({ value }) => (value ? undefined : "Label is required."),
						}}
					>
						{(field) => (
							<div>
								<label htmlFor={field.name} className="center-vertically">
									Label
								</label>
								<div>
									<input
										id={field.name}
										name={field.name}
										type="text"
										value={field.state.value}
										onBlur={field.handleBlur}
										onChange={(e) => field.handleChange(e.target.value)}
									/>
									{field.state.meta.errors[0] && (
										<div className="error">{field.state.meta.errors[0]}</div>
									)}
								</div>
							</div>
						)}
					</form.Field>

					<form.Field name="type">
						{(field) => (
							<div>
								<span id="character-type-label" className="center-vertically">
									Type
								</span>
								<Select
									id="character-type"
									ariaLabelledBy="character-type-label"
									items={TYPE_OPTIONS}
									getId={(option) => option.id}
									getLabel={(option) => option.name}
									selectedId={field.state.value}
									onChange={(id) => field.handleChange(id as CharacterType)}
								/>
							</div>
						)}
					</form.Field>

					<div className={styles["sheet-selector"]}>
						<FilterableListBox
							id="system-filter"
							label="System"
							placeholder="Filter systems"
							items={systems}
							getId={(system) => system.id}
							getLabel={(system) => system.name}
							selectedId={selectedSystem}
							onChange={handleSystemChange}
							maxVisibleItems={5}
						/>

						<form.Field
							name="characterSheetId"
							validators={{
								onChange: ({ value }) => (value ? undefined : "You must pick a sheet."),
								onSubmit: ({ value }) => (value ? undefined : "You must pick a sheet."),
							}}
						>
							{(field) => (
								<div>
									<FilterableListBox
										id="sheet-filter"
										label="Sheets"
										placeholder="Filter sheets"
										items={visibleSheets}
										getId={(sheet) => String(sheet.id)}
										getLabel={(sheet) => sheet.name}
										selectedId={field.state.value || null}
										onChange={(id) => field.handleChange(id ?? "")}
										emptyState="No sheets"
										maxVisibleItems={5}
									/>
									{field.state.meta.errors[0] && (
										<div className="error">{field.state.meta.errors[0]}</div>
									)}
								</div>
							)}
						</form.Field>
					</div>

					<form.Subscribe selector={(state) => state.canSubmit}>
						{(canSubmit) => (
							<button
								type="submit"
								className="skew-btn"
								disabled={!canSubmit || mutation.isPending}
							>
								Save
							</button>
						)}
					</form.Subscribe>
				</form>
			</div>

			<Link to="/characters/sheets">Character Sheets</Link>
		</div>
	);
}
