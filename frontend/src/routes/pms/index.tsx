import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import Paginate from "#/components/Paginate";
import { requireAuth } from "#/lib/auth-route";
import { useHbMargined } from "#/lib/use-hb-margined";
import { deletePM, type PM, type PMBox, pmsQueryOptions } from "#/queries/pms";

export const Route = createFileRoute("/pms/")({
	beforeLoad: requireAuth,
	component: RouteComponent,
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
	const read = box === "inbox" ? pm.recipient.read : pm.sender.read;

	return (
		<div id={`pm-${pm.id}`} className={`pm tr${read ? "" : " new"}`}>
			<div className="del-col">
				<button
					type="button"
					onClick={() => onDelete(pm.id)}
					className="delete-pm sprite cross"
				/>
			</div>
			<div className="info">
				<div className="title">
					<Link to="/pms/$id" params={{ id: String(pm.id) }}>
						{pm.title}
					</Link>
				</div>
				{box === "inbox" ? (
					<div className="details">
						from{" "}
						<Link
							to="/user/$id"
							params={{ id: String(pm.sender.id) }}
							className="username"
						>
							{pm.sender.username}
						</Link>{" "}
						on <span>{pm.datestamp}</span>
					</div>
				) : (
					<div className="details">
						to{" "}
						<Link
							to="/user/$id"
							params={{ id: String(pm.recipient.id) }}
							className="username"
						>
							{pm.recipient.username}
						</Link>{" "}
						on <span>{pm.datestamp}</span>
					</div>
				)}
			</div>
		</div>
	);
}

function RouteComponent() {
	const [box, setBox] = useState<PMBox>("inbox");
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
		setBox(newBox);
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
			<div>
				<div id="pms-list-header" className="headerbar hb-dark" ref={hbMargined.ref}>
					<div className="del-col" />
					<div className="info">Message</div>
				</div>
				<div style={{ marginInline: `${hbMargined.margin}px` }}>
					<div id="pms-list">
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
					</div>
					<div>
						{data && (
							<Paginate
								numItems={data.count}
								itemsPerPage={data.limit}
								current={page}
								onPageChange={setPage}
							/>
						)}
					</div>
				</div>
			</div>
		</div>
	);
}
