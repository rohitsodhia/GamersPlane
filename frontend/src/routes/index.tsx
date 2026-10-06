import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { isTokenValid } from "#/lib/jwt";
import { systemsQueryOptions } from "#/queries/systems";
import { useAuthStore } from "#/stores/auth";
import Home from "./-home";
import Landing from "./-landing";

// Shared by the loader and the component so the preload always matches the
// page actually rendered. Currently inverted so Landing shows even when logged
// in, for testing.
const showsHome = (token: string | null) => !token && isTokenValid(token);

export const Route = createFileRoute("/")({
	// The root route's beforeLoad has already settled the token by the time this
	// runs, so the store holds the final value.
	loader: async ({ context }) => {
		if (!showsHome(useAuthStore.getState().token)) {
			// For the landing page's "Latest Games" system picker.
			await context.queryClient.ensureQueryData(systemsQueryOptions({ basic: true }));
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
