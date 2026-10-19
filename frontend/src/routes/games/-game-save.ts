import { ApiError } from "#/lib/api";
import type { GameAdvancedOptionsInput, GameBackgroundSettings } from "#/queries/game";

/** The background as staged in the game form; nothing here is sent until Save. */
export type BackgroundDraft = {
	file: File | null;
	removed: boolean;
	settings: GameBackgroundSettings;
};

/** Whether the game will have a background image once the draft is applied. */
export function imageWillExist(hasExistingImage: boolean, draft: BackgroundDraft) {
	return draft.file !== null || (hasExistingImage && !draft.removed);
}

/** Background settings are only ever sent when an image will exist to apply them to. */
export function advancedOptionsFor(
	hasExistingImage: boolean,
	draft: BackgroundDraft,
): GameAdvancedOptionsInput | null {
	return imageWillExist(hasExistingImage, draft)
		? { background: draft.settings }
		: null;
}

export function errorMessage(exception: unknown): string {
	if (exception instanceof ApiError) {
		return exception.errors.map((e) => e.detail).join(" ");
	}
	return exception instanceof Error ? exception.message : "Something went wrong.";
}

type SaveOps = {
	create: (advanced: null) => Promise<{ id: number }>;
	update: (
		gameId: number,
		advanced: GameAdvancedOptionsInput | null,
	) => Promise<unknown>;
	upload: (gameId: number, file: File) => Promise<unknown>;
	remove: (gameId: number) => Promise<unknown>;
};

/**
 * Saves a game and its staged background in order. On edit, any failure throws
 * and the form shows it. On create the game exists once the first step succeeds,
 * so a later background failure is returned instead, letting the caller carry the
 * user on to the new game's edit page.
 */
export async function saveGameWithBackground({
	gameId,
	hasExistingImage,
	draft,
	ops,
}: {
	gameId: number | undefined;
	hasExistingImage: boolean;
	draft: BackgroundDraft;
	ops: SaveOps;
}): Promise<{ id: number; backgroundError: string | null }> {
	if (gameId !== undefined) {
		if (draft.file) await ops.upload(gameId, draft.file);
		else if (draft.removed && hasExistingImage) await ops.remove(gameId);
		await ops.update(gameId, advancedOptionsFor(hasExistingImage, draft));
		return { id: gameId, backgroundError: null };
	}

	const { id } = await ops.create(null);
	if (!draft.file) return { id, backgroundError: null };
	try {
		await ops.upload(id, draft.file);
		await ops.update(id, advancedOptionsFor(false, draft));
	} catch (exception) {
		return { id, backgroundError: errorMessage(exception) };
	}
	return { id, backgroundError: null };
}
