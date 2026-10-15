import { formatDateTime, formatDateTimeShort } from "#/lib/format-date";
import styles from "./DateTime.module.css";

/**
 * A date and time in the viewer's timezone: the long form ("May 9, 2026 4:09 am"),
 * or on narrow screens the short one ("May 9, 4:09 am"). Both are in the markup
 * and CSS shows one, so there's no flash and it follows the window size.
 */
export function DateTime({ value }: { value: Date | string | number }) {
	const date = new Date(value);

	return (
		<time dateTime={Number.isNaN(date.getTime()) ? undefined : date.toISOString()}>
			<span className={styles["long"]}>{formatDateTime(value)}</span>
			<span className={styles["short"]}>{formatDateTimeShort(value)}</span>
		</time>
	);
}
