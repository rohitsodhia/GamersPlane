import { Editor, generateHTML, generateJSON, type JSONContent } from "@tiptap/core";
import { StarterKit } from "@tiptap/starter-kit";
import { describe, expect, it } from "vitest";
import { parseYoutubeVideoId, youtubeEmbedUrl } from "./youtube";
import { Youtube } from "./youtube-node-extension";

const ID = "dQw4w9WgXcQ";
const extensions = [StarterKit, Youtube];

const doc = (attrs: object): JSONContent => ({
	type: "doc",
	content: [{ type: "youtube", attrs }],
});

describe("parseYoutubeVideoId", () => {
	it.each([
		`https://youtu.be/${ID}?t=42`,
		`https://youtube.com/watch?feature=share&v=${ID}&x="><script>alert(1)</script>`,
		`https://www.youtube-nocookie.com/embed/${ID}`,
		`https://www.youtube.com/shorts/${ID}`,
		`https://www.youtube.com/live/${ID}`,
		`https://music.youtube.com/watch?v=${ID}`,
		`  www.youtube.com/watch?v=${ID}  `,
	])("reads the id out of %s", (input) => {
		expect(parseYoutubeVideoId(input)).toBe(ID);
	});

	it.each([
		"   ",
		"not a url",
		ID,
		`javascript:alert(1)//youtube.com/watch?v=${ID}`,
		`ftp://youtu.be/${ID}`,
		`https://youtu.be.evil.com/${ID}`,
		`https://youtube.com@evil.com/watch?v=${ID}`,
		`https://www.youtube.com/watch?v=${ID}x`,
		`https://www.youtube.com/watch?v=dQw4w9WgXc"onload="alert(1)`,
		`https://www.youtube.com/channel/${ID}`,
		`https://www.youtube.com/watch`,
		`https://youtu.be/`,
	])("rejects %s", (input) => {
		expect(parseYoutubeVideoId(input)).toBeNull();
	});
});

describe("youtube node", () => {
	it("renders a lazy no-cookie iframe built from the id, and round-trips", () => {
		const html = generateHTML(doc({ videoId: ID }), extensions);
		expect(youtubeEmbedUrl(ID)).toBe(`https://www.youtube-nocookie.com/embed/${ID}`);
		expect(html).toContain(`src="${youtubeEmbedUrl(ID)}"`);
		expect(html).toContain('loading="lazy"');
		expect(html).toContain('referrerpolicy="strict-origin-when-cross-origin"');
		expect(html).toContain("allowfullscreen");
		expect(html).toContain('title="YouTube video player"');
		expect(html).toContain(`data-video-id="${ID}"`);
		expect(html).not.toContain("style=");
		expect(generateJSON(html, extensions).content?.[0]).toEqual({
			type: "youtube",
			attrs: { videoId: ID },
		});
	});

	it.each([
		{ videoId: `${ID}"><script>alert(1)</script>` },
		{ videoId: { raw: 1 } },
	])("renders no iframe for a stored invalid id (%j)", (attrs) => {
		const html = generateHTML(doc(attrs), extensions);
		expect(html).not.toContain("iframe");
		expect(html).not.toContain("script");
		expect(html).not.toContain("src=");
	});

	it("does not create the node from pasted HTML with a bad or missing data-video-id", () => {
		for (const html of [
			'<div data-type="youtube" data-video-id="javascript:alert(1)"></div>',
			'<div data-type="youtube"></div>',
		]) {
			const parsed = generateJSON(html, extensions);
			expect(parsed.content?.some((n: JSONContent) => n.type === "youtube")).toBe(
				false,
			);
		}
	});
});

describe("setYoutube", () => {
	const makeEditor = () => new Editor({ extensions, content: "<p>hi</p>" });

	it("inserts the video for a valid link", () => {
		const editor = makeEditor();
		expect(editor.commands.setYoutube({ url: `https://youtu.be/${ID}` })).toBe(true);
		const videos = editor.getJSON().content?.filter((n) => n.type === "youtube");
		expect(videos).toEqual([{ type: "youtube", attrs: { videoId: ID } }]);
		editor.destroy();
	});

	it("inserts nothing and reports failure for anything else", () => {
		const editor = makeEditor();
		expect(editor.commands.setYoutube({ url: `https://evil.com/watch?v=${ID}` })).toBe(
			false,
		);
		expect(editor.getJSON().content?.map((n) => n.type)).toEqual(["paragraph"]);
		editor.destroy();
	});
});
