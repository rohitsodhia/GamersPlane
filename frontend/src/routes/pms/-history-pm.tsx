import { Link } from "@tanstack/react-router";
import { TiptapContent } from "#/components/TiptapContent";
import { formatDateTime } from "#/lib/format-date";
import type { PM } from "#/queries/pms";

function HistoryPM({ pm, isFirst }: { pm: PM; isFirst: boolean }) {
	return (
		<div className={`history-pm${isFirst ? " first" : ""}`}>
			<p className="title">
				<Link to="/pms/$pmId" params={{ pmId: String(pm.id) }}>
					{pm.title}
				</Link>
			</p>
			<p className="user">
				from{" "}
				<Link to="/user/$id" params={{ id: String(pm.sender.id) }} className="username">
					{pm.sender.username}
				</Link>{" "}
				on <span>{formatDateTime(pm.datestamp)}</span>
			</p>
			<p className="user">
				to{" "}
				<Link
					to="/user/$id"
					params={{ id: String(pm.recipient.id) }}
					className="username"
				>
					{pm.recipient.username}
				</Link>
			</p>
			<TiptapContent content={pm.message} className="message" />
		</div>
	);
}

export function PmHistory({ pms }: { pms: PM[] }) {
	if (pms.length === 0) return null;

	return (
		<div id="pm-history-container">
			{pms.map((pm, index) => (
				<HistoryPM key={pm.id} pm={pm} isFirst={index === 0} />
			))}
		</div>
	);
}
