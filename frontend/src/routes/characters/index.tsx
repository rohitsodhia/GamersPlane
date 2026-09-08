import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { FilterableListBox } from "#/components/FilterableListBox";
import { useHbMargined } from "#/lib/use-hb-margined";
import {
	type BasicCharacterSheet,
	myCharacterSheetsQueryOptions,
} from "#/queries/characterSheet";

export const Route = createFileRoute("/characters/")({
	loader: async ({ context }) => {
		await context.queryClient.ensureQueryData(myCharacterSheetsQueryOptions);
	},
	component: RouteComponent,
});

const ALL_SYSTEMS = "all";

function RouteComponent() {
	const hbMarginedH1 = useHbMargined<HTMLHeadingElement>();
	const hbMarginedH2 = useHbMargined<HTMLHeadingElement>();
	const { data: sheets } = useSuspenseQuery(myCharacterSheetsQueryOptions);

	const [selectedSystem, setSelectedSystem] = useState(ALL_SYSTEMS);
	const [selectedSheet, setSelectedSheet] = useState<string | null>(null);

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
		const stillVisible = sheets.some(
			(sheet: BasicCharacterSheet) =>
				String(sheet.id) === selectedSheet &&
				(next === ALL_SYSTEMS || sheet.system.id === next),
		);
		if (!stillVisible) setSelectedSheet(null);
	};

	return (
		<div>
			<h1 className="headerbar" ref={hbMarginedH1.ref}>
				My Characters
			</h1>

			<h2 className="headerbar" ref={hbMarginedH2.ref}>
				New Character
			</h2>
			<form style={{ marginInline: `${hbMarginedH2.margin}px` }}>
				<label htmlFor="character-label">Character Label</label>
				<input id="character-label" type="text" name="label" />

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

				<FilterableListBox
					id="sheet-filter"
					label="Sheets"
					placeholder="Filter sheets"
					items={visibleSheets}
					getId={(sheet) => String(sheet.id)}
					getLabel={(sheet) => sheet.name}
					selectedId={selectedSheet}
					onChange={setSelectedSheet}
					emptyState="No sheets"
				/>
				<button type="button" className="skew-btn">
					Save
				</button>
			</form>

			<Link to="/characters/sheets">Character Sheets</Link>
		</div>
	);
}
