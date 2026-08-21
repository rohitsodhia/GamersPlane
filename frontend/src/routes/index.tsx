import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { isTokenValid } from "#/lib/jwt";
import { useAuthStore } from "#/stores/auth";
import Home from "./-home";
import Landing from "./-landing";

export const Route = createFileRoute("/")({ component: Index });

function Index() {
	const token = useAuthStore((state) => state.token);

	// Mirrors __root.tsx's mount gating: the persisted token isn't available
	// during SSR/first hydration, so wait until mounted to avoid flashing
	// the wrong subpage.
	const [mounted, setMounted] = useState(false);
	useEffect(() => setMounted(true), []);
	if (!mounted) return null;

	return !token && isTokenValid(token) ? <Home /> : <Landing />;
}
