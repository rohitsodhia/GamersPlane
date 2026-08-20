import { ApiError, apiFetch } from "#/lib/api";

export type BasicDiceTerm = {
	count: number;
	sides: number;
	sign: number;
	keep_high: boolean | null;
	keep_count: number | null;
	rolls: (number | number[])[];
	dropped: number[];
	subtotal: number;
};

export type BasicRollGroup = {
	expression: string;
	terms: BasicDiceTerm[];
	modifier: number;
	total: number;
};

export type BasicRollResult = {
	groups: BasicRollGroup[];
	total: number;
};

export type FateRollResult = {
	rolls: number[];
	modifier: number;
	positive: number;
	blank: number;
	negative: number;
	total: number;
};

export type FengShuiRollType = "standard" | "fortune" | "closed";

export type FengShuiRollResult = {
	type: FengShuiRollType;
	action_value: number;
	positive: number[];
	negative: number[];
	extra: number | null;
	total: number;
};

export type StarWarsFFGDieType =
	| "ability"
	| "proficiency"
	| "boost"
	| "difficulty"
	| "challenge"
	| "setback"
	| "force";

export type StarWarsFFGIcon =
	| "success"
	| "advantage"
	| "triumph"
	| "failure"
	| "threat"
	| "despair"
	| "whiteDot"
	| "blackDot";

export type StarWarsFFGRollTerm = {
	die: StarWarsFFGDieType;
	result: string;
};

export type StarWarsFFGRollResult = {
	rolls: StarWarsFFGRollTerm[];
	totals: Record<StarWarsFFGIcon, number>;
	net_success: number;
	net_advantage: number;
};

export type DiceSystem = "basic" | "fate" | "fengshui" | "starwarsffg";

export type RollDiceParams =
	| { system: "basic"; roll: string; rerollAces?: boolean }
	| { system: "fate"; roll: string; modifier?: number }
	| { system: "fengshui"; roll: string; rollType?: FengShuiRollType }
	| { system: "starwarsffg"; roll: string };

export type RollDiceResult =
	| BasicRollResult
	| FateRollResult
	| FengShuiRollResult
	| StarWarsFFGRollResult;

export async function rollDice(params: RollDiceParams): Promise<RollDiceResult> {
	const search = new URLSearchParams({ system: params.system, roll: params.roll });
	if (params.system === "basic" && params.rerollAces) {
		search.set("reroll_aces", "true");
	}
	if (params.system === "fate" && params.modifier) {
		search.set("modifier", String(params.modifier));
	}
	if (params.system === "fengshui" && params.rollType) {
		search.set("roll_type", params.rollType);
	}

	const res = await apiFetch(`/tools/dice?${search.toString()}`);
	if (!res.ok) {
		const { errors } = await res.json();
		throw new ApiError(res.status, errors);
	}
	return res.json();
}
