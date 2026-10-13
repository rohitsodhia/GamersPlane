import clsx from "clsx";
import {
	type CSSProperties,
	type MouseEvent,
	type ReactNode,
	useEffect,
	useRef,
	useState,
	useSyncExternalStore,
} from "react";
import {
	Button,
	Dialog,
	DialogTrigger,
	Focusable,
	Popover,
	Tooltip,
	TooltipTrigger,
} from "react-aria-components";
import DieOutlineIcon from "#/components/DieOutlineIcon";
import { useRefResolver } from "./loop-context";
import {
	type AdvantageChoice,
	applyAdvantage,
	type BuildRollResult,
	buildRoll,
	isInteractiveTarget,
} from "./roll";
import { useOnRoll } from "./roll-context";
import { useSheetMode, useSheetSubscribe } from "./sheet-values";
import type { RollIconAnchor, RollSpec } from "./types";

const ANCHOR_PERCENT: Record<RollIconAnchor, string> = {
	start: "0%",
	middle: "50%",
	end: "100%",
};

/** What an element needs to become rollable; null in edit mode (no roll UI at all). */
export interface RollableState {
	/** Classes for the element's root (positioning context, dice cursor). */
	className: string;
	/** The icon-anchor custom properties for the element's root. */
	style: CSSProperties;
	/** Click handler for the element's root: forwards to the roll unless an interactive descendant was hit. */
	onClick: (e: MouseEvent<HTMLElement>) => void;
	/** The dice icon, to render inside the root. */
	icon: ReactNode;
}

/**
 * Wires a `roll` spec onto an element. In display mode it builds the roll
 * (reactively, so the dice follow the sheet's values) and returns the root
 * classes / click handler / icon; in edit mode it returns null so the element
 * renders exactly as it does without a `roll`. The click handler comes from
 * `RollContext`; without one the icon still shows the dice but isn't clickable.
 */
export function useRollable(
	roll: RollSpec,
	fallbackReason: string,
): RollableState | null {
	const mode = useSheetMode();
	const resolve = useRefResolver();
	const subscribe = useSheetSubscribe();
	const onRoll = useOnRoll();
	const [open, setOpen] = useState(false);

	// Serialised so the snapshot is a primitive and an unchanged roll doesn't re-render.
	const snapshot = useSyncExternalStore(subscribe, () =>
		mode === "display" ? JSON.stringify(buildRoll(roll, resolve, fallbackReason)) : "",
	);
	const built: BuildRollResult | null = snapshot ? JSON.parse(snapshot) : null;
	const error = built != null && "error" in built ? built.error : null;

	useEffect(() => {
		if (import.meta.env.DEV && error != null) {
			console.warn(`[sheet] roll "${fallbackReason}": ${error}`);
		}
	}, [error, fallbackReason]);

	if (built == null) return null;

	const clickable = error == null && onRoll != null;
	const fire = (choice: AdvantageChoice) => {
		if (error != null || onRoll == null) return;
		const ok = built as Exclude<BuildRollResult, { error: string }>;
		onRoll({
			dice: ok.advantage ? applyAdvantage(ok.dice, choice) : ok.dice,
			reason: ok.reason,
			mode: ok.mode,
		});
		setOpen(false);
	};

	const x = roll.icon?.x ?? "start";
	const y = roll.icon?.y ?? "middle";

	return {
		className: clsx(
			"char-sheet-rollable",
			clickable && "char-sheet-rollable--clickable",
		),
		style: {
			"--roll-x": ANCHOR_PERCENT[x],
			"--roll-y": ANCHOR_PERCENT[y],
		} as CSSProperties,
		onClick: (e) => {
			if (!clickable) return;
			if (isInteractiveTarget(e.target, e.currentTarget)) return;
			if (!("error" in built) && built.advantage) setOpen(true);
			else fire("normal");
		},
		icon: (
			<RollIcon
				built={built}
				clickable={clickable}
				fire={fire}
				open={open}
				setOpen={setOpen}
			/>
		),
	};
}

function describe(built: BuildRollResult): string {
	if ("error" in built) return `Can't roll: ${built.error}`;
	const advice = built.advantage ? " (advantage or disadvantage)" : "";
	return built.reason
		? `Roll ${built.reason}: ${built.dice}${advice}`
		: `Roll ${built.dice}${advice}`;
}

interface RollIconProps {
	built: BuildRollResult;
	clickable: boolean;
	fire: (choice: AdvantageChoice) => void;
	open: boolean;
	setOpen: (open: boolean) => void;
}

function RollIcon({ built, clickable, fire, open, setOpen }: RollIconProps) {
	const text = describe(built);
	const isError = "error" in built;
	const tooltip = (
		<Tooltip className="char-sheet-roll-tooltip" offset={6}>
			{text}
		</Tooltip>
	);

	// Not clickable (no host handler, or a broken roll): keep the icon and its
	// tooltip reachable, without pretending to be a control.
	if (!clickable) {
		return (
			<TooltipTrigger delay={200}>
				<Focusable>
					<span
						className={clsx(
							"char-sheet-roll-icon",
							isError && "char-sheet-roll-icon--error",
						)}
						role="img"
						aria-label={text}
					>
						<DieOutlineIcon />
					</span>
				</Focusable>
				{tooltip}
			</TooltipTrigger>
		);
	}

	if (!isError && built.advantage) {
		return <AdvantageRoll text={text} fire={fire} open={open} setOpen={setOpen} />;
	}

	return (
		<TooltipTrigger delay={200}>
			<Button
				className="char-sheet-roll-icon"
				aria-label={text}
				onPress={() => fire("normal")}
			>
				<DieOutlineIcon />
			</Button>
			{tooltip}
		</TooltipTrigger>
	);
}

const ADVANTAGE_CHOICES: { choice: AdvantageChoice; label: string }[] = [
	{ choice: "advantage", label: "Advantage" },
	{ choice: "normal", label: "Normal" },
	{ choice: "disadvantage", label: "Disadvantage" },
];

function AdvantageRoll({
	text,
	fire,
	open,
	setOpen,
}: {
	text: string;
	fire: (choice: AdvantageChoice) => void;
	open: boolean;
	setOpen: (open: boolean) => void;
}) {
	const triggerRef = useRef<HTMLButtonElement>(null);
	const popoverRef = useRef<HTMLElement>(null);

	// Non-modal so opening it doesn't lock page scrolling (see `ActionsMenu`),
	// which means an outside press has to close it by hand. The trigger is left to
	// DialogTrigger's own toggle so pressing it again doesn't close-then-reopen.
	useEffect(() => {
		if (!open) return;
		const closeOnOutsidePress = (e: PointerEvent) => {
			const target = e.target as Node;
			if (popoverRef.current?.contains(target)) return;
			if (triggerRef.current?.contains(target)) return;
			setOpen(false);
		};
		const closeOnEscape = (e: KeyboardEvent) => {
			if (e.key === "Escape") setOpen(false);
		};
		document.addEventListener("pointerdown", closeOnOutsidePress);
		document.addEventListener("keydown", closeOnEscape);
		return () => {
			document.removeEventListener("pointerdown", closeOnOutsidePress);
			document.removeEventListener("keydown", closeOnEscape);
		};
	}, [open, setOpen]);

	return (
		<DialogTrigger isOpen={open} onOpenChange={setOpen}>
			<TooltipTrigger delay={200} isDisabled={open}>
				<Button ref={triggerRef} className="char-sheet-roll-icon" aria-label={text}>
					<DieOutlineIcon />
				</Button>
				<Tooltip className="char-sheet-roll-tooltip" offset={6}>
					{text}
				</Tooltip>
			</TooltipTrigger>
			<Popover
				ref={popoverRef}
				className="char-sheet-roll-popover"
				placement="bottom"
				offset={6}
				isNonModal
			>
				<Dialog className="char-sheet-roll-choices" aria-label="Roll with advantage?">
					{ADVANTAGE_CHOICES.map(({ choice, label }) => (
						<Button
							key={choice}
							className="char-sheet-roll-choice"
							onPress={() => fire(choice)}
						>
							{label}
						</Button>
					))}
				</Dialog>
			</Popover>
		</DialogTrigger>
	);
}

interface RollableProps {
	roll: RollSpec;
	/** The element's own text, used when the roll has no `reason`. */
	fallbackReason: string;
	/** Author classes / styles; moved onto the wrapper in display mode so layout rules still hit the box the icon anchors to. */
	className?: string;
	style?: CSSProperties;
	/** The wrapped element is a `label`; it keeps its fixed label column in an inline group. */
	isLabel?: boolean;
	children: (props: { className?: string; style?: CSSProperties }) => ReactNode;
}

/**
 * Wraps a leaf element (`text`, `label`) so it can be rolled. In edit mode it
 * renders the element as-is. In display mode it adds a positioned wrapper that
 * takes over the author's `className` / `style` and holds the icon — the icon
 * can't live inside the element itself (a `label` may not contain a button).
 * `group` doesn't use this: it already has a root `div` and calls `useRollable`.
 */
export function Rollable({
	roll,
	fallbackReason,
	className,
	style,
	isLabel,
	children,
}: RollableProps) {
	const rollable = useRollable(roll, fallbackReason);
	if (rollable == null) return <>{children({ className, style })}</>;
	return (
		// biome-ignore lint/a11y/noStaticElementInteractions: the click is a pointer convenience over the icon button, which is the keyboard / assistive-tech route
		// biome-ignore lint/a11y/useKeyWithClickEvents: see above
		<span
			className={clsx(
				rollable.className,
				isLabel && "char-sheet-rollable--label",
				className,
			)}
			style={{ ...style, ...rollable.style }}
			onClick={rollable.onClick}
		>
			{children({})}
			{rollable.icon}
		</span>
	);
}
