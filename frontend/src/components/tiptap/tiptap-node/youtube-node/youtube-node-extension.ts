import { mergeAttributes, Node } from "@tiptap/core";
import { isYoutubeVideoId, parseYoutubeVideoId, youtubeEmbedUrl } from "./youtube";

export const YOUTUBE_NODE_NAME = "youtube";

declare module "@tiptap/core" {
	interface Commands<ReturnType> {
		youtube: {
			/**
			 * Insert a YouTube video from a pasted link. Returns false (and inserts
			 * nothing) when the text isn't a YouTube link.
			 */
			setYoutube: (options: { url: string }) => ReturnType;
		};
	}
}

// A YouTube embed: an atom block that stores only a validated video id. The iframe
// address is built from that id, so no user text ever reaches `src`. Parsing reads
// `data-video-id` and re-validates it (a node with a bad id is not created), and a
// stored document with a bad id renders an empty wrapper instead of an iframe. Plain
// `renderHTML`, no node view, so the editor and the read-only content match.
export const Youtube = Node.create({
	name: YOUTUBE_NODE_NAME,
	group: "block",
	atom: true,
	selectable: true,
	draggable: true,

	addAttributes() {
		return {
			videoId: {
				default: "",
				parseHTML: (element: HTMLElement) => {
					const id = element.getAttribute("data-video-id");
					return isYoutubeVideoId(id) ? id : "";
				},
				renderHTML: () => ({}),
			},
		};
	},

	parseHTML() {
		return [
			{
				tag: `div[data-type="${YOUTUBE_NODE_NAME}"]`,
				getAttrs: (element) =>
					isYoutubeVideoId((element as HTMLElement).getAttribute("data-video-id"))
						? null
						: false,
			},
		];
	},

	renderHTML({ node, HTMLAttributes }) {
		const videoId: unknown = node.attrs["videoId"];
		if (!isYoutubeVideoId(videoId)) {
			return [
				"div",
				mergeAttributes(HTMLAttributes, { "data-type": YOUTUBE_NODE_NAME }),
			];
		}
		return [
			"div",
			mergeAttributes(HTMLAttributes, {
				"data-type": YOUTUBE_NODE_NAME,
				"data-video-id": videoId,
				class: "youtube-embed",
			}),
			[
				"iframe",
				{
					src: youtubeEmbedUrl(videoId),
					title: "YouTube video player",
					loading: "lazy",
					referrerpolicy: "strict-origin-when-cross-origin",
					allow: "encrypted-media; picture-in-picture; fullscreen",
					allowfullscreen: "",
				},
			],
		];
	},

	addCommands() {
		return {
			setYoutube:
				({ url }) =>
				({ commands }) => {
					const videoId = parseYoutubeVideoId(url);
					if (!videoId) return false;
					return commands.insertContent({
						type: this.name,
						attrs: { videoId },
					});
				},
		};
	},
});

export default Youtube;
