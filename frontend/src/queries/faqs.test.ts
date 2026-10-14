import { describe, expect, it } from "vitest";
import { ApiError } from "#/lib/api";
import { faqErrorMessage } from "./faqs";

describe("faqErrorMessage", () => {
	it("explains a 403 as a permission problem", () => {
		expect(faqErrorMessage(new ApiError(403, []))).toMatch(/permission/);
	});

	it("explains a 404 as a missing FAQ", () => {
		expect(faqErrorMessage(new ApiError(404, []))).toMatch(/no longer exists/);
	});

	it("joins the API's validation details on a 422", () => {
		const error = new ApiError(422, [
			{ code: "a", detail: "Question is too long." },
			{ code: "b", detail: "Answer is required." },
		]);
		expect(faqErrorMessage(error)).toBe("Question is too long. Answer is required.");
	});

	it("falls back to a generic validation message on a 422 with no details", () => {
		expect(faqErrorMessage(new ApiError(422, []))).toMatch(/couldn't be saved/);
	});

	it("falls back to a generic message for network or unknown errors", () => {
		expect(faqErrorMessage(new TypeError("fetch failed"))).toBe(
			"Something went wrong. Please try again.",
		);
	});
});
