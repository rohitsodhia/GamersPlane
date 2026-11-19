import { generateHTML, type JSONContent } from "@tiptap/core";
import { describe, expect, it } from "vitest";
import { extensionsFor } from "#/components/TiptapContent";
import { sanitizeHtml } from "#/components/tiptap/sanitize-html";
import { isAllowedLinkUri } from "#/components/tiptap/tiptap-extension/link-options";

function parse(html: string): HTMLElement {
	const root = document.createElement("div");
	root.innerHTML = sanitizeHtml(html);
	return root;
}

describe("sanitizeHtml", () => {
	it("strips a javascript: href but keeps the anchor text", () => {
		const root = parse('<p><a href="javascript:alert(1)">click</a></p>');
		const link = root.querySelector("a");
		expect(link?.hasAttribute("href")).toBe(false);
		expect(link?.textContent).toBe("click");
	});

	it("keeps http, https, and mailto hrefs", () => {
		for (const href of [
			"https://example.com/",
			"http://example.com/",
			"mailto:a@b.co",
		]) {
			expect(
				parse(`<a href="${href}">x</a>`).querySelector("a")?.getAttribute("href"),
			).toBe(href);
		}
	});

	it("drops a tel: href that DOMPurify would otherwise allow", () => {
		expect(
			parse('<a href="tel:123">x</a>').querySelector("a")?.hasAttribute("href"),
		).toBe(false);
	});

	it("removes script elements and inline event handlers", () => {
		const root = parse(
			'<p onclick="x()">hi</p><script>alert(1)</script><img src="/a.png" onerror="x()">',
		);
		expect(root.querySelector("script")).toBeNull();
		expect(root.querySelector("p")?.hasAttribute("onclick")).toBe(false);
		expect(root.querySelector("img")?.hasAttribute("onerror")).toBe(false);
	});

	it("keeps target on a link and forces a safe rel", () => {
		const link = parse(
			'<a href="https://example.com/" target="_blank" rel="opener">x</a>',
		).querySelector("a");
		expect(link?.getAttribute("target")).toBe("_blank");
		expect(link?.getAttribute("rel")).toBe("noopener noreferrer nofollow");
	});

	it("keeps a mention link's data-user-id and class", () => {
		const link = parse(
			'<a data-type="mention" data-user-id="7" class="mention" href="/user/7">@bob</a>',
		).querySelector("a");
		expect(link?.getAttribute("data-user-id")).toBe("7");
		expect(link?.getAttribute("href")).toBe("/user/7");
		expect(link?.className).toBe("mention");
	});

	it("keeps a YouTube embed iframe and its attributes", () => {
		const frame = parse(
			'<iframe src="https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ" allow="encrypted-media; picture-in-picture; fullscreen" allowfullscreen="" loading="lazy" title="t"></iframe>',
		).querySelector("iframe");
		expect(frame?.getAttribute("src")).toBe(
			"https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ",
		);
		expect(frame?.hasAttribute("allowfullscreen")).toBe(true);
		expect(frame?.getAttribute("allow")).toBe(
			"encrypted-media; picture-in-picture; fullscreen",
		);
	});

	it("removes an iframe from any other host or with a malformed id", () => {
		for (const src of [
			"https://evil.example/embed/dQw4w9WgXcQ",
			"https://www.youtube.com/embed/dQw4w9WgXcQ",
			"https://www.youtube-nocookie.com/embed/short",
			"javascript:alert(1)",
		]) {
			expect(
				parse(`<div><iframe src="${src}"></iframe></div>`).querySelector("iframe"),
			).toBeNull();
		}
	});

	it("drops an iframe allow attribute that is not the embed's own", () => {
		const frame = parse(
			'<iframe src="https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ" allow="camera"></iframe>',
		).querySelector("iframe");
		expect(frame).not.toBeNull();
		expect(frame?.hasAttribute("allow")).toBe(false);
	});

	it("keeps color, background-color, and text-align styles", () => {
		const root = parse(
			'<p style="text-align: center"><span style="color: #d62828">a</span><mark style="background-color: #ffeb3b; color: #000000">b</mark></p>',
		);
		expect(root.querySelector("p")?.style.textAlign).toBe("center");
		expect(root.querySelector("span")?.getAttribute("style")).toBe("color: #d62828");
		expect(root.querySelector("mark")?.getAttribute("style")).toBe(
			"background-color: #ffeb3b; color: #000000",
		);
	});

	it("drops style values containing url( or expression(, and unlisted properties", () => {
		const root = parse(
			'<p style="background-color: url(https://x/y.png)">a</p><p style="color: expression(alert(1))">b</p><p style="position: fixed; color: red">c</p><p style="text-align: evil">d</p><p style="color: rgb(1, 2, 3)">e</p>',
		);
		const [a, b, c, d, e] = root.querySelectorAll("p");
		expect(a?.hasAttribute("style")).toBe(false);
		expect(b?.hasAttribute("style")).toBe(false);
		expect(c?.getAttribute("style")).toBe("color: red");
		expect(d?.hasAttribute("style")).toBe(false);
		expect(e?.getAttribute("style")).toBe("color: rgb(1, 2, 3)");
	});

	it("cleans an img with a javascript: or data: src and keeps a relative or http(s) one", () => {
		const root = parse(
			'<img src="javascript:alert(1)"><img src="data:image/svg+xml;base64,PHN2Zz4="><img src="/images/a.png"><img src="https://example.com/a.png">',
		);
		const srcs = [...root.querySelectorAll("img")].map((img) =>
			img.getAttribute("src"),
		);
		expect(srcs).toEqual([null, null, "/images/a.png", "https://example.com/a.png"]);
	});

	it("returns an empty string when there is no window", () => {
		const real = globalThis.window;
		// @ts-expect-error simulating a server render
		delete globalThis.window;
		try {
			expect(sanitizeHtml("<p>hi</p>")).toBe("");
		} finally {
			globalThis.window = real;
		}
	});
});

describe("isAllowedLinkUri", () => {
	it("allows http, https, mailto, and scheme-less values", () => {
		for (const uri of [
			"https://a.b",
			"HTTP://a.b",
			"mailto:a@b.co",
			"/path",
			"#frag",
			"example.com",
		]) {
			expect(isAllowedLinkUri(uri)).toBe(true);
		}
	});

	it("refuses other schemes, including ones hidden by whitespace", () => {
		for (const uri of [
			"javascript:alert(1)",
			" java\tscript:alert(1)",
			"tel:123",
			"ftp://a.b",
			"data:text/html,x",
		]) {
			expect(isAllowedLinkUri(uri)).toBe(false);
		}
	});
});

describe("generateHTML round trip", () => {
	const text = (value: string): JSONContent => ({ type: "text", text: value });
	const para = (...content: JSONContent[]): JSONContent => ({
		type: "paragraph",
		content,
	});

	const doc: JSONContent = {
		type: "doc",
		content: [
			{ type: "heading", attrs: { level: 1 }, content: [text("Title")] },
			{
				type: "paragraph",
				attrs: { textAlign: "center" },
				content: [
					{
						type: "text",
						text: "colored",
						marks: [{ type: "textStyle", attrs: { color: "#d62828" } }],
					},
					{
						type: "text",
						text: "lit",
						marks: [{ type: "highlight", attrs: { color: "#ffeb3b" } }],
					},
					{
						type: "text",
						text: "link",
						marks: [{ type: "link", attrs: { href: "https://example.com/" } }],
					},
					{ type: "mention", attrs: { userId: 7 } },
				],
			},
			{ type: "note", attrs: { mode: "private" }, content: [para(text("secret"))] },
			{ type: "quote", attrs: { quotee: "Bob" }, content: [para(text("q"))] },
			{ type: "spoiler", attrs: { title: "Hidden" }, content: [para(text("s"))] },
			{ type: "youtube", attrs: { videoId: "dQw4w9WgXcQ" } },
			{ type: "poll" },
			{ type: "box", attrs: { variant: "paper" }, content: [para(text("b"))] },
			{
				type: "columns",
				attrs: { count: 2 },
				content: [
					{ type: "column", content: [para(text("c1"))] },
					{ type: "column", content: [para(text("c2"))] },
				],
			},
			{
				type: "table",
				content: [
					{
						type: "tableRow",
						content: [{ type: "tableCell", content: [para(text("t"))] }],
					},
				],
			},
			{ type: "npcSpeaker", attrs: { npcId: 3 }, content: [para(text("hi"))] },
			{ type: "npcRoster", attrs: { npcIds: [3] } },
			{
				type: "taskList",
				content: [
					{ type: "taskItem", attrs: { checked: true }, content: [para(text("do"))] },
				],
			},
			{
				type: "image",
				attrs: {
					src: "/images/a.png",
					alt: "a",
					float: "left",
					href: "https://example.com/big.png",
				},
			},
			{ type: "horizontalRule" },
		],
	};

	const html = sanitizeHtml(
		generateHTML(
			doc,
			extensionsFor(
				{ 3: { name: "Gob", image: { url: "/images/gob.png" } } },
				{ 7: "bob" },
				{},
				"alice",
			),
		),
	);
	const root = document.createElement("div");
	root.innerHTML = html;

	it.each([
		["banner heading", "h1.headerbar"],
		["colored span", 'span[style^="color: "]'],
		["text align", 'p[style="text-align: center"]'],
		["highlight", "mark[data-color='#ffeb3b']"],
		["link target", 'a[href="https://example.com/"][target="_blank"]'],
		["mention", 'a.mention[data-user-id="7"][href="/user/7"]'],
		["note", 'div[data-type="note"][data-mode="private"]'],
		["quote", 'blockquote.quote[data-type="quote"] .quote-node-content'],
		["spoiler", 'details[data-type="spoiler"] summary'],
		[
			"youtube",
			'div[data-type="youtube"] iframe[src^="https://www.youtube-nocookie.com/embed/"]',
		],
		["poll slot", 'div[data-type="poll"]'],
		["box", 'div[data-type="box"][data-variant="paper"]'],
		["columns", 'div[data-type="columns"] div[data-type="column"]'],
		["table", "div.tableWrapper table tbody tr td"],
		[
			"npc speaker",
			'div[data-type="npcSpeaker"][data-npc-id="3"] img[src="/images/gob.png"]',
		],
		["npc roster", 'div[data-type="npcRoster"] .npc-roster-grid img'],
		[
			"task item",
			'li[data-type="taskItem"][data-checked="true"] input[type="checkbox"]',
		],
		[
			"linked image",
			'a.image-link[target="_blank"] img[src="/images/a.png"][data-float="left"]',
		],
		["horizontal rule", 'div[data-type="horizontalRule"] hr'],
	])("keeps the %s", (_name, selector) => {
		expect(root.querySelector(selector), html).not.toBeNull();
	});
});
