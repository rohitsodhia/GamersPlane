// A YouTube video id is exactly 11 characters of this alphabet. Everything the
// embed knows about a video is this id: the document stores it and nothing else, and
// the iframe address is built from it, never from text a user typed.
const VIDEO_ID_PATTERN = /^[A-Za-z0-9_-]{11}$/;

export function isYoutubeVideoId(value: unknown): value is string {
	return typeof value === "string" && VIDEO_ID_PATTERN.test(value);
}

const SHORT_HOSTS: ReadonlySet<string> = new Set(["youtu.be", "www.youtu.be"]);
const LONG_HOSTS: ReadonlySet<string> = new Set([
	"youtube.com",
	"www.youtube.com",
	"m.youtube.com",
	"music.youtube.com",
	"youtube-nocookie.com",
	"www.youtube-nocookie.com",
]);
// Paths of the form /<prefix>/<id> on the long hosts.
const ID_PATH_PREFIXES: ReadonlySet<string> = new Set(["embed", "shorts", "live", "v"]);

/**
 * The video id in a pasted YouTube link (`youtu.be/ID`, `youtube.com/watch?v=ID`,
 * `/embed/ID`, `/shorts/ID`, `/live/ID`), or null when the text isn't one. Only the
 * host's exact name is trusted, and the id must pass the 11-character check, so
 * anything else in the link (other query parameters, a start time, a fragment) is
 * dropped. Text without an http(s) scheme gets `https://` put in front, so another
 * scheme (`javascript:`, `data:`, `ftp:`) ends up as an invalid host and is rejected.
 */
export function parseYoutubeVideoId(input: string): string | null {
	const text = input.trim();
	if (!text) return null;
	let url: URL;
	try {
		url = new URL(/^https?:\/\//i.test(text) ? text : `https://${text}`);
	} catch {
		return null;
	}
	const host = url.hostname.toLowerCase();
	const segments = url.pathname.split("/").filter(Boolean);

	let candidate: string | null | undefined = null;
	if (SHORT_HOSTS.has(host)) {
		candidate = segments[0];
	} else if (LONG_HOSTS.has(host)) {
		if (segments[0] === "watch") {
			candidate = url.searchParams.get("v");
		} else if (segments[0] !== undefined && ID_PATH_PREFIXES.has(segments[0])) {
			candidate = segments[1];
		}
	}
	return isYoutubeVideoId(candidate) ? candidate : null;
}

/** The privacy-enhanced embed address for a validated id. */
export function youtubeEmbedUrl(videoId: string): string {
	return `https://www.youtube-nocookie.com/embed/${videoId}`;
}
