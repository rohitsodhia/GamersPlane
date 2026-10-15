import { useNavigate } from "@tanstack/react-router";
import clsx from "clsx";
import { useState } from "react";
import { SEARCH_MAX_LENGTH } from "#/queries/search";
import styles from "./ForumSearchForm.module.css";

/**
 * Forum post search box. Submitting goes to the search page (page 1), even when
 * blank, where an empty search shows a prompt rather than doing nothing.
 */
function ForumSearchForm({
	initialValue = "",
	gameId,
	placeholder = "Search forums",
	showButton = true,
	className,
}: {
	initialValue?: string;
	gameId?: number;
	placeholder?: string;
	showButton?: boolean;
	className?: string;
}) {
	const navigate = useNavigate();
	const [value, setValue] = useState(initialValue);

	return (
		<form
			className={clsx(styles["search-form"], className)}
			onSubmit={(e) => {
				e.preventDefault();
				navigate({
					to: "/forums/search",
					search: { q: value.trim() || undefined, game_id: gameId },
				});
			}}
		>
			<input
				type="search"
				value={value}
				maxLength={SEARCH_MAX_LENGTH}
				placeholder={placeholder}
				aria-label={placeholder}
				onChange={(e) => setValue(e.target.value)}
			/>
			{showButton && (
				<button type="submit" className="skew-btn">
					Search
				</button>
			)}
		</form>
	);
}

export default ForumSearchForm;
