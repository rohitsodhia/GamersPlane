import {
	useMutation,
	useQuery,
	useQueryClient,
	useSuspenseQuery,
} from "@tanstack/react-query";
import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import clsx from "clsx";
import { useState } from "react";
import { ConfirmDialog } from "#/components/ConfirmDialog";
import { DateTime } from "#/components/DateTime";
import { requireAcpPermission } from "#/lib/auth-route";
import { notFoundOnMissing, requirePositiveId } from "#/lib/not-found-route";
import { describeReportTarget, reportTargetLink } from "#/lib/report-targets";
import { useHbMargined } from "#/lib/use-hb-margined";
import {
	IMAGE_TARGET_TYPES,
	invalidateReports,
	REPORT_DETAILS_MAX,
	REPORT_REASON_LABELS,
	REPORT_TARGET_LABELS,
	REPORT_TARGET_TYPES,
	type ReportSnapshot,
	type ReportTargetType,
	removeReportedImage,
	reportActionErrorMessage,
	reportSnapshotImageQueryOptions,
	resolveReports,
	type TargetReport,
	targetReportsQueryOptions,
} from "#/queries/reports";
import styles from "./reports.$targetType.$targetId.module.css";

export const Route = createFileRoute("/acp/reports/$targetType/$targetId")({
	params: {
		parse: (params) => ({
			targetType: params.targetType as ReportTargetType,
			targetId: Number(params.targetId),
		}),
		stringify: ({ targetType, targetId }) => ({
			targetType,
			targetId: String(targetId),
		}),
	},
	beforeLoad: ({ params }) => {
		if (!REPORT_TARGET_TYPES.includes(params.targetType)) throw notFound();
		requirePositiveId(params.targetId);
	},
	loader: async ({ context, params }) => {
		await requireAcpPermission("manage_reports")({ context });
		await notFoundOnMissing(
			context.queryClient.ensureQueryData(
				targetReportsQueryOptions(params.targetType, params.targetId),
			),
		);
	},
	component: RouteComponent,
});

/** Text snapshots as plain text with their line breaks. */
function SnapshotText({ snapshot }: { snapshot: ReportSnapshot }) {
	const title = typeof snapshot.title === "string" ? snapshot.title : null;
	const body = typeof snapshot.body_text === "string" ? snapshot.body_text : null;
	if (!title && !body) return null;

	return (
		<div className={styles["snapshot"]}>
			{title && <strong>{title}</strong>}
			{body && <p className={styles["snapshot-body"]}>{body}</p>}
		</div>
	);
}

function SnapshotImage({ reportId }: { reportId: number }) {
	const { data, isPending, isError } = useQuery(
		reportSnapshotImageQueryOptions(reportId),
	);

	if (isPending) return <div className="loading">Loading image...</div>;
	if (isError) return <p className="banner error-banner">Failed to load the image.</p>;
	return <img className={styles["snapshot-image"]} src={data} alt="Reported content" />;
}

function ReportCard({ report }: { report: TargetReport }) {
	return (
		<article className={styles["report"]}>
			<header className={styles["report-header"]}>
				<span
					className={clsx(
						styles["reason"],
						report.reason === "illegal_content" && styles["reason-illegal"],
					)}
				>
					{REPORT_REASON_LABELS[report.reason]}
				</span>
				<span>
					by{" "}
					<Link to="/user/$userId" params={{ userId: report.reporter.id }}>
						{report.reporter.username}
					</Link>
				</span>
				<DateTime value={report.created_at} />
				<span className={styles["status"]}>{report.status}</span>
			</header>
			{report.details && <p className={styles["snapshot-body"]}>{report.details}</p>}
			{report.status !== "open" && (
				<p className={styles["resolution"]}>
					{report.status === "actioned" ? "Actioned" : "Dismissed"}
					{report.resolved_by && (
						<>
							{" "}
							by{" "}
							<Link to="/user/$userId" params={{ userId: report.resolved_by.id }}>
								{report.resolved_by.username}
							</Link>
						</>
					)}
					{report.resolved_at && (
						<>
							{" "}
							<DateTime value={report.resolved_at} />
						</>
					)}
					{report.resolution_note && <>: {report.resolution_note}</>}
				</p>
			)}
		</article>
	);
}

function ActionPanel({
	targetType,
	targetId,
}: {
	targetType: ReportTargetType;
	targetId: number;
}) {
	const queryClient = useQueryClient();
	const [note, setNote] = useState("");
	const [error, setError] = useState<string | null>(null);
	const [confirmingRemove, setConfirmingRemove] = useState(false);
	const isImage = IMAGE_TARGET_TYPES.includes(targetType);

	const onSuccess = () => {
		setError(null);
		setNote("");
		return invalidateReports(queryClient);
	};
	const onError = (e: unknown) => setError(reportActionErrorMessage(e));

	const resolve = useMutation({ mutationFn: resolveReports, onSuccess, onError });
	const remove = useMutation({ mutationFn: removeReportedImage, onSuccess, onError });
	const busy = resolve.isPending || remove.isPending;

	const submit = (status: "actioned" | "dismissed") =>
		resolve.mutate({ type: targetType, id: targetId, status, note: note.trim() });

	return (
		<section className={styles["actions"]}>
			<h3>Resolve</h3>
			{error && <p className="banner error-banner">{error}</p>}
			<label htmlFor="resolution-note">Note (optional)</label>
			<textarea
				id="resolution-note"
				value={note}
				maxLength={REPORT_DETAILS_MAX}
				rows={3}
				onChange={(e) => setNote(e.target.value)}
			/>
			<div className={styles["action-buttons"]}>
				<button
					type="button"
					className="skew-btn"
					disabled={busy}
					onClick={() => submit("dismissed")}
				>
					Dismiss
				</button>
				<button
					type="button"
					className="skew-btn"
					disabled={busy}
					onClick={() => submit("actioned")}
				>
					Mark actioned
				</button>
				{isImage && (
					<button
						type="button"
						className="skew-btn"
						disabled={busy}
						onClick={() => setConfirmingRemove(true)}
					>
						Remove image
					</button>
				)}
			</div>
			<p className={styles["hint"]}>
				Dismiss and Mark actioned close every open report on this item. To delete a post
				or thread, or to ban a user, use the link above and do it from their own page,
				then mark the reports actioned.
			</p>
			<ConfirmDialog
				isOpen={confirmingRemove}
				onOpenChange={setConfirmingRemove}
				message="Remove this image? It's taken down right away and kept in quarantine, and every open report on it is marked actioned."
				onConfirm={() => remove.mutate({ type: targetType, id: targetId })}
			/>
		</section>
	);
}

function RouteComponent() {
	const { targetType, targetId } = Route.useParams();
	const hbMargined = useHbMargined<HTMLHeadingElement>();
	const { data } = useSuspenseQuery(targetReportsQueryOptions(targetType, targetId));

	// Oldest first, so the snapshot shown is from the last one.
	const reports = data.reports;
	const latest = reports.at(-1);
	const snapshot = latest?.snapshot ?? {};
	const link = reportTargetLink(targetType, targetId, snapshot);
	const description = describeReportTarget(targetType, snapshot);
	const hasOpen = reports.some((report) => report.status === "open");
	const fileReport = reports.find((report) => report.has_snapshot_file);

	return (
		<div>
			<h2 className="headerbar" ref={hbMargined.ref}>
				{REPORT_TARGET_LABELS[targetType]} reports
			</h2>
			<div style={{ marginInline: `${hbMargined.margin}px` }}>
				<p>
					<Link to="/acp/reports">&laquo; Back to reports</Link>
				</p>

				<section className={styles["target"]}>
					<h3>
						{link ? (
							// biome-ignore lint/suspicious/noExplicitAny: link is a union of typed routes
							<Link {...(link as any)}>{description}</Link>
						) : (
							description
						)}
					</h3>
					{targetType === "npc_image" && (
						<p>
							NPC images have no page of their own. Game{" "}
							{String(snapshot.game_id ?? "-")}, user {String(snapshot.user_id ?? "-")}.
						</p>
					)}
					<SnapshotText snapshot={snapshot} />
					{fileReport && <SnapshotImage reportId={fileReport.id} />}
					{IMAGE_TARGET_TYPES.includes(targetType) && !fileReport && (
						<p className={styles["hint"]}>No copy of the image was kept.</p>
					)}
				</section>

				{hasOpen && <ActionPanel targetType={targetType} targetId={targetId} />}

				<section>
					<h3>
						{reports.length} {reports.length === 1 ? "report" : "reports"}
					</h3>
					{reports.map((report) => (
						<ReportCard key={report.id} report={report} />
					))}
				</section>
			</div>
		</div>
	);
}
