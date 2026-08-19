import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { z } from "zod";
import Paginate from "#/components/Paginate";
import { requireAuth } from "#/lib/auth-route";
import { formatDateTime } from "#/lib/format-date";
import { useHbMargined } from "#/lib/use-hb-margined";
import { deletePM, type PM, type PMBox, pmsQueryOptions } from "#/queries/pms";
import styles from "./index.module.css";

export const Route = createFileRoute("/pms/")({
	beforeLoad: requireAuth,
	component: RouteComponent,
	validateSearch: z.object({
		box: z.enum(["inbox", "outbox"]).optional().catch(undefined),
		page: z.number().optional(),
	}),
});

function PMRow({
	pm,
	box,
	onDelete,
}: {
	pm: PM;
	box: PMBox;
	onDelete: (id: number) => void;
}) {
	const isInbox = box === "inbox";
	const read = isInbox ? pm.recipient.read : pm.sender.read;
	const displayedUser = isInbox ? pm.sender : pm.recipient;

	return (
		<div className={`${styles.pm} ${read ? "read" : styles.unread}`}>
			<div className={styles["del-col"]}>
				<button type="button" onClick={() => onDelete(pm.id)}>
					<img src="/images/icons/cross.png" alt="Delete PM" />
				</button>
			</div>
			<div className={styles.info}>
				<div className={styles.title}>
					<Link to="/pms/$pmId" params={{ pmId: String(pm.id) }}>
						{pm.title}
					</Link>
				</div>
				<div className={styles.details}>
					{isInbox ? "from" : "to"}{" "}
					<Link
						to="/user/$userId"
						params={{ userId: String(displayedUser.id) }}
						className="username"
					>
						{displayedUser.username}
					</Link>{" "}
					on <span>{formatDateTime(pm.datestamp)}</span>
				</div>
			</div>
		</div>
	);
}

function RouteComponent() {
	const { box: searchBox, page: searchPage } = Route.useSearch();
	const box = searchBox ?? "inbox";
	const navigate = Route.useNavigate();
	const [page, setPage] = useState(searchPage ?? 1);
	const queryClient = useQueryClient();

	const { data, isPending } = useQuery(pmsQueryOptions({ box, page }));

	const deletePMMutation = useMutation({
		mutationFn: deletePM,
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["pms"] });
		},
	});

	const switchBox = (newBox: PMBox) => {
		navigate({ search: { box: newBox } });
		setPage(1);
	};

	const hbMargined = useHbMargined<HTMLDivElement>();

	return (
		<div>
			<h1 className="headerbar">
				Private Messages - {box.charAt(0).toUpperCase() + box.slice(1)}
			</h1>

			<div
				className="controls-container"
				style={{ marginInlineStart: `${hbMargined.margin}px` }}
			>
				<Link to="/pms/send/" className="skew-btn">
					New PM
				</Link>
				<div>
					<div className="trapezoid">
						<button
							type="button"
							className={`border-box${box === "inbox" ? " current" : ""}`}
							onClick={() => switchBox("inbox")}
						>
							Inbox
						</button>
						<button
							type="button"
							className={`border-box${box === "outbox" ? " current" : ""}`}
							onClick={() => switchBox("outbox")}
						>
							Outbox
						</button>
					</div>
				</div>
			</div>
			<div className={styles["pms-list"]}>
				<div
					className={`headerbar hb-dark listed-items-header ${styles["pms-list-header"]}`}
					ref={hbMargined.ref}
				>
					<div></div>
					<div>Message</div>
				</div>
				<div
					className={styles["pms-list-container"]}
					style={{ marginInline: `${hbMargined.margin}px` }}
				>
					<div>
						{isPending && <div className="loading">Loading...</div>}
						{data?.pms.map((pm) => (
							<PMRow
								key={pm.id}
								pm={pm}
								box={box}
								onDelete={(id) => deletePMMutation.mutate(id)}
							/>
						))}
						{data && data.pms.length === 0 && (
							<div className={styles["no-results"]}>No messages</div>
						)}
					</div>
					{data && (
						<Paginate numItems={data.count} current={page} onPageChange={setPage} />
					)}
				</div>
			</div>
		</div>
	);
}
