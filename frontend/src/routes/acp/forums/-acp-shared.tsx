import { ApiError } from "#/lib/api";

export function errorList(exception: unknown): string[] {
	if (exception instanceof ApiError) return exception.errors.map((e) => e.detail);
	return ["Something went wrong."];
}

export function ErrorBanner({ errors }: { errors: string[] }) {
	if (errors.length === 0) return null;
	return (
		<div className="banner error-banner">
			<ul>
				{errors.map((error) => (
					<li key={error}>{error}</li>
				))}
			</ul>
		</div>
	);
}
