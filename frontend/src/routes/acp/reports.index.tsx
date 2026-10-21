import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import clsx from "clsx";
import { z } from "zod";
import { DateTime } from "#/components/DateTime";
import Paginate from "#/components/Paginate";
import { requireAcpPermission } from "#/lib/auth-route";
import { describeReportTarget } from "#/lib/report-targets";
import { useHbMargined } from "#/lib/use-hb-margined";
import {
	REPORT_GROUPS_PER_PAGE,
	REPORT_REASON_LABELS,
	REPORT_STATUSES,
	REPORT_TARGET_LABELS,
	type ReportGroup,
	type ReportStatus,
	reportGroupsQueryOptions,
} from "#/queries/reports";
import styles from "./reports.module.css";

export const Route = createFileRoute("/acp/reports/")({
	loader: requireAcpPermission("manage_reports"),
	component: RouteComponent,
	validateSearch: z.object({
		status: z.enum(REPORT_STATUSES as [ReportStatus, ...ReportStatus[]]).optional(),
		page: z.number().optional(),
	}),
});

const STATUS_LABELS: Record<ReportStatus, string> = {
	open: "Open",
	actioned: "Actioned",
	dismissed: "Dismissed",
};

function GroupRow({ group }: { group: ReportGroup }) {
	const illegal = group.reason === "illegal_content";

	return (
		<div className={clsx(styles["row"], illegal && styles["illegal"])}>
			<div className={styles["summary"]}>
				<span className={styles["target-type"]}>
					{REPORT_TARGET_LABELS[group.target_type]}
				</span>
				<Link
					to="/acp/reports/$targetType/$targetId"
					params={{ targetType: group.target_type, targetId: group.target_id }}
				>
					{describeReportTarget(group.target_type, group.latest_snapshot)}
				</Link>
			</div>
			<div className={styles["meta"]}>
				<span className={clsx(styles["reason"], illegal && styles["reason-illegal"])}>
					{REPORT_REASON_LABELS[group.reason]}
				</span>
				<span>
					{group.count} {group.count === 1 ? "report" : "reports"}
				</span>
				<span>
					Last: <DateTime value={group.last_reported_at} />
				</span>
			</div>
		</div>
	);
}

function RouteComponent() {
	const hbMargined = useHbMargined<HTMLHeadingElement>();
	const { status = "open", page = 1 } = Route.useSearch();

	const { data, isPending, isError } = useQuery(reportGroupsQueryOptions(status, page));

	const pagination = data ? (
		<Paginate
			numItems={data.total}
			itemsPerPage={REPORT_GROUPS_PER_PAGE}
			current={page}
			onPageChange={() => {}}
		/>
	) : null;

	return (
		<div>
			<h2 className="headerbar" ref={hbMargined.ref}>
				Reports
			</h2>
			<div style={{ marginInline: `${hbMargined.margin}px` }}>
				<nav className={styles["tabs"]} aria-label="Report status">
					{REPORT_STATUSES.map((tabStatus) => (
						<Link
							key={tabStatus}
							to="/acp/reports"
							search={{ status: tabStatus === "open" ? undefined : tabStatus }}
							className={clsx(
								styles["tab"],
								tabStatus === status && styles["current-tab"],
							)}
							aria-current={tabStatus === status ? "page" : undefined}
						>
							{STATUS_LABELS[tabStatus]}
						</Link>
					))}
				</nav>

				{isPending && <div className="loading">Loading...</div>}
				{isError && <p className="banner error-banner">Failed to load reports.</p>}

				{data && (
					<>
						{pagination}
						{data.groups.length === 0 ? (
							<div className={styles["no-results"]}>
								No {STATUS_LABELS[status].toLowerCase()} reports.
							</div>
						) : (
							<div className={styles["list"]}>
								{data.groups.map((group) => (
									<GroupRow
										key={`${group.target_type}-${group.target_id}`}
										group={group}
									/>
								))}
							</div>
						)}
						{pagination}
					</>
				)}
			</div>
		</div>
	);
}
