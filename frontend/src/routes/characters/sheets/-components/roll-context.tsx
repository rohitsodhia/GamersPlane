import { createContext, useContext } from "react";
import type { RollRequest } from "./roll";

/**
 * Receives a roll the user activated on a sheet (the post composer prefills it;
 * nothing rolls automatically). Undefined when the host doesn't take rolls — the
 * dice icon then only shows what would be rolled. A returned string is a message
 * for why the roll wasn't taken; the sheet shows it next to the icon.
 */
// biome-ignore lint/suspicious/noConfusingVoidType: hosts that never refuse a roll return nothing
export type OnRoll = (roll: RollRequest) => string | void;

export const RollContext = createContext<OnRoll | undefined>(undefined);

/**
 * Why the host can't take rolls right now (rolls off in the thread, no
 * permission), shown in the dice icon's tooltip. Undefined when there's no reason.
 */
export const RollBlockedContext = createContext<string | undefined>(undefined);

export function useOnRoll(): OnRoll | undefined {
	return useContext(RollContext);
}

export function useRollBlockedReason(): string | undefined {
	return useContext(RollBlockedContext);
}
