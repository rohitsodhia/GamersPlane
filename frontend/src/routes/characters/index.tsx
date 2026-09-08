import { useForm } from "@tanstack/react-form";
import { useMutation, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { FilterableListBox } from "#/components/FilterableListBox";
import { Select } from "#/components/Select";
import { ApiError } from "#/lib/api";
import { useHbMargined } from "#/lib/use-hb-margined";
import { type CharacterType, createCharacter } from "#/queries/character";
import { myCharacterSheetsQueryOptions } from "#/queries/characterSheet";

export const Route = createFileRoute("/characters/")({
	loader: async ({ context }) => {
		await context.queryClient.ensureQueryData(myCharacterSheetsQueryOptions);
	},
	component: RouteComponent,
});

const ALL_SYSTEMS = "all";

const TYPE_OPTIONS: { id: CharacterType; name: string }[] = [
	{ id: "pc", name: "PC" },
	{ id: "npc", name: "NPC" },
];

function RouteComponent() {
	const hbMarginedH1 = useHbMargined<HTMLHeadingElement>();
	const hbMarginedH2 = useHbMargined<HTMLHeadingElement>();
	const { data: sheets } = useSuspenseQuery(myCharacterSheetsQueryOptions);

	const [selectedSystem, setSelectedSystem] = useState(ALL_SYSTEMS);
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

	// Deduped systems drawn from the user's sheets, sorted by name, with an
	// "All" pseudo-option pinned to the top.
	const systems = [
		{ id: ALL_SYSTEMS, name: "All" },
		...[
			...new Map(sheets.map((sheet) => [sheet.system.id, sheet.system])).values(),
		].sort((a, b) => a.name.localeCompare(b.name)),
	];

	// Second listbox: every sheet under "All", otherwise just the chosen system's.
	const visibleSheets = sheets.filter(
		(sheet) => selectedSystem === ALL_SYSTEMS || sheet.system.id === selectedSystem,
	);

	const handleSystemChange = (systemId: string | null) => {
		const next = systemId ?? ALL_SYSTEMS;
		setSelectedSystem(next);
		// Drop the sheet selection if it no longer belongs to the chosen system.
		const currentSheetId = form.getFieldValue("characterSheetId");
		const stillVisible = sheets.some(
			(sheet) =>
				String(sheet.id) === currentSheetId &&
				(next === ALL_SYSTEMS || sheet.system.id === next),
		);
		if (!stillVisible) form.setFieldValue("characterSheetId", "");
	};

	return (
		<div>
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
				>
					<form.Field
						name="label"
						validators={{
							onBlur: ({ value }) => (value ? undefined : "Label is required."),
						}}
					>
						{(field) => (
							<div>
								<label htmlFor={field.name}>Character Label</label>
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
						)}
					</form.Field>

					<FilterableListBox
						id="system-filter"
						label="System"
						placeholder="Filter systems"
						items={systems}
						getId={(system) => system.id}
						getLabel={(system) => system.name}
						selectedId={selectedSystem}
						onChange={handleSystemChange}
						disallowEmptySelection
					/>

					<form.Field
						name="characterSheetId"
						validators={{
							onChange: ({ value }) => (value ? undefined : "You must pick a sheet."),
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
								/>
								{field.state.meta.errors[0] && (
									<div className="error">{field.state.meta.errors[0]}</div>
								)}
							</div>
						)}
					</form.Field>

					<form.Field name="type">
						{(field) => (
							<div>
								<span id="character-type-label">Type</span>
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
