import { TanStackDevtools } from "@tanstack/react-devtools";
import { type QueryClient, useQuery } from "@tanstack/react-query";
import {
	createRootRouteWithContext,
	HeadContent,
	Outlet,
	Scripts,
} from "@tanstack/react-router";
import { TanStackRouterDevtoolsPanel } from "@tanstack/react-router-devtools";
import { useEffect, useState } from "react";
import Footer from "#/components/Footer";
import Header from "#/components/Header";
import NotFound from "#/components/NotFound";
import TanStackQueryDevtools from "#/integrations/tanstack-query/devtools";
import { isTokenExpiringSoon, isTokenValid } from "#/lib/jwt";
import { meHeaderQueryOptions, meQueryOptions } from "#/queries/me";
import { referralLinksQueryOptions } from "#/queries/referralLinks";
import { refreshToken } from "#/queries/refresh";
import { useAuthStore } from "#/stores/auth";
import appCss from "#/styles.css?url";
import "./__root.module.css";

const REFRESH_THRESHOLD_MS = 1000 * 60 * 60 * 24 * 2; // 2 days

interface MyRouterContext {
	queryClient: QueryClient;
}

export const Route = createRootRouteWithContext<MyRouterContext>()({
	head: () => ({
		meta: [
			{
				charSet: "utf-8",
			},
			{
				name: "viewport",
				content: "width=device-width, initial-scale=1",
			},
			{
				title: "Gamers' Plane",
			},
		],
		links: [
			{
				rel: "preload",
				href: "/fonts/LucidaGrande.woff2",
				as: "font",
				type: "font/woff2",
				crossOrigin: "anonymous",
			},
			{
				rel: "stylesheet",
				href: appCss,
			},
		],
	}),
	shellComponent: RootDocument,
	component: RootLayout,
	loader: async ({ context }) => {
		const { token, setToken } = useAuthStore.getState();
		let validToken = token ? isTokenValid(token) : false;
		if (token && !validToken) {
			setToken(null);
		}
		if (validToken && token && isTokenExpiringSoon(token, REFRESH_THRESHOLD_MS)) {
			const newToken = await refreshToken();
			if (newToken) {
				setToken(newToken);
			} else {
				setToken(null);
				validToken = false;
			}
		}
		await Promise.all([
			context.queryClient.ensureQueryData(referralLinksQueryOptions),
			...(validToken
				? [
						context.queryClient
							.ensureQueryData(meQueryOptions)
							.catch(() => setToken(null)),
						context.queryClient.ensureQueryData(meHeaderQueryOptions).catch(() => {}),
					]
				: []),
		]);
	},
	notFoundComponent: NotFound,
});

function RootLayout() {
	const token = useAuthStore((state) => state.token);
	const { isFetched: meFetched } = useQuery({ ...meQueryOptions, enabled: !!token });
	const { isFetched: referralLinksFetched } = useQuery(referralLinksQueryOptions);

	const [mounted, setMounted] = useState(false);
	useEffect(() => setMounted(true), []);
	// `mounted` is false during SSR/the static shell build (effects never run there)
	// and on the client's first hydration commit, so this stays consistent across
	// both — Header/Footer only mount once we actually know the freshly-loaded data,
	// instead of briefly rendering the shell's build-time content before it flips.
	const authResolved = mounted && (!token || meFetched);
	const referralLinksResolved = mounted && referralLinksFetched;

	return (
		<>
			{authResolved && <Header />}
			<main className="page-wrap">
				<Outlet />
			</main>
			{referralLinksResolved && <Footer />}
		</>
	);
}

function RootDocument({ children }: { children: React.ReactNode }) {
	return (
		<html lang="en">
			<head>
				<HeadContent />
			</head>
			<body>
				{children}
				<TanStackDevtools
					config={{
						position: "bottom-right",
					}}
					plugins={[
						{
							name: "Tanstack Router",
							render: <TanStackRouterDevtoolsPanel />,
						},
						TanStackQueryDevtools,
					]}
				/>
				<Scripts />
			</body>
		</html>
	);
}
