import { describe, expect, it } from "vitest";
import { ApiError } from "#/lib/api";
import { reportErrorMessage, reportFormError } from "./report-dialog";

describe("reportFormError", () => {
	it("requires a reason to be chosen", () => {
		expect(reportFormError("", "Some details")).not.toBeNull();
	});

	it("requires details only when the reason is other", () => {
		expect(reportFormError("other", "")).not.toBeNull();
		expect(reportFormError("other", "   ")).not.toBeNull();
		expect(reportFormError("other", "Impersonation")).toBeNull();
		expect(reportFormError("spam", "")).toBeNull();
	});
});

describe("reportErrorMessage", () => {
	it("maps known statuses to friendly messages", () => {
		expect(reportErrorMessage(new ApiError(409, []))).toBe(
			"You've already reported this.",
		);
		expect(reportErrorMessage(new ApiError(429, []))).toMatch(/several reports/);
		expect(reportErrorMessage(new ApiError(404, []))).toMatch(/no longer available/);
	});

	it("falls back to a generic message", () => {
		expect(reportErrorMessage(new ApiError(500, []))).toMatch(/Something went wrong/);
		expect(reportErrorMessage(new Error("network"))).toMatch(/Something went wrong/);
	});
});
