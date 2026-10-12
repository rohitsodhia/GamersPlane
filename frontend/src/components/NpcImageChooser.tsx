import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
	Button,
	FileTrigger,
	Input,
	TextField,
	ToggleButton,
	ToggleButtonGroup,
} from "react-aria-components";
import { ApiError } from "#/lib/api";
import {
	linkNpcImage,
	type NpcImage,
	type NpcLibrary,
	npcImagesQueryOptions,
	uploadNpcImage,
} from "#/queries/quick-npcs";
import styles from "./NpcImageChooser.module.css";

// Picks a quick NPC's image from a library (a game's or the viewer's own), or adds
// one to it (an upload, or a link the server downloads a copy of). A new image is
// selected on arrival. `value` is the chosen image's id; null is no image.
export function NpcImageChooser({
	library,
	value,
	onChange,
	isDisabled = false,
}: {
	library: NpcLibrary;
	value: number | null;
	onChange: (imageId: number | null) => void;
	isDisabled?: boolean;
}) {
	const queryClient = useQueryClient();
	const imagesQuery = npcImagesQueryOptions(library);
	const { data: images = [] } = useQuery(imagesQuery);
	const [url, setUrl] = useState("");
	const [error, setError] = useState<string | null>(null);

	const added = {
		onSuccess: (image: NpcImage) => {
			queryClient.setQueryData<NpcImage[]>(imagesQuery.queryKey, (cached) => [
				...(cached ?? []),
				image,
			]);
			setError(null);
			onChange(image.id);
		},
		onError: (exception: unknown) =>
			setError(
				exception instanceof ApiError && exception.errors[0]?.detail
					? exception.errors[0].detail
					: "Couldn't add the image.",
			),
	};
	const upload = useMutation({
		mutationFn: (file: File) => uploadNpcImage(library, file),
		...added,
	});
	const link = useMutation({
		mutationFn: (linked: string) => linkNpcImage(library, linked),
		...added,
		onSuccess: (image) => {
			added.onSuccess(image);
			setUrl("");
		},
	});

	const busy = isDisabled || upload.isPending || link.isPending;
	const submitLink = () => {
		const trimmed = url.trim();
		if (trimmed !== "" && !busy) link.mutate(trimmed);
	};

	return (
		<div className={styles["chooser"]}>
			<ToggleButtonGroup
				aria-label="Image"
				className={styles["images"]}
				selectionMode="single"
				disallowEmptySelection
				isDisabled={isDisabled}
				selectedKeys={[value === null ? "none" : String(value)]}
				onSelectionChange={(keys) => {
					const [key] = [...keys];
					if (key === undefined) return;
					onChange(key === "none" ? null : Number(key));
				}}
			>
				<ToggleButton id="none" className={styles["none"]}>
					No image
				</ToggleButton>
				{images.map((image, index) => (
					<ToggleButton
						key={image.id}
						id={String(image.id)}
						className={styles["thumb"]}
						aria-label={`Image ${index + 1}`}
					>
						<img src={image.url} alt="" />
					</ToggleButton>
				))}
			</ToggleButtonGroup>
			<div className={styles["add"]}>
				<FileTrigger
					acceptedFileTypes={["image/*"]}
					onSelect={(files) => {
						const file = files?.[0];
						if (file) upload.mutate(file);
					}}
				>
					<Button className={styles["button"]} isDisabled={busy}>
						{upload.isPending ? "Uploading..." : "Upload"}
					</Button>
				</FileTrigger>
				<TextField
					aria-label="Image URL"
					className={styles["url"]}
					value={url}
					onChange={setUrl}
					isDisabled={busy}
				>
					<Input
						placeholder="or paste an image link"
						onKeyDown={(e) => {
							if (e.key === "Enter") {
								// Inside the post form, where Enter would submit the post.
								e.preventDefault();
								submitLink();
							}
						}}
					/>
				</TextField>
				<Button
					className={styles["button"]}
					isDisabled={busy || url.trim() === ""}
					onPress={submitLink}
				>
					{link.isPending ? "Adding..." : "Add link"}
				</Button>
			</div>
			{error && (
				<div className="error" role="alert">
					{error}
				</div>
			)}
		</div>
	);
}
