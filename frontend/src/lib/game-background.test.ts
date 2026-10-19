import { describe, expect, it } from "vitest";
import {
	BACKGROUND_MAX_BYTES,
	backgroundFileError,
	backgroundStyle,
	DEFAULT_BACKGROUND_SETTINGS,
} from "./game-background";

describe("backgroundFileError", () => {
	it("accepts an allowed type at the size limit", () => {
		expect(
			backgroundFileError({ type: "image/webp", size: BACKGROUND_MAX_BYTES }),
		).toBeNull();
	});

	it("rejects other types", () => {
		expect(backgroundFileError({ type: "image/gif", size: 10 })).toMatch(
			/JPEG, PNG or WEBP/,
		);
	});

	it("rejects files over the limit", () => {
		expect(
			backgroundFileError({ type: "image/png", size: BACKGROUND_MAX_BYTES + 1 }),
		).toMatch(/10MB/);
	});
});

describe("backgroundStyle", () => {
	it("maps settings to css, quoting the url", () => {
		expect(
			backgroundStyle(
				{ position: "top left", size: "contain", fixed: true },
				'https://x.test/a"b.png',
			),
		).toEqual({
			backgroundImage: 'url("https://x.test/a\\"b.png")',
			backgroundPosition: "top left",
			backgroundSize: "contain",
			backgroundRepeat: "no-repeat",
			backgroundAttachment: "fixed",
		});
	});

	it("fits the width at the image's own proportions for the width size", () => {
		expect(
			backgroundStyle({ ...DEFAULT_BACKGROUND_SETTINGS, size: "width" }, "/a.png"),
		).toMatchObject({ backgroundSize: "100% auto" });
	});

	it("scrolls with the page when not fixed", () => {
		expect(
			backgroundStyle({ ...DEFAULT_BACKGROUND_SETTINGS, fixed: false }, "/a.png"),
		).toMatchObject({ backgroundAttachment: "scroll" });
	});
});
