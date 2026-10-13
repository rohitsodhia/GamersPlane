import { createContext, useContext } from "react";
import type { RollRequest } from "./roll";

/**
 * Receives a roll the user activated on a sheet (the post composer prefills it;
 * nothing rolls automatically). Undefined when the host doesn't take rolls — the
 * dice icon then only shows what would be rolled.
 */
export type OnRoll = (roll: RollRequest) => void;

export const RollContext = createContext<OnRoll | undefined>(undefined);

export function useOnRoll(): OnRoll | undefined {
	return useContext(RollContext);
}
