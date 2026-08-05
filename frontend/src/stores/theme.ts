// store/auth.ts
import { create } from "zustand";
import { persist } from "zustand/middleware";

type ThemeMode = "light" | "dark" | "auto";
type ResolvedTheme = "light" | "dark";
type ThemeStore = {
	mode: ThemeMode;
	theme: ResolvedTheme;
	setMode: (mode: ThemeMode) => void;
	setTheme: (theme: ResolvedTheme) => void;
};

export const useThemeStore = create<ThemeStore>()(
	persist(
		(set) => ({
			mode: "auto",
			theme: "light",
			setMode: (mode) => set({ mode }),
			setTheme: (theme) => set({ theme }),
		}),
		{ name: "theme" },
	),
);
