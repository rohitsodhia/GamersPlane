import { Link } from "@tanstack/react-router";
import { ApiError } from "#/lib/api";
import { useHbMargined } from "#/lib/use-hb-margined";
import NotFound from "./NotFound";

/**
 * Router-wide fallback for errors a route doesn't handle itself. Never shows
 * the error's message or stack.
 */
function ErrorPage({ error }: { error: unknown }) {
	const hbMargined = useHbMargined<HTMLHeadingElement>();

	// A 404 reaching here came from a client-side navigation, where the loader's
	// notFound() isn't involved (e.g. a query that was never guarded).
	if (error instanceof ApiError && error.status === 404) return <NotFound />;

	return (
		<div>
			<h1 className="headerbar" ref={hbMargined.ref}>
				Something went wrong
			</h1>
			<div style={{ marginInline: `${hbMargined.margin}px` }}>
				<p>An unexpected error occurred. Please try again in a moment.</p>
				<p>
					<Link to="/">Return home</Link>
				</p>
			</div>
		</div>
	);
}
export default ErrorPage;
