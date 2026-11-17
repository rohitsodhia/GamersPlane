import type { Editor } from "@tiptap/react";
import { useState } from "react";
import { CornerDownLeftIcon } from "#/components/tiptap/tiptap-icons/corner-down-left-icon";
import { Button } from "#/components/tiptap/tiptap-ui-primitive/button";
import { ButtonGroup } from "#/components/tiptap/tiptap-ui-primitive/button-group";
import {
	Card,
	CardBody,
	CardItemGroup,
} from "#/components/tiptap/tiptap-ui-primitive/card";
import { Input } from "#/components/tiptap/tiptap-ui-primitive/input";
import {
	Popover,
	PopoverContent,
	PopoverTrigger,
} from "#/components/tiptap/tiptap-ui-primitive/popover";
import { useTiptapEditor } from "#/hooks/use-tiptap-editor";

import "./youtube-popover.scss";

const NOT_YOUTUBE_MESSAGE = "That isn't a YouTube link";

/**
 * A toolbar button that opens a small popover to paste a YouTube link into; a valid
 * link inserts the video, anything else shows an error under the field. The trigger
 * toggles the popover (the primitive closes it on a second press).
 */
export function YoutubePopover({ editor: providedEditor }: { editor?: Editor | null }) {
	const { editor } = useTiptapEditor(providedEditor);
	const [isOpen, setIsOpen] = useState(false);
	const [url, setUrl] = useState("");
	const [error, setError] = useState<string | null>(null);

	if (!editor) return null;

	const handleOpenChange = (open: boolean) => {
		setIsOpen(open);
		if (open) setError(null);
	};

	const insert = () => {
		if (!editor.chain().focus().setYoutube({ url }).run()) {
			setError(NOT_YOUTUBE_MESSAGE);
			return;
		}
		setUrl("");
		setError(null);
		setIsOpen(false);
	};

	return (
		<Popover open={isOpen} onOpenChange={handleOpenChange}>
			<PopoverTrigger asChild>
				<Button
					type="button"
					variant="ghost"
					role="button"
					tabIndex={-1}
					aria-label="YouTube video"
					tooltip="YouTube video"
					data-active-state={isOpen ? "on" : "off"}
				>
					YouTube
				</Button>
			</PopoverTrigger>

			<PopoverContent
				collisionPadding={4}
				onCloseAutoFocus={(event) => {
					// Keep focus in the editor, at the video just inserted.
					event.preventDefault();
					editor.commands.focus();
				}}
			>
				<Card>
					<CardBody>
						<CardItemGroup orientation="horizontal">
							<Input
								type="text"
								inputMode="url"
								placeholder="Paste a YouTube link..."
								name="youtube_url"
							aria-label="YouTube link"
								aria-invalid={error ? true : undefined}
								aria-describedby={error ? "youtube-popover-error" : undefined}
								value={url}
								onChange={(event) => {
									setUrl(event.target.value);
									setError(null);
								}}
								onKeyDown={(event) => {
									if (event.key === "Enter") {
										event.preventDefault();
										insert();
									}
								}}
								autoFocus
								autoComplete="off"
								autoCorrect="off"
								autoCapitalize="off"
								className="tiptap-youtube-input"
							/>
							<ButtonGroup>
								<Button
									type="button"
									variant="ghost"
									title="Insert video"
									aria-label="Insert video"
									onClick={insert}
								>
									<CornerDownLeftIcon className="tiptap-button-icon" />
								</Button>
							</ButtonGroup>
						</CardItemGroup>
						{error && (
							<div
								id="youtube-popover-error"
								className="tiptap-youtube-error"
								role="alert"
							>
								{error}
							</div>
						)}
					</CardBody>
				</Card>
			</PopoverContent>
		</Popover>
	);
}
