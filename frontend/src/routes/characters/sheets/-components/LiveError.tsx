/** Why a live field's last save failed, shown beside the field. */
export function LiveError({ error }: { error: string | null }) {
	return error ? (
		<span role="alert" className="char-sheet-live-error">
			{error}
		</span>
	) : null;
}
