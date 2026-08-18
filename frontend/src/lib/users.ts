type LastActivity = Date | string | number;

const INACTIVE_LIMIT = 14;

function daysSince(lastActivity: LastActivity) {
	const MS_PER_DAY = 1000 * 60 * 60 * 24;
	const diffMs = Date.now() - new Date(lastActivity).getTime();
	return Math.floor(diffMs / MS_PER_DAY);
}

export function lastActivityText(lastActivity: LastActivity) {
	const diffDays = daysSince(lastActivity);
	if (diffDays < 1) return "< 1 day ago";
	if (diffDays === 1) return "1 day ago";
	if (diffDays < INACTIVE_LIMIT) return `${diffDays} days ago`;

	if (diffDays <= 30) {
		return `Inactive for ${diffDays} days`;
	}

	const diffMonths = Math.floor(diffDays / 30);
	if (diffMonths < 12)
		return `Inactive for ${diffMonths} month${diffMonths > 1 ? "s" : ""}`;

	return "Inactive forever!";
}

export function getIsActive(lastActivity: LastActivity) {
	const diffDays = daysSince(lastActivity);
	return diffDays < INACTIVE_LIMIT;
}
