import { createFileRoute } from "@tanstack/react-router";
import { useHbMargined } from "#/lib/use-hb-margined";

export const Route = createFileRoute("/403")({
	component: Forbidden,
});

function Forbidden() {
	const hbMargined = useHbMargined<HTMLHeadingElement>();

	return (
		<div>
			<h1 className="headerbar" ref={hbMargined.ref}>
				Forbidden
			</h1>
			<div style={{ marginInline: `${hbMargined.margin}px` }}>
				<p>You don't have permission to view this page.</p>
			</div>
		</div>
	);
}
