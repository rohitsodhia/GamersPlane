import clsx from "clsx";

/**
 * A d6 drawn as a line outline (the cube silhouette of `DieIcon`, unfilled).
 * Stroke is `currentColor`, so recolor or fade it with CSS `color` / `opacity`.
 * Decorative: give the wrapping control its own accessible name.
 */
function DieOutlineIcon({ className }: { className?: string }) {
	return (
		<svg
			className={clsx("die-outline-icon", className)}
			xmlns="http://www.w3.org/2000/svg"
			width="1em"
			height="1em"
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
			strokeWidth="1.6"
			strokeLinecap="round"
			strokeLinejoin="round"
			aria-hidden="true"
			focusable="false"
		>
			<path d="M12 2.5 20.5 7.25v9.5L12 21.5 3.5 16.75v-9.5Z" />
			<path d="M3.5 7.25 12 12l8.5-4.75M12 12v9.5" />
		</svg>
	);
}

export default DieOutlineIcon;
