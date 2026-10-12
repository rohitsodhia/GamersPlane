import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
	Button,
	Dialog,
	Heading,
	Input,
	Label,
	Modal,
	ModalOverlay,
	TextField,
} from "react-aria-components";
import { ApiError } from "#/lib/api";
import {
	createNpc,
	type NpcLibrary,
	npcsQueryKey,
	type QuickNpc,
} from "#/queries/quick-npcs";
import { NpcImageChooser } from "./NpcImageChooser";
import styles from "./QuickNpcModal.module.css";

const MAX_NAME_LENGTH = 100;

// Makes a quick NPC (a name and an optional image from the library). The server
// gets or creates the pair, so naming an existing one returns it. Knows nothing of
// where it was opened from: `onCreated` gets the NPC and the modal closes.
export function QuickNpcModal({
	library,
	isOpen,
	onOpenChange,
	initialName = "",
	onCreated,
}: {
	library: NpcLibrary;
	isOpen: boolean;
	onOpenChange: (isOpen: boolean) => void;
	initialName?: string;
	onCreated: (npc: QuickNpc) => void;
}) {
	return (
		<ModalOverlay
			className={styles["overlay"]}
			isOpen={isOpen}
			onOpenChange={onOpenChange}
			isDismissable
		>
			<Modal className={styles["modal"]}>
				<Dialog aria-label="New quick NPC" className={styles["dialog"]}>
					{({ close }) => (
						<NewNpcForm
							library={library}
							initialName={initialName}
							onCreated={(npc) => {
								onCreated(npc);
								close();
							}}
							onCancel={close}
						/>
					)}
				</Dialog>
			</Modal>
		</ModalOverlay>
	);
}

// Mounted only while the modal is open, so each opening starts from `initialName`.
function NewNpcForm({
	library,
	initialName,
	onCreated,
	onCancel,
}: {
	library: NpcLibrary;
	initialName: string;
	onCreated: (npc: QuickNpc) => void;
	onCancel: () => void;
}) {
	const queryClient = useQueryClient();
	const [name, setName] = useState(initialName);
	const [imageId, setImageId] = useState<number | null>(null);
	const [error, setError] = useState<string | null>(null);

	const trimmed = name.trim();
	const create = useMutation({
		mutationFn: () => createNpc(library, { name: trimmed, image_id: imageId }),
		onSuccess: (npc) => {
			queryClient.invalidateQueries({ queryKey: npcsQueryKey(library) });
			onCreated(npc);
		},
		onError: (exception) =>
			setError(
				exception instanceof ApiError && exception.errors[0]?.detail
					? exception.errors[0].detail
					: "Couldn't create the NPC.",
			),
	});

	return (
		<form
			className={styles["form"]}
			onSubmit={(e) => {
				e.preventDefault();
				// React bubbles this through the portal to a surrounding form (the post
				// form), which would otherwise submit the post.
				e.stopPropagation();
				if (trimmed !== "" && !create.isPending) {
					setError(null);
					create.mutate();
				}
			}}
		>
			<Heading slot="title" className={styles["title"]}>
				New quick NPC
			</Heading>
			<TextField
				className={styles["name"]}
				value={name}
				onChange={setName}
				isDisabled={create.isPending}
				autoFocus
			>
				<Label>Name</Label>
				<Input maxLength={MAX_NAME_LENGTH} />
			</TextField>
			<div className={styles["image"]}>
				<span>Image</span>
				<NpcImageChooser
					library={library}
					value={imageId}
					onChange={setImageId}
					isDisabled={create.isPending}
				/>
			</div>
			{error && (
				<div className="error" role="alert">
					{error}
				</div>
			)}
			<div className={styles["actions"]}>
				<Button
					type="submit"
					className="skew-btn"
					isDisabled={trimmed === "" || create.isPending}
				>
					{create.isPending ? "Creating..." : "Create"}
				</Button>
				<Button className="skew-btn" onPress={onCancel} isDisabled={create.isPending}>
					Cancel
				</Button>
			</div>
		</form>
	);
}
