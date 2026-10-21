import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import {
	Button,
	Dialog,
	Heading,
	Label,
	Modal,
	ModalOverlay,
	TextArea,
	TextField,
} from "react-aria-components";
import {
	fileReport,
	REPORT_DETAILS_MAX,
	REPORT_REASON_LABELS,
	REPORT_REASONS,
	type ReportReason,
	type ReportTargetType,
} from "#/queries/reports";
import styles from "./ReportDialog.module.css";
import { reportErrorMessage, reportFormError } from "./report-dialog";
import { Select } from "./Select";

type Props = {
	isOpen: boolean;
	onOpenChange: (isOpen: boolean) => void;
	targetType: ReportTargetType;
	targetId: number;
	/** What's being reported, in the dialog's words: "this post", "avatar of Bob". */
	targetLabel: string;
};

/** Controlled modal for reporting content to staff. */
export function ReportDialog({
	isOpen,
	onOpenChange,
	targetType,
	targetId,
	targetLabel,
}: Props) {
	return (
		<ModalOverlay
			className={styles["overlay"]}
			isOpen={isOpen}
			onOpenChange={onOpenChange}
			isDismissable
		>
			<Modal className={styles["modal"]}>
				<Dialog aria-label="Report content" className={styles["dialog"]}>
					{({ close }) => (
						<ReportForm
							targetType={targetType}
							targetId={targetId}
							targetLabel={targetLabel}
							onClose={close}
						/>
					)}
				</Dialog>
			</Modal>
		</ModalOverlay>
	);
}

// Mounted only while the dialog is open, so every opening starts fresh.
function ReportForm({
	targetType,
	targetId,
	targetLabel,
	onClose,
}: {
	targetType: ReportTargetType;
	targetId: number;
	targetLabel: string;
	onClose: () => void;
}) {
	// Nothing is preselected, so a reason is always a deliberate choice.
	const [reason, setReason] = useState<ReportReason | "">("");
	const [details, setDetails] = useState("");
	const [error, setError] = useState<string | null>(null);

	const report = useMutation({
		mutationFn: fileReport,
		onError: (exception) => setError(reportErrorMessage(exception)),
	});

	if (report.isSuccess) {
		return (
			<div className={styles["form"]}>
				<Heading slot="title" className={styles["title"]}>
					Report sent
				</Heading>
				<p>Thanks, staff will review it.</p>
				<div className={styles["actions"]}>
					<Button className="skew-btn" onPress={onClose}>
						Close
					</Button>
				</div>
			</div>
		);
	}

	return (
		<form
			className={styles["form"]}
			onSubmit={(e) => {
				e.preventDefault();
				// Portalled forms bubble submit through React to any surrounding form.
				e.stopPropagation();
				if (report.isPending) return;
				const problem = reportFormError(reason, details);
				// The empty-reason check narrows the type; the form error already covers it.
				if (problem || reason === "") {
					setError(problem);
					return;
				}
				setError(null);
				report.mutate({
					target_type: targetType,
					target_id: targetId,
					reason,
					details: details.trim() || undefined,
				});
			}}
		>
			<Heading slot="title" className={styles["title"]}>
				Report {targetLabel}
			</Heading>
			<div className={styles["field"]}>
				<span id="report-reason-label">Reason</span>
				<Select
					id="report-reason"
					ariaLabelledBy="report-reason-label"
					items={REPORT_REASONS}
					getId={(item) => item}
					getLabel={(item) => REPORT_REASON_LABELS[item]}
					selectedId={reason}
					onChange={(id) => setReason(id as ReportReason)}
					isDisabled={report.isPending}
				/>
			</div>
			<TextField
				className={styles["field"]}
				value={details}
				onChange={setDetails}
				isDisabled={report.isPending}
			>
				<Label>Details{reason === "other" ? "" : " (optional)"}</Label>
				<TextArea rows={4} maxLength={REPORT_DETAILS_MAX} />
				<span className={styles["counter"]}>
					{details.length}/{REPORT_DETAILS_MAX}
				</span>
			</TextField>
			{error && (
				<div className="error" role="alert">
					{error}
				</div>
			)}
			<div className={styles["actions"]}>
				<Button type="submit" className="skew-btn" isDisabled={report.isPending}>
					{report.isPending ? "Sending..." : "Submit"}
				</Button>
				<Button className="skew-btn" onPress={onClose} isDisabled={report.isPending}>
					Cancel
				</Button>
			</div>
		</form>
	);
}
