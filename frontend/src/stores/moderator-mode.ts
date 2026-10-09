import { create } from "zustand";
import { persist } from "zustand/middleware";

// Off (player mode) by default. Admins and moderators of the forums above the games
// opt in per browser; see ForumPermissions on the API for what the mode changes.
type ModeratorModeStore = {
	moderatorMode: boolean;
	setModeratorMode: (moderatorMode: boolean) => void;
};

export const useModeratorModeStore = create<ModeratorModeStore>()(
	persist(
		(set) => ({
			moderatorMode: false,
			setModeratorMode: (moderatorMode) => set({ moderatorMode }),
		}),
		{ name: "moderator-mode" },
	),
);
