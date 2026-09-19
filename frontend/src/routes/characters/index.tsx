import { useForm } from "@tanstack/react-form";
import {
	useMutation,
	useQuery,
	useQueryClient,
	useSuspenseQuery,
} from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Button, Dialog, DialogTrigger, Popover } from "react-aria-components";
import { z } from "zod";
import { Autocomplete } from "#/components/Autocomplete";
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
	deleteCharacter,
	type GetCharactersResponse,
	myCharactersQueryOptions,
	toggleCharacterLibrary,
} from "#/queries/character";
import { myCharacterSheetsQueryOptions } from "#/queries/characterSheet";
import styles from "./index.module.css";

export const Route = createFileRoute("/characters/")({
	beforeLoad: requireAuth,
	validateSearch: z.object({
		page: z.number().optional(),
		search: z.string().optional(),
		type: z.enum(["pc", "npc"]).optional(),
		system_id: z.string().optional(),
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

			<div style={{ marginInline: `${hbMarginedH1.margin}px` }}>
				<CharacterList systems={systems} />
			</div>

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

function CharacterList({ systems }: { systems: { id: string; name: string }[] }) {
	const navigate = useNavigate({ from: Route.fullPath });
	const {
		page: urlPage,
		search: urlSearch,
		type: urlType,
		system_id: urlSystemId,
	} = Route.useSearch();
	const page = urlPage ?? 1;

	// Plain useQuery (not useSuspenseQuery): with placeholderData: keepPreviousData,
	// suspense queries still suspend on every key change (search/page), which would
	// hand rendering to the router's full-page pendingComponent. useQuery instead
	// just flips isFetching and keeps rendering the previous data, so the spinner
	// stays scoped to character-results below.
	const { data, isFetching, isError } = useQuery(
		myCharactersQueryOptions({
			search: urlSearch,
			type: urlType,
			system_id: urlSystemId,
			page,
		}),
	);
	// A failed (re)fetch leaves react-query holding the last successful data;
	// don't render it as if it were current.
	const shown = isError ? undefined : data;
	const characters = shown?.characters ?? [];
	const total = shown?.total ?? 0;

	// Flip in_library in the cached lists in place rather than invalidating: a
	// refetch sets isFetching, which would swap the whole list for the spinner.
	const queryClient = useQueryClient();
	const toggleLibraryMutation = useMutation({
		mutationFn: toggleCharacterLibrary,
		onSuccess: (_data, characterId) => {
			queryClient.setQueriesData<GetCharactersResponse>(
				{ queryKey: ["characters", "mine"] },
				(old) =>
					old && {
						...old,
						characters: old.characters.map((character) =>
							character.id === characterId
								? { ...character, in_library: !character.in_library }
								: character,
						),
					},
			);
			queryClient.invalidateQueries({ queryKey: ["character", characterId] });
		},
	});

	// Drop the row from the cached lists in place (same reasoning as above) and
	// discard the single-character query so a stale copy isn't served.
	const deleteMutation = useMutation({
		mutationFn: deleteCharacter,
		onSuccess: (_data, characterId) => {
			queryClient.setQueriesData<GetCharactersResponse>(
				{ queryKey: ["characters", "mine"] },
				(old) =>
					old && {
						...old,
						characters: old.characters.filter(
							(character) => character.id !== characterId,
						),
						total: Math.max(0, old.total - 1),
					},
			);
			queryClient.removeQueries({ queryKey: ["character", characterId] });
		},
	});

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
			<div className={styles["character-filters"]}>
				<input
					type="text"
					placeholder="Search..."
					value={searchInput}
					onChange={(e) => setSearchInput(e.target.value)}
				/>

				<Autocomplete
					id="character-type-filter"
					className={styles["type-filter"]}
					items={TYPE_OPTIONS}
					getId={(option) => option.id}
					getLabel={(option) => option.name}
					placeholder="Type"
					onAction={(id) => {
						navigate({
							search: (prev) => ({
								...prev,
								type: id as CharacterType,
								page: undefined,
							}),
						});
					}}
					onClear={() => {
						navigate({
							search: (prev) => ({ ...prev, type: undefined, page: undefined }),
						});
					}}
				/>

				<Autocomplete
					id="character-system-filter"
					items={systems}
					getId={(option) => option.id}
					getLabel={(option) => option.name}
					placeholder="System"
					onAction={(id) => {
						navigate({
							search: (prev) => ({
								...prev,
								system_id: id,
								page: undefined,
							}),
						});
					}}
					onClear={() => {
						navigate({
							search: (prev) => ({ ...prev, system_id: undefined, page: undefined }),
						});
					}}
				/>
			</div>

			<div className={styles["character-results"]}>
				{isFetching && (
					<div className={styles["results-loading"]}>
						<LoadingSpinner />
					</div>
				)}

				{isFetching ? null : isError ? (
					<div className="banner error-banner">
						Could not load your characters. Please try again.
					</div>
				) : shown && characters.length > 0 ? (
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
								<div className={styles["char-type"]}>
									{character.type.toLocaleUpperCase()}
								</div>
								<div className={styles["system-type"]}>
									{character.character_sheet.system.name}
								</div>
								<div className={styles.links}>
									<button
										type="button"
										disabled={toggleLibraryMutation.isPending}
										onClick={() => toggleLibraryMutation.mutate(character.id)}
									>
										{character.in_library ? (
											<img
												src="/images/icons/library_on.png"
												alt="Remove from library"
											/>
										) : (
											<img src="/images/icons/library_off.png" alt="Add to Library" />
										)}
									</button>
									<DialogTrigger>
										<Button isDisabled={deleteMutation.isPending}>
											<img src="/images/icons/cross.png" alt="Delete Character" />
										</Button>
										<Popover
											className={`react-aria-Popover ${styles["confirm-popover"]}`}
											placement="bottom end"
										>
											<Dialog
												aria-label="Confirm delete"
												className={styles["confirm-delete"]}
											>
												{({ close }) => (
													<>
														<p>
															Deleting this character will remove it from the character
															library, if added. It will also be removed from any game
															it's currently in.
														</p>
														<div className={styles["confirm-actions"]}>
															<button
																type="button"
																className="skew-btn"
																onClick={() => {
																	deleteMutation.mutate(character.id);
																	close();
																}}
															>
																Confirm
															</button>
															<button
																type="button"
																className="skew-btn"
																onClick={close}
															>
																Cancel
															</button>
														</div>
													</>
												)}
											</Dialog>
										</Popover>
									</DialogTrigger>
								</div>
							</li>
						))}
					</ul>
				) : !isFetching && shown ? (
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
