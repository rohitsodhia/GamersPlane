import type { PollData } from "#/queries/threads";

export type PollView = "voting" | "results" | "plain";

// Results win over the form, so a creator who hasn't voted sees them (with a Vote
// button). `changing` is the viewer's choice to open the form from the results.
export function pollView(poll: PollData, changing: boolean): PollView {
	if (poll.can_vote && (changing || !poll.show_results)) return "voting";
	return poll.show_results ? "results" : "plain";
}

// Why a viewer who sees neither the form nor results can't vote.
export function plainNote(loggedIn: boolean): string {
	return loggedIn ? "You can't vote in this forum." : "Log in to vote.";
}

// Share of voters (not of votes: with several choices each, votes can exceed
// voters), rounded to a whole percent.
export function percentOfVoters(
	votes: number | null,
	totalVoters: number | null,
): number {
	if (!votes || !totalVoters) return 0;
	return Math.round((votes / totalVoters) * 100);
}

// Checking past the cap is ignored; unchecking always works.
export function toggleSelection(selected: number[], id: number, max: number): number[] {
	if (selected.includes(id)) return selected.filter((s) => s !== id);
	if (selected.length >= max) return selected;
	return [...selected, id];
}

export function canSubmitVote(selected: number[], max: number): boolean {
	return selected.length >= 1 && selected.length <= max;
}
