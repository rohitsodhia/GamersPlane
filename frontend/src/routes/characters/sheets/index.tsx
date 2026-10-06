import { useForm } from "@tanstack/react-form";
import {
	useMutation,
	useQuery,
	useQueryClient,
	useSuspenseQuery,
} from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { z } from "zod";
import { Autocomplete } from "#/components/Autocomplete";
import { ConfirmDeleteButton } from "#/components/ConfirmDeleteButton";
import { ListFilters, singleSystemFilterSearchSchema } from "#/components/ListFilters";
import { ListResults } from "#/components/ListResults";
import { RowList, RowListItem, rowLinksClassName } from "#/components/RowList";
import { ApiError } from "#/lib/api";
import { requireAuth } from "#/lib/auth-route";
import { removeFromCachedLists } from "#/lib/cached-lists";
import { useHbMargined } from "#/lib/use-hb-margined";
import {
	createCharacterSheet,
	deleteCharacterSheet,
	myCharacterSheetsListQueryOptions,
	toggleCharacterSheetFavorite,
} from "#/queries/characterSheet";
import { meQueryOptions } from "#/queries/me";
import { type BasicSystem, systemsQueryOptions } from "#/queries/systems";
import styles from "../list-page.module.css";

export const Route = createFileRoute("/characters/sheets/")({
	beforeLoad: requireAuth,
	validateSearch: singleSystemFilterSearchSchema.extend({
		page: z.number().optional(),
	}),
	// As in /characters: no loaderDeps and the list isn't fetched here, so
	// search/page changes never re-run the loader (which would flash the
	// router's pending component). SheetList's own useQuery handles them.
	loader: async ({ context }) => {
		await context.queryClient.ensureQueryData(systemsQueryOptions({ basic: true }));
	},
	component: RouteComponent,
});

function RouteComponent() {
	const hbMarginedH1 = useHbMargined<HTMLHeadingElement>();
	const hbMarginedH2 = useHbMargined<HTMLHeadingElement>();
	const navigate = useNavigate();
	const { data: systems } = useSuspenseQuery(systemsQueryOptions({ basic: true }));
	const mutation = useMutation({ mutationFn: createCharacterSheet });
	const [apiErrors, setApiErrors] = useState<string[]>([]);

	const form = useForm({
		defaultValues: {
			name: "",
			systemId: "",
		},
		onSubmit: async ({ value }) => {
			setApiErrors([]);
			try {
				const result = await mutation.mutateAsync({
					name: value.name,
					system_id: value.systemId,
				});
				navigate({
					to: "/characters/sheets/$sheetId",
					params: { sheetId: result.id },
				});
			} catch (exception) {
				if (exception instanceof ApiError) {
					setApiErrors(exception.errors.map((e) => e.detail));
				}
			}
		},
	});

	return (
		<div className={styles["list-page"]}>
			<h1 className="headerbar" ref={hbMarginedH1.ref}>
				My Character Sheets
			</h1>

			<div className={styles["top-links"]}>
				<Link to="/characters/sheets/library" className="skew-btn">
					Character Sheet Library
				</Link>
			</div>

			<div style={{ marginInline: `${hbMarginedH1.margin}px` }}>
				<SheetList />
			</div>

			<h2 className="headerbar" ref={hbMarginedH2.ref}>
				New Sheet
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
				<form
					onSubmit={(e) => {
						e.preventDefault();
						form.handleSubmit();
					}}
					className="grid-layout"
				>
					<form.Field
						name="name"
						validators={{
							onBlur: ({ value }) => (value ? undefined : "Label is required."),
						}}
					>
						{(field) => (
							<div>
								<label htmlFor={field.name} className="center-vertically">
									Name
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

					<form.Field
						name="systemId"
						validators={{
							onChange: ({ value }) => (value ? undefined : "You must pick a system."),
						}}
					>
						{(field) => (
							<div>
								<label htmlFor="system-combo" className="center-vertically">
									System
								</label>
								<div>
									<Autocomplete
										id="system-combo"
										items={systems}
										getId={(system: BasicSystem) => system.id}
										getLabel={(system: BasicSystem) => system.name}
										onAction={(id) => field.handleChange(id)}
									/>
									{field.state.meta.errors[0] && (
										<div className="error">{field.state.meta.errors[0]}</div>
									)}
								</div>
							</div>
						)}
					</form.Field>

					<form.Subscribe selector={(state) => state.canSubmit}>
						{(canSubmit) => (
							<div className="is-container">
								<button
									type="submit"
									className="skew-btn"
									disabled={!canSubmit || mutation.isPending}
								>
									Create
								</button>
							</div>
						)}
					</form.Subscribe>
				</form>
			</div>
		</div>
	);
}

function SheetList() {
	const {
		page: urlPage,
		search: urlSearch,
		system_id: urlSystemId,
	} = Route.useSearch();
	const page = urlPage ?? 1;
	const { data: me } = useQuery(meQueryOptions);

	const { data, isFetching, isError } = useQuery(
		myCharacterSheetsListQueryOptions({
			search: urlSearch,
			system_id: urlSystemId,
			page,
		}),
	);
	// A failed (re)fetch leaves react-query holding the last successful data;
	// don't render it as if it were current.
	const shown = isError ? undefined : data;
	const sheets = shown?.char_sheets ?? [];

	// Also discard the single-sheet query so a stale copy isn't served, and
	// invalidate the unfiltered list behind the New Character picker so it stops
	// offering the deleted sheet.
	const queryClient = useQueryClient();
	const deleteMutation = useMutation({
		mutationFn: deleteCharacterSheet,
		onSuccess: (_data, sheetId) => {
			removeFromCachedLists(
				queryClient,
				["characterSheets", "mine"],
				"char_sheets",
				sheetId,
			);
			queryClient.removeQueries({ queryKey: ["characterSheet", sheetId] });
			queryClient.invalidateQueries({ queryKey: ["characterSheets", "my"] });
		},
	});

	// Unfavoriting removes the row (and shifts pagination), so refetch the
	// list; the unfiltered "my" list and the library's favorited flags are
	// stale too.
	const unfavoriteMutation = useMutation({
		mutationFn: toggleCharacterSheetFavorite,
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["characterSheets", "mine"] });
			queryClient.invalidateQueries({ queryKey: ["characterSheets", "my"] });
			queryClient.invalidateQueries({ queryKey: ["characterSheets", "library"] });
		},
	});

	return (
		<div className={styles["results"]}>
			<ListFilters filters={["search", "system"]} idPrefix="sheets" />

			<ListResults
				isFetching={isFetching}
				isError={isError}
				hasResults={sheets.length > 0}
				total={shown?.total ?? 0}
				page={page}
				errorMessage="Could not load your character sheets. Please try again."
				emptyMessage={
					urlSearch || urlSystemId
						? "No character sheets match your filters."
						: "You have no character sheets yet."
				}
			>
				<RowList columns="1fr auto auto">
					{sheets.map((sheet) => {
						const favoritedOnly = me !== undefined && sheet.creator.id !== me.id;
						return (
							<RowListItem key={sheet.id} favorited={favoritedOnly}>
								<div>
									<Link to="/characters/sheets/$sheetId" params={{ sheetId: sheet.id }}>
										{sheet.name}
									</Link>
								</div>
								<div>{sheet.system.name}</div>
								<div className={rowLinksClassName}>
									{favoritedOnly ? (
										<button
											type="button"
											disabled={
												unfavoriteMutation.isPending &&
												unfavoriteMutation.variables === sheet.id
											}
											onClick={() => unfavoriteMutation.mutate(sheet.id)}
										>
											<img src="/images/icons/bookmark_on.png" alt="Favorited" />
										</button>
									) : (
										<ConfirmDeleteButton
											label="Delete Sheet"
											message="Deleting this sheet removes it from the sheet library and from anyone's favorites. Characters already built on it will keep working."
											isDisabled={deleteMutation.isPending}
											onConfirm={() => deleteMutation.mutate(sheet.id)}
										/>
									)}
								</div>
							</RowListItem>
						);
					})}
				</RowList>
			</ListResults>
		</div>
	);
}
