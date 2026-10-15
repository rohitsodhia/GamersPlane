import type { ReactNode } from "react";
import { Dialog, Modal, ModalOverlay } from "react-aria-components";
import confirmStyles from "./ConfirmDeleteButton.module.css";
import styles from "./ConfirmDialog.module.css";

type Props = {
	isOpen: boolean;
	onOpenChange: (isOpen: boolean) => void;
	/** Explains what confirming does. */
	message: ReactNode;
	onConfirm: () => void;
};

/**
 * Controlled confirm/cancel modal, for confirming from somewhere that can't host
 * a trigger (e.g. a menu item). Same body as ConfirmDeleteButton's popover.
 */
export function ConfirmDialog({ isOpen, onOpenChange, message, onConfirm }: Props) {
	return (
		<ModalOverlay
			className={styles["overlay"]}
			isOpen={isOpen}
			onOpenChange={onOpenChange}
			isDismissable
		>
			<Modal className={styles["modal"]}>
				<Dialog aria-label="Confirm delete" className={confirmStyles["confirm-delete"]}>
					{({ close }) => (
						<>
							<p>{message}</p>
							<div className={confirmStyles["confirm-actions"]}>
								<button
									type="button"
									className="skew-btn"
									onClick={() => {
										onConfirm();
										close();
									}}
								>
									Confirm
								</button>
								<button type="button" className="skew-btn" onClick={close}>
									Cancel
								</button>
							</div>
						</>
					)}
				</Dialog>
			</Modal>
		</ModalOverlay>
	);
}
