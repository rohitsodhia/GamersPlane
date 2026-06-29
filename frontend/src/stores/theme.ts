// store/auth.ts
import { create } from "zustand";
import { persist } from "zustand/middleware";

type ThemeMode = "light" | "dark" | "auto";
type ThemeStore = {
	theme: ThemeMode;
	setTheme: (token: ThemeMode) => void;
};

export const useThemeStore = create<ThemeStore>()(
	persist(
		(set) => ({
			theme: "auto",
			setTheme: (theme) => set({ theme }),
		}),
		{ name: "theme" },
	),
);
