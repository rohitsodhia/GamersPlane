import { useEffect, useId, useRef, useState } from "react";
import type { OnRoll } from "#/routes/characters/sheets/-components/roll-context";
import { useRollTargetStore } from "#/stores/roll-target";
import { type Attachments, addSheetRoll } from "./-attachment-rows";

// The row a sheet roll just landed in. `pulse` changes with every roll, so a roll
// into the same row again can restart the highlight.
export type RollHighlight = { key: string; pulse: number };

const HIGHLIGHT_MS = 1800;

// Registers a post composer as the place the game bar's character sheet sends
// rolls to, for as long as it's mounted. A roll lands as a prefilled row in
// `attachments`; `reveal` opens whatever hides the Rolls section. Returns the row
// to highlight. `blockedReason` is why rolls can't be added (null when they can).
export function useSheetRollTarget({
	enabled = true,
	attachments,
	onAttachmentsChange,
	blockedReason,
	reveal,
}: {
	// False while the composer isn't on screen (e.g. the user can't reply).
	enabled?: boolean;
	attachments: Attachments;
	onAttachmentsChange: (value: Attachments) => void;
	blockedReason: string | null;
	reveal: () => void;
}): RollHighlight | null {
	const id = useId();
	const register = useRollTargetStore((state) => state.register);
	const unregister = useRollTargetStore((state) => state.unregister);
	const [highlight, setHighlight] = useState<RollHighlight | null>(null);

	// The latest rows and callbacks, read when a roll arrives. Registering a fresh
	// handler on every render instead would re-render the whole sheet in the panel
	// on each keystroke in the composer.
	const latest = useRef({ attachments, onAttachmentsChange, reveal });
	useEffect(() => {
		latest.current = { attachments, onAttachmentsChange, reveal };
	});

	// Re-registers only when what the sheet shows changes; the store keeps the
	// entry's place, so this doesn't reorder composers.
	useEffect(() => {
		if (!enabled) return;
		const addRoll: OnRoll = (roll) => {
			const { attachments, onAttachmentsChange, reveal } = latest.current;
			const added = addSheetRoll(attachments, roll);
			if ("error" in added) return added.error;
			onAttachmentsChange(added.attachments);
			reveal();
			setHighlight((current) => ({
				key: added.rowKey,
				pulse: (current?.pulse ?? 0) + 1,
			}));
		};
		register({
			id,
			// `OnRoll` may return nothing; the store's handler always says string | undefined.
			addRoll: (roll) => {
				const refusal = addRoll(roll);
				return typeof refusal === "string" ? refusal : undefined;
			},
			blockedReason,
		});
	}, [enabled, id, blockedReason, register]);
	useEffect(() => {
		if (!enabled) return;
		return () => unregister(id);
	}, [enabled, id, unregister]);

	useEffect(() => {
		if (highlight == null) return;
		const timer = setTimeout(() => setHighlight(null), HIGHLIGHT_MS);
		return () => clearTimeout(timer);
	}, [highlight]);

	return highlight;
}
