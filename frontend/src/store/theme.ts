// store/auth.ts
import { create } from "zustand";
import { persist } from "zustand/middleware";

type ThemeMode = "light" | "dark" | "auto";
type ThemeStore = {
	theme: ThemeMode;
	setToken: (token: ThemeMode) => void;
};

export const useThemeStore = create<ThemeStore>()(
	persist(
		(set) => ({
			theme: "auto",
			setToken: (theme) => set({ theme }),
		}),
		{ name: "theme" },
	),
);
