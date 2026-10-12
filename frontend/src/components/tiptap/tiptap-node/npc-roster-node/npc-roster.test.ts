import { generateHTML, generateJSON } from "@tiptap/core";
import { StarterKit } from "@tiptap/starter-kit";
import { describe, expect, it } from "vitest";
import { initialOf, rosterIds, speakerLookup } from "../npc-speaker-node/npc-speaker";
import { NpcRoster } from "./npc-roster-node-extension";

const guard = { id: 1, name: "Guard", image: { id: 10, url: "/npcs/10.png" } };
const thief = { id: 2, name: "Thief", image: null };

const doc = (npcIds: unknown, title = "") => ({
	type: "doc",
	content: [{ type: "npcRoster", attrs: { title, npcIds } }],
});
const render = (body: ReturnType<typeof doc>, npcs = speakerLookup([guard, thief])) =>
	generateHTML(body, [StarterKit, NpcRoster.configure({ npcs })]);

describe("rosterIds", () => {
	it("keeps only well-formed ids, in order", () => {
		expect(rosterIds([3, "4", 0, 1.5, null, 2])).toEqual([3, 2]);
	});

	it("is empty for anything but a list", () => {
		expect(rosterIds(undefined)).toEqual([]);
		expect(rosterIds("1,2")).toEqual([]);
	});
});

describe("initialOf", () => {
	it("is the first letter or digit, upper-cased", () => {
		expect(initialOf("  'old guard")).toBe("O");
		expect(initialOf("!!!")).toBe("?");
		expect(initialOf("\u{1F5E1}魔王")).toBe("魔");
	});
});

describe("roster rendering", () => {
	it("renders the title and a tile per NPC, in order, with image or initial", () => {
		const html = render(doc([2, 1], "The Crew"));

		expect(html).toContain('<div class="npc-roster-title">The Crew</div>');
		expect(html).toContain('<img src="/npcs/10.png"');
		expect(html).toContain("<span>T</span>");
		expect(html.indexOf("Thief")).toBeLessThan(html.indexOf("Guard"));
		expect(html).toContain('data-npc-ids="2,1"');
	});

	it("omits the title heading when there is no title", () => {
		expect(render(doc([1]))).not.toContain("npc-roster-title");
	});

	it("renders an unknown NPC as an Unknown NPC tile", () => {
		const html = render(doc([99]));

		expect(html).toContain("Unknown NPC");
		expect(html).not.toContain("<img");
	});

	it("round-trips its ids and title through the stored HTML", () => {
		const html = render(doc([2, 1], "The Crew"));
		const json = generateJSON(html, [StarterKit, NpcRoster]);

		expect(json.content[0].attrs).toEqual({ title: "The Crew", npcIds: [2, 1] });
	});
});
