import { createFileRoute, Link } from "@tanstack/react-router";
import { useHbMargined } from "#/lib/use-hb-margined";

export const Route = createFileRoute("/characters/")({
	component: RouteComponent,
});

function RouteComponent() {
	const hbMargined = useHbMargined<HTMLHeadingElement>();

	return (
		<div>
			<h1 className="headerbar" ref={hbMargined.ref}>
				My Characters
			</h1>

			<Link to="/characters/sheets">Character Sheets</Link>
		</div>
	);
}
