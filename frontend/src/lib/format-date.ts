const dateTimeFormatter = new Intl.DateTimeFormat("en-US", {
	month: "long",
	day: "numeric",
	year: "numeric",
	hour: "numeric",
	minute: "2-digit",
	hour12: true,
});

const shortDateTimeFormatter = new Intl.DateTimeFormat("en-US", {
	month: "short",
	day: "numeric",
	year: "numeric",
	hour: "numeric",
	minute: "2-digit",
	hour12: true,
});

const dateFormatter = new Intl.DateTimeFormat("en-US", {
	month: "long",
	day: "numeric",
	year: "numeric",
});

// Produces "May 9, 2026"
export function formatDate(date: Date | string | number) {
	return dateFormatter.format(new Date(date));
}

// Produces "May 9, 2026 4:09 am" (Intl's dateStyle/timeStyle shortcuts insert
// "at" and uppercase AM/PM, so the parts are assembled manually instead).
export function formatDateTime(date: Date | string | number) {
	const parts = dateTimeFormatter.formatToParts(new Date(date));
	const get = (type: Intl.DateTimeFormatPartTypes) =>
		parts.find((part) => part.type === type)?.value;

	return `${get("month")} ${get("day")}, ${get("year")} ${get("hour")}:${get("minute")} ${get("dayPeriod")?.toLowerCase()}`;
}

// Produces "May 9, 4:09 am", or "May 9, 2025 4:09 am" for a year other than the
// current one (`now` is for tests). For narrow screens; see the DateTime component.
export function formatDateTimeShort(date: Date | string | number, now = new Date()) {
	const value = new Date(date);
	const parts = shortDateTimeFormatter.formatToParts(value);
	const get = (type: Intl.DateTimeFormatPartTypes) =>
		parts.find((part) => part.type === type)?.value;
	// Local time, like the parts above.
	const year = value.getFullYear() === now.getFullYear() ? "" : ` ${get("year")}`;

	return `${get("month")} ${get("day")},${year} ${get("hour")}:${get("minute")} ${get("dayPeriod")?.toLowerCase()}`;
}
