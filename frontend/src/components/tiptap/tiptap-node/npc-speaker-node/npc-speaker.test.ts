import { generateHTML } from "@tiptap/core";
import { StarterKit } from "@tiptap/starter-kit";
import { describe, expect, it } from "vitest";
import {
	filterSpeakers,
	findSpeaker,
	flattenNpcBlocks,
	speakerFor,
	speakerLookup,
	UNKNOWN_SPEAKER,
} from "./npc-speaker";
import { NpcSpeaker } from "./npc-speaker-node-extension";

const guard = { id: 1, name: "Guard", image: { id: 10, url: "/npcs/10.png" } };
const thief = { id: 2, name: "Thief", image: null };

describe("speakerFor", () => {
	it("looks the NPC up by id", () => {
		expect(speakerFor(1, speakerLookup([guard, thief]))).toEqual(guard);
	});

	it("gives a neutral placeholder for an unlisted or malformed id", () => {
		const lookup = speakerLookup([guard]);

		expect(speakerFor(99, lookup)).toBe(UNKNOWN_SPEAKER);
		expect(speakerFor(null, lookup)).toBe(UNKNOWN_SPEAKER);
		expect(speakerFor("1", lookup)).toBe(UNKNOWN_SPEAKER);
	});
});

describe("findSpeaker", () => {
	it("prefers the live library over the post's own copy", () => {
		const renamed = { ...guard, name: "Captain" };

		expect(findSpeaker(1, [renamed], [guard]).name).toBe("Captain");
	});

	it("falls back to the post's copy for an NPC the library no longer lists", () => {
		expect(findSpeaker(2, [guard], [thief]).name).toBe("Thief");
	});

	it("is unknown when neither has it", () => {
		expect(findSpeaker(3, [guard], [thief])).toBe(UNKNOWN_SPEAKER);
	});
});

describe("filterSpeakers", () => {
	const npcs = [{ name: "Old Guard" }, { name: "Guardian" }, { name: "Thief" }];

	it("matches a substring of the name, ignoring case, in list order", () => {
		expect(filterSpeakers(npcs, "gUARD").map((npc) => npc.name)).toEqual([
			"Old Guard",
			"Guardian",
		]);
	});

	it("returns everything for a blank search", () => {
		expect(filterSpeakers(npcs, "  ")).toHaveLength(3);
	});
});

describe("flattenNpcBlocks", () => {
	const para = (text: string) => ({
		type: "paragraph",
		content: [{ type: "text", text }],
	});
	const speakerBlock = (npcId: number, ...content: object[]) => ({
		type: "npcSpeaker",
		attrs: { npcId },
		content,
	});
	const bold = (text: string) => ({
		type: "paragraph",
		content: [{ type: "text", text, marks: [{ type: "bold" }] }],
	});

	it("replaces a block with a bold name line and its content", () => {
		const nodes = [para("Before"), speakerBlock(1, para("Halt!"), para("Who?"))];

		expect(flattenNpcBlocks(nodes, [guard])).toEqual([
			para("Before"),
			bold("Guard:"),
			para("Halt!"),
			para("Who?"),
		]);
	});

	it("flattens blocks nested in other nodes", () => {
		const list = {
			type: "bulletList",
			content: [{ type: "listItem", content: [speakerBlock(2, para("Hi"))] }],
		};

		expect(flattenNpcBlocks([list], [thief])).toEqual([
			{
				type: "bulletList",
				content: [{ type: "listItem", content: [bold("Thief:"), para("Hi")] }],
			},
		]);
	});

	it("names an unlisted speaker as unknown", () => {
		expect(flattenNpcBlocks([speakerBlock(9, para("Hi"))], [])[0]).toEqual(
			bold("Unknown NPC:"),
		);
	});

	describe("rosters", () => {
		const rosterBlock = (npcIds: unknown, title?: string) => ({
			type: "npcRoster",
			attrs: { title, npcIds },
		});
		const text = (value: string, marks?: object[]) => ({
			type: "text",
			text: value,
			...(marks ? { marks } : {}),
		});

		it("becomes a paragraph of the bold title then the comma-separated names", () => {
			expect(
				flattenNpcBlocks([rosterBlock([1, 2], "The Crew")], [guard, thief]),
			).toEqual([
				{
					type: "paragraph",
					content: [text("The Crew:", [{ type: "bold" }]), text(" Guard, Thief")],
				},
			]);
		});

		it("is just the names without a title", () => {
			expect(flattenNpcBlocks([rosterBlock([2, 1], "")], [guard, thief])).toEqual([
				{ type: "paragraph", content: [text("Thief, Guard")] },
			]);
		});

		it("names a missing NPC as unknown", () => {
			expect(flattenNpcBlocks([rosterBlock([1, 9])], [guard])).toEqual([
				{ type: "paragraph", content: [text("Guard, Unknown NPC")] },
			]);
		});

		it("flattens a roster nested in another node", () => {
			const list = {
				type: "bulletList",
				content: [{ type: "listItem", content: [rosterBlock([1])] }],
			};

			expect(flattenNpcBlocks([list], [guard])).toEqual([
				{
					type: "bulletList",
					content: [
						{
							type: "listItem",
							content: [{ type: "paragraph", content: [text("Guard")] }],
						},
					],
				},
			]);
		});

		it("gives an empty paragraph, not an empty text node, with nothing to show", () => {
			expect(flattenNpcBlocks([rosterBlock([])], [])).toEqual([{ type: "paragraph" }]);
		});
	});

	it("leaves content without speakers unchanged", () => {
		const nodes = [para("a"), { type: "horizontalRule" }];

		expect(flattenNpcBlocks(nodes, [guard])).toStrictEqual(nodes);
	});
});

describe("speaker block rendering", () => {
	const doc = (npcId: unknown) => ({
		type: "doc",
		content: [
			{
				type: "npcSpeaker",
				attrs: { npcId },
				content: [{ type: "paragraph", content: [{ type: "text", text: "Halt!" }] }],
			},
		],
	});
	const render = (npcId: unknown, npcs = speakerLookup([guard, thief])) =>
		generateHTML(doc(npcId), [StarterKit, NpcSpeaker.configure({ npcs })]);

	it("renders the NPC's name, avatar and the block's content", () => {
		const html = render(1);

		expect(html).toContain('data-npc-id="1"');
		expect(html).toContain('<img src="/npcs/10.png"');
		expect(html).toContain("Guard");
		expect(html).toContain("<p>Halt!</p>");
	});

	it("renders an unknown NPC as a neutral bubble rather than failing", () => {
		const html = render(99);

		expect(html).toContain("Unknown NPC");
		expect(html).toContain("<p>Halt!</p>");
		expect(html).not.toContain("<img");
	});

	it("renders an NPC without an image with its initial", () => {
		expect(render(2)).toContain("<span>T</span>");
	});
});
