import { create } from "zustand";

type LayoutStore = {
	noGap: boolean;
	setNoGap: (noGap: boolean) => void;
};

export const useLayoutStore = create<LayoutStore>()((set) => ({
	noGap: false,
	setNoGap: (noGap) => set({ noGap }),
}));
