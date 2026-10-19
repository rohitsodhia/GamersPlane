import type { CSSProperties } from "react";
import type { GameBackgroundSettings } from "#/queries/game";

export const DEFAULT_BACKGROUND_SETTINGS: GameBackgroundSettings = {
	position: "top",
	size: "width",
	fixed: true,
	color: null,
};

export const BACKGROUND_MAX_BYTES = 10 * 1024 * 1024;
export const BACKGROUND_TYPES = ["image/jpeg", "image/png", "image/webp"];

/** An error message for a file that can't be a background, or null if it's fine. */
export function backgroundFileError(file: {
	type: string;
	size: number;
}): string | null {
	if (!BACKGROUND_TYPES.includes(file.type)) {
		return "The background must be a JPEG, PNG or WEBP image.";
	}
	if (file.size > BACKGROUND_MAX_BYTES) {
		return "The background image must be 10MB or smaller.";
	}
	return null;
}

export function backgroundStyle(
	settings: GameBackgroundSettings,
	url: string,
): CSSProperties {
	return {
		backgroundColor: settings.color ?? undefined,
		backgroundImage: `url(${JSON.stringify(url)})`,
		backgroundPosition: settings.position,
		backgroundSize: settings.size === "width" ? "100% auto" : settings.size,
		backgroundRepeat: "no-repeat",
		backgroundAttachment: settings.fixed ? "fixed" : "scroll",
	};
}
