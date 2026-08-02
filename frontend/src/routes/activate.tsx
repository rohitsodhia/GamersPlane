import { createFileRoute, Link } from "@tanstack/react-router";
import { z } from "zod";
import { useHbMargined } from "#/lib/use-hb-margined";
import { activate } from "#/queries/activate";

export const Route = createFileRoute("/activate")({
	component: RouteComponent,
	validateSearch: z.object({
		token: z.string(),
	}),
	errorComponent: MissingToken,
	loaderDeps: ({ search }) => ({ token: search.token }),
	loader: async ({ deps }) => {
		await activate(deps.token);
	},
});

function MissingToken() {
	const hbMargined = useHbMargined<HTMLHeadingElement>();

	return (
		<div>
			<h1 className="headerbar" ref={hbMargined.ref}>
				Missing token
			</h1>
			<div style={{ marginInline: `${hbMargined.margin}px` }}>
				<p>
					The link you followed is incorrect. If you copied and pasted it, please double
					check you copied the entire link, otherwise request a new link.
				</p>
			</div>
		</div>
	);
}

function RouteComponent() {
	const hbMargined = useHbMargined<HTMLHeadingElement>();

	return (
		<div>
			<h1 className="headerbar" ref={hbMargined.ref}>
				Welcome to Gamers' Plane!
			</h1>
			<div style={{ marginInline: `${hbMargined.margin}px` }}>
				<p>Congratulations! Your account has been activated. You can now log in.</p>
				<p>
					We recommend you check out the <Link to="/faqs/">FAQs</Link> and our{" "}
					<Link to="/forums/thread/2461/">New Player Guide</Link> to get an idea of what
					you can do to get started. You can also head straight to make a new{" "}
					<Link to="/characters/my/">character</Link> or find a{" "}
					<Link to="/games/list/">game</Link>, and be sure to stop by the{" "}
					<Link to="/forums/">forums</Link> and{" "}
					<Link to="/forums/14/">introduce yourself</Link>!
				</p>
			</div>
		</div>
	);
}
