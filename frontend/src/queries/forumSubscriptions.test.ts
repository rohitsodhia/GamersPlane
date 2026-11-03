import { describe, expect, it } from "vitest";
import { buildSubscriptionTree } from "./forumSubscriptions";

const forum = (id: number, parent_id: number | null, subscribed = true) => ({
	id,
	title: `Forum ${id}`,
	parent_id,
	subscribed,
});

describe("buildSubscriptionTree", () => {
	it("nests forums under their parent, keeping the list order", () => {
		const tree = buildSubscriptionTree([
			forum(1, null, false),
			forum(5, 1),
			forum(6, 5),
			forum(7, 1),
			forum(9, null),
		]);

		expect(tree.map((node) => node.id)).toEqual([1, 9]);
		expect(tree[0].subscribed).toBe(false);
		expect(tree[0].children.map((node) => node.id)).toEqual([5, 7]);
		expect(tree[0].children[0].children.map((node) => node.id)).toEqual([6]);
	});

	it("treats a forum whose parent is missing from the list as top level", () => {
		const tree = buildSubscriptionTree([forum(5, 1)]);

		expect(tree.map((node) => node.id)).toEqual([5]);
	});
});
