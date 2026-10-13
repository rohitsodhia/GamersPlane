import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useEffect, useRef } from "react";
import { Button } from "react-aria-components";
import { useLiveSave } from "#/lib/use-live-save";
import { characterQueryOptions } from "#/queries/character";
import { meQueryOptions } from "#/queries/me";
import { SheetRenderer } from "#/routes/characters/sheets/-components/SheetRenderer";
import { SheetValuesProvider } from "#/routes/characters/sheets/-components/sheet-values";
import { useAuthStore } from "#/stores/auth";
import { selectPanelCharacterId, useGameBarStore } from "#/stores/game-bar";
import { selectActiveRollTarget, useRollTargetStore } from "#/stores/roll-target";
import { characterDisplayName, ownerLabelHint } from "./game-bar";
import LoadingSpinner from "./LoadingSpinner";
import styles from "./SheetPanel.module.css";
import {
	clampPanelHeight,
	heightForKey,
	loadPanelHeight,
	maxPanelHeight,
	PANEL_MIN_HEIGHT,
	panelHeightCss,
	resolvePanelHeight,
	savePanelHeight,
} from "./sheet-panel";

const viewportHeight = () => (typeof window === "undefined" ? 800 : window.innerHeight);

// A character's sheet docked above the game bar. Non-modal: no focus trap, scroll
// lock or backdrop, so the page (and a post being written) stays usable behind it.
export default function SheetPanel({
	gameId,
	fallbackLabel,
}: {
	gameId: number;
	/** Shown in the header until the character itself has loaded. */
	fallbackLabel?: string;
}) {
	const characterId = useGameBarStore(selectPanelCharacterId(gameId));
	if (characterId === null) return null;
	return <SheetPanelContent characterId={characterId} fallbackLabel={fallbackLabel} />;
}

function SheetPanelContent({
	characterId,
	fallbackLabel,
}: {
	characterId: number;
	fallbackLabel?: string;
}) {
	const closePanel = useGameBarStore((state) => state.closePanel);
	const panelHeight = useGameBarStore((state) => state.panelHeight);
	const setPanelHeight = useGameBarStore((state) => state.setPanelHeight);
	const { data: character, isError } = useQuery(characterQueryOptions(characterId));
	const onLiveSave = useLiveSave(characterId);
	const token = useAuthStore((state) => state.token);
	const { data: me } = useQuery({ ...meQueryOptions, enabled: !!token });
	// Rollables take clicks only while a post composer is on the page to receive them.
	const rollTarget = useRollTargetStore(selectActiveRollTarget);

	// Pick up the remembered height. Done after mount so the first render matches the
	// default and a missing or blocked storage changes nothing.
	useEffect(() => {
		if (useGameBarStore.getState().panelHeight !== null) return;
		const stored = loadPanelHeight();
		if (stored !== null) setPanelHeight(stored);
	}, [setPanelHeight]);

	const label = character
		? characterDisplayName(character)
		: (fallbackLabel ?? "Character");
	// The private label is only the owner's to see.
	const ownerLabel = character
		? ownerLabelHint(character, !!me && me.id === character.user_id)
		: null;

	return (
		<section
			className={styles["panel"]}
			style={{ height: panelHeightCss(panelHeight) }}
			aria-label={`${label} sheet`}
		>
			<ResizeHandle />
			<header className={styles["header"]}>
				<div className={styles["header-content"]}>
					<h2 className={styles["title"]} title={label}>
						{label}
					</h2>
					{ownerLabel && <span className={styles["name"]}>{ownerLabel}</span>}
					<Link
						to="/characters/$characterId"
						params={{ characterId }}
						className={styles["full-page"]}
					>
						Open full page
					</Link>
					<Button className={styles["close"]} aria-label="Close" onPress={closePanel}>
						<span aria-hidden="true">&times;</span>
					</Button>
				</div>
			</header>
			<div className={styles["body"]}>
				<div className={styles["body-content"]}>
					{isError ? (
						<p role="alert" className={styles["error"]}>
							Couldn't load this character's sheet.
						</p>
					) : !character ? (
						<LoadingSpinner />
					) : (
						<SheetValuesProvider
							key={characterId}
							mode="display"
							initialValues={character.values ?? {}}
							onLiveSave={onLiveSave}
							canEditLive={character.can_edit_live}
						>
							<SheetRenderer
								schema={character.layout}
								onRoll={
									rollTarget && !rollTarget.blockedReason
										? rollTarget.addRoll
										: undefined
								}
								rollBlockedReason={rollTarget?.blockedReason ?? undefined}
							/>
						</SheetValuesProvider>
					)}
				</div>
			</div>
		</section>
	);
}

function ResizeHandle() {
	const panelHeight = useGameBarStore((state) => state.panelHeight);
	const setPanelHeight = useGameBarStore((state) => state.setPanelHeight);
	const drag = useRef<{
		startY: number;
		startHeight: number;
		moved: boolean;
	} | null>(null);

	const current = resolvePanelHeight(panelHeight, viewportHeight());

	return (
		// biome-ignore lint/a11y/useSemanticElements: a window splitter is a focusable separator; <hr> can't take focus or values.
		<div
			role="separator"
			aria-orientation="horizontal"
			aria-label="Resize character sheet"
			aria-valuenow={current}
			aria-valuemin={PANEL_MIN_HEIGHT}
			aria-valuemax={maxPanelHeight(viewportHeight())}
			tabIndex={0}
			className={styles["handle"]}
			onPointerDown={(e) => {
				e.currentTarget.setPointerCapture(e.pointerId);
				drag.current = { startY: e.clientY, startHeight: current, moved: false };
			}}
			onPointerMove={(e) => {
				if (!drag.current) return;
				const { startY, startHeight } = drag.current;
				drag.current.moved = true;
				setPanelHeight(
					clampPanelHeight(startHeight + startY - e.clientY, viewportHeight()),
				);
			}}
			onPointerUp={(e) => {
				if (!drag.current) return;
				const { moved } = drag.current;
				drag.current = null;
				e.currentTarget.releasePointerCapture(e.pointerId);
				const chosen = useGameBarStore.getState().panelHeight;
				if (moved && chosen !== null) savePanelHeight(chosen);
			}}
			onPointerCancel={() => {
				drag.current = null;
			}}
			onKeyDown={(e) => {
				const next = heightForKey(e.key, current, viewportHeight());
				if (next === null) return;
				e.preventDefault();
				setPanelHeight(next);
				savePanelHeight(next);
			}}
		/>
	);
}
