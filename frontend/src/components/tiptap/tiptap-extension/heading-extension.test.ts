import { generateHTML, type JSONContent } from "@tiptap/core";
import { StarterKit } from "@tiptap/starter-kit";
import { describe, expect, it } from "vitest";
import { BannerHeading } from "./heading-extension";

const extensions = [StarterKit.configure({ heading: false }), BannerHeading];

const headingDoc = (level: unknown): JSONContent => ({
	type: "doc",
	content: [
		{ type: "heading", attrs: { level }, content: [{ type: "text", text: "T" }] },
	],
});
const render = (level: unknown) => generateHTML(headingDoc(level), extensions);

describe("BannerHeading", () => {
	it("gives h1 the headerbar class and h2 the dark one", () => {
		expect(render(1)).toBe('<h1 class="headerbar">T</h1>');
		expect(render(2)).toBe('<h2 class="headerbar hb-dark">T</h2>');
	});

	it.each([3, 4])("leaves h%i plain", (level) => {
		const html = render(level);
		expect(html).toContain(`<h${level}`);
		expect(html).not.toContain("headerbar");
	});

	it("renders a level outside the allowed ones as the first allowed level", () => {
		expect(render(9)).toBe('<h1 class="headerbar">T</h1>');
		expect(render("evil")).toBe('<h1 class="headerbar">T</h1>');
	});
});
