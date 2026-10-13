import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "#/lib/api";
import { characterQueryOptions } from "#/queries/character";
import { useLiveSave } from "./use-live-save";

const updateCharacterLiveValue = vi.fn();
vi.mock("#/queries/character", async (importOriginal) => ({
	...(await importOriginal<typeof import("#/queries/character")>()),
	updateCharacterLiveValue: (...args: unknown[]) => updateCharacterLiveValue(...args),
}));

let queryClient: QueryClient;
beforeEach(() => {
	updateCharacterLiveValue.mockReset();
	queryClient = new QueryClient({
		defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
	});
});

function setup() {
	const wrapper = ({ children }: { children: ReactNode }) => (
		<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
	);
	return renderHook(() => useLiveSave(7), { wrapper }).result.current;
}

describe("useLiveSave", () => {
	it("patches the field and puts the returned character in the cache", async () => {
		const saved = { id: 7, label: "Hero" };
		updateCharacterLiveValue.mockResolvedValue(saved);
		const save = setup();

		await save(["hp1"], "7");

		expect(updateCharacterLiveValue).toHaveBeenCalledWith(7, {
			path: ["hp1"],
			value: "7",
		});
		expect(queryClient.getQueryData(characterQueryOptions(7).queryKey)).toBe(saved);
	});

	it("rejects with the API's first error detail", async () => {
		updateCharacterLiveValue.mockRejectedValue(
			new ApiError(400, [
				{ code: "invalid", detail: "That isn't a number." },
				{ code: "other", detail: "Second." },
			]),
		);
		const save = setup();

		await expect(save(["hp1"], "x")).rejects.toThrow("That isn't a number.");
	});

	it("rejects with a generic message when the API gave no detail", async () => {
		updateCharacterLiveValue.mockRejectedValue(new ApiError(500, []));
		const save = setup();

		await expect(save(["hp1"], "7")).rejects.toMatchObject({
			message: "Couldn't save this change.",
		});
	});

	it("rejects with a connection hint on a non-API failure", async () => {
		updateCharacterLiveValue.mockRejectedValue(new TypeError("Failed to fetch"));
		const save = setup();

		await expect(save(["hp1"], "7")).rejects.toThrow(
			"Couldn't save this change. Check your connection.",
		);
	});
});
