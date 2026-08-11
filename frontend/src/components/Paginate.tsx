import { useNavigate } from "@tanstack/react-router";

interface PaginateProps {
	numItems: number;
	itemsPerPage?: number;
	current: number;
	onPageChange: (page: number) => void;
	updateUrl?: boolean;
}

function Paginate({
	numItems,
	itemsPerPage = Number(import.meta.env.VITE_PAGINATE_PER_PAGE),
	current,
	onPageChange,
	updateUrl = false,
}: PaginateProps) {
	const navigate = useNavigate();
	const numPages = Math.ceil(numItems / itemsPerPage);

	if (numPages <= 1) return null;

	const pages: number[] = [];
	for (let i = Math.max(1, current - 2); i <= Math.min(numPages, current + 2); i++) {
		pages.push(i);
	}

	const changePage = (page: number) => {
		onPageChange(page);
		if (updateUrl) {
			// biome-ignore lint/suspicious/noExplicitAny: generic component can't know calling route's search schema
			(navigate as any)({ search: (prev: any) => ({ ...prev, page }) });
		}
	};

	return (
		<div className="paginate-container">
			<div className="page-display">
				{current} of {numPages} &bull;
			</div>
			{current > 1 && (
				<button type="button" onClick={() => changePage(1)}>
					{"<< First"}
				</button>
			)}
			{current > 1 && (
				<button type="button" onClick={() => changePage(current - 1)}>
					{"<"}
				</button>
			)}
			{pages.map((page) => (
				<button
					type="button"
					key={page}
					className={page === current ? "current-page" : undefined}
					onClick={page !== current ? () => changePage(page) : undefined}
					disabled={page === current}
				>
					{page}
				</button>
			))}
			{current < numPages && (
				<button type="button" onClick={() => changePage(current + 1)}>
					{">"}
				</button>
			)}
			{current < numPages && (
				<button type="button" onClick={() => changePage(numPages)}>
					{"Last >>"}
				</button>
			)}
		</div>
	);
}

export default Paginate;
