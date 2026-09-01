import { createFileRoute } from "@tanstack/react-router";
import { useHbMargined } from "#/lib/use-hb-margined";

export const Route = createFileRoute("/acp/")({
	component: RouteComponent,
});

function RouteComponent() {
	const hbMargined = useHbMargined<HTMLHeadingElement>();

	return (
		<div>
			<h2 className="headerbar" ref={hbMargined.ref}>
				Admin Control Panel
			</h2>
		</div>
	);
}
