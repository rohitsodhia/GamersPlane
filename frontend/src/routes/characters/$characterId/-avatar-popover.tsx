import { useMutation, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { useRef, useState } from "react";
import { ApiError } from "#/lib/api";
import { useHbMargined } from "#/lib/use-hb-margined";
import {
	addCharacterAvatar,
	type CharacterAvatar,
	characterQueryOptions,
	deleteCharacterAvatar,
	setPrimaryCharacterAvatar,
} from "#/queries/character";
import styles from "./-avatar-popover.module.css";

// Keep in sync with AVATAR_MAX_COUNT in api/src/app/characters/routes.py
const AVATAR_MAX_COUNT = 5;

type AvatarPopoverProps = {
	id: string;
	characterId: number;
	avatars: CharacterAvatar[];
};

function AvatarPopover({ id, characterId, avatars }: AvatarPopoverProps) {
	const popoverRef = useRef<HTMLDivElement>(null);
	const fileInputRef = useRef<HTMLInputElement>(null);
	const queryClient = useQueryClient();

	const [file, setFile] = useState<File | undefined>(undefined);
	const [selectedId, setSelectedId] = useState<number | null>(null);
	const [error, setError] = useState<string | null>(null);

	const atMax = avatars.length >= AVATAR_MAX_COUNT;
	const selectedAvatar = avatars.find((avatar) => avatar.id === selectedId) ?? null;

	// Popovers don't unmount between opens, so a stale selection/error/file
	// from a previous open would otherwise leak into the next one.
	const resetState = () => {
		setFile(undefined);
		setSelectedId(null);
		setError(null);
		if (fileInputRef.current) fileInputRef.current.value = "";
	};

	const setAvatars = (updater: (avatars: CharacterAvatar[]) => CharacterAvatar[]) => {
		queryClient.setQueryData(
			characterQueryOptions(characterId).queryKey,
			(character) =>
				character ? { ...character, avatars: updater(character.avatars) } : character,
		);
	};

	const uploadMutation = useMutation({
		mutationFn: (file: File) => addCharacterAvatar(characterId, file),
		onSuccess: ({ avatar }) => {
			setAvatars((avatars) => [...avatars, avatar]);
			setFile(undefined);
			setError(null);
			if (fileInputRef.current) fileInputRef.current.value = "";
		},
		onError: (err: unknown) => {
			if (err instanceof ApiError && err.errors[0]?.detail) {
				setError(err.errors[0].detail);
			} else {
				setError("Failed to upload avatar");
			}
		},
	});

	const deleteMutation = useMutation({
		mutationFn: (avatarId: number) => deleteCharacterAvatar(characterId, avatarId),
		onSuccess: (_, avatarId) => {
			setAvatars((avatars) => avatars.filter((avatar) => avatar.id !== avatarId));
			setSelectedId((current) => (current === avatarId ? null : current));
			setError(null);
		},
		onError: (err: unknown) => {
			if (err instanceof ApiError && err.errors[0]?.detail) {
				setError(err.errors[0].detail);
			} else {
				setError("Failed to delete avatar");
			}
		},
	});

	const primaryMutation = useMutation({
		mutationFn: (avatarId: number) => setPrimaryCharacterAvatar(characterId, avatarId),
		onSuccess: ({ avatar }) => {
			setAvatars((avatars) =>
				avatars.map((existing) => ({
					...existing,
					is_primary: existing.id === avatar.id,
				})),
			);
			setError(null);
		},
		onError: (err: unknown) => {
			if (err instanceof ApiError && err.errors[0]?.detail) {
				setError(err.errors[0].detail);
			} else {
				setError("Failed to set primary avatar");
			}
		},
	});

	const hbMargin = useHbMargined<HTMLHeadingElement>();

	return (
		<div
			id={id}
			ref={popoverRef}
			popover="auto"
			className={styles["avatar-popover"]}
			onToggle={(e) => {
				if (e.newState === "open") resetState();
			}}
		>
			<h2 className={clsx("headerbar", styles.title)} ref={hbMargin.ref}>
				Manage Avatars
			</h2>
			<div style={{ marginInline: hbMargin.margin }}>
				<div className={styles.field}>
					<div className={styles["field-header"]}>
						<span>Upload Avatar</span>
						{atMax && (
							<span className={styles.notice}>
								Maximum of {AVATAR_MAX_COUNT} avatars reached.
							</span>
						)}
					</div>
					<div className={styles["upload-row"]}>
						<input
							ref={fileInputRef}
							type="file"
							accept="image/*"
							onChange={(e) => setFile(e.target.files?.[0])}
							disabled={atMax || uploadMutation.isPending}
						/>
						<button
							type="button"
							className="skew-btn"
							onClick={() => file && uploadMutation.mutate(file)}
							disabled={!file || atMax || uploadMutation.isPending}
						>
							Upload
						</button>
					</div>
				</div>

				<ul className={styles["avatar-list"]}>
					{avatars.map((avatar) => (
						<li key={avatar.id}>
							<button
								type="button"
								className={clsx(
									styles.thumb,
									avatar.is_primary && styles.primary,
									selectedId === avatar.id && styles.selected,
								)}
								onClick={() =>
									setSelectedId((current) => (current === avatar.id ? null : avatar.id))
								}
							>
								<img src={avatar.url} alt="Character avatar" />
							</button>
						</li>
					))}
					{avatars.length === 0 && (
						<li className={styles.notice}>No avatars uploaded yet.</li>
					)}
				</ul>

				{selectedAvatar && (
					<div className={styles.actions}>
						<button
							type="button"
							className="skew-btn"
							onClick={() => primaryMutation.mutate(selectedAvatar.id)}
							disabled={selectedAvatar.is_primary || primaryMutation.isPending}
						>
							Make Primary
						</button>
						<button
							type="button"
							className="skew-btn"
							onClick={() => deleteMutation.mutate(selectedAvatar.id)}
							disabled={deleteMutation.isPending}
						>
							Delete
						</button>
					</div>
				)}

				{error && <div className="error">{error}</div>}

				<div className="align-center">
					<button
						type="button"
						className="skew-btn"
						onClick={() => popoverRef.current?.hidePopover()}
					>
						Close
					</button>
				</div>
			</div>
		</div>
	);
}

export default AvatarPopover;
