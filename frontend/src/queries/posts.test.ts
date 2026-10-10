import { describe, expect, it } from "vitest";
import { type PostDraw, type PostsResponse, withUpdatedDraw } from "./posts";

function draw(id: number, revealed: boolean[]): PostDraw {
	return {
		id,
		deck_id: 1,
		deck_label: "Deck",
		deck_type: "pcwj",
		reason: "Why",
		cards: [1, 2],
		revealed,
	};
}

const page = {
	count: 2,
	page: 1,
	posts: [
		{ id: 10, draws: [draw(1, [false, false]), draw(2, [false, false])] },
		{ id: 11, draws: [draw(1, [false, false])] },
	],
} as unknown as PostsResponse;

describe("withUpdatedDraw", () => {
	it("replaces only the matching draw on the matching post", () => {
		const updated = draw(2, [true, false]);
		const result = withUpdatedDraw(page, 10, updated) as PostsResponse;
		expect(result.posts[0].draws[0]).toBe(page.posts[0].draws[0]);
		expect(result.posts[0].draws[1]).toBe(updated);
		expect(result.posts[1]).toBe(page.posts[1]);
	});

	it("leaves cache entries that aren't a page of posts alone", () => {
		const details = { id: 10, draws: [] } as never;
		expect(withUpdatedDraw(details, 10, draw(1, [true]))).toBe(details);
		expect(withUpdatedDraw(undefined, 10, draw(1, [true]))).toBeUndefined();
	});
});
