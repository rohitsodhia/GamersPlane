import { Focusable, Tooltip, TooltipTrigger } from "react-aria-components";
import styles from "./InactiveMarker.module.css";

const MS_PER_DAY = 1000 * 60 * 60 * 24;
const INACTIVE_AFTER_DAYS = 14;
const MAX_DAYS_SHOWN = 30;
const DAYS_PER_MONTH = 30;
const MONTHS_PER_YEAR = 12;

/**
 * The "Inactive for ..." text for a user's last activity, or null while they're
 * still active (under 14 days). No recorded activity counts as over a year.
 * Ported from the legacy `User::inactive`.
 */
export function inactiveLabel(
	lastActivity: string | null,
	now: number = Date.now(),
): string | null {
	if (lastActivity === null) return "Inactive for over a year";

	const days = Math.floor((now - new Date(lastActivity).getTime()) / MS_PER_DAY);
	if (days < INACTIVE_AFTER_DAYS) return null;
	if (days <= MAX_DAYS_SHOWN) return `Inactive for ${days} days`;

	const months = Math.floor(days / DAYS_PER_MONTH);
	if (months >= MONTHS_PER_YEAR) return "Inactive for over a year";
	return `Inactive for ${months} month${months === 1 ? "" : "s"}`;
}

export function InactiveMarker({ lastActivity }: { lastActivity: string | null }) {
	const label = inactiveLabel(lastActivity);
	if (label === null) return null;

	return (
		<TooltipTrigger delay={200}>
			<Focusable>
				<span className={styles["marker"]}>
					<img src="/images/icons/sleeping.png" alt={label} />
				</span>
			</Focusable>
			<Tooltip className={styles["tooltip"]} offset={6}>
				{label}
			</Tooltip>
		</TooltipTrigger>
	);
}
