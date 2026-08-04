import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { z } from "zod";
import Paginate from "#/components/Paginate";
import { requireAuth } from "#/lib/auth-route";
import { formatDateTime } from "#/lib/format-date";
import { useHbMargined } from "#/lib/use-hb-margined";
import { deletePM, type PM, type PMBox, pmsQueryOptions } from "#/queries/pms";

export const Route = createFileRoute("/pms/")({
	beforeLoad: requireAuth,
	component: RouteComponent,
	validateSearch: z.object({
		box: z.enum(["inbox", "outbox"]).optional().catch(undefined),
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
		<div id={`pm-${pm.id}`} className={`pm tr${read ? "" : " new"}`}>
			<div className="del-col">
				<button type="button" onClick={() => onDelete(pm.id)}>
					<img src="/images/icons/cross.png" alt="Delete PM" />
				</button>
			</div>
			<div className="info">
				<div className="title">
					<Link to="/pms/$id" params={{ id: String(pm.id) }}>
						{pm.title}
					</Link>
				</div>
				<div className="details">
					{isInbox ? "from" : "to"}{" "}
					<Link
						to="/user/$id"
						params={{ id: String(displayedUser.id) }}
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
	const { box: searchBox } = Route.useSearch();
	const box = searchBox ?? "inbox";
	const navigate = Route.useNavigate();
	const [page, setPage] = useState(1);
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
				id="pms-controls-container"
				style={{ marginInlineStart: `${hbMargined.margin}px` }}
			>
				<Link to="/pms/send/" className="trap-btn">
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
			<div id="pms-list">
				<div id="pms-list-header" className="headerbar hb-dark" ref={hbMargined.ref}>
					&nbsp;
				</div>
				<div id="pms-list-container" style={{ marginInline: `${hbMargined.margin}px` }}>
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
						<div className="no-results">No messages</div>
					)}
					{data && (
						<Paginate
							numItems={data.count}
							itemsPerPage={1}
							current={page}
							onPageChange={setPage}
						/>
					)}
				</div>
			</div>
		</div>
	);
}
