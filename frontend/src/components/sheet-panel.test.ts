import { afterEach, describe, expect, it, vi } from "vitest";
import {
	clampPanelHeight,
	heightForKey,
	loadPanelHeight,
	PANEL_MIN_HEIGHT,
	panelHeightCss,
	resolvePanelHeight,
	savePanelHeight,
} from "./sheet-panel";

afterEach(() => {
	vi.restoreAllMocks();
	localStorage.clear();
});

describe("clampPanelHeight", () => {
	it("keeps a height inside the minimum and the viewport share", () => {
		expect(clampPanelHeight(10, 1000)).toBe(PANEL_MIN_HEIGHT);
		expect(clampPanelHeight(400, 1000)).toBe(400);
		expect(clampPanelHeight(990, 1000)).toBe(800);
	});

	it("never goes below the minimum even in a tiny viewport", () => {
		expect(clampPanelHeight(500, 100)).toBe(PANEL_MIN_HEIGHT);
	});
});

describe("resolvePanelHeight", () => {
	it("defaults to a third of the viewport, and clamps a chosen height", () => {
		expect(resolvePanelHeight(null, 900)).toBe(297);
		expect(resolvePanelHeight(2000, 900)).toBe(720);
	});
});

describe("panelHeightCss", () => {
	it("uses dvh by default and caps a chosen height by the viewport", () => {
		expect(panelHeightCss(null)).toBe("33dvh");
		expect(panelHeightCss(400)).toBe("min(400px, 80dvh)");
	});
});

describe("heightForKey", () => {
	it("steps with the arrows, jumps with Home/End, ignores other keys", () => {
		expect(heightForKey("ArrowUp", 300, 1000)).toBe(324);
		expect(heightForKey("ArrowDown", 300, 1000)).toBe(276);
		expect(heightForKey("Home", 300, 1000)).toBe(PANEL_MIN_HEIGHT);
		expect(heightForKey("End", 300, 1000)).toBe(800);
		expect(heightForKey("a", 300, 1000)).toBeNull();
	});

	it("stops at the limits", () => {
		expect(heightForKey("ArrowDown", PANEL_MIN_HEIGHT, 1000)).toBe(PANEL_MIN_HEIGHT);
		expect(heightForKey("ArrowUp", 800, 1000)).toBe(800);
	});
});

describe("saved height", () => {
	it("round-trips, and is null when nothing (or junk) is stored", () => {
		expect(loadPanelHeight()).toBeNull();
		savePanelHeight(420);
		expect(loadPanelHeight()).toBe(420);
		localStorage.setItem("game-bar:sheet-panel-height", "wide");
		expect(loadPanelHeight()).toBeNull();
	});

	it("survives unavailable storage", () => {
		vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
			throw new Error("blocked");
		});
		vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
			throw new Error("blocked");
		});

		expect(loadPanelHeight()).toBeNull();
		expect(() => savePanelHeight(300)).not.toThrow();
	});
});
