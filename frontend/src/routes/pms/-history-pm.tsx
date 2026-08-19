import { Link } from "@tanstack/react-router";
import { TiptapContent } from "#/components/TiptapContent";
import { formatDateTime } from "#/lib/format-date";
import type { PM } from "#/queries/pms";
import styles from "./-history-pm.module.css";

function HistoryPM({ pm, isFirst }: { pm: PM; isFirst: boolean }) {
	return (
		<div className={`${styles["history-pm"]}${isFirst ? ` ${styles.first}` : ""}`}>
			<p className={styles.title}>
				<Link to="/pms/$pmId" params={{ pmId: String(pm.id) }}>
					{pm.title}
				</Link>
			</p>
			<p className={styles.user}>
				from{" "}
				<Link
					to="/user/$userId"
					params={{ userId: String(pm.sender.id) }}
					className="username"
				>
					{pm.sender.username}
				</Link>{" "}
				on <span>{formatDateTime(pm.datestamp)}</span>
			</p>
			<p className={styles.user}>
				to{" "}
				<Link
					to="/user/$userId"
					params={{ userId: String(pm.recipient.id) }}
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
		<div className={styles["pm-history-container"]}>
			{pms.map((pm, index) => (
				<HistoryPM key={pm.id} pm={pm} isFirst={index === 0} />
			))}
		</div>
	);
}
