import { ApiError } from "#/lib/api";
import type { ReportReason } from "#/queries/reports";

/** The message to show for an invalid report form, or null when it can be sent. */
export const reportFormError = (
	reason: ReportReason | "",
	details: string,
): string | null => {
	if (reason === "") return "Choose a reason for the report.";
	if (reason === "other" && details.trim() === "") {
		return "Tell us what's wrong when the reason is Other.";
	}
	return null;
};

/** Turns a failed report submit into a message that's safe to show the user. */
export const reportErrorMessage = (error: unknown): string => {
	if (error instanceof ApiError) {
		if (error.status === 409) return "You've already reported this.";
		if (error.status === 429) {
			return "You've filed several reports recently. Please try again later.";
		}
		if (error.status === 404) return "That's no longer available to report.";
	}
	return "Something went wrong sending your report. Please try again.";
};
