export const PANEL_MIN_HEIGHT = 128;
/** The panel never takes more than this share of the viewport. */
export const PANEL_MAX_SHARE = 0.8;
/** The default height, as a share of the viewport. */
export const PANEL_DEFAULT_SHARE = 0.33;
export const PANEL_KEY_STEP = 24;
export const PANEL_STORAGE_KEY = "game-bar:sheet-panel-height";

export const maxPanelHeight = (viewportHeight: number) =>
	Math.max(PANEL_MIN_HEIGHT, Math.floor(viewportHeight * PANEL_MAX_SHARE));

/** Keeps a panel height (px) between the minimum and the viewport's share. */
export const clampPanelHeight = (height: number, viewportHeight: number) =>
	Math.min(
		maxPanelHeight(viewportHeight),
		Math.max(PANEL_MIN_HEIGHT, Math.round(height)),
	);

/** The height in px: the chosen one, or the default share of the viewport. */
export const resolvePanelHeight = (height: number | null, viewportHeight: number) =>
	clampPanelHeight(height ?? viewportHeight * PANEL_DEFAULT_SHARE, viewportHeight);

/**
 * The panel's CSS height. A chosen height is capped by the viewport share in CSS
 * too, so a window that shrinks afterwards can't leave the panel oversized.
 * Shared by the panel and the page-end spacer so the two always agree.
 */
export const panelHeightCss = (height: number | null) =>
	height === null
		? `${PANEL_DEFAULT_SHARE * 100}dvh`
		: `min(${height}px, ${PANEL_MAX_SHARE * 100}dvh)`;

/** The next height for a key press on the resize handle, or null for other keys. */
export function heightForKey(
	key: string,
	current: number,
	viewportHeight: number,
): number | null {
	switch (key) {
		case "ArrowUp":
			return clampPanelHeight(current + PANEL_KEY_STEP, viewportHeight);
		case "ArrowDown":
			return clampPanelHeight(current - PANEL_KEY_STEP, viewportHeight);
		case "Home":
			return PANEL_MIN_HEIGHT;
		case "End":
			return maxPanelHeight(viewportHeight);
		default:
			return null;
	}
}

/** The remembered height, or null when none is stored (or storage is unavailable). */
export function loadPanelHeight(): number | null {
	try {
		const stored = Number(localStorage.getItem(PANEL_STORAGE_KEY));
		return Number.isFinite(stored) && stored > 0 ? stored : null;
	} catch {
		return null;
	}
}

export function savePanelHeight(height: number) {
	try {
		localStorage.setItem(PANEL_STORAGE_KEY, String(height));
	} catch {
		// Storage unavailable: the height just isn't remembered.
	}
}
