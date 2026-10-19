import { describe, expect, it, vi } from "vitest";
import { DEFAULT_BACKGROUND_SETTINGS } from "#/lib/game-background";
import { type BackgroundDraft, saveGameWithBackground } from "./-game-save";

const file = new File(["x"], "bg.png", { type: "image/png" });
const draft = (changes: Partial<BackgroundDraft> = {}): BackgroundDraft => ({
	file: null,
	removed: false,
	settings: DEFAULT_BACKGROUND_SETTINGS,
	...changes,
});

function makeOps() {
	const calls: string[] = [];
	const record = (name: string) =>
		vi.fn(async (...args: unknown[]) => {
			calls.push(name);
			return { id: 7, args };
		});
	return {
		calls,
		ops: {
			create: record("create"),
			update: record("update"),
			upload: record("upload"),
			remove: record("remove"),
		},
	};
}

describe("saveGameWithBackground, editing", () => {
	it("uploads before patching with the settings", async () => {
		const { calls, ops } = makeOps();
		await saveGameWithBackground({
			gameId: 3,
			hasExistingImage: false,
			draft: draft({ file }),
			ops,
		});
		expect(calls).toEqual(["upload", "update"]);
		expect(ops.update).toHaveBeenCalledWith(3, {
			background: DEFAULT_BACKGROUND_SETTINGS,
		});
	});

	it("deletes a removed image and patches with no background settings", async () => {
		const { calls, ops } = makeOps();
		await saveGameWithBackground({
			gameId: 3,
			hasExistingImage: true,
			draft: draft({ removed: true }),
			ops,
		});
		expect(calls).toEqual(["remove", "update"]);
		expect(ops.update).toHaveBeenCalledWith(3, null);
	});

	it("keeps an existing image's settings without touching the image", async () => {
		const { calls, ops } = makeOps();
		await saveGameWithBackground({
			gameId: 3,
			hasExistingImage: true,
			draft: draft(),
			ops,
		});
		expect(calls).toEqual(["update"]);
		expect(ops.update).toHaveBeenCalledWith(3, {
			background: DEFAULT_BACKGROUND_SETTINGS,
		});
	});

	it("does not patch when the upload fails", async () => {
		const { ops } = makeOps();
		ops.upload.mockRejectedValueOnce(new Error("bad file"));
		await expect(
			saveGameWithBackground({
				gameId: 3,
				hasExistingImage: false,
				draft: draft({ file }),
				ops,
			}),
		).rejects.toThrow("bad file");
		expect(ops.update).not.toHaveBeenCalled();
	});
});

describe("saveGameWithBackground, creating", () => {
	it("creates without background settings and stops when no file is staged", async () => {
		const { calls, ops } = makeOps();
		const result = await saveGameWithBackground({
			gameId: undefined,
			hasExistingImage: false,
			draft: draft(),
			ops,
		});
		expect(calls).toEqual(["create"]);
		expect(ops.create).toHaveBeenCalledWith(null);
		expect(result).toEqual({ id: 7, backgroundError: null });
	});

	it("uploads then patches the new game when a file is staged", async () => {
		const { calls, ops } = makeOps();
		await saveGameWithBackground({
			gameId: undefined,
			hasExistingImage: false,
			draft: draft({ file }),
			ops,
		});
		expect(calls).toEqual(["create", "upload", "update"]);
		expect(ops.update).toHaveBeenCalledWith(7, {
			background: DEFAULT_BACKGROUND_SETTINGS,
		});
	});

	it("returns the new id and the message when the upload fails", async () => {
		const { ops } = makeOps();
		ops.upload.mockRejectedValueOnce(new Error("too big"));
		const result = await saveGameWithBackground({
			gameId: undefined,
			hasExistingImage: false,
			draft: draft({ file }),
			ops,
		});
		expect(result).toEqual({ id: 7, backgroundError: "too big" });
		expect(ops.update).not.toHaveBeenCalled();
	});
});
