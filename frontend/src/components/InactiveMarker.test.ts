import { describe, expect, it } from "vitest";
import { inactiveLabel } from "#/components/InactiveMarker";

const NOW = Date.UTC(2026, 9, 10);
const daysAgo = (days: number) =>
	new Date(NOW - days * 24 * 60 * 60 * 1000).toISOString();

describe("inactiveLabel", () => {
	it("is null under 14 days", () => {
		expect(inactiveLabel(daysAgo(13), NOW)).toBeNull();
	});

	it("shows days from 14 through 30", () => {
		expect(inactiveLabel(daysAgo(14), NOW)).toBe("Inactive for 14 days");
		expect(inactiveLabel(daysAgo(30), NOW)).toBe("Inactive for 30 days");
	});

	it("switches to months at 31 days, using floor(days / 30)", () => {
		expect(inactiveLabel(daysAgo(31), NOW)).toBe("Inactive for 1 month");
		expect(inactiveLabel(daysAgo(90), NOW)).toBe("Inactive for 3 months");
	});

	it("says over a year from 12 months on", () => {
		expect(inactiveLabel(daysAgo(359), NOW)).toBe("Inactive for 11 months");
		expect(inactiveLabel(daysAgo(360), NOW)).toBe("Inactive for over a year");
	});

	it("treats no recorded activity as over a year", () => {
		expect(inactiveLabel(null, NOW)).toBe("Inactive for over a year");
	});
});
