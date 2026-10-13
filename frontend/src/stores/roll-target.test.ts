import { afterEach, describe, expect, it, vi } from "vitest";
import {
	type RollTarget,
	selectActiveRollTarget,
	useRollTargetStore,
} from "./roll-target";

const target = (id: string, blockedReason: string | null = null): RollTarget => ({
	id,
	addRoll: vi.fn(),
	blockedReason,
});
const active = () => selectActiveRollTarget(useRollTargetStore.getState());

afterEach(() => {
	useRollTargetStore.setState({ targets: [] });
});

describe("roll target store", () => {
	it("makes the most recently registered composer the active one", () => {
		const { register } = useRollTargetStore.getState();
		expect(active()).toBeNull();

		register(target("full"));
		register(target("quick"));

		expect(active()?.id).toBe("quick");
	});

	it("falls back to the earlier composer when the latest unregisters", () => {
		const { register, unregister } = useRollTargetStore.getState();
		register(target("full"));
		register(target("quick"));
		unregister("quick");

		expect(active()?.id).toBe("full");
	});

	it("keeps a composer's place when it re-registers with new state", () => {
		const { register } = useRollTargetStore.getState();
		register(target("full"));
		register(target("quick"));
		register(target("full", "Rolls are off."));

		expect(active()?.id).toBe("quick");
		expect(useRollTargetStore.getState().targets[0]?.blockedReason).toBe(
			"Rolls are off.",
		);
	});
});
