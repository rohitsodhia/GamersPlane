import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button, Input, TextField } from "react-aria-components";
import { ApiError } from "#/lib/api";
import {
	deleteNpc,
	type NpcLibrary,
	npcsQueryOptions,
	type QuickNpc,
	updateNpc,
} from "#/queries/quick-npcs";
import styles from "#/routes/games/$gameId/index.module.css";
import { ConfirmDeleteButton } from "./ConfirmDeleteButton";
import { NpcImageChooser } from "./NpcImageChooser";
import npcStyles from "./QuickNpcList.module.css";
import { QuickNpcModal } from "./QuickNpcModal";

const errorMessage = (exception: unknown) =>
	exception instanceof ApiError && exception.errors[0]?.detail
		? exception.errors[0].detail
		: "Something went wrong.";

// A game's quick NPCs. Any accepted player can add one; each can be renamed,
// re-imaged or deleted by whoever `can_edit` it (the game's GMs and its creator).
// Posts made as one change with it. `isReadOnly` (a retired game) hides all of that.
export function QuickNpcList({
	gameId,
	margin,
	isReadOnly = false,
}: {
	gameId: number;
	margin: number;
	isReadOnly?: boolean;
}) {
	const queryClient = useQueryClient();
	const library: NpcLibrary = { kind: "game", gameId };
	const { data: npcs = [], isError } = useQuery(npcsQueryOptions(library));
	const [adding, setAdding] = useState(false);

	return (
		<div id="quick-npcs">
			<h2 className="headerbar hb-dark">
				<i className="ra ra-hood" /> Quick NPCs
			</h2>
			<div style={{ marginInline: margin }}>
				{isError && <div className="error">Failed to load quick NPCs</div>}
				{!isError && npcs.length === 0 && (
					<p className={styles["notice"]}>
						No quick NPCs yet.
						{!isReadOnly &&
							" Add one here, or make one while posting in the game's forums."}
					</p>
				)}
				{npcs.length > 0 && (
					<ul className={styles["row-list"]}>
						{npcs.map((npc) => (
							<NpcRow
								key={npc.id}
								gameId={gameId}
								npc={npc}
								canEdit={npc.can_edit && !isReadOnly}
							/>
						))}
					</ul>
				)}
				{!isReadOnly && (
					<div className={npcStyles["add"]}>
						<Button className="skew-btn" onPress={() => setAdding(true)}>
							Add NPC
						</Button>
					</div>
				)}
			</div>
			{!isReadOnly && (
				<QuickNpcModal
					library={library}
					isOpen={adding}
					onOpenChange={setAdding}
					onCreated={() => {
						// Pickers list the NPCs.
						queryClient.invalidateQueries({ queryKey: ["forums"] });
					}}
				/>
			)}
		</div>
	);
}

function NpcRow({
	gameId,
	npc,
	canEdit,
}: {
	gameId: number;
	npc: QuickNpc;
	canEdit: boolean;
}) {
	const queryClient = useQueryClient();
	const library: NpcLibrary = { kind: "game", gameId };
	const [editing, setEditing] = useState<"name" | "image" | null>(null);
	const [name, setName] = useState(npc.name);
	const [error, setError] = useState<string | null>(null);

	const done = () => {
		queryClient.invalidateQueries({ queryKey: npcsQueryOptions(library).queryKey });
		// Pickers list the NPCs, and posts show their name and image.
		queryClient.invalidateQueries({ queryKey: ["forums"] });
		queryClient.invalidateQueries({ queryKey: ["posts"] });
	};
	const update = useMutation({
		mutationFn: (data: { name?: string; image_id?: number | null }) =>
			updateNpc(gameId, npc.id, data),
		onSuccess: () => {
			setError(null);
			setEditing(null);
			done();
		},
		onError: (exception) => setError(errorMessage(exception)),
	});
	const remove = useMutation({
		mutationFn: () => deleteNpc(gameId, npc.id),
		onSuccess: done,
		onError: (exception) => setError(errorMessage(exception)),
	});

	const saveName = () => {
		const trimmed = name.trim();
		if (trimmed === "") return;
		if (trimmed === npc.name) setEditing(null);
		else update.mutate({ name: trimmed });
	};

	return (
		<li>
			<div className={styles["row"]}>
				{npc.image ? (
					<img className={npcStyles["thumb"]} src={npc.image.url} alt="" />
				) : (
					<span className={npcStyles["thumb"]} aria-hidden="true" />
				)}
				<div className={styles["row-label"]}>
					{editing === "name" ? (
						<TextField
							aria-label={`Name for ${npc.name}`}
							value={name}
							onChange={setName}
							isDisabled={update.isPending}
							autoFocus
						>
							<Input
								maxLength={100}
								onKeyDown={(e) => {
									if (e.key === "Enter") saveName();
									if (e.key === "Escape") setEditing(null);
								}}
							/>
						</TextField>
					) : (
						<span>{npc.name}</span>
					)}
				</div>
				{canEdit && (
					<div className={styles["action-links"]}>
						{editing === "name" ? (
							<>
								<button
									type="button"
									className={styles["inline-action"]}
									onClick={saveName}
									disabled={update.isPending || name.trim() === ""}
								>
									Save
								</button>
								<button
									type="button"
									className={styles["inline-action"]}
									onClick={() => setEditing(null)}
								>
									Cancel
								</button>
							</>
						) : (
							<>
								<button
									type="button"
									className={styles["inline-action"]}
									onClick={() => {
										setError(null);
										setName(npc.name);
										setEditing("name");
									}}
								>
									Rename
								</button>
								<button
									type="button"
									className={styles["inline-action"]}
									aria-expanded={editing === "image"}
									onClick={() => {
										setError(null);
										setEditing(editing === "image" ? null : "image");
									}}
								>
									{editing === "image" ? "Done" : "Image"}
								</button>
								<span className={styles["icon-button"]}>
									<ConfirmDeleteButton
										label={`Delete ${npc.name}`}
										message="Delete this quick NPC? Posts made as it keep its name and image."
										onConfirm={() => {
											setError(null);
											remove.mutate();
										}}
										isDisabled={remove.isPending}
									/>
								</span>
							</>
						)}
					</div>
				)}
			</div>
			{canEdit && editing === "image" && (
				<div className={npcStyles["chooser"]}>
					<NpcImageChooser
						library={library}
						value={npc.image?.id ?? null}
						onChange={(imageId) => update.mutate({ image_id: imageId })}
						isDisabled={update.isPending}
					/>
				</div>
			)}
			{error && <div className="error">{error}</div>}
		</li>
	);
}
