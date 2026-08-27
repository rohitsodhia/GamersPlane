import { QueryClient } from "@tanstack/react-query";
import { useAuthStore } from "#/stores/auth";

export function getContext() {
	const queryClient = new QueryClient();

	// Many endpoints return different data (or are gated entirely) depending on
	// whether the caller is authenticated, so cached responses from before a
	// login/logout are no longer valid once auth actually flips. Refresh-only
	// token changes (still logged in/out) shouldn't trigger this.
	useAuthStore.subscribe((state, prevState) => {
		if (!!state.token !== !!prevState.token) {
			queryClient.invalidateQueries();
		}
	});

	return {
		queryClient,
	};
}
export default function TanstackQueryProvider() {}
