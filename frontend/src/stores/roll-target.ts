import { create } from "zustand";
import type { RollRequest } from "#/routes/characters/sheets/-components/roll";

/**
 * A post composer that can take rolls from a character sheet. `addRoll` returns a
 * message when the roll couldn't be added (shown beside the sheet's dice icon).
 * `blockedReason` is set when the composer can't take rolls at all (rolls off in
 * the thread, no permission): the sheet's rollables stay unclickable and say why.
 */
export type RollTarget = {
	id: string;
	addRoll: (roll: RollRequest) => string | undefined;
	blockedReason: string | null;
};

type RollTargetStore = {
	/** Registered composers in registration order; the last one is the active one. */
	targets: RollTarget[];
	/** Adds a composer, or replaces its entry (keeping its place) when `id` is registered. */
	register: (target: RollTarget) => void;
	/** Removes the composer; a no-op when it isn't registered. */
	unregister: (id: string) => void;
};

export const useRollTargetStore = create<RollTargetStore>()((set) => ({
	targets: [],
	register: (target) =>
		set((state) =>
			state.targets.some((existing) => existing.id === target.id)
				? {
						targets: state.targets.map((existing) =>
							existing.id === target.id ? target : existing,
						),
					}
				: { targets: [...state.targets, target] },
		),
	unregister: (id) =>
		set((state) =>
			state.targets.some((existing) => existing.id === id)
				? { targets: state.targets.filter((existing) => existing.id !== id) }
				: state,
		),
}));

/** The composer a sheet roll goes to: the most recently mounted one, or null. */
export const selectActiveRollTarget = (state: RollTargetStore): RollTarget | null =>
	state.targets.at(-1) ?? null;
