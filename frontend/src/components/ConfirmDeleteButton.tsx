import type { ReactNode } from "react";
import { Button, Dialog, DialogTrigger, Popover } from "react-aria-components";
import styles from "./ConfirmDeleteButton.module.css";

type Props = {
	/** Alt text for the cross icon, e.g. "Delete Character". */
	label: string;
	/** Explains what deleting does; shown in the confirm popover. */
	message: ReactNode;
	onConfirm: () => void;
	isDisabled?: boolean;
};

/** Cross icon that opens a confirm/cancel popover before calling `onConfirm`. */
export function ConfirmDeleteButton({ label, message, onConfirm, isDisabled }: Props) {
	return (
		<DialogTrigger>
			<Button isDisabled={isDisabled}>
				<img src="/images/icons/cross.png" alt={label} />
			</Button>
			<Popover
				className={`react-aria-Popover ${styles["confirm-popover"]}`}
				placement="bottom end"
			>
				<Dialog aria-label="Confirm delete" className={styles["confirm-delete"]}>
					{({ close }) => (
						<>
							<p>{message}</p>
							<div className={styles["confirm-actions"]}>
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
			</Popover>
		</DialogTrigger>
	);
}
