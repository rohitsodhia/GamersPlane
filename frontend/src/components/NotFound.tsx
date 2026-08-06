import { useHbMargined } from "#/lib/use-hb-margined";

function NotFound() {
	const hbMargined = useHbMargined<HTMLHeadingElement>();

	return (
		<div>
			<h1 className="headerbar" ref={hbMargined.ref}>
				Page not found
			</h1>
			<div style={{ marginInline: `${hbMargined.margin}px` }}>
				<p>Your treasure is in another dungeon!</p>
				<p>You might want to try looking somewhere else.</p>
			</div>
		</div>
	);
}
export default NotFound;
