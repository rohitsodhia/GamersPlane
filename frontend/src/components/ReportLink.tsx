import { useState } from "react";
import type { ReportTargetType } from "#/queries/reports";
import { ReportDialog } from "./ReportDialog";

/** A link-styled button that owns a ReportDialog for one target. */
export function ReportLink({
	targetType,
	targetId,
	targetLabel,
	children,
}: {
	targetType: ReportTargetType;
	targetId: number;
	/** What's being reported, in the dialog's words: "this post", "avatar of Bob". */
	targetLabel: string;
	children: string;
}) {
	const [isOpen, setIsOpen] = useState(false);
	return (
		<>
			<button type="button" className="link-btn" onClick={() => setIsOpen(true)}>
				{children}
			</button>
			<ReportDialog
				isOpen={isOpen}
				onOpenChange={setIsOpen}
				targetType={targetType}
				targetId={targetId}
				targetLabel={targetLabel}
			/>
		</>
	);
}
