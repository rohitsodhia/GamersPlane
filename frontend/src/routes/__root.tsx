import { TanStackDevtools } from "@tanstack/react-devtools";
import type { QueryClient } from "@tanstack/react-query";
import {
	createRootRouteWithContext,
	HeadContent,
	Outlet,
	Scripts,
} from "@tanstack/react-router";
import { TanStackRouterDevtoolsPanel } from "@tanstack/react-router-devtools";
import Footer from "#/components/Footer";
import Header from "#/components/Header";
import TanStackQueryDevtools from "#/integrations/tanstack-query/devtools";
import { meQueryOptions } from "#/queries/me";
import { referralLinksQueryOptions } from "#/queries/referralLinks";
import { useAuthStore } from "#/stores/auth";
import appCss from "#/styles.css?url";

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
				rel: "stylesheet",
				href: appCss,
			},
		],
	}),
	shellComponent: RootDocument,
	component: RootLayout,
	loader: async ({ context }) => {
		const { token, setToken } = useAuthStore.getState();
		await Promise.all([
			context.queryClient.ensureQueryData(referralLinksQueryOptions),
			...(token
				? [
						context.queryClient
							.ensureQueryData(meQueryOptions)
							.catch(() => setToken(null)),
					]
				: []),
		]);
	},
});

function RootLayout() {
	return (
		<>
			<Header />
			<main className="page-wrap">
				<Outlet />
			</main>
			<Footer />
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
