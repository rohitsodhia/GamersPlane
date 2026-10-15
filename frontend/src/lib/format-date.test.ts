import { describe, expect, it } from "vitest";
import { formatDateTimeShort } from "#/lib/format-date";

// Dates are built in local time, like the formatter's output, so these hold in any
// timezone.
describe("formatDateTimeShort", () => {
	const now = new Date(2026, 9, 20);

	it("leaves out the year for the current one", () => {
		expect(formatDateTimeShort(new Date(2026, 9, 15, 12, 47), now)).toBe(
			"Oct 15, 12:47 pm",
		);
	});

	it("shows the year for any other", () => {
		expect(formatDateTimeShort(new Date(2025, 9, 9, 17, 26), now)).toBe(
			"Oct 9, 2025 5:26 pm",
		);
	});
});
