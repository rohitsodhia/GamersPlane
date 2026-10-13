import { act, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MAX_ROLLS_PER_POST } from "#/queries/posts";
import { selectActiveRollTarget, useRollTargetStore } from "#/stores/roll-target";
import { type Attachments, emptyAttachments, newRollRow } from "./-attachment-rows";
import { PostAttachmentsEditor } from "./-post-attachments";
import { useSheetRollTarget } from "./-use-sheet-roll-target";

afterEach(() => {
	useRollTargetStore.setState({ targets: [] });
});

const activeTarget = () => selectActiveRollTarget(useRollTargetStore.getState());
// `act` returns a thenable, so the handler's return value is captured inside it.
const send = (roll: { dice: string; reason: string; mode?: "new" | "add" }) => {
	let refusal: string | undefined;
	act(() => {
		refusal = activeTarget()?.addRoll({ mode: "new", ...roll });
	});
	return refusal;
};

// A stand-in composer: the hook plus the real rolls editor.
function Composer({
	enabled = true,
	blockedReason = null,
	reveal = () => {},
	initial = emptyAttachments,
}: {
	enabled?: boolean;
	blockedReason?: string | null;
	reveal?: () => void;
	initial?: Attachments;
}) {
	const [attachments, setAttachments] = useState(initial);
	const highlight = useSheetRollTarget({
		enabled,
		attachments,
		onAttachmentsChange: setAttachments,
		blockedReason,
		reveal,
	});
	return (
		<PostAttachmentsEditor
			value={attachments}
			onChange={setAttachments}
			access={{ rolls: true, draws: false }}
			decks={[]}
			showErrors={false}
			highlight={highlight}
		/>
	);
}

describe("useSheetRollTarget", () => {
	it("registers while mounted and unregisters on unmount", () => {
		const { unmount } = render(<Composer />);
		expect(activeTarget()).not.toBeNull();

		unmount();
		expect(activeTarget()).toBeNull();
	});

	it("doesn't register while disabled", () => {
		render(<Composer enabled={false} />);
		expect(activeTarget()).toBeNull();
	});

	it("publishes why rolls are blocked", () => {
		render(<Composer blockedReason="Rolls are turned off in this thread." />);
		expect(activeTarget()?.blockedReason).toBe("Rolls are turned off in this thread.");
	});

	it("adds a prefilled roll row, reveals the section and highlights the row", () => {
		const reveal = vi.fn();
		render(<Composer reveal={reveal} />);

		const refusal = send({ dice: "1d20+5", reason: "Athletics" });

		expect(refusal).toBeUndefined();
		expect(screen.getByRole("textbox", { name: "Roll" })).toHaveValue("1d20+5");
		expect(screen.getByRole("textbox", { name: "Reason" })).toHaveValue("Athletics");
		expect(reveal).toHaveBeenCalledTimes(1);
		expect(screen.getByRole("listitem").className).toMatch(/flash/);
	});

	it("appends an `add` roll to the existing row, through a handler that stays stable", () => {
		render(<Composer />);
		send({ dice: "1d6", reason: "Fireball" });
		const addRollAfterFirst = activeTarget()?.addRoll;

		send({ dice: "1d8", reason: "Burn", mode: "add" });

		expect(screen.getAllByRole("textbox", { name: "Roll" })).toHaveLength(1);
		expect(screen.getByRole("textbox", { name: "Roll" })).toHaveValue("1d6,1d8");
		expect(screen.getByRole("textbox", { name: "Reason" })).toHaveValue("Fireball");
		// The composer re-rendered with new rows, yet the sheet's handler wasn't
		// re-registered; it still saw the latest rows (the append hit the new row).
		expect(addRollAfterFirst).toBeDefined();
		expect(activeTarget()?.addRoll).toBe(addRollAfterFirst);
	});

	it("refuses a new roll once the post is full, with a message and no reveal", () => {
		const reveal = vi.fn();
		const full: Attachments = {
			rolls: Array.from({ length: MAX_ROLLS_PER_POST }, () => newRollRow()),
			draws: [],
		};
		render(<Composer reveal={reveal} initial={full} />);

		const refusal = send({ dice: "1d20", reason: "Too many" });

		expect(refusal).toBe(`A post can have at most ${MAX_ROLLS_PER_POST} rolls.`);
		expect(screen.getAllByRole("textbox", { name: "Roll" })).toHaveLength(
			MAX_ROLLS_PER_POST,
		);
		expect(reveal).not.toHaveBeenCalled();
	});
});
