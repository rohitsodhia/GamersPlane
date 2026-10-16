import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { isTokenValid } from "#/lib/jwt";
import { latestGamesQueryOptions, myGamesQueryOptions } from "#/queries/game";
import { systemsQueryOptions } from "#/queries/systems";
import { announcementQueryOptions, recentThreadsQueryOptions } from "#/queries/threads";
import { useAuthStore } from "#/stores/auth";
import Home from "./-home";
import Landing from "./-landing";

// Shared by the loader and the component so the preload always matches the
// page actually rendered.
const showsHome = (token: string | null) => !!token && isTokenValid(token);

export const Route = createFileRoute("/")({
	// The root route's beforeLoad has already settled the token by the time this
	// runs, so the store holds the final value.
	loader: async ({ context }) => {
		const { queryClient } = context;
		if (showsHome(useAuthStore.getState().token)) {
			// The dashboard's widgets; prefetch (not ensure) so one failing request
			// shows as that widget's error instead of failing the whole page.
			await Promise.all([
				queryClient.prefetchQuery(announcementQueryOptions()),
				queryClient.prefetchQuery(latestGamesQueryOptions(null, { excludeMine: true })),
				queryClient.prefetchQuery(recentThreadsQueryOptions("latest", 1, 5)),
				queryClient.prefetchQuery(recentThreadsQueryOptions("latest_game", 1, 5)),
				queryClient.prefetchQuery(recentThreadsQueryOptions("latest_public", 1, 2)),
				queryClient.prefetchQuery(myGamesQueryOptions()),
			]);
		} else {
			// For the landing page's "Latest Games" system picker.
			await queryClient.ensureQueryData(systemsQueryOptions({ basic: true }));
		}
	},
	component: Index,
});

function Index() {
	const token = useAuthStore((state) => state.token);

	// Mirrors __root.tsx's mount gating: the persisted token isn't available
	// during SSR/first hydration, so wait until mounted to avoid flashing
	// the wrong subpage.
	const [mounted, setMounted] = useState(false);
	useEffect(() => setMounted(true), []);
	if (!mounted) return null;

	return showsHome(token) ? <Home /> : <Landing />;
}
