import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { isContentEmpty } from "#/components/Editor";
import { TiptapContent } from "#/components/TiptapContent";
import { redirectToLoginOnAuthFailure } from "#/lib/auth-route";
import { formatDate } from "#/lib/format-date";
import { useHbMargined } from "#/lib/use-hb-margined";
import {
	characterSheetQueryOptions,
	characterSheetVersionsQueryOptions,
} from "#/queries/characterSheet";
import styles from "./changelog.module.css";

export const Route = createFileRoute("/characters/sheets/$sheetId/changelog")({
	params: {
		parse: (params) => ({ sheetId: Number(params.sheetId) }),
	},
	loader: ({ context, params, location }) =>
		redirectToLoginOnAuthFailure(
			Promise.all([
				context.queryClient.ensureQueryData(characterSheetQueryOptions(params.sheetId)),
				context.queryClient.ensureQueryData(
					characterSheetVersionsQueryOptions(params.sheetId),
				),
			]),
			location,
		),
	component: RouteComponent,
});

function RouteComponent() {
	const { sheetId } = Route.useParams();
	const { data: sheet } = useSuspenseQuery(characterSheetQueryOptions(sheetId));
	const { data: versions } = useSuspenseQuery(
		characterSheetVersionsQueryOptions(sheetId),
	);
	const hbMargined = useHbMargined<HTMLHeadingElement>();

	return (
		<div>
			<div style={{ marginLeft: hbMargined.margin }}>
				<Link to="/characters/sheets/$sheetId" params={{ sheetId }}>
					Back to {sheet.name}
				</Link>
			</div>
			<h1 className="headerbar" ref={hbMargined.ref}>
				{sheet.name} Change Log
			</h1>

			{versions.length === 0 ? (
				<p>No versions have been published yet.</p>
			) : (
				<ol className={styles["versions"]}>
					{versions.map((version, index) => (
						<li key={version.number} className={styles["version"]}>
							<div className={styles["version-meta"]}>
								<h2 className={styles["version-number"]}>v{version.number}</h2>
								<time dateTime={version.published_at}>
									{formatDate(version.published_at)}
								</time>
								{index === 0 ? (
									<span className={styles["current"]}>Current</span>
								) : null}
							</div>
							{version.changelog && !isContentEmpty(version.changelog) ? (
								<TiptapContent content={version.changelog} />
							) : (
								<p className={styles["no-notes"]}>No notes for this version.</p>
							)}
						</li>
					))}
				</ol>
			)}
		</div>
	);
}
