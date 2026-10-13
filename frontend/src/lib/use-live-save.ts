import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "#/lib/api";
import { characterQueryOptions, updateCharacterLiveValue } from "#/queries/character";
import type { LiveSave } from "#/routes/characters/sheets/-components/sheet-values";

/**
 * The `onLiveSave` handler for a display-mode sheet's `<SheetValuesProvider>`:
 * saves one live field of the character and puts the response in the cached
 * character. Rejects with an `Error` worded for the user (the API's detail when
 * it gave one).
 */
export function useLiveSave(characterId: number): LiveSave {
	const queryClient = useQueryClient();
	const mutation = useMutation({
		mutationFn: (data: Parameters<LiveSave>) =>
			updateCharacterLiveValue(characterId, { path: data[0], value: data[1] }),
		onSuccess: (character) => {
			queryClient.setQueryData(characterQueryOptions(characterId).queryKey, character);
		},
	});

	return async (path, value) => {
		try {
			await mutation.mutateAsync([path, value]);
		} catch (err) {
			if (err instanceof ApiError) {
				throw new Error(err.errors[0]?.detail ?? "Couldn't save this change.");
			}
			throw new Error("Couldn't save this change. Check your connection.");
		}
	};
}
