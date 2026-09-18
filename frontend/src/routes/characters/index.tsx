import { useForm } from "@tanstack/react-form";
import {
	useMutation,
	useQuery,
	useQueryClient,
	useSuspenseQuery,
} from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { z } from "zod";
import { FilterableListBox } from "#/components/FilterableListBox";
import LoadingSpinner from "#/components/LoadingSpinner";
import Paginate from "#/components/Paginate";
import { Select } from "#/components/Select";
import { ApiError } from "#/lib/api";
import { redirectToLoginOnAuthFailure, requireAuth } from "#/lib/auth-route";
import { DEBOUNCE_MS } from "#/lib/constants";
import { useHbMargined } from "#/lib/use-hb-margined";
import {
	type CharacterType,
	createCharacter,
	myCharactersQueryOptions,
} from "#/queries/character";
import { myCharacterSheetsQueryOptions } from "#/queries/characterSheet";
import styles from "./index.module.css";

export const Route = createFileRoute("/characters/")({
	beforeLoad: requireAuth,
	validateSearch: z.object({
		page: z.number().optional(),
		search: z.string().optional(),
	}),
	// No loaderDeps, and the character list is deliberately not fetched here at
	// all: with defaultPendingMs: 0, ANY loader invocation for this route (even
	// one that resolves from cache) crosses an async boundary and paints the
	// router's full-page pendingComponent for a tick. loaderDeps on page/search
	// would re-run this loader on every debounced search navigation, causing
	// that flash on every keystroke. Leaving those out of loaderDeps means the
	// loader only runs once, on initial entry to the route — CharacterList's own
	// useQuery (not useSuspenseQuery) handles all later page/search fetches
	// entirely client-side, with keepPreviousData + isFetching driving a spinner
	// scoped to the results area instead.
	loader: ({ context, location }) => {
		return redirectToLoginOnAuthFailure(
			context.queryClient.ensureQueryData(myCharacterSheetsQueryOptions),
			location,
		);
	},
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

	const queryClient = useQueryClient();
	const mutation = useMutation({
		mutationFn: createCharacter,
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["characters", "mine"] });
		},
	});

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

			<CharacterList />

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

function CharacterList() {
	const navigate = useNavigate({ from: Route.fullPath });
	const { page: urlPage, search: urlSearch } = Route.useSearch();
	const page = urlPage ?? 1;

	// Plain useQuery (not useSuspenseQuery): with placeholderData: keepPreviousData,
	// suspense queries still suspend on every key change (search/page), which would
	// hand rendering to the router's full-page pendingComponent. useQuery instead
	// just flips isFetching and keeps rendering the previous data, so the spinner
	// stays scoped to character-results below.
	const { data, isFetching } = useQuery(
		myCharactersQueryOptions({ search: urlSearch, page }),
	);
	const characters = data?.characters ?? [];
	const total = data?.total ?? 0;

	const [searchInput, setSearchInput] = useState(urlSearch ?? "");

	// biome-ignore lint/correctness/useExhaustiveDependencies: navigate is stable and re-running on it would loop
	useEffect(() => {
		const timer = setTimeout(() => {
			navigate({
				search: (prev) => ({
					...prev,
					search: searchInput || undefined,
					page: undefined,
				}),
			});
		}, DEBOUNCE_MS);
		return () => clearTimeout(timer);
	}, [searchInput]);

	return (
		<div className={styles["character-list"]}>
			<input
				type="text"
				placeholder="Search..."
				value={searchInput}
				onChange={(e) => setSearchInput(e.target.value)}
			/>

			<div className={styles["character-results"]}>
				{isFetching && (
					<div className={styles["results-loading"]}>
						<LoadingSpinner />
					</div>
				)}

				{isFetching ? null : data && characters.length > 0 ? (
					<ul>
						{characters.map((character) => (
							<li key={character.id} className={styles["character-row"]}>
								<div className={styles.label}>
									<Link
										to="/characters/$characterId"
										params={{ characterId: character.id }}
									>
										{character.label}
									</Link>
								</div>
								<div className={styles["char-type"]}>{character.type}</div>
								<div className={styles["system-type"]}>
									{character.character_sheet.system.name}
								</div>
								<div className={styles.links}>
									<button
										type="button"
										// TODO: inline-edit label/type, mirroring the legacy editBasic flow.
										onClick={() => {}}
									>
										<img src="/images/icons/gear.png" alt="Edit Label/Type" />
									</button>
									<button
										type="button"
										// TODO: wire up once a library/favorites concept exists for the new Character model.
										onClick={() => {}}
									>
										<img src="/images/icons/bookmark_off.png" alt="Add to Library" />
									</button>
									<button
										type="button"
										// TODO: wire up once a delete endpoint exists for characters.
										onClick={() => {}}
									>
										<img src="/images/icons/cross.png" alt="Delete Character" />
									</button>
								</div>
							</li>
						))}
					</ul>
				) : !isFetching && data ? (
					<div className={styles["no-results"]}>
						{urlSearch
							? "No characters match your search."
							: "You have no characters yet."}
					</div>
				) : null}
			</div>

			<Paginate numItems={total} current={page} onPageChange={() => {}} />
		</div>
	);
}
