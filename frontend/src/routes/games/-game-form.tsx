import { useForm } from "@tanstack/react-form";
import { useMutation, useSuspenseQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import type { JSONContent } from "@tiptap/core";
import clsx from "clsx";
import { useState } from "react";
import { Autocomplete } from "#/components/Autocomplete";
import { Checkbox } from "#/components/Checkbox";
import Editor, { emptyContent, isContentEmpty } from "#/components/Editor";
import { Select } from "#/components/Select";
import { ApiError } from "#/lib/api";
import { useHbMargined } from "#/lib/use-hb-margined";
import { createGame, type GameDetails, updateGame } from "#/queries/game";
import { type BasicSystem, systemsQueryOptions } from "#/queries/systems";
import { AdvancedOptions } from "./-advanced-options";
import styles from "./-game-form.module.css";

function FieldError({ message }: { message: string | undefined }) {
	if (!message) return null;
	return <>{message}</>;
}

export function GameForm({ title, game }: { title: string; game?: GameDetails }) {
	const navigate = useNavigate();
	const { data: systems } = useSuspenseQuery(systemsQueryOptions({ basic: true }));
	const mutation = useMutation({
		mutationFn: game
			? (data: Parameters<typeof updateGame>[1]) => updateGame(game.id, data)
			: createGame,
	});
	const [apiErrors, setApiErrors] = useState<string[]>([]);

	const charSheetSystems = systems.filter((system) => system.has_char_sheet);

	const form = useForm({
		defaultValues: {
			title: game?.title ?? "",
			systemId: game?.system ?? "custom",
			allowedCharSheets: game?.allowed_char_sheets ?? ([] as string[]),
			timesPer: game?.post_frequency.times_per ?? 1,
			perPeriod: game?.post_frequency.per_period ?? ("d" as "d" | "w"),
			numPlayers: game?.num_players ?? 2,
			charsPerPlayer: game?.chars_per_player ?? 1,
			description: (game?.description ?? emptyContent) as JSONContent,
			charGenInfo: (game?.char_gen_info ?? emptyContent) as JSONContent,
			isPublic: game?.public ?? true,
			recruitmentThreadId: game?.recruitment_thread_id
				? String(game.recruitment_thread_id)
				: "",
			advancedOptions: (game?.advanced_options ?? {}) as Record<string, unknown>,
		},
		onSubmit: async ({ value }) => {
			setApiErrors([]);
			try {
				const result = await mutation.mutateAsync({
					title: value.title,
					system_id: value.systemId,
					allowed_char_sheets: value.allowedCharSheets,
					post_frequency: `${value.timesPer}/${value.perPeriod}`,
					num_players: value.numPlayers,
					chars_per_player: value.charsPerPlayer,
					description: isContentEmpty(value.description) ? null : value.description,
					char_gen_info: isContentEmpty(value.charGenInfo) ? null : value.charGenInfo,
					public: value.isPublic,
					recruitment_thread_id: value.recruitmentThreadId
						? Number(value.recruitmentThreadId)
						: null,
					advanced_options: Object.keys(value.advancedOptions).length
						? value.advancedOptions
						: null,
				});
				navigate({ to: "/games/$gameId", params: { gameId: result.id } });
			} catch (exception) {
				if (exception instanceof ApiError) {
					setApiErrors(exception.errors.map((e) => e.detail));
				}
			}
		},
	});

	const hbMargined = useHbMargined<HTMLHeadingElement>();

	return (
		<div>
			<h1 className="headerbar" ref={hbMargined.ref}>
				{title}
			</h1>
			<div style={{ marginInline: `${hbMargined.margin}px` }}>
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
					className={`grid-layout ${styles["game-form"]}`}
				>
					<form.Field
						name="title"
						validators={{
							onBlur: ({ value }) => {
								if (!value) return "Title is required.";
								if (value.length > 50) return "Title must be 50 characters or fewer.";
								return undefined;
							},
						}}
					>
						{(field) => (
							<div>
								<label htmlFor={field.name}>Title:</label>
								<div>
									<input
										id={field.name}
										name={field.name}
										type="text"
										maxLength={50}
										value={field.state.value}
										onBlur={field.handleBlur}
										onChange={(e) => field.handleChange(e.target.value)}
										className={clsx(
											styles["input-field"],
											field.state.meta.isValid ? "" : "field-invalid",
										)}
									/>
									{field.state.meta.errors[0] && (
										<div className="error">
											<FieldError message={field.state.meta.errors[0]} />
										</div>
									)}
								</div>
							</div>
						)}
					</form.Field>

					<form.Field name="systemId">
						{(field) => (
							<div>
								<label htmlFor={field.name}>System:</label>
								<div>
									<Select
										id={field.name}
										items={systems}
										getId={(system: BasicSystem) => system.id}
										getLabel={(system: BasicSystem) => system.name}
										selectedId={field.state.value}
										onChange={(newSystemId) => {
											const oldSystemId = field.state.value;
											field.handleChange(newSystemId);
											form.setFieldValue("allowedCharSheets", (prev) => {
												const withoutOld = prev.filter((id) => id !== oldSystemId);
												const newSystemHasCharSheet = charSheetSystems.some(
													(system) => system.id === newSystemId,
												);
												if (newSystemHasCharSheet) {
													const withoutCustom = withoutOld.filter(
														(id) => id !== "custom",
													);
													return withoutCustom.includes(newSystemId)
														? withoutCustom
														: [...withoutCustom, newSystemId];
												}
												return withoutOld.includes("custom")
													? withoutOld
													: [...withoutOld, "custom"];
											});
										}}
									/>
								</div>
							</div>
						)}
					</form.Field>

					<form.Field
						name="allowedCharSheets"
						validators={{
							onChange: ({ value }) =>
								value.length === 0
									? "You must allow at least one character sheet."
									: undefined,
						}}
					>
						{(field) => {
							const available = charSheetSystems.filter(
								(system) => !field.state.value.includes(system.id),
							);
							return (
								<div>
									<label htmlFor="allowed-char-sheets-combo" className="push-down">
										Allowed character sheets:
									</label>
									<div>
										<div className={styles["char-sheet-picker"]}>
											<Autocomplete
												id="allowed-char-sheets-combo"
												items={available}
												getId={(system: BasicSystem) => system.id}
												getLabel={(system: BasicSystem) => system.name}
												onAction={(id) =>
													field.handleChange([...field.state.value, id])
												}
											/>
											{field.state.meta.errors[0] && (
												<div className="error">
													<FieldError message={field.state.meta.errors[0]} />
												</div>
											)}
										</div>
										{field.state.value.length > 0 && (
											<ul className={styles["char-sheet-list"]}>
												{field.state.value.map((id) => {
													const system = systems.find((s) => s.id === id);
													return (
														<li key={id}>
															{system?.name ?? id}{" "}
															<button
																type="button"
																onClick={() =>
																	field.handleChange(
																		field.state.value.filter(
																			(existing) => existing !== id,
																		),
																	)
																}
															>
																[ - ]
															</button>
														</li>
													);
												})}
											</ul>
										)}
									</div>
								</div>
							);
						}}
					</form.Field>

					<div>
						<label htmlFor="times-per">Post frequency:</label>
						<div>
							<form.Field name="timesPer">
								{(field) => (
									<input
										id="times-per"
										type="number"
										min={1}
										max={99}
										value={field.state.value}
										onChange={(e) => field.handleChange(Number(e.target.value))}
									/>
								)}
							</form.Field>
							{" time(s) per "}
							<form.Field name="perPeriod">
								{(field) => (
									<select
										value={field.state.value}
										onChange={(e) => field.handleChange(e.target.value as "d" | "w")}
									>
										<option value="d">day</option>
										<option value="w">week</option>
									</select>
								)}
							</form.Field>
						</div>
					</div>

					<form.Field name="numPlayers">
						{(field) => (
							<div>
								<label htmlFor={field.name}>Number of players:</label>
								<div>
									<input
										id={field.name}
										type="number"
										min={1}
										max={99}
										value={field.state.value}
										onChange={(e) => field.handleChange(Number(e.target.value))}
									/>
								</div>
							</div>
						)}
					</form.Field>

					<form.Field name="charsPerPlayer">
						{(field) => (
							<div>
								<label htmlFor={field.name}>Characters per player:</label>
								<div>
									<input
										id={field.name}
										type="number"
										min={1}
										max={9}
										value={field.state.value}
										onChange={(e) => field.handleChange(Number(e.target.value))}
									/>
								</div>
							</div>
						)}
					</form.Field>

					<form.Field name="description">
						{(field) => (
							<div>
								<label htmlFor={field.name} className="push-down">
									Description:
								</label>
								<div>
									<Editor
										id={field.name}
										value={field.state.value}
										onChange={(value) => field.handleChange(value)}
									/>
								</div>
							</div>
						)}
					</form.Field>

					<form.Field name="charGenInfo">
						{(field) => (
							<div>
								<label htmlFor={field.name} className="push-down">
									Character generation info:
								</label>
								<div>
									<Editor
										id={field.name}
										value={field.state.value}
										onChange={(value) => field.handleChange(value)}
									/>
								</div>
							</div>
						)}
					</form.Field>

					<form.Field name="isPublic">
						{(field) => (
							<div>
								<label htmlFor={field.name}>Public:</label>
								<div>
									<Checkbox
										id={field.name}
										checked={field.state.value}
										onChange={(checked) => field.handleChange(checked)}
									/>
								</div>
							</div>
						)}
					</form.Field>

					<form.Field name="recruitmentThreadId">
						{(field) => (
							<div>
								<label htmlFor={field.name}>Recruitment thread:</label>
								<div>
									<span className={styles["thread-url"]}>
										/forums/thread/
										<input
											id={field.name}
											type="number"
											min={1}
											value={field.state.value}
											onChange={(e) => field.handleChange(e.target.value)}
										/>
										/
									</span>
								</div>
							</div>
						)}
					</form.Field>

					<div className="is-container">
						<form.Field name="advancedOptions">
							{(field) => (
								<AdvancedOptions
									value={field.state.value}
									onChange={(value) => field.handleChange(value)}
								/>
							)}
						</form.Field>
					</div>

					<form.Subscribe selector={(state) => state.canSubmit}>
						{(canSubmit) => (
							<div className="is-container">
								<button
									type="submit"
									className="skew-btn"
									disabled={!canSubmit || mutation.isPending}
								>
									{game ? "Save" : "Create"}
								</button>
							</div>
						)}
					</form.Subscribe>
				</form>
			</div>
		</div>
	);
}
