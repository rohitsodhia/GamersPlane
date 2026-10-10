import { describe, expect, it } from "vitest";
import type { PollData } from "#/queries/threads";
import {
	canSubmitVote,
	percentOfVoters,
	plainNote,
	pollView,
	toggleSelection,
} from "./-thread-poll-state";

const poll = (overrides: Partial<PollData> = {}): PollData => ({
	question: "Q",
	options_per_user: 1,
	allow_revoting: false,
	options: [],
	my_votes: [],
	voted: false,
	can_vote: false,
	show_results: false,
	total_voters: null,
	...overrides,
});

describe("pollView", () => {
	it("shows the form to a viewer who can vote and hasn't", () => {
		expect(pollView(poll({ can_vote: true }), false)).toBe("voting");
	});

	it("shows results to a creator who hasn't voted", () => {
		expect(pollView(poll({ can_vote: true, show_results: true }), false)).toBe(
			"results",
		);
	});

	it("shows results after voting", () => {
		const voted = poll({ can_vote: true, voted: true, show_results: true });
		expect(pollView(voted, false)).toBe("results");
	});

	it("returns to the form when changing a vote", () => {
		const voted = poll({ can_vote: true, voted: true, show_results: true });
		expect(pollView(voted, true)).toBe("voting");
	});

	it("ignores a stale changing flag once voting is no longer allowed", () => {
		const closed = poll({ voted: true, show_results: true });
		expect(pollView(closed, true)).toBe("results");
	});

	it("shows plain options when neither voting nor results are available", () => {
		expect(pollView(poll(), false)).toBe("plain");
	});
});

describe("plainNote", () => {
	it("asks guests to log in and tells members they lack permission", () => {
		expect(plainNote(false)).toBe("Log in to vote.");
		expect(plainNote(true)).toBe("You can't vote in this forum.");
	});
});

describe("percentOfVoters", () => {
	it("rounds to a whole percent of voters", () => {
		expect(percentOfVoters(1, 3)).toBe(33);
		expect(percentOfVoters(2, 3)).toBe(67);
	});

	it("is 0 with no voters or hidden counts", () => {
		expect(percentOfVoters(0, 0)).toBe(0);
		expect(percentOfVoters(null, null)).toBe(0);
	});
});

describe("toggleSelection", () => {
	it("adds an option under the cap", () => {
		expect(toggleSelection([1], 2, 2)).toEqual([1, 2]);
	});

	it("ignores an unchecked option at the cap", () => {
		expect(toggleSelection([1, 2], 3, 2)).toEqual([1, 2]);
	});

	it("removes a checked option even at the cap", () => {
		expect(toggleSelection([1, 2], 1, 2)).toEqual([2]);
	});
});

describe("canSubmitVote", () => {
	it("needs at least one choice", () => {
		expect(canSubmitVote([], 2)).toBe(false);
	});

	it("allows one up to the cap", () => {
		expect(canSubmitVote([1], 2)).toBe(true);
		expect(canSubmitVote([1, 2], 2)).toBe(true);
	});

	it("rejects more than the cap (e.g. a preselection after the cap was lowered)", () => {
		expect(canSubmitVote([1, 2, 3], 2)).toBe(false);
	});
});
