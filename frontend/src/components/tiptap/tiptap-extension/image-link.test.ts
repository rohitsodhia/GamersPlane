import { Editor, generateHTML, generateJSON, type JSONContent } from "@tiptap/core";
import { Link } from "@tiptap/extension-link";
import { StarterKit } from "@tiptap/starter-kit";
import { describe, expect, it } from "vitest";
import { canSetLink } from "#/components/tiptap/tiptap-ui/link-popover/use-link-popover";
import { FloatImage, safeImageLink } from "./image-extension";

// StarterKit already brings Link; the image sits beside it just as in the editor.
const extensions = [StarterKit, FloatImage];
const imageDoc = (attrs: object): JSONContent => ({
	type: "doc",
	content: [{ type: "image", attrs: { src: "https://img.test/a.png", ...attrs } }],
});
const parse = (html: string): JSONContent => generateJSON(html, extensions);
const imageAttrs = (doc: JSONContent) => doc.content?.[0]?.attrs;

describe("safeImageLink", () => {
	it("accepts http and https and normalizes the address", () => {
		expect(safeImageLink("https://example.com/big.png")).toBe(
			"https://example.com/big.png",
		);
		expect(safeImageLink("  http://example.com  ")).toBe("http://example.com/");
	});

	it.each([
		"javascript:alert(1)",
		"JaVaScRiPt:alert(1)",
		" java\tscript:alert(1)",
		"data:text/html,<script>alert(1)</script>",
		"//example.com/x",
		"/relative/path",
		"example.com/no-scheme",
		"ftp://example.com/x",
		"mailto:a@b.test",
		"https://user:pass@example.com/",
		"https://",
		"",
		"   ",
		`https://example.com/${"a".repeat(2100)}`,
	])("rejects %j", (value) => {
		expect(safeImageLink(value)).toBeNull();
	});

	it("rejects non-strings", () => {
		expect(safeImageLink(undefined)).toBeNull();
		expect(safeImageLink({ href: "https://example.com" })).toBeNull();
	});
});

describe("linked image rendering and parsing", () => {
	it("renders a safe anchor around the image with the address on a data attribute", () => {
		const html = generateHTML(
			imageDoc({ href: "https://example.com/big.png" }),
			extensions,
		);
		expect(html).toContain('<a href="https://example.com/big.png"');
		expect(html).toContain('rel="noopener noreferrer nofollow"');
		expect(html).toContain('target="_blank"');
		expect(html).toContain('data-href="https://example.com/big.png"');
		expect(html).not.toContain("style=");
	});

	it("renders a plain image when there is no link", () => {
		const html = generateHTML(imageDoc({}), extensions);
		expect(html).not.toContain("<a");
		expect(html).not.toContain("data-href");
	});

	it("round-trips the address, and a link survives beside the float", () => {
		const html = generateHTML(
			imageDoc({ href: "https://example.com/big.png", float: "right" }),
			extensions,
		);
		expect(html).toContain('data-float="right"');
		expect(imageAttrs(parse(html))).toMatchObject({
			href: "https://example.com/big.png",
			float: "right",
		});
	});

	it("reads the address from a wrapping anchor when the data attribute is missing", () => {
		const doc = parse(
			'<a href="https://example.com/x"><img src="https://img.test/a.png"></a>',
		);
		expect(doc.content).toHaveLength(1);
		expect(doc.content?.[0]?.type).toBe("image");
		expect(imageAttrs(doc)?.["href"]).toBe("https://example.com/x");
	});

	it("does not give the image a link mark when the Link extension is also loaded", () => {
		const withLink = [StarterKit.configure({ link: false }), Link, FloatImage];
		const html = generateHTML(imageDoc({ href: "https://example.com/x" }), withLink);
		const doc = generateJSON(html, withLink);
		expect(doc.content?.[0]?.marks).toBeUndefined();
		expect(imageAttrs(doc)?.["href"]).toBe("https://example.com/x");
	});

	it.each([
		"javascript:alert(1)",
		"data:text/html,x",
		"//evil.example/x",
	])("never renders or parses a hostile address (%s)", (href) => {
		const rendered = generateHTML(imageDoc({ href }), extensions);
		expect(rendered).not.toContain("<a");
		expect(rendered).not.toContain("data-href");
		const parsed = parse(
			`<a href="${href}"><img src="https://img.test/a.png" data-href="${href}"></a>`,
		);
		expect(imageAttrs(parsed)?.["href"]).toBeNull();
	});
});

describe("image link commands", () => {
	const makeEditor = () =>
		new Editor({
			extensions,
			content: '<p>text</p><img src="https://img.test/a.png">',
		});
	const selectImage = (editor: Editor) => {
		let imagePos = -1;
		editor.state.doc.descendants((node, pos) => {
			if (node.type.name === "image") imagePos = pos;
		});
		editor.commands.setNodeSelection(imagePos);
	};
	const href = (editor: Editor) => editor.getAttributes("image")["href"];

	it("sets, replaces, and removes the link on the selected image", () => {
		const editor = makeEditor();
		selectImage(editor);
		expect(editor.commands.setImageLink("https://example.com/one")).toBe(true);
		expect(href(editor)).toBe("https://example.com/one");
		expect(editor.commands.setImageLink("https://example.com/two")).toBe(true);
		expect(href(editor)).toBe("https://example.com/two");
		expect(editor.commands.unsetImageLink()).toBe(true);
		expect(href(editor)).toBeNull();
		editor.destroy();
	});

	it("refuses an invalid address and leaves the existing link alone", () => {
		const editor = makeEditor();
		selectImage(editor);
		editor.commands.setImageLink("https://example.com/keep");
		expect(editor.commands.setImageLink("javascript:alert(1)")).toBe(false);
		expect(href(editor)).toBe("https://example.com/keep");
		editor.destroy();
	});

	it("keeps the float when the link changes", () => {
		const editor = makeEditor();
		selectImage(editor);
		editor.commands.setImageFloat("left");
		editor.commands.setImageLink("https://example.com/x");
		expect(editor.getAttributes("image")["float"]).toBe("left");
		editor.destroy();
	});

	it("leaves the Link button unavailable while an image is selected", () => {
		const editor = makeEditor();
		expect(canSetLink(editor)).toBe(true);
		selectImage(editor);
		expect(canSetLink(editor)).toBe(false);
		editor.destroy();
	});
});
