import { QueryClient } from "@tanstack/react-query";
import { useAuthStore } from "#/stores/auth";
import { useModeratorModeStore } from "#/stores/moderator-mode";

export function getContext() {
	const queryClient = new QueryClient();

	// Many endpoints return different data (or are gated entirely) depending on
	// whether the caller is authenticated, so cached responses from before a
	// login/logout are no longer valid once auth actually flips. Reset rather
	// than invalidate: loaders read through `ensureQueryData`, which hands back
	// stale data as-is, so the previous user's responses must be dropped.
	// Refresh-only token changes (still logged in/out) shouldn't trigger this.
	useAuthStore.subscribe((state, prevState) => {
		if (!!state.token !== !!prevState.token) {
			// However the session ended, the next account starts in player mode.
			if (!state.token) useModeratorModeStore.getState().setModeratorMode(false);
			queryClient.resetQueries();
		}
	});

	return {
		queryClient,
	};
}
export default function TanstackQueryProvider() {}
