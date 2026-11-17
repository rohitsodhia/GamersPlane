import type { Editor } from "@tiptap/react";
import { useEditorState } from "@tiptap/react";
import { useState } from "react";
import { safeImageLink } from "#/components/tiptap/tiptap-extension/image-extension";
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

import "./image-link-popover.scss";

const INVALID_LINK_MESSAGE = "Enter a full address starting with http:// or https://";

/** Makes the selected image a link to a bigger image or a page. Shown only while an image is selected. */
export function ImageLinkPopover({
	editor: providedEditor,
}: {
	editor?: Editor | null;
}) {
	const { editor } = useTiptapEditor(providedEditor);
	// Subscribed only so the control re-renders as the selection moves; whether it
	// shows is read from the editor itself below, because this state can be stale on
	// the first render.
	useEditorState({
		editor,
		selector: ({ editor }) => editor?.isActive("image") ?? false,
	});
	const [isOpen, setIsOpen] = useState(false);
	const [url, setUrl] = useState("");
	const [error, setError] = useState<string | null>(null);

	if (!editor?.isEditable || !editor.isActive("image")) return null;

	const currentHref: unknown = editor.getAttributes("image")["href"];
	const hasLink = safeImageLink(currentHref) !== null;

	const handleOpenChange = (open: boolean) => {
		setIsOpen(open);
		if (open) {
			setUrl(typeof currentHref === "string" ? currentHref : "");
			setError(null);
		}
	};

	const apply = () => {
		if (!editor.chain().focus().setImageLink(url).run()) {
			setError(INVALID_LINK_MESSAGE);
			return;
		}
		setError(null);
		setIsOpen(false);
	};

	const remove = () => {
		editor.chain().focus().unsetImageLink().run();
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
					aria-label="Image link"
					tooltip="Image link"
					data-active-state={hasLink ? "on" : "off"}
				>
					Image link
				</Button>
			</PopoverTrigger>

			<PopoverContent
				collisionPadding={4}
				onCloseAutoFocus={(event) => {
					// Keep focus in the editor, on the image.
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
								placeholder="https://..."
								name="image_link_url"
								aria-label="Image link address"
								aria-invalid={error ? true : undefined}
								aria-describedby={error ? "image-link-popover-error" : undefined}
								value={url}
								onChange={(event) => {
									setUrl(event.target.value);
									setError(null);
								}}
								onKeyDown={(event) => {
									if (event.key === "Enter") {
										event.preventDefault();
										apply();
									}
								}}
								autoFocus
								autoComplete="off"
								autoCorrect="off"
								autoCapitalize="off"
								className="tiptap-image-link-input"
							/>
							<ButtonGroup>
								<Button
									type="button"
									variant="ghost"
									title="Apply link"
									aria-label="Apply link"
									onClick={apply}
								>
									<CornerDownLeftIcon className="tiptap-button-icon" />
								</Button>
								<Button
									type="button"
									variant="ghost"
									aria-label="Remove link"
									title="Remove link"
									disabled={!hasLink}
									onClick={remove}
								>
									Remove link
								</Button>
							</ButtonGroup>
						</CardItemGroup>
						{error && (
							<div
								id="image-link-popover-error"
								className="tiptap-image-link-error"
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
