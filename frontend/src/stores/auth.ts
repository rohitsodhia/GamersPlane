// store/auth.ts
import { create } from "zustand";
import { persist } from "zustand/middleware";

type AuthStore = {
	token: string | null;
	setToken: (token: string | null) => void;
};

export const useAuthStore = create<AuthStore>()(
	persist(
		(set) => ({
			token: null,
			setToken: (token) => set({ token }),
		}),
		{ name: "token" },
	),
);
