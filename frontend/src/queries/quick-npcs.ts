import { queryOptions } from "@tanstack/react-query";
import { ApiError, apiFetch } from "#/lib/api";

// Whose library of quick NPCs and images: a game's (shared by its accepted
// players) or the viewer's personal one (used outside games).
export type NpcLibrary = { kind: "game"; gameId: number } | { kind: "me" };

// A picture in a library; one image can serve many quick NPCs.
export type NpcImage = {
	id: number;
	url: string;
};

// A quick NPC: a name with an optional image, per library.
export type QuickNpc = {
	id: number;
	name: string;
	image: NpcImage | null;
	// When the viewer last posted as it.
	last_used_at: string | null;
	// Whether the viewer may rename, re-image or delete it (a game's GMs and the
	// pair's creator; personal NPCs can't be edited).
	can_edit: boolean;
};

// A quick NPC a post body's speaker and roster blocks name, as the post's response carries it
// (deleted ones included, so old posts still render).
export type ContentNpc = Pick<QuickNpc, "id" | "name" | "image">;

const basePath = (library: NpcLibrary) =>
	library.kind === "game" ? `/games/${library.gameId}` : "/me";

export const npcsQueryKey = (library: NpcLibrary) =>
	library.kind === "game" ? ["game", library.gameId, "npcs"] : ["me", "npcs"];

export const npcImagesQueryKey = (library: NpcLibrary) =>
	library.kind === "game" ? ["game", library.gameId, "images"] : ["me", "npc-images"];

const failure = async (res: Response) => {
	const { errors } = await res.json();
	return new ApiError(res.status, errors);
};

export const npcsQueryOptions = (library: NpcLibrary) =>
	queryOptions({
		queryKey: npcsQueryKey(library),
		queryFn: async (): Promise<QuickNpc[]> => {
			const res = await apiFetch(`${basePath(library)}/npcs`);
			if (!res.ok) throw new Error("Failed to fetch quick NPCs");
			return res.json();
		},
	});

export const npcImagesQueryOptions = (library: NpcLibrary) =>
	queryOptions({
		queryKey: npcImagesQueryKey(library),
		queryFn: async (): Promise<NpcImage[]> => {
			const res = await apiFetch(`${basePath(library)}/images`);
			if (!res.ok) throw new Error("Failed to fetch NPC images");
			return res.json();
		},
		staleTime: 1000 * 60 * 5,
	});

// Get-or-create: an existing live pair with the same name and image is returned.
export const createNpc = async (
	library: NpcLibrary,
	data: { name: string; image_id: number | null },
): Promise<QuickNpc> => {
	const res = await apiFetch(`${basePath(library)}/npcs`, {
		method: "POST",
		body: JSON.stringify(data),
	});
	if (!res.ok) throw await failure(res);
	return res.json();
};

export const uploadNpcImage = async (
	library: NpcLibrary,
	file: File,
): Promise<NpcImage> => {
	const body = new FormData();
	body.append("image", file);
	const res = await apiFetch(`${basePath(library)}/images`, { method: "POST", body });
	if (!res.ok) throw await failure(res);
	return res.json();
};

// The server downloads the image and keeps its own copy.
export const linkNpcImage = async (
	library: NpcLibrary,
	url: string,
): Promise<NpcImage> => {
	const res = await apiFetch(`${basePath(library)}/images/link`, {
		method: "POST",
		body: JSON.stringify({ url }),
	});
	if (!res.ok) throw await failure(res);
	return res.json();
};

// Game libraries only. Absent fields are left alone; a null image_id drops the
// image. Every post that used the NPC changes with it.
export const updateNpc = async (
	gameId: number,
	npcId: number,
	data: { name?: string; image_id?: number | null },
): Promise<QuickNpc> => {
	const res = await apiFetch(`/games/${gameId}/npcs/${npcId}`, {
		method: "PATCH",
		body: JSON.stringify(data),
	});
	if (!res.ok) throw await failure(res);
	return res.json();
};

// Game libraries only.
export const deleteNpc = async (gameId: number, npcId: number): Promise<void> => {
	const res = await apiFetch(`/games/${gameId}/npcs/${npcId}`, { method: "DELETE" });
	if (!res.ok) throw await failure(res);
};
