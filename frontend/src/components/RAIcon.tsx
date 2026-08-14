import clsx from "clsx";

function RAIcon({ className, title }: { className?: string; title?: string }) {
	if (title) {
		return (
			<span className={clsx("ra", className)} role="img" aria-label={title}></span>
		);
	}
	return <span className={clsx("ra", className)} aria-hidden="true"></span>;
}
export default RAIcon;
